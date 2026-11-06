"""Day-zero views, fail-closed startup and every one-command handler rehearsal."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from core import readiness


def room():
    spec = importlib.util.spec_from_file_location('gate4_room', ROOT / 'agents/market_lab/app.py')
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


@pytest.mark.parametrize('setting', readiness.REQUIRED)
def test_missing_core_setting_starts_but_never_creates_worker_pool(monkeypatch, setting):
    import asyncpg
    for name in readiness.REQUIRED:
        monkeypatch.setenv(name, 'placeholder-configured')
    monkeypatch.delenv(setting, raising=False)
    pool = AsyncMock(side_effect=AssertionError('must not start background work'))
    monkeypatch.setattr(asyncpg, 'create_pool', pool)
    value = room()
    with TestClient(value.app) as client:
        response = client.get('/health')
        assert response.status_code == 503
        assert response.json()['missing_settings'] == [setting]
        assert setting in response.json()['detail']
        response = client.post('/jobs', json={})
        assert response.status_code == 503
        assert response.json()['missing_settings'] == [setting]
    pool.assert_not_called()


@pytest.mark.parametrize('setting', (*readiness.UPLOADS, *readiness.MAIL, *readiness.KEY_NAMES))
def test_optional_capability_reports_exact_missing_name_only(monkeypatch, setting):
    from fastapi import FastAPI
    for name in (*readiness.REQUIRED, *readiness.UPLOADS, *readiness.MAIL, *readiness.KEY_NAMES):
        monkeypatch.setenv(name, 'placeholder-private-value')
    monkeypatch.delenv(setting)
    app = FastAPI()
    readiness.install(app)
    with TestClient(app) as client:
        response = client.get('/market/settings', headers={'X-Tank-Key': 'placeholder-private-value'})
        assert response.status_code == 200
        data = response.json()
        assert data['missing_settings'] == []
        assert [n for names in data['features'].values() for n in names] == [setting]
        assert 'placeholder-private-value' not in response.text


def test_missing_upload_setting_prevents_all_side_effects(monkeypatch):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    for name in readiness.REQUIRED:
        monkeypatch.setenv(name, 'placeholder-configured')
    for name in readiness.UPLOADS:
        monkeypatch.delenv(name, raising=False)
    entered = []
    @asynccontextmanager
    async def lifespan(app):
        entered.append(True)
        yield
    app = FastAPI(lifespan=lifespan)
    @app.put('/market/files/{ident}')
    async def write(ident):
        raise AssertionError('must not touch storage')
    readiness.install(app)
    with TestClient(app) as client:
        response = client.put('/market/files/placeholder')
        assert response.status_code == 503
        assert response.json()['missing_settings'] == list(readiness.UPLOADS)
        assert client.get('/market/settings', headers={'X-Tank-Key': 'placeholder-configured'}).json()['missing_settings'] == []
    assert entered == [True]  # Optional settings do not prevent core startup.


def test_real_frontend_empty_views():
    result = subprocess.run(['node', '--experimental-strip-types', '--import',
        str(ROOT / 'tests/market_lab_gate4_hooks.mjs'), '--test',
        str(ROOT / 'tests/market_lab_gate4.test.tsx')], cwd=ROOT, text=True, capture_output=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def test_one_command_replays_every_handler_offline():
    result = subprocess.run([str(ROOT / 'scripts/run-market-lab.sh'), '--dry-run'],
                            cwd=ROOT, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    value = room()
    assert set(data['jobs']) == set(value.app.state.handlers)
    assert {s['kind'] for s in value.app.state.schedules} <= set(data['jobs'])
    assert all(j['status'] == 'passed' for j in data['jobs'].values())
    assert data['network'] == 'disabled' and data['storage'] == 'disposable'
    assert data['training'] == 'not_applicable' and data['publisher_downloads'] == 4
    assert data['jobs']['feed_links']['result']['feeds'][0]['rows'] > 0
    assert data['jobs']['alerts']['result']['mail']['sent'] == 0


def test_live_command_with_missing_settings_is_safe_and_names_them(monkeypatch):
    for name in readiness.REQUIRED:
        monkeypatch.delenv(name, raising=False)
    result = subprocess.run([str(ROOT / 'scripts/run-market-lab.sh'), '--job', 'refresh',
        '--tenant', '00000000-0000-0000-0000-000000000031'], cwd=ROOT,text=True,capture_output=True,timeout=20)
    assert result.returncode == 0
    assert json.loads(result.stdout) == {'status': 'not_configured', 'missing_settings': list(readiness.REQUIRED)}


def test_existing_feed_command_dry_run_ignores_external_database(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder.invalid/never-used')
    result = subprocess.run([str(ROOT / 'scripts/run-market-lab.sh'), '--dry-run'],
        cwd=ROOT, text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['storage'] == 'disposable'
    # The legacy feed entry point dispatches to that same rehearsal before any
    # caller-selected Postgres or SQLite target is opened.
    from feeds.cli import main
    from core import dry_run
    from unittest.mock import patch
    with patch.object(dry_run, 'run', AsyncMock(return_value={'dry_run': True})) as replay:
        assert main(['run', '--engine', 'ffl', '--dry-run', '--db', 'postgresql://placeholder.invalid/never-used']) == 0
    replay.assert_awaited_once()


@pytest.mark.asyncio
async def test_empty_audit_brief_never_appears_on_client_list():
    from core.jobs import perform_opportunities
    from core.ledger import MemoryLedger
    ledger = MemoryLedger()
    owner = '00000000-0000-0000-0000-000000000031'
    await perform_opportunities(tenant_id=owner, engine='ffl', ledger=ledger, areas=[])
    assert ledger.reports and ledger.reports[0]['answer'] == ''
    assert ledger.briefs_for(owner) == []
