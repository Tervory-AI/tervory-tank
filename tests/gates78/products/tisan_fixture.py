"""Tisan ingress on the canonical stack; no private product/Hermes overlays.

Only the local signed issuer and external HTTP responses are fixture boundaries.
Missing runtime integrations fail explicitly, before claiming scenario evidence.
"""
from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[3]
USER_A = 'placeholder-tisan-user-a'
USER_B = 'placeholder-tisan-user-b'
KEY = 'placeholder-gate78-product-key'
WORKSPACE_KEY = 'placeholder-tisan-workspace-key'
FIXTURE_COST = 0.0025
FIXTURE_INPUT = 1200
FIXTURE_OUTPUT = 300

@pytest.fixture
def tisan_runtime():
    paths = ('agents/tisan/gates_memory.py', 'agents/tisan/memory_api.py',
             'agents/tisan/brain_service.py', 'agents/tisan/plan_jobs.py')
    absent = [path for path in paths if not (ROOT / path).is_file()]
    if absent:
        pytest.fail('BLOCKED: Tank platform lacks authoritative Tisan PR #1 runtime: ' + ', '.join(absent)
                    + '. Head must integrate that product runtime; no private overlay or obsolete Hermes patch is used.')
    runtime = {name: importlib.import_module('agents.tisan.' + name)
               for name in ('app', 'builder', 'gates_memory', 'memory_api', 'brain_service')}
    import tisan_requests
    if not hasattr(tisan_requests, 'memory_request'):
        pytest.fail('BLOCKED: fixed Tank lacks Tisan memory-control forwarding. Needs a minimal current-core adapter using product_identity, not the obsolete timestamp signer.')
    assert hasattr(runtime['builder'], 'remembered_plan'), 'Integrated builder must contain the actual Gate 7/8 plan path'
    return SimpleNamespace(**runtime)

class Observe:
    """Read-only observation of actual ASGI identity verification, never a signer."""
    def __init__(self, app):
        self.app, self.states = app, []

    async def __call__(self, scope, receive, send):
        await self.app(scope, receive, send)
        if scope['type'] == 'http':
            self.states.append(dict(scope.get('state', {})))

class Tisan:
    def __init__(self, runtime, stack, provider, tank_http, room, monkeypatch, tmp_path):
        self.runtime, self.stack, self.provider = runtime, stack, provider
        self.http, self.room = tank_http, room
        self.monkeypatch, self.root = monkeypatch, tmp_path
        self.provider_calls, self.events = [], []
        self.transport_outage = None

    def headers(self, user=USER_A, tenant=None):
        return {'X-Tank-Key': WORKSPACE_KEY,
                **self.provider.workspace_headers(user, tenant or self.stack.tenant)}

    async def control(self, method, suffix='', *, user=USER_A, tenant=None, body=None):
        headers = self.headers(user, tenant)
        url = '/v1/command/tisan/memory' + suffix
        response = await self.http.request(method, url, headers=headers, json=body) if body is not None else await self.http.request(method, url, headers=headers)
        return response

    async def view(self, user=USER_A, tenant=None):
        response = await self.control('GET', user=user, tenant=tenant)
        assert response.status_code == 200, response.text
        return response.json()

    async def records(self, user=USER_A, tenant=None):
        return await self.stack.records.list('tisan', tenant or self.stack.tenant, user_id=user)

    async def plan(self, request='placeholder first brief', *, user=USER_A, tenant=None, plan=None, run_id=None):
        """Sign in, enqueue a durable room job, claim it and run its real handler."""
        from tisan_worker_fixture import finish_job
        tenant = tenant or self.stack.tenant
        payload = {'name': 'placeholder site', 'slug': 'placeholder-site', 'locale': 'en',
            'brand': {'colours': {'ink': '#001840', 'paper': '#F4F6FB', 'accent': '#E80008', 'line': '#B8BFD0'},
                      'fonts': {'heading': 'Jost', 'body': 'Inter'}}, 'request': request}
        if plan is not None:
            payload['plan'] = plan
        self.last_brief = payload
        response = await self.http.post('/v1/command/tisan/plan', headers=self.headers(user, tenant),
            json={'run_id': run_id or str(uuid.uuid4()), 'brief': payload})
        assert response.status_code == 200, (response.text, self.events)
        return await finish_job(self, response.json()['job_id'], tenant)

    async def correct(self, memory_id, value, user=USER_A):
        response = await self.control('POST', '/' + memory_id, user=user, body={'value': value})
        assert response.status_code == 200, response.text
        return response.json()

    async def counts(self):
        return {'provider_calls': len(self.provider_calls),
                'cost': sum(c['cost'] for c in self.provider_calls),
                'tokens': sum(c['input'] + c['output'] for c in self.provider_calls)}

