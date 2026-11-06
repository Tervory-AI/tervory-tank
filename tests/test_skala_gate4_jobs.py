import base64
from datetime import date
from decimal import Decimal
import json
import sys
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

import gold
import storage
import training
from test_skala_approval_safety import database as _database
from test_skala_finish_jobs import room_runtime

database = _database


@pytest.mark.asyncio
async def test_dry_run_collector_reads_receipts_and_resumes(database, monkeypatch):
    room_runtime(database, monkeypatch, lambda request: httpx.Response(500))
    tenant = uuid4()
    rows = []
    for outcome, region in [('delivered', 'us-east'), ('failed', 'us-east'), ('delivered', 'za')]:
        ident = uuid4()
        rows.append(ident)
        await database.execute('''INSERT INTO tank.ledger
            (id,tenant_id,region,agent,task_type,model,rung,outcome,feedback,feedback_by,accept_after)
            VALUES($1,$2,$3,'base','base.offline','code',3,$4,'accepted','offline-reviewer',now()-interval '1 second')''',
            ident, tenant, region, outcome)
        await database.execute('''INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
            VALUES($1,$2,'base.offline',$3::jsonb,'{"answer":"verified"}')''', ident, tenant,
            json.dumps([{'role': 'user', 'content': json.dumps({'record': str(ident)})}]))
    await training.collect_once()
    await training.collect_once()
    pairs = await database.fetch('SELECT * FROM tank.training_pairs')
    assert len(pairs) == 1
    assert pairs[0]['source_ref'] == str(rows[0]) and pairs[0]['tenant_id'] == tenant
    assert pairs[0]['active'] and not pairs[0]['public'] and pairs[0]['teacher_model'] is None
    await database.execute("UPDATE tank.ledger SET feedback='rejected' WHERE id=$1", rows[0])
    await training.collect_once()
    assert await database.fetchval('SELECT count(*) FROM tank.training_pairs WHERE active') == 0
    assert await database.fetchval("SELECT count(*) FROM tank.training_pairs WHERE polarity='negative'") == 1


class Archive:
    def __init__(self):
        self.objects = {}
        self.closed = False

    async def put(self, tenant, category, name, content, *, public):
        assert tenant == str(gold.PLATFORM_TENANT) and category == 'training' and public
        self.objects[name] = content

    async def get(self, tenant, category, name, *, public):
        assert tenant == str(gold.PLATFORM_TENANT) and category == 'training' and public
        return self.objects[name]

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
@pytest.mark.parametrize('agent', ['base', 'trigger', 'tank'])
async def test_dry_run_export_archives_exact_payload_before_private_upload(database, monkeypatch, agent):
    uploaded, objects, calls = [], {}, []
    archive = Archive()
    def response(request):
        calls.append((request.method, request.url.host, request.url.path))
        if request.url.host == 'agent-base':
            assert request.headers['X-Tank-Key'] == 'offline-room-placeholder'
            assert 'Authorization' not in request.headers
            assert request.url.params['region'] == 'us-east'
            if request.method == 'PUT':
                objects[request.url.path] = request.content
                return httpx.Response(200)
            return httpx.Response(200, content=objects[request.url.path])
        assert request.url.host == 'huggingface.co'
        assert request.headers['Authorization'] == 'Bearer offline-hf-placeholder'
        assert 'X-Tank-Key' not in request.headers
        # The archive manifest has been written and verified before HF is used.
        assert any(name.endswith('/manifest.json') for name in (objects or archive.objects))
        if request.url.path == '/api/repos/create':
            assert json.loads(request.content)['private'] is True
            return httpx.Response(201)
        if request.method == 'GET':
            return httpx.Response(200, json={'private': True})
        for line in request.content.splitlines():
            item = json.loads(line)
            if item['key'] == 'file':
                uploaded.append(base64.b64decode(item['value']['content']))
        return httpx.Response(200)
    room_runtime(database, monkeypatch, response)
    monkeypatch.setattr(storage, 'uploads', lambda: archive)
    monkeypatch.setenv('TANK_KEY_BASE', 'offline-room-placeholder')
    monkeypatch.setenv('HF_TOKEN', 'offline-hf-placeholder')
    monkeypatch.setenv('HF_ORG', 'offline-org')
    await training.save_pair(database, tenant=gold.PLATFORM_TENANT, agent=agent, task=agent + '.offline',
        value={'record': 'public'}, output={'verified': True}, approved_by='offline-reviewer',
        source='offline', ref='snapshot', public=True)
    result = await training.export_once(day=date(2026, 11, 7))
    assert result == {'status': 'complete', 'exported': 1}
    assert len(uploaded) == 1
    stored = objects or archive.objects
    parts = [value for name, value in stored.items() if '/part-' in name]
    assert b''.join(parts) == uploaded[0]
    if agent == 'trigger':
        assert all(name.startswith('trigger/2026-11-07/') for name in stored)
    if agent in {'tank', 'trigger'}:
        assert archive.closed
    before = list(calls)
    assert (await training.export_once(day=date(2026, 11, 7)))['exported'] == 0
    assert calls == before
    assert await database.fetchval('SELECT count(*) FROM tank.training_exports') == 1


