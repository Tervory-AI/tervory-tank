"""Pre-change policy proof uses the real eval handler and SQL, with code-only fixtures."""
import json
from unittest.mock import AsyncMock

import pytest
import roster_validation as roster
import skala
import skala_revalidation
from fastapi import HTTPException
from gold import PLATFORM_TENANT
from skala_b3_b4.test_lifecycle import package
from test_tank_ladder import REAL_RUN
from test_tank_tenant_boundaries import boundary  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize("fails", [False, True])
async def test_all_approved_evals_precede_policy_write(boundary, monkeypatch, tmp_path, fails):  # noqa: F811
    b = boundary
    async with b.pool.acquire() as conn:
        await conn.execute("DELETE FROM tank.skill_revalidations")
        await conn.execute("UPDATE tank.skills SET state='staging'")
    monkeypatch.setattr(skala, 'run_skill', REAL_RUN)
    monkeypatch.setattr(skala, '_run_cache', {})
    for name in ('base.one', 'base.two'):
        pkg = package(tmp_path, name=name, task=None, code=True)
        (pkg.path / 'run.py').write_text('async def run(payload, ctx):\n    return {"text": "good"} if payload.get("text") else {"refused": True}\n')
        if fails and name == 'base.one':
            (pkg.path / 'run.py').write_text('async def run(payload, ctx):\n    return {"text": "wrong"} if payload.get("text") else {"refused": True}\n')
        b.tank._packages[pkg.id, pkg.version] = pkg
        async with b.pool.acquire() as conn:
            await conn.execute("INSERT INTO tank.skills(id,version,agent,rung,state,present) VALUES($1,$2,'base',3,'approved',true)", pkg.id, pkg.version)
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[{'model_name': 'luna'}]))
    body = b.tank.PolicyRow(task_type='base.normalize', model='luna', rung=1,
                            system_prompt='New instructions')
    async with b.pool.acquire() as conn:
        original = await conn.fetchval("SELECT system_prompt FROM tank.policy WHERE task_type='base.normalize' AND tenant_id IS NULL")
    with pytest.raises(HTTPException) as pending:
        await b.tank.put_policy(body.task_type, body)
    assert pending.value.status_code == 409
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT system_prompt FROM tank.policy WHERE task_type='base.normalize' AND tenant_id IS NULL") == original
        jobs = await conn.fetch('SELECT * FROM tank.skill_revalidations WHERE tenant_id=$1 AND preflight_hash IS NOT NULL', PLATFORM_TENANT)
        assert {r['skill_id'] for r in jobs} == {'base.one', 'base.two'}
    # Code packages run their real cases, no model/provider stub can hide a call.
    assert await skala_revalidation.drain(b.tank, limit=200) > 0
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.skill_revalidations WHERE preflight_hash IS NOT NULL AND completed_at IS NULL") == 0
    if fails:
        with pytest.raises(HTTPException) as blocked:
            await b.tank.put_policy(body.task_type, body)
        assert blocked.value.detail['failed'] == 1
        assert await skala_revalidation.drain(b.tank) == 0
        return
    await b.tank.put_policy(body.task_type, body)
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT system_prompt FROM tank.policy WHERE task_type='base.normalize' AND tenant_id IS NULL") == 'New instructions'
        rows = await conn.fetch("SELECT models_validated FROM tank.skills WHERE state='approved'")
        assert all(json.loads(r['models_validated'])[-1]['validated'] for r in rows)
    # An observed roster change holds even a writer outside the API.
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[{'model_name': 'luna', 'revision': 2}]))
    await roster.prepare(b.tank)
    async with b.pool.acquire() as conn:
        with pytest.raises(Exception, match='models_validation_required'):
            await conn.execute("UPDATE tank.policy SET auto_promote=false WHERE task_type='base.normalize' AND tenant_id IS NULL")
    await skala_revalidation.drain(b.tank)
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET auto_promote=false WHERE task_type='base.normalize' AND tenant_id IS NULL")
    # Cached proof makes repeating the same request free.
    assert await skala_revalidation.drain(b.tank) == 0
