"""M26 offline: real standing-record logic, fake SQL/Hermes/Tank and signed events."""
import json
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

from agents.ghost.shared_blocks import StandingBlocks, published_id, SHARE_SECONDS
from agents.ghost.threat_queue import ThreatPayloadQueue, mark_undo_used, enforce_drain_once
from agents.ghost.client_settings import ClientAutumbraSettings, ApplyMode
from agents.ghost.store import Store
from agents.ghost.app import create_app
from agents.ghost.webhooks import CF_SECRET_ENV, sign_body
from agents.ghost.fixture_edge import FixtureEdgeControl
from agents.ghost.never_block import ActionCap
from hermes.publishing import Publisher
from hermes.record_routes import register_record_routes
from hermes.deidentify import deidentify

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
RID = '33333333-3333-4333-8333-333333333333'
IP = '45.33.32.156'
NOW = 1793664000.0


def iso(when):
    return datetime.fromtimestamp(when, timezone.utc).isoformat()


class FakeMemory:
    def __init__(self):
        self.client, self.platform, self.writes = {}, {}, []

    async def records(self, tenant, *, tier='client'):
        return list(self.platform.values()) if tier == 'platform' else list(self.client.get(tenant, {}).values())

    async def remember(self, tenant, text, kind, source, **options):
        assert options['index'] is False
        self.writes.append((text, source, options))
        row = {'id': options['row_id'], 'claim': text, 'kind': kind, 'last_verified': options['last_verified']}
        self.client.setdefault(tenant, {})[row['id']] = row
        return row

    async def forget(self, identity, tenant):
        self.client[tenant].pop(identity)


@pytest.fixture
def standing(tmp_path):
    store = Store(tmp_path / 'placeholder.sqlite3')
    queues = {t: ThreatPayloadQueue(tmp_path / t) for t in (A, B)}
    memory = FakeMemory()
    async def retract(method, path, body):
        assert path == '/v1/ghost/autumbra/blocks/withdraw'
        assert body['tenant_id'] == A
        memory.platform.pop(body['published_row'])
        return {'result': 'withdrawn'}
    tank = SimpleNamespace(call=AsyncMock(side_effect=retract))
    service = StandingBlocks(memory, tank, store, queues.__getitem__, clock=lambda: NOW)
    queues[A].write_receipt({'id': RID, 'tenant_id': A, 'applied': True, 'kind': 'block_ip',
        'address': IP, 'timestamp': iso(NOW - 25 * 3600), 'site': 'placeholder-private.example',
        'advisory_url': 'https://www.cisa.gov/known-exploited-vulnerabilities-catalog'})
    yield SimpleNamespace(service=service, queues=queues, memory=memory, store=store, tank=tank)
    store.close()


@pytest.mark.asyncio
async def test_stands_24h_once_without_customer_fields(standing):
    s = standing
    s.service.clock = lambda: NOW - 2 * 3600
    assert await s.service.reconcile(A) == [] and not s.memory.writes
    s.service.clock = lambda: NOW
    rows = await s.service.reconcile(A)
    await s.service.reconcile(A)
    assert len(rows) == len(s.memory.writes) == 1
    fact = json.loads(rows[0]['claim'])
    assert set(fact) == {'kind', 'address', 'receipt_id', 'applied_at', 'public_sources'}
    assert fact['address'] == IP and fact['receipt_id'] == RID
    assert 'placeholder-private' not in json.dumps(s.memory.writes)
    assert fact['public_sources'] == ['https://www.cisa.gov/known-exploited-vulnerabilities-catalog']


@pytest.mark.asyncio
async def test_undo_before_hold_and_own_address_write_nothing(standing):
    s = standing
    mark_undo_used(s.queues[A], prior_receipt_id=RID, tenant_id=A)
    assert await s.service.reconcile(A) == [] and not s.memory.writes
    s.store.set_state(A, 'autumbra_client_settings', {'own_cidrs': [IP + '/32']})
    # Independent receipt not marked undone, still protected by own CIDRs.
    s.queues[A].write_receipt({'id': B, 'tenant_id': A, 'applied': True, 'kind': 'block_ip',
                             'address': IP, 'timestamp': iso(NOW - 26 * 3600)})
    assert await s.service.reconcile(A) == [] and not s.memory.writes


