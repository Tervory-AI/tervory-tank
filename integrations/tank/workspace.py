"""Workspace's code-first tools, assembled by Tank's existing Command/MCP registry."""
from __future__ import annotations

import asyncio
import csv
import io
import json
import re
from urllib.parse import urlencode
from functools import lru_cache
from types import SimpleNamespace
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, ValidationError

TOOLS = {}
FOUNDER_TOOLS = []
TENANT_ADMIN_TOOLS = []
TENANT_TOOLS = ('workspace.tasks', 'workspace.task.create', 'workspace.task.receipt',
                'workspace.savings', 'workspace.files', 'workspace.feedback', 'workspace.csv.parse',
                'workspace.data.run', 'workspace.data.retry', 'workspace.chat',
                'workspace.memory.view', 'workspace.memory.control', 'workspace.memory.edit',
                'workspace.memory.forget')
REQUEST_BODY_TOOLS = frozenset(TENANT_TOOLS)
CONFIRMED = frozenset({'workspace.task.create', 'workspace.feedback', 'workspace.data.run', 'workspace.data.retry'})


class Empty(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Page(Empty):
    limit: int = Field(default=50, ge=1, le=50)


class Files(Page):
    batch: str | None = Field(default=None, min_length=1, max_length=200)


class Create(Empty):
    title: str = Field(min_length=1, max_length=200, pattern=r'\S')
    request: str = Field(min_length=1, max_length=20000, pattern=r'\S')
    task_type: Literal['tier0.answer', 'tier0.draft', 'reason.brief'] = 'tier0.answer'
    memory_control: Literal['off', 'view', 'edit', 'forget'] | None = None


class Receipt(Empty):
    task_id: UUID


class Feedback(Empty):
    ledger_id: UUID
    verdict: Literal['useful', 'not_useful', 'wrong']
    note: str | None = Field(default=None, max_length=1000)


class CSV(Empty):
    text: str = Field(min_length=1, max_length=20000)


class Batch(Empty):
    batch: str = Field(min_length=1, max_length=200, pattern=r'\S')


class DataRun(Batch):
    records: list[dict[str, str]] = Field(min_length=1, max_length=500)
    preview: bool = True


class Chat(Empty):
    messages: list[dict] = Field(min_length=1, max_length=12)
    task_type: Literal['tier0.answer', 'tier0.draft', 'reason.brief'] = 'tier0.answer'
    memory_control: Literal['off', 'view', 'edit', 'forget'] | None = None


class MemoryView(Empty):
    task_key: str = Field(default='memory_control', min_length=1, max_length=120)
    memory_id: str | None = Field(default=None, min_length=1, max_length=80)
    memory_control: Literal['off', 'view', 'edit', 'forget'] = 'view'


class MemoryControlSet(Empty):
    control: Literal['off', 'view', 'edit', 'forget']


class MemoryForget(Empty):
    memory_id: str = Field(min_length=1, max_length=80)
    memory_control: Literal['forget'] = 'forget'


class MemoryEdit(Empty):
    memory_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=20000, pattern=r'\S')
    memory_control: Literal['edit', 'forget'] | None = None


SCHEMAS = dict(zip(TENANT_TOOLS, (Page, Create, Receipt, Empty, Files, Feedback, CSV, DataRun, Batch,
                                  Chat, MemoryView, MemoryControlSet, MemoryEdit, MemoryForget)))
POST = frozenset({'workspace.task.create', 'workspace.feedback', 'workspace.csv.parse',
                  'workspace.data.run', 'workspace.data.retry', 'workspace.chat',
                  'workspace.memory.control', 'workspace.memory.edit', 'workspace.memory.forget'})


def adapters(command):
    return {tool: command.Adapter('POST' if tool in POST else 'GET',
            '/v1/command/workspace/' + tool.removeprefix('workspace.'), schema, tool,
            tool in {'workspace.task.create', 'workspace.data.run', 'workspace.data.retry'},
            'paid_run' if tool in {'workspace.task.create', 'workspace.chat', 'workspace.data.run', 'workspace.data.retry'} else 'other')
            for tool, schema in SCHEMAS.items()}


