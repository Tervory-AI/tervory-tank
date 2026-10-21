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
    runtime = SimpleNamespace(TANK_API_KEY='fixture-workspace-key', box_region=lambda: 'us-east')
    monkeypatch.setitem(sys.modules, 'main', runtime)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    monkeypatch.setenv('TANK_KEY_WORKERS', 'fixture-worker-key')
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
    headers['x-tank-key'] = 'fixture-worker-key'
    with pytest.raises(HTTPException) as refused:
        await command.identity(request(**headers))
    assert refused.value.status_code == 401


@pytest.mark.asyncio
async def test_worker_key_is_separate(runtime):
    with pytest.raises(HTTPException):
        await command.worker(request(**{'x-tank-key': runtime.TANK_API_KEY}))
    await command.worker(request(**{'x-tank-key': 'fixture-worker-key'}))


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
    assert (await client.get(f'/v1/command/threads/{thread}/events?after=1')).text == ''
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
    workers = {'x-tank-key': 'fixture-worker-key'}
    assert (await client.get('/v1/command/builds/next')).status_code == 401
    claims = await asyncio.gather(*[client.get('/v1/command/builds/next', headers=workers) for _ in range(2)])
    assert sum(r.json() is not None for r in claims) == 1
    progress = {'status': 'awaiting_review', 'step_label': 'PR opened', 'pr_url': 'https://github.com/Tervory-AI/tervory-tank/pull/123', 'ci_status': 'passed', 'review_status': 'pending'}
    assert (await client.post(f'/v1/command/builds/{build_id}/progress', headers=workers, json=progress)).status_code == 200
    data = (await client.get(f'/v1/command/threads/{thread}')).json()
    assert data['steps'][0]['link'] == progress['pr_url']
    assert data['steps'][0]['ci_status'] == 'passed'
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
    assert route.call_args.args[1][0]['content'] == 'Hi\nAttachment notes.txt:\nLocal notes'
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
