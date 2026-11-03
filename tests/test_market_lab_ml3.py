"""ML3 offline contracts. Placeholder credentials; no provider/model/outside network."""
import asyncio
import hashlib
import hmac
import json
import sys
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from core import intel
from feeds.licence import LicenceBlocked, require_commercial_intel
from agents.ghost.market_lab_intel import accept_ioc_bundle
import command
import market_lab_ml3 as ml3

FORMAT = json.loads((ROOT / 'tests/market_lab_ml3/sources.json').read_text())
OWNER, OTHER = UUID('00000000-0000-0000-0000-000000000031'), UUID('00000000-0000-0000-0000-000000000032')
PLACEHOLDER = 'placeholder-webhook-secret-once'


class Publisher:
    def __init__(self):
        self.client = SimpleNamespace(max_bytes=None)
        self.gets, self.posts = [], []
    def get(self, url):
        self.gets.append(url)
        if url == intel.REPO:
            data = {'sha': 'a' * 40, 'truncated': False, 'tree': [
                {'type': 'blob', 'path': 'workspace/package-lock.json'},
                {'type': 'blob', 'path': 'tests/placeholder/package-lock.json'}]}
        elif url == intel.KEV:
            data = FORMAT['kev']
        elif url.endswith('/v1/vulns/' + FORMAT['osv_advisory']['id']):
            data = FORMAT['osv_advisory']
        elif url.endswith('/workspace/package-lock.json'):
            data = FORMAT['lock']
        else:
            raise AssertionError('unexpected placeholder publisher URL')
        return json.dumps(data).encode()
    def post_json(self, url, payload):
        assert url == intel.OSV
        self.posts.append(payload)
        return json.dumps(FORMAT['osv_query']).encode()


def test_real_format_bundle_matches_existing_consumer_and_licence_gate():
    publisher = Publisher()
    raw = intel.produce(publisher)
    accepted = accept_ioc_bundle(raw)
    assert accepted['schema_version'] == 'market_lab.ioc.v1' and accepted['paid'] is False
    assert {s['id'] for s in accepted['sources']} == {'cisa_kev', 'osv_ghsa'}
    assert {i['value'] for i in accepted['indicators']} == {'CVE-2021-44228', FORMAT['osv_advisory']['id']}
    assert not any('/tests/' in url for url in publisher.gets)
    assert raw['pinned_packages'] == 1 and raw['lock_commit'] == 'a' * 40
    for field, value in [('licence', ''), ('terms_checked_at', ''), ('id', 'placeholder-unreviewed'), ('key_required', True)]:
        with pytest.raises(LicenceBlocked):
            require_commercial_intel(replace(intel.SOURCES[0], **{field: value}))


def test_osv_pagination_cannot_silently_truncate():
    publisher = Publisher()
    publisher.post_json = lambda *_: json.dumps({'results': [{'next_page_token': 'placeholder'}]}).encode()
    with pytest.raises(ValueError, match='pagination'):
        intel.osv_indicators(publisher, [{'ecosystem': 'npm', 'name': 'minimist', 'version': '1.2.5'}])


def test_signature_covers_exact_raw_body():
    raw = b'{"text":"placeholder"}'
    expected = 'sha256=' + hmac.new(PLACEHOLDER.encode(), raw, hashlib.sha256).hexdigest()
    assert ml3.signature(raw, PLACEHOLDER) == expected
    assert ml3.signature(raw + b' ', PLACEHOLDER) != expected


