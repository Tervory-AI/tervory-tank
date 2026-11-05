import asyncio
from datetime import date
import gzip
import hashlib
import json
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import uuid4, UUID

import asyncpg
import pytest
import pytest_asyncio

from test_b3_base_room import ROOT, BASE_CORE, _load, _scripted
from engines.ffl.reference import parse_file
import room
import training_day as training

INGEST = _load('base_training_recorded_ingest', ROOT / 'tank/skills/ffl.ingest/1.0.1/run.py')
TODAY = date(2025, 9, 20)


@pytest.fixture(scope='module')
def recorded():
    content = gzip.open(ROOT / 'tests/fixtures/base-atf/0925-ffl-list-complete.txt.gz', 'rb').read()
    return {'rows': parse_file(content), 'sha256': hashlib.sha256(content).hexdigest(),
            'source_url': 'https://www.atf.gov/resource-center/docs/0925-ffl-list-complete.txt',
            'published_on': '2025-09-01'}


@pytest.fixture(scope='module')
def postgres(tmp_path_factory):
    from pgserver import get_server
    server = get_server(tmp_path_factory.mktemp('base-training') / 'pg', cleanup_mode='delete')
    yield server
    server.cleanup()


@pytest_asyncio.fixture
async def database(postgres):
    name = 'base_finish_' + uuid4().hex
    admin = await asyncpg.connect(postgres.get_uri())
    await admin.execute('CREATE DATABASE ' + name)
    pool = await asyncpg.create_pool(postgres.get_uri(database=name), min_size=1, max_size=4)
    try:
        yield pool
    finally:
        await pool.close()
        await admin.execute('DROP DATABASE ' + name)
        await admin.close()


def test_complete_recorded_list_keeps_all_77611_licences_and_sorts_every_jurisdiction(recorded):
    result = training.plan(recorded, today=TODAY)
    assert result['records'] == result['source_records'] == 77611
    states = result['states']
    assert len(states) == 55
    assert states[0]['state'] == 'DC' and states[0]['count'] == 4
    assert [(r['count'], r['state']) for r in states] == sorted((r['count'], r['state']) for r in states)
    assert sum(row['count'] for row in states) == 77611
    assert sum(state['count'] for state in states if state['state'] in {'DC', 'MP', 'VI', 'GU', 'PR'}) == 109
    assert states[0]['rows'][0]['_base_reference']['source_url'] == recorded['source_url']


def test_any_collector_licences_present_in_a_source_are_not_dropped(recorded):
    from base_product_fixtures import atf_bytes, raw
    content = atf_bytes([raw(3, kind='03')])
    source = {**recorded, 'rows': parse_file(content), 'sha256': hashlib.sha256(content).hexdigest()}
    result = training.plan(source, today=TODAY)
    assert result['records'] == 1
    assert result['states'][0]['rows'][0]['_base_reference']['licence_type'] == '03'


def test_restart_uses_the_retained_source_and_rejects_cache_tampering(recorded, tmp_path):
    # A later publication must not silently replace the input of an unfinished run.
    small = {**recorded, 'rows': recorded['rows'][:1]}
    assert training.retained_source(tmp_path) is None
    training.retain_source(tmp_path, small)
    assert training.retained_source(tmp_path) == small
    path = tmp_path / 'sources' / (small['sha256'] + '.json')
    path.write_text(path.read_text().replace('2025-09-01', '2025-10-01'))
    with pytest.raises(ValueError, match='retained official source changed'):
        training.retained_source(tmp_path)


def test_only_the_explicitly_configured_dated_fallback_source_is_accepted(recorded, monkeypatch):
    selected = 'https://approved-source.example/0925-ffl-list-complete.txt'
    monkeypatch.setenv('BASE_REFERENCE_FILE_URL', selected)
    source = {**recorded, 'source_url': selected}
    assert training.plan(source, today=TODAY)['records'] == 77611
    with pytest.raises(ValueError):
        training.plan({**source, 'source_url': 'https://other.example/0925-ffl-list-complete.txt'}, today=TODAY)


