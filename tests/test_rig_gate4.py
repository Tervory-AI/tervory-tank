"""Day-zero clients, missing settings and the executable Saturday dry run."""
from datetime import date
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from unittest.mock import AsyncMock
from urllib.parse import urlunsplit

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents/rig"))

from rigbox.configuration import GROUPS, report, startup_missing
from rigbox.dry_run import JOBS, TENANT, database, local_database, offline_network
from rigbox.retailer import Retailer
from rigbox.service import Service
from rigbox.store import PgStore
from rigbox.quotes.store import PgQuotes, EVENTS
from rigbox.three_d.store import Store as Models
from rigbox.cart import Cart
from test_rig_postgres import _admin_url

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_day_zero_database_has_no_invented_counts_lists_or_receipts():
    async with database(_admin_url()) as pool:
        store = PgStore(pool)
        await store.apply_schema()
        service = Service(store)
        panel = await Retailer(service).panel(TENANT)
        assert panel['products'] == 0
        for name in ('product_rows', 'fits', 'missed_searches', 'receipts'):
            assert panel[name] == []
        assert panel['templates'] == {}
        assert await PgQuotes(pool).analytics(TENANT, date.min) == dict.fromkeys(EVENTS, 0)
        assert await PgQuotes(pool).pending(TENANT) == []
        assert await Cart(service, AsyncMock()).rows.checkouts(TENANT) == []
        assert await Models(pool).entitlement(TENANT) is None
        assert await Models(pool).jobs(TENANT) == []
        assert await Models(pool).review_queue(TENANT) == []
        await pool.execute('ALTER TABLE agent_rig.searches ENABLE ROW LEVEL SECURITY')
        name = await pool.fetchval('SELECT current_database()')
        url = urlunsplit(local_database(_admin_url())._replace(path='/' + name))
        assert await startup_missing('rig', {'DATABASE_URL': url}) == [
            'CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE']


@pytest.mark.parametrize('group,name', [(g, n) for g, names in GROUPS.items() for n in names])
def test_each_missing_setting_is_named_without_exposing_other_values(group, name):
    env = {n: 'placeholder-private-value' for names in GROUPS.values() for n in names}
    del env[name]
    result = report(env)
    assert result[group] == {'ready': False, 'missing_settings': [name]}
    assert 'placeholder-private-value' not in json.dumps(result)


def test_existing_smtp_sender_fallback_is_not_reported_missing():
    env = {'SMTP_HOST': 'placeholder', 'SMTP_USER': 'placeholder', 'SMTP_PASSWORD': 'placeholder'}
    assert report(env)['email']['ready']
    del env['SMTP_PASSWORD']
    assert report(env)['email']['missing_settings'] == ['SMTP_PASSWORD']


@pytest.mark.asyncio
async def test_row_security_missing_admin_settings_are_reported_before_workers_start(monkeypatch):
    import asyncpg
    from types import SimpleNamespace
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=True), close=AsyncMock())
    connect = AsyncMock(return_value=conn)
    monkeypatch.setattr(asyncpg, 'connect', connect)
    env = {'DATABASE_URL': 'placeholder-database'}
    assert await startup_missing('rig', env) == ['CHASSIS_ADMIN_DATABASE_URL', 'CHASSIS_RLS_ADMIN_ROLE']
    conn.close.assert_awaited_once()
    env['CHASSIS_RLS_ADMIN_ROLE'] = 'placeholder-role'
    assert await startup_missing('rig', env) == ['CHASSIS_ADMIN_DATABASE_URL']
    env['CHASSIS_ADMIN_DATABASE_URL'] = 'placeholder-admin'
    assert await startup_missing('rig', env) == []
    del env['CHASSIS_RLS_ADMIN_ROLE']
    connect.reset_mock()
    assert await startup_missing('rig', env) == ['CHASSIS_RLS_ADMIN_ROLE']
    connect.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['connection', 'authentication', 'dsn'])
async def test_unusable_database_setting_is_reported_without_connection_details(monkeypatch, kind):
    import asyncpg
    error = {'connection': OSError, 'authentication': asyncpg.InvalidPasswordError, 'dsn': ValueError}[kind]
    monkeypatch.setattr(asyncpg, 'connect', AsyncMock(side_effect=error('placeholder-private-detail')))
    assert await startup_missing('rig', {'DATABASE_URL': 'placeholder-private-url'}) == ['DATABASE_URL']


