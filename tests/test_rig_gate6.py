"""Savings journeys through the real catalogue, room, and accounting contracts."""
import asyncio
import copy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/rig"))
from fastapi import FastAPI

from rigbox import inference, savings
from rigbox.inference import Models
from rigbox.service import Service, RigError
from rigbox.store import MemoryStore
from rigbox.token_reference import input_tokens, tokens
from test_rig import _loaded, TENANT, OTHER

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'tests/fixtures/rig_savings/recorded.json'


@pytest.fixture(autouse=True)
def explicitly_enable_new_code_cache_and_receipts(monkeypatch):
    monkeypatch.setenv('RIG_MEMORY_ENABLED', 'true')


@pytest.mark.asyncio
async def test_recorded_catalogue_calls_use_code_with_zero_model_tokens(monkeypatch):
    fixture = json.loads(FIXTURE.read_text())
    tank = SimpleNamespace(route=AsyncMock(side_effect=AssertionError('No model needed')))
    models = Models(tank)
    before = 0
    for row in fixture['cases']:
        result = json.loads(await models.structured(TENANT, row['task'], row['payload']))
        assert result == row['expected']
        assert json.loads(await models.structured(TENANT, row['task'], row['payload'])) == result
        before += input_tokens([{'role': 'user', 'content': row['before_prompt']}]) + tokens(row['before_response'])
    assert before == fixture['before_tokens'] > 0
    assert fixture['after_tokens'] == 0
    tank.route.assert_not_called()


@pytest.mark.asyncio
async def test_cache_is_tenant_content_and_time_scoped(monkeypatch):
    row = json.loads(FIXTURE.read_text())['cases'][0]
    clock = [0]; seen = []
    original = inference.code_result
    def code(task, payload):
        seen.append(task)
        return original(task, payload)
    monkeypatch.setattr(inference, 'code_result', code)
    model = Models(None, clock=lambda: clock[0])
    for tenant in (TENANT, TENANT, OTHER):
        await model.structured(tenant, row['task'], row['payload'])
    assert len(seen) == 2
    changed = copy.deepcopy(row['payload']); changed['products'][0]['name'] += ' changed'
    await model.structured(TENANT, row['task'], changed)
    assert len(seen) == 3
    clock[0] = 301
    await model.structured(TENANT, row['task'], row['payload'])
    assert len(seen) == 4
    for number in range(270):
        await model.structured(TENANT, row['task'], {**row['payload'], 'question': str(number)})
    assert len(model.cache) == 256


@pytest.mark.asyncio
async def test_actual_catalogue_journey_failure_empty_receipt_and_tenant_scope():
    service, store, _, _ = await _loaded()
    service.models = Models(None)
    assert await savings.view(service, OTHER) == {'receipts': []}
    result = await service.ask(TENANT, 'EXAMPLE-SCOPE-01', 'Which scope is listed?')
    assert result['answer'] != "I don't know" and result['cites'] == ['EXAMPLE-SCOPE-01']
    receipt = savings.latest.get()
    assert receipt['cost'] == '0' and receipt['tokens_in'] == receipt['tokens_out'] == 0
    assert receipt['reference_tokens_in'] > 0 and receipt['reference_tokens_out'] > 0
    with pytest.raises(RigError):
        await service.ask(TENANT, 'absent', 'price')
    rows = await savings.Receipts(store).rows(TENANT)
    assert len(rows) == 2 and {row['outcome'] for row in rows} == {'delivered', 'failed'}
    assert await savings.Receipts(store).rows(OTHER, identity=receipt['id']) == []
    assert 'question' not in json.dumps(rows) and 'scope?' not in json.dumps(rows)
    assert (await savings.view(service, TENANT))['receipts'][0]['would_have_cost'] is None


