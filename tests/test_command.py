"""Command contract tests; Postgres integration also runs in the existing CI service."""
import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

import command

TENANT = uuid.UUID('00000000-0000-0000-0000-000000000011')
OTHER = uuid.UUID('00000000-0000-0000-0000-000000000012')


def request(**headers):
    return Request({'type': 'http', 'method': 'GET', 'path': '/', 'query_string': b'',
                    'headers': [(k.encode(), v.encode()) for k, v in headers.items()]})


@pytest.fixture
def runtime(monkeypatch):
    runtime = SimpleNamespace(TANK_API_KEY='dummy-workspace-key', box_region=lambda: 'us-east')
    monkeypatch.setitem(sys.modules, 'main', runtime)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    monkeypatch.setenv('TANK_KEY_WORKERS', 'dummy-worker-key')
    return runtime


@pytest.mark.asyncio
async def test_identity_roles_and_region(runtime):
    headers = {'x-tank-key': runtime.TANK_API_KEY, 'x-tervory-tenant': str(TENANT),
               'x-tervory-user': 'client', 'x-tervory-squad': 'tiger'}
    actor = await command.identity(request(**headers))
    assert command.allowed_tools(actor) == ['tiger.read', 'tiger.watch']
    with pytest.raises(HTTPException) as refused:
        command.require_tool(actor, 'worker.build')
    assert refused.value.status_code == 403
    headers['x-tervory-user'] = 'founder'
    founder = await command.identity(request(**headers))
    assert 'worker.build' in command.allowed_tools(founder)
    assert 'zenas.review' in command.allowed_tools(founder)
    headers['x-tervory-home-region'] = 'za'
    with pytest.raises(HTTPException) as refused:
        await command.identity(request(**headers))
    assert refused.value.status_code == 403
    headers['x-tank-key'] = 'dummy-worker-key'
    with pytest.raises(HTTPException) as refused:
        await command.identity(request(**headers))
    assert refused.value.status_code == 401


@pytest.mark.asyncio
async def test_worker_key_is_separate(runtime):
    with pytest.raises(HTTPException):
        await command.worker(request(**{'x-tank-key': runtime.TANK_API_KEY}))
    await command.worker(request(**{'x-tank-key': 'dummy-worker-key'}))


def test_receipts_never_invent_baseline():
    row = {'id': uuid.uuid4(), 'model': 'fixture-model', 'tokens_in': 10, 'tokens_out': 20, 'cost_usd': 0.02}
    receipt = command.receipt_row(row, 'step')
    assert receipt['baseline_status'] == 'baseline pending'
    assert receipt['saved_usd'] is None
    assert command.totals([receipt]) == {'cost_usd': 0.02, 'baseline_cost_usd': None, 'saved_usd': None}
    row.update(baseline_model='fixture-baseline', baseline_cost_usd=0.01)
    receipt = command.receipt_row(row, 'step')
    assert receipt['saved_usd'] == -0.01  # A loss must not be hidden.
    assert receipt['ledger_id'] == str(row['id'])
    assert command.totals([receipt])['baseline_cost_usd'] == 0.01


@pytest.mark.asyncio
async def test_auto_turn_uses_existing_router(runtime):
    runtime.Message = lambda **kw: kw
    runtime.RouteRequest = lambda **kw: SimpleNamespace(**kw)
    runtime.run_route = AsyncMock(return_value='answer')
    actor = command.Actor(TENANT, 'client', False)
    messages = [{'role': 'user', 'content': 'Hello'}]
    assert await command.route_turn(actor, messages) == 'answer'
    req = runtime.run_route.call_args.args[0]
    assert req.task_type == 'command.turn'
    assert req.tenant_id == TENANT
    assert req.home_region == 'us-east'
    assert req.messages == messages
    assert not hasattr(req, 'model')
    runtime.run_route.side_effect = HTTPException(503, 'paid work is paused')
    with pytest.raises(HTTPException) as error:
        await command.route_turn(actor, messages)
    assert error.value.status_code == 503


@pytest.mark.asyncio
async def test_pin_fails_explicitly_before_any_write(runtime):
    runtime.list_models = AsyncMock(return_value=[{'name': 'fixture-model'}])
    actor = command.Actor(TENANT, 'client', False)
    for name, status in [('missing', 422), ('fixture-model', 409)]:
        with pytest.raises(HTTPException) as error:
            await command.turn(uuid.uuid4(), command.Turn(text='Hi', model=name), actor)
        assert error.value.status_code == status