@pytest.mark.asyncio
async def test_expiry_and_source_undo_withdraw(standing):
    s = standing
    source = (await s.service.reconcile(A))[0]
    target = published_id(A, source['id'])
    s.memory.platform[target] = {**source, 'id': target}
    assert await s.service.count(B, IP) == 1
    s.memory.platform[target]['last_verified'] = iso(NOW - SHARE_SECONDS)
    assert await s.service.count(B, IP) == 0
    s.memory.platform[target]['last_verified'] = iso(NOW)
    mark_undo_used(s.queues[A], prior_receipt_id=RID, tenant_id=A)
    assert await s.service.reconcile(A) == []
    assert not s.memory.platform and not s.memory.client[A]
    s.tank.call.assert_awaited_once()
    assert s.store.get_state(A, 'block_withdrawals', {}) == {}


class SQL:
    def __init__(self, tier='platform', policy=True):
        self.source = uuid.UUID(B)
        self.target = uuid.UUID(published_id(A, B))
        self.row = {'id': self.target, 'tier': tier, 'embed_model': ''}
        self.log = []
        self.policy = policy

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetchrow(self, query, *args):
        if 'memory_publish_policy' in query:
            return {'enabled': self.policy, 'identifiers': json.dumps({'reviewed': True, 'names': ['placeholder owner'],
                'emails': [], 'phones': [], 'addresses': [], 'client_domains': ['placeholder-private.example']})}
        if 'SELECT source_row' in query:
            return {'source_row': self.source}
        if query.lstrip().startswith('DELETE'):
            assert "tier='platform'" in query and args[1] == uuid.UUID('00000000-0000-0000-0000-000000000001')
            if self.row and self.row['tier'] == 'platform':
                row, self.row = self.row, None
                return row
            return None
        return {'id': self.source, 'kind': 'blocked_address', 'claim': json.dumps({'kind': 'blocked_address', 'address': IP}),
                'evidence': '[]', 'confidence': .5, 'last_verified': datetime.fromtimestamp(NOW, timezone.utc),
                'meta': json.dumps({'_index_enabled': False, 'public_addresses': [IP]})}

    async def fetchval(self, query, *args):
        if query.lstrip().startswith('INSERT'):
            assert args[6] == 'blocked_address'
            assert json.loads(args[7]) == {'_index_enabled': False}
            return self.target
        return False

    async def fetch(self, *args):
        return []

    async def execute(self, query, *args):
        if 'INSERT INTO' in query and 'memory_publish_log' in query:
            self.log.append('withdrawn' if "'withdrawn'" in query else args[3])
        return 'placeholder result'


def records(sql):
    return SimpleNamespace(pool=sql, schema=lambda agent: 'agent_ghost', agents=['ghost'],
                           lock=AsyncMock(), enqueue=AsyncMock(), model='placeholder-model')


@pytest.mark.asyncio
async def test_real_publisher_policy_log_and_code_only_share():
    sql = SQL(policy=False)
    r = records(sql)
    publisher = Publisher(r)
    assert (await publisher.publish('ghost', A, B, 'placeholder-founder'))['result'] == 'disabled'
    assert sql.log == ['disabled']
    sql.policy = True
    assert (await publisher.publish('ghost', A, B, 'placeholder-founder'))['result'] == 'published'
    assert sql.log == ['disabled', 'published']
    r.enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_withdraw_is_founder_only_platform_only_and_logged(monkeypatch):
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('TANK_KEY_GHOST', 'placeholder-ghost-key')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    sql = SQL(tier='client')
    r = records(sql)
    app = FastAPI()
    register_record_routes(app, lambda: r, lambda *args, **kwargs: 'ghost')
    path = '/founder/records/' + str(sql.target) + '/withdraw'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        body = {'tenant_id': A, 'agent': 'ghost'}
        assert (await client.post(path, json=body)).status_code == 404
        assert (await client.post(path, json=body, headers={'X-Tank-Key': 'placeholder-ghost-key', 'X-Tervory-Admin': 'placeholder-founder'})).status_code == 404
        headers = {'X-Tank-Key': 'placeholder-workspace-key', 'X-Tervory-Admin': 'placeholder-founder'}
        assert (await client.post(path, json=body, headers=headers)).status_code == 409
        assert sql.row['tier'] == 'client' and not sql.log
        sql.row['tier'] = 'platform'
        assert (await client.post(path, json=body, headers=headers)).status_code == 200
        assert sql.row is None and sql.log == ['withdrawn']


