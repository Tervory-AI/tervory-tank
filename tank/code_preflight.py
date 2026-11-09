"""Gate before: preflight controls ahead of the first paid code model call.

Six controls for the signed Command code path (OPLI, the desktop window and any
product that writes code or pages): intent triage, task splitter, plan first,
scope lock, cost quote and a budget per task. Everything here is deterministic
local code (Tank's code rung, recorded at $0); nothing in this module chooses,
names or calls a model. State lives in the existing tenant/user-owned Command
thread transaction, after the durable request reservation, exactly like
code_gate. Off unless ENGINE_CODE_PREFLIGHT_ENABLED is the literal `true`.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import uuid
from decimal import Decimal

from fastapi import HTTPException

SETTING = 'ENGINE_CODE_PREFLIGHT_ENABLED'
BUDGET_TOKENS = 'ENGINE_CODE_BUDGET_TOKENS'
BUDGET_USD = 'ENGINE_CODE_BUDGET_USD'
TASK_TYPE = 'command.code'
MAX_TASKS = 8
MAX_FILES = 20  # the same bound as one propose_edit diff
MAX_TURNS = 200
SYSTEM_TOKENS = 4000  # estimate for the fixed code instructions and catalogue
BYTES_PER_TOKEN = 4
NAMESPACE = uuid.UUID('733d3207-8d13-4503-bc5e-d4f3846eacb8')
ANSWER_ROOM = 39000

QUESTION = ('Which file, function or behaviour should change, and how will you know it works? '
            'Reply with those details and the work will be planned before any paid model call.')
LABELS = {
    'question': 'Clarifying question', 'too_many_tasks': 'Too many separate asks', 'listing': 'Planning: listing files',
    'needs_files': 'Plan needs files', 'outside_plan': 'Refused outside the plan', 'setting': 'Budget setting invalid',
    'no_policy': 'No routing policy', 'awaiting_approval': 'Plan and quote waiting for approval',
    'declined': 'Paid step declined', 'paid_paused': 'Paid work paused', 'price_unknown': 'Price not set',
    'budget': 'Task budget reached', 'turn_limit': 'Task round limit reached', 'complete': 'All tasks done',
}
EXTENSIONS = frozenset(('py', 'pyi', 'js', 'jsx', 'ts', 'tsx', 'mjs', 'cjs', 'json', 'md', 'mdx', 'yml', 'yaml',
                        'toml', 'sql', 'sh', 'css', 'scss', 'html', 'htm', 'go', 'rs', 'java', 'kt', 'rb', 'php',
                        'c', 'h', 'cc', 'cpp', 'hpp', 'cs', 'swift', 'txt', 'ini', 'cfg', 'vue', 'svelte', 'xml',
                        'csv', 'lock', 'gradle', 'tf', 'proto', 'graphql', 'svg'))
NAMES = frozenset(('Dockerfile', 'Makefile', 'Procfile', 'Gemfile', 'LICENSE'))
SEGMENT = re.compile(r'[\w.\-]+')
TOKEN = re.compile(r'[^\s`\'"(),;:<>\[\]{}]+')
CONCRETE = [re.compile(pattern) for pattern in (
    r'`[^`\n]+`', r'\b[a-z][a-z0-9]*_[a-z0-9_]+\b', r'\b[a-z]+[A-Z][A-Za-z0-9]*\b', r'\b[A-Z][a-z0-9]+[A-Z]\w*\b',
    r'\b\w+\(\)', r'\b\w*(?:Error|Exception)\b|Traceback', r'\bline \d+\b', r'"[^"\n]{3,}"', r'#\d+\b')]
VAGUE_WORDS = frozenset(('something', 'somehow', 'stuff', 'whatever', 'etc', 'things', 'everything'))
# Linear-time markers only: no nested or adjacent quantifiers over user text.
LIST_MARKER = re.compile(r'(?:[-*\u2022]|\d{1,2}[.)])(?=\s)')
JOINERS = ('also', 'then', 'next', 'additionally', 'separately', 'finally')
STOP = frozenset(('the', 'and', 'for', 'with', 'that', 'this', 'from', 'into', 'add', 'fix', 'make', 'use', 'when',
                  'should', 'please', 'file', 'files', 'code', 'change', 'update', 'all', 'new', 'not', 'are', 'can',
                  'our', 'its', 'has', 'have', 'then', 'also', 'any', 'out', 'more', 'less', 'one', 'two'))
DIFF_PATH = re.compile(r'^(?:---|\+\+\+) (?:[ab]/)?(\S+)', re.M)


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


class SettingError(ValueError):
    pass


def budget() -> dict:
    """Per-task caps by setting name; blank or unset means no cap on that measure."""
    cap = {}
    tokens = os.environ.get(BUDGET_TOKENS, '')
    if tokens != '':
        if not re.fullmatch(r'[1-9][0-9]{0,11}', tokens):
            raise SettingError(BUDGET_TOKENS)
        cap['tokens'] = int(tokens)
    usd = os.environ.get(BUDGET_USD, '')
    if usd != '':
        if not re.fullmatch(r'(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,6})?', usd) or Decimal(usd) <= 0:
            raise SettingError(BUDGET_USD)
        cap['usd'] = Decimal(usd)
    return cap


def norm(path) -> str | None:
    """A relative path inside the selected folder, or None."""
    if not isinstance(path, str) or not path or len(path) > 500 or '\\' in path:
        return None
    path = path[2:] if path.startswith('./') else path
    parts = path.split('/')
    if path.startswith(('/', '~')) or any(part in ('', '.', '..') or not SEGMENT.fullmatch(part) for part in parts):
        return None
    return path


def code_path(token: str) -> str | None:
    path = norm(token.rstrip('.'))
    if path is None:
        return None
    name = path.rsplit('/', 1)[-1]
    if name in NAMES:
        return path
    stem, dot, extension = name.rpartition('.')
    return path if dot and stem and extension in EXTENSIONS else None


def paths_in(text: str) -> list[str]:
    found = (code_path(token) for token in TOKEN.findall(text))
    return list(dict.fromkeys(path for path in found if path))[:MAX_FILES]


def vague(text: str) -> bool:
    """Deterministic intent triage: no concrete target and too short or hand-wavy."""
    if paths_in(text) or any(pattern.search(text) for pattern in CONCRETE):
        return False
    words = re.findall(r'[A-Za-z0-9]+', text.lower())
    return len(words) < 8 or bool(VAGUE_WORDS.intersection(words))


def split(text: str) -> list[str]:
    """Separate asks: a list of two or more items, or sentences joined by Also/Then/Next."""
    items: list[str] = []
    preamble: list[str] = []
    for line in text.splitlines():
        match = LIST_MARKER.match(line.strip())
        if match and line.strip()[match.end():].strip():
            items.append(line.strip()[match.end():].strip())
        elif line.strip() and items:
            items[-1] += '\n' + line.strip()
        elif line.strip():
            preamble.append(line.strip())
    if len(items) >= 2:
        context = ' '.join(preamble)
        return [context + '\n' + item if context else item for item in items]
    parts = [part.strip() for part in sentences(text) if part.strip()]
    return parts if len(parts) >= 2 else [text.strip()]


def sentences(text: str) -> list[str]:
    """Split after . ! ? ; when the next word is a joiner (one linear scan)."""
    parts, start, index = [], 0, 0
    while index < len(text):
        if text[index] in '.!?;' and index + 1 < len(text) and text[index + 1].isspace():
            after = index + 1
            while after < len(text) and text[after].isspace():
                after += 1
            word = re.match(r'[A-Za-z]+', text[after:after + 16])
            if word and word.group(0).lower() in JOINERS:
                parts.append(text[start:index + 1])
                start = after
            index = after
            continue
        index += 1
    parts.append(text[start:])
    return parts


def words(text: str) -> set[str]:
    spaced = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', text)
    return {word for word in re.findall(r'[a-z][a-z0-9]{2,}', spaced.lower()) if word not in STOP}


def match_files(text: str, names) -> list[str]:
    """Plan from a local listing: the files sharing the most words with the ask."""
    wanted = words(text)
    scored = []
    for name in names if isinstance(names, list) else []:
        path = norm(name)
        if path is None:
            continue
        score = len(wanted & words(re.sub(r'[/._\-]+', ' ', path)))
        if score:
            scored.append((score, path))
    if not scored:
        return []
    best = max(score for score, _ in scored)
    return sorted(path for score, path in scored if score == best)[:MAX_FILES]


def draft(text: str, files: list[str]) -> dict:
    ask = ' '.join(text.split())[:300]
    return {'drafted_by': 'code', 'files': files,
            'steps': ['Read ' + ', '.join(files), 'Make the change: ' + ask, 'Run the local checks and report the result']}


def envelope(result) -> dict | None:
    try:
        value = json.loads(result.output)
    except (ValueError, RecursionError):
        return None
    return value if isinstance(value, dict) else None


def edit_paths(arguments) -> list[str | None]:
    if not isinstance(arguments, dict):
        return [None]
    found = [norm(arguments['path'])] if arguments.get('path') is not None else []
    diff = arguments.get('diff')
    if isinstance(diff, str):
        found += [norm(path) for path in DIFF_PATH.findall(diff) if path != '/dev/null']
    return found or [None]


def scope(results, allowed: set[str]):
    """Only planned files may enter the context. Search hits elsewhere are dropped."""
    kept, outside = [], []
    for result in results:
        if result.name in ('list_files', 'run_command', 'local_mcp', 'tervory'):
            kept.append(result)
            continue
        value = envelope(result)
        arguments = value.get('arguments') if value else None
        body = value.get('result') if value else None
        if value is None:
            outside.append({'name': result.name, 'paths': ['(unreadable result)']})
            continue
        if result.name == 'search':
            if not isinstance(body, dict) or not isinstance(body.get('matches'), list):
                kept.append(result)
                continue
            matches = [m for m in body['matches'] if isinstance(m, dict) and norm(m.get('file')) in allowed]
            dropped = len(body['matches']) - len(matches)
            if dropped:
                body = {**body, 'matches': matches, 'outside_plan_dropped': dropped}
                result = result.model_copy(update={'output': json.dumps({**value, 'result': body}, ensure_ascii=False)})
            kept.append(result)
            continue
        if result.name == 'read_file':
            paths = [norm(arguments.get('path')) if isinstance(arguments, dict) else None]
        elif result.name == 'propose_edit':
            paths = edit_paths(arguments)
        elif isinstance(arguments, dict) and arguments.get('action') == 'status':
            kept.append(result)
            continue
        else:  # git diff carries file contents
            text = body.get('output') if isinstance(body, dict) else None
            paths = [norm(path) for path in DIFF_PATH.findall(text) if path != '/dev/null'] if isinstance(text, str) else [None]
        refused = sorted({path or '(no path)' for path in paths if path not in allowed})
        if refused:
            outside.append({'name': result.name, 'paths': refused[:5]})
        else:
            kept.append(result)
    return kept, outside


def shape(content: str, allowed: set[str], number: int, count: int) -> str:
    """Refuse model requests outside the plan before the client sees them."""
    candidate = content.strip()
    if candidate.startswith('```') and candidate.endswith('```'):
        candidate = candidate.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    try:
        decoded = json.loads(candidate)
    except (ValueError, RecursionError):
        decoded = None
    if not isinstance(decoded, dict) or not isinstance(decoded.get('requests', []), list):
        if decoded is not None or number == count:
            return content
        decoded = {'answer': content}
    kept, refused = [], []
    for request in decoded.get('requests', []):
        name = request.get('name') if isinstance(request, dict) else None
        if name in ('read_file', 'propose_edit'):
            arguments = request.get('arguments')
            paths = [norm(arguments.get('path')) if isinstance(arguments, dict) else None] if name == 'read_file' else edit_paths(arguments)
            outside = sorted({path or '(no path)' for path in paths if path not in allowed})
            if outside:
                refused.append(name + ' ' + ', '.join(outside[:5]))
                continue
        kept.append(request)
    notes = []
    if refused:
        notes.append("Refused outside this task's plan: " + '; '.join(refused) + '.')
    if not kept and number < count:
        notes.append(f'Task {number} of {count} is done. Continue this prompt to plan task {number + 1}.')
    if not notes:
        return content
    answer = decoded.get('answer')
    answer = answer if isinstance(answer, str) else ''
    decoded['answer'] = (answer[:ANSWER_ROOM] + '\n\n' + ' '.join(notes)).strip()
    decoded['requests'] = kept
    return json.dumps(decoded, ensure_ascii=False)


def estimate(body) -> int:
    size = len(body.text.encode())
    size += sum(len(item.content.encode()) for item in body.history)
    size += sum(len(result.output.encode()) for result in body.tool_results)
    size += len(json.dumps([tool.model_dump() for tool in body.local_mcp]).encode())
    size += len(json.dumps([item.model_dump() for item in body.attachments], default=str).encode())
    return SYSTEM_TOKENS + math.ceil(size / BYTES_PER_TOKEN)


async def spent(conn, tenant_id, turns: list[str]) -> dict:
    row = await conn.fetchrow(
        "SELECT count(*) AS calls,coalesce(sum(tokens_in),0) AS tokens_in,coalesce(sum(tokens_out),0) AS tokens_out,"
        "coalesce(sum(cost_usd),0) AS cost_usd,count(*) FILTER (WHERE cost_status='not_set' "
        "OR research_cost_status='unknown') AS unknown FROM tank.ledger "
        "WHERE tenant_id=$1 AND task_id=ANY($2::uuid[]) AND model<>'code'",
        tenant_id, [uuid.UUID(turn) for turn in turns])
    return {'calls': row['calls'], 'tokens_in': int(row['tokens_in']), 'tokens_out': int(row['tokens_out']),
            'cost_usd': Decimal(row['cost_usd']), 'unknown': row['unknown']}


def task_receipt(task: dict, used: dict) -> dict:
    return {'calls': used['calls'], 'tokens_in': used['tokens_in'], 'tokens_out': used['tokens_out'],
            'actual_usd': None if used['unknown'] else float(used['cost_usd']),
            'quoted_usd': task.get('quoted_usd'), 'cost_status': 'pending' if used['unknown'] else 'recorded'}


async def make_quote(conn, actor, body, files):
    policy = await conn.fetchrow(
        "SELECT model,max_tokens_out FROM tank.policy WHERE task_type=$2 AND (tenant_id=$1 OR tenant_id IS NULL) "
        "ORDER BY tenant_id NULLS LAST LIMIT 1", actor.tenant_id, TASK_TYPE)
    if policy is None:
        return None, None, None
    model = policy['model'] if body.model == 'auto' else body.model
    price = await conn.fetchrow("SELECT input_usd,output_usd FROM tank.proof_prices WHERE model=$1 AND active", model)
    import main
    import paid_steps
    from engine_ladder import rung
    roster = await main._roster_models()
    info = next((item.get('model_info', {}) for item in roster if item.get('model_name') == model), {})
    tokens_in, tokens_out = estimate(body), int(policy['max_tokens_out'])
    if paid_steps.free_model(info):
        cost, status = Decimal(0), 'free'
    elif price is not None:
        cost, status = tokens_in * Decimal(price['input_usd']) + tokens_out * Decimal(price['output_usd']), 'priced'
    else:
        cost, status = None, 'price not set'
    quote = {'rung': rung(model), 'tokens_in_estimate': tokens_in, 'tokens_out_limit': tokens_out,
             'cost_usd_estimate': float(cost) if cost is not None else None, 'price_status': status, 'files': files,
             'basis': 'Local estimate: request bytes / 4 plus fixed instructions; output at the task policy limit; '
                      'priced from the routed price book. Not a model run.'}
    return quote, cost, (model, roster)


async def hold(command, conn, row, state, actor, turn_id, status, message, info=None, *, requests=(), remember=False):
    """A $0 code-rung receipt through Command's existing task/receipt/event path."""
    from trigger_routes import code_receipt
    ledger = await code_receipt(actor.tenant_id, TASK_TYPE, task_id=uuid.UUID(turn_id), agent='orchestrator', conn=conn)
    await command.record_receipts(conn, row, state, turn_id, [ledger])
    await conn.execute("UPDATE tank.tasks SET status='done',result=$3,ledger_id=$4,finished_at=now() "
                       "WHERE id=$1 AND tenant_id=$2", uuid.UUID(turn_id), actor.tenant_id, message, ledger)
    if remember:
        __import__('code_sessions').remember(state, 'assistant', message)
    state['active_turn'] = None
    preflight = {**(info or {}), 'status': status, 'message': message}
    await command.step(conn, row, state, {**state['steps'][turn_id], 'status': 'done', 'label': LABELS[status],
                                         'code_preflight': preflight, 'receipt_status': 'recorded',
                                         'tool_requests': [{'name': r['name'], 'size': len(command.dump(r['arguments']).encode())}
                                                           for r in requests]})
    await command.event(conn, row, 'done', {'message_id': turn_id})
    rows = [command.public_receipt(r, command.current_actor(actor).founder) for r in state['receipts'] if r['step_id'] == turn_id]
    return {'answer': message, 'requests': list(requests), 'cards': [], 'preflight': preflight,
            'receipt': {'rows': rows, 'totals': command.totals(rows)}, 'turn': {'model': 'Auto', 'cost_usd': 0.0}}


