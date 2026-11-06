"""Crash recovery with real local persistence and fake DNS/scanners."""
import pytest

from test_radix_passive import database as database, A, B, FakeServer
from test_radix_weekly import DOMAIN, due
from chassis.tenant_db import tenant_scope
from passive_store import Store
import passive_gateway
import passive_watch
import passive_weekly
import regulation_events
from radix_i8.test_events import message


async def interrupted_week(database):
    await database.issue(A, DOMAIN)
    await database.consent(A, DOMAIN, 'placeholder-admin', 'placeholder consent')
    await due(database)
    with tenant_scope(A):
        await passive_weekly.queue(database.pool, A, DOMAIN)
    async with database.pool.acquire() as conn:
        ident = await conn.fetchval("SELECT scan_id FROM agent_radix.weekly_runs WHERE tenant_id=$1 AND kind='passive'", A)
    assert await database.running(A, ident)
    await expire(database, ident)
    return ident


async def expire(database, ident):
    async with database.pool.acquire() as conn:
        await conn.execute("UPDATE agent_radix.passive_scans SET lease_until=now()-interval '1 second' WHERE tenant_id=$1 AND id=$2", A, ident)


@pytest.mark.asyncio
@pytest.mark.parametrize('maintenance', ['gateway', 'scheduler'])
async def test_expired_weekly_pair_resumes_same_ids_after_restart(database, monkeypatch, maintenance):
    ident = await interrupted_week(database)
    restarted = Store(database.pool)
    if maintenance == 'gateway':
        await restarted.reap_expired()
    proofs = []
    async def proof(domain, challenge):
        proofs.append((domain, challenge))
        return True
    monkeypatch.setattr(passive_gateway, 'private_bind_address', lambda: '127.0.0.1')
    lease = passive_gateway.Lease(restarted, check=proof, server=FakeServer)

    async def finish(store, tenant, scan, infra=False):
        await lease.start(tenant, scan, active=infra, infra=infra)
        await store.complete(tenant, scan, [])
        await lease.release(tenant, scan)
        return {'scan_id': str(scan)}

    async def passive(store, body, **kwargs):
        return await finish(store, body.tenant_id, kwargs['ident'])
    async def infra(store, tenant, target, **kwargs):
        assert kwargs['client'] is True
        return await finish(store, tenant, kwargs['ident'], infra=True)
    original = passive_weekly.tick
    async def tick(pool, conn):
        return await original(pool, conn, execute_passive=passive, execute_infra=infra)
    monkeypatch.setattr(passive_weekly, 'tick', tick)
    first = await passive_watch.tick(database.pool)
    assert first['scan_id'] == str(ident) and first['kind'] == 'passive'
    assert (await passive_watch.tick(database.pool))['kind'] == 'infra'
    assert (await passive_watch.tick(database.pool))['count'] == 0
    assert len(proofs) == 2 and all(domain == DOMAIN for domain, _ in proofs)
    async with database.pool.acquire() as conn:
        rows = await conn.fetch('SELECT id,status FROM agent_radix.passive_scans WHERE tenant_id=$1', A)
        assert len(rows) == 2 and all(row['status'] == 'complete' for row in rows)
        assert ident in {row['id'] for row in rows}
        assert not await conn.fetchval('SELECT 1 FROM agent_radix.passive_scans WHERE tenant_id=$1', B)


@pytest.mark.asyncio
async def test_recovery_never_revives_withdrawn_consent(database, monkeypatch):
    await interrupted_week(database)
    await database.withdraw_consent(A, DOMAIN, 'placeholder-admin')
    calls = []
    async def forbidden(*args, **kwargs):
        calls.append(args)
        raise AssertionError('withdrawn consent reached scanner')
    original = passive_weekly.tick
    async def tick(pool, conn):
        return await original(pool, conn, execute_passive=forbidden, execute_infra=forbidden)
    monkeypatch.setattr(passive_weekly, 'tick', tick)
    for _ in range(3):
        assert (await passive_watch.tick(database.pool)).get('count', 0) == 0
    assert calls == []
    async with database.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM agent_radix.passive_scans WHERE status='error'") == 2


@pytest.mark.asyncio
async def test_expiry_is_rechecked_after_administrative_discovery(database):
    ident = await interrupted_week(database)
    class Discovery:
        async def fetch(self, query):
            async with database.pool.acquire() as conn:
                rows = await conn.fetch(query)
                await conn.execute("UPDATE agent_radix.passive_scans SET lease_until=now()+interval '1 minute' WHERE tenant_id=$1 AND id=$2", A, ident)
            return rows
    await database.reap_expired(discovery=Discovery())
    async with database.pool.acquire() as conn:
        assert await conn.fetchval('SELECT status FROM agent_radix.passive_scans WHERE tenant_id=$1 AND id=$2', A, ident) == 'running'


@pytest.mark.asyncio
async def test_expired_regulation_run_resumes_and_settles_once(database, monkeypatch):
    await database.issue(A, DOMAIN)
    await database.watch(A, DOMAIN, 'daily', run_now=False)
    delivery = message()
    await regulation_events.Queue(database.pool).enqueue(A, delivery)
    async with database.pool.acquire() as conn:
        ident = await conn.fetchval('SELECT scan_id FROM agent_radix.regulation_runs WHERE tenant_id=$1', A)
    assert await database.running(A, ident)
    await expire(database, ident)
    calls = []
    async def execute(store, body, **kwargs):
        from passive_r6 import collect_notices
        assert kwargs['scanner'] is collect_notices and kwargs['ident'] == ident
        assert body.tenant_id == A
        calls.append(ident)
        assert await store.running(A, ident)
        await store.complete(A, ident, [])
        return {'scan_id': str(ident)}
    original = regulation_events.run_queued
    async def run(pool, conn):
        return await original(pool, conn, execute_scan=execute)
    monkeypatch.setattr(regulation_events, 'run_queued', run)
    assert (await passive_watch.tick(database.pool))['scan_id'] == str(ident)
    await regulation_events.Queue(database.pool).enqueue(A, delivery)
    assert (await passive_watch.tick(database.pool))['count'] == 0
    assert calls == [ident]
    async with database.pool.acquire() as conn:
        rows = await conn.fetch('SELECT settled,scan_id FROM agent_radix.regulation_runs WHERE tenant_id=$1', A)
        assert len(rows) == 1 and rows[0]['settled'] and rows[0]['scan_id'] == ident
