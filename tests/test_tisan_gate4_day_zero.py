"""New-client views and receipts remain empty even when another tenant has work."""
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4
from unittest.mock import AsyncMock, Mock
from urllib.parse import urlsplit

import pytest
import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agents.tisan import archive, gold_sources, promotion, promotion_api, publish
from chassis.tenant_db import bind_tenant_endpoints, tenant_scope
from test_tisan_quotes_designed import api as quote_api, database as database, HEADERS, designed
from test_tisan_quotes import A, B
from test_tisan_gold_sources import setup as gold_setup, approve
from test_tisan_publish import build, TENANT
from test_command import command_pool as command_pool
from test_tisan_finish_sources import wire_storage

ROOT = Path(__file__).resolve().parents[1]


def test_all_client_empty_views_show_real_zero_counts_and_existing_first_actions():
    result = subprocess.run(['node', str(ROOT / 'tests/tisan_gate4_day_zero.cjs')],
                            cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '11 empty client views' in result.stdout


@pytest.mark.asyncio
async def test_fresh_tenant_lists_counts_and_receipts_never_borrow_another_clients_data(quote_api, tmp_path, monkeypatch):
    client, store, admin, app = quote_api
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    await admin.execute(gold_sources.SCHEMA)
    await admin.execute('GRANT SELECT ON agent_tisan.page_approvals TO agent_tisan')
    gold_sources.mount(app)
    promotion_api.mount(app, promotion)
    publish.mount(app, promotion)
    with tenant_scope(A):
        foreign = await store.create(A, 'placeholder-founder', designed(), submitted=True)
    journal = promotion.Journal(tmp_path / 'promotion.sqlite3')
    journal.register(str(A), 'site', {'staging': 'placeholder-stage', 'production': 'placeholder-prod',
                                    'url': 'https://placeholder-stage.invalid/'})
    ident = str(uuid4())
    journal.reserve(str(A), 'site', ident, 'publish', 'placeholder-founder', 'build:1')
    journal.update(str(A), 'site', ident, 'succeeded', {'expected': 'build:1',
                   'commit': 'a' * 40, 'url': 'https://placeholder-stage.invalid/'}, terminal=True)
    bind_tenant_endpoints(app)
    for path in ('/gold/pages', '/gold/candidates', '/quotes', '/promotion/history'):
        response = await client.get(path, headers=HEADERS, params={'tenant_id': str(B), 'site': 'site'})
        assert response.status_code == 200, response.text
        assert response.json() == []
    latest = await client.get('/publish/latest', headers=HEADERS, params={'tenant_id': str(B), 'slug': 'site'})
    assert latest.status_code == 200 and latest.json() == {'status': 'unavailable'}
    absent = await client.get('/quotes/' + str(foreign['id']), headers=HEADERS, params={'tenant_id': str(B)})
    assert absent.status_code == 404
    with tenant_scope(B):
        async with store.pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM agent_tisan.quote_requests') == 0
            assert await conn.fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 0
    # The private operation exists for its actual owner only.
    assert len(journal.history(str(A), 'site')) == 1
    assert journal.history(str(B), 'site') == []
    assert not (tmp_path / 'builds' / str(B)).exists()


def test_incomplete_review_evidence_keeps_the_existing_refusal_instead_of_claiming_an_empty_account(gold_setup):
    client, headers, root = gold_setup
    assert approve(client, headers).status_code == 200
    tenant = gold_sources.PLATFORM_TENANT
    frame = root / 'readings' / tenant / 'frame.json'
    data = json.loads(frame.read_text())
    data['visual'] = []
    frame.write_text(json.dumps(data))
    for path in ('/gold/pages', '/gold/candidates'):
        response = client.get(path, headers=headers, params={'tenant_id': tenant})
        assert response.status_code == 422
        assert response.json() == {'detail': 'frame data incomplete'}


@pytest.mark.asyncio
async def test_actual_room_starts_with_core_only_and_blocks_unconfigured_sources(command_pool, tmp_path, monkeypatch):
    from agents.tisan import app as room
    from agents.tisan import runtime
    database_name = 'tisan_gate4_' + uuid4().hex
    async with command_pool.acquire() as conn:
        await conn.execute('CREATE DATABASE ' + database_name)
    base = urlsplit(os.environ['POOL_SCHEMA_DATABASE_URL'])
    assert base.hostname in {'127.0.0.1', 'localhost'}
    monkeypatch.setenv('DATABASE_URL', base._replace(path='/' + database_name).geturl())
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.delenv('CHASSIS_ADMIN_DATABASE_URL', raising=False)
    monkeypatch.delenv('CHASSIS_RLS_ADMIN_ROLE', raising=False)
    for name in {name for names in runtime.CAPABILITIES.values() for name in names} - set(runtime.CORE):
        monkeypatch.delenv(name, raising=False)
    try:
        with TestClient(room.app) as client:
            assert client.get('/health').status_code == 200
            report = client.get('/readiness').json()
            assert report['ok'] is True
            assert all(not value['ready'] for value in report['capabilities'].values())
            for method, path, body in [
                ('POST', '/pipeline/start', {}), ('POST', '/publish/build', {}),
                ('POST', '/promotion/promote', {}), ('POST', '/promotion/rollback', {}),
                ('GET', '/storage/usage', None), ('GET', '/quotes', None),
                ('POST', '/jobs', {'kind': 'archive', 'input': {'slug': 'site', 'build': 1}}),
            ]:
                response = client.request(method, path, json=body)
                assert response.status_code == 503
                assert response.json()['missing_settings']
    finally:
        async with command_pool.acquire() as conn:
            await conn.execute('DROP DATABASE ' + database_name)
    assert room.app.state.tisan_active is False


@pytest.mark.asyncio
async def test_rls_missing_admin_bindings_start_blocked_without_opening_worker_pools(command_pool, tmp_path, monkeypatch):
    from agents.tisan import app as room
    import chassis.app
    async with command_pool.acquire() as conn:
        name = await conn.fetchval('SELECT current_database()')
        await conn.execute('CREATE SCHEMA agent_tisan; CREATE TABLE agent_tisan.placeholder_probe (id int); '
                           'ALTER TABLE agent_tisan.placeholder_probe ENABLE ROW LEVEL SECURITY')
    base = urlsplit(os.environ['POOL_SCHEMA_DATABASE_URL'])
    assert base.hostname in {'127.0.0.1', 'localhost'}
    monkeypatch.setenv('DATABASE_URL', base._replace(path='/' + name).geturl())
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    for setting in ('CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE'):
        monkeypatch.delenv(setting, raising=False)
    pools = AsyncMock(side_effect=AssertionError('worker pools forbidden'))
    monkeypatch.setattr(chassis.app.asyncpg, 'create_pool', pools)
    with TestClient(room.app) as client:
        response = client.get('/health')
        assert response.status_code == 503
        assert response.json()['missing_settings'] == ['CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE']
        pools.assert_not_awaited()
    async with command_pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database()") == 1


def test_archive_one_command_dry_run_validates_real_bytes_and_writes_nothing(tmp_path, monkeypatch, capsys):
    contents, _ = build(tmp_path)
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    outgoing = Mock(side_effect=AssertionError('provider use forbidden'))
    monkeypatch.setattr(archive, 'Storage', outgoing)
    monkeypatch.setattr(archive, 'MemoryClient', outgoing)
    monkeypatch.setattr(sys, 'argv', ['archive.py', '--tenant', TENANT, '--slug', 'site', '--build', '1', '--dry-run'])
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    archive.main()
    report = json.loads(capsys.readouterr().out)
    assert report['dry_run'] is True and report['ready'] is True and report['uploaded'] is False
    assert report['tenant_id'] == TENANT and report['files'] == len(contents)
    assert len(report['archive_sha256']) == 64
    assert {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before
    outgoing.assert_not_called()


@pytest.mark.parametrize('setting', ['DATA_DIR', 'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TISAN', 'R2_SECRET_ACCESS_KEY_TISAN'])
def test_archive_launch_names_each_missing_setting_without_constructing_a_client(tmp_path, monkeypatch, capsys, setting):
    for name in ('DATA_DIR', 'R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TISAN', 'R2_SECRET_ACCESS_KEY_TISAN'):
        monkeypatch.setenv(name, str(tmp_path) if name == 'DATA_DIR' else 'placeholder')
    monkeypatch.delenv(setting)
    outgoing = Mock(side_effect=AssertionError('provider use forbidden'))
    monkeypatch.setattr(archive, 'Storage', outgoing)
    monkeypatch.setattr(sys, 'argv', ['archive.py', '--tenant', TENANT, '--slug', 'site', '--build', '1'])
    with pytest.raises(SystemExit) as stopped:
        archive.main()
    assert stopped.value.code == 1
    output = capsys.readouterr()
    assert output.out == '' and output.err == 'Missing settings: ' + setting + '\n'
    assert list(tmp_path.iterdir()) == []
    outgoing.assert_not_called()


def test_dry_run_refuses_failed_or_missing_real_builds(tmp_path):
    with pytest.raises(OSError):
        archive.dry_run(TENANT, {'slug': 'site', 'build': 1}, root=tmp_path)
    build(tmp_path, passed=False)
    with pytest.raises(ValueError, match='did not pass'):
        archive.dry_run(TENANT, {'slug': 'site', 'build': 1}, root=tmp_path)
    assert not list(tmp_path.rglob('*.archive.json'))


@pytest.mark.asyncio
@pytest.mark.parametrize('setting', ['HERMES_URL', 'TANK_KEY'])
async def test_missing_memory_setting_keeps_verified_archive_but_never_dials_a_default(tmp_path, monkeypatch, setting):
    build(tmp_path)
    wire_storage(monkeypatch)
    for name in ('HERMES_URL', 'TANK_KEY'):
        monkeypatch.setenv(name, 'placeholder')
    monkeypatch.delenv(setting)
    outgoing = Mock(side_effect=AssertionError('unconfigured memory use forbidden'))
    monkeypatch.setattr(archive, 'MemoryClient', outgoing)
    result = await archive.export(TENANT, {'slug': 'site', 'build': 1}, root=tmp_path)
    assert result['ok'] is True and result['memory'] == 'not_configured'
    assert result['missing_settings'] == [setting] and 'memory_id' not in result
    assert json.loads((tmp_path / 'builds' / TENANT / 'site/1.archive.json').read_text()) == result
    outgoing.assert_not_called()


@pytest.mark.asyncio
async def test_empty_storage_returns_measured_zero_counts_and_no_objects(monkeypatch):
    from chassis import storage_api
    from chassis.storage import Storage
    calls = []
    def respond(request):
        assert request.method == 'GET' and request.url.host == '0' * 32 + '.r2.cloudflarestorage.com'
        calls.append(request.url)
        return httpx.Response(200, content=b'<ListBucketResult><IsTruncated>false</IsTruncated></ListBucketResult>')
    settings = {'AGENT_NAME': 'tisan', 'TANK_REGION': 'us-east', 'R2_ACCOUNT_ID': '0' * 32,
                'R2_ACCESS_KEY_ID_TISAN': 'placeholder', 'R2_SECRET_ACCESS_KEY_TISAN': 'placeholder'}
    monkeypatch.setattr(storage_api, 'Storage', lambda owner: Storage(owner, environ=settings,
                                                                     transport=httpx.MockTransport(respond)))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    app = FastAPI()
    app.include_router(storage_api.storage_router('tisan'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-room') as client:
        usage = await client.get('/storage/usage', headers={'X-Tank-Key': 'placeholder-room-key'})
        assert usage.status_code == 200
        assert usage.json()['used_bytes'] == 0 and usage.json()['objects'] == 0
        assert usage.json()['measured_at']
        objects = await client.get('/storage/objects/work', params={'tenant_id': TENANT},
                                   headers={'X-Tank-Key': 'placeholder-room-key'})
        assert objects.status_code == 200 and objects.json() == []
    assert len(calls) == 2


def test_saturday_command_has_no_implicit_live_launch():
    for args in ([], ['--live'], ['--dry-run', '--live']):
        result = subprocess.run([str(ROOT / 'scripts/saturday.sh'), *args], cwd=ROOT,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 2
        assert result.stderr.strip() == 'Usage: scripts/saturday.sh --dry-run'
        assert result.stdout == ''
