"""Founder Ask/Auto decisions at paid dispatch boundaries, never at free rungs.

Approval parks the existing coroutine. It never replays a run or a paid call.
An interrupted process leaves an interrupted run, requiring inspection.
"""
from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import logging
import re
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from gold import PLATFORM_TENANT
from tenant_db import tenant_scope

POLL_SECONDS = 1.0
WAIT_LIMIT = timedelta(hours=24)
SERVER = uuid.uuid4()
STEP_PATTERN = r"^[a-zA-Z0-9][a-zA-Z0-9_.:/@-]{0,199}$"
FIXED = {
    'vendor.brave': 'Brave search',
    'vendor.google_places': 'Google Places',
    'vendor.apollo': 'Apollo contacts',
    'vendor.context_dev': 'Context.dev credits',
    'vendor.perplexity.search_web': 'Research bundle: provider web searches',
    'vendor.perplexity.fetch_url': 'Research bundle: provider page fetches',
    'hf.jobs.photogrammetry': 'Hugging Face photogrammetry job',
    'hf.jobs.trellis2': 'Hugging Face TRELLIS job',
}


def runtime():
    import main
    return main


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str, separators=(',', ':')).encode()).hexdigest()


def model_step(model: str, rung: int = 1) -> str:
    return f'model.rung{rung}.{model}'


@dataclass
class Run:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    tenant: uuid.UUID | None = None
    caller: str | None = None
    task: Any = None
    paused: asyncio.Event = field(default_factory=asyncio.Event)
    waiting_count: int = 0
    saved: bool = False
    task_id: uuid.UUID | None = None
    card_id: uuid.UUID | None = None
    card_tenant: uuid.UUID | None = None
    deadline: datetime | None = None
    on_pause: Any = None
    on_resume: Any = None

    @property
    def waiting(self):
        return self.waiting_count > 0


CURRENT: contextvars.ContextVar[Run | None] = contextvars.ContextVar('paid_step_run', default=None)
# Mutable counters are inherited by awaited child tasks, but sibling timeout
# scopes keep their own counter. One waiting MoA seat cannot uncap another.
BUDGETS: contextvars.ContextVar[tuple] = contextvars.ContextVar('paid_active_budgets', default=())
LIVE: set[asyncio.Task] = set()
RUNS: dict[asyncio.Task, Run] = {}


def track(task):
    """Own detached work and consume failures without logging private inputs."""
    LIVE.add(task)
    def completed(value):
        LIVE.discard(value)
        if not value.cancelled() and (error := value.exception()) is not None:
            logging.getLogger(__name__).warning('Paid continuation stopped: %s', type(error).__name__)
    task.add_done_callback(completed)
    return task


def detached_context():
    context = contextvars.copy_context()
    context.run(CURRENT.set, None)
    context.run(BUDGETS.set, ())
    return context


@asynccontextmanager
async def run_scope(**kwargs):
    """A maintenance job owns one continuation, including its awaited children."""
    run = Run(task=asyncio.current_task(), **kwargs)
    parent = RUNS.get(run.task)
    token = CURRENT.set(run)
    RUNS[run.task] = run
    try:
        yield run
        await finish_run(run, 200)
    except BaseException:
        await finish_run(run)
        raise
    finally:
        CURRENT.reset(token)
        if parent:
            RUNS[run.task] = parent
        else:
            RUNS.pop(run.task, None)


class Queries:
    """Short tenant-owned SQL checkouts; a parked run never reserves a connection."""
    def __init__(self, pool, tenant):
        self.pool, self.tenant = pool, tenant
        self.connection = contextvars.ContextVar('paid_worker_connection', default=None)

    def __getattr__(self, name):
        if name not in {'execute','fetch','fetchrow','fetchval'}:
            raise AttributeError(name)
        async def query(*args, **kwargs):
            if self.connection.get() is not None:
                return await getattr(self.connection.get(), name)(*args, **kwargs)
            with tenant_scope(self.tenant):
                async with self.pool.acquire() as conn:
                    return await getattr(conn, name)(*args, **kwargs)
        return query

    @asynccontextmanager
    async def transaction(self):
        with tenant_scope(self.tenant):
            async with self.pool.acquire() as conn, conn.transaction():
                token = self.connection.set(conn)
                try:
                    yield
                finally:
                    self.connection.reset(token)