@pytest_asyncio.fixture
async def database(tmp_path, monkeypatch):
    import pgserver
    server = pgserver.get_server(tmp_path / 'pg')
    pool = await asyncpg.create_pool(server.get_uri(), min_size=1, max_size=3)
    await pool.execute((ROOT / 'tank/schema.sql').read_text())
    app = FastAPI()
    actor = command.Actor(OWNER, 'placeholder-admin', False, frozenset({'market_lab'}), True)
    runtime = SimpleNamespace(pool=lambda: pool, box_region=lambda: 'us-east', app=app, TANK_API_KEY='placeholder-workspace-key')
    monkeypatch.setitem(sys.modules, 'main', runtime)
    monkeypatch.setenv('TANK_KEY_GHOST', 'placeholder-ghost-key')
    monkeypatch.setenv('TANK_KEY_MARKET_LAB', 'placeholder-market-lab-key')
    monkeypatch.setattr(command, 'authorized_actor', AsyncMock(side_effect=lambda actor, *args, **kwargs: actor))
    monkeypatch.setattr(ml3.secrets, 'token_urlsafe', lambda *_: PLACEHOLDER)
    import vault
    # No real encryption key is generated, installed, inspected or used in tests.
    sealed = {}
    def seal(value, context):
        sealed[context] = value
        return 'placeholder-ciphertext'
    monkeypatch.setattr(vault, 'seal', seal)
    monkeypatch.setattr(vault, 'open_seal', lambda value, context: sealed[context])

    async def identity(request: Request):
        tenant = UUID(request.headers.get('x-placeholder-tenant', str(OWNER)))
        return replace(actor, tenant_id=tenant)
    app.dependency_overrides[command.identity] = identity
    app.include_router(command.router)
    app.include_router(ml3.build_router(runtime))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        yield SimpleNamespace(pool=pool, app=app, client=client, actor=actor, sealed=sealed)
    await pool.close()


async def proposal(db, tool, arguments=None):
    thread = (await db.client.post('/v1/command/threads', json={})).json()['thread_id']
    response = await db.client.post(f'/v1/command/threads/{thread}/actions', json={'tool': tool, 'arguments': arguments or {}})
    assert response.status_code == 200
    return thread, response.json()['card_id']


@pytest.mark.asyncio
async def test_confirm_once_and_no_secret_in_history_or_logs(database, monkeypatch, caplog):
    db = database
    monkeypatch.setattr(ml3, 'room', AsyncMock(return_value={'status': 'queued'}))
    thread, card = await proposal(db, 'market_lab.alerts.webhook', {'url': 'https://placeholder.example/hooks'})
    assert await db.pool.fetchval('SELECT count(*) FROM tank.market_lab_alerts') == 0
    result = await db.client.post('/v1/command/cards/' + card, json={'action': 'confirm'})
    assert result.status_code == 200
    assert result.json()['result']['text'] == PLACEHOLDER
    repeated = await db.client.post('/v1/command/cards/' + card, json={'action': 'confirm'})
    assert PLACEHOLDER not in repeated.text
    history = await db.client.get('/v1/command/threads/' + thread)
    assert PLACEHOLDER not in history.text
    assert PLACEHOLDER not in caplog.text
    assert PLACEHOLDER not in json.dumps(await db.pool.fetchval('SELECT state FROM tank.command_threads WHERE tenant_id=$1', OWNER))
    assert PLACEHOLDER not in str(await db.pool.fetch('SELECT data FROM tank.command_events WHERE tenant_id=$1', OWNER))
    assert await db.pool.fetchval('SELECT webhook_sealed FROM tank.market_lab_alerts WHERE tenant_id=$1', OWNER) == 'placeholder-ciphertext'
    assert await db.pool.fetchval('SELECT count(*) FROM tank.market_lab_alerts WHERE tenant_id=$1', OTHER) == 0
    assert (await db.client.post('/v1/market-lab/alerts/webhook', json={'url':'https://placeholder.example/hooks'})).status_code == 404