@lru_cache(maxsize=128)
def parse_command(tenant: str, user: str, text: str) -> tuple[str, str]:
    # Only deterministic syntax is cached. Mutable reads and writes never are.
    match = re.fullmatch(r'\s*(workspace\.[a-z.]+)\s*(\{.*\})?\s*', text, re.S)
    if not match or match[1] not in SCHEMAS:
        raise HTTPException(422, 'Choose an available Workspace tool and JSON arguments.')
    try:
        args = json.loads(match[2] or '{}')
        value = SCHEMAS[match[1]].model_validate(args).model_dump(mode='json', exclude_none=True)
    except (ValueError, ValidationError):
        raise HTTPException(422, 'Check the Workspace tool arguments.') from None
    return match[1], json.dumps(value, separators=(',', ':'), ensure_ascii=False)


async def record(actor, source, output, *, task_id=None, cached=False, pending=False):
    from agent_skills import input_encoding
    from main import box_region, pool
    encoding = input_encoding()
    # Comparison tokens describe the hypothetical paid default, never actual use.
    row = await pool().fetchrow(
        'INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,'
        'tokens_in,tokens_out,task_id,cache_hit,comparison_tokens_in,comparison_tokens_out,outcome) '
        'VALUES($1,$2,\'workspace\',\'command.turn\',$3,$4,0,0,0,$5,$6,$7,$8,$9) '
        'RETURNING id,cost_usd,baseline_cost_usd,baseline_status',
        actor.tenant_id, box_region(), 4 if cached else 3, 'cache' if cached else 'code',
        task_id, cached, len(encoding.encode(source)), len(encoding.encode(output)),
        'unverified' if pending else 'delivered')
    return {**dict(row), 'id': str(row['id'])}


async def finish_receipt(actor, receipt, result, *, failed=False):
    from agent_skills import input_encoding
    from main import pool
    output = json.dumps(result, separators=(',', ':'), ensure_ascii=False, default=str)
    row = await pool().fetchrow(
        'UPDATE tank.ledger SET comparison_tokens_out=$3,outcome=$4 '
        'WHERE id=$1 AND tenant_id=$2 RETURNING id,cost_usd,baseline_cost_usd,baseline_status',
        UUID(receipt['id']), actor.tenant_id, len(input_encoding().encode(output)),
        'failed' if failed else 'delivered')
    return {**dict(row), 'id': str(row['id'])}


async def code_plan(actor, messages, task_id):
    from command import authorized_actor, PlannedAction, validate_action
    last = messages[-1] if messages else {}
    text = last.get('content', '')
    if last.get('role') != 'user' or not re.match(r'\s*workspace\.', text, re.I):
        return None
    if len(text) > 24000:
        raise HTTPException(422, 'Workspace requests must be at most 24,000 characters.')
    actor = await authorized_actor(actor)
    tool, raw = parse_command(str(actor.tenant_id), actor.user_id, text)
    # Recheck permissions even on a cache hit, before any receipt or dispatch.
    action = validate_action(PlannedAction(tool=tool, arguments=json.loads(raw)), actor)
    content = json.dumps({'text': '', 'actions': [action.model_dump(mode='json')]}, separators=(',', ':'))
    receipt = await record(actor, text, content, task_id=task_id)
    return SimpleNamespace(content=content, ledger_id=UUID(receipt['id']))


@lru_cache(maxsize=64)
def parse_csv(tenant: str, user: str, text: str) -> str:
    try:
        rows = list(csv.reader(io.StringIO(text, newline=''), strict=True))
        if not rows or not rows[0] or len(rows) > 501 or len(rows[0]) > 50:
            raise ValueError
        headers = rows[0]
        if any(not h.strip() for h in headers) or len(set(headers)) != len(headers):
            raise ValueError
        if any(len(row) != len(headers) for row in rows[1:]):
            raise ValueError
    except (ValueError, csv.Error):
        raise HTTPException(422, 'Use a CSV with unique headers, at most 500 rows and 50 columns.') from None
    # Treat cells as data; never evaluate formulas or follow links.
    return json.dumps({'columns': headers, 'rows': [dict(zip(headers, row)) for row in rows[1:]]},
                      separators=(',', ':'), ensure_ascii=False)


