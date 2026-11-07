import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
import engine_quality
import tervor_eval
import tervor_registry
from test_train1 import database as _database
from test_tervor_registry import sample

database = _database


class Request(SimpleNamespace):
    def model_copy(self, *, update):
        return Request(**(vars(self) | update))


def gold_set(tenant, n=200):
    cases = [dict(input={'text': str(i)}, expected='checked', task_type='zenas.answer', holdout=True) for i in range(n)]
    return dict(tenant_id=str(tenant), product='zenas', region='us-east', holdout=True,
                cases=cases, count=n, sha256=tervor_registry.digest(cases))


async def setup(pool, monkeypatch, *, candidate_score=1., baseline_score=1., failure=None):
    tenant, model = uuid4(), sample()
    async with pool.acquire() as conn:
        await tervor_registry.register(conn, tenant, model)
    calls = []
    async def policy(task, scope):
        assert scope == tenant
        return {'model': 'current-fixture-rung', 'rung': 1}
    async def route(req, caller=None, _paid_policy=None):
        assert req.tenant_id == tenant
        assert _paid_policy['shadow_rate'] == 0 and _paid_policy['fallbacks'] == []
        calls.append(_paid_policy['model'])
        if failure == 'timeout':
            raise TimeoutError('fixture timeout')
        return SimpleNamespace(model='unexpected' if failure == 'wrong model' else _paid_policy['model'],
            content=_paid_policy['model'], cost_usd=None if failure == 'cost' else .001, ledger_id=uuid4())
    async def assess(rt, req, policy, candidate, messages, expected, actual, caller=None):
        assert expected == 'checked'
        score = candidate_score if actual == model['id'] else baseline_score
        return dict(scores=dict.fromkeys(tervor_eval.METRICS, score), passed=score == 1,
                    cost_usd=.002, ledger_ids=[str(uuid4())])
    monkeypatch.setattr(engine_quality, 'assess', assess)
    rt = SimpleNamespace(pool=lambda: pool, load_policy=policy, _run_route=route,
                         Message=SimpleNamespace, box_region=lambda: 'us-east')
    return rt, Request(tenant_id=tenant), model['id'], calls


@pytest.mark.asyncio
@pytest.mark.parametrize('candidate,baseline,eligible', [(1.,1.,True),(.99,1.,False),(.98,.98,False),(1.,.8,True)])
async def test_gold_compares_adapter_against_current_rung_and_records_version(database, monkeypatch, candidate, baseline, eligible):
    pool, _ = database
    rt, req, model, calls = await setup(pool, monkeypatch, candidate_score=candidate, baseline_score=baseline)
    report = await tervor_eval.evaluate(rt, req, model, gold_set(req.tenant_id))
    assert report['eligible'] is eligible
    assert report['completed'] == 200 and report['status'] == 'evaluated'
    assert report['model_id'] == model and report['version'] == 'tervor-lite-1.0'
    assert report['cost_usd'] == pytest.approx(1.2)
    assert len(report['ledger_ids']) == 800
    assert calls == ['current-fixture-rung', model] * 200
    async with pool.acquire() as conn:
        assert await tervor_eval.reports(conn, req.tenant_id, model) == [report]
        assert await tervor_eval.reports(conn, uuid4(), model) == []
        assert await conn.fetchval("SELECT count(*) FROM tank.policy WHERE model=$1", model) == 0
        stored = json.loads(await conn.fetchval("SELECT detail FROM tank.policy_log WHERE action='report'"))
        assert 'checked' not in json.dumps(stored)


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['timeout','wrong model','cost'])
async def test_evaluation_failures_leave_report_and_never_promote(database, monkeypatch, failure):
    pool, _ = database
    rt, req, model, calls = await setup(pool, monkeypatch, failure=failure)
    report = await tervor_eval.evaluate(rt, req, model, gold_set(req.tenant_id))
    assert report['status'] == 'failed' and not report['eligible']
    assert report['completed'] == 0 and len(calls) == 1
    if failure == 'cost':
        assert report['cost_usd'] is None


@pytest.mark.asyncio
async def test_insufficient_gold_and_other_tenant_cannot_call_models(database, monkeypatch):
    pool, _ = database
    rt, req, model, calls = await setup(pool, monkeypatch)
    report = await tervor_eval.evaluate(rt, req, model, gold_set(req.tenant_id, 199))
    assert not report['eligible'] and report['status'] == 'held'
    assert report['cost_usd'] == 0 and calls == []
    with pytest.raises(ValueError, match='registered for this tenant'):
        await tervor_eval.evaluate(rt, Request(tenant_id=uuid4()), model, gold_set(req.tenant_id))
    assert calls == []