@pytest.mark.asyncio
async def test_read_receipts_and_tenant_scope(database, monkeypatch):
    db = database
    async def data(operation, tenant):
        assert UUID(str(tenant)) in {OWNER, OTHER}
        if operation == 'predictions':
            return {'predictions': [{'id': str(tenant), 'statement': 'placeholder prediction', 'confidence': .75,
                                     'horizon_seconds': 86400, 'outcome': 'hit', 'realised_value': 12}]}
        return {'warnings': [], 'feeds': [], 'curves': [], 'hits': 0, 'misses': 0}
    monkeypatch.setattr(ml3, 'room', data)
    for operation in ('warnings', 'predictions', 'calibration', 'feeds'):
        response = await db.client.get('/v1/market-lab/reads/' + operation)
        assert response.status_code == 200
        body = response.json()
        row = await db.pool.fetchrow('SELECT tenant_id,rung,model,cost_usd FROM tank.ledger WHERE id=$1', UUID(body['ledger_id']))
        assert row['tenant_id'] == OWNER and row['rung'] == 3 and row['model'] == 'code' and row['cost_usd'] == 0
        if operation == 'predictions':
            summary = json.loads(body['records'][0]['summary'])
            assert summary['confidence'] == .75 and summary['horizon_seconds'] == 86400 and summary['realised_value'] == 12
    other = await db.client.get('/v1/market-lab/reads/predictions', headers={'x-placeholder-tenant': str(OTHER)})
    assert str(OWNER) not in other.text
    for name in ('warnings', 'predictions', 'calibration', 'feeds'):
        adapter = command.ADAPTERS['market_lab.' + name]
        assert not adapter.paid and adapter.kind == 'other'
    ordinary = replace(db.actor, tenant_admin=False)
    assert not any(t.startswith('market_lab.alerts.') for t in command.allowed_tools(ordinary))


@pytest.mark.asyncio
async def test_intel_corridor_accepts_only_autumbra_or_founder(database, monkeypatch):
    proxy = AsyncMock(return_value=accept_ioc_bundle(intel.produce(Publisher())))
    monkeypatch.setattr(ml3, 'room', proxy)
    for headers in ({}, {'x-tank-key': 'placeholder-market-lab-key'}, {'x-tank-key': 'placeholder-other-key'}):
        response = await database.client.get('/v1/market-lab/intel', headers=headers)
        assert response.status_code in {401, 403}
    response = await database.client.get('/v1/market-lab/intel', headers={'x-tank-key': 'placeholder-ghost-key'})
    assert response.status_code == 200
    proxy.assert_awaited_once_with('intel', ml3.PLATFORM)


@pytest.mark.asyncio
async def test_interrupted_smtp_claim_is_not_retried(database):
    from agents.tiger.alert_email import deliver_pending
    db = database
    warning = uuid4()
    await db.pool.execute('INSERT INTO tank.market_lab_alerts(tenant_id,email_enabled,email_since) VALUES($1,true,now())', OWNER)
    await db.pool.execute("INSERT INTO tank.market_lab_deliveries(tenant_id,warning_id,channel,status,letter) VALUES($1,$2,'email','pending',$3::jsonb)", OWNER, warning, json.dumps({'subject': 'placeholder existing warning', 'text':'placeholder existing warning'}))
    class Store:
        async def pending_mail(self, tenant, now):
            return [r['warning_id'] for r in await db.pool.fetch("SELECT warning_id FROM tank.market_lab_deliveries WHERE tenant_id=$1 AND status='pending'", UUID(tenant))]
        async def claim_mail(self, tenant, ident, now):
            return await ml3.claim(UUID(tenant), ident, 'email')
        async def finish_mail(self, tenant, ident, status, now):
            await db.pool.execute('UPDATE tank.market_lab_deliveries SET status=$3 WHERE tenant_id=$1 AND warning_id=$2', UUID(tenant), ident, status)
    class Interrupted:
        count = 0
        async def send(self, letter):
            self.count += 1
            raise asyncio.CancelledError
    transport = Interrupted()
    with pytest.raises(asyncio.CancelledError):
        await deliver_pending(Store(), str(OWNER), transport=transport, recipient='placeholder@example.test', namespace='market_lab')
    assert await db.pool.fetchval('SELECT status FROM tank.market_lab_deliveries WHERE tenant_id=$1', OWNER) == 'sending'
    await deliver_pending(Store(), str(OWNER), transport=transport, recipient='placeholder@example.test', namespace='market_lab')
    assert transport.count == 1
    assert await ml3.claim(OTHER, warning, 'email') is None