@pytest_asyncio.fixture
async def api(runtime, monkeypatch):
    url = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('POOL_SCHEMA_DATABASE_URL is not set; CI provides isolated Postgres')
    admin = await asyncpg.connect(url)
    name = 'command_test_' + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    from urllib.parse import urlsplit, urlunsplit
    parsed = urlsplit(url)
    target = urlunsplit((parsed.scheme, parsed.netloc, '/' + name, parsed.query, ''))
    pool = await asyncpg.create_pool(target, min_size=1, max_size=5)
    try:
        schema = Path('tank/schema.sql').read_text()
        async with pool.acquire() as conn:
            await conn.execute(schema)
            await conn.execute(schema)  # Empty database and idempotent reapplication.
        monkeypatch.setattr(command, 'db', lambda: pool)
        app = FastAPI()
        app.include_router(command.router)
        headers = {'x-tank-key': runtime.TANK_API_KEY, 'x-tervory-tenant': str(TENANT), 'x-tervory-user': 'founder'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture', headers=headers) as client:
            yield client, pool
    finally:
        if command._background:
            import asyncio
            await asyncio.gather(*command._background)
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


@pytest.mark.asyncio
async def test_persistence_search_ownership_and_replay(api):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={'title': 'Build the window'})).json()['thread_id']
    assert (await client.patch(f'/v1/command/threads/{thread}', json={'title': 'New title'})).status_code == 200
    assert len((await client.get('/v1/command/threads?q=New')).json()) == 1
    assert (await client.get('/v1/command/threads?q=absent')).json() == []
    for headers in [{'x-tervory-user': 'someone-else'}, {'x-tervory-tenant': str(OTHER)}]:
        assert (await client.get(f'/v1/command/threads/{thread}', headers=headers)).status_code == 404
        assert (await client.patch(f'/v1/command/threads/{thread}', json={'title': 'stolen'}, headers=headers)).status_code == 404
        assert (await client.get(f'/v1/command/threads/{thread}/events', headers=headers)).status_code == 404
        assert (await client.get('/v1/command/threads', headers=headers)).json() == []
    card = (await client.post('/v1/command/build', json={'thread_id': thread, 'brief_markdown': 'Make it work'})).json()
    event = await client.get(f'/v1/command/threads/{thread}/events')
    assert 'event: card' in event.text
    assert '"seq": 1' in event.text
    assert (await client.get(f'/v1/command/threads/{thread}/events?after=2')).text == ''
    assert (await client.get(f'/v1/command/threads/{thread}')).json()['cards'][0]['card_id'] == card['card_id']


@pytest.mark.asyncio
async def test_confirm_cancel_worker_progress_followups(api):
    import asyncio
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    body = {'thread_id': thread, 'brief_markdown': 'Build from this brief, no issue'}
    assert (await client.post('/v1/command/build', json=body, headers={'x-tervory-user': 'client'})).status_code == 403
    card = (await client.post('/v1/command/build', json=body)).json()
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_builds') == 0
    route = f"/v1/command/cards/{card['card_id']}"
    assert (await client.post(route, json={'action': 'confirm'}, headers={'x-tervory-user': 'client'})).status_code == 404
    replies = await asyncio.gather(*[client.post(route, json={'action': 'confirm'}) for _ in range(2)])
    assert all(r.status_code == 200 for r in replies)
    build_id = replies[0].json()['build_id']
    assert replies[1].json()['build_id'] == build_id
    assert (await client.post(route, json={'action': 'cancel'})).status_code == 409
    workers = {'x-tank-key': 'dummy-worker-key'}
    assert (await client.get('/v1/command/builds/next')).status_code == 401
    claims = await asyncio.gather(*[client.get('/v1/command/builds/next', headers=workers) for _ in range(2)])
    assert sum(r.json() is not None for r in claims) == 1
    progress = {'status': 'awaiting_review', 'step_label': 'PR opened', 'pr_url': 'https://github.com/Tervory-AI/tervory-tank/pull/123', 'ci_status': 'passed', 'review_status': 'pending'}
    assert (await client.post(f'/v1/command/builds/{build_id}/progress', headers=workers, json=progress)).status_code == 200
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    build_step = next(s for s in data['steps'] if s['step_id'] == build_id)
    assert build_step['link'] == progress['pr_url']
    assert build_step['ci_status'] == 'passed'
    follow = (await client.post(f'/v1/command/builds/{build_id}/followups', json={'followup_text': 'Fix X on the same PR'})).json()
    replay = await client.get(f'/v1/command/builds/{build_id}/followups', headers=workers)
    assert replay.json() == [{'followup_id': follow['followup_id'], 'followup_text': 'Fix X on the same PR'}]
    assert (await client.get(f"/v1/command/builds/{build_id}/followups?after={follow['followup_id']}", headers=workers)).json() == []
    # A cancelled proposal creates no additional build.
    card = (await client.post('/v1/command/build', json=body)).json()
    assert (await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'cancel'})).status_code == 200
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_builds') == 1