@pytest.mark.asyncio
async def test_outbox_retries_only_delivery_handles_unpriced_and_rejects_foreign_reply():
    service = Service(MemoryStore(), Models(None))
    await service.search(TENANT, 'placeholder', 12)
    receipt = savings.latest.get(); post = AsyncMock(side_effect=TimeoutError)
    service.models.tank = SimpleNamespace(_post=post)
    await savings.reconcile(service, TENANT)
    assert len(await savings.Receipts(service.store).rows(TENANT)) == 1
    def reply(body, **changes):
        return {**body, 'ledger_id': body['id'], 'would_have_cost': '0.001', 'baseline_model': 'sol',
                'baseline_status': 'bpe_reference', **changes}
    async def wrong(path, body): return reply(body, tenant_id=OTHER)
    post.side_effect = wrong
    await savings.reconcile(service, TENANT)
    assert (await savings.Receipts(service.store).rows(TENANT))[0]['accounting'] == 'pending'
    async def unpriced(path, body): return reply(body, would_have_cost=None, baseline_status='unpriced')
    post.side_effect = unpriced
    await savings.reconcile(service, TENANT)
    assert (await savings.Receipts(service.store).rows(TENANT))[0]['accounting'] == 'pending'
    async def priced(path, body): return reply(body)
    post.side_effect = priced
    await savings.reconcile(service, TENANT)
    row = (await savings.Receipts(service.store).rows(TENANT))[0]
    assert row['id'] == receipt['id'] and row['accounting'] == 'recorded' and row['would_have_cost'] == '0.001'
    assert post.await_count == 4
    assert all(call.args[1]['id'] == receipt['id'] for call in post.await_args_list)
    await savings.reconcile(service, TENANT)
    assert post.await_count == 4


@pytest.mark.asyncio
async def test_tank_receipt_view_keeps_provider_cost_and_no_duplicate_code_rows():
    service = Service(MemoryStore(), Models(None)); await service.search(TENANT, 'placeholder', 12)
    local = savings.latest.get(); external = {**local, 'id': str(uuid4()), 'cost': '0.166667', 'cost_status': 'upper_bound'}
    post = AsyncMock(return_value={'tenant_id': TENANT, 'receipts': [local, external]})
    service.models.tank = SimpleNamespace(_post=post)
    view = await savings.view(service, TENANT)
    assert len(view['receipts']) == 2 and any(row['cost_status'] == 'upper_bound' for row in view['receipts'])
    post.return_value['tenant_id'] = OTHER
    assert len((await savings.view(service, TENANT))['receipts']) == 1


@pytest.mark.asyncio
async def test_command_room_tools_auth_identity_admin_and_same_receipts(monkeypatch):
    from rigbox.api import mount
    service, store, _, _ = await _loaded(); service.models = Models(None)
    app = FastAPI(); app.state.rig = service; mount(app)
    monkeypatch.setenv('TANK_KEY', 'placeholder-room')
    monkeypatch.setenv('RIG_ROOM_TENANT', TENANT)
    body = {'tenant_id': TENANT, 'actor': 'placeholder-user', 'arguments': {'q': 'scope'}}
    url = '/v1/rig/internal/tools/search'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        assert (await client.post(url, json=body)).status_code == 401
        client.headers['X-Tank-Key'] = 'placeholder-room'
        assert (await client.post(url, json={**body, 'tenant_id': OTHER})).status_code == 403
        response = await client.post(url, json=body)
        assert response.status_code == 200, response.text
        result = response.json(); assert result['result']['results'] and result['receipt']['cost'] == '0'
        identity = result['receipt']['id']
        query = {**body, 'arguments': {'id': identity}}
        assert (await client.post('/v1/rig/internal/tools/receipt', json=query)).status_code == 403
        response = await client.post('/v1/rig/internal/tools/receipt', json={**query, 'administrator': True})
        assert response.json()['result']['receipts'][0]['id'] == identity
        assert (await client.post(url, json={**body, 'arguments': {'q': 'x', 'tenant_id': OTHER}})).status_code == 422
    assert len(await savings.Receipts(store).rows(TENANT)) == 1