@pytest.mark.asyncio
async def test_webhook_raw_signature_and_no_resend(database, monkeypatch):
    db = database
    monkeypatch.setattr(ml3, 'room', AsyncMock(return_value={'status': 'queued'}))
    _, card = await proposal(db, 'market_lab.alerts.webhook', {'url':'https://placeholder.example/hooks'})
    await db.client.post('/v1/command/cards/' + card, json={'action':'confirm'})
    warning = uuid4()
    await db.pool.execute("INSERT INTO tank.market_lab_deliveries(tenant_id,warning_id,channel,status,letter) VALUES($1,$2,'webhook','pending',$3::jsonb)", OWNER, warning, json.dumps({'subject':'placeholder','text':'placeholder'}))
    captured = []
    @asynccontextmanager
    async def sender(url, **kwargs):
        assert url == 'https://placeholder.example/hooks'
        captured.append(kwargs)
        assert kwargs['headers']['X-Market-Lab-Signature'] == ml3.signature(kwargs['content'], PLACEHOLDER)
        yield SimpleNamespace(status_code=202)
    import access
    monkeypatch.setattr(access, 'public_stream', sender)
    assert await ml3.webhooks(OWNER) == {'sent':1}
    assert await ml3.webhooks(OWNER) == {'sent':0}
    assert await ml3.webhooks(OTHER) == {'sent':0}
    assert len(captured) == 1


@pytest.mark.asyncio
async def test_tables_follow_existing_rls_rollout(database):
    pool = database.pool
    staged = await pool.fetchval("SELECT bool_or(relrowsecurity) FROM pg_class WHERE oid IN ('tank.market_lab_alerts'::regclass,'tank.market_lab_deliveries'::regclass)")
    assert staged is False
    await pool.execute("ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY")
    await pool.execute((ROOT / 'tank/schema.sql').read_text())
    policies = await pool.fetch("SELECT relname,relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid IN ('tank.market_lab_alerts'::regclass,'tank.market_lab_deliveries'::regclass)")
    assert all(r['relrowsecurity'] and r['relforcerowsecurity'] for r in policies)
    await pool.execute('INSERT INTO tank.market_lab_alerts(tenant_id,email_enabled) VALUES($1,true)', OWNER)
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute('CREATE ROLE ml3_placeholder NOBYPASSRLS')
        await conn.execute('GRANT USAGE ON SCHEMA tank TO ml3_placeholder')
        await conn.execute('GRANT SELECT ON tank.market_lab_alerts TO ml3_placeholder')
        await conn.execute('SET LOCAL ROLE ml3_placeholder')
        await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(OTHER))
        assert await conn.fetchval('SELECT count(*) FROM tank.market_lab_alerts') == 0
        await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(OWNER))
        assert await conn.fetchval('SELECT count(*) FROM tank.market_lab_alerts') == 1


@pytest.mark.asyncio
async def test_room_prediction_read_is_the_existing_ledger(database):
    from core.ml3 import build_router
    from core.ledger import PostgresLedger
    from core.pure import make_prediction
    from datetime import datetime, timedelta, timezone
    @asynccontextmanager
    async def ledger_context():
        async with database.pool.acquire() as conn:
            yield PostgresLedger(conn)
    async with ledger_context() as ledger:
        await ledger.apply_schema()
        now = datetime(2026, 11, 1, tzinfo=timezone.utc)
        prediction = make_prediction(tenant_id=str(OWNER), statement='placeholder prediction', metric_series_id='placeholder-series', comparator='gte', target=12, made_at=now, resolve_by=now + timedelta(days=1), rationale='placeholder')
        prediction.update(confidence=.75, kind='placeholder', feed='placeholder')
        await ledger.save_prediction(prediction)
    room_app = FastAPI()
    room_app.include_router(build_router(key_ok=lambda key: key == 'placeholder-room-key', ledger_context=ledger_context, engine='ffl'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room_app), base_url='http://placeholder') as client:
        assert (await client.post('/market/ml3/predictions', json={'tenant_id':str(OWNER)})).status_code == 401
        own = (await client.post('/market/ml3/predictions', json={'tenant_id':str(OWNER)}, headers={'x-tank-key':'placeholder-room-key'})).json()['predictions']
        foreign = (await client.post('/market/ml3/predictions', json={'tenant_id':str(OTHER)}, headers={'x-tank-key':'placeholder-room-key'})).json()['predictions']
        assert own[0]['confidence'] == .75 and own[0]['horizon_seconds'] == 86400
        assert foreign == []