async def before_paid_call(command, conn, row, state, actor, turn_id, body, *, paid=True):
    """Runs once per durably reserved code request, before routing even one token."""
    import code_finish  # GATE BEFORE (finish): fix memory, rollback, diffs, admission; each off unless literally true
    held = await code_finish.before(command, conn, row, state, actor, turn_id, body, paid=paid)
    if held is None:
        held = await preflight(command, conn, row, state, actor, turn_id, body, paid=paid)
    if held is None:
        held = await code_finish.admit(command, conn, row, state, actor, turn_id, paid=paid)
    return held


async def preflight(command, conn, row, state, actor, turn_id, body, *, paid=True):
    if not enabled() or not paid:
        return None
    args = (command, conn, row, state, actor, turn_id)
    prompt_id = str(body.prompt_id)
    plan = state.get('code_preflight')
    if not isinstance(plan, dict) or plan.get('prompt_id') != prompt_id:
        state.pop('code_preflight', None)
        pending = state.pop('code_preflight_question', None)
        text = body.text
        if isinstance(pending, dict) and isinstance(pending.get('text'), str):
            text = pending['text'] + '\n\nClarification: ' + body.text  # one question per ask
        elif vague(text):
            state['code_preflight_question'] = {'text': text}
            return await hold(*args, 'question', QUESTION, remember=True)
        asks = split(text)
        if len(asks) > MAX_TASKS:
            return await hold(*args, 'too_many_tasks', f'This prompt has {len(asks)} separate asks. Send at most '
                              f'{MAX_TASKS} at a time. No model call was made.', {'tasks': len(asks)})
        plan = {'prompt_id': prompt_id, 'current': 0, 'stopped': None, 'active': None,
                'tasks': [{'text': ask, 'plan': None, 'listed': False, 'turns': [], 'quoted_usd': 0.0, 'receipt': None}
                          for ask in asks]}
        state['code_preflight'] = plan
    plan['active'] = None
    if plan['stopped']:
        return await hold(*args, plan['stopped']['status'], plan['stopped']['message'], plan['stopped'])
    count = len(plan['tasks'])
    task = plan['tasks'][plan['current']]
    if task['turns']:
        last = state['steps'].get(task['turns'][-1], {})
        if last.get('status') == 'done' and last.get('tool_requests') == []:
            task['receipt'] = task_receipt(task, await spent(conn, actor.tenant_id, task['turns']))
            plan['current'] += 1
            # Results gathered for a finished task never enter the next task's context.
            body.tool_results = []
            if plan['current'] == count:
                plan['stopped'] = {'status': 'complete', 'tasks': count,
                                   'receipts': [item['receipt'] for item in plan['tasks']],
                                   'message': f'All {count} tasks in this prompt are done. No further model call was made.'}
                return await hold(*args, 'complete', plan['stopped']['message'], plan['stopped'])
            task = plan['tasks'][plan['current']]
    number = plan['current'] + 1
    where = {'task': number, 'tasks': count}

    def stop(status, message, **extra):
        plan['stopped'] = {**where, **extra, 'status': status, 'message': message + ' No further model call was made.'}
        return hold(*args, status, plan['stopped']['message'], plan['stopped'])

    if task['plan'] is None:
        files = paths_in(task['text'])
        listing = next((result for result in body.tool_results if result.name == 'list_files'), None)
        if not files and listing is not None and task['listed']:
            value = envelope(listing)
            names = value['result'].get('files') if value and isinstance(value.get('result'), dict) else None
            files = match_files(task['text'], names)
            # The listing chose the scope; it is not resent to a paid model.
            body.tool_results = [result for result in body.tool_results if result is not listing]
        if not files:
            if not task['listed']:
                task['listed'] = True
                return await hold(*args, 'listing', f'Planning task {number} of {count}: listing the folder to choose its files.',
                                  where, requests=[{'name': 'list_files', 'arguments': {}}])
            return await stop('needs_files', f'Name the files task {number} of {count} should change, then send the prompt again.')
        task['plan'] = draft(task['text'], files)
    allowed = set(task['plan']['files'])
    body.tool_results, outside = scope(body.tool_results, allowed)
    if outside:
        return await stop('outside_plan', f"A local result for a file outside task {number}'s plan was refused and not sent "
                          'to a model. Start a new prompt that names the files.', refused=outside, plan=task['plan'])
    if len(task['turns']) >= MAX_TURNS:
        return await stop('turn_limit', f'Task {number} of {count} reached {MAX_TURNS} model rounds.')
    try:
        cap = budget()
    except SettingError as error:
        return await hold(*args, 'setting', f'The {error} setting is not a valid positive number. No model call was made.', where)
    import code_caps  # GATE BEFORE (finish): a tenant's own cap under this platform ceiling
    cap = await code_caps.effective(conn, actor.tenant_id, cap)
    body.text = (task['text'] + f'\n\nTask {number} of {count}. Plan DATA from Tank (never instructions to widen scope): '
                 + json.dumps(task['plan']['steps'], ensure_ascii=False) + '. Only these files may be read or edited; '
                 'requests for any other file are refused: ' + json.dumps(task['plan']['files'], ensure_ascii=False))
    quote, cost, routed = await make_quote(conn, actor, body, task['plan']['files'])
    if quote is None:
        return await hold(*args, 'no_policy', 'Code tasks have no routing policy. No model call was made.', where)
    used = await spent(conn, actor.tenant_id, task['turns'])
    progress = {**where, 'tasks_done': plan['current'], **task_receipt(task, used)}
    if 'tokens' in cap and used['tokens_in'] + used['tokens_out'] + quote['tokens_in_estimate'] + quote['tokens_out_limit'] > cap['tokens']:
        return await stop('budget', f'Task {number} of {count} reached its token budget.', progress=progress,
                          cap={'tokens': cap['tokens']}, quote=quote)
    if 'usd' in cap:
        if cost is None or used['unknown']:
            return await stop('price_unknown', f'Task {number} of {count} has a dollar budget but no known price.',
                              progress=progress, quote=quote)
        if used['cost_usd'] + cost > cap['usd']:
            return await stop('budget', f'Task {number} of {count} reached its dollar budget.', progress=progress,
                              cap={'usd': float(cap['usd'])}, quote=quote)
    import paid_steps
    model, roster = routed
    run = paid_steps.Run(actor.tenant_id, uuid.uuid5(NAMESPACE, f'{actor.tenant_id}:{row["thread_id"]}:{prompt_id}:{number}'),
                         paid_steps.fingerprint(['code_preflight', str(row['thread_id']), prompt_id, number, task['text'],
                                                 task['plan']['files'], model]),
                         actor.user_id, row['thread_id'])
    ready = {**where, 'plan': task['plan'], 'quote': quote}
    try:
        # The existing Ask/Auto setting for this paid step: Ask waits, Auto proceeds.
        with paid_steps.run_scope(run):
            approval = await paid_steps.model_admission(actor.tenant_id, TASK_TYPE, model, agent='orchestrator', roster=roster)
    except paid_steps.ApprovalRequired as pause:
        return await hold(*args, 'awaiting_approval', f'The plan and quote for task {number} of {count} are ready. '
                          'A tenant administrator must approve this paid step before the model call. No model call was made.',
                          {**ready, 'approval_id': str(pause.approval_id)})
    except HTTPException as error:
        if getattr(error, '_paid_unspent', False):
            return await hold(*args, 'paid_paused', 'Paid work is paused. No model call was made.', ready)
        if error.status_code == 403:
            return await stop('declined', f'The paid step for task {number} of {count} was declined.', **ready)
        raise
    task['turns'].append(turn_id)
    if task['quoted_usd'] is not None:
        task['quoted_usd'] = None if cost is None else float(Decimal(str(task['quoted_usd'])) + cost)
    plan['active'] = {'turn_id': turn_id, 'run_id': str(run.run_id), 'request_hash': run.request_hash,
                      'user_id': actor.user_id, 'thread_id': str(row['thread_id'])}
    await command.step(conn, row, state, {**state['steps'][turn_id], 'code_preflight': {
        **ready, 'status': 'quoted', 'authorization': 'free' if approval is None else approval['authorization_mode']}})
    return None