@pytest.mark.asyncio
async def test_auto_stream_matches_ledger_and_recovers_errors(api, monkeypatch):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    ledger_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd) VALUES($1,$2,'orchestrator','command.turn','fixture-model',10,20,0.02)", ledger_id, TENANT)
    route = AsyncMock(return_value=SimpleNamespace(ledger_id=ledger_id, content='A measured answer'))
    monkeypatch.setattr(command, 'route_turn', route)
    response = await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Hi', 'attachments': [{'name': 'notes.txt', 'text': 'Local notes'}]})
    assert response.status_code == 200
    items = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith('data: ')]
    assert [r['seq'] for r in items] == list(range(1, len(items) + 1))
    receipt = next(item for item in items if 'rows' in item)
    assert receipt['rows'][0]['ledger_id'] == str(ledger_id)
    assert receipt['totals']['cost_usd'] == 0.02
    assert receipt['totals']['saved_usd'] is None
    assert route.call_args.args[1][-1]['content'] == 'Hi\nAttachment notes.txt:\nLocal notes'
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert data['messages'][-1]['content'] == 'A measured answer'
    assert (await client.get('/v1/command/threads?q=Local')).json()[0]['spent_usd'] == 0.02
    route.side_effect = RuntimeError('private upstream detail must never escape')
    failed = await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Again'})
    assert 'event: error' in failed.text
    assert 'private upstream detail' not in failed.text
    async with pool.acquire() as conn:
        state = json.loads(await conn.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1', uuid.UUID(thread)))
    assert state['active_turn'] is None


@pytest.mark.asyncio
async def test_interrupted_turn_is_not_retried_and_new_turn_can_start(api, monkeypatch):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.command_threads SET state=state || $2::jsonb WHERE thread_id=$1",
                           uuid.UUID(thread), json.dumps({'active_turn': 'interrupted', 'active_started_at': '2000-01-01T00:00:00+00:00'}))
    route = AsyncMock(side_effect=HTTPException(503, 'paused'))
    monkeypatch.setattr(command, 'route_turn', route)
    reply = await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'New request'})
    assert reply.status_code == 200
    assert 'previous answer was interrupted' in reply.text
    route.assert_awaited_once()  # Only the new request, never the stale request.


@pytest.mark.asyncio
async def test_failed_paid_turn_keeps_ledger_receipt(api, monkeypatch):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    ledger_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd,outcome) VALUES($1,$2,'orchestrator','command.turn','fixture-model',0.01,'failed')", ledger_id, TENANT)
    error = HTTPException(502, {'ledger_id': str(ledger_id), 'upstream': 'private upstream text'})
    monkeypatch.setattr(command, 'route_turn', AsyncMock(side_effect=error))
    reply = await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Hello'})
    assert 'event: error' in reply.text
    assert 'event: receipt' in reply.text
    assert str(ledger_id) in reply.text
    assert 'private upstream text' not in reply.text
    detail = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert detail['thread']['spent_usd'] == 0.01


@pytest.mark.asyncio
async def test_revoked_founder_cannot_send_implicit_worker_followup(api, monkeypatch):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    card = (await client.post('/v1/command/build', json={'thread_id': thread, 'brief_markdown': 'Build'})).json()
    await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'confirm'})
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', '')
    monkeypatch.setattr(command, 'route_turn', AsyncMock(side_effect=HTTPException(503, 'paused')))
    await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Change the build'})
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_followups') == 0


