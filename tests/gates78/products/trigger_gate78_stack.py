"""Trigger-only network wiring; production auth, orchestration, SQL and receipts."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import asyncpg
import httpx
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[3]
USER_A = 'placeholder-user-a'
USER_B = 'placeholder-user-b'
COST = .0024
TOKENS = (80, 20)


class TriggerNetwork(httpx.AsyncBaseTransport):
    def __init__(self, stack, room, tank):
        self.stack, self.room, self.tank = stack, room, tank
        self.calls, self.providers, self.forwarded, self.tank_answers = [], [], [], []
        self.failure = None
        self.body_status = 503

    async def handle_async_request(self, request):
        host, path = request.url.host, request.url.path
        self.calls.append((host, request.method, path))
        if host in {'hermes', 'placeholder-hermes'}:
            if self.failure == (request.method, path):
                return httpx.Response(self.body_status, json={'detail': 'placeholder unavailable'})
            return await self.stack.http.send(request)
        if host == 'agent-trigger':
            self.forwarded.append(request)
            return await httpx.ASGITransport(app=self.room).handle_async_request(request)
        if host == 'tank':
            answer = await httpx.ASGITransport(app=self.tank).handle_async_request(request)
            await answer.aread()
            self.tank_answers.append((answer.status_code, answer.json()))
            return answer
        if host == 'placeholder-gateway':
            if path == '/model/info':
                from engine_models import OPEN
                return httpx.Response(200, json={'data': [{'model_name': name,
                    'litellm_params': {'model': 'openai/placeholder-fixture'}, 'model_info': {
                        'input_cost_per_token': .00002, 'output_cost_per_token': .00004}}
                    for name in (*OPEN, 'placeholder-fixture')]})
            if path == '/router/settings':
                return httpx.Response(200, json={'current_values': {'fallbacks': []}})
            assert request.method == 'POST' and path == '/v1/chat/completions'
            self.providers.append(json.loads(request.content))
            return httpx.Response(200, headers={'x-litellm-response-cost': str(COST)}, json={
                'choices': [{'message': {'content': 'A placeholder reliable product.'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': TOKENS[0], 'completion_tokens': TOKENS[1]}})
        if host in {'trigger-languagetool', 'placeholder-language'}:
            return httpx.Response(200, json={'matches': []})
        raise AssertionError('Unexpected network destination: ' + host + path)


@pytest_asyncio.fixture
async def trigger_stack(gate78_memory, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['MEMORY_TEST_DATABASE_URL'])
    from chassis.memory import MemoryClient
    from chassis.tank import TankClient
    from trigger import app as product
    import main as tank
    import identity_oidc as oidc
    import trigger_routes
    from trigger_signin_fakes import native_provider, set_founders

    stack = await gate78_memory('trigger')
    pool = await asyncpg.create_pool(os.environ['MEMORY_TEST_DATABASE_URL'], min_size=1, max_size=8)
    await pool.execute((ROOT / 'tank/schema.sql').read_text())
    await pool.execute('CREATE SCHEMA IF NOT EXISTS agent_trigger')
    await pool.execute((ROOT / 'agents/trigger/schema.sql').read_text())
    stack.records.pool = pool
    monkeypatch.setenv('TANK_KEY', stack.key)
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder-provider-key')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('TRIGGER_MEMORY_ENABLED', '1')
    monkeypatch.delenv('TRIGGER_BRAIN_ENABLED', raising=False)
    monkeypatch.setattr(tank, 'TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setattr(tank, 'LITELLM_URL', 'http://placeholder-gateway')
    monkeypatch.setattr(tank, 'LITELLM_MASTER_KEY', 'placeholder-provider-key')
    monkeypatch.setattr(tank, '_pool', pool)
    monkeypatch.setattr(tank, '_redis', None)
    monkeypatch.setattr(tank, '_roster_cache', None)
    monkeypatch.setattr(tank, '_agent_keys_synced', True)
    monkeypatch.setattr(product.app.state, 'pool', pool, raising=False)
    monkeypatch.setattr(product.app.state, 'missing_settings', [], raising=False)
    monkeypatch.setattr(product.app.state, 'product_nonce_stores', {}, raising=False)
    provider = native_provider(monkeypatch, {'10001': stack.tenant, '10002': stack.other_tenant})
    set_founders(monkeypatch, USER_A + ',' + USER_B)
    spec = importlib.util.spec_from_file_location('zenas_scope', ROOT / 'agents/zenas/core/scope_rules.py')
    scope = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scope)
    monkeypatch.setitem(__import__('sys').modules, 'zenas_scope', scope)
    net = TriggerNetwork(stack, product.app, tank.app)
    original_client = httpx.AsyncClient
    def client(**kwargs):
        kwargs.setdefault('transport', net)
        return original_client(**kwargs)
    # Replace transports only, leaving Tank's selected policy and ledger path real.
    network_http = SimpleNamespace(**{name: getattr(httpx, name) for name in dir(httpx) if not name.startswith('_')})
    network_http.AsyncClient = client
    monkeypatch.setattr(tank, 'httpx', network_http)
    monkeypatch.setattr(trigger_routes, 'httpx', network_http)
    shared_http = client()
    monkeypatch.setattr(tank, '_http', shared_http)
    monkeypatch.setattr(product.app.state, 'http', shared_http, raising=False)
    monkeypatch.setattr(product.app.state, 'tank', TankClient('http://tank', stack.key, 'trigger', shared_http), raising=False)
    monkeypatch.setattr(product.app.state, 'memory', MemoryClient('http://hermes', stack.key, 'trigger', shared_http), raising=False)
    from paid_steps_fixtures import configure_paid_auto
    configure_paid_auto(monkeypatch, lambda: pool)
    for tenant in (stack.tenant, stack.other_tenant):
        await pool.execute("""INSERT INTO tank.policy SELECT (jsonb_populate_record(NULL::tank.policy,
            to_jsonb(p)||jsonb_build_object('tenant_id',$1::uuid,'model','placeholder-fixture',
            'rung',1,'cache_scope','none','semantic_cache',false,'candidate_model',null,'shadow_rate',0))).*
            FROM tank.policy p WHERE task_type='trigger.write' AND tenant_id IS NULL""", UUID(tenant))
    async with original_client(transport=httpx.ASGITransport(app=tank.app), base_url='http://tank') as front:
        result = SimpleNamespace(stack=stack, pool=pool, room=product, tank=tank, front=front, net=net,
                                 provider=provider, http=shared_http, key=stack.key,
                                 tenant=stack.tenant, other=stack.other_tenant)
        try:
            yield result
        finally:
            if __import__('command')._background:
                await __import__('asyncio').gather(*tuple(__import__('command')._background))
            await shared_http.aclose()
            oidc._cache.clear()
            await pool.close()


def headers(b, user=USER_A, tenant=None):
    return b.provider.workspace_headers(user, UUID(tenant or b.tenant), 'org_admin') | {
        'X-Tank-Key': 'placeholder-workspace-key'}


async def actor(b, user=USER_A, tenant=None):
    """Verify a local issuer JWT using production ingress AND verifier, never body IDs."""
    import command
    import identity_oidc as oidc
    h = headers(b, user, tenant)
    response = await b.front.get('/v1/command/tools', headers=h)
    assert response.status_code == 200, response.text
    claims = await oidc.verify(h['x-trigger-signin-token'], workspace=True)
    owner, subject, admin = oidc.principal(claims, org_id=h['x-trigger-signin-org'], workspace=True)
    from starlette.requests import Request
    verified = {'X-Tank-Key': 'placeholder-workspace-key', 'X-Tervory-Tenant': str(owner),
                'X-Tervory-User': subject, 'X-Tervory-Role': 'org:admin' if admin else ''}
    request = Request({'type': 'http', 'headers': [(key.lower().encode(), value.encode()) for key, value in verified.items()]})
    return await command.identity(request)


async def control(b, operation='records', *, user=USER_A, tenant=None, body=None, **changes):
    """The actual signed product controls; reuse Tank's signing HTTP client."""
    import paid_http
    import product_identity
    who = await actor(b, user, tenant)
    path = '/memory/' + operation
    async with paid_http.Client(transport=b.net, base_url='http://agent-trigger:8000', headers={'X-Tank-Key': b.key}) as http:
        with product_identity.actor_scope(who):
            if operation == 'records':
                return await http.get(path, params={'tenant_id': tenant or b.tenant, **changes})
            return await http.post(path, json={'tenant_id': tenant or b.tenant, **(body or {}), **changes})


