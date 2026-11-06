import json
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from test_tiger import ROOT, TENANT_A, TENANT_B, NOW, _load, _watch
from batch import job_id
from operations import preview
from tiger_sheet.test_finish_batch import BATCH, URL
from test_tiger_competitors import database as database, postgres as postgres


def command(script, args):
    result = subprocess.run([sys.executable, str(ROOT/'agents/tiger'/script), *args],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_batch_command_replays_real_flow_and_resume_without_touching_live_files(tmp_path):
    rows = [{'id': 'first', 'state': 'WY', 'product_urls': [URL]},
            {'id': 'second', 'state': 'CA'}, {'id': 'third', 'state': 'CA'}]
    source, responses = tmp_path/'input.jsonl', tmp_path/'responses.json'
    source.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    ident = str(job_id(TENANT_A, BATCH, 'first', URL))
    responses.write_text(json.dumps([{'method': 'POST', 'path': '/batch/check', 'status': 201,
        'body': {'tenant_id': TENANT_A, 'batch_id': BATCH, 'record_id': 'first', 'url': URL, 'retry_failed': False},
        'json': {'id': ident, 'tenant_id': TENANT_A, 'status': 'done', 'result': {
            'status': 'observed', 'observation': {'id': 'placeholder-observation', 'ts': NOW.isoformat(),
            'tenant_id': TENANT_A, 'url': URL, 'price': '12', 'currency': 'USD'}}}}]))
    checkpoint, receipts = tmp_path/'live.sqlite', tmp_path/'live.jsonl'
    checkpoint.write_bytes(b'placeholder untouched database')
    receipts.write_text('placeholder untouched receipts')
    result = command('batch.py', ['--dry-run', '--smallest-state', '--responses', str(responses),
        '--input', str(source), '--tenant', TENANT_A, '--batch', BATCH,
        '--checkpoint', str(checkpoint), '--receipts', str(receipts)])
    assert result['dry_run'] and result['records'] == 1 and result['states'] == {'WY': 1}
    assert result['replayed'] == 1 and result['resume_verified']
    assert checkpoint.read_bytes() == b'placeholder untouched database'
    assert receipts.read_text() == 'placeholder untouched receipts'


def test_batch_missing_setting_is_named_before_any_work(tmp_path, monkeypatch):
    monkeypatch.delenv('TIGER_BATCH_URL', raising=False)
    source = tmp_path/'input.csv'
    source.write_text('record_id,state,website\none,WY,https://placeholder.example\n')
    result = command('batch.py', ['--input', str(source), '--tenant', TENANT_A, '--batch', BATCH,
        '--checkpoint', str(tmp_path/'new.sqlite'), '--receipts', str(tmp_path/'receipts')])
    assert result == {'status': 'not_configured', 'settings': ['TIGER_BATCH_URL']}
    assert sorted(path.name for path in tmp_path.iterdir()) == ['input.csv']


def test_batch_77000_command_plans_all_groups_and_missing_sources(tmp_path):
    source = tmp_path/'input.csv'
    source.write_text('record_id,state,website\n' + ''.join(f'{i},{"WY" if i < 10 else "CA"},\n' for i in range(77000)))
    result = command('batch.py', ['--dry-run', '--input', str(source), '--tenant', TENANT_A, '--batch', BATCH,
        '--checkpoint', str(tmp_path/'new.sqlite'), '--receipts', str(tmp_path/'receipts')])
    assert result['records'] == 77000 and result['missing_sources'] == 77000
    assert result['product_pages'] == 0 and result['discovery_sites'] == 0
    assert not (tmp_path/'new.sqlite').exists()


def snapshot():
    watches = [_watch(), {**_watch(), 'url': URL, 'enabled': False},
               {**_watch(), 'url': URL + '/busy'}, {**_watch(), 'url': URL + '/fresh'}]
    return {'tenant_id': TENANT_A, 'watches': watches, 'open_jobs': [URL + '/busy'],
            'observations': [{'url': URL + '/fresh', 'ts': NOW.isoformat()}],
            'pending_mail': ['placeholder-pending'], 'rig_tenants': [TENANT_A],
            'rig_products': [{'sku': 'placeholder-item', 'url': URL}]}


def test_all_scheduled_jobs_from_one_command_are_read_only(tmp_path):
    data = snapshot()
    path = tmp_path/'snapshot.json'
    path.write_text(json.dumps(data))
    before = path.read_bytes()
    result = command('operations.py', ['--dry-run', '--snapshot', str(path), '--tenant', TENANT_A, '--at', NOW.isoformat()])
    assert result['dry_run']
    assert result['dispatch']['would_queue'] == [data['watches'][0]['url']]
    assert result['dispatch']['queued'] == []
    assert result['dispatch']['rig_products'] == 1
    assert result['dispatch']['email']['sent'] == 0
    assert result['dispatch']['email']['pending'] == 1
    assert result['rig_discover'] == {'tenants': 1}
    assert result['ping']['would_remember']
    assert path.read_bytes() == before
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.asyncio
async def test_empty_schedule_and_foreign_snapshot():
    result = await preview({'tenant_id': TENANT_A}, TENANT_A, NOW)
    assert result['dispatch']['would_queue'] == [] and result['rig_discover']['tenants'] == 0
    with pytest.raises(ValueError, match='another tenant'):
        await preview(snapshot(), TENANT_B, NOW)
    foreign = snapshot()
    foreign['watches'][0]['tenant_id'] = TENANT_B
    with pytest.raises(ValueError, match='another tenant'):
        await preview(foreign, TENANT_A, NOW)


@pytest.mark.asyncio
async def test_schedule_preview_performs_only_reads_on_real_schema(database, monkeypatch):
    import watch
    agent = _load('tiger_gate4_readonly', ROOT/'agents/tiger/app.py')
    store = watch.PgStore(database)
    await store.create_watch(_watch())
    monkeypatch.setattr(watch, 'ensure_tables', AsyncMock(side_effect=AssertionError('no dry-run DDL')))
    async with database.acquire() as conn:
        async with conn.transaction(readonly=True):
            class Pool:
                def acquire(self):
                    from contextlib import asynccontextmanager
                    @asynccontextmanager
                    async def connection():
                        yield conn
                    return connection()
            result = await agent.dry_dispatch(watch.PgStore(Pool()),
                SimpleNamespace(products=AsyncMock(return_value=[])), TENANT_A, NOW)
            assert result['would_queue'] == [_watch()['url']]
            assert await conn.fetchval('SELECT count(*) FROM agent_tiger.jobs') == 0


@pytest.mark.asyncio
async def test_real_dispatch_handler_dry_run_does_not_enqueue_or_send(monkeypatch):
    agent = _load('tiger_gate4_dispatch', ROOT/'agents/tiger/app.py')
    from operations import Snapshot
    from rig_watch import RigWatches
    store = Snapshot(snapshot(), TENANT_A)
    store.enqueue_check = AsyncMock(side_effect=AssertionError('must not queue'))
    monkeypatch.setattr(agent, 'PgStore', lambda *args: store)
    monkeypatch.setattr(agent, 'TankRig', lambda *args: SimpleNamespace(products=AsyncMock(return_value=[])))
    monkeypatch.setattr(RigWatches, 'deliver', AsyncMock(side_effect=AssertionError('must not publish')))
    agent.app.state.pool, agent.app.state.http = None, None
    result = await agent.dispatch(SimpleNamespace(tenant_id=TENANT_A, input={'dry_run': True}))
    assert result['dry_run'] and result['queued'] == []
    store.enqueue_check.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('absent', ['DATABASE_URL', 'TANK_KEY', 'DOMAIN_INTERVAL_S'])
async def test_missing_or_bad_configuration_starts_blocked_without_resources(monkeypatch, caplog, absent):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder.invalid/placeholder')
    monkeypatch.setenv('TANK_KEY', 'placeholder')
    monkeypatch.setenv('DOMAIN_INTERVAL_S', '10')
    if absent == 'DOMAIN_INTERVAL_S':
        monkeypatch.setenv(absent, 'NaN')
    else:
        monkeypatch.delenv(absent)
    agent = _load('tiger_gate4_config_' + absent, ROOT/'agents/tiger/app.py')
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def forbidden(instance):
        raise AssertionError('must not start workers, DB or HTTP clients')
        yield
    monkeypatch.setattr(agent, '_tiger_chassis', forbidden)
    async with agent.app.router.lifespan_context(agent.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app), base_url='http://placeholder') as client:
            for method, path in [('GET', '/health'), ('POST', '/jobs'), ('POST', '/batch/check'), ('GET', '/watchlist')]:
                response = await client.request(method, path)
                assert response.status_code == 503
                assert response.json()['settings'] == [absent]
    assert absent in caplog.text and 'placeholder.invalid' not in caplog.text


@pytest.mark.asyncio
async def test_storage_settings_disable_storage_before_reading_upload(monkeypatch):
    monkeypatch.setenv("TANK_KEY", "placeholder-room-key")
    from readiness import capabilities
    for name in capabilities()['storage'] + ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TIGER', 'R2_SECRET_ACCESS_KEY_TIGER']:
        monkeypatch.delenv(name, raising=False)
    agent = _load('tiger_gate4_storage', ROOT/'agents/tiger/app.py')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app), base_url='http://placeholder') as client:
        response = await client.put('/storage/objects/screenshots/placeholder', headers={'X-Tank-Key': 'placeholder-room-key'})
    assert response.status_code == 503
    assert response.json()['settings'] == ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TIGER', 'R2_SECRET_ACCESS_KEY_TIGER']


def test_browser_blank_optional_settings_use_existing_defaults(monkeypatch):
    monkeypatch.setenv('TIGER_MAX_PAGES', '')
    monkeypatch.setenv('DATA_DIR', '')
    browser = _load('tiger_gate4_browser', ROOT/'tiger/app.py')
    assert browser.MAX_PAGES == 4 and browser.DATA_DIR == '/data'