async def heartbeat(tank=None):
    tank = tank or runtime()
    with tenant_scope(PLATFORM_TENANT):
        async with tank.pool().acquire() as conn:
            await conn.execute('''INSERT INTO tank.paid_step_workers(tenant_id,id) VALUES($1,$2)
                ON CONFLICT(tenant_id,id) DO UPDATE SET heartbeat=now()''', PLATFORM_TENANT, SERVER)


def current() -> Run:
    value = CURRENT.get()
    if value is None:
        value = Run(task=asyncio.current_task())
        CURRENT.set(value)
        RUNS[value.task] = value
        run = value
        def completed(task):
            status = 500 if task.cancelled() or task.exception() is not None else 200
            cleanup = asyncio.create_task(finish_run(run, status))
            cleanup.add_done_callback(lambda task: task.exception() if not task.cancelled() else None)
        value.task.add_done_callback(completed)
    return value


async def mode(step_id: str) -> str:
    if not re.fullmatch(STEP_PATTERN, step_id):
        raise HTTPException(503, 'Paid step identity is unavailable')
    with tenant_scope(PLATFORM_TENANT):
        async with runtime().pool().acquire() as conn:
            value = await conn.fetchval('SELECT mode FROM tank.paid_step_settings WHERE tenant_id=$1 AND step_id=$2', PLATFORM_TENANT, step_id)
    if value is None:
        return 'ask'
    if value not in {'ask', 'auto'}:
        raise HTTPException(503, 'Paid step setting is unavailable')
    return value


async def authorize(step_id: str, payload: Any, *, tenant: uuid.UUID | None = None, task: str = 'paid step'):
    """One exact dispatch, with no pool checkout held while asking a person."""
    import controls
    await controls.refuse_paid(task=task, path='paid-step:'+step_id)
    selected = await mode(step_id)
    if selected == 'auto':
        # Global pause can change while the individual setting is read.
        await controls.refuse_paid(task=task, path='paid-step:'+step_id)
        return
    run = current()
    from tenant_db import _tenant
    owner = tenant or run.tenant or uuid.UUID(_tenant.get() or str(PLATFORM_TENANT))
    if run.tenant is not None and run.tenant != owner:
        raise HTTPException(409, 'A paid run must belong to one tenant')
    run.tenant = owner
    approval = uuid.uuid4()
    expires = min(datetime.now(UTC) + WAIT_LIMIT, run.deadline) if run.deadline else datetime.now(UTC) + WAIT_LIMIT
    with tenant_scope(owner):
        async with runtime().pool().acquire() as conn, conn.transaction():
            await conn.execute('''INSERT INTO tank.paid_runs(tenant_id,id,region,server_id,caller,source_card_id,source_tenant_id,status)
                VALUES($1,$2,$3,$4,$5,$6,$7,'waiting') ON CONFLICT(tenant_id,id) DO UPDATE SET status='waiting' ''',
                owner, run.id, runtime().box_region(), SERVER, run.caller, run.card_id, run.card_tenant)
            await conn.execute('''INSERT INTO tank.paid_step_approvals
                (tenant_id,id,run_id,step_id,request_hash,task_type,expires_at)
                VALUES($1,$2,$3,$4,$5,$6,$7)''', owner, approval, run.id, step_id, digest(payload), task[:120], expires)
    run.saved = True
    run.waiting_count += 1
    budgets = BUDGETS.get()
    for budget in budgets:
        budget[0] += 1
    try:
        if run.on_pause:
            await run.on_pause(approval, step_id)
        elif run.task_id:
            with tenant_scope(owner):
                async with runtime().pool().acquire() as conn:
                    await conn.execute("UPDATE tank.tasks SET status='queued' WHERE tenant_id=$1 AND id=$2 AND status='running'", owner, run.task_id)
        run.paused.set()
        while True:
            with tenant_scope(owner):
                async with runtime().pool().acquire() as conn:
                    row = await conn.fetchrow('''SELECT status,request_hash,expires_at FROM tank.paid_step_approvals
                        WHERE tenant_id=$1 AND id=$2''', owner, approval)
            if row is None or row['status'] in {'cancelled', 'interrupted', 'claimed'}:
                raise HTTPException(409, 'Paid step approval is no longer available')
            if row['expires_at'] <= datetime.now(UTC):
                raise HTTPException(408, 'Paid step approval expired without dispatch')
            if row['request_hash'] != digest(payload):
                raise HTTPException(409, 'Paid step inputs changed after the approval request')
            if row['status'] == 'approved' or await mode(step_id) == 'auto':
                # A founder approval never overrides the global pause.
                await controls.refuse_paid(task=task, path='paid-step:'+step_id)
                with tenant_scope(owner):
                    async with runtime().pool().acquire() as conn, conn.transaction():
                        claimed = await conn.fetchval('''UPDATE tank.paid_step_approvals SET status='claimed',claimed_at=now()
                            WHERE tenant_id=$1 AND id=$2 AND status IN ('waiting','approved') AND expires_at>now()
                            RETURNING id''', owner, approval)
                        if claimed:
                            await conn.execute("UPDATE tank.paid_runs SET status=$3 WHERE tenant_id=$1 AND id=$2", owner, run.id,
                                               'waiting' if run.waiting_count > 1 else 'running')
                if not claimed:
                    raise HTTPException(409, 'Paid step approval was already consumed')
                if run.on_resume and run.waiting_count == 1:
                    await run.on_resume()
                elif run.task_id and run.waiting_count == 1:
                    with tenant_scope(owner):
                        async with runtime().pool().acquire() as conn:
                            await conn.execute("UPDATE tank.tasks SET status='running' WHERE tenant_id=$1 AND id=$2 AND status='queued' AND finished_at IS NULL", owner, run.task_id)
                return
            await asyncio.sleep(POLL_SECONDS)
    except BaseException:
        with tenant_scope(owner):
            async with runtime().pool().acquire() as conn:
                await conn.execute('''UPDATE tank.paid_step_approvals SET status='cancelled'
                    WHERE tenant_id=$1 AND id=$2 AND status IN ('waiting','approved')''', owner, approval)
        raise
    finally:
        run.waiting_count -= 1
        for budget in budgets:
            budget[0] -= 1


