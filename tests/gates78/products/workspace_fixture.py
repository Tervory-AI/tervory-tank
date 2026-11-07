"""Workspace's real signed ingress; only issuer/provider network edges are faked."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest_asyncio
from fastapi import FastAPI

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
    monkeypatch.setattr(main, '_pool', pool)
    monkeypatch.setattr(main, 'TANK_API_KEY', SERVICE_KEY)
    monkeypatch.setenv('TANK_API_KEY', SERVICE_KEY)
    monkeypatch.setenv('WORKSPACE_MEMORY_ENABLED', 'true')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    provider = native_provider(monkeypatch, {'10001': stack.tenant, '10002': stack.other_tenant})
    memory = build_workspace_memory_client(http=stack.http, base_url='http://hermes')
    monkeypatch.setattr(main, 'memory', memory, raising=False)
    requests = []
    fault = {'method': None, 'status': 503}
    originals = []

    async def observe(request):
        requests.append(request)
    stack.http.event_hooks['request'].append(observe)
    # An outage is injected at the HTTP boundary, never into memory/orchestration.
    transport = stack.http._transport
    class Boundary(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            if fault['method'] == request.method:
                return httpx.Response(fault['status'], json={'detail': 'placeholder unavailable'})
            return await transport.handle_async_request(request)
    monkeypatch.setattr(stack.http, '_transport', Boundary())
    calls = []
    async def provider_edge(request):
        assert request.url.host in {'litellm', 'placeholder-litellm'}
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'model_name': 'placeholder-gate78-model',
                'litellm_params': {'model': 'placeholder/provider'},
                'model_info': {'input_cost_per_token': .001, 'output_cost_per_token': .001}}]})
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={'id': 'placeholder-completion', 'model': 'placeholder-gate78-model',
            'choices': [{'message': {'content': 'placeholder completed answer'}}],
            'usage': {'prompt_tokens': 10, 'completion_tokens': 3, 'total_tokens': 13}})
    http = httpx.AsyncClient(transport=httpx.MockTransport(provider_edge))
    monkeypatch.setattr(main, '_http', http)
    # This is a deliberately fake policy/model, never a real model selection.
    for tenant in (stack.tenant, stack.other_tenant):
        for task_type in ('tier0.answer', 'tier0.draft', 'reason.brief'):
            await pool.execute("INSERT INTO tank.policy(task_type,tenant_id,model,priority,cache_scope) VALUES($1,$2,'placeholder-gate78-model','urgent','none')", task_type, UUID(tenant))
    monkeypatch.setattr(main, '_roster_cache', None)
    app = FastAPI()
    app.add_middleware(TriggerSigninMiddleware)
    app.include_router(workspace.build_router())
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
    entry = SimpleNamespace(stack=stack, pool=pool, main=main, client=client, request=request,
        headers=headers, provider=provider, memory=memory, provider_calls=calls, requests=requests,
        fault=fault, snapshot=snapshot, seed=seed, originals=originals)
    try:
        yield entry
    finally:
        for task in tuple(main._background):
            await task
        await client.aclose()
        await http.aclose()
        await pool.execute('DELETE FROM tank.policy WHERE tenant_id=ANY($1::uuid[])', [UUID(stack.tenant), UUID(stack.other_tenant)])