async def base_request(actor, operation, data, *, method='GET'):
    import main
    # Existing room proxy owns the room key and route allowlist. Its identity is
    # always server-bound; caller-provided tenant/user fields are forbidden.
    from starlette.requests import Request
    payload = json.dumps({**data, 'tenant_id': str(actor.tenant_id), 'created_by': actor.user_id}).encode() if method == 'POST' else b''
    query = urlencode({**data, 'tenant_id': str(actor.tenant_id)}).encode() if method == 'GET' else b''
    async def receive():
        return {'type': 'http.request', 'body': payload, 'more_body': False}
    request = Request({'type': 'http', 'method': method, 'path': '/v1/base/' + operation,
                       'query_string': query, 'headers': [(b'content-type', b'application/json')]}, receive)
    response = await main.base_proxy(operation, request)
    if not 200 <= response.status_code < 300:
        raise HTTPException(response.status_code, 'Data action could not finish. Check its status before retrying.')
    if len(response.body) > 240000:
        raise HTTPException(413, 'Data result is too large. Use a smaller page.')
    return json.loads(response.body)




def _refuse_args_impersonation(gates_memory, actor, data: dict):
    """Client-supplied tenant/user/created_by must match the authorized actor or be absent."""
    claimed_tenant = data.get('tenant_id') or data.get('x-tervory-tenant')
    claimed_user = data.get('user_id') or data.get('created_by') or data.get('x-tervory-user')
    return gates_memory.refuse_client_impersonation(
        session_tenant_id=actor.tenant_id,
        session_user_id=actor.user_id,
        claimed_tenant_id=claimed_tenant,
        claimed_user_id=claimed_user,
    )


def _workspace_memory(main_mod):
    """Reuse Tank's injected memory client, else build MemoryClient with the Workspace agent key.

    Writes go to Hermes (/memories, /recall) authenticated by TANK_KEY_WORKSPACE —
    never Tank /v1/memory and never the shared TANK_API_KEY.
    """
    memory = getattr(main_mod, "memory", None)
    if memory is not None:
        return memory
    app = getattr(main_mod, "app", None)
    if app is not None:
        memory = getattr(getattr(app, "state", None), "memory", None)
        if memory is not None:
            return memory
    try:
        from integrations.workspace.memory_client import build_workspace_memory_client
        return build_workspace_memory_client()
    except Exception:
        return None


class _BracketImportError(RuntimeError):
    """Raised when gates_memory/request_path cannot be imported (memory outage class)."""


def _load_memory_bracket():
    from integrations.workspace import gates_memory, request_path
    return gates_memory, request_path



def _memory_unavailable_bracket(paid: dict, *, reason: str) -> dict:
    """Receipt marker for answering through Tank with no memory during an outage."""
    return {
        'memory_unavailable': True,
        'memory_status': 'memory unavailable',
        'reason': reason,
        'answered_from_memory': False,
        'paid_calls': 1,
        'cost_usd': float(paid.get('cost_usd') or 0),
        'tokens_in': int(paid.get('tokens_in') or 0),
        'tokens_out': int(paid.get('tokens_out') or 0),
        'steps': [
            {'action': 'memory_unavailable', 'reason': reason},
            {'action': 'tank_agent', 'status': 'done'},
        ],
        # Never identical_reuse during outage.
        'identical_reuse': False,
    }