async def catalog() -> list[dict]:
    known = dict(FIXED)
    try:
        roster = await runtime()._roster_models()
    except Exception:
        # Settings remain usable while the served roster is unavailable. The
        # dispatch boundary still independently validates availability/policy.
        roster = []
    for row in roster:
        name = row['model_name']
        for rung in (1, 2):
            known[model_step(name, rung)] = f'Model rung {rung}: {name}'
    with tenant_scope(PLATFORM_TENANT):
        async with runtime().pool().acquire() as conn:
            rows = await conn.fetch('SELECT step_id,mode,updated_by,updated_at FROM tank.paid_step_settings WHERE tenant_id=$1', PLATFORM_TENANT)
    saved = {row['step_id']: dict(row) for row in rows}
    for key in saved:
        known.setdefault(key, key)
    for row in await pending():
        known.setdefault(row['step_id'], row['step_id'])
    return [{'step_id': key, 'label': value, 'mode': saved.get(key, {}).get('mode', 'ask'),
             'updated_by': saved.get(key, {}).get('updated_by'), 'updated_at': saved.get(key, {}).get('updated_at')}
            for key, value in sorted(known.items())]


class Setting(BaseModel):
    model_config = ConfigDict(extra='forbid')
    step_id: str = Field(pattern=STEP_PATTERN, max_length=200)
    mode: Literal['ask', 'auto']


class ApprovalArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    approval_id: uuid.UUID


