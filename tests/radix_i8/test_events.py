"""Offline I8: fake HTTP/bus plus an opt-in disposable loopback database."""
import json
import os
from pathlib import Path
import sys
from uuid import UUID, uuid4

import asyncpg
from fastapi import FastAPI, HTTPException
import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'agents/radix'), str(ROOT / 'agents/_chassis'), str(ROOT / 'tank')]
import regulation_events as events
import passive_r6 as notices
import passive_routes as routes
from passive_store import DDL, Store, watch_artifact
import passive_watch
import event_bus

A = UUID('11111111-1111-4111-8111-111111111111')
B = UUID('22222222-2222-4222-8222-222222222222')
DOMAIN = 'placeholder.example'
TARGET = 'https://placeholder.example/'
FACTS = {'source': 'eur-lex', 'document_id': 'placeholder-law', 'date': '2026-11-03',
         'link': 'https://eur-lex.europa.eu/placeholder'}


def message(facts=None):
    return {'id': '1-0', 'event_id': str(uuid4()), 'facts': FACTS.copy() if facts is None else facts}


@pytest.mark.parametrize('value', [FACTS, {'document_id': 'a'*64, 'version_id': 'b'*64}])
def test_both_bus_shapes(value):
    assert events.facts(value) == event_bus.FACTS[events.EVENT].model_validate(value).model_dump(mode='json')


@pytest.mark.parametrize('value', [None, {}, {'tenant_id': str(B), **FACTS},
    {**FACTS, 'source': 'placeholder'}, {**FACTS, 'link': 'https://placeholder.example/'},
    {**FACTS, 'date': 'placeholder'}, {**FACTS, 'link': FACTS['link']+'?token=placeholder'},
    {'document_id': 'placeholder', 'version_id': 'placeholder'}])
def test_malformed_facts_refused(value):
    with pytest.raises((ValueError, TypeError)):
        events.facts(value)


@pytest.mark.asyncio
async def test_consumer_ack_only_after_queue_and_fail_errors(monkeypatch):
    calls = []
    msg = message()
    class Queue:
        async def tenant_ids(self): return [str(A)]
        async def enqueue(self, tenant, item):
            assert tenant == A and item is msg
            calls.append('queued')
    async def request(http, tenant, operation, body):
        assert tenant == str(A)
        calls.append((operation, body.copy()))
        return {'messages': [msg]} if operation == 'receive' else {'settled': 1}
    monkeypatch.setattr(events, 'request', request)
    assert await events.consume_tenant(Queue(), None, A, str(uuid4())) == 1
    assert calls[1] == 'queued' and calls[-1][1]['action'] == 'ack'
    calls.clear()
    assert await events.consume_tenant(Queue(), None, B, str(uuid4())) == 0
    assert calls == []
    class Broken(Queue):
        async def enqueue(self, *args): raise ValueError('placeholder')
    assert await events.consume_tenant(Broken(), None, A, str(uuid4())) == 0
    assert calls[-1][1]['action'] == 'fail'


async def notice_browser(argv, directory, seconds):
    assert argv[0] == '/usr/bin/node' and argv[-1] == 'notice-only'
    return 0, json.dumps({'findings': [], 'cookies': [{'name':'placeholder', 'domain':DOMAIN,
        'path':'/', 'expiry':-1, 'Secure':False, 'HttpOnly':False, 'SameSite':'Lax', 'first_party':True}],
        'third_party_refused':0, 'client_refused':0}).encode(), b''


@pytest.mark.asyncio
async def test_notice_cookie_rules_use_fake_page_and_no_other_checks(tmp_path):
    seen = []
    async def page(request):
        seen.append(str(request.url))
        return httpx.Response(200, headers={'content-type': 'text/html',
            'set-cookie': 'placeholder=placeholder; Path=/'}, text='<html><p>placeholder</p></html>')
    result = await notices.collect_notices(TARGET, tmp_path, run=notice_browser, transport=httpx.MockTransport(page))
    findings = result['findings']
    assert seen == [TARGET]
    assert {f['rule'] for f in findings} == {'missing-privacy-notice', 'cookie'}
    assert all(f['file'] == TARGET for f in findings)
    assert set(result['checks']) == {'page_load','notices','browser'}
    assert all(v['status']=='complete' for v in result['checks'].values())
    cookie = next(f for f in findings if f['rule']=='cookie')
    assert cookie['facts']['Secure'] is False and cookie['facts']['HttpOnly'] is False
    assert cookie['facts']['SameSite']=='Lax' and 'value' not in cookie['facts']
    notice = next(f for f in findings if f['rule']=='missing-privacy-notice')
    assert 'explanation' in json.loads(notice['fix'])[notice['rule']]
    assert 'placeholder=placeholder' not in json.dumps(findings)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('status,headers,body', [
    (302, {'location': 'https://other-placeholder.example/'}, ''),
    (200, {'content-type': 'text/html'}, 'placeholder' * 100001),
    (200, {'content-type': 'application/json'}, '{}'),
])
async def test_incomplete_not_passed(status, headers, body, tmp_path):
    async def page(request): return httpx.Response(status, headers=headers, text=body)
    result = await notices.collect_notices(TARGET, tmp_path, run=notice_browser, transport=httpx.MockTransport(page))
    assert result['checks']['page_load']['status']=='partial'
    assert result['checks']['notices']['status']=='partial'
    assert any(f['rule']=='partial' for f in result['findings'])