async def _run_task_create_with_memory(actor, args, main_mod):
    """Task create: free steps then Tank agent. Auth/scope refuse; memory outage degrades."""
    async def tank_create(task):
        created = await main_mod.create_task(main_mod.TaskCreate(
            tenant_id=actor.tenant_id,
            created_by=actor.user_id,
            title=task['title'],
            task_type=task.get('task_type') or args.task_type,
            messages=[main_mod.Message(role='user', content=task['request'])],
        ))
        cost = float(getattr(created, 'cost_usd', None) or (created.get('cost_usd') if isinstance(created, dict) else 0) or 0)
        tokens_in = int(getattr(created, 'tokens_in', None) or (created.get('tokens_in') if isinstance(created, dict) else 0) or 0)
        tokens_out = int(getattr(created, 'tokens_out', None) or (created.get('tokens_out') if isinstance(created, dict) else 0) or 0)
        payload = created if isinstance(created, dict) else dict(created)
        return {
            'cost_usd': cost,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'result': {
                'conversations': [task['request'][:200]],
                'projects': [task['title']],
                'files': ['task-board'],
                'outcome': payload.get('result') or payload.get('id') or 'task-created',
                'task': payload,
            },
        }

    task = {
        'title': args.title,
        'request': args.request,
        'task_type': args.task_type,
        'messages': [{'role': 'user', 'content': args.request}],
    }

    try:
        gates_memory, request_path = _load_memory_bracket()
    except _BracketImportError as exc:
        paid = await tank_create(task)
        result = (paid.get('result') or {}).get('task') or paid.get('result') or {}
        return {**result, 'memory_bracket': _memory_unavailable_bracket(paid, reason=str(exc))}

    try:
        tenant, user = gates_memory.require_authenticated_scope(
            tenant_id=actor.tenant_id, user_id=actor.user_id)
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(401, str(exc)) from exc

    if not gates_memory.memory_enabled_env():
        paid = await tank_create(task)
        return (paid.get('result') or {}).get('task') or paid.get('result') or {}

    memory = _workspace_memory(main_mod)
    if memory is None:
        paid = await tank_create(task)
        result = (paid.get('result') or {}).get('task') or paid.get('result') or {}
        return {**result, 'memory_bracket': _memory_unavailable_bracket(
            paid, reason='Workspace memory client unavailable')}

    try:
        bracket = await request_path.run_task_request(
            memory,
            tenant_id=tenant,
            user_id=user,
            title=args.title,
            request=args.request,
            task_type=args.task_type,
            memory_control=getattr(args, 'memory_control', None),
            tank_create=tank_create,
        )
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(401, str(exc)) from exc
    except gates_memory.MemoryOutageError as exc:
        # If a paid call already completed inside the bracket, never retry it.
        already = getattr(exc, 'paid_receipt', None)
        if isinstance(already, dict) and int(already.get('paid_calls') or 0) >= 1:
            bracket = already
        else:
            paid = await tank_create(task)
            result = (paid.get('result') or {}).get('task') or paid.get('result') or {}
            return {**result, 'memory_bracket': _memory_unavailable_bracket(paid, reason=str(exc))}

    result = (bracket.get('result') or {}).get('task') or bracket.get('result') or {}
    unavailable = bool(bracket.get('memory_unavailable'))
    return {**result, 'memory_bracket': {
        'steps': bracket.get('steps'),
        'paid_calls': bracket.get('paid_calls'),
        'cost_usd': bracket.get('cost_usd'),
        'tokens_in': bracket.get('tokens_in'),
        'tokens_out': bracket.get('tokens_out'),
        'answered_from_memory': bracket.get('answered_from_memory'),
        'memory_control': bracket.get('memory_control'),
        'input_fingerprint': bracket.get('input_fingerprint'),
        'memory_unavailable': unavailable,
        'memory_status': 'memory unavailable' if unavailable else 'ok',
    }}