@pytest_asyncio.fixture
async def tisan(tisan_runtime, gate78_memory, monkeypatch, tmp_path):
    """Wire production routers and clients to real shared memory/SQL only."""
    from fastapi import FastAPI
    import command
    import main
    import identity_oidc
    import paid_http
    from trigger_signin_guard import TriggerSigninMiddleware
    from trigger_signin_fakes import Provider, install_registry, set_founders, ORG
    from chassis.memory import MemoryClient
    from chassis.db import ensure_schema
    from chassis.tenant_db import TenantPool
    from chassis.roles import apply_roles
    import asyncpg
    from urllib.parse import urlsplit, urlunsplit
    import tisan_requests

    stack = await gate78_memory('tisan')
    provider = Provider('us-east')
    install_registry(monkeypatch, [provider], {ORG: stack.tenant, '10002': stack.other_tenant})
    set_founders(monkeypatch, USER_A + ',' + USER_B)
    monkeypatch.setattr(identity_oidc, 'http_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    identity_oidc._cache.clear()
    for name, value in {'TANK_API_KEY': WORKSPACE_KEY, 'TANK_KEY': KEY, 'TANK_KEY_TISAN': KEY,
                        'TANK_REGION': 'us-east', 'TISAN_BRAIN_ENABLED': 'true',
                        'TERVORY_ADMIN_USER_IDS': USER_A + ',' + USER_B,
                        'DATA_DIR': str(tmp_path), 'TANK_URL': 'http://placeholder-tank',
                        'HERMES_URL': 'http://hermes'}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(main, 'TANK_API_KEY', WORKSPACE_KEY)
    monkeypatch.setenv('ENGINE_LOCAL_URL', '')
    monkeypatch.setattr(main, '_roster_cache', None)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://127.0.0.1/placeholder-fixture')
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder-fixture-gateway')
    room = Observe(tisan_runtime.app.app)
    tisan_runtime.app.app.state.pool = stack.records.pool
    tisan_runtime.app.app.state.memory = MemoryClient('http://hermes', KEY, 'tisan', stack.http)
    product_transport = httpx.ASGITransport(app=room)
    app = FastAPI()
    app.include_router(command.router)
    app.include_router(tisan_requests.build_router())
    app.add_middleware(TriggerSigninMiddleware)
    app_transport = httpx.ASGITransport(app=app)
    native_transport = httpx.ASGITransport(app=main.app)

    database = 'placeholder_tisan_gate78_' + uuid.uuid4().hex
    import os
    database_url = os.environ['MEMORY_TEST_DATABASE_URL']
    async with stack.records.pool.acquire() as admin:
        await admin.execute('CREATE DATABASE "' + database + '"')
    target = urlunsplit(urlsplit(database_url)._replace(path='/' + database))
    core_pool = await asyncpg.create_pool(target, min_size=1, max_size=5)
    async with core_pool.acquire() as conn:
        await conn.execute((ROOT / 'tank/schema.sql').read_text())
        await ensure_schema(conn, 'tisan')
        from tisan_worker_fixture import configure_ladder
        await configure_ladder(conn, stack)
        await apply_roles(conn, {'AGENT_DB_PASSWORD_TISAN': 'placeholder-disposable-test-password'})
        async with conn.transaction():
            await conn.execute('SET LOCAL ROLE agent_tisan')
            await conn.execute(Path(tisan_runtime.builder.__file__).with_name('schema.sql').read_text())
    async def room_role(connection):
        await connection.execute('SET ROLE agent_tisan')
    raw_room_pool = await asyncpg.create_pool(target, min_size=1, max_size=4, init=room_role)
    room_pool = TenantPool(raw_room_pool)
    tisan_runtime.app.app.state.pool = room_pool
    tisan_runtime.brain_service.app.state.pool = room_pool
    monkeypatch.setattr(main, 'pool', lambda: core_pool)
    monkeypatch.setattr(main, 'DATABASE_URL', target)
    monkeypatch.setattr(main, 'LITELLM_MASTER_KEY', 'placeholder-fixture-gateway')
    monkeypatch.setattr(main, 'LITELLM_URL', 'http://placeholder-litellm')
    harness = None

    async def room_edge(request):
        from tisan_transport_fixture import room_edge as dispatch
        return await dispatch(request, tisan_runtime, product_transport, native_transport, stack, harness,
                              FIXTURE_COST, FIXTURE_INPUT, FIXTURE_OUTPUT)

    original_client = httpx.AsyncClient
    def offline_client(*args, **kwargs):
        kwargs.setdefault('transport', httpx.MockTransport(room_edge))
        return original_client(*args, **kwargs)
    monkeypatch.setattr(httpx, 'AsyncClient', offline_client)
    try:
        async with paid_http.Client(transport=httpx.MockTransport(room_edge)) as shipping_client, \
                httpx.AsyncClient(transport=httpx.MockTransport(room_edge)) as room_client:
            monkeypatch.setattr(main, '_http', shipping_client)
            tisan_runtime.app.app.state.memory = MemoryClient('http://hermes', KEY, 'tisan', room_client)
            async with httpx.AsyncClient(transport=app_transport, base_url='http://placeholder-tank') as ingress:
                harness = Tisan(tisan_runtime, stack, provider, ingress, room, monkeypatch, tmp_path)
                from chassis.tank import TankClient
                tisan_runtime.app.app.state.tank = TankClient('http://placeholder-tank', KEY, 'tisan', room_client)
                monkeypatch.setitem(tisan_runtime.brain_service._tank, 'client', tisan_runtime.app.app.state.tank)
                tisan_runtime.app.app.state.files = None
                tisan_runtime.app.app.state.browser = None
                yield harness
    finally:
        await raw_room_pool.close()
        await core_pool.close()
        async with stack.records.pool.acquire() as admin:
            await admin.execute('DROP DATABASE "' + database + '"')

def corrected_plan(value):
    result = copy.deepcopy(value)
    result['pages'].append({'name': 'contact', 'path': '/contact', 'sections': []})
    return result