@pytest.mark.asyncio
async def test_proxy_is_mandatory_for_production_client(monkeypatch, tmp_path):
    class Client:
        def __init__(self, **kwargs):
            assert kwargs['proxy'] == 'http://radix-passive-proxy:8082'
            assert kwargs['trust_env'] is False and kwargs['follow_redirects'] is False
            raise RuntimeError('placeholder-stop-before-network')
    monkeypatch.setattr(notices.httpx, 'AsyncClient', Client)
    with pytest.raises(RuntimeError):
        await notices.collect_notices(TARGET, tmp_path)


@pytest.mark.asyncio
async def test_txt_failure_runs_no_notice_scanner(tmp_path):
    called = []
    class FakeStore:
        async def fail(self, *args): called.append('failed')
    async def scanner(*args): raise AssertionError('scanner ran without proof')
    async def gateway(request):
        called.append(request.url.path)
        return httpx.Response(403 if request.url.path == '/lease' else 200, json={})
    client = httpx.AsyncClient(transport=httpx.MockTransport(gateway))
    with pytest.raises(HTTPException) as exc:
        await routes.execute(FakeStore(), routes.Scan(tenant_id=A, target=TARGET,
            artifact=watch_artifact(DOMAIN)), ident=uuid4(), scanner=scanner, http=client)
    assert exc.value.status_code == 403
    assert called == ['/lease', 'failed', '/release']


@pytest.mark.asyncio
async def test_http_corridor_all_room_event_pairs(monkeypatch):
    app = FastAPI()
    app.include_router(event_bus.router)
    accepted = []
    class Bus:
        async def receive(self, actor, event, consumer):
            accepted.append((actor.agent, event)); return []
        async def settle(self, actor, event, *args):
            accepted.append((actor.agent, event)); return 1
    monkeypatch.setattr(event_bus, 'bus', lambda: Bus())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        for room in {*event_bus.EVENTS.values(), 'rig'}:
            for event in event_bus.EVENTS:
                async def identity(room=room): return event_bus.Scope(A, room, 'us-east')
                app.dependency_overrides[event_bus.identity] = identity
                body = {'event': event, 'consumer': str(uuid4())}
                allowed = (room, event) in {('rig','tiger.price.changed'), ('radix',events.EVENT)}
                for path in ('receive', 'settle'):
                    payload = body if path == 'receive' else {**body, 'id': '1-0', 'action': 'ack'}
                    response = await client.post('/v1/events/'+path, json=payload)
                    assert response.status_code == (200 if allowed else
                        403 if event in {'tiger.price.changed', events.EVENT} else 422)
    assert set(accepted) == {('rig','tiger.price.changed'), ('radix',events.EVENT)}