def test_plans_are_bounded_and_cannot_supply_authority(runtime):
    founder = command.Actor(TENANT, 'founder', True)
    client = command.Actor(TENANT, 'client', False, frozenset({'tiger'}))
    valid = {'text': 'Review this proposal.', 'actions': [{'tool': 'skala.approve', 'arguments': {'skill_id': 'base.find_site', 'version': '1.0.0'}}]}
    assert len(command.parse_plan(json.dumps(valid), founder).actions) == 1
    assert not command.parse_plan('Plain answer', client).actions
    with pytest.raises(HTTPException):
        command.parse_plan(json.dumps(valid), client)
    for args in [{'skill_id': '../main', 'version': '1.0.0'},
                 {'skill_id': 'base.find_site', 'version': '1.0.0', 'by': 'someone-else'},
                 {'skill_id': 'base.find_site', 'version': '1.0.0', 'tenant_id': str(OTHER)},
                 {'skill_id': 'base.find_site', 'version': '1.0.0', 'confirmed': True}]:
        with pytest.raises(HTTPException):
            command.validate_action(command.PlannedAction(tool='skala.approve', arguments=args), founder)
    with pytest.raises(ValueError):
        command.parse_plan(json.dumps({**valid, 'actions': valid['actions'] * 5}), founder)
    with pytest.raises(ValueError):
        command.parse_plan('x' * (command.MAX_PLAN_BYTES + 1), founder)
    with pytest.raises(HTTPException):
        command.validate_action(command.PlannedAction(tool='repo.read'), founder)
    prompt = command.planning_message(client)['content']
    assert 'tiger.watch' in prompt and 'skala.approve' not in prompt


def test_adapters_force_identity_and_do_not_accept_paid_route_overrides(runtime):
    actor = command.Actor(TENANT, 'founder', True)
    action = command.PlannedAction(tool='market_lab.research', arguments={'question': 'A question'})
    method, path, query, body = command.adapter_request(action, actor)
    assert (method, path) == ('POST', '/v1/research')
    assert body == {'question': 'A question', 'tenant_id': str(TENANT), 'home_region': 'us-east'}
    assert query['tenant_id'] == str(TENANT)
    for overrides in [{'preset': 'high'}, {'model': 'expensive'}, {'home_region': 'za'}, {'tenant_id': str(OTHER)}]:
        with pytest.raises(HTTPException):
            command.validate_action(command.PlannedAction(tool='market_lab.research', arguments={'question': 'Q', **overrides}), actor)
    method, path, query, body = command.adapter_request(command.PlannedAction(tool='skala.approve', arguments={'skill_id': 'base.find_site', 'version': '1.0.0'}), actor)
    assert path == '/v1/skala/base.find_site/1.0.0/approve'
    assert body == {'by': 'founder'}
    assert all(a.path.startswith('/v1/') for a in command.ADAPTERS.values())


def test_receipt_ids_are_explicit_and_unknown_cost_is_not_zero():
    one, two = uuid.uuid4(), uuid.uuid4()
    assert command.explicit_ledger_ids({'ledger_id': str(one), 'receipt': {'ledger_ids': {'model': str(one), 'search': str(two)}}}) == [one, two]
    assert command.explicit_ledger_ids({'records': [{'ledger_id': str(one)}], '_cost_usd': 123}) == []
    unknown = command.receipt_row({'id': one, 'model': 'fixture', 'tokens_in': 0, 'tokens_out': 0,
                                   'cost_usd': 0, 'research_cost_status': 'unknown'}, 'step')
    assert unknown['cost_usd'] is None
    assert command.totals([unknown])['cost_usd'] is None


async def seed_ledger(pool, tenant=TENANT, cost=0.02):
    ledger_id = uuid.uuid4()
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd) VALUES($1,$2,'orchestrator','command.turn','fixture-model',10,20,$3)", ledger_id, tenant, cost)
    return ledger_id


async def planned_turn(client, pool, monkeypatch, actions):
    ledger_id = await seed_ledger(pool)
    turn = AsyncMock(return_value=SimpleNamespace(ledger_id=ledger_id, content=json.dumps({'text': 'Please confirm the proposed actions.', 'actions': actions})))
    monkeypatch.setattr(command, 'route_turn', turn)
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    reply = await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Do this work'})
    assert reply.status_code == 200
    turn.assert_awaited_once()
    return thread, (await client.get(f'/v1/command/threads/{thread}')).json()


