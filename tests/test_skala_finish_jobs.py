import asyncio
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

import gold
import skala_intake
import training
from test_skala_approval_safety import database as _database

database = _database
NOW = datetime(2026, 11, 7, 6, tzinfo=timezone.utc)


@pytest.mark.asyncio
@pytest.mark.parametrize('database_failure', [False, True])
async def test_intake_recovers_after_long_room_startup(monkeypatch, database_failure):
    app = FastAPI()
    finished = asyncio.Event()
    attempts, delays = [], []
    real_sleep = asyncio.sleep

    async def stage(tank):
        attempts.append(1)
        if database_failure and len(attempts) == 1:
            raise ConnectionError('offline database unavailable')
        if len(attempts) <= 12:
            return ['trigger.languagetool']
        finished.set()
        return []

    async def sleep(delay):
        delays.append(delay)
        await real_sleep(0)

    monkeypatch.setattr(skala_intake, 'stage_ready', stage)
    monkeypatch.setattr(skala_intake.asyncio, 'sleep', sleep)
    skala_intake.install(app, SimpleNamespace())
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(finished.wait(), 2)
    assert len(attempts) == 13
    assert delays == [30] * 12


@pytest.mark.asyncio
async def test_intake_stops_before_database_closes(monkeypatch):
    app = FastAPI()
    sleeping = asyncio.Event()
    stopped = []

    async def stage(tank):
        return ['trigger.languagetool']

    async def sleep(delay):
        sleeping.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.append('worker')

    async def close_pool():
        stopped.append('pool')

    app.router.on_shutdown.append(close_pool)
    monkeypatch.setattr(skala_intake, 'stage_ready', stage)
    monkeypatch.setattr(skala_intake.asyncio, 'sleep', sleep)
    skala_intake.install(app, SimpleNamespace())
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(sleeping.wait(), 2)
    assert stopped == ['worker', 'pool']


def candidate(room, number=1, **changes):
    return {'skill_id': room + '.finish', 'region': 'us-east', 'public': True,
            'label_source': room + ':offline-record', 'input': {'record': number},
            'expected': {'verified': True}, **changes}


def room_runtime(database, monkeypatch, handler):
    runtime = SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east')
    monkeypatch.setattr(training, 'runtime', lambda: runtime)
    monkeypatch.setattr(gold, 'runtime', lambda: runtime)
    monkeypatch.setattr(training, 'ROOMS', ('base', 'tiger'))
    monkeypatch.setattr(training, 'skill_owners', lambda: {'base.finish': {'base'}, 'tiger.finish': {'tiger'}})
    for room in ('BASE', 'TIGER'):
        monkeypatch.setenv('TANK_KEY_' + room, 'offline-placeholder')
    client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(handler), **kw))
    return runtime


async def completed(database):
    return await database.fetch('SELECT detail FROM tank.policy_log WHERE task_type=\'training.schedule\' AND action=\'complete\'')


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['http', 'malformed', 'storage'])
async def test_gold_schedule_retries_partial_sources_and_records_one_completion(database, monkeypatch, failure):
    recovered = False
    requests = []
    def response(request):
        room = request.url.host.removeprefix('agent-')
        requests.append(room)
        assert request.headers['X-Tank-Key'] == 'offline-placeholder'
        assert request.url.path == '/gold/candidates'
        if room == 'tiger' and not recovered:
            if failure == 'http':
                return httpx.Response(503)
            if failure == 'malformed':
                return httpx.Response(200, content=b'{invalid')
        return httpx.Response(200, json=[candidate(room)])

    room_runtime(database, monkeypatch, response)
    settle = gold.settle_auto_source
    async def settlement(conn, row):
        if failure == 'storage' and row['skill_id'] == 'tiger.finish' and not recovered:
            raise ConnectionError('offline transient storage failure')
        return await settle(conn, row)
    monkeypatch.setattr(gold, 'settle_auto_source', settlement)
    await training.scheduled_once('gold', NOW)
    assert await completed(database) == []
    rows = await database.fetch('SELECT skill_id FROM tank.gold_examples')
    assert [r['skill_id'] for r in rows] == ['base.finish']
    recovered = True
    await training.scheduled_once('gold', NOW)
    rows = await database.fetch('SELECT skill_id,tenant_id,region,status FROM tank.gold_examples ORDER BY skill_id')
    assert [r['skill_id'] for r in rows] == ['base.finish', 'tiger.finish']
    assert all(r['tenant_id'] == gold.PLATFORM_TENANT and r['region'] == 'us-east' and r['status'] == 'candidate' for r in rows)
    receipts = await completed(database)
    assert len(receipts) == 1
    assert json.loads(receipts[0]['detail']) == {'operation': 'gold', 'region': 'us-east',
        'slot': '2026-11-07T02:00:00+00:00', 'tenant_id': str(gold.PLATFORM_TENANT)}
    before = list(requests)
    await training.scheduled_once('gold', NOW)
    assert requests == before  # A new worker observes the committed receipt.
    assert len(await completed(database)) == 1


