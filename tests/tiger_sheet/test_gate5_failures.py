import asyncio
from datetime import datetime, timedelta, timezone
import json
import smtplib
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

from test_tiger import ROOT, TENANT_A, TENANT_B, _load, _watch
from test_tiger_competitors import database, postgres
from test_tiger_alert_email import pending
from alert_email import deliver_pending
from rig_watch import RigWatches, TankRig
from watch import MemoryStore, PgStore, FeedUnavailable
from tiger_sheet.patch_source import source


@pytest.mark.asyncio
@pytest.mark.parametrize('persistent', [False, True])
async def test_rejected_email_stops_after_three_attempts_and_keeps_receipt(database, persistent):
    store, _ = await pending(PgStore(database) if persistent else MemoryStore())
    transport = SimpleNamespace(send=AsyncMock(side_effect=smtplib.SMTPDataError(451, b'placeholder rejection')))
    now = datetime.now(timezone.utc) + timedelta(days=1)
    for attempt in range(6):
        result = await deliver_pending(store, TENANT_A, transport=transport, recipient='a@example.test',
                                       clock=lambda: now + timedelta(hours=attempt))
        if attempt == 2:
            assert result['failed'] == 1 and result['pending'] == 0
            assert result['error'] == 'Tiger is not reachable right now.'
    assert transport.send.await_count == 3
    assert await store.pending_mail(TENANT_A, now + timedelta(days=1)) == []
    if persistent:
        row = await database.fetchrow('SELECT status,attempts FROM agent_tiger.alert_mail WHERE tenant_id=$1', UUID(TENANT_A))
    else:
        row = next(iter(store.mail.values()))
    assert row['status'] == 'failed' and row['attempts'] == 3


@pytest.mark.asyncio
@pytest.mark.parametrize('reject', [False, True])
async def test_rig_delivery_claim_is_atomic_bounded_and_scoped(database, monkeypatch, reject):
    watch = await PgStore(database).create_watch(_watch())
    payload = {'price': '12.00', 'currency': 'USD', 'active': True}
    for tenant in (TENANT_A, TENANT_B):
        await database.execute('''INSERT INTO agent_tiger.rig_targets(tenant_id,sku,url,watch_id,pending)
            VALUES($1,'placeholder-sku',$2,$3,$4::jsonb)''', UUID(tenant), watch['url'], UUID(watch['id']), json.dumps(payload))
    rig = RigWatches(PgStore(database))
    monkeypatch.setattr(rig, 'sync', AsyncMock())
    calls = []
    async def send(tenant, sku, body):
        calls.append((tenant, sku, body))
        await asyncio.sleep(.02)
        if reject:
            raise httpx.ReadTimeout('placeholder transport failure')
        return True
    client = SimpleNamespace(send=send)
    for _ in range(5):
        await asyncio.gather(*(rig.deliver(TENANT_A, client) for _ in range(3)))
        await database.execute("UPDATE agent_tiger.rig_targets SET next_attempt_at=now()-interval '1 minute' WHERE tenant_id=$1", UUID(TENANT_A))
    assert len(calls) == (3 if reject else 1)
    assert all(tenant == TENANT_A and body == payload for tenant, sku, body in calls)
    foreign = await database.fetchrow('SELECT attempts,pending FROM agent_tiger.rig_targets WHERE tenant_id=$1', UUID(TENANT_B))
    assert foreign['attempts'] == 0 and foreign['pending'] is not None
    own = await database.fetchrow('SELECT attempts,pending FROM agent_tiger.rig_targets WHERE tenant_id=$1', UUID(TENANT_A))
    assert own['attempts'] == (3 if reject else 0)
    assert (own['pending'] is not None) == reject
    assert rig.receipt['failed'] == int(reject)
    if reject:
        assert rig.receipt['error'] == 'Tiger is not reachable right now.'


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['render', 'robots', 'catalogue', 'feed', 'rig'])
async def test_entire_external_call_has_deadline_and_no_transport_replay(monkeypatch, operation):
    agent = _load('gate5_timeout_'+operation, ROOT/'agents/tiger/app.py')
    calls = []
    async def stall(*args, **kwargs):
        calls.append((args, kwargs))
        await asyncio.Event().wait()
    http = SimpleNamespace(get=stall, post=stall, request=stall)
    agent.app.state.http = http
    monkeypatch.setattr(agent, 'asyncio', SimpleNamespace(timeout=lambda seconds: asyncio.timeout(.02)))
    if operation == 'render':
        call = agent._render('https://placeholder.example/item', '', 'tiger', TENANT_A)
    elif operation == 'feed':
        call = agent.official_feed(TENANT_A, 'https://placeholder.example/item')
    elif operation == 'rig':
        import rig_watch
        monkeypatch.setattr(rig_watch, 'asyncio', SimpleNamespace(timeout=lambda seconds: asyncio.timeout(.02)))
        call = TankRig(http).products(TENANT_A)
    else:
        monkeypatch.setattr(agent, '_fetch_text_request', stall)
        call = agent._fetch_text('https://placeholder.example/robots.txt', catalogue=operation == 'catalogue')
    with pytest.raises(FeedUnavailable if operation == 'feed' else TimeoutError):
        await call
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_dns_failure_never_mutates_watch_and_event_loop_remains_available(monkeypatch):
    import threading
    agent = _load('gate5_dns', ROOT/'agents/tiger/app.py')
    store = MemoryStore()
    released = threading.Event()
    monkeypatch.setattr(agent, '_store', lambda: store)
    monkeypatch.setattr(agent, 'check_url', lambda url: released.wait(1) and url)
    monkeypatch.setattr(agent, 'asyncio', SimpleNamespace(timeout=lambda seconds: asyncio.timeout(.02), to_thread=asyncio.to_thread))
    try:
        with pytest.raises(agent.HTTPException) as failure:
            await agent.create_watch(agent.WatchIn(tenant_id=TENANT_A, url=_watch()['url'], every='1d'))
        assert failure.value.status_code == 503 and 'not reachable' in failure.value.detail
        assert store.watches == []
    finally:
        released.set()


