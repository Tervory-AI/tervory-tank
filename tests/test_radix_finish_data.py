"""Real handlers and persistence, official baked advisories, fake external I/O."""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi.encoders import jsonable_encoder

from test_command import TENANT, OTHER, api as api, runtime as runtime, command_pool as command_pool
from test_command_radix_repo import repo_api as repo_api, upload, propose, JOB
import test_radix_finish_scanners as finish_scanners
scanner_reports = finish_scanners.reports
from test_rx1_scans import Ctx, FIXTURE, _dirty, _tar
from scanlib import orchestrate, runtime as scan_runtime, secrets
from test_radix_passive import database as database, A, B, FakeServer
from test_radix_finish_recovery import expire
from radix_i8.test_events import DOMAIN, TARGET, message, notice_browser
import passive_gateway
import passive_routes
import passive_r6
import passive_watch
import regulation_events

DEPENDENCY_SCAN = scan_runtime.dependency_scan


@pytest.mark.asyncio
@pytest.mark.parametrize('partial', [False, True])
async def test_production_reports_persist_and_deliver_private_zero_cost_receipts(
        repo_api, scanner_reports, monkeypatch, partial):
    client, pool, tank = repo_api
    monkeypatch.setattr(scan_runtime, 'dependency_scan', DEPENDENCY_SCAN)
    monkeypatch.setenv('RADIX_OSV_DIR', str(Path(os.environ['RADIX_OSV_REAL']).parent))
    scanner_reports['findings_json'] = json.dumps([{'RuleID': secrets.FIXTURE_RULE,
        'File': 'config.env', 'StartLine': 1, 'Secret': 'REDACTED', 'Match': 'REDACTED'}]).encode()
    scanner_reports['static'] = json.dumps({'results': [{
        'check_id': 'python-sql-format', 'path': 'app.py', 'start': {'line': 2},
        'extra': {'severity': 'ERROR', 'message': 'SQL is built with string formatting.'},
    }], 'errors': [{'type': 'ParseError'}] if partial else []}).encode()
    monkeypatch.setattr('radix_report.pdf_available', lambda: False)
    published = AsyncMock(return_value=True)
    monkeypatch.setattr('chassis.events.publish', published)
    await pool.execute('CREATE SCHEMA IF NOT EXISTS agent_radix')
    thread, attachment = await upload(client, _tar(_dirty()))
    jobs, launches = {}, []

    class Connection:
        def __init__(self, conn): self.conn = conn
        def __getattr__(self, name): return getattr(self.conn, name)
        async def close(self): await pool.release(self.conn)

    async def connect():
        return Connection(await pool.acquire())

    async def room(request):
        assert request.headers['x-tank-key'] == 'placeholder-room-auth'
        if request.method == 'POST':
            payload = json.loads(request.content)
            assert payload['tenant_id'] == payload['input']['tenant_id'] == str(TENANT)
            launches.append(payload)
            ctx = Ctx(payload['input']['source'], payload['input']['ref'], str(TENANT))
            ctx.job_id = str(JOB)
            result = await orchestrate.scan_job(ctx, connect=connect)
            jobs[str(JOB)] = {'id': str(JOB), 'tenant_id': str(TENANT),
                             'kind': 'scan', 'status': 'done', 'result': result}
            return httpx.Response(201, json={'id': str(JOB), 'tenant_id': str(TENANT),
                                            'kind': 'scan', 'status': 'queued'})
        if request.url.params.get('tenant_id') != str(TENANT) or '/jobs/' not in request.url.path:
            return httpx.Response(404, json={})
        return httpx.Response(200, json=jobs[str(JOB)])

    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as http:
        tank._http = http
        card = await propose(client, thread, 'radix.repo.scan', {'attachment_id': attachment})
        assert not launches
        confirmation = f"/v1/command/cards/{card['card_id']}"
        response = await client.post(confirmation, json={'action': 'confirm'})
        assert response.status_code == 200 and response.json()['status'] == 'confirmed', response.text
        await client.post(confirmation, json={'action': 'confirm'})
        assert len(launches) == 1
        for tool in ('radix.repo.findings', 'radix.report'):
            read = await propose(client, thread, tool, {'scan_id': str(JOB)})
            response = await client.post(f"/v1/command/cards/{read['card_id']}", json={'action': 'confirm'})
            assert response.status_code == 200 and response.json()['status'] == 'confirmed', response.text
            assert FIXTURE not in response.text
        scan = jobs[str(JOB)]['result']
        assert scan['scan_complete'] is (not partial) and scan['deploy_blocked']
        assert {f['tool'] for f in scan['findings']} == {'scan.secrets', 'scan.static', 'scan.dependencies'}
        assert any(f.get('advisory') == 'GHSA-8q59-q68h-6hv4' for f in scan['findings'])
        stored = await pool.fetch('SELECT * FROM agent_radix.findings WHERE tenant_id=$1 AND scan_id=$2', TENANT, JOB)
        assert len(stored) == len(scan['findings']) and FIXTURE not in str(stored)
        assert not await pool.fetchval('SELECT 1 FROM agent_radix.findings WHERE tenant_id=$1 AND scan_id=$2', OTHER, JOB)
        download = await client.get(f'/v1/command/radix/reports/{JOB}/html')
        assert download.status_code == 200 and download.text.count('<article>') == len(stored)
        assert ('<dd>failed</dd>' if partial else '<dd>complete</dd>') in download.text
        assert download.headers['cache-control'] == 'private, no-store'
        assert FIXTURE not in download.text
        assert (await client.get(f'/v1/command/radix/reports/{JOB}/html',
                                headers={'x-tervory-tenant': str(OTHER)})).status_code == 404
        receipts = await pool.fetch('SELECT task_type,model,cost_usd,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1', TENANT)
        assert len(receipts) == 3 and {r['task_type'] for r in receipts} == {'radix.repo.scan', 'radix.repo.findings', 'radix.report'}
        assert all(r['model'] == 'code' and r['cost_usd'] == r['tokens_in'] == r['tokens_out'] == 0 for r in receipts)
        snapshot = (await client.get(f'/v1/command/threads/{thread}')).json()
        assert len(snapshot['receipts']) == 3 and snapshot['thread']['spent_usd'] == 0
    assert published.await_count == len(jobs[str(JOB)]['result']['findings'])
    tank.run_route.assert_not_called()