async def write(b, text='Describe the placeholder product.', *, user=USER_A, tenant=None, retry=None, allow_failure=False):
    """Real Command confirmation -> shipped Tank room adapter -> POST /write."""
    import command
    who = await actor(b, user, tenant)
    h = headers(b, user, tenant)
    if retry:
        response = await b.front.post('/v1/command/cards/' + retry, json={'action': 'confirm'}, headers=h)
        return response.json()
    response = await b.front.post('/v1/command/threads', json={'title': 'placeholder acceptance'}, headers=h)
    assert response.status_code == 200, response.text
    thread = UUID(response.json()['thread_id'])
    async with command.editing(thread, who) as (conn, row, state):
        action = command.validate_action(command.PlannedAction(tool='trigger.write', arguments={'text': text}), who)
        card = await command.propose_action(conn, row, state, action, who)
    response = await b.front.post('/v1/command/cards/' + card['card_id'], json={'action': 'confirm'}, headers=h)
    assert response.status_code == 200, response.text
    data = response.json()
    if not allow_failure:
        assert data['status'] == 'confirmed', (data, b.net.calls, b.net.providers, b.net.tank_answers)
    return data


async def rows(b):
    table = b.stack.records.schema('trigger')
    from hermes.records import public_row
    return [public_row(row) for row in await b.pool.fetch('SELECT * FROM ' + table + '.memory_records ORDER BY id')]


async def signed_request(b, method, path, *, user=USER_A, tenant=None, body=None, overrides=None):
    import product_identity
    who = await actor(b, user, tenant)
    raw = json.dumps(body, sort_keys=True, separators=(',', ':')).encode() if body is not None else b''
    args = dict(product='trigger', user=product_identity.user_from_actor(who), method=method,
                target=path, body=raw, key=b.key)
    args.update(overrides or {})
    token = product_identity.sign(**args)
    request = b.http.build_request(method, 'http://agent-trigger:8000' + path, content=raw,
        headers={'X-Tank-Key': b.key, product_identity.HEADER: token, 'Content-Type': 'application/json'})
    return request