@pytest.mark.asyncio
@pytest.mark.parametrize('priced', [False, True])
async def test_real_vendor_outbox_and_learning_survive_ledger_outage_without_buying_again(database, monkeypatch, priced):
    import httpx
    from sources.trial import run_trial
    from sources.vendor_ledger import PLATFORM_TENANT
    monkeypatch.setenv('CONTEXT_DEV_API_KEY', 'placeholder-offline-only')
    monkeypatch.setenv('TANK_KEY', 'placeholder-offline-room')
    monkeypatch.setenv('TANK_URL', 'http://127.0.0.1:8141')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA agent_base')
        await room.ensure_tables(conn)
        task = await room.insert_batch(conn, UUID(PLATFORM_TENANT), 'fixture', 'receipt proof',
                                       [{'name': 'Recorded Business'}], '', False, None, 1, None)
        await conn.execute("UPDATE agent_base.tasks SET status='done' WHERE id=$1", task['id'])
        record = await conn.fetchval("UPDATE agent_base.records SET status='done' WHERE task_id=$1 RETURNING id", task['id'])
    requests = []
    ledger_available = False

    def respond(request):
        requests.append(request.url.path)
        if request.url.path == '/v1/paid-steps/admit':
            return httpx.Response(200, json={'approval_id': None, 'mode': 'automatic'})
        if request.url.host == 'api.context.dev':
            return httpx.Response(200, headers={'X-Credits-Used': '10'}, json={
                'status': 'ok', 'brand': {'domain': 'business.example', 'title': 'Recorded Business'}})
        assert request.url.path == '/v1/base-product/context-dev'
        if not ledger_available:
            return httpx.Response(503)
        body = json.loads(request.content)
        return httpx.Response(200, json={'ledger_id': body['id'], 'recorded': True,
            **({'cost_usd': '0.125', 'cost_status': 'set'} if priced else {})})

    records = [{'record_id': str(record), 'public': True, 'name': 'Recorded Business',
                'checked_answers': {'website': 'https://business.example'},
                'label_source': 'Recorded official evidence'}]
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        with pytest.raises(RuntimeError, match='ledger unavailable'):
            await run_trial(database, http, PLATFORM_TENANT, str(task['id']), records)
        ledger_available = True
        first = await run_trial(database, http, PLATFORM_TENANT, str(task['id']), records)
        assert first['records_sent'] == 0 and first['results'][0]['lessons'] == 1
        assert first['results'][0]['receipt']['cost_usd'] == ('0.125' if priced else None)
        async with database.acquire() as conn:
            await conn.execute("UPDATE agent_base.records SET profile=$2::jsonb WHERE id=$1", record,
                               json.dumps({'website': {'value': 'https://changed.example'}}))
        second = await run_trial(database, http, PLATFORM_TENANT, str(task['id']), records)
        assert second['results'][0]['lessons'] == 1
    assert requests.count('/v1/brand/retrieve') == 1
    async with database.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_base.context_dev_calls WHERE posted') == 1
        saved = await conn.fetchval("SELECT passes->'context_dev_learning' FROM agent_base.records WHERE id=$1", record)
        assert json.loads(saved)['code'] == {}


@pytest.mark.parametrize('change', ['stale', 'date_mismatch', 'source', 'duplicate'])
def test_run_refuses_stale_misdated_unofficial_or_duplicate_sources(recorded, change):
    source = {**recorded}
    today = TODAY
    if change == 'stale':
        today = date(2026, 11, 7)
    elif change == 'date_mismatch':
        source['published_on'] = '2025-09-02'
    elif change == 'source':
        source['source_url'] = 'https://untrusted.example/0925-ffl-list-complete.txt'
    else:
        source['rows'] = [recorded['rows'][0], recorded['rows'][0]]
    with pytest.raises(ValueError):
        training.plan(source, today=today)