def test_production_entry_point_starts_safely_without_database_setting(tmp_path):
    code = '''
import asyncpg, httpx
from fastapi.testclient import TestClient
def forbidden(*args, **kwargs):
    raise AssertionError('Missing configuration must not open connections')
asyncpg.create_pool = forbidden
httpx.AsyncClient = forbidden
from rigbox.three_d.asgi import app
with TestClient(app) as client:
    for path in ('/health', '/v1/rig/search?q=anything'):
        response = client.get(path)
        assert response.status_code == 503
        assert response.json()['missing_settings'] == ['DATABASE_URL']
    config = client.get('/3d/config')
    assert config.status_code == 200 and config.json()['configured'] is False
    assert config.json()['publishable_key'] == ''
    assert client.get('/3d/').status_code == 200
    assert client.get('/3d/terminal.js').status_code == 200
    result = client.get('/health/configuration')
    assert result.status_code == 200
    assert result.json()['catalogue']['missing_settings'] == ['DATABASE_URL']
    assert result.json()['gpu']['missing_settings'] == ['HF_JOBS_TOKEN', 'HF_JOBS_NAMESPACE']
    assert not hasattr(app.state, 'pool') and not hasattr(app.state, 'rig')
'''
    env = {k: v for k, v in os.environ.items() if k not in {n for ns in GROUPS.values() for n in ns}}
    env.update(DATA_DIR=str(tmp_path), PYTHONDONTWRITEBYTECODE='1',
        PYTHONPATH=os.pathsep.join(map(str, (ROOT / 'agents/rig', ROOT / 'agents/_chassis', ROOT / 'vendor/tervory-tank/agents/_chassis', ROOT))))
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    assert not list(tmp_path.iterdir())


def test_brain_missing_key_reports_name_before_creating_task(monkeypatch, tmp_path):
    # Match Dockerfile.brain's COPY agents/_brain /app/brain package name.
    shared = ROOT / 'agents/_brain'
    if not shared.is_dir():
        shared = ROOT / 'vendor/tervory-tank/agents/_brain'
    packages = tmp_path / 'packages'
    packages.mkdir()
    (packages / 'brain').symlink_to(shared, target_is_directory=True)
    monkeypatch.syspath_prepend(str(packages))
    from rig_brain.service import app
    monkeypatch.delenv('TANK_KEY', raising=False)
    data = tmp_path / 'data'
    data.mkdir()
    monkeypatch.setenv('DATA_DIR', str(data))
    with TestClient(app) as client:
        health = client.get('/health')
        assert health.status_code == 503 and health.json()['missing_settings'] == ['TANK_KEY']
        response = client.post('/tasks', json={'tenant_id': TENANT, 'task_id': TENANT,
            'home_region': 'us-east', 'question': 'offline'})
        assert response.status_code == 401
    assert not list(data.iterdir())


@pytest.mark.asyncio
async def test_forge_missing_storage_and_gpu_settings_never_launch(monkeypatch, tmp_path):
    from agents.rig.forge import service
    from test_rig_forge_review import job
    from fastapi import HTTPException
    for name in (*GROUPS['storage'], *GROUPS['gpu'], 'TANK_KEY', 'TANK_API_KEY', 'TANK_KEY_RIG'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('FORGE_DATA_DIR', str(tmp_path))
    perform = AsyncMock(side_effect=AssertionError('No launch'))
    monkeypatch.setattr(service, 'perform', perform)
    async with service.lifespan(service.app):
        result = await service.configuration()
        assert result['storage']['missing_settings'] == list(GROUPS['storage'])
        assert result['gpu']['missing_settings'] == list(GROUPS['gpu'])
        with pytest.raises(HTTPException) as error:
            await service.submit(job())
        assert error.value.status_code == 503
    perform.assert_not_called()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('job', ['all', *JOBS])
def test_each_job_runs_from_the_one_dry_run_command(job):
    # The command creates and destroys its own database. It never uses a room DB.
    env = dict(os.environ, RIG_TEST_DATABASE_URL=_admin_url(), PYTHONDONTWRITEBYTECODE='1', RIG_PYTHON=sys.executable)
    result = subprocess.run(['bash', 'scripts/rig-dry-run.sh', '--dry-run', '--job', job],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(result.stdout.splitlines()[-1])
    assert report['dry_run'] and report['external_calls'] == 0
    assert set(report['jobs']) == (set(JOBS) if job == 'all' else {job})
    assert all(row['ok'] for row in report['jobs'].values())


@pytest.mark.parametrize('url', ['postgresql://remote.example/db', 'postgresql://127.0.0.1/db?host=remote.example',
    'postgresql:///db', 'https://localhost/db'])
def test_dry_run_refuses_remote_or_overridden_database(url):
    with pytest.raises(ValueError):
        local_database(url)


def test_dry_run_blocks_dns_and_connections_to_any_external_service():
    with offline_network():
        with pytest.raises(RuntimeError):
            socket.getaddrinfo('must-not-resolve.example', 443)
        with socket.socket() as sock, pytest.raises(RuntimeError):
            sock.connect(('192.0.2.1', 443))


def test_day_zero_rendered_screens():
    result = subprocess.run(['node', 'tests/rig_gate4_browser.mjs'], cwd=ROOT,
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr
