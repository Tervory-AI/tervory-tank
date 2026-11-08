"""Rig's wire harness: real sign-in, Tank client, product routes and Hermes.

Requests enter the actual Tank app, grant checks and explicit Rig routes.
The transport switches local app destinations without implementing routes.
The issuer and external providers are offline; SQL and Qdrant are real.
"""
from __future__ import annotations

import importlib.util
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

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
        import asyncio
        self.worker_lock = asyncio.Lock()

    def headers(self, user=USER_A, tenant=None):
        return {'X-Tank-Key': PLACEHOLDER_WORKSPACE_KEY, **self.provider.workspace_headers(
            user, tenant or self.stack.tenant)}

    async def request(self, method, path, *, user=USER_A, tenant=None, body=None, headers=None):
        tenant = tenant or self.stack.tenant
        data = dict(body or {})
        if method != 'GET':
            data.setdefault('tenant_id', tenant)
        target = '/v1/rig' + path if path.startswith(('/memory/', '/tasks')) else path
        return await self.ingress.request(method, target,
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

    async def open_worker(self):
        async with self.worker_lock:
            if not self.worker_open:
                from products.rig_provider_fixture import worker_corridor
                await self.resources.enter_async_context(worker_corridor(self, self.monkeypatch, ROOT))
                self.worker_open = True

    async def delegate(self, question='placeholder build a display stand', *, user=USER_A,
                       tenant=None, run_id=None):
        from chassis.tank import TankClient
        from chassis.user_assertion import SignedUser
        await self.open_worker()
        tenant = tenant or self.stack.tenant
        client = TankClient('http://placeholder-tank', self.stack.key, 'rig', self.ingress)
        return await client.delegate_task(SignedUser(tenant, user, 'member'), str(run_id or uuid4()),
            'rig.build', {'messages': [{'role': 'user', 'content': question}]}, [])

    async def build(self, question='placeholder build a display stand', *, user=USER_A,
                    tenant=None, task_id=None):
        tenant = tenant or self.stack.tenant
        await self.open_worker()
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
        result = await self.ingress.get('/v1/rig/tasks/' + identity,
            params={'tenant_id': tenant, 'home_region': 'us-east'}, headers=self.headers(user, tenant))
        assert result.status_code == 200, result.text
        return result.json()


@pytest_asyncio.fixture
async def rig_wire(gate78_memory, gate78_database, monkeypatch, tmp_path, request):
    require_runtime()
    monkeypatch.setenv("DATABASE_URL", gate78_database)
    monkeypatch.setenv("LITELLM_MASTER_KEY", "placeholder-provider-key")
    stack = await gate78_memory('rig')
    import identity_oidc
    import paid_http
    from chassis.memory import MemoryClient
    from chassis.user_assertion import PostgresNonces
    from trigger_signin_fakes import Provider, install_registry

    # No mutable product or core overlay: imports must resolve inside this Tank checkout.
    monkeypatch.syspath_prepend(str(ROOT / 'agents/rig'))
    from rigbox.store import PgStore
    spec = importlib.util.spec_from_file_location('rig_gate78_entry', ROOT / 'agents/rig/app.py')
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, module)
    monkeypatch.setenv('TANK_KEY', stack.key)
    monkeypatch.setenv('TANK_KEY_RIG', stack.key)
    monkeypatch.setenv('TANK_API_KEY', PLACEHOLDER_WORKSPACE_KEY)
    monkeypatch.delenv('RIG_ROOM_TENANT', raising=False)
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

    (tmp_path / 'brain').symlink_to(ROOT / 'agents/_brain', target_is_directory=True)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setenv('PYTHONPATH', ':'.join([str(tmp_path), str(ROOT / 'agents/rig'), str(ROOT / 'agents/_chassis'), str(ROOT / 'tank'), str(ROOT)]))
    import rig_brain.service as brain
    brain.app.state.pool = stack.records.pool
    brain.app.state.product_nonce_stores = {'rig': nonces}
    original_client = httpx.AsyncClient
    captured = []

    async def observe(request):
        captured.append(request)

    async def room(request):
        target = brain.app if request.url.path.startswith(('/tasks', '/delegate')) else product
        return await httpx.ASGITransport(app=target).handle_async_request(request)

    async with paid_http.Client(transport=httpx.MockTransport(room),
                                event_hooks={'request': [observe]}, follow_redirects=False) as relay:
        import command
        import main
        monkeypatch.setattr(main, 'TANK_API_KEY', PLACEHOLDER_WORKSPACE_KEY)
        monkeypatch.setattr(main, '_pool', stack.records.pool)
        monkeypatch.setattr(main, '_admin_pool', stack.records.pool)
        monkeypatch.setattr(main, '_http', relay)
        monkeypatch.setattr(command, 'db', lambda pool=stack.records.pool: pool)
        await stack.records.pool.execute((ROOT / 'tank/schema.sql').read_text())
        for tenant in (stack.tenant, stack.other_tenant):
            await stack.records.pool.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1::uuid,'rig','placeholder-founder') ON CONFLICT DO NOTHING", tenant)
        async with original_client(transport=httpx.ASGITransport(app=main.app),
                                   base_url='http://placeholder-tank') as ingress:
            wire = RigWire(stack, provider, ingress, product, relay, stack.records.pool, tmp_path)
            wire.captured = captured
            wire.monkeypatch = monkeypatch
            async with AsyncExitStack() as resources:
                wire.resources = resources
                try:
                    yield wire
                finally:
                    import json
                    output = ROOT / '.tmp/gates78/rig-observed'
                    output.mkdir(parents=True, exist_ok=True)
                    runs = []
                    for path in tmp_path.rglob('receipt.json'):
                        row = json.loads(path.read_text())
                        runs.append({key: row.get(key) for key in ('status', 'paid_calls', 'cost_usd',
                            'tokens_in', 'tokens_out', 'would_have_cost', 'answered_from_memory', 'memory_status')})
                    (output / (request.node.name + '.json')).write_text(json.dumps({
                        'test': request.node.nodeid, 'provider_calls': wire.provider_calls, 'runs': runs}, indent=2))
    for task in list(brain.jobs.values()):
        task.cancel()
    if brain.jobs:
        import asyncio
        await asyncio.gather(*list(brain.jobs.values()), return_exceptions=True)
