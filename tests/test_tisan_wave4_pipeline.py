"""Offline tracked pipeline, approval races, real request/card dispatch and safe replay."""
import copy
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agents.tisan import gold_sources, pipeline
from test_tisan_requests import client as client, command_pool as command_pool, runtime as runtime
from test_tisan_requests import TENANT, brief
import command
import tisan_requests


def reading():
    return {'source': 'figma', 'ready': True, 'visual': [
        {'width': width, 'tokens': {'--placeholder': '#001840'}, 'elements': [
            {'text': 'placeholder approved text', 'box': {'x': 0, 'y': 0, 'width': 10, 'height': 10}}]}
        for width in (375, 1440)]}


def service(tmp_path):
    frame = reading()
    approved = {'page_id': 'placeholder-home', 'figma_file_id': 'placeholderFigmaFileKey01',
                'figma_frame_id': '0:1', 'frame_hash': gold_sources.digest(frame), 'page_hash': 'placeholder-page-hash'}
    built = {'ok': True, 'slug': 'placeholder-site', 'build': 1,
        'checks': [{'name': name, 'ok': True} for name in
                   ('accessibility', 'lighthouse', 'links', 'secrets', 'k6', 'radix.repo')]}
    callbacks = SimpleNamespace(approval=AsyncMock(return_value=approved), read=AsyncMock(return_value=frame),
        build=AsyncMock(return_value=built), stage=AsyncMock(return_value={'id': str(uuid4()), 'result': 'succeeded',
        'details': {'commit': 'a' * 40, 'url': 'https://placeholder-stage.test/'}}))
    result = pipeline.Pipeline(pipeline.Journal(tmp_path / 'promotion.sqlite3'), callbacks.approval,
                               callbacks.read, callbacks.build, callbacks.stage, gold_sources)
    return result, callbacks


def payload():
    return {'page_id': 'placeholder-home', 'brief': brief(), 'actor': 'placeholder-founder'}


@pytest.mark.asyncio
async def test_one_request_runs_to_staging_records_steps_and_never_promotes(tmp_path):
    flow, calls = service(tmp_path)
    ident = str(uuid4())
    result = await flow.run(str(TENANT), ident, payload())
    assert result['ok'] is True and result['pipeline_status'] == 'awaiting_promote'
    assert [step['state'] for step in result['steps']] == ['requested', 'figma', 'build', 'checks', 'staging', 'awaiting_promote']
    from datetime import datetime
    assert all(datetime.fromisoformat(step['at']).utcoffset() is not None for step in result['steps'])
    assert result['checks'][-1]['name'] == 'radix.repo'
    assert flow.journal.get(str(TENANT), ident) == result
    assert flow.journal.get(str(uuid4()), ident) is None
    assert await flow.run(str(TENANT), ident, payload()) == result
    calls.build.assert_awaited_once()
    calls.stage.assert_awaited_once()
    with pytest.raises(ValueError, match='identity changed'):
        await flow.run(str(TENANT), ident, {**payload(), 'actor': 'placeholder-other'})


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['missing', 'changed', 'incomplete', 'fixture', 'not_ready', 'revoked'])
async def test_unapproved_live_changed_or_revoked_page_never_starts_build(tmp_path, failure):
    flow, calls = service(tmp_path)
    if failure == 'missing':
        calls.approval.return_value = None
    elif failure == 'revoked':
        calls.approval.side_effect = [calls.approval.return_value, None]
    elif failure == 'changed':
        calls.read.return_value = {**reading(), 'placeholder_changed': True}
    elif failure == 'incomplete':
        calls.read.return_value = {**reading(), 'visual': []}
    elif failure == 'fixture':
        calls.read.return_value = {**reading(), 'source': 'recorded'}
    else:
        calls.read.return_value = {**reading(), 'ready': False}
    result = await flow.run(str(TENANT), str(uuid4()), payload())
    assert result['ok'] is False and result['pipeline_status'] == 'blocked'
    calls.build.assert_not_called()
    calls.stage.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('check', ['k6', 'radix.repo'])
async def test_failed_quality_or_critical_repo_scan_never_stages(tmp_path, check):
    flow, calls = service(tmp_path)
    calls.build.return_value = copy.deepcopy(calls.build.return_value)
    calls.build.return_value.update(ok=False, detail='placeholder failed check')
    next(c for c in calls.build.return_value['checks'] if c['name'] == check)['ok'] = False
    result = await flow.run(str(TENANT), str(uuid4()), payload())
    assert result['pipeline_status'] == 'blocked' and result['ok'] is False
    assert result['checks'] == calls.build.return_value['checks']
    calls.stage.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_side_effect_is_recorded_without_resubmission(tmp_path):
    flow, calls = service(tmp_path)
    calls.stage.side_effect = RuntimeError('placeholder-private-upstream-error')
    ident = str(uuid4())
    result = await flow.run(str(TENANT), ident, payload())
    assert result['pipeline_status'] == 'blocked'
    assert 'placeholder-private-upstream-error' not in json.dumps(result)
    assert await flow.run(str(TENANT), ident, payload()) == result
    calls.stage.assert_awaited_once()