@pytest.mark.asyncio
async def test_plan_only_proposes_then_native_tank_route_runs_once(api, runtime, monkeypatch):
    import asyncio
    client, pool = api
    app = client._transport.app
    runtime.app = app
    calls = []

    @app.post('/v1/skala/{skill_id}/{version}/approve')
    async def existing_approval(skill_id: str, version: str, request: Request):
        assert request.headers['x-tank-key'] == runtime.TANK_API_KEY
        assert request.headers['x-tervory-admin'] == 'founder'
        calls.append((skill_id, version, await request.json()))
        await asyncio.sleep(0.05)
        return {'ok': True}

    thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.approve', 'arguments': {'skill_id': 'base.find_site', 'version': '1.0.0'}}])
    assert calls == []
    card = data['cards'][0]
    assert card['kind'] == 'approve_skill' and card['status'] == 'pending'
    route = f"/v1/command/cards/{card['card_id']}"
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', '')
    assert (await client.post(route, json={'action': 'confirm'})).status_code == 403
    assert calls == []
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    replies = await asyncio.gather(client.post(route, json={'action': 'confirm'}), client.post(route, json={'action': 'confirm'}))
    assert all(r.status_code == 200 for r in replies)
    assert calls == [('base.find_site', '1.0.0', {'by': 'founder'})]
    assert (await client.post(route, json={'action': 'confirm'})).json()['status'] == 'confirmed'
    assert len(calls) == 1
    assert (await client.post(route, json={'action': 'cancel'})).status_code == 409
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert data['cards'][0]['receipt_status'] == 'pending'
    receipt_events = (await client.get(f'/v1/command/threads/{thread}/events')).text
    assert '"cost_usd": null' in receipt_events  # no invented zero-cost approval receipt


@pytest.mark.asyncio
async def test_paid_cancel_has_no_side_effect_and_failed_preflight_can_recover(api, monkeypatch):
    import controls
    client, pool = api
    dispatch = AsyncMock(return_value=(200, {'ok': True}))
    pause = AsyncMock(side_effect=HTTPException(503, 'paused'))
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    monkeypatch.setattr(controls, 'refuse_paid', pause)
    thread, data = await planned_turn(client, pool, monkeypatch, [
        {'tool': 'rig.ask', 'arguments': {'product_id': 'fixture', 'question': 'Will it fit?'}},
        {'tool': 'rig.ask', 'arguments': {'product_id': 'other', 'question': 'Will it fit?'}},
    ])
    first, second = data['cards']
    await client.post(f"/v1/command/cards/{first['card_id']}", json={'action': 'cancel'})
    pause.assert_not_awaited()
    dispatch.assert_not_awaited()
    route = f"/v1/command/cards/{second['card_id']}"
    failed = (await client.post(route, json={'action': 'confirm'})).json()
    assert failed['status'] == 'failed' and failed['retry_safe']
    dispatch.assert_not_awaited()
    pause.side_effect = None
    assert (await client.post(route, json={'action': 'confirm'})).json()['status'] == 'confirmed'
    dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_timeout_and_crashed_claim_are_never_redispatched(api, monkeypatch):
    client, pool = api
    dispatch = AsyncMock(side_effect=TimeoutError('unknown upstream outcome'))
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.retire', 'arguments': {'skill_id': 'base.find_site', 'version': '1.0.0'}}])
    route = f"/v1/command/cards/{data['cards'][0]['card_id']}"
    assert (await client.post(route, json={'action': 'confirm'})).json()['status'] == 'unknown'
    assert (await client.post(route, json={'action': 'confirm'})).status_code == 409
    dispatch.assert_awaited_once()
    async with pool.acquire() as conn:
        state = json.loads(await conn.fetchval('SELECT state FROM tank.command_threads WHERE thread_id=$1', uuid.UUID(thread)))
        card = state['cards'][data['cards'][0]['card_id']]
        card.update(status='executing', started_at='2000-01-01T00:00:00+00:00')
        await conn.execute('UPDATE tank.command_threads SET state=$2::jsonb WHERE thread_id=$1', uuid.UUID(thread), json.dumps(state))
    assert (await client.post(route, json={'action': 'confirm'})).json()['status'] == 'unknown'
    dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_tool_receipts_validate_ownership_and_reconcile_without_dispatch(api, monkeypatch):
    client, pool = api
    actual = await seed_ledger(pool, cost=0.03)
    dispatch = AsyncMock(return_value=(200, {'ledger_id': str(actual), 'ledger_ids': [str(actual)]}))
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.list', 'arguments': {}}])
    route = f"/v1/command/cards/{data['cards'][0]['card_id']}"
    original = command.refresh_action_receipts
    monkeypatch.setattr(command, 'refresh_action_receipts', AsyncMock(side_effect=RuntimeError('temporary database failure')))
    result = (await client.post(route, json={'action': 'confirm'})).json()
    assert result['status'] == 'confirmed' and result['receipt_status'] == 'pending'
    monkeypatch.setattr(command, 'refresh_action_receipts', original)
    assert (await client.post(route, json={'action': 'confirm'})).json()['receipt_status'] == 'recorded'
    await client.post(route, json={'action': 'confirm'})
    dispatch.assert_awaited_once()
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert sum(r['ledger_id'] == str(actual) for r in data['receipts']) == 1
    assert data['thread']['spent_usd'] == 0.05
    # A successful route response cannot attach another tenant's ledger row.
    foreign = await seed_ledger(pool, OTHER, 9)
    dispatch.return_value = (200, {'ledger_id': str(foreign)})
    other_thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.list', 'arguments': {}}])
    await client.post(f"/v1/command/cards/{data['cards'][0]['card_id']}", json={'action': 'confirm'})
    data = (await client.get(f'/v1/command/threads/{other_thread}')).json()
    assert all(r['ledger_id'] != str(foreign) for r in data['receipts'])
    assert data['cards'][0]['receipt_status'] == 'pending'
    assert data['thread']['spent_usd'] is None
    assert data['thread']['recorded_spent_usd'] == 0.02


