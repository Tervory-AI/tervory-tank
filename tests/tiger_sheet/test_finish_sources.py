import base64
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest

from test_tiger import TENANT_A, TENANT_B, NOW, _watch, _load, ROOT
from test_tiger_competitors import database as database, postgres as postgres
from tiger_works.fixture import URL, saved_page, extract, no_paid_call as no_paid_call
from watch import DomainLimiter, MemoryStore, external_observation, _save_png
from batch import run
from tiger_sheet.test_finish_batch import BATCH


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('quantity', 'NaN'), ('quantity', None), ('quantity', -1),
    ('price', 'Infinity'), ('price', None), ('price', -1), ('price', 'placeholder')])
async def test_incomplete_real_feed_fields_save_unknown_without_alert(field, value):
    store = MemoryStore()
    watch = await store.create_watch(_watch())
    item = {'name': 'placeholder item', 'price': '10', 'currency': 'USD', 'quantity': 1}
    await external_observation(store, TENANT_A, watch, item, 'official_feed', {'id': 'placeholder'}, lambda: NOW)
    result = await external_observation(store, TENANT_A, watch, {**item, field: value},
                                        'official_feed', {'id': 'placeholder'}, lambda: NOW)
    assert result['status'] == "can't read" and result['alerts'] == []
    assert result['observation']['price'] is None and result['observation']['method'] == 'unread'
    assert await store.list_observations(TENANT_B, watch['url']) == []


def test_screenshots_in_same_second_keep_each_receipts_bytes():
    saved = {}
    files = SimpleNamespace(save_file=lambda tenant, name, raw: saved.setdefault((tenant, name), raw) and name)
    a, b = b'\x89PNGplaceholder one', b'\x89PNGplaceholder two'
    first = _save_png(files, TENANT_A, base64.b64encode(a).decode(), NOW)
    second = _save_png(files, TENANT_A, base64.b64encode(b).decode(), NOW)
    assert first != second and saved[(TENANT_A, first)] == a and saved[(TENANT_A, second)] == b
    assert _save_png(files, TENANT_A, base64.b64encode(a).decode(), NOW) == first


@pytest.mark.asyncio
@pytest.mark.parametrize('image_only', [False, True])
async def test_small_state_handoff_runs_actual_reader_to_saved_receipt(database, monkeypatch, tmp_path, image_only):
    agent = _load('tiger_finish_sources_app', ROOT/'agents/tiger/app.py')
    agent.app.state.pool = database
    monkeypatch.setattr(agent, 'check_url', lambda url: url)
    monkeypatch.setattr(agent, '_limiter', DomainLimiter(0))
    monkeypatch.setattr(agent, 'official_feed', AsyncMock(return_value={'found': False}))
    renders = []
    async def render(url, session, name, tenant, task):
        renders.append((url, tenant, task))
        return {'ok': True, 'html': '<h1>placeholder product</h1><p>In stock</p>' if image_only else saved_page(),
                'png_base64': base64.b64encode(b'\x89PNGplaceholder picture').decode()}
    monkeypatch.setattr(agent, '_render', render)
    async def skill(tenant, name, payload):
        assert tenant == TENANT_A
        if name == 'tiger.price_extract':
            output = await extract(payload['html'], payload['url'])
        else:
            assert image_only and name == 'tiger.price_ocr'
            reader = _load('finish_code_ocr', ROOT/'tank/skills/tiger.price_ocr/1.0.1/run.py')
            # Recorded/fake Tesseract response feeds the shipped pure-code parser.
            output = await reader.run({'text': '$12.50', 'url': payload['url']}, None)
        return {**output, '_ledger_id': 'placeholder-ledger', '_cost_usd': 0}
    relay = SimpleNamespace(alert_context=AsyncMock(return_value={'urls': [], 'product': None}))
    monkeypatch.setattr(agent, 'TankRig', lambda http: relay)
    monkeypatch.setattr(agent.RigWatches, 'deliver', AsyncMock(return_value=0))
    agent.app.state.http = None
    async def transport(request):
        if request.method == 'POST':
            queued = await agent.batch_check(agent.BatchCheckIn(**json.loads(request.content)))
            if queued['status'] != 'done':
                body = json.loads(await database.fetchval('SELECT input FROM agent_tiger.jobs WHERE id=$1', UUID(queued['id'])))
                ctx = SimpleNamespace(input=body, tenant_id=TENANT_A, agent='tiger', job_id=queued['id'], files=None,
                    tank=SimpleNamespace(run_skill=skill, approved_skill=AsyncMock(return_value=None)))
                result = await agent.check(ctx)
                await database.execute("UPDATE agent_tiger.jobs SET status='done',result=$2::jsonb WHERE id=$1",
                                       UUID(queued['id']), json.dumps(result, default=str))
                queued.update(status='done', result=json.loads(json.dumps(result, default=str)))
            return httpx.Response(201, json=queued)
        raise AssertionError('This fake worker finishes synchronously')
    # State codes and record IDs are the engine's handoff, not Tiger vocabulary.
    rows = [{'id': 'placeholder-small-state-1', 'state': 'WY', 'product_urls': [URL]}]
    async with httpx.AsyncClient(base_url='http://placeholder', transport=httpx.MockTransport(transport)) as client:
        receipts = await run(rows, TENANT_A, BATCH, tmp_path/'checkpoint', client)
        assert await run(rows, TENANT_A, BATCH, tmp_path/'checkpoint', client) == receipts
    page = receipts[0]['pages'][0]
    assert page['price'] == ('12.50' if image_only else '120.00') and page['currency'] == 'USD'
    assert page['observation_id'] and page['job_id'] and page['model_calls'] == 0
    assert page['skill_receipts'] == [{'skill': name, 'ledger_id': 'placeholder-ledger', 'cost_usd': 0}
        for name in (['tiger.price_extract', 'tiger.price_ocr'] if image_only else ['tiger.price_extract'])]
    assert len(renders) == 1
    assert await database.fetchval('SELECT count(*) FROM agent_tiger.observations WHERE tenant_id=$1', UUID(TENANT_B)) == 0
    assert await database.fetchval('SELECT count(*) FROM agent_tiger.schedules WHERE tenant_id=$1 AND kind=$2', UUID(TENANT_A), 'dispatch') == 1


@pytest.mark.asyncio
async def test_exhausted_batch_job_resumes_only_when_requested(database, monkeypatch):
    agent = _load('tiger_finish_retry_app', ROOT/'agents/tiger/app.py')
    agent.app.state.pool = database
    monkeypatch.setattr(agent, 'check_url', lambda url: url)
    body = agent.BatchCheckIn(tenant_id=TENANT_A, batch_id=BATCH, record_id='placeholder', url=URL)
    first = await agent.batch_check(body)
    await database.execute("UPDATE agent_tiger.jobs SET status='failed',attempts=3 WHERE id=$1", UUID(first['id']))
    assert (await agent.batch_check(body))['status'] == 'failed'
    resumed = await agent.batch_check(body.model_copy(update={'retry_failed': True}))
    assert resumed['status'] == 'queued' and resumed['id'] == first['id']