def test_public_address_survives_but_inventory_identity_wins():
    inventory = {'reviewed': True, 'names': ['placeholder owner'], 'emails': [], 'phones': [],
                 'addresses': [], 'client_domains': ['placeholder-private.example']}
    claim, _ = deidentify(json.dumps({'address': IP, 'site': 'placeholder-private.example'}), [], A, inventory, public_addresses=[IP])
    assert IP in claim and 'placeholder-private.example' not in claim
    inventory['addresses'] = [IP]
    claim, _ = deidentify(json.dumps({'address': IP}), [], A, inventory, public_addresses=[IP])
    assert IP not in claim


@pytest.mark.asyncio
async def test_signed_second_tenant_still_needs_own_log_and_mode(tmp_path, monkeypatch):
    monkeypatch.setenv(CF_SECRET_ENV, 'placeholder-signing-secret')
    monkeypatch.setenv('THREAT_PAYLOAD_QUEUE_ROOT', str(tmp_path / 'placeholder-queues'))
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    app = create_app()
    store = Store(tmp_path / 'placeholder-webhook.sqlite3')
    app.state.store = store
    app.state.block_memory_failures = 0
    app.state.shared_blocks = SimpleNamespace(count=AsyncMock(return_value=1))
    counter = 0
    async def event(client, log):
        nonlocal counter
        counter += 1
        body = json.dumps({'tenant_id': B, 'site': 'coolify.tervory.com', 'address': IP, 'raw_log': log}).encode()
        timestamp, nonce = str(int(time.time())), 'placeholder-nonce-' + str(counter)
        signature = sign_body(secret='placeholder-signing-secret', body=body, timestamp=timestamp, nonce=nonce)
        return await client.post('/ghost/autumbra/webhooks/edge', content=body, headers={
            'X-Autumbra-Signature': signature, 'X-Autumbra-Timestamp': timestamp, 'X-Autumbra-Nonce': nonce})
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
            result = await event(client, 'placeholder log without address')
            assert result.status_code == 200
            app.state.shared_blocks.count.assert_not_called()
            result = await event(client, 'placeholder attacking address ' + IP)
            assert result.status_code == 200 and result.json()['queued']
            q = ThreatPayloadQueue(tmp_path / 'placeholder-queues' / B)
            settings = ClientAutumbraSettings(tenant_id=B, shield_mode=ApplyMode.never)
            edge = FixtureEdgeControl(tenant_id=B)
            receipt = enforce_drain_once(queue=q, settings=settings, control=edge, action_cap=ActionCap(limit=100))
            assert receipt['source_data'] == {'autumbra.shared_blocks': 1}
            assert receipt['applied'] is False and not edge.list_blocked()
    finally:
        store.close()


@pytest.mark.asyncio
async def test_withdrawal_retry_survives_deleted_client_source(standing):
    s = standing
    source = (await s.service.reconcile(A))[0]
    target = published_id(A, source['id'])
    s.memory.platform[target] = {**source, 'id': target}
    retract = s.tank.call.side_effect
    s.tank.call.side_effect = RuntimeError('placeholder unavailable')
    mark_undo_used(s.queues[A], prior_receipt_id=RID, tenant_id=A)
    with pytest.raises(RuntimeError):
        await s.service.reconcile(A)
    assert not s.memory.client[A]
    assert s.store.get_state(A, 'block_withdrawals', {})
    s.tank.call.side_effect = retract
    await s.service.reconcile(A)
    assert not s.memory.platform and s.store.get_state(A, 'block_withdrawals', {}) == {}


@pytest.mark.asyncio
async def test_code_only_records_never_call_encoder_or_index():
    from hermes.records import Records
    sql = SQL()
    encoder = SimpleNamespace(validate=lambda claim: (_ for _ in ()).throw(AssertionError('placeholder encoder called')))
    r = Records(sql, None, encoder, 'placeholder-model', ['ghost'])
    r.lock = AsyncMock()
    r.enqueue = AsyncMock()
    r.process_one = AsyncMock()
    r.get = AsyncMock(return_value={'id': B, 'claim': 'placeholder claim', 'evidence': [], 'embed_model': ''})
    await r.save('ghost', A, 'placeholder claim', [], row_id=B, index=False)
    r.enqueue.assert_not_called()
    r.process_one.assert_not_called()


