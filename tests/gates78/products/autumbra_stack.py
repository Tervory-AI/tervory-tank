"""Autumbra's real request paths; only network edges and the shared encoder are fixtures."""
from contextlib import AsyncExitStack
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode, urlsplit, urlunsplit
import uuid

import asyncpg
import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[3]
A, B = 'placeholder-alice', 'placeholder-bob'
TASK = 'ghost.brain.explain_incident'
TEXT = 'Spike of 403s on /login during the deploy'
COST, TOKENS_IN, TOKENS_OUT = .0042, 310, 95  # FAKE external provider tariff, not billing.
WORKSPACE_KEY = 'placeholder-autumbra-workspace-key'


def require_runtime():
    required = ('agents.ghost.brain', 'agents.ghost.brain_service', 'agents.ghost.brain_state')
    missing = [name for name in required if importlib.util.find_spec(name) is None]
    if not all(task in (ROOT/'tank/schema.sql').read_text() for task in ('ghost.brain.explain_incident','ghost.brain.plan_fix')):
        missing.append('Tank brain policy rows from PR #3 patch')
    if missing:
        pytest.fail('BLOCKED runtime dependency: integrate Autumbra PR #3 source_sha from autumbra.json; missing ' + ', '.join(missing))


@pytest_asyncio.fixture
async def autumbra(gate78_memory, monkeypatch, tmp_path):
    require_runtime()
    from agents.ghost.app import create_app, _brain_service
    from agents.ghost.brain import Brain, UserMemory, classify_alert_code, TASK_TYPES
    from agents.ghost.brain_service import create_app as brain_app
    from agents.ghost.store import Store
    from chassis.memory import MemoryClient
    from trigger_signin_fakes import Provider, install_registry
    import engine_ladder
    import engine_models
    import identity_oidc
    import main as tank
    import paid_http
    import paid_steps
    from tenant_db import TenantPool

    stack = await gate78_memory('autumbra')
    state = SimpleNamespace(provider_calls=[], network=[], signed=[], fault=None)
    original_http, original_paid = httpx.AsyncClient, paid_http.Client
    provider = Provider('us-east')
    install_registry(monkeypatch, [provider], {'10001':stack.tenant, '10002':stack.other_tenant})
    monkeypatch.setattr(identity_oidc, 'http_client', lambda: original_http(transport=httpx.MockTransport(provider)))
    identity_oidc._cache.clear()
    for key, value in {'TANK_KEY':stack.key, 'TANK_KEY_GHOST':stack.key, 'TANK_API_KEY':WORKSPACE_KEY,
                       'GHOST_BRAIN_ENABLED':'true', 'TANK_REGION':'us-east', 'AUTUMBRA_BRAIN_URL':'http://autumbra-brain:8001',
                       'TANK_URL':'http://tank:8000', 'LITELLM_MASTER_KEY':'placeholder-offline-provider'}.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(tank, 'TANK_API_KEY', WORKSPACE_KEY)
    # No live local runtime: catalogue and approvals mirror the available ladder.
    monkeypatch.delenv('ENGINE_LOCAL_URL', raising=False)
    monkeypatch.delenv('ENGINE_LARGE_URL', raising=False)
    models = engine_ladder.order({'model':'luna'})
    state.catalogue = list(models)
    # A private DB for actual policy/admission/ledger code. No fake SQL or receipts.
    admin = await asyncpg.connect(os.environ['MEMORY_TEST_DATABASE_URL'])
    dbname = 'autumbra_gate78_' + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{dbname}"')
    url = urlunsplit(urlsplit(os.environ['MEMORY_TEST_DATABASE_URL'])._replace(path='/' + dbname))
    monkeypatch.setattr(tank, 'DATABASE_URL', url)
    monkeypatch.setattr(tank, 'LITELLM_MASTER_KEY', 'placeholder-offline-provider')
    raw = restricted = old_pool = role = None
    try:
        raw = await asyncpg.create_pool(url, min_size=1, max_size=5)
        monkeypatch.setattr(tank, '_pool', TenantPool(raw))
        monkeypatch.setattr(tank, '_admin_pool', None)
        monkeypatch.setattr(tank, '_redis', None)
        monkeypatch.setattr(tank, '_roster_cache', None)
        monkeypatch.setattr(tank, '_agent_keys_synced', False)
        async with raw.acquire() as conn:
            await conn.execute((ROOT/'tank/schema.sql').read_text())
            policies = await conn.fetch("SELECT task_type FROM tank.policy WHERE task_type LIKE 'ghost.brain.%'")
            assert set(TASK_TYPES) <= {row['task_type'] for row in policies}, 'BLOCKED: apply PR #3 policy/corridor patches to Tank before acceptance'
            for tenant in (stack.tenant, stack.other_tenant):
                for task in TASK_TYPES:
                    for model in models:
                        step = paid_steps.model_step(task, model, agent='ghost')
                        await paid_steps.register(conn, step, 'autumbra', 'model', 'tank.policy', task=task, model=model)
                        await conn.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto','placeholder-offline-owner')",
                                           uuid.UUID(tenant), step)

        # Real non-superuser SQL, with the same schema privileges used by agent roles.
        schema = stack.records.schema('ghost')
        role = 'autumbra_gate78_' + uuid.uuid4().hex
        async with stack.records.pool.acquire() as conn:
            await conn.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
            await conn.execute(f'GRANT USAGE,CREATE ON SCHEMA "{schema}" TO "{role}"')
            await conn.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
        restricted = await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'], min_size=1, max_size=2,
                                             server_settings={'role':role})
        old_pool = stack.records.pool
        stack.records.pool = restricted
        watch = create_app()
        store = Store(tmp_path/'watch.sqlite3')
        watch.state.store = store
        apps = {'agent-ghost':watch, 'hermes':stack.app, 'tank':tank.app}

        async def edge(request):
            state.network.append((request.method, request.url.host, request.url.path))
            if request.url.host in apps:
                if request.url.host == 'hermes' and state.fault and state.fault[0] == (request.method, request.url.path):
                    if state.fault[1] == 'timeout':
                        raise httpx.ReadTimeout('placeholder memory outage', request=request)
                    return httpx.Response(state.fault[1], json={'detail':'Memory request refused.'})
                if request.url.host == 'agent-ghost':
                    state.signed.append((request.method, request.url.raw_path.decode(), request.content, dict(request.headers)))
                response = await httpx.ASGITransport(app=apps[request.url.host]).handle_async_request(request)
                await response.aread()
                return response
            if request.url.host == 'litellm':
                if request.url.path == '/model/info':
                    return httpx.Response(200, json={'data':[{'model_name':model,
                        'litellm_params':{'model':engine_models.SELECTED.get(model, 'placeholder/' + model)},
                        'model_info':{'input_cost_per_token':.000001,'output_cost_per_token':.000001}}
                        for model in state.catalogue]})
                if request.url.path == '/router/settings':
                    return httpx.Response(200, json={'current_values':{'fallbacks':[]}})
                assert request.url.path == '/v1/chat/completions', request.url
                state.provider_calls.append(json.loads(request.content))
                return httpx.Response(200, headers={'x-litellm-response-cost':str(COST), 'x-litellm-model-group':state.provider_calls[-1]['model']},
                    json={'choices':[{'message':{'content':f'Fixture analysis {len(state.provider_calls)}: inspect the deployment rule.'}}],
                          'usage':{'prompt_tokens':TOKENS_IN,'completion_tokens':TOKENS_OUT}})
            raise AssertionError('Unexpected network edge: ' + str(request.url))

        def http(*args, **kwargs):
            kwargs.setdefault('transport', httpx.MockTransport(edge))
            return original_http(*args, **kwargs)

        def paid(*args, **kwargs):
            kwargs.setdefault('transport', httpx.MockTransport(edge))
            return original_paid(*args, **kwargs)

        monkeypatch.setattr(httpx, 'AsyncClient', http)
        monkeypatch.setattr(paid_http, 'Client', paid)
        async with AsyncExitStack() as cleanup:
            network = await cleanup.enter_async_context(http())
            tank_http = await cleanup.enter_async_context(paid())
            monkeypatch.setattr(tank, '_http', tank_http)
            apps['autumbra-brain'] = brain_app(network)
            watch.state.user_memory = UserMemory(MemoryClient('http://tank:8000/v1/ghost/autumbra/memory', stack.key, 'ghost', network), store)
            watch.state.brain = Brain(watch.state.user_memory, _brain_service(network), [classify_alert_code])
            client = await cleanup.enter_async_context(original_http(transport=httpx.ASGITransport(app=tank.app), base_url='http://tank'))
            direct = await cleanup.enter_async_context(original_http(transport=httpx.ASGITransport(app=watch), base_url='http://agent-ghost',
                                                                    headers={'X-Tank-Key':stack.key}))
            async def request(method, path, *, user=A, tenant=None, body=None, headers=None, role="org_admin"):
                tenant = tenant or stack.tenant
                identity = {'X-Tank-Key':WORKSPACE_KEY, **provider.workspace_headers(user, tenant, role=role), **(headers or {})}
                return await client.request(method, '/v1/ghost/autumbra/personal' + path, headers=identity, **({'json':body} if body is not None else {}))

            async def task(*, user=A, tenant=None, text=TEXT, task_type=TASK, run_id=None):
                tenant = tenant or stack.tenant
                body = {'tenant_id':tenant,'user_id':user,'task_type':task_type,'text':text,'run_id':run_id or str(uuid.uuid4())}
                response = await request('POST','/brain/tasks',user=user,tenant=tenant,body=body)
                assert response.status_code == 200, response.text
                return response.json()

            async def rows(user=A, tenant=None):
                tenant = tenant or stack.tenant
                response = await request('GET', '/memory?' + urlencode({'tenant_id':tenant,'user_id':user}), user=user, tenant=tenant)
                assert response.status_code == 200, response.text
                return response.json()['memories']

            async def write(kind='incident', text='Owner observed failed deployment', user=A, tenant=None):
                tenant = tenant or stack.tenant
                response = await request('POST','/memory',user=user,tenant=tenant,
                    body={'tenant_id':tenant,'user_id':user,'kind':kind,'text':text,'evidence':['urn:autumbra:fixture:incident']})
                assert response.status_code == 200 and response.json()['saved'], response.text
                return response.json()

            box = SimpleNamespace(stack=stack,state=state,watch=watch,store=store,tank=tank,provider=provider,
                                  client=client,direct=direct,request=request,task=task,rows=rows,write=write,role=role)
            try:
                yield box
            finally:
                if tank._background:
                    import asyncio
                    await asyncio.gather(*list(tank._background))
                store.close()
                stack.records.pool = old_pool
                await restricted.close()
                async with old_pool.acquire() as conn:
                    await conn.execute(f'DROP OWNED BY "{role}"')
                    await conn.execute(f'DROP ROLE "{role}"')
    finally:
        if raw is not None:
            await raw.close()
        await admin.execute(f'DROP DATABASE "{dbname}" WITH (FORCE)')
        await admin.close()
