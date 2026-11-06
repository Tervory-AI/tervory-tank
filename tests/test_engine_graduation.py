"""Recorded traffic and a fake trained provider traverse the real Tank ledger."""
import json

import httpx
import pytest

import engine_ladder
import graduate
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_engine_ladder import setup_engine


@pytest.mark.asyncio
async def test_trained_candidate_needs_gold_and_distinct_traffic_then_auto_graduates(boundary, monkeypatch):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    roster = await b.tank._roster_models()
    model = 'trained-fixture'
    async def trained_roster():
        return [*roster, {'model_name': model,
        'litellm_params': {'model': 'openai/trained-fixture'},
        'model_info': {'input_cost_per_token': 0, 'output_cost_per_token': 0}}]
    monkeypatch.setattr(b.tank, '_roster_models', trained_roster)
    original = httpx.AsyncClient
    trained_answer = ['wrong']
    async def dispatch(request):
        name = json.loads(request.content)['model']
        return httpx.Response(200, headers={'x-litellm-response-cost': '0', 'x-litellm-model-group': name},
            json={'choices': [{'message': {'content': trained_answer[0] if name == model else 'billing'}}],
                  'usage': {'prompt_tokens': 40, 'completion_tokens': 2}})
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(dispatch), **kw))
    async with b.pool.acquire() as conn:
        await conn.execute('''INSERT INTO tank.evals(tenant_id,task_type,input,expected)
            VALUES($1,'engine.classify','{"text":"Classify a duplicate charge"}','"billing"')''', req.tenant_id)
    headers = b.native_headers('founder-fixture', 'org_admin')
    body = {'tenant_id': str(req.tenant_id), 'task_type': req.task_type, 'model': model, 'checkpoint': 'a'*64}
    assert (await b.client.post('/v1/engine/candidates', json=body)).status_code in {401, 403, 404}
    response = await b.client.post('/v1/engine/candidates', json=body, headers=headers)
    assert response.status_code == 200 and response.json()['state'] == 'candidate', response.text
    policy = await b.tank.load_policy(req.task_type, req.tenant_id)
    selected = await engine_ladder.select(b.tank, req, policy)
    assert selected['model'] == 'local'
    receipts = []
    for i in range(200):
        recorded = req.model_copy(update={'messages': [b.tank.Message(role='user', content=f'Classify charge event {i}.')]})
        answer = await b.tank._record_local(recorded, selected, model='local', rung=2, content='billing')
        receipts.append(answer.ledger_id)
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET feedback='accepted' WHERE tenant_id=$1 AND task_type=$2", req.tenant_id, req.task_type)
    held = await graduate.engine_tick(b.tank, req, selected, limit=200)
    assert held['state'] == 'held'  # Traffic cannot override failed gold evals.
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.engine_proofs WHERE tenant_id=$1', req.tenant_id) == 0
    trained_answer[0] = 'billing'
    body['checkpoint'] = 'b'*64
    assert (await b.client.post('/v1/engine/candidates', json=body, headers=headers)).status_code == 200
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local'
    result = await graduate.engine_tick(b.tank, req, selected, limit=199)
    assert result['state'] == 'candidate' and result['samples'] == 199
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local'
    # A normal route closes the loop and processes the final recorded example.
    answer = await b.tank.run_route(req)
    assert answer.engine['graduation']['state'] == 'graduated'
    assert answer.engine['graduation']['samples'] == 200
    winner = await b.tank.run_route(req)
    assert winner.model == model and winner.cost_usd == 0
    foreign = req.model_copy(update={'tenant_id': b.tenants[1]})
    assert (await engine_ladder.select(b.tank, foreign, policy))['model'] == 'local'
    # Replaying identical accepted traffic never increases independent evidence.
    result = await graduate.engine_tick(b.tank, req, selected, limit=200)
    assert result['samples'] == 200
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.ledger SET feedback='rejected' WHERE tenant_id=$1 AND id=ANY($2::uuid[])", req.tenant_id, receipts[:11])
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local'
    body['checkpoint'] = 'c'*64
    assert (await b.client.post('/v1/engine/candidates', json=body, headers=headers)).status_code == 200
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local'
    # Even passing gold evals alone cannot move an established larger rung down.
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.engine_state SET model='local-large' WHERE tenant_id=$1", req.tenant_id)
    assert (await engine_ladder.select(b.tank, req, policy))['model'] == 'local-large'


def test_engine_proof_keeps_99_percent_floor():
    from engine_proof import proven
    policy = {'eval_threshold': .5, 'min_shadow_samples': 1}
    assert not proven(policy, graduate.Evidence(samples=199, agreement=1))[0]
    assert not proven(policy, graduate.Evidence(samples=200, agreement=.985))[0]
    assert proven(policy, graduate.Evidence(samples=200, agreement=.99))[0]
