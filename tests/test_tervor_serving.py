"""A fake trained adapter takes the real authenticated Tank/E7 path."""
import json
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

import engine_ladder
import engine_quality
import graduate
import tervor_eval
import tervor_registry
import tervor_serving
from test_tank_tenant_boundaries import boundary as _boundary
from test_engine_ladder import setup_engine
from test_tervor_registry import sample
from test_tervor_eval import gold_set

boundary = _boundary


@pytest.mark.asyncio
async def test_unset_serving_never_reads_roster_or_changes_state(monkeypatch):
    monkeypatch.delenv('TERVOR_SERVING_ENABLED', raising=False)
    with pytest.raises(HTTPException, match='disabled') as error:
        await tervor_serving.register(SimpleNamespace(), SimpleNamespace())
    assert error.value.status_code == 409


@pytest.mark.asyncio
@pytest.mark.parametrize('kind,artifact', [('gguf', 'private/adapter.gguf'), ('hf-scale-zero', 'private/adapter')])
async def test_trained_model_registers_shadows_graduates_and_rolls_back(boundary, monkeypatch, kind, artifact):
    b = boundary
    req = await setup_engine(b, monkeypatch)
    req = req.model_copy(update={'task_type': 'zenas.classify'})
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET task_type='zenas.classify' WHERE task_type='engine.classify'")
        await conn.execute('''INSERT INTO tank.evals(tenant_id,task_type,input,expected)
            VALUES($1,'zenas.classify','{"text":"Classify a duplicate charge"}','"billing"')''', req.tenant_id)
    gold = gold_set(req.tenant_id)
    for case in gold['cases']:
        case.update(task_type=req.task_type, expected='billing')
    gold['sha256'] = tervor_registry.digest(gold['cases'])
    model = sample(data_hashes=[gold['sha256']], rung='local' if kind == 'gguf' else 'own-trained')
    async with b.pool.acquire() as conn:
        await tervor_registry.register(conn, req.tenant_id, model)
    serving = dict(kind=kind, artifact=artifact, sha256='d'*64, min_replicas=0)
    roster = await b.tank._roster_models()
    async def models():
        return [*roster, {'model_name': model['id'], 'litellm_params': {'model': 'openai/fixture'},
            'model_info': {'input_cost_per_token': 0, 'output_cost_per_token': 0, 'tervor_serving': serving}}]
    monkeypatch.setattr(b.tank, '_roster_models', models)
    original = httpx.AsyncClient
    calls = []
    async def dispatch(request):
        data = json.loads(request.content)
        calls.append(data['model'])
        return httpx.Response(200, headers={'x-litellm-response-cost':'0', 'x-litellm-model-group':data['model']},
            json={'choices':[{'message':{'content':'billing'}}], 'usage':{'prompt_tokens':20,'completion_tokens':1}})
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(dispatch), **kw))
    async def quality(rt, request, policy, candidate, messages, expected, actual, caller=None):
        assert actual == expected == 'billing'
        return dict(passed=True, scores=dict.fromkeys(tervor_eval.METRICS, 1.), cost_usd=0., ledger_ids=[],
            judge='fixture', revision=engine_quality.revision(request.task_type))
    monkeypatch.setattr(engine_quality, 'assess', quality)
    assert (await b.tank.run_route(req)).model == 'local'
    report = await tervor_eval.evaluate(b.tank, req, model['id'], gold)
    assert report['eligible'] and report['artifact_sha256'] == serving['sha256']
    assert report['baselines'] == {'zenas.classify':'local'}
    body = dict(tenant_id=str(req.tenant_id), task_type=req.task_type, model=model['id'],
        checkpoint=serving['sha256'], serving=serving)
    headers = b.native_headers('founder-fixture', 'org_admin')
    assert (await b.client.post('/v1/engine/candidates', json=body)).status_code in (401,403,404)
    assert (await b.client.post('/v1/engine/candidates', json=body, headers=headers)).status_code == 409
    monkeypatch.setenv('TERVOR_SERVING_ENABLED', 'true')
    other = {**body, 'tenant_id':str(b.tenants[1])}
    assert (await b.client.post('/v1/engine/candidates', json=other, headers=headers)).status_code == 422
    invalid = {**body, 'checkpoint':'e'*64}
    assert (await b.client.post('/v1/engine/candidates', json=invalid, headers=headers)).status_code == 422
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy_log SET detail=jsonb_set(detail,'{eligible}','false') WHERE task_type='tervor.evaluation'")
    assert (await b.client.post('/v1/engine/candidates', json=body, headers=headers)).status_code == 422
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy_log SET detail=jsonb_set(detail,'{eligible}','true') WHERE task_type='tervor.evaluation'")
    assert (await b.client.post('/v1/engine/candidates', json=body, headers=headers)).status_code == 200
    policy = await b.tank.load_policy(req.task_type, req.tenant_id)
    selected = await engine_ladder.select(b.tank, req, policy)
    assert selected['model'] == 'local'
    for i in range(200):
        recorded = req.model_copy(update={'messages':[b.tank.Message(role='user',content=f'Classify recorded charge {i}')]})
        await b.tank._record_local(recorded, selected, model='local', rung=2, content='billing')
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET feedback='accepted' WHERE tenant_id=$1 AND task_type=$2",
            req.tenant_id, req.task_type)
    result = await graduate.engine_tick(b.tank, req, selected, limit=199)
    assert result['state'] == 'candidate' and result['samples'] == 199
    result = await graduate.engine_tick(b.tank, req, selected, limit=1)
    assert result['state'] == 'graduated' and result['samples'] == 200
    assert (await b.tank.run_route(req)).model == model['id']
    serving['sha256'] = 'f'*64
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local'
    serving['sha256'] = 'd'*64
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == model['id']
    async with b.pool.acquire() as conn:
        stored = await tervor_serving.private_record(conn, req.tenant_id, model['id'])
        assert stored['graduations'][0]['previous_model'] == 'local'
        assert stored['promotion_reports'][0]['id'] == report['id']
        assert await tervor_serving.private_record(conn, b.tenants[1], model['id']) is None
        assert await conn.fetchval('''SELECT count(*) FROM tank.ledger WHERE tenant_id=$1
            AND model=$2 AND task_type LIKE '%#engine-shadow' ''', req.tenant_id, model['id']) == 200
    monkeypatch.delenv('TERVOR_SERVING_ENABLED')
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local'
    assert model['id'] in calls
