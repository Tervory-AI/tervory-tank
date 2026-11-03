"""Offline watch acceptance: real disposable storage, fake DNS and fake scans."""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from test_radix_passive import (A, B, TARGET, FakeServer, database as database,
                               gateway, no_external_network as no_external_network,
                               routes, store, tools)
import passive_watch


@pytest.fixture(autouse=True)
def no_events(monkeypatch):
    from chassis import events
    monkeypatch.setattr(events, 'publish', AsyncMock(return_value=False))


def finding(rule, severity='low', target=TARGET):
    return tools.rule_text(tools.finding('zap', severity, rule, target),
                           f'Explanation for {rule}', f'Remediation for {rule}')


def executor(database, monkeypatch, scan):
    lease = gateway.Lease(database, server=FakeServer)
    async def request(req):
        import json
        from uuid import UUID
        payload = json.loads(req.content)
        args = UUID(payload['tenant_id']), UUID(payload['scan_id'])
        try:
            result = await (lease.start(*args) if req.url.path == '/lease' else lease.release(*args))
            return httpx.Response(200, json=result or {})
        except HTTPException as exc:
            return httpx.Response(exc.status_code, json={'detail': exc.detail})
    async def run(db, body, **kwargs):
        client = httpx.AsyncClient(transport=httpx.MockTransport(request))
        return await routes.execute(db, body, scanner=scan, http=client, **kwargs)
    return run


async def dns_for(database, monkeypatch):
    challenges = {}
    for tenant, domain in [(A, 'owned.example'), (B, 'other.example')]:
        challenges[domain] = (await database.issue(tenant, domain))['value']
    async def resolve(name, kind, **kwargs):
        assert kind == 'TXT'
        domain = name.removeprefix('_tervory-verify.')
        value = challenges.get(domain)
        if value is None:
            raise gateway.dns.resolver.NXDOMAIN
        return [SimpleNamespace(strings=(value.encode(),))]
    monkeypatch.setattr(gateway.dns.asyncresolver, 'resolve', resolve)
    return challenges


@pytest.mark.asyncio
@pytest.mark.parametrize('reason,value', [('txt_missing', None), ('txt_changed', 'different-public-proof')])
async def test_removed_or_changed_txt_stops_without_scanning(database, monkeypatch, reason, value):
    dns = await dns_for(database, monkeypatch)
    await database.watch(A, 'owned.example', 'weekly')
    dns['owned.example'] = value
    scan = AsyncMock(return_value=[])
    result = await passive_watch.tick(database.pool, execute_scan=executor(database, monkeypatch, scan))
    assert result == {'count': 0}
    scan.assert_not_awaited()
    watch = (await database.watches(A))[0]
    assert (watch['status'], watch['stop_reason']) == ('stopped', reason)
    assert await passive_watch.tick(database.pool, execute_scan=executor(database, monkeypatch, scan)) == {'count': 0}
    scan.assert_not_awaited()


@pytest.mark.asyncio
async def test_two_runs_persist_new_fixed_unchanged_and_current_rule_text(database, monkeypatch):
    await dns_for(database, monkeypatch)
    await database.watch(A, 'owned.example', 'weekly')
    scan = AsyncMock(side_effect=[[finding('fixed'), finding('same'), finding('severity')],
                                  [finding('new'), finding('same'), finding('severity', 'high')]])
    run = executor(database, monkeypatch, scan)
    first = await passive_watch.tick(database.pool, execute_scan=run)
    assert first['count'] == 1
    await database.watch(A, 'owned.example', 'weekly')
    second = await passive_watch.tick(database.pool, execute_scan=run)
    changed = await database.changes(A, 'owned.example')
    assert changed['scan_id'] == second['scan_id']
    assert changed['previous_scan_id'] == first['scan_id']
    assert {x['rule'] for x in changed['new']} == {'new', 'severity'}
    assert {x['rule'] for x in changed['fixed']} == {'fixed', 'severity'}
    assert {x['rule'] for x in changed['unchanged']} == {'same'}
    assert {x['rule'] for x in changed['findings']} == {'new', 'same', 'severity'}
    assert all(x['explanation'].startswith('Explanation') and x['remediation'].startswith('Remediation') for x in changed['findings'])
    assert changed['findings'] == await database.findings(A, __import__('uuid').UUID(second['scan_id']))
    # Restart does not recompute or lose historical classification.
    assert await store.Store(database.pool).changes(A, 'owned.example') == changed
    async with database.pool.acquire() as conn:
        assert await conn.fetchval("SELECT next_run > now()+interval '6 days' FROM agent_radix.passive_watches WHERE tenant_id=$1", A)
        assert await conn.fetchval('SELECT artifact FROM agent_radix.passive_scans WHERE tenant_id=$1 ORDER BY created_at DESC LIMIT 1', A) == store.watch_artifact('owned.example')