@pytest.mark.asyncio
async def test_recovered_regulation_job_rechecks_dns_and_persists_actual_measurements(database, monkeypatch, tmp_path):
    proof = await database.issue(A, DOMAIN)
    await database.watch(A, DOMAIN, 'daily', run_now=False)
    event = message()
    await regulation_events.Queue(database.pool).enqueue(A, event)
    async with database.pool.acquire() as conn:
        ident = await conn.fetchval('SELECT scan_id FROM agent_radix.regulation_runs WHERE tenant_id=$1', A)
    assert await database.running(A, ident)
    await expire(database, ident)
    checks, requests = [], []
    async def dns(domain, challenge):
        assert domain == DOMAIN and challenge == proof['value']
        checks.append(domain)
        return True
    async def page(request):
        requests.append(str(request.url))
        return httpx.Response(200, headers={'content-type': 'text/html', 'set-cookie': 'placeholder=private-value; Path=/'},
                              text='<html><p>placeholder business page</p></html>')
    async def scanner(target, directory):
        return await passive_r6.collect_notices(target, directory, run=notice_browser,
                                               transport=httpx.MockTransport(page))
    lease = passive_gateway.Lease(database, check=dns, server=FakeServer)
    monkeypatch.setattr(passive_gateway, 'private_bind_address', lambda: '127.0.0.1')
    monkeypatch.setattr(passive_gateway.app.state, 'lease', lease, raising=False)
    monkeypatch.setattr('chassis.events.publish', AsyncMock(return_value=True))
    async def execute(store, body, **kwargs):
        assert kwargs['scanner'] is passive_r6.collect_notices
        http = httpx.AsyncClient(transport=httpx.ASGITransport(passive_gateway.app))
        return await passive_routes.execute(store, body, ident=kwargs['ident'], watched=True, scanner=scanner, http=http)
    original = regulation_events.run_queued
    async def run(pool, conn):
        return await original(pool, conn, execute_scan=execute)
    monkeypatch.setattr(regulation_events, 'run_queued', run)
    completed = await passive_watch.tick(database.pool)
    assert completed == {'count': 1, 'scan_id': str(ident)}
    assert checks == [DOMAIN] and requests == [TARGET] and lease.run is None
    report = await database.report(A, ident)
    assert report['status'] == 'complete'
    assert set(report['checks']) == {'page_load', 'notices', 'browser'}
    assert all(c['status'] == 'complete' for c in report['checks'].values())
    assert {f['rule'] for f in report['findings']} == {'missing-privacy-notice', 'cookie'}
    assert 'private-value' not in json.dumps(jsonable_encoder(report))
    with pytest.raises(LookupError):
        await database.report(B, ident)
    await regulation_events.Queue(database.pool).enqueue(A, event)
    assert (await passive_watch.tick(database.pool))['count'] == 0
    assert checks == [DOMAIN] and requests == [TARGET]