@pytest.mark.asyncio
async def test_worker_receipts_require_explicit_ids_and_are_idempotent(api):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    card = (await client.post('/v1/command/build', json={'thread_id': thread, 'brief_markdown': 'Build'})).json()
    build = (await client.post(f"/v1/command/cards/{card['card_id']}", json={'action': 'confirm'})).json()['build_id']
    worker = {'x-tank-key': 'dummy-worker-key'}
    await client.get('/v1/command/builds/next', headers=worker)
    own = await seed_ledger(pool, cost=0.04)
    foreign = await seed_ledger(pool, OTHER, 9)
    route = f'/v1/command/builds/{build}/progress'
    body = {'status': 'done', 'step_label': 'Finished'}
    rejected = await client.post(route, headers=worker, json={**body, 'ledger_ids': [str(own), str(foreign)]})
    assert rejected.status_code == 409
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT status FROM tank.command_builds WHERE build_id=$1', uuid.UUID(build)) == 'running'
        assert await conn.fetchval('SELECT count(*) FROM tank.command_receipt_links') == 0
    assert (await client.post(route, headers=worker, json=body)).json()['receipt_status'] == 'pending'
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert data['receipts'] == []  # a same-tenant row is not inferred as build spend
    assert data['thread']['spent_usd'] is None
    assert data['thread']['receipt_status'] == 'pending'
    for _ in range(2):
        reply = await client.post(route, headers=worker, json={**body, 'ledger_ids': [str(own), str(own)]})
        assert reply.status_code == 200
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert len(data['receipts']) == 1
    assert data['receipts'][0]['cost_usd'] == 0.04