@pytest.mark.asyncio
async def test_actual_confirm_request_queues_one_durable_room_job_and_refreshes_card(client, runtime, monkeypatch, tmp_path):
    browser, pool, _, room = client
    from chassis.db import ensure_schema
    async with pool.acquire() as conn:
        await ensure_schema(conn, 'tisan')
    room.state.pool = pool
    from agents.tisan import promotion, publish
    modules = {'gold_sources.py': gold_sources, 'promotion.py': promotion, 'publish.py': publish}
    pipeline.mount(room, lambda key, filename: modules[filename])
    # Role comes from the existing authenticated founder identity, not body authority.
    browser.headers['X-Tervory-User'] = 'placeholder-founder'
    app = __import__('fastapi').FastAPI()
    app.include_router(command.router)
    app.include_router(tisan_requests.build_router())
    runtime.app = app
    args = {**brief(), 'page_id': 'placeholder-home', 'assembly': {'plan': {'placeholder': True}, 'copy': {}, 'media': {}}}
    thread = (await browser.post('/v1/command/threads', json={'title': 'placeholder pipeline'})).json()['thread_id']
    proposed = await browser.post(f'/v1/command/threads/{thread}/actions', json={'tool': 'tisan.request', 'arguments': args})
    assert proposed.status_code == 200, proposed.text
    card_id = proposed.json()['card_id']
    confirmed = await browser.post('/v1/command/cards/' + card_id, json={'action': 'confirm'})
    assert confirmed.status_code == 200, confirmed.text
    result = confirmed.json()['result']
    assert result['kind'] == 'pipeline' and result['status'] == 'queued'
    again = await browser.post('/v1/command/cards/' + card_id, json={'action': 'confirm'})
    assert again.status_code == 200
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT id,input,max_attempts FROM agent_tisan.jobs WHERE tenant_id=$1', TENANT)
    assert len(rows) == 1 and str(rows[0]['id']) == result['job_id']
    stored = json.loads(rows[0]['input'])
    assert stored['actor'] == 'placeholder-founder' and rows[0]['max_attempts'] == 1
    assert stored['brief']['plan'] == {'placeholder': True}
    flow, _ = service(tmp_path)
    measured = await flow.run(str(TENANT), result['job_id'], stored)
    hydrated = await browser.get('/v1/command/threads/' + thread)
    assert hydrated.status_code == 200, hydrated.text
    card = next(c for c in hydrated.json()['cards'] if c['card_id'] == card_id)
    assert card['result']['pipeline_status'] == 'awaiting_promote'
    assert card['result']['checks'][-1]['name'] == 'radix.repo'
    assert card['result']['url'] == measured['url']


@pytest.mark.asyncio
async def test_pending_staging_refresh_uses_only_reads_and_never_redeploys(tmp_path, monkeypatch):
    import httpx
    from uuid import uuid5, UUID
    from agents.tisan import promotion, publish
    from test_tisan_publish import FakeServices, TENANT as PUBLISH_TENANT, NEW
    fake = FakeServices()
    fake.pinned = fake.deployed = NEW
    fake.deployment, fake.status = 'new-deploy', 'finished'
    ident = str(uuid4())
    operation = str(uuid5(UUID(ident), 'staging'))
    journal = promotion.Journal(tmp_path / 'promotion.sqlite3')
    journal.register(PUBLISH_TENANT, 'site', {'staging': 'stage', 'production': 'prod', 'url': fake.fqdn})
    journal.reserve(PUBLISH_TENANT, 'site', operation, 'publish', 'placeholder-founder', 'build:1')
    journal.update(PUBLISH_TENANT, 'site', operation, 'pending',
        {'expected': 'build:1', 'commit': NEW, 'url': fake.fqdn, 'deployment': 'new-deploy'})
    measured = {'tenant_id': PUBLISH_TENANT, 'request_id': ident, 'slug': 'site', 'build': 1,
                'pipeline_status': 'staging_pending', 'status': 'done', 'steps': [], 'ok': False}
    pipeline_journal = pipeline.Journal(tmp_path / 'promotion.sqlite3')
    pipeline_journal.claim(PUBLISH_TENANT, ident, {})
    pipeline_journal.save(measured)
    original = httpx.AsyncClient
    monkeypatch.setattr(pipeline, 'httpx', SimpleNamespace(AsyncClient=lambda **kw:
        original(transport=httpx.MockTransport(fake.transport), **kw)))
    monkeypatch.setenv('TISAN_COOLIFY_URL', 'https://coolify.test')
    monkeypatch.setenv('TISAN_COOLIFY_TOKEN', 'coolify-marker-test-only')
    result = await pipeline.refresh_staging(measured, lambda key, filename:
        promotion if filename == 'promotion.py' else publish, tmp_path)
    assert result['pipeline_status'] == 'awaiting_promote' and result['commit'] == NEW
    assert all(method == 'GET' for method, _, _ in fake.calls)
    assert pipeline_journal.get(PUBLISH_TENANT, ident) == result