@pytest.mark.asyncio
async def test_recovery_uses_persisted_owner_with_enforced_tenant_policy(database):
    import asyncpg
    from chassis.tenant_db import TenantPool, tenant_scope
    from passive_store import Store
    from test_radix_finish_recovery import interrupted_week
    ident = await interrupted_week(database)
    async with database.pool.acquire() as conn:
        prior_security = await conn.fetchrow("SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='agent_radix.passive_scans'::regclass")
        await conn.execute("""DO $$ BEGIN CREATE ROLE radix_placeholder_finish NOLOGIN;
          EXCEPTION WHEN duplicate_object THEN NULL; END $$""")
        await conn.execute('GRANT USAGE ON SCHEMA agent_radix TO radix_placeholder_finish')
        await conn.execute('GRANT SELECT,UPDATE ON ALL TABLES IN SCHEMA agent_radix TO radix_placeholder_finish')
        await conn.execute('ALTER TABLE agent_radix.passive_scans ENABLE ROW LEVEL SECURITY')
        await conn.execute('ALTER TABLE agent_radix.passive_scans FORCE ROW LEVEL SECURITY')
        await conn.execute("""CREATE POLICY radix_finish_owner ON agent_radix.passive_scans
          USING(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)
          WITH CHECK(tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)""")
    async def setup(conn):
        await conn.execute('SET ROLE radix_placeholder_finish')
    raw = await asyncpg.create_pool(os.environ['RADIX_PASSIVE_TEST_DATABASE_URL'],
                                   setup=setup, min_size=1, max_size=2)
    scoped = TenantPool(raw, database.pool)
    try:
        with tenant_scope(B):
            await Store(scoped).reap_expired()
            async with scoped.acquire() as conn:
                assert not await conn.fetchval('SELECT 1 FROM agent_radix.passive_scans WHERE id=$1', ident)
        with tenant_scope(A):
            async with scoped.acquire() as conn:
                assert await conn.fetchval('SELECT status FROM agent_radix.passive_scans WHERE id=$1', ident) == 'pending'
    finally:
        await raw.close()
        async with database.pool.acquire() as conn:
            await conn.execute('DROP POLICY radix_finish_owner ON agent_radix.passive_scans')
            if not prior_security['relforcerowsecurity']:
                await conn.execute('ALTER TABLE agent_radix.passive_scans NO FORCE ROW LEVEL SECURITY')
            if not prior_security['relrowsecurity']:
                await conn.execute('ALTER TABLE agent_radix.passive_scans DISABLE ROW LEVEL SECURITY')
