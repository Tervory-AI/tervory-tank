import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest

from test_tiger import TENANT_A, TENANT_B, NOW, _load, ROOT
from test_tiger_competitors import database, postgres  # local-only database fixtures
from batch import Checkpoint, job_id, plan, run

BATCH = '33333333-3333-4333-8333-333333333333'
URL = 'https://placeholder.example/product'


def test_state_order_uses_record_counts_before_product_counts():
    rows = [{'id': str(i), 'state': state, 'product_urls': []} for i, state in enumerate(['CA', 'WY', 'CA', 'AK', 'AK', 'CA'])]
    result = plan(rows, TENANT_A)
    assert [row['state'] for row in result] == ['WY', 'AK', 'AK', 'CA', 'CA', 'CA']
    assert result == plan(list(reversed(rows)), TENANT_A)


@pytest.mark.parametrize('row', [
    {'id': 'x', 'tenant_id': TENANT_B}, {'id': ''}, {'id': 'x', 'product_urls': 'url'},
    {'id': 'x', 'product_urls': ['file:///placeholder']}, {'id': 'x', 'product_urls': ['https://user:placeholder@example.com/x']},
])
def test_invalid_handoff_stops_before_remote_work(row):
    with pytest.raises(ValueError):
        plan([row], TENANT_A)


def test_checkpoint_binds_source_and_tenant(tmp_path):
    path = tmp_path / 'checkpoint.sqlite'
    rows = plan([{'id': 'one', 'state': 'WY'}], TENANT_A)
    Checkpoint(path, TENANT_A, BATCH, rows).close()
    for tenant, batch, source in [(TENANT_B, BATCH, rows), (TENANT_A, str(uuid4()), rows), (TENANT_A, BATCH, [])]:
        with pytest.raises(ValueError):
            Checkpoint(path, tenant, batch, source)


@pytest.mark.asyncio
async def test_receipts_resume_after_lost_submission_without_rechecking_completed_record(tmp_path):
    rows = [{'id': 'a', 'state': 'WY', 'product_urls': [URL]},
            {'id': 'b', 'state': 'AK', 'product_urls': [URL + '2']},
            {'id': 'c', 'state': 'AK'}]
    jobs, posts, failed = {}, [], False
    async def answer(request):
        nonlocal failed
        if request.method == 'POST':
            body = json.loads(request.content)
            ident = str(job_id(body['tenant_id'], body['batch_id'], body['record_id'], body['url']))
            posts.append(body['record_id'])
            jobs.setdefault(ident, {'id': ident, 'tenant_id': TENANT_A, 'status': 'done', 'result': {
                'status': 'observed', 'observation': {'id': str(uuid4()), 'tenant_id': TENANT_A,
                'url': body['url'], 'ts': NOW.isoformat(), 'price': '120.00', 'currency': 'USD', 'method': 'jsonld'}}})
            if body['record_id'] == 'b' and not failed:
                failed = True
                raise httpx.ReadTimeout('placeholder lost reply')
            return httpx.Response(201, json=jobs[ident])
        raise AssertionError('completed jobs need no poll')
    path = tmp_path / 'checkpoint.sqlite'
    async with httpx.AsyncClient(base_url='http://placeholder', transport=httpx.MockTransport(answer)) as client:
        with pytest.raises(httpx.ReadTimeout):
            await run(rows, TENANT_A, BATCH, path, client)
        result = await run(rows, TENANT_A, BATCH, path, client)
        assert await run(rows, TENANT_A, BATCH, path, client) == result
    assert posts == ['a', 'b', 'b'] and len(jobs) == 2
    assert [row['record_id'] for row in result] == ['a', 'b', 'c']
    assert result[0]['pages'][0]['price'] == '120.00'
    assert result[2]['source_status'] == 'no_product_urls' and result[2]['pages'] == []


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['foreign', 'missing', 'failed'])
async def test_bad_receipt_cannot_complete_record(tmp_path, failure):
    ident = str(job_id(TENANT_A, BATCH, 'a', URL))
    job = {'id': ident, 'tenant_id': TENANT_B if failure == 'foreign' else TENANT_A,
           'status': 'failed' if failure == 'failed' else 'done', 'result': {}}
    async with httpx.AsyncClient(base_url='http://placeholder', transport=httpx.MockTransport(
        lambda request: httpx.Response(200, json=job))) as client:
        with pytest.raises((ValueError, RuntimeError)):
            await run([{'id': 'a', 'product_urls': [URL]}], TENANT_A, BATCH, tmp_path/'state', client)


@pytest.mark.asyncio
async def test_batch_submission_is_idempotent_and_keeps_existing_watch_preferences(database, monkeypatch):
    agent = _load('tiger_finish_batch_app', ROOT/'agents/tiger/app.py')
    agent.app.state.pool = database
    monkeypatch.setattr(agent, 'check_url', lambda url: url)
    body = agent.BatchCheckIn(tenant_id=TENANT_A, batch_id=BATCH, record_id='a', url=URL)
    first = await agent.batch_check(body)
    store = agent._store()
    watch = await store.get_watch(TENANT_A, URL)
    await store.update_watch(TENANT_A, watch['id'], {'enabled': False, 'alert_stock': False})
    results = await asyncio.gather(*(agent.batch_check(body) for _ in range(10)))
    assert all(row['id'] == first['id'] for row in results)
    assert await database.fetchval("SELECT count(*) FROM agent_tiger.jobs WHERE kind='check'") == 1
    assert not (await store.get_watch(TENANT_A, URL))['enabled']
    other = await agent.batch_check(body.model_copy(update={'tenant_id': UUID(TENANT_B)}))
    assert other['id'] != first['id']
    assert (await store.get_watch(TENANT_B, URL))['enabled']
    assert (await database.fetchval('SELECT input FROM agent_tiger.jobs WHERE id=$1', UUID(first['id'])))
