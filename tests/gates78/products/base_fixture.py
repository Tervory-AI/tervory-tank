"""Real Base routes/worker and central Hermes; only network edges are routed locally."""
import asyncio
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import UUID

import httpx
import pytest
import pytest_asyncio

from trigger_signin_fakes import native_provider

ROOT = Path(__file__).resolve().parents[3]
USER_A = 'placeholder-base-user-a'
USER_B = 'placeholder-base-user-b'
SERVICE = 'placeholder-base-workspace-key'
REAL_HTTP = httpx.AsyncClient


@pytest.fixture
def base_module_scope():
    """A flat shipped image has no other product's same-named Python modules."""
    names = {path.stem for path in (ROOT / 'agents/base').glob('*.py')} - {'__init__'}
    prefixes = {'brain', 'sources', 'base_gold', 'engines'}
    def owned(name):
        return name in names or any(name == prefix or name.startswith(prefix + '.') for prefix in prefixes)
    saved = {name: module for name, module in list(sys.modules.items()) if owned(name)}
    for name in saved:
        sys.modules.pop(name)
    try:
        yield
    finally:
        for name in list(sys.modules):
            if owned(name):
                sys.modules.pop(name)
        sys.modules.update(saved)


@pytest_asyncio.fixture
async def base_entry(gate78_memory, monkeypatch, tmp_path, base_module_scope):
    stack = await gate78_memory('base')
    import asyncpg, os
    # Base reserves an advisory-lock connection; keep its service pool separate
    # from the unchanged single-connection Hermes fixture.
    pool = await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'],min_size=1,max_size=6,statement_cache_size=0)
    await pool.execute((ROOT / 'tank/schema.sql').read_text())
    import os
    monkeypatch.setenv('DATABASE_URL',os.environ['MEMORY_TEST_DATABASE_URL'])
    monkeypatch.setenv('LITELLM_MASTER_KEY','placeholder-base-litellm-key')
    monkeypatch.setenv('LITELLM_URL','http://litellm')
    monkeypatch.setenv('TANK_URL','http://tank')
    monkeypatch.setenv('HERMES_URL','http://hermes')
    main = importlib.import_module('main')
    monkeypatch.setattr(main, '_pool', pool)
    monkeypatch.setattr(main, 'TANK_API_KEY', SERVICE)
    monkeypatch.setenv('TANK_API_KEY', SERVICE)
    monkeypatch.setenv('TANK_KEY', stack.key)
    monkeypatch.setenv('TANK_KEY_BASE', stack.key)
    monkeypatch.setenv('BASE_AGENT_URL', 'http://agent-base:8000')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.delenv('BASE_BRAIN_URL', raising=False)
    provider = native_provider(monkeypatch, {'10001': stack.tenant, '10002': stack.other_tenant})
    # Use the same flat module packaging as Base's shipped image.
    monkeypatch.syspath_prepend(str(ROOT / 'agents/base'))
    brain_pkg = ModuleType('brain')
    brain_pkg.__path__ = [str(ROOT / 'agents/_brain')]
    monkeypatch.setitem(sys.modules, 'brain', brain_pkg)
    security = importlib.import_module('brain.security')
    monkeypatch.setitem(sys.modules, 'reference_security', security)
    spec = importlib.util.spec_from_file_location('gate78_base_room_app', ROOT / 'agents/base/app.py')
    room_app = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, room_app)
    spec.loader.exec_module(room_app)
    room = importlib.import_module('room')
    worker = importlib.import_module('base_brain')
    brain = importlib.import_module('personal_brain')
    async with pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_base')
        await room.ensure_tables(conn, recover=False)
    room_app.app.state.pool = pool
    from chassis.memory import MemoryClient
    # Product clients must obtain the owner from each verified request/queued row.
    room_app.app.state.memory = MemoryClient('http://hermes',stack.key,'base',stack.http)
    room_app.app.state.configuration_missing = []
    # Real package metadata and approval rows; no fake SkillClient/pipeline.
    import skala
    packages = skala.load_packages()
    monkeypatch.setattr(main, '_packages', packages)
    for (skill, version), package in packages.items():
        if skill.startswith('base.'):
            await pool.execute("INSERT INTO tank.skills(id,version,agent,state) VALUES($1,$2,'base','approved') ON CONFLICT(id,version) DO UPDATE SET state='approved'", skill, version)
    import paid_steps
    monkeypatch.setattr(main, '_roster_cache', None)
    for tenant in (stack.tenant, stack.other_tenant):
        await pool.execute("INSERT INTO tank.policy(task_type,tenant_id,model,priority,cache_scope) VALUES('agent.base.think',$1,'placeholder-base-model','urgent','none')", UUID(tenant))
        step = paid_steps.model_step('agent.base.think', 'placeholder-base-model')
        await paid_steps.register(pool, step, 'base', 'model', 'placeholder-gate78-policy', task='agent.base.think', model='placeholder-base-model')
        await pool.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto',$3) ON CONFLICT(tenant_id,step_id) DO UPDATE SET mode='auto'", UUID(tenant), step, USER_A)
    requests, provider_calls = [], []
    faults = {'path': None, 'status': 503}

    class LocalNetwork(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            requests.append(request)
            host = request.url.host
            if host == 'hermes':
                if faults['path'] == request.url.path:
                    return httpx.Response(faults['status'], json={'detail': 'placeholder storage boundary fault'})
                return await httpx.ASGITransport(app=stack.app).handle_async_request(request)
            if host in {'tank', 'placeholder-tank'}:
                response = await httpx.ASGITransport(app=main.app).handle_async_request(request)
                return response
            if host == 'agent-base':
                return await httpx.ASGITransport(app=room_app.app).handle_async_request(request)
            if host == 'base-brain':
                return await httpx.ASGITransport(app=brain.app).handle_async_request(request)
            if host == 'litellm':
                if request.method == 'GET':
                    import engine_models
                    return httpx.Response(200, json={'data':[{'model_name':name, 'litellm_params':{'model':'placeholder/provider'}, 'model_info':{'input_cost_per_token':.000001,'output_cost_per_token':.000002}} for name in (*engine_models.OPEN,'placeholder-base-model')]})
                provider_calls.append(request)
                return httpx.Response(200, headers={'x-litellm-response-cost': '.00056'}, json={'id':'placeholder-completion', 'model':json.loads(request.content).get('model'),
                    'choices':[{'message':{'content':'placeholder verified business'}}],
                    'usage':{'prompt_tokens':400,'completion_tokens':80,'total_tokens':480}})
            if request.method in {'GET', 'HEAD'} and host not in {'tank', 'hermes', 'agent-base', 'base-brain', 'litellm'}:
                return httpx.Response(404, text='No public fixture evidence')
            raise AssertionError('Unconfigured external boundary: ' + str(host))

    import base_public_http
    # No real public host is contacted; retain request/redirect/block policy without wall-clock politeness sleeps.
    monkeypatch.setattr(base_public_http, 'HOST_INTERVAL', 0)
    network = LocalNetwork()
    # Storage faults must affect the real product client too, not just brain HTTP.
    monkeypatch.setattr(stack.http, '_transport', network)
    def local_http(**kwargs):
        return REAL_HTTP(transport=network, **kwargs)
    # Change only the HTTP transport. The worker, brain and receipt code remain real.
    import brain_route
    monkeypatch.setattr(brain_route, 'httpx', SimpleNamespace(AsyncClient=local_http))
    monkeypatch.setattr(brain, 'httpx', SimpleNamespace(AsyncClient=local_http))
    import agent_skills
    monkeypatch.setattr(agent_skills, 'httpx', SimpleNamespace(AsyncClient=local_http, HTTPError=httpx.HTTPError))
    import paid_http
    outbound = paid_http.Client(transport=network)
    monkeypatch.setattr(main, '_http', outbound)
    room_app.app.state.http = outbound
    tank = REAL_HTTP(transport=httpx.ASGITransport(app=main.app), base_url='http://tank')
    room_http = REAL_HTTP(transport=httpx.ASGITransport(app=room_app.app), base_url='http://agent-base:8000')

    def headers(user=USER_A, tenant=None):
        return {'X-Tank-Key': SERVICE, **provider.workspace_headers(user, tenant or stack.tenant)}
    async def request(path, body=None, *, method='POST', user=USER_A, tenant=None, extra=None):
        body = {'tenant_id': tenant or stack.tenant, **(body or {})}
        h = headers(user, tenant)
        h.update(extra or {})
        return await tank.request(method, '/v1/base/' + path, headers=h,
            **({'params': body} if method=='GET' else {'json':body}))
    async def submit(*, user=USER_A, tenant=None, request_id=None, count=1, control='edit', **claims):
        from uuid import uuid4
        body = {'created_by':user,'batch':'placeholder-batch', 'request_id':str(request_id or uuid4()),
                'records':[{'name':'placeholder-business','website':'https://placeholder.example'} for _ in range(count)], **claims}
        if control != 'historical':
            body['memory_control'] = control
        return await request('run', body, user=user, tenant=tenant)
    async def snapshot():
        rows = await pool.fetch(f'SELECT * FROM {stack.records.schema("base")}.memory_records ORDER BY id')
        return [dict(row) for row in rows]
    async def queued(task_id, tenant=None):
        return await pool.fetchrow('SELECT * FROM agent_base.tasks WHERE id=$1 AND tenant_id=$2', UUID(str(task_id)), UUID(tenant or stack.tenant))
    entry = SimpleNamespace(stack=stack, pool=pool, main=main, app=room_app, room=room, worker=worker,
        brain=brain, client=tank, room_http=room_http, request=request, submit=submit, queued=queued,
        headers=headers, snapshot=snapshot, provider_calls=provider_calls, requests=requests, faults=faults)
    try:
        yield entry
    finally:
        task = getattr(room_app.app.state, 'base_worker', None)
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await pool.execute('DELETE FROM agent_base.records WHERE tenant_id=ANY($1::uuid[])',[UUID(stack.tenant),UUID(stack.other_tenant)])
        await pool.execute('DELETE FROM agent_base.tasks WHERE tenant_id=ANY($1::uuid[])',[UUID(stack.tenant),UUID(stack.other_tenant)])
        await tank.aclose()
        await room_http.aclose()
        await outbound.aclose()
        await pool.close()