async def _run_chat_with_memory(actor, args, main_mod):
    """Chat: free steps then Tank agent. Auth/scope refuse; memory outage degrades."""
    async def tank_route(task):
        messages = task.get('messages') or [{'role': 'user', 'content': task['request']}]
        routed = await main_mod.route(
            tenant_id=actor.tenant_id,
            agent='tier0',
            task_type=task.get('task_type') or args.task_type,
            messages=messages,
        )
        payload = routed if isinstance(routed, dict) else dict(routed)
        return {
            'cost_usd': float(payload.get('cost_usd') or 0),
            'tokens_in': int(payload.get('tokens_in') or 0),
            'tokens_out': int(payload.get('tokens_out') or 0),
            'result': {
                'conversations': [task.get('request', '')[:200]],
                'projects': ['chat'],
                'files': ['chat-thread'],
                'outcome': payload.get('content') or payload.get('answer') or 'chat-done',
                'route': payload,
            },
        }

    content = '\n'.join(
        str(m.get('content', '')).strip()
        for m in list(args.messages)
        if isinstance(m, dict) and str(m.get('content', '')).strip()
    ) or 'chat'
    task = {
        'title': 'chat',
        'request': content,
        'task_type': args.task_type,
        'messages': list(args.messages),
    }

    try:
        gates_memory, request_path = _load_memory_bracket()
    except _BracketImportError as exc:
        paid = await tank_route(task)
        route_result = (paid.get('result') or {}).get('route') or paid.get('result') or {}
        return {**route_result, 'memory_bracket': _memory_unavailable_bracket(paid, reason=str(exc))}

    try:
        tenant, user = gates_memory.require_authenticated_scope(
            tenant_id=actor.tenant_id, user_id=actor.user_id)
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(401, str(exc)) from exc

    if not gates_memory.memory_enabled_env():
        paid = await tank_route(task)
        return (paid.get('result') or {}).get('route') or paid.get('result') or {}

    memory = _workspace_memory(main_mod)
    if memory is None:
        paid = await tank_route(task)
        route_result = (paid.get('result') or {}).get('route') or paid.get('result') or {}
        return {**route_result, 'memory_bracket': _memory_unavailable_bracket(
            paid, reason='Workspace memory client unavailable')}

    try:
        bracket = await request_path.run_chat_request(
            memory,
            tenant_id=tenant,
            user_id=user,
            messages=list(args.messages),
            task_type=args.task_type,
            memory_control=args.memory_control,
            tank_route=tank_route,
        )
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(401, str(exc)) from exc
    except gates_memory.MemoryOutageError as exc:
        already = getattr(exc, 'paid_receipt', None)
        if isinstance(already, dict) and int(already.get('paid_calls') or 0) >= 1:
            bracket = already
        else:
            paid = await tank_route(task)
            route_result = (paid.get('result') or {}).get('route') or paid.get('result') or {}
            return {**route_result, 'memory_bracket': _memory_unavailable_bracket(paid, reason=str(exc))}

    route_result = ((bracket.get('result') or {}).get('route') if isinstance(bracket.get('result'), dict) else None) or bracket.get('result') or {}
    unavailable = bool(bracket.get('memory_unavailable'))
    return {**route_result, 'memory_bracket': {
        'steps': bracket.get('steps'),
        'paid_calls': bracket.get('paid_calls'),
        'cost_usd': bracket.get('cost_usd'),
        'tokens_in': bracket.get('tokens_in'),
        'tokens_out': bracket.get('tokens_out'),
        'answered_from_memory': bracket.get('answered_from_memory'),
        'memory_control': bracket.get('memory_control'),
        'input_fingerprint': bracket.get('input_fingerprint'),
        'memory_unavailable': unavailable,
        'memory_status': 'memory unavailable' if unavailable else 'ok',
    }}


def _require_memory(main_mod):
    """For memory.* tools only: outage returns 503 (no Tank agent substitute)."""
    memory = _workspace_memory(main_mod)
    if memory is None:
        raise HTTPException(503, 'Workspace memory is unavailable.')
    return memory


async def _run_memory_view(actor, args, main_mod, *, raw: dict | None = None):
    try:
        gates_memory, _ = _load_memory_bracket()
    except _BracketImportError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        tenant, user = _refuse_args_impersonation(gates_memory, actor, raw or {})
        result = await gates_memory.apply_memory_view(
            _require_memory(main_mod),
            tenant_id=tenant,
            user_id=user,
            task_key=args.task_key,
            memory_id=getattr(args, 'memory_id', None),
            memory_control=args.memory_control,
        )
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(403, str(exc)) from exc
    except gates_memory.MemoryOutageError as exc:
        raise HTTPException(503, str(exc)) from exc
    return result