@pytest.mark.asyncio
async def test_approval_revoked_during_build_does_not_stage(tmp_path):
    flow, calls = service(tmp_path)
    approved = calls.approval.return_value
    calls.approval.side_effect = [approved, approved, None]
    result = await flow.run(str(TENANT), str(uuid4()), payload())
    assert result['pipeline_status'] == 'blocked'
    calls.stage.assert_not_called()


@pytest.mark.asyncio
async def test_real_approval_snapshot_and_live_reader_are_tenant_bound(client, tmp_path):
    from agents.tisan import promotion, publish
    browser, pool, _, _ = client
    del browser
    from chassis.db import ensure_schema
    frame = reading()
    file_key = 'placeholderFigmaFileKey01'
    frame_path = file_key + '/0-1.json'
    built_path = 'placeholder-site/1-home.page.json'
    frame_file = tmp_path / 'readings' / str(TENANT) / frame_path
    frame_file.parent.mkdir(parents=True)
    frame_file.write_text(json.dumps(frame))
    built = {'structure': {'path': '/', 'nodes': []}, 'html': 'placeholder approved page', 'css': ''}
    built_file = tmp_path / 'builds' / str(TENANT) / built_path
    built_file.parent.mkdir(parents=True)
    built_file.write_text(json.dumps(built))
    review = tmp_path / 'reviews' / str(TENANT) / 'placeholder-home.json'
    review.parent.mkdir(parents=True)
    review.write_text(json.dumps({'tenant_id': str(TENANT), 'region': 'us-east', 'frame_path': frame_path,
                                 'built_page_path': built_path, 'figma_file_id': file_key, 'figma_frame_id': '0:1'}))
    async with pool.acquire() as conn:
        await ensure_schema(conn, 'tisan')
        await conn.execute(gold_sources.SCHEMA)
        await conn.execute('INSERT INTO agent_tisan.page_approvals '
            '(tenant_id,page_id,figma_file_id,figma_frame_id,frame_hash,built_page_path,page_hash,approved_by) '
            'VALUES($1,$2,$3,$4,$5,$6,$7,$8)', TENANT, 'placeholder-home', file_key, '0:1',
            gold_sources.digest(frame), built_path, gold_sources.digest(built), 'placeholder-founder')
    live = SimpleNamespace(execute=AsyncMock(return_value=frame))
    modules = {'gold_sources.py': gold_sources, 'builder.py': SimpleNamespace(), 'figma.py': live,
               'publish.py': publish, 'promotion.py': promotion}
    flow = pipeline.service(SimpleNamespace(), pool, lambda key, filename: modules[filename], tmp_path)
    approved = await flow.approved_page(str(TENANT), 'placeholder-home')
    assert approved['figma_file_id'] == file_key
    assert live.execute.call_args.kwargs == {'live': True, 'data_root': tmp_path}
    with pytest.raises(ValueError):
        await flow.approved_page(str(uuid4()), 'placeholder-home')
    assert live.execute.await_count == 1
    # A changed approved artifact is refused before any new live read/build.
    built_file.write_text(json.dumps({**built, 'html': 'placeholder changed page'}))
    with pytest.raises(ValueError):
        await flow.approved_page(str(TENANT), 'placeholder-home')
    assert live.execute.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('source,allowed', [(None, True),
    ({'file_key': 'placeholder-approved-file', 'node_id': '0:1'}, True),
    ({'file_key': 'placeholder-other-file', 'node_id': '0:1'}, False), ('placeholder-invalid', False)])
async def test_legacy_handler_cannot_substitute_an_unapproved_frame(monkeypatch, source, allowed):
    from agents.tisan import app as room
    module = room._load_beside(room._figma_cache(), 'tisan_pipeline_room', 'pipeline.py')
    gate = SimpleNamespace(approved_page=AsyncMock(return_value={
        'figma_file_id': 'placeholder-approved-file', 'figma_frame_id': '0:1'}))
    monkeypatch.setattr(module, 'service', lambda *args: gate)
    monkeypatch.setattr(room.app.state, 'pool', object(), raising=False)
    data = {'page_id': 'placeholder-home'}
    if source is not None:
        data['figma'] = source
    assert await room._approved_build(SimpleNamespace(tenant_id=str(TENANT), input=data)) is allowed


@pytest.mark.asyncio
async def test_missing_page_reference_is_tracked_without_starting_any_build(tmp_path):
    flow, calls = service(tmp_path)
    result = await flow.run(str(TENANT), str(uuid4()), {**payload(), 'page_id': None})
    assert result['pipeline_status'] == 'blocked' and result['steps'][0]['state'] == 'requested'
    calls.read.assert_not_called()
    calls.build.assert_not_called()
    calls.stage.assert_not_called()
