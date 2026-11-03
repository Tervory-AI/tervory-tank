"""Cart state survives new objects and obeys the platform's actual forced RLS."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/rig'))
sys.path.insert(0, str(ROOT / 'agents/_chassis'))
from chassis.tenant_db import TenantPool, tenant_scope
from rigbox.cart_store import CartStore
from rigbox.store import PgStore


@pytest.mark.asyncio
async def test_cart_durable_scoped_state_schema_twice_and_forced_rls():
    url = os.environ.get('RIG_TEST_DATABASE_URL')
    if not url:
        pytest.skip('RIG_TEST_DATABASE_URL explicitly enables throwaway Postgres')
    parts = urlsplit(url)
    name = 'rig_cart_' + uuid4().hex
    role = name + '_tenant'
    def dsn(database, user=None):
        authority = f'{user}@{parts.hostname}:{parts.port or 5432}' if user else parts.netloc
        return urlunsplit((parts.scheme, authority, '/' + database, '', ''))
    admin = await asyncpg.connect(dsn('postgres'))
    raw = owner = None
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
        await admin.execute(f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOBYPASSRLS')
        owner = await asyncpg.create_pool(dsn(name), min_size=1, max_size=2)
        store = PgStore(owner)
        await store.apply_schema()
        await store.apply_schema()
        async with owner.acquire() as conn:
            await conn.execute((ROOT / 'db/migrations/tenant_rls/agent_rig.sql').read_text())
            await conn.execute(f'GRANT USAGE ON SCHEMA agent_rig TO "{role}"')
            await conn.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA agent_rig TO "{role}"')
        raw = await asyncpg.create_pool(dsn(name, role), min_size=1, max_size=2)
        scoped = PgStore(TenantPool(raw))
        tenant, other = str(uuid4()), str(uuid4())
        with tenant_scope(tenant):
            rows = CartStore(scoped)
            async with rows.lock(tenant, 'co_same') as transaction:
                await transaction.put(tenant, 'co_same', {'id': 'co_same', 'state': 'pending'})
            # A fresh store object sees the committed state.
            assert (await CartStore(PgStore(TenantPool(raw))).get(tenant, 'co_same'))['state'] == 'pending'
            assert len(await rows.checkouts(tenant)) == 1
        with tenant_scope(other):
            assert await rows.get(tenant, 'co_same') is None
            assert await rows.checkouts(tenant) == []
            async with rows.lock(other, 'co_same') as transaction:
                await transaction.put(other, 'co_same', {'id': 'co_same', 'state': 'expired'})
            assert (await rows.get(other, 'co_same'))['state'] == 'expired'
        with tenant_scope(None):
            assert await rows.get(tenant, 'co_same') is None
    finally:
        if raw is not None:
            await raw.close()
        if owner is not None:
            await owner.close()
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()


@pytest.mark.asyncio
async def test_postgres_paid_cart_lease_concurrency_retry_and_quantity(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from rigbox.cart import Cart
    from rigbox.fulfilment import RigOrders
    from rigbox.quotes.senders import DeliveryError
    from test_rig_cart import setup, TENANT, OTHER, SESSION, NOW, signed
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database

    admin, name = _admin_url(), 'rig_cart_placeholder_' + uuid4().hex[:12]
    await _create_database(admin, name)
    pool = client = None
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=4)
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()
        memory, fake, config, _, clock, client = await setup(monkeypatch)
        for sku in ('stock', 'located', 'back'):
            await memory.add(TENANT, SESSION, sku, 2, back_order=sku == 'back')
        checkout = await memory.checkout(TENANT, SESSION)
        initial = await memory.rows.get(TENANT, checkout['id'])
        await store.put_retailer(TENANT, 'placeholder-store', None, None, locate_enabled=True)
        await store.save_commerce_config(TENANT, config)
        cart = Cart(SimpleNamespace(store=store), memory.platforms, clock=lambda: clock[0])
        await cart.rows.put(TENANT, initial['id'], initial)
        assert await cart.rows.get(OTHER, initial['id']) is None
        calls = []
        real = cart.fulfilment.place_located_order
        async def fail_after_insert(**kwargs):
            calls.append(kwargs['quote_id'])
            await real(**kwargs)
            raise DeliveryError('order_unavailable')
        cart.fulfilment.place_located_order = fail_after_insert
        fake.orders['1'].update(status='processing', date_paid=NOW.isoformat())
        raw = b'{"id":1}'
        await cart.webhook(TENANT, raw, signed(raw))
        pending = await cart.rows.get(TENANT, initial['id'])
        assert pending['state'] == 'paid_pending' and pending['attempt_id'] is None
        cart.fulfilment.place_located_order = real
        await asyncio.gather(cart.webhook(TENANT, raw, signed(raw)), cart.webhook(TENANT, raw, signed(raw)),
                             cart.order(TENANT, SESSION, initial['id']))
        result = await cart.order(TENANT, SESSION, initial['id'])
        assert result['state'] == 'placed'
        saved = await store.locate_order(TENANT, calls[0])
        assert saved['purchase_order']['quantity'] == 2
        assert (await cart.rows.get(TENANT, initial['id']))['lines'][2]['fulfilment_state'] == 'back_order'
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM agent_rig.locate_orders WHERE tenant_id=$1', UUID(TENANT)) == 1
            assert await conn.fetchval('SELECT count(*) FROM agent_rig.supplier_purchase_orders WHERE tenant_id=$1', UUID(TENANT)) == 1
        line = initial['lines'][1]
        await RigOrders(store).place_located_order(tenant_id=TENANT, quote_id='placeholder-quote-default',
            located=line['located'], price={'amount': line['price'], 'currency': 'USD'})
        assert (await store.locate_order(TENANT, 'placeholder-quote-default'))['purchase_order']['quantity'] == 1
        # A fresh object reads the same final state; stale CAS cannot undo it.
        assert not await CartStore(store).swap(TENANT, initial['id'], pending, initial)
        assert (await CartStore(store).get(TENANT, initial['id']))['state'] == 'placed'
    finally:
        if client is not None:
            await client.aclose()
        if pool is not None:
            await pool.close()
        await _drop_database(admin, name)