@pytest_asyncio.fixture
async def pool():
    url = os.environ.get('RADIX_I8_TEST_DATABASE_URL')
    if not url:
        pytest.skip('set RADIX_I8_TEST_DATABASE_URL to a disposable loopback database')
    from urllib.parse import urlsplit
    assert urlsplit(url).hostname == '127.0.0.1' and urlsplit(url).path == '/radix_passive_test'
    pool = await asyncpg.create_pool(url, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_radix')
        schema = (ROOT / 'agents/radix/schema.sql').read_text()
        await conn.execute(schema)
        await conn.execute(DDL)
        await conn.execute(schema)
        await conn.execute(DDL)
        await conn.execute('TRUNCATE agent_radix.page_hashes,agent_radix.regulation_runs,agent_radix.passive_scans,agent_radix.passive_domains CASCADE')
    try: yield pool
    finally: await pool.close()


async def watched(pool, tenant=A, domain=DOMAIN):
    store = Store(pool)
    await store.issue(tenant, domain)
    await store.watch(tenant, domain, 'daily')
    return store


@pytest.mark.asyncio
async def test_queue_dedup_isolation_atomic_and_event_data(pool):
    await watched(pool)
    await watched(pool, domain='second-placeholder.example')
    await watched(pool, B, 'other-placeholder.example')
    queue = events.Queue(pool)
    msg = message()
    await queue.enqueue(A, msg)
    await queue.enqueue(A, msg)
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT tenant_id,domain,event_id,scan_id FROM agent_radix.regulation_runs')
        assert len(rows) == 2 and {r['tenant_id'] for r in rows} == {A}
        assert {r['domain'] for r in rows} == {DOMAIN, 'second-placeholder.example'}
        assert await conn.fetchval('SELECT count(*) FROM agent_radix.passive_scans') == 2
        # Queued behind a long scan: a delivery older than five minutes stays runnable.
        await conn.execute("UPDATE agent_radix.passive_scans SET created_at=now()-interval '10 minutes'")
    store = Store(pool)
    for row in rows:
        assert await store.pending(A, row['scan_id'])
        assert await store.pending(B, row['scan_id']) is None
    result = await store.changes(A, DOMAIN)
    assert result['regulation_event']['event_id'] == msg['event_id']
    assert result['regulation_event']['facts'] == FACTS
    assert result['regulation_event']['browser_cookies_checked'] is False
    assert await store.changes(B, DOMAIN) == {'status': 'pending'}
    with pytest.raises(ValueError):
        await queue.enqueue(A, message({**FACTS, 'tenant_id': str(B)}))


@pytest.mark.asyncio
async def test_worker_only_notice_cookie_and_shared_watch_lock(pool):
    store = await watched(pool)
    await events.Queue(pool).enqueue(A, message())
    calls = []
    async def execute_scan(s, body, **kwargs):
        calls.append(kwargs)
        assert body.tenant_id == A and body.target == TARGET and kwargs['watched']
        from passive_r6 import collect_notices
        assert kwargs['scanner'] is collect_notices
        assert await s.running(A, kwargs['ident'])
        await s.complete(A, kwargs['ident'], [])
    async with pool.acquire() as conn:
        async with conn.transaction():
            assert await conn.fetchval('SELECT pg_try_advisory_xact_lock($1)', passive_watch.WATCH_LOCK)
            assert await passive_watch.tick(pool) == {'queued': True}
        result = await events.run_queued(pool, conn, execute_scan=execute_scan)
    assert result['count'] == 1 and len(calls) == 1
    assert (await store.changes(A, DOMAIN))['status'] == 'complete'
    async with pool.acquire() as conn:
        assert await events.run_queued(pool, conn, execute_scan=execute_scan) is None


@pytest.mark.asyncio
async def test_worker_busy_retry_and_txt_failure_terminal(pool):
    await watched(pool)
    await events.Queue(pool).enqueue(A, message())
    calls = []
    async def busy(s, body, **kwargs):
        calls.append('busy'); await s.fail(A, kwargs['ident']); raise HTTPException(409)
    async def txt(s, body, **kwargs):
        calls.append('txt'); await s.fail(A, kwargs['ident']); raise HTTPException(403)
    async with pool.acquire() as conn:
        assert (await events.run_queued(pool, conn, execute_scan=busy))['count'] == 0
        assert await events.run_queued(pool, conn, execute_scan=txt) is None
        await conn.execute('UPDATE agent_radix.regulation_runs SET next_attempt=now()')
        assert (await events.run_queued(pool, conn, execute_scan=txt))['count'] == 1
        assert await events.run_queued(pool, conn, execute_scan=txt) is None
    assert calls == ['busy','txt']


@pytest.mark.asyncio
async def test_notice_comparison_cannot_fix_full_scan_findings(pool):
    store = await watched(pool)
    full = await store.create(A, TARGET, watch_artifact(DOMAIN), watched=True)
    finding = {'tool': 'placeholder', 'rule': 'placeholder', 'file': TARGET,
               'line': 0, 'severity': 'medium'}
    assert await store.running(A, full)
    await store.complete(A, full, [finding])
    await events.Queue(pool).enqueue(A, message())
    async def notice_scan(s, body, **kwargs):
        assert await s.running(A, kwargs['ident'])
        await s.complete(A, kwargs['ident'], [])
    async with pool.acquire() as conn:
        await events.run_queued(pool, conn, execute_scan=notice_scan)
    changes = await store.changes(A, DOMAIN)
    assert changes['fixed'] == [] and changes['previous_scan_id'] is None
    later = await store.create(A, TARGET, watch_artifact(DOMAIN), watched=True)
    assert await store.running(A, later)
    await store.complete(A, later, [finding])
    changes = await store.changes(A, DOMAIN)
    assert changes['previous_scan_id'] == str(full)
    assert len(changes['unchanged']) == 1 and changes['new'] == changes['fixed'] == []


@pytest.mark.asyncio
async def test_gateway_txt_removal_stops_event_watch_before_checks(pool, monkeypatch):
    import passive_gateway as gateway
    store = await watched(pool)
    await events.Queue(pool).enqueue(A, message())
    async def gone(domain, challenge): return False
    lease = gateway.Lease(store, check=gone)
    monkeypatch.setattr(gateway.app.state, 'lease', lease, raising=False)
    async def scanner(*args): raise AssertionError('placeholder: scanner ran without TXT')
    async def execute_scan(s, body, **kwargs):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway.app))
        return await routes.execute(s, body, ident=kwargs['ident'], scanner=scanner, http=client, watched=True)
    async with pool.acquire() as conn:
        result = await events.run_queued(pool, conn, execute_scan=execute_scan)
        assert result['count'] == 1
    assert (await store.watches(A))[0]['status'] == 'stopped'
    assert (await store.changes(A, DOMAIN))['status'] == 'failed'


