"""Workspace's real signed ingress; only issuer/provider network edges are faked."""
from __future__ import annotations

import importlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import asyncpg
import pytest_asyncio
from fastapi import FastAPI
import engine_models
import paid_steps

from tank_routing.litellm_probe import COMPLETIONS_PATH
from command_tools import workspace
from command_tools._workspace.memory_client import build_workspace_memory_client
from trigger_signin_fakes import native_provider
from trigger_signin_guard import TriggerSigninMiddleware

ROOT = Path(__file__).resolve().parents[3]
USER_A = 'placeholder-workspace-user-a'
USER_B = 'placeholder-workspace-user-b'
SERVICE_KEY = 'placeholder-workspace-service-key'


@pytest_asyncio.fixture
async def workspace_entry(gate78_memory, monkeypatch):
    stack = await gate78_memory('workspace')
    pool = stack.records.pool
    # Real deployed ledger, policy and Command authorization tables. No SQL fake.
    await pool.execute((ROOT / 'tank/schema.sql').read_text())
    main = importlib.import_module('main')
    # Command's real editing/authorization path nests independent acquisitions.
    # The shared memory fixture's one connection is not a serving-app pool.
    app_pool = await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'], min_size=1, max_size=6, statement_cache_size=0)
    monkeypatch.setattr(main, '_pool', app_pool)
    monkeypatch.setattr(main, 'TANK_API_KEY', SERVICE_KEY)
    monkeypatch.setattr(main, 'DATABASE_URL', os.environ['MEMORY_TEST_DATABASE_URL'])
    monkeypatch.setattr(main, 'LITELLM_MASTER_KEY', 'placeholder-litellm-master-key')
    monkeypatch.setenv('TANK_API_KEY', SERVICE_KEY)
    monkeypatch.setenv('WORKSPACE_MEMORY_ENABLED', 'true')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    provider = native_provider(monkeypatch, {'10001': stack.tenant, '10002': stack.other_tenant})
    # Product-owned infrastructure extension: real isolated Tank engine collection,
    # with the existing service-key and signed-personal-identity routes unchanged.
    from hermes.records import Records
    from hermes.record_schema import schema_sql
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    engine_schema = 'agent_wsengine_' + uuid4().hex[:12]
    await pool.execute(schema_sql('tank').replace('agent_tank', engine_schema))
    records = Records(pool, stack.records.index, stack.records.encoder, stack.records.model, ['workspace', 'tank'])
    records._schemas['workspace'] = stack.records.schema('workspace')
    records._schemas['tank'] = engine_schema
    engine_app = create_app(InMemoryStore(), records.encoder, records=records)
    monkeypatch.setattr(stack, 'records', records)
    monkeypatch.setattr(stack, 'app', engine_app)
    monkeypatch.setattr(stack.http, '_transport', httpx.ASGITransport(app=engine_app))
    memory = build_workspace_memory_client(http=stack.http, base_url='http://hermes')
    monkeypatch.setattr(main, 'memory', memory, raising=False)
    requests = []
    timeline = []
    fault = {'method': None, 'path': None, 'status': 503, 'hits': 0}
    originals = []

    async def observe(request):
        requests.append(request)
        timeline.append((request.method, request.url.path))
    stack.http.event_hooks['request'].append(observe)
    # An outage is injected at the HTTP boundary, never into memory/orchestration.
    transport = stack.http._transport
    class Boundary(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if fault['method'] == request.method and (fault['path'] is None or fault['path'] == request.url.path):
                fault['hits'] += 1
                return httpx.Response(fault['status'], json={'detail': 'placeholder unavailable'})
            return await transport.handle_async_request(request)
    monkeypatch.setattr(stack.http, '_transport', Boundary())
    calls = []
    statuses = []
    names = (*engine_models.OPEN, 'placeholder-gate78-model')
    async def provider_edge(request):
        assert request.url.host in {'litellm', 'placeholder-litellm'}
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'model_name': name,
                'litellm_params': {'model': 'placeholder/' + name},
                'model_info': {'input_cost_per_token': .001, 'output_cost_per_token': .001}}
                for name in names]})
        assert request.method == 'POST' and request.url.path == COMPLETIONS_PATH
        timeline.append(('PAID', request.url.path))
        calls.append(json.loads(request.content))
        return httpx.Response(200, headers={'x-litellm-response-cost': '0.013'}, json={'id': 'placeholder-completion', 'model': calls[-1]['model'],
            'choices': [{'message': {'content': 'placeholder completed answer'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}})
    http = httpx.AsyncClient(transport=httpx.MockTransport(provider_edge))
    monkeypatch.setattr(main, '_http', http)
    # Dispatch creates a fresh HTTP client. Fake that network edge too, keeping
    # explicitly mounted ASGI/issuer transports and the real routing code intact.
    actual_client = httpx.AsyncClient
    async def outbound(request):
        if request.url.host in {'litellm', 'placeholder-litellm'}:
            return await provider_edge(request)
        if request.url.host == 'hermes':
            return await stack.http.send(request)
        raise AssertionError('Unconfigured fixture network destination')
    def network_client(*args, **kwargs):
        kwargs.setdefault('transport', httpx.MockTransport(outbound))
        async def status(response):
            statuses.append((response.request.method, response.request.url.path, response.status_code))
        hooks = dict(kwargs.get('event_hooks') or {})
        hooks['response'] = [*hooks.get('response', []), status]
        kwargs['event_hooks'] = hooks
        return actual_client(*args, **kwargs)
    monkeypatch.setattr(main.httpx, 'AsyncClient', network_client)
    import engine_memory
    monkeypatch.setattr(engine_memory, 'HTTP', network_client)
    # This is a deliberately fake policy/model, never a real model selection.
    for tenant in (stack.tenant, stack.other_tenant):
        for task_type in ('tier0.answer', 'tier0.draft', 'reason.brief', 'command.turn'):
            await pool.execute("INSERT INTO tank.policy(task_type,tenant_id,model,priority,cache_scope) VALUES($1,$2,'placeholder-gate78-model','urgent','none')", task_type, UUID(tenant))
            for task in (task_type, task_type + '#engine-eval'):
                for name in names:
                    step = paid_steps.model_step(task, name)
                    await paid_steps.register(pool, step, paid_steps.product(task, 'tier0'), 'model', 'placeholder-gate78-policy', task=task, model=name)
                    await pool.execute("INSERT INTO tank.paid_step_settings(tenant_id,step_id,mode,updated_by) VALUES($1,$2,'auto',$3) ON CONFLICT(tenant_id,step_id) DO UPDATE SET mode='auto'", UUID(tenant), step, USER_A)
    # Counterfactual prices are explicit disposable fixtures, never production
    # model recommendations. The actual ladder/Auto authorization still runs.
    old_prices = await pool.fetch('SELECT * FROM tank.proof_prices WHERE model=ANY($1::text[])', list(names))
    old_standard = await pool.fetchrow("SELECT * FROM tank.provider_standards WHERE provider='placeholder'")
    for name in names:
        await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) "
            "VALUES($1,'placeholder',.001,.001) ON CONFLICT(model) DO UPDATE "
            "SET family='placeholder',input_usd=.001,output_usd=.001", name)
    await pool.execute("INSERT INTO tank.provider_standards(provider,model) "
        "VALUES('placeholder','placeholder-gate78-model') ON CONFLICT(provider) DO UPDATE SET model=EXCLUDED.model")
    monkeypatch.setattr(main, '_roster_cache', None)
    app = FastAPI()
    app.add_middleware(TriggerSigninMiddleware)
    import command
    app.include_router(command.router)
    app.include_router(workspace.build_router())
    app.add_middleware(paid_steps.ApprovalMiddleware)
    # In-process Command dispatch must re-enter this same mounted/authenticated app.
    monkeypatch.setattr(main, 'app', app)
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-workspace')
    def headers(user=USER_A, tenant=None):
        return {'X-Tank-Key': SERVICE_KEY, **provider.workspace_headers(user, tenant or stack.tenant)}
    async def request(path, body=None, *, user=USER_A, tenant=None, method=None, extra=None):
        method = method or ('GET' if path == 'memory.view' else 'POST')
        bound = {key.lower(): value for key, value in headers(user, tenant).items()}
        bound.update({key.lower(): value for key, value in (extra or {}).items()})
        return await client.request(method, '/v1/command/workspace/' + path,
            headers=bound,
            **({'params': body or {}} if method == 'GET' else {'json': body or {}}))
    async def snapshot():
        schema = stack.records.schema(stack.agent)
        rows = await pool.fetch(f'SELECT id,tenant_id,claim,kind,meta FROM {schema}.memory_records ORDER BY id')
        return [dict(row) for row in rows]
    async def seed(user=USER_A, tenant=None, text='placeholder original answer', kind='workspace.task', **meta):
        return await stack.client(user).remember(tenant or stack.tenant, text, kind,
            'urn:placeholder:workspace:fixture', meta={'task_key': 'placeholder-task', **meta})
    async def confirmed_task(body):
        signed = headers()
        thread = await client.post('/v1/command/threads', json={}, headers=signed)
        assert thread.status_code == 200, thread.text
        card = await client.post(f"/v1/command/threads/{thread.json()['thread_id']}/actions",
            json={'tool': 'workspace.task.create', 'arguments': body}, headers=signed)
        assert card.status_code == 200, card.text
        reply = await client.post(f"/v1/command/cards/{card.json()['card_id']}", json={'action': 'confirm'}, headers=signed)
        assert reply.status_code == 200, reply.text
        return reply
    async def restart():
        nonlocal app, client
        await client.aclose()
        # Recreate the serving application and adapter; SQL checkpoints and the
        # existing Hermes service survive, as they do across a Tank restart.
        importlib.reload(workspace)
        app = FastAPI()
        app.add_middleware(TriggerSigninMiddleware)
        app.include_router(command.router)
        app.include_router(workspace.build_router())
        app.add_middleware(paid_steps.ApprovalMiddleware)
        monkeypatch.setattr(main, 'app', app)
        client = actual_client(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-workspace')
    entry = SimpleNamespace(stack=stack, pool=pool, main=main, client=client, request=request,
        app=app, restart=restart, records=records, engine_schema=engine_schema, headers=headers, provider=provider, memory=memory, provider_calls=calls, requests=requests,
        fault=fault, snapshot=snapshot, seed=seed, originals=originals, timeline=timeline, confirmed_task=confirmed_task, statuses=statuses)
    try:
        yield entry
    finally:
        for task in tuple(main._background):
            await task
        for task in tuple(command._background):
            await task
        await client.aclose()
        await app_pool.close()
        await http.aclose()
        await pool.execute(f'DROP SCHEMA {engine_schema} CASCADE')
        await pool.execute('DELETE FROM tank.proof_prices WHERE model=ANY($1::text[])', list(names))
        for row in old_prices:
            await pool.execute('INSERT INTO tank.proof_prices SELECT * FROM jsonb_populate_record(NULL::tank.proof_prices,$1::jsonb)', json.dumps(dict(row), default=str))
        await pool.execute("DELETE FROM tank.provider_standards WHERE provider='placeholder'")
        if old_standard:
            await pool.execute('INSERT INTO tank.provider_standards SELECT * FROM jsonb_populate_record(NULL::tank.provider_standards,$1::jsonb)', json.dumps(dict(old_standard), default=str))
        await pool.execute('DELETE FROM tank.policy WHERE tenant_id=ANY($1::uuid[])', [UUID(stack.tenant), UUID(stack.other_tenant)])