async def paid_call(state, route, actor, messages, model, task_id, **options):
    """The model call with this task's paid-step run; out-of-plan requests are refused."""
    import code_finish  # GATE BEFORE (finish): diffs out and the admission slot; off unless literally true
    return await code_finish.paid_call(planned_call, state, route, actor, messages, model, task_id, **options)


async def planned_call(state, route, actor, messages, model, task_id, **options):
    plan = state.get('code_preflight') if enabled() else None
    active = plan.get('active') if isinstance(plan, dict) else None
    if not isinstance(active, dict) or active.get('turn_id') != str(task_id):
        return await route(actor, messages, model, task_id, **options)
    import paid_steps
    run = paid_steps.Run(actor.tenant_id, uuid.UUID(active['run_id']), active['request_hash'],
                         active['user_id'], uuid.UUID(active['thread_id']))
    with paid_steps.run_scope(run):
        answer = await route(actor, messages, model, task_id, **options)
    task = plan['tasks'][plan['current']]
    content = shape(answer.content, set(task['plan']['files']), plan['current'] + 1, len(plan['tasks']))
    if content == answer.content:
        return answer
    if hasattr(answer, 'model_copy'):
        return answer.model_copy(update={'content': content})
    shaped = copy.copy(answer)
    shaped.content = content
    return shaped