@pytest.mark.asyncio
async def test_binary_attachments_are_owned_bounded_and_not_given_to_text_model(api, monkeypatch):
    client, pool = api
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    binary = b'\x89PNG\x00\xffbinary bytes'
    metadata = (await client.post(f'/v1/command/threads/{thread}/attachments?name=picture.png', content=binary)).json()
    assert metadata['size'] == len(binary) and metadata['model_readable'] is False
    attachment = metadata['attachment_id']
    download = await client.get(f'/v1/command/attachments/{attachment}')
    assert download.content == binary
    assert download.headers['content-type'] == 'application/octet-stream'
    assert download.headers['x-content-type-options'] == 'nosniff'
    for headers in [{'x-tervory-user': 'other'}, {'x-tervory-tenant': str(OTHER)}]:
        assert (await client.get(f'/v1/command/attachments/{attachment}', headers=headers)).status_code == 404
    other = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    assert (await client.post(f'/v1/command/threads/{other}/turn', json={'text': 'Read', 'attachments': [{'attachment_id': attachment}]})).status_code == 404
    ledger = await seed_ledger(pool)
    turn = AsyncMock(return_value=SimpleNamespace(ledger_id=ledger, content='The attachment is stored.'))
    monkeypatch.setattr(command, 'route_turn', turn)
    assert (await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Read', 'attachments': [{'attachment_id': attachment}]})).status_code == 200
    context = json.dumps(turn.call_args.args[1])
    assert 'content unavailable to the text router' in context
    assert 'binary bytes' not in context
    assert (await client.post(f'/v1/command/threads/{thread}/attachments?name=../bad', content=b'x')).status_code == 422
    monkeypatch.setattr(command, 'MAX_ATTACHMENT_BYTES', 4)
    assert (await client.post(f'/v1/command/threads/{thread}/attachments?name=big', content=b'12345')).status_code == 413
    monkeypatch.setattr(command, 'MAX_THREAD_ATTACHMENT_BYTES', len(binary))
    assert (await client.post(f'/v1/command/threads/{thread}/attachments?name=full', content=b'x')).status_code == 413


@pytest.mark.asyncio
async def test_invalid_plan_preserves_turn_receipt_and_creates_no_cards(api, monkeypatch):
    client, pool = api
    dispatch = AsyncMock()
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    thread, data = await planned_turn(client, pool, monkeypatch, [
        {'tool': 'skala.list', 'arguments': {}},
        {'tool': 'skala.approve', 'arguments': {'skill_id': '../invalid', 'version': '1.0.0'}},
    ])
    assert data['cards'] == []
    assert len(data['receipts']) == 1
    dispatch.assert_not_awaited()
    assert 'No action was started' in data['messages'][-1]['content']


@pytest.mark.asyncio
async def test_reused_tool_receipt_cannot_count_again_in_another_thread(api, monkeypatch):
    client, pool = api
    ledger = await seed_ledger(pool, cost=0.03)
    monkeypatch.setattr(command, 'dispatch_action', AsyncMock(return_value=(200, {'ledger_id': str(ledger)})))
    for index in range(2):
        thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.list', 'arguments': {}}])
        await client.post(f"/v1/command/cards/{data['cards'][0]['card_id']}", json={'action': 'confirm'})
        data = (await client.get(f'/v1/command/threads/{thread}')).json()
        assert sum(r['ledger_id'] == str(ledger) for r in data['receipts']) == (1 if index == 0 else 0)
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.command_receipt_links WHERE ledger_id=$1', ledger) == 1


@pytest.mark.asyncio
async def test_tool_http_failure_keeps_exact_receipt_and_is_not_retried(api, monkeypatch):
    client, pool = api
    ledger = await seed_ledger(pool, cost=0.04)
    dispatch = AsyncMock(return_value=(502, {'detail': {'ledger_id': str(ledger), 'upstream': 'private provider detail'}}))
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.list', 'arguments': {}}])
    route = f"/v1/command/cards/{data['cards'][0]['card_id']}"
    result = await client.post(route, json={'action': 'confirm'})
    assert result.json()['status'] == 'failed'
    assert result.json()['receipt_status'] == 'recorded'
    assert 'private provider detail' not in result.text
    await client.post(route, json={'action': 'confirm'})
    dispatch.assert_awaited_once()
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert data['thread']['spent_usd'] == 0.06
    assert any(r['ledger_id'] == str(ledger) for r in data['receipts'])


def test_url_arguments_reject_embedded_credentials(runtime):
    actor = command.Actor(TENANT, 'founder', True)
    with pytest.raises(HTTPException):
        command.validate_action(command.PlannedAction(tool='tiger.watch', arguments={'url': 'https://dummy:dummy@example.com/item'}), actor)


@pytest.mark.asyncio
async def test_unknown_ledger_cost_can_refresh_without_reexecuting_action(api, monkeypatch):
    client, pool = api
    ledger = await seed_ledger(pool, cost=0)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET research_cost_status='unknown' WHERE id=$1", ledger)
    dispatch = AsyncMock(return_value=(200, {'ledger_id': str(ledger)}))
    monkeypatch.setattr(command, 'dispatch_action', dispatch)
    thread, data = await planned_turn(client, pool, monkeypatch, [{'tool': 'skala.list', 'arguments': {}}])
    route = f"/v1/command/cards/{data['cards'][0]['card_id']}"
    assert (await client.post(route, json={'action': 'confirm'})).json()['receipt_status'] == 'pending'
    assert (await client.get(f'/v1/command/threads/{thread}')).json()['thread']['spent_usd'] is None
    # Simulate the upstream cost-reconciliation owner supplying actual evidence.
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET cost_usd=0.04,research_cost_status='itemized' WHERE id=$1", ledger)
    assert (await client.post(route, json={'action': 'confirm'})).json()['receipt_status'] == 'recorded'
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert data['thread']['spent_usd'] == 0.06
    assert sum(r['ledger_id'] == str(ledger) for r in data['receipts']) == 1
    dispatch.assert_awaited_once()


@pytest.mark.asyncio
async def test_core_baseline_fields_are_used_without_repricing(api, monkeypatch):
    client, pool = api
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('fixture-model','fixture',0.001,0.002)")
    ledger = await seed_ledger(pool, cost=0.02)
    thread = (await client.post('/v1/command/threads', json={})).json()['thread_id']
    monkeypatch.setattr(command, 'route_turn', AsyncMock(return_value=SimpleNamespace(ledger_id=ledger, content='Measured answer')))
    await client.post(f'/v1/command/threads/{thread}/turn', json={'text': 'Hello'})
    receipt = (await client.get(f'/v1/command/threads/{thread}')).json()['receipts'][0]
    async with pool.acquire() as conn:
        actual = await conn.fetchrow('SELECT baseline_model,baseline_cost_usd FROM tank.ledger WHERE id=$1', ledger)
    assert receipt['baseline_model'] == actual['baseline_model']
    assert receipt['baseline_cost_usd'] == float(actual['baseline_cost_usd']) == 0.05
    assert receipt['saved_usd'] == pytest.approx(0.03)


@pytest.mark.asyncio
async def test_ledger_view_uses_existing_proof_route_and_scopes_output(api, runtime):
    client, pool = api
    runtime.app = client._transport.app
    received = []
    ledger_id = uuid.uuid4()

    @runtime.app.get('/v1/proof')
    async def existing_proof(request: Request):
        received.append(dict(request.query_params))
        assert request.headers['x-tervory-admin'] == 'founder'
        return {'tenants': [str(OTHER)], 'all_tenant_total': {'actual_usd': 999},
                'ledger': [{'id': str(ledger_id), 'tenant_id': str(TENANT), 'cost_usd': 0.02}],
                'page': 0, 'has_more': {'ledger': False}}

    actor = command.Actor(TENANT, 'founder', True)
    status, result = await command.dispatch_action(command.PlannedAction(tool='ledger.receipts', arguments={}), actor)
    assert status == 200
    assert received == [{'page': '0', 'tenant_id': str(TENANT)}]
    assert 'all_tenant_total' not in result and 'tenants' not in result
    assert result['ledger'][0]['id'] == str(ledger_id)
    assert command.explicit_ledger_ids(result) == []  # historical rows are not this read's cost



def test_scan_adapter_preserves_packaged_skill_input(runtime):
    import importlib.util
    skill = Path('tank/skills/scan.static/1.0.1')
    case = json.loads((skill / 'evals/cases.jsonl').read_text().splitlines()[0])
    actor = command.Actor(TENANT, 'founder', True)
    method, path, query, body = command.adapter_request(command.PlannedAction(tool='radix.scan', arguments=case['input']), actor)
    assert (method, path) == ('POST', '/v1/skala/scan.static/run')
    assert body['preview'] is False
    spec = importlib.util.spec_from_file_location('command_scan_fixture', skill / 'engine.py')
    engine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(engine)
    assert engine.run_skill(body['input']) == case['expected']
    _, _, _, scaffold = command.adapter_request(command.PlannedAction(tool='tisan.scaffold', arguments={
        'name': 'Example', 'slug': 'example', 'brand': {'colours': {}}}), actor)
    assert 'pages' not in scaffold['input']  # preserve the existing route's default pages
    assert command.ADAPTERS['tisan.scaffold'].paid is False  # current scaffold is pure code
