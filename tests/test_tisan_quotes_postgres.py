"""Optional real SQL/RLS checks, only on an explicitly selected local test port.

Run against a fresh disposable trust-auth PostgreSQL container. No production
connection setting or credential is read. The test creates a temporary database
and removes it after each test.
"""
import asyncio
import os
import sys
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from test_tisan_quotes import A, B, DATA, ROOT, q

sys.path.insert(0, str(ROOT / 'agents/_chassis'))
from chassis.tenant_db import TenantPool, tenant_scope


@pytest_asyncio.fixture
async def database():
    port = os.environ.get('J4_TEST_POSTGRES_PORT')
    if not port:
        pytest.skip('J4_TEST_POSTGRES_PORT must select a disposable local PostgreSQL')
    options = dict(host='127.0.0.1', port=int(port), user='postgres', ssl=False)
    admin = await asyncpg.connect(database='postgres', **options)
    name = 'tisan_j4_test_' + uuid4().hex
    await admin.execute(f'CREATE DATABASE {name}')
    conn = await asyncpg.connect(database=name, **options)
    await conn.execute('CREATE SCHEMA agent_tisan')
    schema = (ROOT / 'agents/tisan/schema.sql').read_text()
    # The platform RLS rollout marker: quote RLS follows tank.command_threads.
    await conn.execute('CREATE SCHEMA tank; CREATE TABLE tank.command_threads (id uuid); '
                       'ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    # Bootstrap DDL before room-role provisioning, as the all-schema RLS fixture
    # does. Installing a schema must not create a login or weaken its policies.
    existed = await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agent_tisan')")
    await conn.execute(schema)
    assert await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agent_tisan')") == existed
    assert await conn.fetchval("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='agent_tisan' AND c.relname IN ('quote_requests','quote_events') AND c.relrowsecurity AND c.relforcerowsecurity") == 2
    await conn.execute("DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='agent_tisan') THEN CREATE ROLE agent_tisan NOLOGIN; END IF; END $$")
    await conn.execute('GRANT USAGE ON SCHEMA agent_tisan TO agent_tisan')
    # Reapply after provisioning: same production grants, no PUBLIC grant.
    await conn.execute(schema)
    assert await conn.fetchval("SELECT has_table_privilege('agent_tisan','agent_tisan.quote_requests','SELECT,INSERT,UPDATE')")
    assert await conn.fetchval("SELECT has_table_privilege('agent_tisan','agent_tisan.quote_events','SELECT,INSERT')")
    assert await conn.fetchval("SELECT has_sequence_privilege('agent_tisan','agent_tisan.quote_events_id_seq','USAGE,SELECT')")

    async def room_role(connection):
        await connection.execute('SET ROLE agent_tisan')
    raw = await asyncpg.create_pool(database=name, min_size=1, max_size=4, init=room_role, **options)
    try:
        yield q.Quotes(TenantPool(raw)), conn, raw
    finally:
        await raw.close()
        await conn.close()
        await admin.execute(f'DROP DATABASE {name}')
        await admin.close()


@pytest.mark.asyncio
async def test_real_schema_audit_isolation_and_all_moves(database):
    store, admin, raw = database
    with tenant_scope(A):
        row = await store.create(A, 'requester', DATA, submitted=True)
        for target in ('acknowledged', 'quoted', 'declined'):
            await store.move(A, row['id'], 'store-actor', target)
        result = await store.read(A, row['id'])
        assert [e['to_state'] for e in result['events']] == ['draft', 'submitted', 'acknowledged', 'quoted', 'declined']
        assert all(e['happened_at'].tzinfo for e in result['events'])
        with pytest.raises(q.Refused):
            await store.move(A, row['id'], 'store-actor', 'accepted')
    with tenant_scope(B):
        assert await store.list(B) == []
        with pytest.raises(q.Missing):
            await store.read(B, row['id'])
        with pytest.raises(q.Missing):
            await store.move(B, row['id'], 'other', 'acknowledged')
        async with store.pool.acquire() as conn:
            # Deliberately unqualified SQL: RLS still hides A's request and events.
            assert await conn.fetchval('SELECT count(*) FROM agent_tisan.quote_requests') == 0
            assert await conn.fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 0
    assert await admin.fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 5


@pytest.mark.asyncio
async def test_concurrent_state_moves_have_one_winner(database):
    store, _, _ = database
    with tenant_scope(A):
        row = await store.create(A, 'requester', DATA, submitted=True)
        results = await asyncio.gather(
            store.move(A, row['id'], 'actor-one', 'acknowledged'),
            store.move(A, row['id'], 'actor-two', 'acknowledged'), return_exceptions=True)
        assert sum(isinstance(r, q.Refused) for r in results) == 1
        assert sum(isinstance(r, dict) for r in results) == 1
        assert len((await store.read(A, row['id']))['events']) == 3


@pytest.mark.asyncio
async def test_event_failure_rolls_back_state_and_initial_event_constraint(database):
    store, admin, _ = database
    with tenant_scope(A):
        row = await store.create(A, 'requester', DATA, submitted=True)
        # Local test database only: force the real event INSERT to fail.
        await admin.execute("ALTER TABLE agent_tisan.quote_events ADD CONSTRAINT test_no_ack CHECK (to_state <> 'acknowledged')")
        with pytest.raises(asyncpg.CheckViolationError):
            await store.move(A, row['id'], 'store-actor', 'acknowledged')
        assert (await store.read(A, row['id']))['state'] == 'submitted'
        with pytest.raises(asyncpg.CheckViolationError):
            await admin.execute("INSERT INTO agent_tisan.quote_events (tenant_id,request_id,from_state,to_state,actor) VALUES ($1,$2,NULL,'accepted','test')", A, row['id'])


@pytest.mark.asyncio
async def test_quote_rls_stays_off_before_the_platform_rollout():
    """1 Nov 2026: an unconditional ENABLE made Tank refuse to start. Without the
    rollout marker the schema leaves RLS off, and turns it off where it was on."""
    port = os.environ.get('J4_TEST_POSTGRES_PORT')
    if not port:
        pytest.skip('J4_TEST_POSTGRES_PORT must select a disposable local PostgreSQL')
    options = dict(host='127.0.0.1', port=int(port), user='postgres', ssl=False)
    admin = await asyncpg.connect(database='postgres', **options)
    name = 'tisan_j4_norls_' + uuid4().hex
    await admin.execute(f'CREATE DATABASE {name}')
    conn = await asyncpg.connect(database=name, **options)
    try:
        await conn.execute('CREATE SCHEMA agent_tisan')
        schema = (ROOT / 'agents/tisan/schema.sql').read_text()
        await conn.execute(schema)
        on = ("SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
              "WHERE n.nspname='agent_tisan' AND c.relname IN ('quote_requests','quote_events') "
              "AND (c.relrowsecurity OR c.relforcerowsecurity)")
        assert await conn.fetchval(on) == 0
        await conn.execute('ALTER TABLE agent_tisan.quote_requests ENABLE ROW LEVEL SECURITY; '
                           'ALTER TABLE agent_tisan.quote_requests FORCE ROW LEVEL SECURITY')
        await conn.execute(schema)
        assert await conn.fetchval(on) == 0
    finally:
        await conn.close()
        await admin.execute(f'DROP DATABASE {name}')
        await admin.close()


@pytest.mark.asyncio
@pytest.mark.parametrize('rollout_on', [False, True])
async def test_schema_reapplies_as_provisioned_room_without_tank_access(rollout_on):
    """The room owns its tables but cannot resolve names inside Tank's schema."""
    from chassis.roles import apply_roles

    port = os.environ.get('J4_TEST_POSTGRES_PORT')
    if not port:
        pytest.skip('J4_TEST_POSTGRES_PORT must select a disposable local PostgreSQL')
    options = dict(host='127.0.0.1', port=int(port), user='postgres', ssl=False)
    admin = await asyncpg.connect(database='postgres', **options)
    name = 'tisan_j4_owner_' + uuid4().hex
    await admin.execute(f'CREATE DATABASE {name}')
    conn = await asyncpg.connect(database=name, **options)
    try:
        await conn.execute('CREATE SCHEMA tank; CREATE TABLE tank.command_threads (id uuid)')
        if rollout_on:
            await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        await conn.execute('CREATE SCHEMA agent_tisan')
        schema = (ROOT / 'agents/tisan/schema.sql').read_text()
        await conn.execute(schema)
        # Reproduce #564's accidentally enabled state on BOTH quote tables.
        await conn.execute('ALTER TABLE agent_tisan.quote_requests ENABLE ROW LEVEL SECURITY; '
                           'ALTER TABLE agent_tisan.quote_requests FORCE ROW LEVEL SECURITY; '
                           'ALTER TABLE agent_tisan.quote_events ENABLE ROW LEVEL SECURITY; '
                           'ALTER TABLE agent_tisan.quote_events FORCE ROW LEVEL SECURITY')
        await apply_roles(conn, {'AGENT_DB_PASSWORD_TISAN': 'disposable-test-password'})
        await conn.execute('SET ROLE agent_tisan')
        assert not await conn.fetchval("SELECT has_schema_privilege(current_user,'tank','USAGE')")
        await conn.execute(schema)
        await conn.execute(schema)
        rows = await conn.fetch(
            "SELECT c.relrowsecurity,c.relforcerowsecurity FROM pg_class c "
            "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='agent_tisan' "
            "AND c.relname IN ('quote_requests','quote_events')")
        assert len(rows) == 2
        assert all(row['relrowsecurity'] == rollout_on and
                   row['relforcerowsecurity'] == rollout_on for row in rows)
    finally:
        await conn.execute('RESET ROLE')
        await conn.close()
        await admin.execute(f'DROP DATABASE {name}')
        await admin.close()
