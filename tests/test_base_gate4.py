import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4
from contextlib import asynccontextmanager

import httpx
import pytest
from test_b3_base_room import ROOT, _load


@pytest.mark.parametrize('missing', ['DATABASE_URL', 'TANK_KEY', 'both'])
@pytest.mark.asyncio
async def test_missing_required_settings_start_with_diagnostics_and_no_work(monkeypatch, missing):
    for name in ('DATABASE_URL', 'TANK_KEY'):
        if missing in (name, 'both'):
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, 'placeholder-configured-value')
    base = _load('base_gate4_configuration_app', ROOT / 'agents/base/app.py')
    worker = AsyncMock()
    monkeypatch.setattr(base, 'ensure_worker', worker)

    @asynccontextmanager
    async def unsafe_start(app):
        raise AssertionError('Missing settings must not create pools or schedules')
        yield

    monkeypatch.setattr(base, '_chassis_lifespan', unsafe_start)
    async with base.app.router.lifespan_context(base.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app), base_url='http://localhost') as client:
            health = await client.get('/health')
            assert health.status_code == 200 and health.json()['ok'] is False
            assert health.json()['status'] == 'not_configured'
            expected = {'DATABASE_URL','TANK_KEY'} if missing == 'both' else {missing}
            assert set(health.json()['missing_settings']) == expected
            request = await client.post('/v1/base/run', json={})
            assert request.status_code == 503
            assert set(request.json()['missing_settings']) == expected
            assert 'placeholder-configured-value' not in health.text + request.text
    worker.assert_not_called()


@pytest.mark.asyncio
async def test_configured_start_still_uses_the_real_chassis_lifecycle(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','placeholder-configured-value')
    monkeypatch.setenv('TANK_KEY','placeholder-configured-value')
    base = _load('base_gate4_ready_app', ROOT / 'agents/base/app.py')
    entered = []

    @asynccontextmanager
    async def ready(app):
        entered.append(True)
        yield

    monkeypatch.setattr(base, '_chassis_lifespan', ready)
    monkeypatch.setattr(base, 'runtime_missing_settings', AsyncMock(return_value=[]))
    async with base.app.router.lifespan_context(base.app):
        assert base.app.state.configuration_missing == []
    assert entered == [True]


@pytest.mark.asyncio
async def test_missing_rls_admin_binding_is_named_before_chassis_or_jobs_start(monkeypatch):
    monkeypatch.setenv('DATABASE_URL','placeholder-configured-value')
    monkeypatch.setenv('TANK_KEY','placeholder-configured-value')
    monkeypatch.delenv('CHASSIS_ADMIN_DATABASE_URL',raising=False)
    base = _load('base_gate4_rls_app', ROOT / 'agents/base/app.py')
    connection = SimpleNamespace(fetchval=AsyncMock(return_value=True),close=AsyncMock())
    monkeypatch.setattr(base.asyncpg,'connect',AsyncMock(return_value=connection))

    @asynccontextmanager
    async def unsafe(app):
        raise AssertionError('RLS jobs require their existing admin binding')
        yield

    monkeypatch.setattr(base,'_chassis_lifespan',unsafe)
    async with base.app.router.lifespan_context(base.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app),base_url='http://localhost') as client:
            health = (await client.get('/health')).json()
            assert health['missing_settings'] == ['CHASSIS_ADMIN_DATABASE_URL']
    connection.close.assert_awaited_once()


def test_training_command_missing_settings_is_actionable_and_has_no_side_effects(monkeypatch,tmp_path):
    monkeypatch.delenv('DATABASE_URL',raising=False)
    monkeypatch.delenv('TANK_KEY',raising=False)
    output = tmp_path / 'not-created'
    result = subprocess.run(['bash','scripts/train-base.sh','--work-dir',str(output)],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert set(value['missing_settings']) == {'DATABASE_URL','TANK_KEY'}
    assert value['status'] == 'not_configured' and 'Traceback' not in result.stderr
    assert not output.exists()


@pytest.mark.asyncio
async def test_optional_vendor_key_missing_names_it_and_never_calls_a_provider(monkeypatch):
    from sources.context_dev import ContextDev
    from sources.vendor_ledger import PLATFORM_TENANT
    monkeypatch.delenv('CONTEXT_DEV_API_KEY',raising=False)
    http, ledger = AsyncMock(), AsyncMock()
    adapter = ContextDev(http,ledger,tenant_id=PLATFORM_TENANT,run_id=str(uuid4()))
    result = await adapter.lookup(name='Recorded Business')
    assert result['missing_settings'] == ['CONTEXT_DEV_API_KEY']
    http.post.assert_not_called()
    ledger.reserve.assert_not_called()


@pytest.mark.asyncio
async def test_missing_evidence_settings_do_not_touch_local_files_or_storage(monkeypatch):
    import base_brain
    import browser_evidence
    base = _load('base_gate4_storage_app',ROOT/'agents/base/app.py')
    monkeypatch.setattr(base_brain,'selected',lambda *args: object())
    monkeypatch.setattr(browser_evidence,'upload',AsyncMock())
    names = ['R2_ACCOUNT_ID','R2_ACCESS_KEY_ID_BASE','R2_SECRET_ACCESS_KEY_BASE']
    for name in names:
        monkeypatch.delenv(name,raising=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=base.app),base_url='http://localhost') as client:
        result = await client.post('/brain/evidence',json={
            'tenant_id':str(uuid4()),'task_id':str(uuid4()),'evidence_id':'0'*64})
    assert result.status_code == 503
    assert result.json()['detail']['missing_settings'] == names
    browser_evidence.upload.assert_not_called()


def test_day_zero_proposed_views_preserve_shapes_and_real_populated_data():
    result = subprocess.run(['node','tests/base_gate4_view.cjs'],cwd=ROOT,capture_output=True,text=True,timeout=60)
    assert result.returncode == 0,result.stdout + result.stderr


def test_one_command_rehearses_real_state_resume_and_all_scheduled_jobs(tmp_path):
    result = subprocess.run(['bash','scripts/train-base.sh','--dry-run','--work-dir',str(tmp_path)],
                            cwd=ROOT,capture_output=True,text=True,timeout=120)
    assert result.returncode == 0,result.stdout + result.stderr
    value = json.loads(result.stdout)
    assert value['mode'] == 'dry_run' and value['source_records'] == 77611
    assert value['smallest_state'] == 'DC' and value['records'] == 4 and value['resumed'] is True
    assert set(value['scheduled_jobs']) == {'ping','gold.nightly'}
    assert value['scheduled_jobs']['gold.nightly']['status'] == 'done'
    assert value['external_requests'] == value['model_spend'] == 0
