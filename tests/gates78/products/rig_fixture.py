"""Rig's wire harness: real sign-in, Tank client, product routes and Hermes.

The ASGI relay only transports a request through shipped call_room/paid_http.
It implements no product route, ownership check, memory or receipt behavior.
The issuer and external providers are offline; SQL and Qdrant are real.
"""
from __future__ import annotations

from contextlib import AsyncExitStack

import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from starlette.requests import Request
from starlette.responses import Response

ROOT = Path(__file__).resolve().parents[3]
USER_A = 'placeholder-rig-owner'
USER_B = 'placeholder-rig-peer'
USER_C = 'placeholder-rig-other-tenant'
PLACEHOLDER_WORKSPACE_KEY = 'placeholder-gate78-workspace-key'
RUNTIME_FILES = (
    'agents/rig/gates_memory.py', 'agents/rig/memory_api.py',
    'agents/rig/actor_context.py', 'agents/rig/rig_brain_client.py',
    'agents/rig/rigbox/savings.py', 'tank/rig_savings.py',
    'tank/rig_brain_routing.py',
)


def require_runtime():
    missing = [name for name in RUNTIME_FILES if not (ROOT / name).is_file()]
    if missing:
        pytest.fail('BLOCKED: authoritative Rig runtime is not integrated into this Tank candidate: '
                    + ', '.join(missing) + '. Integrate Rig PR #11 and its reviewed Gate 6 dependencies; '
                    'never overlay obsolete Hermes proposal patches.', pytrace=False)


class RigWire:
    def __init__(self, stack, provider, ingress, product, relay, pool, root):
        self.stack, self.provider = stack, provider
        self.ingress, self.product, self.relay = ingress, product, relay
        self.pool, self.root = pool, root
        self.captured = []
        self.provider_calls = []
        self.memory_failure = None
        self.worker_open = False

    def headers(self, user=USER_A, tenant=None):
        return {'X-Tank-Key': PLACEHOLDER_WORKSPACE_KEY, **self.provider.workspace_headers(
            user, tenant or self.stack.tenant)}

    async def request(self, method, path, *, user=USER_A, tenant=None, body=None, headers=None):
        tenant = tenant or self.stack.tenant
        data = dict(body or {})
        if method != 'GET':
            data.setdefault('tenant_id', tenant)
        return await self.ingress.request(method, path,
            params={'tenant_id': tenant} if method == 'GET' else None,
            json=data if method != 'GET' else None,
            headers=headers if headers is not None else self.headers(user, tenant))

    async def edit(self, text='placeholder private build', *, user=USER_A, tenant=None, **changes):
        return await self.request('POST', '/memory/edit', user=user, tenant=tenant, body={
            'text': text, 'kind': 'rig.build', 'source': 'urn:placeholder:rig:gate78',
            'task_key': 'rig.build', **changes})

    async def rows(self, user=USER_A, tenant=None):
        response = await self.request('GET', '/memory/records', user=user, tenant=tenant)
        assert response.status_code == 200, response.text
        return response.json()['memories']

    async def persistent(self):
        schema = self.stack.records.schema('rig')
        return [dict(row) for row in await self.pool.fetch(
            f'SELECT id, tenant_id, claim, meta FROM {schema}.memory_records ORDER BY id')]

    async def build(self, question='placeholder build a display stand', *, user=USER_A,
                    tenant=None, task_id=None):
        tenant = tenant or self.stack.tenant
        if not self.worker_open:
            from rig_provider_fixture import worker_corridor
            await self.resources.enter_async_context(worker_corridor(self, self.monkeypatch, ROOT))
            self.worker_open = True
        identity = str(task_id or uuid4())
        answer = await self.request('POST', '/tasks', user=user, tenant=tenant, body={
            'task_id': identity, 'home_region': 'us-east', 'question': question})
        assert answer.status_code in (200, 202), answer.text
        # Execute the shipped worker, never a fabricated child receipt.
        import asyncio
        import rig_brain.service as brain
        job = brain.jobs.get((tenant, identity))
        if job is not None:
            await asyncio.wait_for(asyncio.shield(job), timeout=90)
        result = await self.ingress.get('/tasks/' + identity,
            params={'tenant_id': tenant, 'home_region': 'us-east'}, headers=self.headers(user, tenant))
        assert result.status_code == 200, result.text
        return result.json()