@pytest.mark.asyncio
async def test_exact_chat_commands_never_reach_a_model(database):
    for name in ('warnings', 'predictions', 'calibration', 'feeds'):
        # The runtime deliberately has no Message/RouteRequest/run_route: a
        # fall-through to the model planner fails instead of making a call.
        answer = await command.route_turn(database.actor, [{'role':'user', 'content':'market_lab.' + name}])
        plan = json.loads(answer.content)
        assert plan['actions'] == [{'tool':'market_lab.' + name, 'arguments':{'limit':20, 'page':0}}]
        row = await database.pool.fetchrow('SELECT rung,model,cost_usd FROM tank.ledger WHERE id=$1', answer.ledger_id)
        assert row['rung'] == 3 and row['model'] == 'code' and row['cost_usd'] == 0
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await command.route_turn(database.actor, [{'role':'user', 'content':'market_lab.feeds {"tenant_id":"placeholder"}'}])
    assert error.value.status_code == 422


@pytest.mark.asyncio
async def test_missing_owned_exact_command_turn_never_reaches_model(database):
    from fastapi import HTTPException
    # The fake runtime has no run_route or model request types. A model fallback
    # fails this test independently of the expected validation response.
    with pytest.raises(HTTPException) as error:
        await command.route_turn(database.actor,
            [{'role': 'user', 'content': 'market_lab.warnings'}], task_id=uuid4())
    assert error.value.status_code == 422
    assert await database.pool.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1', OWNER) == 0


@pytest.mark.asyncio
async def test_room_feeds_returns_registered_key_names_without_values(monkeypatch):
    from core import ml3 as room
    monkeypatch.setenv('EIA_API_KEY', 'placeholder-private-value')
    monkeypatch.setattr(room, 'overview', AsyncMock(return_value={'feeds': [
        {'id': 'eia_diesel', 'name': 'placeholder feed', 'state': 'off', 'rows': 0}]}))
    monkeypatch.setattr(room, 'latest', AsyncMock(return_value=None))
    @asynccontextmanager
    async def context(): yield SimpleNamespace()
    app = FastAPI()
    app.include_router(room.build_router(key_ok=lambda value: value == 'placeholder-room', ledger_context=context, engine='ffl'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as http:
        response = await http.post('/market/ml3/feeds', json={'tenant_id': str(OWNER)}, headers={'x-tank-key': 'placeholder-room'})
    assert response.status_code == 200
    assert response.json()['feeds'][0]['key_name'] == 'EIA_API_KEY'
    assert 'placeholder-private-value' not in response.text


@pytest.mark.asyncio
async def test_confirmed_alert_setup_ensures_existing_tenant_warning_jobs(monkeypatch):
    from core import ml3 as room
    import chassis.db
    ensure = AsyncMock()
    monkeypatch.setattr(chassis.db, 'ensure_schedules', ensure)
    @asynccontextmanager
    async def context(): yield SimpleNamespace(conn=SimpleNamespace())
    app = FastAPI()
    app.include_router(room.build_router(key_ok=lambda value: value == 'placeholder-room', ledger_context=context, engine='ffl'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as http:
        response = await http.post('/market/ml3/alerts', json={'tenant_id': str(OTHER)}, headers={'x-tank-key': 'placeholder-room'})
    assert response.status_code == 200
    schedules = ensure.await_args.args[2]
    assert {row['kind'] for row in schedules} == {'refresh', 'opportunities', 'resolve', 'alerts'}
    assert all(row['tenant_id'] == str(OTHER) for row in schedules)