@pytest.mark.asyncio
async def test_gold_rejects_invalid_rows_without_losing_valid_source_work(database, monkeypatch):
    def response(request):
        room = request.url.host.removeprefix('agent-')
        return httpx.Response(200, json=[candidate(room), candidate(room, 2, public=False),
            candidate(room, 3, region='za'), candidate(room, 4, tenant_id='00000000-0000-0000-0000-000000000099')])
    room_runtime(database, monkeypatch, response)
    stats = await training.collect_room_gold(NOW.date())
    assert stats == {'inserted': 2, 'rejected': 6, 'capped': 0, 'duplicates': 0, 'rejected_responses': 0, 'unavailable': 0}
    second = await training.collect_room_gold(NOW.date())
    assert second['inserted'] == 0 and second['duplicates'] == 2
    assert await database.fetchval('SELECT count(*) FROM tank.gold_examples') == 2
    assert await database.fetchval('SELECT count(*) FROM tank.training_pairs') == 0


@pytest.mark.asyncio
async def test_gold_receipt_counts_only_committed_rows(database, monkeypatch):
    room_runtime(database, monkeypatch, lambda request: httpx.Response(200, json=[candidate('base')]))
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    # A deferred constraint fails when the outer room transaction commits,
    # after the row was inserted and its savepoint released.
    await database.execute('''CREATE FUNCTION tank.finish_commit_failure() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'offline commit failure'; END $$;
        CREATE CONSTRAINT TRIGGER finish_fail AFTER INSERT ON tank.gold_examples
        DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION tank.finish_commit_failure();''')
    stats = await training.collect_room_gold(NOW.date())
    assert stats['inserted'] == 0 and stats['unavailable'] == 1
    assert await database.fetchval('SELECT count(*) FROM tank.gold_examples') == 0
    await database.execute('DROP TRIGGER finish_fail ON tank.gold_examples')
    recovered = await training.collect_room_gold(NOW.date())
    assert recovered['inserted'] == 1 and recovered['unavailable'] == 0


@pytest.mark.asyncio
async def test_trigger_package_gold_can_be_reviewed_without_models(database, tmp_path, monkeypatch):
    from fastapi import HTTPException
    from test_skala_approval_safety import package
    runtime = room_runtime(database, monkeypatch, lambda request: httpx.Response(500))
    pkg = package(tmp_path, skill='trigger.finish')
    pkg.agent = 'trigger'
    runtime._packages = {(pkg.id, pkg.version): pkg}
    await gold.import_packages()
    await gold.import_packages()
    founder = gold.Reviewer('founder', gold.PLATFORM_TENANT, True)
    reviewer = gold.Reviewer('reviewer', gold.PLATFORM_TENANT, False)
    with pytest.raises(HTTPException):
        await gold.next_example('trigger', pkg.id, actor=reviewer)
    checked = 0
    while example := await gold.next_example('trigger', pkg.id, actor=founder):
        await gold.check(example['id'], gold.Verdict(action='right'), actor=founder)
        checked += 1
    assert checked == len(pkg.cases)
    assert await database.fetchval('SELECT count(*) FROM tank.gold_examples') == len(pkg.cases)
    eligible = await database.fetchval('SELECT count(*) FROM tank.gold_examples WHERE NOT holdout')
    assert eligible > 0
    assert await database.fetchval('SELECT count(*) FROM tank.training_pairs WHERE agent=\'trigger\'') == eligible


