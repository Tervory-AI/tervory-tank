"""Durable weekly passive/infra pairs with real scheduler locks and fake scans."""
import asyncio

import pytest
from fastapi import HTTPException

from test_radix_passive import database as database,FakeServer,A,B
from chassis.tenant_db import tenant_scope
from passive_store import watch_artifact
import passive_gateway
import passive_watch
import passive_weekly

DOMAIN='placeholder.example'


async def due(database,tenant=A,domain=DOMAIN):
    async with database.pool.acquire() as conn:
        await conn.execute("UPDATE agent_radix.weekly_domains SET next_run=now()-interval '1 second' WHERE tenant_id=$1 AND domain=$2",tenant,domain)
        await conn.execute("UPDATE agent_radix.passive_domains SET expires_at=now()-interval '1 day' WHERE tenant_id=$1 AND domain=$2",tenant,domain)


@pytest.mark.asyncio
async def test_durable_pair_once_per_week_expired_challenge_and_scheduler_lock(database,monkeypatch):
    monkeypatch.setattr(passive_gateway,'private_bind_address',lambda:'127.0.0.1')
    await database.issue(A,DOMAIN)
    await database.consent(A,DOMAIN,'placeholder-admin','placeholder consent')
    await due(database)
    # Queue/advance before execution simulates a restart after transaction commit.
    with tenant_scope(A):
        assert await passive_weekly.queue(database.pool,A,DOMAIN)
        assert await passive_weekly.queue(database.pool,A,DOMAIN) is None
    async with database.pool.acquire() as conn:
        rows=await conn.fetch('SELECT * FROM agent_radix.weekly_runs WHERE tenant_id=$1 ORDER BY kind',A)
        assert len(rows)==2 and {r['kind'] for r in rows}=={'passive','infra'}
        assert len({r['period'] for r in rows})==1
    steps=[];running=0;maximum=0
    async def proof(domain,challenge):steps.append('proof:'+domain);return True
    lease=passive_gateway.Lease(database,check=proof,server=FakeServer)
    async def fake(store,tenant,ident,infra):
        nonlocal running,maximum
        await lease.start(tenant,ident,active=infra,infra=infra)
        running+=1;maximum=max(maximum,running);steps.append('infra' if infra else 'passive')
        await asyncio.sleep(.05)
        await store.complete(tenant,ident,[],measurements={'checks':{'active':{'status':'complete'}}} if infra else None)
        running-=1;await lease.release(tenant,ident)
        return {'scan_id':str(ident)}
    async def passive(store,body,**kwargs):return await fake(store,body.tenant_id,kwargs['ident'],False)
    async def infra(store,tenant,target,**kwargs):
        assert kwargs['client'] is True
        return await fake(store,tenant,kwargs['ident'],True)
    real=passive_weekly.tick
    async def tick(pool,conn):return await real(pool,conn,execute_passive=passive,execute_infra=infra)
    monkeypatch.setattr(passive_weekly,'tick',tick)
    results=await asyncio.gather(passive_watch.tick(database.pool),passive_watch.tick(database.pool))
    assert sum(result.get('count',0) for result in results)==1
    assert (await passive_watch.tick(database.pool))['kind']=='infra'
    assert (await passive_watch.tick(database.pool))['count']==0
    assert steps==['proof:'+DOMAIN,'passive','proof:'+DOMAIN,'infra'] and maximum==1
    async with database.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_radix.weekly_runs WHERE tenant_id=$1',A)==2
        assert await conn.fetchval("SELECT next_run>now()+interval '6 days' FROM agent_radix.weekly_domains WHERE tenant_id=$1 AND domain=$2",A,DOMAIN)


@pytest.mark.asyncio
async def test_withdrawal_cancels_queued_week_and_no_consent_never_enrolls(database):
    await database.issue(A,DOMAIN);await database.issue(B,DOMAIN)
    async with database.pool.acquire() as conn:
        assert not await conn.fetchval('SELECT 1 FROM agent_radix.weekly_domains WHERE tenant_id=$1',A)
    await database.consent(A,DOMAIN,'placeholder-admin','placeholder written consent')
    await due(database)
    with tenant_scope(A):await passive_weekly.queue(database.pool,A,DOMAIN)
    await database.withdraw_consent(A,DOMAIN,'placeholder-admin')
    for _ in range(3):await passive_watch.tick(database.pool)
    async with database.pool.acquire() as conn:
        assert not await conn.fetchval('SELECT 1 FROM agent_radix.weekly_domains WHERE tenant_id=$1',B)
        assert await conn.fetchval("SELECT count(*) FROM agent_radix.passive_scans WHERE tenant_id=$1 AND status='error'",A)==2
        assert not await conn.fetchval('SELECT enabled FROM agent_radix.weekly_domains WHERE tenant_id=$1 AND domain=$2',A,DOMAIN)


@pytest.mark.asyncio
async def test_own_list_weekly_and_txt_loss_prevents_any_scanner(database,monkeypatch):
    monkeypatch.setattr(passive_gateway,'private_bind_address',lambda:'127.0.0.1')
    await database.issue(A,'tervory.com',own=True)
    await database.issue(B,DOMAIN,own=True)
    await due(database,domain='tervory.com')
    with tenant_scope(A):await passive_weekly.queue(database.pool,A,'tervory.com')
    async def missing(*args):return False
    lease=passive_gateway.Lease(database,check=missing,server=FakeServer)
    async with database.pool.acquire() as conn:
        assert not await conn.fetchval('SELECT 1 FROM agent_radix.weekly_domains WHERE tenant_id=$1',B)
        ident=await conn.fetchval("SELECT scan_id FROM agent_radix.weekly_runs WHERE tenant_id=$1 AND kind='passive'",A)
    with pytest.raises(HTTPException) as error:await lease.start(A,ident)
    assert error.value.status_code==403 and lease.proxy_server is None
    async with database.pool.acquire() as conn:
        assert not await conn.fetchval('SELECT enabled FROM agent_radix.weekly_domains WHERE tenant_id=$1',A)


@pytest.mark.asyncio
async def test_manual_scan_delays_durable_week_without_overlapping(database,monkeypatch):
    monkeypatch.setattr(passive_gateway,'private_bind_address',lambda:'127.0.0.1')
    await database.issue(A,DOMAIN)
    await database.consent(A,DOMAIN,'placeholder-admin','placeholder consent')
    ident=await database.create(A,'https://'+DOMAIN+'/',watch_artifact(DOMAIN))
    async def yes(*args):return True
    lease=passive_gateway.Lease(database,check=yes,server=FakeServer)
    await lease.start(A,ident)
    await due(database)
    assert (await passive_watch.tick(database.pool))['queued']
    async with database.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM agent_radix.passive_scans WHERE status='running'")==1
        assert await conn.fetchval('SELECT count(*) FROM agent_radix.weekly_runs WHERE tenant_id=$1',A)==2
    await lease.release(A,ident)


@pytest.mark.asyncio
async def test_reissue_preserves_weekly_proof_but_renews_manual_expiry(database):
    from datetime import datetime,timezone
    original=await database.issue(A,DOMAIN)
    await database.consent(A,DOMAIN,'placeholder-admin','placeholder consent')
    await due(database)
    renewed=await database.issue(A,DOMAIN)
    assert renewed['value']==original['value']
    assert datetime.fromisoformat(renewed['expires_at'])>datetime.now(timezone.utc)
