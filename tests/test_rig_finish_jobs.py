"""Cloud-only recovery proofs: real PostgreSQL, fake transport, no providers."""
import asyncio
from contextlib import asynccontextmanager
from datetime import timedelta
from decimal import Decimal
import hashlib
import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import asyncpg
import pytest

from chassis.tenant_db import TenantPool, administrative, tenant_scope
from rigbox import cart_runtime, price_events
from rigbox.commerce import CommerceError
from rigbox.service import Service
from rigbox.store import PgStore
from test_rig_cart import TENANT, OTHER, SESSION, NOW, setup
from test_rig_recall_window import (
    _admin_url, _create_database, _database_url, _drop_database,
    _load_rig_app, _saved, _when,
)


@asynccontextmanager
async def database():
    admin = _admin_url()
    suffix = uuid4().hex[:16]
    name, role = 'rig_finish_' + suffix, 'rig_worker_' + suffix
    await _create_database(admin, name)
    made_role = False
    try:
        async with asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=4) as pool:
            await PgStore(pool).apply_schema()
            await pool.execute(f'CREATE ROLE "{role}" NOLOGIN')
            made_role = True
            await pool.execute(f'GRANT USAGE ON SCHEMA agent_rig TO "{role}"')
            await pool.execute(f'GRANT ALL ON ALL TABLES IN SCHEMA agent_rig TO "{role}"')
            await pool.execute(f'GRANT ALL ON ALL SEQUENCES IN SCHEMA agent_rig TO "{role}"')
            for table in ('searches', 'products', 'price_history'):
                await pool.execute(f'ALTER TABLE agent_rig.{table} ENABLE ROW LEVEL SECURITY')
                await pool.execute(f"""CREATE POLICY finish_tenant ON agent_rig.{table}
                    USING (tenant_id::text = current_setting('app.tenant_id', true))
                    WITH CHECK (tenant_id::text = current_setting('app.tenant_id', true))""")

            async def restrict(conn):
                # SET ROLE on every checkout, after asyncpg's connection reset.
                await conn.execute(f'SET ROLE "{role}"')

            async with asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=4,
                                          setup=restrict) as worker:
                yield pool, TenantPool(worker, pool)
    finally:
        await _drop_database(admin, name)
        if made_role:
            conn = await asyncpg.connect(admin)
            try:
                await conn.execute(f'DROP ROLE "{role}"')
            finally:
                await conn.close()


@pytest.mark.asyncio
async def test_nightly_retention_crosses_rls_only_for_maintenance_tenant(monkeypatch):
    monkeypatch.delenv('RIG_SEARCH_RECALL_DAYS', raising=False)
    module = _load_rig_app()
    async with database() as (pool, scoped):
        for tenant in (TENANT, OTHER):
            store = PgStore(pool)
            await store.add_search(tenant, 'v1', _saved('old', _when(100)))
            await store.add_search(tenant, 'v1', _saved('recent', _when(1)))
        module.app.state.rig = Service(PgStore(scoped))
        ctx = SimpleNamespace(tenant_id=module.HEARTBEAT_TENANT, job_id='offline-retention')
        with tenant_scope(module.HEARTBEAT_TENANT):
            # A normal scheduled job cannot see either retailer through RLS.
            assert await scoped.fetchval('SELECT count(*) FROM agent_rig.searches') == 0
            assert await module.expire_searches(ctx) == {'deleted': 2}
            assert not administrative()
            assert await module.expire_searches(ctx) == {'deleted': 0}
        rows = await pool.fetch('SELECT tenant_id::text,query FROM agent_rig.searches')
        assert {(r['tenant_id'], r['query']) for r in rows} == {(TENANT, 'recent'), (OTHER, 'recent')}
        with tenant_scope(TENANT), pytest.raises(PermissionError):
            await module.expire_searches(SimpleNamespace(tenant_id=TENANT, job_id='not-maintenance'))