@pytest.mark.asyncio
async def test_private_export_retries_without_repeating_completed_agents(database, monkeypatch):
    import base64
    from unittest.mock import AsyncMock
    from uuid import UUID
    recovered = False
    committed = []
    datasets = {}
    def response(request):
        assert request.url.host == 'huggingface.co'
        assert request.headers['Authorization'] == 'Bearer offline-placeholder'
        if request.url.path == '/api/repos/create':
            assert json.loads(request.content)['private'] is True
            return httpx.Response(201)
        if request.method == 'GET':
            return httpx.Response(200, json={'private': True})
        assert request.url.path.endswith('/commit/main')
        agent = request.url.path.split('/tervory-public-')[1].split('/')[0]
        if agent == 'trigger' and not recovered:
            return httpx.Response(503)
        committed.append(agent)
        operations = [json.loads(line) for line in request.content.splitlines()]
        datasets[agent] = {item['value']['path']: [json.loads(line) for line in base64.b64decode(item['value']['content']).splitlines()]
                           for item in operations if item['key'] == 'file'}
        return httpx.Response(200, json={'commitOid': 'offline-commit'})
    room_runtime(database, monkeypatch, response)
    archive = AsyncMock()
    monkeypatch.setattr(training, 'archive_training_snapshot', archive)
    monkeypatch.setenv('HF_TOKEN', 'offline-placeholder')
    monkeypatch.setenv('HF_ORG', 'offline-org')
    for agent in ('base', 'trigger'):
        for label, changes in [('public', {}), ('held', {'holdout': True}),
                               ('private', {'public': False}), ('region', {'region': 'za'}),
                               ('tenant', {'tenant': UUID('00000000-0000-0000-0000-000000000099')})]:
            await training.save_pair(database, **{
                'tenant': gold.PLATFORM_TENANT, 'agent': agent, 'task': agent + '.finish',
                'value': {'record': label}, 'output': {'verified': True}, 'approved_by': 'reviewer',
                'source': 'offline', 'ref': agent + ':' + label, 'public': True, **changes})
    with pytest.raises(RuntimeError, match='Private dataset commit failed'):
        await training.scheduled_once('export', NOW)
    assert committed == ['base']
    assert await completed(database) == []
    assert await database.fetchval('SELECT count(*) FROM tank.training_exports') == 1
    recovered = True
    await training.scheduled_once('export', NOW)
    assert committed == ['base', 'trigger']
    assert await database.fetchval('SELECT count(*) FROM tank.training_exports') == 2
    assert len(await completed(database)) == 1
    for files in datasets.values():
        assert [r['input']['record'] for r in files['snapshots/us-east/2026-11-07.jsonl']] == ['public']
        assert [r['input']['record'] for r in files['holdouts/us-east/2026-11-07.jsonl']] == ['held']
        assert all('tenant_id' not in row and row['region'] == 'us-east' for rows in files.values() for row in rows)
    await training.scheduled_once('export', NOW)
    assert committed == ['base', 'trigger']
    assert archive.await_count == 3


@pytest.mark.asyncio
async def test_weekly_retest_records_real_code_score_and_keeps_holdouts_out(database, tmp_path, monkeypatch):
    from test_skala_approval_safety import package, seed
    runtime = room_runtime(database, monkeypatch, lambda request: httpx.Response(500))
    pkg = package(tmp_path)
    (pkg.path / 'run.py').write_text("async def run(payload, ctx):\n    return {'ok': payload['n'] != 0}\n")
    await seed(database, pkg, 'approved', runs=0)
    contexts = []
    runtime.get_package = lambda *args: pkg
    def make_ctx(package, tenant, **kwargs):
        contexts.append(tenant)
        return SimpleNamespace()
    runtime.make_ctx = make_ctx
    for n in range(5):
        row = await gold.add_candidate(database, tenant=gold.PLATFORM_TENANT, skill=pkg.id,
            agent=pkg.agent, value={'n': n}, expected={'ok': True}, source='offline', ref=str(n))
        await database.execute("UPDATE tank.gold_examples SET status='checked',holdout=$2 WHERE id=$1", row, n == 4)
    await database.execute('''INSERT INTO tank.gold_scores(tenant_id,region,skill_id,version,score,n,ran_at)
        VALUES($1,'us-east',$2,$3,1,4,'2026-10-01')''', gold.PLATFORM_TENANT, pkg.id, pkg.version)
    await training.scheduled_once('retest', NOW)
    scores = await database.fetch('SELECT score,n FROM tank.gold_scores ORDER BY ran_at')
    assert [(float(r['score']), r['n']) for r in scores] == [(1, 4), (.75, 4)]
    assert contexts == [gold.PLATFORM_TENANT] * 4
    summary = await gold.summary(gold.Reviewer('founder', gold.PLATFORM_TENANT, True))
    assert summary['skills'][0]['drop'] is True
    assert summary['skills'][0]['trend'] == -.25
    await training.scheduled_once('retest', NOW)
    assert len(contexts) == 4 and len(await completed(database)) == 1


@pytest.mark.asyncio
async def test_scheduled_session_lock_does_not_hold_a_scoped_transaction(database, monkeypatch):
    from tenant_db import TenantPool
    runtime = SimpleNamespace(pool=lambda: TenantPool(database), admin_pool=lambda: database,
                              box_region=lambda: 'us-east')
    monkeypatch.setattr(training, 'runtime', lambda: runtime)
    calls = []

    async def collect(day):
        calls.append(day)
        async with database.acquire() as conn:
            await asyncio.wait_for(conn.execute(
                'CREATE INDEX CONCURRENTLY schedule_snapshot_probe ON tank.policy_log(action)'), 10)
        return {'unavailable': 0, 'rejected_responses': 0}

    monkeypatch.setattr(training, 'collect_room_gold', collect)
    await asyncio.wait_for(training.scheduled_once('gold', NOW), 15)
    await training.scheduled_once('gold', NOW)
    assert calls == [training.scheduled_slot('gold', NOW).date()]
    assert len(await completed(database)) == 1