def test_mcp_adapters_validate_all_main_actions_and_do_not_allow_identity(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder/placeholder')
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder')
    monkeypatch.setenv('TANK_API_KEY', 'placeholder')
    import command
    import mcp_server
    from command_tools.rig import MAIN, ADMIN
    from fastapi import HTTPException
    monkeypatch.setattr(command.command_repo, 'configured', lambda: True)
    actor = command.Actor(UUID(TENANT), 'placeholder-admin', False, frozenset({'rig'}), tenant_admin=True)
    member = command.Actor(UUID(TENANT), 'placeholder-member', False, frozenset({'rig'}))
    listed = {row['name']: row for row in mcp_server.tools(actor)['tools']}
    assert set(MAIN) <= listed.keys()
    assert listed['rig.search']['annotations']['readOnlyHint']
    # Preserve main's paid preflight; optional code/cache work must not remove it.
    assert command.ADAPTERS['rig.ask'].paid
    for name in MAIN:
        assert 'tenant_id' not in listed[name]['inputSchema']['properties']
        assert listed[name]['inputSchema']['additionalProperties'] is False
        assert command.ADAPTERS[name].path == '/v1/rig/tools/' + name[4:]
        with pytest.raises(HTTPException):
            command.validate_action(command.PlannedAction(tool=name, arguments={'tenant_id': OTHER}), actor)
    for name in ADMIN:
        with pytest.raises(HTTPException): command.require_tool(member, name)
    action = command.PlannedAction(tool='rig.search', arguments={'q': 'scope'})
    assert command.adapter_request(action, actor)[2] == {'q': 'scope', 'limit': 12}


def test_shared_registry_snapshot():
    import test_registry_frozen
    test_registry_frozen.test_registry_matches_frozen_origin_main()


def test_receipt_screen_offline_phone_and_desktop():
    import subprocess
    result = subprocess.run(['node', 'tests/rig_gate6_browser.mjs'], cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_window_command_tools_reach_real_room_actions_and_receipts(monkeypatch):
    for name in ('LITELLM_MASTER_KEY', 'TANK_API_KEY'):
        monkeypatch.setenv(name, 'placeholder')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder/placeholder')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room'); monkeypatch.setenv('RIG_ROOM_TENANT', TENANT)
    import command, main, rig_tools
    from rigbox.api import mount
    service, store, _, _ = await _loaded(); service.models = Models(None)
    room = FastAPI(); room.state.rig = service; mount(room)
    app = FastAPI()
    actor = command.Actor(UUID(TENANT), 'placeholder-admin', False, frozenset({'rig'}), tenant_admin=True)
    app.dependency_overrides[command.identity] = lambda: actor
    monkeypatch.setattr(command.command_repo, 'configured', lambda: True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room), base_url='http://room',
                                 headers={'X-Tank-Key': 'placeholder-room', 'Content-Type': 'application/json'}) as room_client:
        async def corridor(method, path, params, content, timeout):
            assert timeout == 35
            return await room_client.request(method, path, content=content, params=params)
        rt = SimpleNamespace(_rig_call=corridor, _rig_body=main._rig_body, _rig_response=main._rig_response, require_key=main.require_key)
        app.include_router(rig_tools.build_router(rt))
        monkeypatch.setattr(main, 'TANK_API_KEY', 'placeholder-workspace')
        monkeypatch.setattr(main, '_agent_keys_synced', True)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://tank', headers={'X-Tank-Key': 'placeholder-workspace'}) as client:
            setup = (await service.setups(TENANT, 'EXAMPLE-RIFLE-01'))['setups'][0]
            operations = [('search', {'q': 'scope'}), ('product', {'product_id': 'EXAMPLE-SCOPE-01'}),
                ('setups', {'product_id': 'EXAMPLE-RIFLE-01'}), ('graph', {'product_id': 'EXAMPLE-RIFLE-01'}),
                ('ask', {'product_id': 'EXAMPLE-SCOPE-01', 'question': 'Which scope is listed?'}),
                ('compare', {'product_ids': ['EXAMPLE-SCOPE-01']}),
                ('swap', {'setup': setup, 'role': setup['parts'][1]['role']}),
                ('quote', {'product_id': 'EXAMPLE-SCOPE-01', 'contact': {'name': 'Placeholder', 'email': 'placeholder@example.com'}}),
                ('suggest', {})]
            for operation, args in operations:
                adapter = command.ADAPTERS['rig.' + operation]
                response = await client.request(adapter.method, '/v1/rig/tools/' + operation,
                    **({'params': args} if adapter.method == 'GET' else {'json': args}))
                assert response.status_code == 200, (operation, response.text)
                receipt = response.json()['receipt']
                assert receipt['cost'] == '0' and receipt['id']
                assert 'unit_cost' not in response.text and 'tenant_id' not in response.text
            assert (await client.get('/v1/rig/tools/receipts')).json()['result']['receipts']
            response = await client.post('/v1/rig/tools/receipt', json={'id': receipt['id']})
            assert response.json()['result']['receipts'][0]['id'] == receipt['id']
            assert (await client.post('/v1/rig/tools/ask', json={'product_id': 'scope', 'question': 'x', 'tenant_id': OTHER})).status_code == 422


