from unittest.mock import AsyncMock

from fastapi import HTTPException
import pytest

from trigger import app as room


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', [('DATABASE_URL',), ('TANK_KEY',), ('DATABASE_URL', 'TANK_KEY')])
async def test_missing_settings_start_and_report_without_io(monkeypatch, missing):
    for name in ('DATABASE_URL', 'TANK_KEY'):
        monkeypatch.setenv(name, 'placeholder-configured')
    for name in missing:
        monkeypatch.delenv(name)
    database = AsyncMock(side_effect=AssertionError('No database access before configuration'))
    monkeypatch.setattr(room.asyncpg, 'create_pool', database)
    async with room.lifespan(room.app):
        with pytest.raises(HTTPException) as failure:
            await room.health()
        assert failure.value.status_code == 503
        assert set(failure.value.detail['missing_settings']) == set(missing)
        with pytest.raises(HTTPException) as blocked:
            await room.authorized('placeholder-key')
        assert blocked.value.status_code == 503
        assert room.app.state.pool is None
    database.assert_not_awaited()
    room.app.state.missing_settings = []


def test_dry_run_requires_explicit_flag_and_covers_all_job_families():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / 'scripts/dry_run.py'
    spec = importlib.util.spec_from_file_location('trigger_dry_run', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with pytest.raises(SystemExit):
        module.main([])
    assert any('delivery' in target for target in module.TARGETS)
    assert any('retention' in target for target in module.TARGETS)
    assert any('jobs_and_sources' in target for target in module.TARGETS)
    assert any('trigger_w1' in target for target in module.TARGETS)