@pytest.mark.asyncio
async def test_failed_multi_domain_enqueue_rolls_back_all_runs(pool, monkeypatch):
    await watched(pool)
    await watched(pool, domain='second-placeholder.example')
    same_id = uuid4()
    monkeypatch.setattr(events, 'uuid4', lambda: same_id)
    with pytest.raises(asyncpg.UniqueViolationError):
        await events.Queue(pool).enqueue(A, message())
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_radix.regulation_runs') == 0
        assert await conn.fetchval('SELECT count(*) FROM agent_radix.passive_scans') == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('proof_reason', ['txt_missing', 'txt_changed'])
async def test_r4_missing_or_changed_txt_stops_without_scan(pool, monkeypatch, proof_reason):
    import passive_gateway as gateway
    store = await watched(pool)
    async def proof(*args): return proof_reason
    monkeypatch.setattr(gateway, 'proof_status', proof)
    monkeypatch.setattr(gateway.app.state, 'lease', gateway.Lease(store), raising=False)
    async def forbidden(*args): raise AssertionError('placeholder: scan ran after lost TXT')
    async def execute_scan(s, body, **kwargs):
        return await routes.execute(s, body, scanner=forbidden, watched=True,
            http=httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway.app)))
    assert await passive_watch.tick(pool, execute_scan=execute_scan) == {'count': 0}
    rows = await store.watches(A)
    assert rows[0]['status'] == 'stopped' and rows[0]['stop_reason'] == proof_reason
    assert await store.watches(B) == []


@pytest.mark.asyncio
async def test_r4_due_watch_runs_one_and_compares_then_unwatches(pool):
    store = await watched(pool)
    await watched(pool, B, 'other-placeholder.example')
    finding = {'tool': 'placeholder', 'rule': 'placeholder', 'file': TARGET, 'line': 0, 'severity': 'low'}
    async def execute_scan(s, body, **kwargs):
        ident = await s.create(body.tenant_id, body.target, body.artifact, watched=True)
        assert await s.running(body.tenant_id, ident)
        await s.complete(body.tenant_id, ident, [finding])
        return {'scan_id': str(ident)}
    assert (await passive_watch.tick(pool, execute_scan=execute_scan))['count'] == 1
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_radix.passive_scans') == 1
    delta = await store.changes(A, DOMAIN)
    assert len(delta['new']) == 1 and delta['fixed'] == delta['unchanged'] == []
    from passive_store import compare_findings
    changed = {**finding, 'severity': 'high'}
    assert compare_findings([finding], [finding])['unchanged'] == [finding]
    assert compare_findings([], [finding])['fixed'] == [finding]
    assert compare_findings([changed], [finding]) == {'new': [changed], 'fixed': [finding], 'unchanged': []}
    await store.unwatch(A, DOMAIN)
    assert (await store.watches(A))[0]['status'] == 'stopped'
