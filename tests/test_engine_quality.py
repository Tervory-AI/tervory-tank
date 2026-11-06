"""Real DeepEval metrics with a fake judge; calibration never falls back to frontier."""
import json
import os

import pytest

import engine_quality
from fastapi import HTTPException
from test_engine_ladder import setup_engine
from test_tank_tenant_boundaries import boundary  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('TANK_DEEPEVAL_PYTHON'), reason='isolated DeepEval runtime exercised by engine CI')
async def test_real_deepeval_rejects_wrong_answer_even_when_task_format_passes():
    count = [0]
    async def judge(prompt, schema):
        fields = schema['properties']
        if 'score' in fields:
            count[0] += 1
            return json.dumps({'score': 0 if count[0] == 1 else 1, 'reason': 'placeholder factual mismatch'})
        if 'truths' in fields:
            return json.dumps({'truths': ['The total is 12 USD.']})
        if 'claims' in fields:
            return json.dumps({'claims': ['The total is 120 USD.']})
        if 'verdicts' in fields:
            return json.dumps({'verdicts': [{'verdict': 'no', 'reason': 'placeholder unsupported amount'}]})
        return json.dumps({'reason': 'placeholder unsupported amount'})
    result = await engine_quality.metrics({'input': 'Extract total: 12 USD.',
        'primary': '{"amount":12}', 'actual': '{"amount":120}', 'context': ['Total: 12 USD.']}, 'base.extract', judge)
    assert result['scores'] == {'correctness': 0, 'faithfulness': 0, 'task': 1}
    assert not result['passed']
    async def malformed(prompt, schema):
        return 'not a metric verdict'
    with pytest.raises(engine_quality.JudgeCalibrationFailure):
        await engine_quality.metrics({'input': 'Classify billing.', 'primary': 'billing',
            'actual': 'billing', 'context': ['billing']}, 'base.classify', malformed)


@pytest.mark.asyncio
@pytest.mark.parametrize('bad_format', [False, True])
async def test_cheapest_judge_must_calibrate_and_does_not_cross_tenants(boundary, monkeypatch, bad_format):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    selected = []
    async def call(rt, request, policy, model, prompt, schema, caller=None):
        selected.append((str(request.tenant_id), model))
        return model
    async def metric(case, task, generate):
        model = await generate('placeholder calibration', {})
        if bad_format and model == 'local':
            raise engine_quality.JudgeCalibrationFailure('placeholder invalid verdict')
        return {'passed': True if model == 'local' else case['actual'] == case['primary']}
    monkeypatch.setattr(engine_quality, 'judge_call', call)
    monkeypatch.setattr(engine_quality, 'metrics', metric)
    policy = await b.tank.load_policy(req.task_type, req.tenant_id)
    judge = await engine_quality.calibrated_judge(b.tank, req, policy, 'trained-placeholder')
    assert judge[0] == 'local-large'
    assert [model for _, model in selected] == ['local'] * (1 if bad_format else 3) + ['local-large'] * 3
    selected.clear()
    assert (await engine_quality.calibrated_judge(b.tank, req, policy, 'trained-placeholder')) == judge
    assert selected == []
    foreign = req.model_copy(update={'tenant_id': b.tenants[1]})
    await engine_quality.calibrated_judge(b.tank, foreign, policy, 'trained-placeholder')
    assert len(selected) == (4 if bad_format else 6) and all(tenant == str(b.tenants[1]) for tenant, _ in selected)


@pytest.mark.asyncio
async def test_no_calibrated_judge_holds_instead_of_calling_frontier(boundary, monkeypatch):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    checked = []
    async def call(rt, request, policy, model, prompt, schema, caller=None):
        checked.append(model)
        return model
    async def wrong(case, task, generate):
        await generate('placeholder calibration', {})
        return {'passed': True}
    monkeypatch.setattr(engine_quality, 'judge_call', call)
    monkeypatch.setattr(engine_quality, 'metrics', wrong)
    assert await engine_quality.calibrated_judge(b.tank, req, {}, 'trained-placeholder') is None
    assert checked and 'luna' not in checked and 'sol' not in checked


@pytest.mark.asyncio
async def test_paid_judge_cannot_bypass_existing_shadow_budget(boundary, monkeypatch):  # noqa: F811
    import paid_steps
    b = boundary
    req = await setup_engine(b, monkeypatch)
    seen = []
    async def exhausted(task, ceiling, cap):
        assert task == req.task_type and ceiling > 0
        seen.append('reserved')
        raise HTTPException(409, 'Paid evaluation budget is exhausted')
    async def forbidden(*args, **kwargs):
        pytest.fail('A judge must not dispatch after its budget is exhausted')
    monkeypatch.setattr(paid_steps, 'reserve_shadow', exhausted)
    monkeypatch.setattr(b.tank, '_run_route', forbidden)
    with pytest.raises(HTTPException, match='budget is exhausted'):
        await engine_quality.judge_call(b.tank, req, {}, 'gpt-oss-small', 'placeholder prompt', {})
    assert seen == ['reserved']