@pytest.mark.asyncio
async def test_tank_share_uses_existing_publish_policy_and_requires_confirm(monkeypatch):
    import command
    import ghost_routes
    import memory_routes
    import trigger_routes
    from trigger_commands import CONFIRMED
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    actor = command.Actor(uuid.UUID(A), 'placeholder-founder', True)
    monkeypatch.setattr(command, 'identity', AsyncMock(return_value=actor))
    monkeypatch.setattr(trigger_routes, 'code_receipt', AsyncMock(return_value=uuid.UUID(RID)))
    room = AsyncMock(return_value=httpx.Response(200, json={'items': [{'id': B, 'address': IP}]}))
    monkeypatch.setattr(ghost_routes, 'call_room', room)
    sql = SQL(policy=False)
    publisher = Publisher(records(sql))
    async def hermes(method, path, user, *, body=None, params=None):
        assert path == '/founder/publish' and user == actor.user_id
        result = await publisher.publish(body['agent'], body['tenant_id'], body['source_row'], user)
        if result['result'] == 'disabled':
            from fastapi import HTTPException
            raise HTTPException(403, result)
        return result
    monkeypatch.setattr(memory_routes, 'hermes', hermes)
    app = FastAPI()
    app.include_router(memory_routes.router)
    app.include_router(ghost_routes.router)
    monkeypatch.setattr(ghost_routes, 'runtime', lambda: SimpleNamespace(app=app, TANK_API_KEY='placeholder-workspace-key'))
    headers = {'X-Tank-Key': 'placeholder-workspace-key', 'X-Tervory-Admin': actor.user_id}
    body = {'tenant_id': A, 'record_ids': [B]}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        assert (await client.post('/v1/ghost/autumbra/blocks/share', json=body, headers=headers)).status_code == 409
        assert not sql.log
        token = CONFIRMED.set((actor.tenant_id, actor.user_id, uuid.UUID(RID), 'autumbra.blocks.share', body))
        try:
            denied = await client.post('/v1/ghost/autumbra/blocks/share', json=body, headers=headers)
            assert denied.status_code == 403 and denied.json()['items'][0]['result'] == 'disabled'
            assert sql.log == ['disabled']
            sql.policy = True
            accepted = await client.post('/v1/ghost/autumbra/blocks/share', json=body, headers=headers)
            assert accepted.status_code == 200 and accepted.json()['items'][0]['result'] == 'published'
            assert sql.log == ['disabled', 'published']
        finally:
            CONFIRMED.reset(token)


@pytest.mark.asyncio
async def test_live_epoch_applied_time_and_public_sources_only(standing):
    s = standing
    s.queues[A].write_receipt({'id': RID, 'tenant_id': A, 'applied': True,
        'address': IP, 'timestamp': iso(NOW),
        'applied_record': {'kind': 'block_ip', 'applied_at': NOW - 25 * 3600},
        'source_url': 'https://www.cisa.gov/catalog?placeholder_private=customer'})
    row = (await s.service.reconcile(A))[0]
    fact = json.loads(row['claim'])
    assert fact['applied_at'] == iso(NOW - 25 * 3600)
    assert fact['public_sources'] == []
    assert 'placeholder_private' not in json.dumps(s.memory.writes)


@pytest.mark.asyncio
async def test_approval_linked_undo_prevents_standing_record(standing):
    s = standing
    s.queues[A].write_receipt({'id': RID, 'prior_receipt_id': B, 'tenant_id': A,
        'applied': True, 'address': IP, 'timestamp': iso(NOW - 25 * 3600),
        'applied_record': {'kind': 'block_ip'}})
    mark_undo_used(s.queues[A], prior_receipt_id=B, tenant_id=A)
    assert await s.service.reconcile(A) == [] and not s.memory.writes


@pytest.mark.asyncio
async def test_existing_memory_client_pages_without_recall():
    from chassis.memory import MemoryClient
    offsets = []
    def api(request):
        assert request.url.path == '/records' and request.method == 'GET'
        assert request.headers['X-Tank-Key'] == 'placeholder-memory-key'
        offset = int(request.url.params['offset'])
        offsets.append(offset)
        count = 200 if offset == 0 else 1
        return httpx.Response(200, json={'memories': [{'id': 'placeholder-' + str(offset + i)} for i in range(count)]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(api)) as http:
        memory = MemoryClient(base_url='http://placeholder', api_key='placeholder-memory-key', http=http)
        assert len(await memory.records(A)) == 201
    assert offsets == [0, 200]