@pytest.mark.asyncio
async def test_cart_worker_recovers_discovery_and_isolates_tenants(monkeypatch, caplog):
    monkeypatch.setenv('TANK_REGION', 'us-east')
    discoveries, ticks, seen = [], [], []

    async def tenants():
        assert administrative()
        discoveries.append(True)
        if len(discoveries) == 1:
            raise OSError('private database detail')
        return [TENANT, OTHER]

    async def sweep(tenant):
        assert not administrative()
        seen.append(tenant)
        if tenant == TENANT:
            raise CommerceError('private store detail')

    async def sleep(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(cart_runtime, 'Cart', lambda *args: SimpleNamespace(sweep=sweep))
    monkeypatch.setattr(cart_runtime, 'asyncio', SimpleNamespace(
        sleep=sleep, create_task=asyncio.create_task, gather=asyncio.gather))
    service = SimpleNamespace(store=SimpleNamespace(tenant_ids=tenants))
    task = cart_runtime.install(service, None, None)
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, 2)
    assert task.cancelled() and seen == [TENANT, OTHER] and ticks == [1, 1]
    assert len(discoveries) == 2 and 'Cart tenant discovery will retry' in caplog.text
    assert 'private' not in caplog.text


@pytest.mark.asyncio
async def test_unavailable_connection_does_not_block_other_checkout_expiry(monkeypatch):
    cart, fake, _, _, clock, client = await setup(monkeypatch)
    try:
        results = []
        for session in (SESSION, 't' * 43):
            await cart.add(TENANT, session, 'stock', 1)
            results.append(await cart.checkout(TENANT, session))
        first = await cart.rows.get(TENANT, results[0]['id'])
        first['config']['vault_name'] = 'unavailable'
        await cart.rows.put(TENANT, first['id'], first)
        original = cart.platform
        async def platform(tenant, config):
            if config['vault_name'] == 'unavailable':
                raise CommerceError('connection_unavailable')
            return await original(tenant, config)
        cart.platform = platform
        clock[0] += timedelta(minutes=6)
        await cart.sweep(TENANT)
        assert (await cart.rows.get(TENANT, results[0]['id']))['state'] == 'cancel_unknown'
        assert (await cart.rows.get(TENANT, results[1]['id']))['state'] == 'expired'
        assert [row['status'] for row in fake.orders.values()] == ['pending', 'cancelled']
        cart.platform = original
        await cart.sweep(TENANT)
        assert (await cart.rows.get(TENANT, results[0]['id']))['state'] == 'expired'
    finally:
        await client.aclose()


def message(**facts):
    return {'id': 'receipt-1', 'event_id': str(uuid4()), 'facts': {
        'watch_id': str(uuid4()), 'observation_id': str(uuid4()), 'sku': 'part',
        'page_id': hashlib.sha256(b'https://store.example/part').hexdigest(),
        'previous_price': '10', 'price': '12.50', 'currency': 'USD',
        'observed_at': NOW.isoformat(), **facts}}


