import json
from types import SimpleNamespace
from uuid import UUID, uuid4

import httpx
import pytest

from test_tiger import ROOT, TENANT_A, TENANT_B, _load
from test_tiger_competitors import database as database, postgres as postgres
from tiger_works.fixture import extract, saved_page
from batch import discovery_id, job_id, load_input, plan, run
import batch_discovery

BATCH = '33333333-3333-4333-8333-333333333333'
SITE = 'https://placeholder.example'


def test_base_records_csv_and_full_size_state_plan(tmp_path):
    path = tmp_path/'base-records.csv'
    path.write_text('record_id,state,website,name\na,WY,https://placeholder.example,placeholder business\n')
    rows = load_input(path)
    assert plan(rows, TENANT_A)[0]['website'] == SITE
    full = [{'record_id': str(i), 'state': 'CA' if i >= 100 else 'WY'} for i in range(77000)]
    result = plan(list(reversed(full)), TENANT_A)
    assert len(result) == 77000 and [r['state'] for r in result[:100]] == ['WY'] * 100
    assert all(r['state'] == 'CA' for r in result[100:])


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', [False, True, 'unavailable'])
async def test_discovery_reuses_sitemaps_checkpoint_and_real_extractor(database, monkeypatch, blocked):
    agent = _load('tiger_finish_discovery_app', ROOT/'agents/tiger/app.py')
    agent.app.state.pool = database
    monkeypatch.setattr(agent, 'check_url', lambda url: url)
    calls = []
    class Gate:
        def __init__(self, pool): pass
        async def call(self, url, operation): return await operation()
        async def block(self, site): calls.append(('blocked', site))
    monkeypatch.setattr(batch_discovery, 'DiscoveryGate', Gate)
    async def fetch(url):
        calls.append(('fetch', url))
        if url.endswith('/robots.txt'):
            return {'status': 200, 'text': 'User-agent: *\nAllow: /'}
        return {'status': 200, 'text': f'<urlset><url><loc>{SITE}/product</loc></url><url><loc>{SITE}/about</loc></url></urlset>'}
    async def render(url):
        calls.append(('render', url))
        if blocked == 'unavailable':
            return {'ok': False, 'error': 'browser answered 503'}
        if blocked:
            return {'challenge': True, 'status': 403}
        return {'ok': True, 'url': url, 'html': saved_page() if url.endswith('/product') else '<h1>placeholder business</h1>'}
    async def skill(tenant, name, payload):
        assert tenant == TENANT_A and name == 'tiger.price_extract'
        return await extract(payload['html'], payload['url'])
    async def gateway_fetch(url, *, catalogue):
        assert catalogue is True
        return await fetch(url)
    async def gateway_render(url, session, name, tenant, task, *, catalogue_match):
        assert catalogue_match is True and tenant == TENANT_A
        return await render(url)
    monkeypatch.setattr(agent, '_fetch_text', gateway_fetch)
    monkeypatch.setattr(agent, '_render', gateway_render)
    first = await agent.batch_source(agent.BatchCheckIn(tenant_id=TENANT_A, batch_id=BATCH, record_id='a', url=SITE))
    assert first['id'] == str(discovery_id(TENANT_A, BATCH, 'a', SITE))
    ident = first['id']
    results = []
    while ident:
        body = json.loads(await database.fetchval('SELECT input FROM agent_tiger.jobs WHERE id=$1', UUID(ident)))
        ctx = SimpleNamespace(tenant_id=TENANT_A, job_id=ident, input=body, tank=SimpleNamespace(run_skill=skill))
        result = await agent.app.state.handlers['competitor_match'](ctx)
        count = len(calls)
        assert await agent.app.state.handlers['competitor_match'](ctx) == result
        assert len(calls) == count  # A worker replay reuses its saved slice.
        results.append(result)
        ident = result['continuation_id']
        assert len(results) < 20
    assert results[-1]['status'] == 'completed'
    assert results[-1]['product_urls'] == ([] if blocked else [SITE + '/product'])
    assert results[-1]['sites'][0]['status'] == ('human_check' if blocked is True else 'completed')
    if blocked == 'unavailable':
        assert results[-1]['sites'][0]['warnings']
    foreign = SimpleNamespace(tenant_id=TENANT_B, job_id=str(uuid4()), input={'root_job_id': first['id']})
    with pytest.raises(ValueError):
        await batch_discovery.step(foreign, database, fetch, render)


@pytest.mark.asyncio
async def test_base_website_discovery_continuation_feeds_price_checks_and_receipt(tmp_path):
    source = str(discovery_id(TENANT_A, BATCH, 'a', SITE))
    final = str(uuid4())
    price = str(job_id(TENANT_A, BATCH, 'a', SITE + '/product'))
    requests = []
    async def transport(request):
        requests.append(request.url.path)
        if request.url.path == '/batch/discover':
            job = {'id': source, 'result': {'continuation_id': final}}
        elif request.url.path == '/jobs/' + final:
            job = {'id': final, 'result': {'status': 'completed', 'product_urls': [SITE + '/product'], 'sites': [{'status': 'completed'}]}}
        elif request.url.path == '/batch/check':
            assert json.loads(request.content)['url'] == SITE + '/product'
            job = {'id': price, 'result': {'status': 'observed', 'observation': {'id': str(uuid4()),
                'ts': '2026-11-07T10:00:00Z', 'tenant_id': TENANT_A, 'url': SITE + '/product', 'price': '120.00'}}}
        else:
            raise AssertionError(request.url.path)
        return httpx.Response(200, json={'tenant_id': TENANT_A, 'status': 'done', **job})
    async with httpx.AsyncClient(base_url='http://placeholder', transport=httpx.MockTransport(transport)) as client:
        rows = [{'record_id': 'a', 'state': 'WY', 'website': SITE}]
        result = await run(rows, TENANT_A, BATCH, tmp_path/'state', client)
        assert await run(rows, TENANT_A, BATCH, tmp_path/'state', client) == result
    assert requests == ['/batch/discover', '/jobs/' + final, '/batch/check']
    assert result[0]['discovery']['job_id'] == source and result[0]['pages'][0]['job_id'] == price