@pytest.mark.asyncio
async def test_cart_tools_share_checkout_state_and_never_repeat_an_order(monkeypatch):
    from test_rig_cart import setup, TENANT as tenant
    from rigbox.api import mount
    cart, platform, _, _, _, remote = await setup(monkeypatch)
    service = cart.service; service.cart = cart
    monkeypatch.setenv('TANK_KEY', 'placeholder-room'); monkeypatch.setenv('RIG_ROOM_TENANT', str(tenant))
    app = FastAPI(); app.state.rig = service; mount(app)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline', headers={'X-Tank-Key':'placeholder-room'}) as client:
            async def call(name, args):
                response = await client.post('/v1/rig/internal/tools/cart.' + name,
                    json={'tenant_id': str(tenant), 'actor': 'placeholder-user', 'arguments': args})
                assert response.status_code == 200, response.text
                assert response.json()['receipt']['cost'] == '0'
                return response.json()['result']
            token = (await call('session', {}))['session']
            await call('add', {'session': token, 'product_id': 'stock', 'quantity': 1})
            await call('view', {'session': token})
            first = await call('checkout', {'session': token})
            assert (await call('checkout', {'session': token}))['id'] == first['id']
            assert len(platform.orders) == 1
            await call('order', {'session': token, 'checkout_id': first['id']})
    finally:
        await remote.aclose()


@pytest.mark.asyncio
async def test_admin_receipt_costs_survive_shopper_price_guard():
    from rigbox.api import mount
    from rigbox.service import hash_key
    from test_rig import KEY
    service, store, _, _ = await _loaded(); service.models = Models(None)
    await store.put_key(TENANT, hash_key('placeholder-admin'), 'admin', [])
    await service.search(TENANT, 'scope', 12)
    identity = savings.latest.get()['id']
    app = FastAPI(); app.state.rig = service; mount(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        for path in ('/v1/rig/receipts', '/v1/rig/receipts/' + identity):
            assert (await client.get(path, headers={'X-Rig-Key': KEY})).status_code in (401,403)
            response = await client.get(path, headers={'X-Rig-Key': 'placeholder-admin'})
            assert response.status_code == 200, response.text
            row = response.json()['receipts'][0] if path.endswith('receipts') else response.json()
            assert row['cost'] == '0' and row['would_have_cost'] is None
            assert 'no-store' in response.headers['Cache-Control']


@pytest.mark.asyncio
async def test_nested_actions_share_a_receipt_but_background_tasks_get_their_own():
    service = Service(MemoryStore(), Models(None))
    async def foreground(tenant):
        await service.search(tenant, 'same action', 12)
        await asyncio.create_task(service.search(tenant, 'separate background action', 12))
        return {'ok': True}
    await savings.measured(service, 'rig.foreground', foreground)(TENANT)
    rows = await savings.Receipts(service.store).rows(TENANT)
    assert len(rows) == 2 and {row['action'] for row in rows} == {'rig.foreground', 'rig.search'}