class CreditCall(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    call_id: uuid.UUID
    run_id: uuid.UUID
    record_id: uuid.UUID
    units: int = Field(gt=0, le=1000)
    request_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


async def set_mode(body: Setting, by: str):
    if body.step_id not in {row['step_id'] for row in await catalog()}:
        raise HTTPException(422, 'Unknown paid step')
    with tenant_scope(PLATFORM_TENANT):
        async with runtime().pool().acquire() as conn, conn.transaction():
            await conn.execute('SELECT pg_advisory_xact_lock(4810117)')
            old = await conn.fetchval('SELECT mode FROM tank.paid_step_settings WHERE tenant_id=$1 AND step_id=$2', PLATFORM_TENANT, body.step_id) or 'ask'
            await conn.execute('''INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by)
                VALUES($1,$2,$3,$4) ON CONFLICT(tenant_id,step_id) DO UPDATE
                SET mode=EXCLUDED.mode,updated_by=EXCLUDED.updated_by,updated_at=now()''', PLATFORM_TENANT, body.step_id, body.mode, by)
            await conn.execute('''INSERT INTO tank.paid_step_log(tenant_id,step_id,old_mode,new_mode,by_user)
                VALUES($1,$2,$3,$4,$5)''', PLATFORM_TENANT, body.step_id, old, body.mode, by)
    return {'step_id':body.step_id, 'mode':body.mode}


async def pending() -> list[dict]:
    with tenant_scope(None, administrative=True):
        async with runtime().admin_pool().acquire() as conn:
            rows = await conn.fetch('''SELECT a.tenant_id,a.id,a.run_id,a.step_id,a.task_type,a.expires_at,a.status
                FROM tank.paid_step_approvals a JOIN tank.paid_runs r ON r.tenant_id=a.tenant_id AND r.id=a.run_id
                WHERE r.region=$1 AND a.status='waiting' AND a.expires_at>now() ORDER BY a.created_at,a.id LIMIT 100''', runtime().box_region())
    return [dict(row) for row in rows]


async def decide(approval_id: uuid.UUID, by: str, *, approve=True):
    # Caller is re-authorized at the HTTP or /chats boundary, including card confirmation.
    with tenant_scope(None, administrative=True):
        async with runtime().admin_pool().acquire() as conn:
            row = await conn.fetchrow('''SELECT a.tenant_id FROM tank.paid_step_approvals a JOIN tank.paid_runs r
                ON r.tenant_id=a.tenant_id AND r.id=a.run_id WHERE a.id=$1 AND r.region=$2''', approval_id, runtime().box_region())
    if row is None:
        raise HTTPException(404, 'No approval request here')
    import controls
    if approve:
        await controls.refuse_paid(task='founder approval', path='paid-step.confirm')
    with tenant_scope(row['tenant_id']):
        async with runtime().pool().acquire() as conn:
            changed = await conn.fetchval('''UPDATE tank.paid_step_approvals SET status=$3,decided_by=$4,decided_at=now()
                WHERE tenant_id=$1 AND id=$2 AND status='waiting' AND expires_at>now() RETURNING id''',
                row['tenant_id'], approval_id, 'approved' if approve else 'cancelled', by)
    if not changed:
        raise HTTPException(409, 'Approval request is no longer waiting')
    return {'approval_id':str(approval_id), 'status':'approved' if approve else 'cancelled'}


async def card_waiting(card_id, tenant, *, source=None):
    # Called only after ownership of this exact source card was checked and the
    # source checkout released. Global skill evals can own a platform paid run
    # while their founder's source card belongs to a workspace tenant.
    with tenant_scope(None, administrative=True):
        async with (source or runtime().admin_pool()).acquire() as conn:
            return await conn.fetchval('''SELECT EXISTS(SELECT 1 FROM tank.paid_runs
                WHERE source_tenant_id=$1 AND source_card_id=$2 AND region=$3
                AND status IN ('waiting','running') AND tank.paid_worker_alive(server_id))''', tenant, card_id, runtime().box_region())


@asynccontextmanager
async def execution_timeout(seconds: float):
    """Budget active execution time; an Ask wait does not consume this budget."""
    budget = [0]
    token = BUDGETS.set((*BUDGETS.get(), budget))
    timeout = asyncio.timeout(None)
    async def watch():
        remaining, previous = seconds, asyncio.get_running_loop().time()
        while remaining > 0:
            await asyncio.sleep(min(.25, remaining))
            stamp = asyncio.get_running_loop().time()
            if not budget[0]:
                remaining -= stamp - previous
            previous = stamp
        timeout.reschedule(asyncio.get_running_loop().time())
    async with timeout:
        watcher = asyncio.create_task(watch())
        try:
            yield
        finally:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
            BUDGETS.reset(token)


async def finish_run(run: Run, status: int | None = None, body: bytes = b'', headers=None):
    RUNS.pop(run.task, None)
    if not run.saved or run.tenant is None:
        return
    with tenant_scope(run.tenant):
        async with runtime().pool().acquire() as conn:
            await conn.execute('''UPDATE tank.paid_runs SET status=$3,response_status=$4,response_body=$5,
                response_headers=$6::jsonb,finished_at=now() WHERE tenant_id=$1 AND id=$2''',
                run.tenant, run.id, 'completed' if status is not None else 'interrupted', status, body,
                json.dumps(headers or []))
            await conn.execute('''UPDATE tank.paid_step_approvals SET status='interrupted'
                WHERE tenant_id=$1 AND run_id=$2 AND status IN ('waiting','approved')''', run.tenant, run.id)


class PaidRunMiddleware:
    """Detach an Ask wait from an HTTP deadline; keep the exact coroutine alive.

    Nested in-process dispatch uses its parent's run. No body or operation is
    ever replayed. Completion is polled through the authenticated run endpoint.
    Command turns already have their own saved event stream and use callbacks.
    """
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        path = scope.get('path', '')
        selected = (path == '/v1/paid-steps/authorize' or path == '/v1/route' or path.startswith('/v1/route/batch')
                    or path == '/v1/research' or (path.startswith('/v1/skala/') and path.endswith(('/run','/evals')))
                    or (path.startswith('/v1/agents/') and path.endswith(('/chat','/claim')))
                    or path.startswith('/v1/command/cards/'))
        if scope['type'] != 'http' or scope.get('method') != 'POST' or not selected or CURRENT.get() is not None:
            await self.app(scope, receive, send)
            return
        # These JSON corridors are bounded; never buffer uploads or room assets.
        content = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            content.extend(message.get('body', b''))
            if len(content) > 20 * 1024 * 1024:
                await self.respond(send, 413, b'{"detail":"Request exceeds 20 MiB"}')
                return
            if not message.get('more_body'):
                break
        try:
            card_id = uuid.UUID(path.rsplit('/',1)[-1]) if path.startswith('/v1/command/cards/') else None
        except ValueError:
            card_id = None  # Let the route's normal UUID validation return 422.
        run = Run(card_id=card_id)
        complete = asyncio.Event()
        response_start, response_body = {}, bytearray()
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type':'http.request','body':bytes(content),'more_body':False}
            await asyncio.Event().wait()

        async def capture(message):
            if message['type'] == 'http.response.start':
                response_start.update(message)
            elif message['type'] == 'http.response.body':
                response_body.extend(message.get('body', b''))
                if len(response_body) > 20 * 1024 * 1024:
                    raise ValueError('Paid run response exceeds the bounded JSON corridor')

        async def work():
            run.task = asyncio.current_task()
            RUNS[run.task] = run
            token = CURRENT.set(run)
            try:
                await self.app(scope, replay, capture)
                headers = [(k.decode('latin1'),v.decode('latin1')) for k,v in response_start.get('headers', [])
                           if k.lower() in {b'content-type', b'cache-control'}]
                await finish_run(run, response_start.get('status', 500), bytes(response_body), headers)
            except BaseException:
                await finish_run(run)
                raise
            finally:
                CURRENT.reset(token)
                complete.set()
        operation = track(asyncio.create_task(work()))
        paused = asyncio.create_task(run.paused.wait())
        done = asyncio.create_task(complete.wait())
        try:
            await asyncio.wait({paused, done}, return_when=asyncio.FIRST_COMPLETED)
            if complete.is_set():
                await operation
                await send(response_start)
                await send({'type':'http.response.body','body':bytes(response_body)})
            else:
                body = {'status':'waiting_for_approval','paid_run_id':str(run.id),
                        'tenant_id':str(run.tenant), 'status_path':f'/v1/paid-runs/{run.id}'}
                # A card confirmation is still executing, and its final result
                # will arrive through the existing saved thread events.
                if path.startswith('/v1/command/cards/'):
                    import command
                    card_id = path.rsplit('/',1)[-1]
                    owner = run.card_tenant or run.tenant
                    with tenant_scope(owner):
                        async with runtime().pool().acquire() as conn:
                            row = await conn.fetchrow('''SELECT state FROM tank.command_threads WHERE tenant_id=$1
                                AND state->'cards' ? $2 LIMIT 1''', owner, card_id)
                    if row:
                        card = json.loads(row['state'])['cards'][card_id]
                        body = {**command.public_card(card), 'paid_run':body}
                await self.respond(send, 202, json.dumps(body).encode())
        except BaseException:
            if not run.paused.is_set():
                operation.cancel()
                await asyncio.gather(operation, return_exceptions=True)
            raise
        finally:
            paused.cancel()
            done.cancel()
            await asyncio.gather(paused, done, return_exceptions=True)

    @staticmethod
    async def respond(send, status, body):
        await send({'type':'http.response.start','status':status,
                    'headers':[(b'content-type',b'application/json'),(b'cache-control',b'private, no-store')]})
        await send({'type':'http.response.body','body':body})


async def sync_inbox(actor):
    import command
    command.require_founder(command.current_actor(actor))
    rows = await pending()
    if not rows:
        return
    identity = uuid.uuid5(uuid.NAMESPACE_URL, f'paid-approvals:{actor.tenant_id}:{actor.user_id}')
    with tenant_scope(actor.tenant_id):
        async with runtime().pool().acquire() as conn:
            await conn.execute('''INSERT INTO tank.command_threads(thread_id,tenant_id,user_id,title,state)
                VALUES($1,$2,$3,'Paid step approvals',$4::jsonb) ON CONFLICT DO NOTHING''', identity, actor.tenant_id, actor.user_id,
                command.dump({'messages':[],'steps':{},'cards':{},'receipts':[],'active_turn':None}))
        async with command.editing(identity, actor) as (conn, thread, state):
            existing = {card.get('arguments',{}).get('approval_id') for card in state['cards'].values()}
            for row in rows:
                if str(row['id']) in existing:
                    continue
                card = await command.propose_action(conn, thread, state, command.PlannedAction(
                    tool='platform.paid_step.approve', arguments={'approval_id':str(row['id'])}), actor)
                card['summary'] = 'Ask: '+row['step_id']+' · run '+str(row['run_id'])
                await command.event(conn, thread, 'card', command.public_card(card))


@asynccontextmanager
async def command_run(thread_id, actor, turn_id):
    import command
    run = Run(tenant=actor.tenant_id, task=asyncio.current_task())
    RUNS[run.task] = run
    token = CURRENT.set(run)
    async def paused(approval, step_id):
        async with command.editing(thread_id, actor) as (conn, row, state):
            await conn.execute("UPDATE tank.tasks SET status='queued' WHERE tenant_id=$1 AND id=$2 AND status='running'", actor.tenant_id, uuid.UUID(turn_id))
            await command.step(conn, row, state, {**state['steps'][turn_id], 'label':'Waiting for founder approval: '+step_id, 'status':'planned'})
            if state['active_turn'] == turn_id:
                state['active_turn'] = None
            if command.current_actor(actor).founder:
                card = await command.propose_action(conn, row, state, command.PlannedAction(
                    tool='platform.paid_step.approve',arguments={'approval_id':str(approval)}), actor)
                card['summary'] = 'Ask: '+step_id+' · run '+str(run.id)
                await command.event(conn, row, 'card', command.public_card(card))
    async def resumed():
        async with command.editing(thread_id, actor) as (conn, row, state):
            await conn.execute("UPDATE tank.tasks SET status='running' WHERE tenant_id=$1 AND id=$2 AND status='queued'", actor.tenant_id, uuid.UUID(turn_id))
            await command.step(conn, row, state, {**state['steps'][turn_id], 'label':'Paid step approved', 'status':'running'})
    run.on_pause, run.on_resume = paused, resumed
    try:
        yield run
        await finish_run(run, 200)
    except BaseException:
        await finish_run(run)
        raise
    finally:
        RUNS.pop(run.task, None)
        CURRENT.reset(token)


async def code_plan(actor, messages, task_id):
    import command
    from types import SimpleNamespace
    from trigger_routes import code_receipt
    last = messages[-1] if messages else {}
    text = str(last.get('content','')).strip()
    list_match = re.fullmatch(r'(?:/paid-steps|paid steps|paid settings|platform\.paid_steps)', text, re.I)
    change = re.fullmatch(r'(?:/paid-step|paid step|platform\.paid_step\.set)\s+(\S+)\s+(ask|auto)', text, re.I)
    if last.get('role') != 'user' or not (list_match or change):
        return None
    command.require_founder(command.current_actor(actor))
    tool = 'platform.paid_step.set' if change else 'platform.paid_steps'
    args = {'step_id':change[1], 'mode':change[2].lower()} if change else {}
    action = command.validate_action(command.PlannedAction(tool=tool, arguments=args), actor)
    ledger = await code_receipt(actor.tenant_id, tool, task_id=task_id)
    return SimpleNamespace(ledger_id=ledger, content=command.dump({'text':'Paid steps default to Ask. The global pause overrides every setting.', 'actions':[action.model_dump(mode='json')]}))


def install(app, tank):
    from admin import require_admin

    @app.get('/v1/controls/paid-steps', dependencies=[Depends(require_admin)])
    async def read_settings():
        return {'default':'ask', 'steps':await catalog()}

    @app.put('/v1/controls/paid-steps', dependencies=[Depends(require_admin)])
    async def write_setting(body: Setting, request: Request):
        return await set_mode(body, request.headers.get('x-tervory-admin',''))

    @app.get('/v1/controls/paid-steps/pending', dependencies=[Depends(require_admin)])
    async def read_pending():
        return await pending()

    @app.post('/v1/controls/paid-steps/approve', dependencies=[Depends(require_admin)])
    async def approve_step(body: ApprovalArgs, request: Request):
        return await decide(body.approval_id, request.headers.get('x-tervory-admin',''))

    @app.post('/v1/paid-steps/authorize')
    async def credit_call(body: CreditCall, caller: str | None = Depends(tank.require_key)):
        if caller != 'base' or body.tenant_id != PLATFORM_TENANT:
            raise HTTPException(403, 'This credit corridor belongs to Base company trials')
        current().caller = caller
        await authorize('vendor.context_dev', body.model_dump(mode='json'), tenant=body.tenant_id, task='base.context_dev')
        return {'authorized':True, 'call_id':str(body.call_id)}

    @app.get('/v1/paid-runs/{run_id}')
    async def read_run(run_id: uuid.UUID, tenant_id: uuid.UUID, caller: str | None = Depends(tank.require_key)):
        # The same key/tenant corridor as /v1/route/jobs. A room reads only its own run.
        await __import__('tenant_regions').local(tank, tenant_id)
        with tenant_scope(tenant_id):
            async with tank.pool().acquire() as conn:
                row = await conn.fetchrow('SELECT * FROM tank.paid_runs WHERE tenant_id=$1 AND id=$2 AND region=$3', tenant_id, run_id, tank.box_region())
        if row is None or (caller is not None and row['caller'] != caller):
            raise HTTPException(404, 'No paid run for this tenant')
        body = row['response_body']
        return {'id':str(run_id),'status':row['status'],'response_status':row['response_status'],
                'result':json.loads(body) if body else None}

    async def maintain():
        while True:
            try:
                with tenant_scope(PLATFORM_TENANT):
                    async with tank.pool().acquire() as conn:
                        await conn.execute('''INSERT INTO tank.paid_step_workers(tenant_id,id) VALUES($1,$2)
                            ON CONFLICT(tenant_id,id) DO UPDATE SET heartbeat=now()''', PLATFORM_TENANT, SERVER)
                with tenant_scope(None, administrative=True):
                    async with tank.admin_pool().acquire() as conn, conn.transaction():
                        await conn.execute('''UPDATE tank.paid_runs r SET status='interrupted',finished_at=now()
                            WHERE region=$1 AND status IN ('waiting','running') AND NOT EXISTS
                            (SELECT 1 FROM tank.paid_step_workers w WHERE w.tenant_id=$2 AND w.id=r.server_id AND w.heartbeat>now()-interval '90 seconds')''', tank.box_region(), PLATFORM_TENANT)
                        await conn.execute('''UPDATE tank.paid_step_approvals a SET status='interrupted'
                            FROM tank.paid_runs r WHERE a.tenant_id=r.tenant_id AND a.run_id=r.id AND r.region=$1
                            AND r.status='interrupted' AND a.status IN ('waiting','approved')''', tank.box_region())
            except Exception as exc:
                logging.getLogger(__name__).warning('Paid run maintenance deferred: %s', type(exc).__name__)
            await asyncio.sleep(10)
    worker = None
    @app.on_event('startup')
    async def start():
        nonlocal worker
        worker = asyncio.create_task(maintain())
    async def stop():
        if worker:
            worker.cancel()
        tasks = [task for task in RUNS if task is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, *([worker] if worker else []), return_exceptions=True)
    app.router.on_shutdown.insert(0, stop)
    app.add_middleware(PaidRunMiddleware)
