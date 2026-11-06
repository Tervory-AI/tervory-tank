from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

import skala
import skala_revalidation
from test_skala_approval_safety import database as _database, package, reason, seed

database = _database


def model_package(tmp_path):
    pkg = package(tmp_path, model=True)
    (pkg.path / 'run.py').write_text(
        "async def run(payload, ctx):\n"
        "    if payload['n'] == 4:\n"
        "        return {'ok': False}\n"
        "    answer = await ctx.model([{'role': 'user', 'content': str(payload['n'])}], 'base.test')\n"
        "    return {'ok': answer == 'good'}\n")
    for case in pkg.cases[:4]:
        case['model'] = 'good'
    return pkg


def context(pkg, http, model):
    return skala.SkillContext(skala.PLATFORM_TENANT, pkg.ref, pkg.agent, None, model, http)


@pytest.mark.asyncio
async def test_saved_answers_are_offline_proof_but_never_approval_evidence(tmp_path):
    pkg = model_package(tmp_path)
    model = AsyncMock(side_effect=AssertionError('Offline package eval must not call a model'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as http:
        runs = [await skala.run_evals(pkg, lambda: context(pkg, http, model)) for _ in range(3)]
    assert all(r['score'] == 1 and r['eligible'] for r in runs)
    assert all(d['recorded_model'] for r in runs for d in r['details'][:4])
    assert all(not r['details'][4]['recorded_model'] for r in runs)
    assert skala.passing_runs(pkg, runs) == 0
    assert '0/3 runs' in reason(pkg, runs=runs)
    model.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('answer,score,state', [('wrong', .2, 'candidate'), ('good', 1, 'staging')])
async def test_manual_eval_handler_uses_tank_response_and_records_cost(database, tmp_path, monkeypatch, answer, score, state):
    import main as tank
    pkg = model_package(tmp_path)
    await seed(database, pkg, 'candidate', runs=0)
    monkeypatch.setattr(tank, '_pool', database)
    monkeypatch.setattr(tank, '_packages', {(pkg.id, pkg.version): pkg})
    model = AsyncMock(return_value={'content': answer, 'cost_usd': .01})
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as http:
        monkeypatch.setattr(tank, 'make_ctx', lambda *a, **k: context(pkg, http, model))
        runs = [await tank.run_skill_evals(pkg.id, pkg.version) for _ in range(3)]
    assert model.await_count == 12
    for call in model.await_args_list:
        assert call.kwargs['tenant_id'] == skala.PLATFORM_TENANT
        assert call.kwargs['task_type'] == pkg.task_type
    assert all(r['score'] == score and r['state'] == state and r['cost_usd'] == .04 for r in runs)
    assert all(not d['recorded_model'] for r in runs for d in r['details'])
    assert skala.passing_runs(pkg, runs) == (3 if answer == 'good' else 0)
    rows = await database.fetch('SELECT score,cost_usd,details FROM tank.skill_evals WHERE skill_id=$1', pkg.id)
    assert len(rows) == 3 and all(float(r['cost_usd']) == .04 for r in rows)


@pytest.mark.asyncio
async def test_live_evaluation_keeps_pure_code_free(tmp_path):
    pkg = package(tmp_path)
    model = AsyncMock(side_effect=AssertionError('Code needs no model'))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500))) as http:
        ctx = skala_revalidation.eval_context(SimpleNamespace(), pkg, context(pkg, http, model))
        assert ctx.live_evaluation
        assert (await skala.run_skill(pkg, {'n': 2}, ctx))['n'] == 2
        assert ctx.cost_usd == 0 and ctx.calls == 0
    model.assert_not_awaited()