@pytest.mark.asyncio
async def test_price_receipt_replay_is_durable_scoped_and_catalogue_bound(monkeypatch):
    received, settlements = [message()], []
    event_id = UUID(received[0]['event_id'])
    async def request(http, tenant, operation, body):
        assert tenant == TENANT and not administrative()
        if operation == 'receive':
            return {'messages': received}
        settlements.append(body)
        return {}
    monkeypatch.setattr(price_events, 'request', request)
    async with database() as (pool, scoped):
        for tenant in (TENANT, OTHER):
            await PgStore(pool).upsert_product(tenant, dict(sku='part', name='Fixture part',
                brand='Fixture', category='part', price='10', currency='USD', active=True,
                url='https://store.example/part'))
        service = Service(PgStore(scoped))
        with tenant_scope(TENANT):
            for _ in range(2):
                assert await price_events.consume_tenant(service, None, TENANT, 'worker') == 1
            # Rebound pages and unknown SKUs cannot write another product's history.
            for wrong in (message(page_id='wrong-page'), message(sku='missing')):
                await price_events.save_price(service, TENANT, wrong)
            received[:] = [message(price='NaN')]
            assert await price_events.consume_tenant(service, None, TENANT, 'worker') == 0
            # A crash before ACK replays the same event; a failed write settles as fail.
            assert [row['action'] for row in settlements] == ['ack', 'ack', 'fail']
        rows = await pool.fetch('SELECT tenant_id::text,price,event_id FROM agent_rig.price_history')
        assert len(rows) == 1 and rows[0]['tenant_id'] == TENANT and rows[0]['price'] == Decimal('12.50')
        assert rows[0]['event_id'] == event_id
        assert await pool.fetchval('SELECT count(*) FROM agent_rig.products WHERE price=10') == 2
        with tenant_scope(OTHER):
            assert await scoped.fetchval('SELECT count(*) FROM agent_rig.price_history') == 0


@pytest.mark.asyncio
async def test_price_loop_recovers_discovery_and_scopes_each_consumer(monkeypatch):
    discoveries, seen, ticks = [], [], []
    async def tenants():
        assert administrative()
        discoveries.append(True)
        if len(discoveries) == 1:
            raise OSError('offline discovery interruption')
        return [TENANT, OTHER]
    async def consume(service, http, tenant, consumer):
        assert not administrative()
        seen.append(tenant)
        if tenant == TENANT:
            raise OSError('offline bus interruption')
    async def sleep(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            raise asyncio.CancelledError
    monkeypatch.setattr(price_events, 'consume_tenant', consume)
    monkeypatch.setattr(price_events, 'asyncio', SimpleNamespace(sleep=sleep))
    with tenant_scope(None, administrative=True), pytest.raises(asyncio.CancelledError):
        await price_events.consume_loop(SimpleNamespace(store=SimpleNamespace(tenant_ids=tenants)), None)
    assert seen == [TENANT, OTHER] and ticks == [5, 5] and len(discoveries) == 2


@pytest.mark.asyncio
async def test_forge_retention_retries_and_preserves_owed_receipts(monkeypatch, tmp_path, caplog):
    from agents.rig.forge import retention, service
    monkeypatch.setattr(service, 'tasks', {})
    monkeypatch.setenv('FORGE_DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FORGE_RETENTION_SECONDS', '3600')
    calls, ticks = [], []
    finished = asyncio.Event()
    async def sleep(seconds):
        ticks.append(seconds)
        if len(ticks) > 2:
            finished.set()
            await asyncio.Future()
    def sweep(root, active):
        calls.append(True)
        if len(calls) == 2:
            raise OSError('private storage detail')
        retention.sweep(root, active, now=10000)
    monkeypatch.setattr(service, 'sweep', sweep)
    monkeypatch.setattr(service, 'asyncio', SimpleNamespace(
        sleep=sleep, create_task=asyncio.create_task, gather=asyncio.gather))
    async with service.lifespan(service.app):
        work = tmp_path / TENANT / str(uuid4())
        work.mkdir(parents=True)
        (work / 'request.json').write_text('{}')
        state = {'status': 'failed', 'finished_at': 0, 'receipts': [{'status': 'pending'}]}
        (work / 'state.json').write_text(json.dumps(state))
        (work / 'pending-receipt.json').write_text('{"receipt":"owed"}')
        (work / 'large-intermediate').write_bytes(b'fixture')
        await asyncio.wait_for(finished.wait(), 2)
        assert not (work / 'large-intermediate').exists()
        assert json.loads((work / 'pending-receipt.json').read_text()) == {'receipt': 'owed'}
        assert json.loads((work / 'state.json').read_text()) == state
    assert len(calls) == 3 and ticks == [60, 60, 60]
    assert 'Forge retention will retry.' in caplog.text and 'private' not in caplog.text