@pytest.mark.asyncio
async def test_watch_retains_challenge_after_one_day_but_still_checks_dns(database, monkeypatch):
    dns = await dns_for(database, monkeypatch)
    await database.watch(A, 'owned.example', 'daily')
    async with database.pool.acquire() as conn:
        await conn.execute("UPDATE agent_radix.passive_domains SET expires_at=now()-interval '2 days' WHERE tenant_id=$1", A)
    assert (await database.issue(A, 'owned.example'))['value'] == dns['owned.example']
    scan = AsyncMock(return_value=[])
    assert (await passive_watch.tick(database.pool, execute_scan=executor(database, monkeypatch, scan)))['count'] == 1
    assert scan.await_count == 1
    await database.watch(A, 'owned.example', 'daily')
    dns['owned.example'] = None
    await passive_watch.tick(database.pool, execute_scan=executor(database, monkeypatch, scan))
    assert scan.await_count == 1
    with pytest.raises(PermissionError):
        await database.create(A, TARGET, store.watch_artifact('owned.example'))


@pytest.mark.asyncio
async def test_concurrent_ticks_queue_one_scan_at_a_time(database, monkeypatch):
    await dns_for(database, monkeypatch)
    await database.watch(A, 'owned.example', 'daily')
    await database.watch(B, 'other.example', 'weekly')
    entered, release = asyncio.Event(), asyncio.Event()
    active = peak = 0
    targets = []
    async def scan(target, directory):
        nonlocal active, peak
        active += 1; peak = max(peak, active); targets.append(target)
        entered.set()
        await release.wait()
        active -= 1
        return []
    run = executor(database, monkeypatch, scan)
    first = asyncio.create_task(passive_watch.tick(database.pool, execute_scan=run))
    await asyncio.wait_for(entered.wait(), 5)
    assert await passive_watch.tick(database.pool, execute_scan=run) == {'queued': True}
    assert len(targets) == 1
    release.set()
    assert (await first)['count'] == 1
    assert (await passive_watch.tick(database.pool, execute_scan=run))['count'] == 1
    assert peak == 1 and targets == [TARGET, 'https://other.example/']


@pytest.mark.asyncio
async def test_manual_scan_busy_keeps_watch_queued_and_tenants_isolated(database, monkeypatch):
    await dns_for(database, monkeypatch)
    await database.watch(B, 'other.example', 'weekly')
    manual = await database.create(A, TARGET, store.watch_artifact('owned.example'))
    assert await database.running(A, manual)
    scan = AsyncMock(return_value=[])
    assert await passive_watch.tick(database.pool, execute_scan=executor(database, monkeypatch, scan)) == {'count': 0}
    scan.assert_not_awaited()
    assert (await database.watches(B))[0]['status'] == 'active'
    assert await database.watches(A) == []
    assert await database.changes(A, 'other.example') == {'status': 'pending'}
    await database.unwatch(A, 'other.example')
    assert (await database.watches(B))[0]['status'] == 'active'
    with pytest.raises(PermissionError):
        await database.watch(A, 'other.example', 'daily')
    await database.unwatch(B, 'other.example')
    assert (await database.watches(B))[0]['status'] == 'stopped'


@pytest.mark.asyncio
async def test_dns_timeout_retries_without_stopping(database, monkeypatch):
    await dns_for(database, monkeypatch)
    await database.watch(A, 'owned.example', 'weekly')
    async def timeout(*args, **kwargs):
        raise gateway.dns.exception.Timeout
    monkeypatch.setattr(gateway.dns.asyncresolver, 'resolve', timeout)
    scan = AsyncMock(return_value=[])
    await passive_watch.tick(database.pool, execute_scan=executor(database, monkeypatch, scan))
    scan.assert_not_awaited()
    watch = (await database.watches(A))[0]
    assert watch['status'] == 'active' and watch['stop_reason'] is None


def test_artifact_identifies_origin_and_compare_is_item_specific():
    import hashlib
    assert store.watch_artifact('owned.example') == 'sha256:' + hashlib.sha256(TARGET.encode()).hexdigest()
    result = store.compare_findings([finding('same', target='https://owned.example/a')],
                                    [finding('same', target='https://owned.example/b')])
    assert len(result['new']) == len(result['fixed']) == 1 and result['unchanged'] == []