async def _run_memory_control(actor, args, main_mod, *, raw: dict | None = None):
    try:
        gates_memory, _ = _load_memory_bracket()
    except _BracketImportError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        tenant, user = _refuse_args_impersonation(gates_memory, actor, raw or {})
        memory = _require_memory(main_mod)
        saved = await gates_memory.set_memory_control(
            memory,
            tenant_id=tenant,
            user_id=user,
            control=args.control,
            claimed_tenant_id=(raw or {}).get('tenant_id'),
            claimed_user_id=(raw or {}).get('user_id') or (raw or {}).get('created_by'),
        )
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(403, str(exc)) from exc
    except gates_memory.MemoryOutageError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {'tenant_id': tenant, 'user_id': user, 'memory_control': args.control, 'saved': saved}


async def _run_memory_edit(actor, args, main_mod, *, raw: dict | None = None):
    try:
        gates_memory, _ = _load_memory_bracket()
    except _BracketImportError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        tenant, user = _refuse_args_impersonation(gates_memory, actor, raw or {})
        memory = _require_memory(main_mod)
        result = await gates_memory.apply_memory_edit(
            memory,
            memory_id=args.memory_id,
            tenant_id=tenant,
            user_id=user,
            text=args.text,
            memory_control=getattr(args, 'memory_control', None),
        )
    except gates_memory.MemoryControlError as exc:
        raise HTTPException(403, str(exc)) from exc
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(403, str(exc)) from exc
    except gates_memory.MemoryOutageError as exc:
        raise HTTPException(503, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {'tenant_id': tenant, 'user_id': user, **result}


async def _run_memory_forget(actor, args, main_mod, *, raw: dict | None = None):
    try:
        gates_memory, _ = _load_memory_bracket()
    except _BracketImportError as exc:
        raise HTTPException(503, str(exc)) from exc
    try:
        tenant, user = _refuse_args_impersonation(gates_memory, actor, raw or {})
        memory = _require_memory(main_mod)
        await gates_memory.apply_memory_forget(
            memory,
            memory_id=args.memory_id,
            tenant_id=tenant,
            user_id=user,
            memory_control=args.memory_control,
        )
    except gates_memory.MemoryControlError as exc:
        raise HTTPException(403, str(exc)) from exc
    except gates_memory.MemoryScopeError as exc:
        raise HTTPException(403, str(exc)) from exc
    except gates_memory.MemoryOutageError as exc:
        raise HTTPException(503, str(exc)) from exc
    return {'tenant_id': tenant, 'user_id': user, 'memory_id': args.memory_id, 'forgotten': True}


async def execute(tool, data, actor, *, claims: dict | None = None):
    import command
    import main
    actor = await command.authorized_actor(actor)
    command.require_tool(actor, tool)
    args = SCHEMAS[tool].model_validate(data)
    raw_claims = {}
    if isinstance(data, dict):
        raw_claims.update(data)
    if claims:
        raw_claims.update({k: v for k, v in claims.items() if v is not None})
    if tool in CONFIRMED:
        from trigger_commands import confirmation
        confirmation(actor, tool, args.model_dump(mode='json', exclude_none=True))
    # Code receipts are written before dispatch so lost acknowledgements cannot
    # erase evidence. Command's durable confirmation path prevents replaying writes.
    source = tool + ' ' + args.model_dump_json(exclude_none=True)
    output = None
    cached = False
    csv_error = None
    if tool == 'workspace.csv.parse':
        hits = parse_csv.cache_info().hits
        try:
            output = parse_csv(str(actor.tenant_id), actor.user_id, args.text)
            cached = parse_csv.cache_info().hits > hits
        except HTTPException as error:
            csv_error = error
    receipt = await record(actor, source, output or '', cached=cached, pending=True)
    try:
        if csv_error is not None:
            raise csv_error
        async with asyncio.timeout(30):
            if tool == 'workspace.tasks':
                result = {'tasks': await main.list_tasks(actor.tenant_id, args.limit)}
            elif tool == 'workspace.task.create':
                result = await _run_task_create_with_memory(actor, args, main)
            elif tool == 'workspace.chat':
                result = await _run_chat_with_memory(actor, args, main)
            elif tool == 'workspace.memory.view':
                result = await _run_memory_view(actor, args, main, raw=raw_claims)
            elif tool == 'workspace.memory.control':
                result = await _run_memory_control(actor, args, main, raw=raw_claims)
            elif tool == 'workspace.memory.edit':
                result = await _run_memory_edit(actor, args, main, raw=raw_claims)
            elif tool == 'workspace.memory.forget':
                result = await _run_memory_forget(actor, args, main, raw=raw_claims)
            elif tool == 'workspace.task.receipt':
                result = await command.task_receipts(args.task_id, actor)
            elif tool == 'workspace.savings':
                from proof import client_savings
                result = await client_savings(actor.tenant_id)
            elif tool == 'workspace.feedback':
                result = await main.ledger_feedback(args.ledger_id, main.Feedback(tenant_id=actor.tenant_id,
                    by=actor.user_id, verdict=args.verdict, feedback='accepted' if args.verdict == 'useful' else 'rejected', note=args.note))
            elif tool == 'workspace.files':
                # The existing Base adapter already owns its authorization, deadlines,
                # and data query. No new provider or filesystem path is introduced.
                result = {'records': await base_request(actor, 'records', args.model_dump(exclude_none=True))}
            elif tool == 'workspace.data.run':
                result = await base_request(actor, 'run', args.model_dump(), method='POST')
            elif tool == 'workspace.data.retry':
                result = await base_request(actor, 'retry', args.model_dump(), method='POST')
            else:
                result = json.loads(output)
    except BaseException as error:
        receipt = await finish_receipt(actor, receipt, {'status': 'failed'}, failed=True)
        if not isinstance(error, Exception):
            raise
        status = error.status_code if isinstance(error, HTTPException) else 503
        message = 'Workspace could not finish this action. Check its receipt before trying again.'
        if isinstance(error, HTTPException) and error.detail == 'Missing setting: TANK_KEY_BASE':
            message = error.detail
        raise HTTPException(status, {'ledger_id': receipt['id'], 'message': message}) from None
    receipt = await finish_receipt(actor, receipt, result)
    if tool == 'workspace.task.receipt':
        result = {**result, 'ledger_ids': [row['ledger_id'] for row in result.get('rows', [])]}
    return {**result, 'ledger_id': receipt['id'], 'receipt': {
        'cost_usd': receipt['cost_usd'], 'baseline_cost_usd': receipt['baseline_cost_usd'],
        'baseline_status': receipt['baseline_status']}}


def build_router():
    import command
    router = APIRouter(prefix='/v1/command/workspace', tags=['workspace'])

    def endpoint(tool):
        async def run(request: Request, actor=Depends(command.identity)):
            try:
                if request.method == 'GET':
                    data = dict(request.query_params)
                else:
                    body = bytearray()
                    async with asyncio.timeout(10):
                        async for chunk in request.stream():
                            body.extend(chunk)
                            if len(body) > 32000:
                                raise HTTPException(413, 'Workspace arguments are too large.')
                    data = json.loads(body)
                claims = {
                    'x-tervory-tenant': request.headers.get('x-tervory-tenant'),
                    'x-tervory-user': request.headers.get('x-tervory-user'),
                }
                return await execute(tool, data, actor, claims=claims)
            except (ValueError, ValidationError):
                raise HTTPException(422, 'Check the Workspace tool arguments.') from None
            except (TimeoutError, OSError):
                raise HTTPException(503, 'Workspace could not finish this action. Check its receipt before trying again.') from None
        return run

    for tool in TENANT_TOOLS:
        router.add_api_route('/' + tool.removeprefix('workspace.'), endpoint(tool),
                             methods=['POST' if tool in POST else 'GET'], name=tool)
    return router
