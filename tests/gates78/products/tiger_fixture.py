"""Tiger entry-path wiring; only external HTTP and embeddings are fixtures.

The canonical run imports runtime from this Tank checkout. Missing product sync
is an explicit failure, never an import fallback to a proposal or private core.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest_asyncio
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[3]
USER_A = 'placeholder-user-a'
USER_B = 'placeholder-user-b'
MODEL = 'placeholder-tiger-model'
KEY = 'placeholder-gate78-product-key'
WORKSPACE_KEY = 'placeholder-gate78-workspace-key'
PREFIX = '/v1/command/tiger/watches'
RUNTIME = ('gates_api.py', 'gates_brain.py', 'gates_brain_service.py', 'gates_memory.py')


def runtime_dependencies():
    missing = [f'agents/tiger/{name}' for name in RUNTIME if not (ROOT / 'agents/tiger' / name).is_file()]
    assert not missing, 'BLOCKED: Tiger PR #3 runtime not integrated: ' + ', '.join(missing)


def load_room(monkeypatch):
    runtime_dependencies()
    monkeypatch.syspath_prepend(str(ROOT / 'agents/tiger'))
    spec = importlib.util.spec_from_file_location('gate78_tiger_room', ROOT / 'agents/tiger/app.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


class TigerSystem:
    def __init__(self, **values):
        self.__dict__.update(values)

    def headers(self, user=USER_A, tenant=None):
        return {'X-Tank-Key': WORKSPACE_KEY,
                **self.issuer.workspace_headers(user, tenant or self.memory.tenant)}

    async def request(self, method, path, body=None, *, user=USER_A, tenant=None, headers=None):
        return await self.http.request(method, PREFIX + path, json=body,
                                       headers=headers or self.headers(user, tenant))

    async def task(self, payload=None, *, task='tiger.supplier', run_id=None, user=USER_A, tenant=None):
        return await self.request('POST', '/brain/tasks', {
            'task_key': task, 'input': payload or {'sku': 'placeholder-sku'},
            'run_id': run_id or str(uuid4()),
        }, user=user, tenant=tenant)

    async def rows(self, user=USER_A, tenant=None):
        response = await self.request('GET', '/memory', user=user, tenant=tenant)
        assert response.status_code == 200, response.text
        return response.json()

    async def snapshot(self):
        schema = self.memory.records.schema('tiger')
        async with self.memory.records.pool.acquire() as conn:
            rows = await conn.fetch(f'SELECT row_to_json(r)::text AS row FROM {schema}.memory_records r ORDER BY id')
        async with self.pool.acquire() as conn:
            receipts = await conn.fetch('SELECT row_to_json(r)::text AS row FROM tank.agent_receipts r ORDER BY ledger_id')
        return [r['row'] for r in rows], [r['row'] for r in receipts]

    async def ledger(self):
        async with self.pool.acquire() as conn:
            return await conn.fetch('SELECT * FROM tank.ledger ORDER BY ts,id')

    def restart_nonces(self):
        from chassis.user_assertion import PostgresNonces
        for app in (self.room, self.brain):
            store = PostgresNonces(self.memory.records.pool, 'tiger')
            store.schema = self.memory.records.schema('tiger')
            app.state.product_nonce_stores = {'tiger': store}


@pytest_asyncio.fixture
async def tiger_system(gate78_memory, gate78_database, monkeypatch):
    runtime_dependencies()
    memory = await gate78_memory('tiger')
    for name, value in {'DATABASE_URL': gate78_database, 'TANK_API_KEY': WORKSPACE_KEY,
                        'LITELLM_MASTER_KEY': 'placeholder-model-key', 'TANK_REGION': 'us-east',
                        'TANK_KEY_TIGER': KEY, 'TANK_KEY': KEY, 'TIGER_BRAIN_ENABLED': 'true',
                        'TANK_URL': 'http://placeholder-tank', 'HERMES_URL': 'http://hermes',
                        'TIGER_AGENT_URL': 'http://agent-tiger:8000',
                        'TIGER_BRAIN_URL': 'http://tiger-brain:8001'}.items():
        monkeypatch.setenv(name, value)
    import main
    import paid_http
    import paid_steps
    import controls
    import identity_oidc
    import agent_skills
    import tiger_watch_commands
    from trigger_signin_guard import TriggerSigninMiddleware
    from trigger_signin_fakes import Provider, install_registry
    room = load_room(monkeypatch)
    import gates_brain_service
    brain = gates_brain_service.app
    command_router = tiger_watch_commands.build_router()
    paths = {route.path for route in command_router.routes}
    required = {PREFIX + path for path in ('/memory', '/memory/{record_id}', '/memory/setting',
                                          '/memory/correction', '/brain/tasks')}
    assert required <= paths, 'BLOCKED: Tiger authenticated ingress not integrated: ' + ', '.join(sorted(required - paths))
    admin = await asyncpg.connect(gate78_database)
    name = 'placeholder_tiger_gate78_' + uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    url = urlsplit(gate78_database)._replace(path='/' + name).geturl()
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    opened = []
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / 'tank/schema.sql').read_text())
            await paid_steps.register(conn, paid_steps.model_step('agent.tiger.think', MODEL, agent='tiger'),
                                      'tiger', 'model', 'placeholder-policy', task='agent.tiger.think', model=MODEL)
            for tenant in (memory.tenant, memory.other_tenant):
                await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'tiger','placeholder-admin')", UUID(tenant))
                await conn.execute("INSERT INTO tank.policy(task_type,tenant_id,model,rung,max_tokens_out) VALUES('agent.tiger.think',$1,$2,1,100)", UUID(tenant), MODEL)
                await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto',$3)",
                                   UUID(tenant), paid_steps.model_step('agent.tiger.think', MODEL, agent='tiger'), USER_A)
        monkeypatch.setattr(main, 'pool', lambda: pool)
        monkeypatch.setattr(main, 'TANK_API_KEY', WORKSPACE_KEY)
        monkeypatch.setattr(main, 'TIGER_AGENT_URL', 'http://agent-tiger:8000')
        monkeypatch.setattr(main, 'LITELLM_URL', 'http://placeholder-model')
        monkeypatch.setattr(main, 'LITELLM_MASTER_KEY', 'placeholder-model-key')
        monkeypatch.setattr(paid_steps, 'db', lambda: pool)
        monkeypatch.setattr(controls, 'db', lambda: pool)
        # Fixture policy/roster data, not a replacement for admission or accounting.
        async def roster():
            return [{'model_name': MODEL, 'model_info': {'input_cost_per_token': .001,
                    'output_cost_per_token': .002, 'family': 'placeholder-family'}}]
        monkeypatch.setattr(main, '_roster_models', roster)
        issuer = Provider('us-east')
        install_registry(monkeypatch, [issuer], {'10001': memory.tenant,
                                                '10002': memory.other_tenant})
        identity_oidc._cache.clear()
        tank = FastAPI()
        tank.add_middleware(TriggerSigninMiddleware)
        tank.include_router(command_router)
        tank.include_router(agent_skills.build_router(main))
        observed, sends, assertions = [], [], []
        system = TigerSystem(memory=memory, room=room, brain=brain, pool=pool, issuer=issuer,
                             events=observed, sends=sends, assertions=assertions, outage=None)
        original_client = httpx.AsyncClient

        class Network(httpx.AsyncBaseTransport):
            async def handle_async_request(self, request):
                observed.append((request.method, request.url.host, request.url.path))
                host = request.url.host
                if host == urlsplit(issuer.issuer).hostname:
                    return issuer(request)
                if host == 'placeholder-model':
                    assert request.url.path == '/v1/chat/completions'
                    sends.append(request)
                    return httpx.Response(200, headers={'x-litellm-response-cost': '0.01',
                        'x-litellm-model-group': MODEL}, json={
                        'choices': [{'index': 0, 'message': {'role': 'assistant',
                        'content': '{"supplier":"placeholder-supplier-result"}'}, 'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})
                if host == 'hermes':
                    memory.calls.append((request.method, request.url.path))
                    if system.outage:
                        refusal = system.outage(request)
                        if refusal:
                            return httpx.Response(refusal, json={'detail': 'placeholder-unavailable'})
                    app = memory.app
                elif host == 'agent-tiger':
                    assertions.append(request)
                    app = room
                elif host == 'tiger-brain':
                    app = brain
                elif host == 'placeholder-tank':
                    app = tank
                else:
                    raise AssertionError('Unexpected external boundary: ' + host)
                return await httpx.ASGITransport(app=app).handle_async_request(request)

        class OfflineClient(original_client):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault('transport', Network())
                super().__init__(*args, **kwargs)
        # All HTTP still uses the shipped client; only socket routing changes.
        monkeypatch.setattr(httpx, 'AsyncClient', OfflineClient)
        monkeypatch.setattr(identity_oidc, 'http_client', OfflineClient)
        outbound = paid_http.Client(transport=Network())
        opened.append(outbound)
        monkeypatch.setattr(main, '_http', outbound)
        for app in (room, brain):
            app.state.pool = memory.records.pool
            app.state.http = OfflineClient()
            opened.append(app.state.http)
        system.restart_nonces()
        system.http = OfflineClient(base_url='http://placeholder-tank')
        system.direct = OfflineClient(base_url='http://agent-tiger:8000', headers={'X-Tank-Key': KEY})
        opened.extend([system.http, system.direct])
        yield system
    finally:
        for client in opened:
            await client.aclose()
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()