@pytest_asyncio.fixture
async def rig_wire(gate78_memory, monkeypatch, tmp_path):
    require_runtime()
    stack = await gate78_memory('rig')
    from chassis.memory import MemoryClient
    from chassis.user_assertion import PostgresNonces
    import identity_oidc
    import paid_http
    import ghost_routes
    from trigger_signin_fakes import Provider, install_registry
    from trigger_signin_guard import TriggerSigninMiddleware

    # No mutable product or core overlay: imports must resolve inside this Tank checkout.
    monkeypatch.syspath_prepend(str(ROOT / 'agents/rig'))
    from rigbox.store import PgStore
    spec = importlib.util.spec_from_file_location('rig_gate78_entry', ROOT / 'agents/rig/app.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.setenv('TANK_KEY', stack.key)
    monkeypatch.setenv('TANK_KEY_RIG', stack.key)
    monkeypatch.setenv('TANK_API_KEY', PLACEHOLDER_WORKSPACE_KEY)
    monkeypatch.setenv('RIG_ROOM_TENANT', stack.tenant)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('RIG_MEMORY_ENABLED', 'true')
    monkeypatch.setenv('RIG_BRAIN_ENABLED', 'true')
    spec.loader.exec_module(module)
    product = module.app
    product.state.pool = stack.records.pool
    product.state.memory = MemoryClient('http://hermes', stack.key, 'rig', stack.http)
    nonces = PostgresNonces(stack.records.pool, 'rig')
    # Namespace only, exactly like the canonical memory fixture; real atomic SQL.
    nonces.schema = stack.records.schema('rig')
    product.state.product_nonce_stores = {'rig': nonces}
    product.state.missing_settings = []
    store = PgStore(stack.records.pool)
    await store.apply_schema()
    from rigbox.service import Service
    product.state.rig = Service(store, module._TankModels(None))
    product.state.rig.models.app = product

    provider = Provider('us-east')
    install_registry(monkeypatch, [provider], {'10001': stack.tenant, '10002': stack.other_tenant})
    monkeypatch.setattr(identity_oidc, 'http_client',
                        lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    identity_oidc._cache.clear()

    import rig_brain.service as brain
    brain.app.state.pool = stack.records.pool
    brain.app.state.product_nonce_stores = {'rig': nonces}
    original_client = httpx.AsyncClient
    captured = []

    async def observe(request):
        captured.append(request)

    async def room(request):
        target = brain.app if request.url.path.startswith('/tasks') else product
        return await httpx.ASGITransport(app=target).handle_async_request(request)

    async with paid_http.Client(transport=httpx.MockTransport(room),
                                event_hooks={'request': [observe]}, follow_redirects=False) as relay:
        runtime = SimpleNamespace(_http=relay, TANK_API_KEY=PLACEHOLDER_WORKSPACE_KEY, box_region=lambda: 'us-east')
        monkeypatch.setattr(ghost_routes, 'runtime', lambda: runtime)
        # Only the existing OIDC middleware's configuration read is supplied here.
        import main
        monkeypatch.setattr(main, 'TANK_API_KEY', PLACEHOLDER_WORKSPACE_KEY)

        async def handoff(scope, receive, send):
            request = Request(scope, receive)
            raw = await request.body()
            body = json.loads(raw) if raw else None
            response = await ghost_routes.call_room(request.method, 'rig', request.url.path,
                body=body, params=list(request.query_params.multi_items()),
                tenant=(body or {}).get('tenant_id') or request.query_params.get('tenant_id'))
            await Response(response.content, status_code=response.status_code,
                           media_type='application/json')(scope, receive, send)

        async with original_client(transport=httpx.ASGITransport(app=TriggerSigninMiddleware(handoff)),
                                   base_url='http://placeholder-tank') as ingress:
            wire = RigWire(stack, provider, ingress, product, relay, stack.records.pool, tmp_path)
            wire.captured = captured
            wire.monkeypatch = monkeypatch
            async with AsyncExitStack() as resources:
                wire.resources = resources
                yield wire
    for task in list(brain.jobs.values()):
        task.cancel()
    if brain.jobs:
        import asyncio
        await asyncio.gather(*list(brain.jobs.values()), return_exceptions=True)
