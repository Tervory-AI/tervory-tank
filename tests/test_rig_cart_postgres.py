"""Cart state survives new objects and obeys the platform's actual forced RLS."""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

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