def test_workspace_http_paths_bound_headers_and_body_and_redact_errors(tmp_path):
    import subprocess
    proposed = tmp_path/'tank.ts'
    proposed.write_text(source('workspace/lib/tank.ts'))
    result = subprocess.run(['node', str(ROOT/'tests/tiger_sheet/gate5_http.cjs'), str(proposed)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'all Tiger HTTP paths' in result.stdout


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [302, 503, 200])
async def test_public_text_checks_address_caps_body_and_never_follows_redirects(monkeypatch, status):
    agent = _load('gate5_public_text_'+str(status), ROOT/'agents/tiger/app.py')
    validated, requests = [], []
    monkeypatch.setattr(agent, 'check_url', lambda url: validated.append(url) or url)
    async def answer(request):
        requests.append(request)
        return httpx.Response(status, content=b'x'*200_000, headers={'Location': 'http://127.0.0.1/private'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        agent.app.state.http = client
        if status == 200:
            assert len(await agent._fetch_text('https://store.example/robots.txt')) == 100_000
        else:
            with pytest.raises(httpx.HTTPStatusError):
                await agent._fetch_text('https://store.example/robots.txt')
    assert validated == ['https://store.example/robots.txt'] and len(requests) == 1


@pytest.mark.asyncio
async def test_discovery_resume_polls_last_saved_job_without_restarting_source(tmp_path):
    from batch import discovery_id, run
    from tiger_sheet.test_finish_batch import BATCH
    from uuid import uuid4
    root = str(discovery_id(TENANT_A, BATCH, 'one', 'https://store.example'))
    child = str(uuid4())
    requests, resume = [], False
    async def answer(request):
        requests.append((request.method, request.url.path))
        if request.method == 'POST':
            job = {'id': root, 'status': 'done', 'result': {'continuation_id': child}}
        elif resume:
            job = {'id': child, 'status': 'done', 'result': {'status': 'completed', 'product_urls': [], 'sites': []}}
        else:
            job = {'id': child, 'status': 'running'}
        return httpx.Response(200, json={**job, 'tenant_id': TENANT_A})
    async def interrupted(_): raise TimeoutError
    rows = [{'id': 'one', 'website': 'https://store.example'}]
    async with httpx.AsyncClient(base_url='https://placeholder.invalid', transport=httpx.MockTransport(answer)) as client:
        with pytest.raises(TimeoutError):
            await run(rows, TENANT_A, BATCH, tmp_path/'state', client, sleep=interrupted)
        resume = True
        result = await run(rows, TENANT_A, BATCH, tmp_path/'state', client, sleep=interrupted)
    assert requests == [('POST', '/batch/discover'), ('GET', '/jobs/'+child), ('GET', '/jobs/'+child)]
    assert result[0]['discovery']['final_job_id'] == child and result[0]['status'] == 'complete'


@pytest.mark.asyncio
async def test_batch_missing_room_key_stops_before_checkpoint_or_network(tmp_path, monkeypatch):
    from batch import main
    from tiger_sheet.test_finish_batch import BATCH
    monkeypatch.setenv('TIGER_BATCH_URL', 'https://placeholder.invalid')
    monkeypatch.delenv('TANK_KEY', raising=False)
    path = tmp_path/'input.csv'
    path.write_text('record_id,state,website\none,WY,https://store.example\n')
    args = SimpleNamespace(input=str(path), tenant=TENANT_A, batch=BATCH, checkpoint=str(tmp_path/'checkpoint'),
                           receipts=str(tmp_path/'receipts'), retry_failed=False)
    assert await main(args) == {'status': 'not_configured', 'settings': ['TANK_KEY']}
    assert list(tmp_path.iterdir()) == [path]