@pytest.mark.parametrize('url', ['https://tank.tervory.com', 'http://192.0.2.1', 'http://tank:8000'])
def test_command_never_targets_a_tervory_server_or_remote_database(url):
    with pytest.raises(ValueError):
        training.local_service(url)
    assert training.local_service('http://127.0.0.1:8000') == 'http://127.0.0.1:8000'


class RecordedSkills:
    def __init__(self, *, blocked=False):
        self.versions = {skill: '1.0.0' for skill in [*BASE_CORE, 'ffl.ingest', 'ffl.profile']}
        self.versions.update({'base.extract': '2.0.0', 'base.business_data': '2.0.0', 'ffl.ingest': '1.0.1'})
        self.attempted = []
        self.first = None
        self.blocked = blocked

    async def pin(self, preview, engine):
        assert preview is False and engine == 'ffl'
        return self.versions, {skill: skill + '@' + version for skill, version in self.versions.items()}

    def bind(self, versions, preview, tenant):
        async def call(skill, payload):
            if skill == 'ffl.ingest':
                return {**await INGEST.run(payload, None), '_cost_usd': 0}
            if skill == 'base.find_site':
                ident = payload['_base_record_id']
                self.first = self.first or ident
                self.attempted.append(ident)
                if self.blocked and ident != self.first:
                    await asyncio.Event().wait()
            result = _scripted(skill, payload)
            return {**result, '_cost_usd': 0, '_skill': skill + '@' + versions[skill]}
        return call


@pytest.mark.asyncio
async def test_real_small_state_runs_through_worker_and_resume_never_replays_completed_records(database, recorded, tmp_path, monkeypatch):
    monkeypatch.setattr(room, 'publish', AsyncMock())
    skills = RecordedSkills(blocked=True)
    job = asyncio.create_task(training.execute(database, skills, recorded, tmp_path, states={'DC'}, today=TODAY))

    async def one_saved():
        while True:
            async with database.acquire() as conn:
                exists = await conn.fetchval("SELECT to_regclass('agent_base.records') IS NOT NULL")
                if exists and await conn.fetchval("SELECT count(*) FROM agent_base.records WHERE status='done'") == 1:
                    return
            if job.done():
                await job
                raise AssertionError('recorded state unexpectedly finished before interruption')
            await asyncio.sleep(0.01)

    try:
        await asyncio.wait_for(one_saved(), 15)
    finally:
        job.cancel()
        with pytest.raises(asyncio.CancelledError):
            await job
    first = skills.first
    skills.blocked = False
    result = await training.execute(database, skills, recorded, tmp_path, states={'DC'}, today=TODAY)
    assert result['done'] == result['records'] == 4 and result['failed'] == 0
    assert result['states'] == 1 and result['complete'] is False
    assert result['model_spend'] == 0 and skills.attempted.count(first) == 1
    run_dir = tmp_path / result['run_id']
    state = json.loads((run_dir / 'DC.json').read_text())
    assert state['source_sha256'] == recorded['sha256']
    assert state['total'] == state['done'] == 4
    assert state['refs']['base.extract'] == 'base.extract@2.0.0'
    assert (run_dir / 'gold-candidates.json').is_file()
    attempted = len(skills.attempted)
    again = await training.execute(database, skills, recorded, tmp_path, states={'DC'}, today=TODAY)
    assert again == result and len(skills.attempted) == attempted
    async with database.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_base.records') == 4
        assert await conn.fetchval("SELECT count(*) FROM agent_base.tasks WHERE task_type='base.training'") == 1


@pytest.mark.asyncio
async def test_training_refuses_model_skill_versions_before_any_state_is_queued(database, recorded, tmp_path):
    skills = RecordedSkills()
    skills.versions['base.extract'] = '1.0.0'
    with pytest.raises(ValueError, match='code-only'):
        await training.execute(database, skills, recorded, tmp_path, states={'DC'}, today=TODAY)
    async with database.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_base.tasks') == 0