@pytest.mark.asyncio
async def test_missing_archive_setting_blocks_hf_and_keeps_retryable_receipt(database, monkeypatch):
    requests = []
    room_runtime(database, monkeypatch, lambda request: requests.append(request) or httpx.Response(500))
    monkeypatch.setenv('HF_TOKEN', 'offline-placeholder')
    monkeypatch.setenv('HF_ORG', 'offline-org')
    for name in ('R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_UPLOADS', 'R2_SECRET_ACCESS_KEY_UPLOADS'):
        monkeypatch.delenv(name, raising=False)
    await training.save_pair(database, tenant=gold.PLATFORM_TENANT, agent='trigger', task='trigger.offline',
        value={'record': 'public'}, output={'verified': True}, approved_by='offline-reviewer',
        source='offline', ref='snapshot', public=True)
    result = await training.export_once(day=date(2026, 11, 7))
    assert result['status'] == 'incomplete' and result['exported'] == 0
    assert result['issues'][0]['agent'] == 'trigger'
    assert 'R2_ACCOUNT_ID' in result['issues'][0]['message']
    assert requests == []
    assert await database.fetchval('SELECT count(*) FROM tank.training_exports') == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('agent,region', [('', 'us-east'), ('zenas', 'za')])
async def test_dry_run_training_start_stops_before_launch(monkeypatch, agent, region):
    from training_jobs import run
    requests = []
    class Provider:
        def __init__(self, *, token):
            assert token == 'offline-placeholder'
        def list_jobs_hardware(self):
            requests.append('price')
            return [SimpleNamespace(name='a10g-small', unit_label='minute', unit_cost_micro_usd=10000)]
        def __getattr__(self, name):
            raise AssertionError('Dry run must not call ' + name)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=Provider))
    monkeypatch.setenv('HF_TOKEN', 'offline-placeholder')
    monkeypatch.setenv('HF_ORG', 'offline-org')
    monkeypatch.setenv('HF_TRAIN_MAX_USD', '50')
    monkeypatch.setenv('TANK_REGION', region)
    args = SimpleNamespace(agent=agent, minutes=120, day='2026-11-07', submit=False, dry_run=True,
        receipt=None, job_id='', billed_usd='0')
    result = await run.run(args)
    assert result == {'status': 'ready', 'cost_usd': Decimal('1.20'), 'hardware': 'a10g-small'}
    assert requests == ['price']
    args.submit = True
    with pytest.raises(ValueError, match='Dry run cannot submit'):
        await run.run(args)
    assert requests == ['price']


@pytest.mark.asyncio
@pytest.mark.parametrize('name', ['HF_TOKEN', 'HF_ORG', 'DATABASE_URL'])
async def test_training_command_names_missing_settings_before_provider_access(monkeypatch, name):
    from training_jobs import run
    for key in ('HF_TOKEN', 'HF_ORG', 'DATABASE_URL'):
        monkeypatch.setenv(key, 'offline-placeholder')
    monkeypatch.delenv(name)
    args = SimpleNamespace(agent='', submit=True, receipt=None, job_id='', dry_run=False)
    result = await run.run(args)
    assert result['status'] == 'unconfigured' and result['missing_settings'] == [name]


def test_training_cli_rejects_dry_run_with_submit(monkeypatch):
    from skala_integrated_sources import SOURCES
    filename = next(name for name in SOURCES if name.endswith('/tank/training_jobs/run.py'))
    monkeypatch.setattr(sys, 'argv', [filename, '--dry-run', '--submit', '--day', '2026-11-07'])
    with pytest.raises(SystemExit) as rejected:
        exec(compile(SOURCES[filename], filename, 'exec'), {'__name__': '__main__', '__file__': filename})
    assert rejected.value.code == 2


@pytest.mark.asyncio
async def test_dry_run_training_receipt_records_actual_bill_once(database):
    from training_jobs import run
    await database.execute('''INSERT INTO tank.training_jobs(id,tenant_id,region,model_repo,estimated_usd)
        VALUES('offline-training-job',$1,'us-east','offline-org/offline-model',1.20)''', gold.PLATFORM_TENANT)
    async with database.acquire() as conn:
        first = await run.record_receipt(conn, 'offline-training-job', Decimal('0.75'))
        second = await run.record_receipt(conn, 'offline-training-job', Decimal('0.75'))
        with pytest.raises(ValueError, match='conflicts with recorded bill'):
            await run.record_receipt(conn, 'offline-training-job', Decimal('0.80'))
    assert first == second
    receipt = await database.fetchrow('SELECT * FROM tank.ledger WHERE id=$1', first)
    assert receipt['tenant_id'] == gold.PLATFORM_TENANT
    assert receipt['cost_usd'] == Decimal('0.75') and receipt['outcome'] == 'delivered'
    assert await database.fetchval('SELECT count(*) FROM tank.ledger') == 1
    assert await database.fetchval("SELECT actual_usd FROM tank.training_jobs WHERE id='offline-training-job'") == Decimal('0.75')
