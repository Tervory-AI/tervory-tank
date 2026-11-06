"""Twenty requests through real CPU models, Hermes and Tank; paid HTTP is fake."""
import json
import os
import uuid

import pytest

import engine_memory
from test_engine_memory import remembered  # noqa: F401
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_engine_ladder import setup_engine, local_gateway


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('ENGINE_LOCAL_URL'), reason='real cloud-local llama.cpp servers required')
async def test_twenty_real_local_requests_with_receipts_and_tenant_isolation(remembered, monkeypatch):  # noqa: F811
    b = remembered
    req = await setup_engine(b, monkeypatch)
    async with b.pool.acquire() as conn:
        await conn.execute("""UPDATE tank.policy SET task_type='engine.answer', system_prompt=
            'Answer using the newest tenant fact. Output only the office city. If no office city is known, output UNKNOWN.'
            WHERE task_type='engine.classify'""")
    req = req.model_copy(update={'task_type': 'engine.answer', 'messages': [b.tank.Message(role='user', content='What is our office city?')]})
    calls = local_gateway(b, monkeypatch)
    result = await b.memory_client.post('/founder/memories', headers={'X-Tervory-Admin': 'founder-fixture'},
        json={'id': str(uuid.uuid4()), 'tenant_id': str(req.tenant_id), 'agent': 'tank', 'claim': 'Our office city is Paris.'})
    assert result.status_code == 200, result.text
    recalled, _ = await engine_memory.recall(b.tank, req)
    async with b.pool.acquire() as conn:
        await conn.execute('''INSERT INTO tank.evals(tenant_id,task_type,input,expected)
            VALUES($1,'engine.answer',$2::jsonb,'"Paris"')''', req.tenant_id,
            json.dumps({'messages': [m.model_dump() for m in recalled.messages]}))
    answers = [await b.tank.run_route(req) for _ in range(20)]
    assert {a.content.strip().rstrip('.').lower() for a in answers} == {'paris'}
    assert set(calls) == {'local', 'local-large'}  # Both real models ran; no paid provider was needed.
    assert answers[0].rung != 4 and answers[0].model == 'local-large'
    assert all(a.cost_usd == 0 and a.ledger_id and a.engine for a in answers[9:])
    assert all(a.rung == 4 for a in answers[9:])
    assert all(a.engine['memory_hits'] > 0 and a.engine['remembered'] for a in answers)
    assert all(a.engine['would_have_cost_usd'] > 0 for a in answers)
    assert len({a.ledger_id for a in answers}) == 20
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.engine_receipts WHERE tenant_id=$1', req.tenant_id) == 20
    headers = b.native_headers('founder-fixture', 'org_admin')
    async def status(tenant):
        response = await b.client.get('/v1/engine/status', params={'tenant_id': str(tenant)}, headers=headers)
        assert response.status_code == 200
        return next(r for r in response.json()['tasks'] if r['task_type'] == req.task_type)
    usage = await status(req.tenant_id)
    assert usage['requests'] == 20 and usage['memory_hits'] == 20 and usage['cache_hits'] >= 18
    assert usage['rung'] == 'local large' and usage['cost_usd'] == 0 and usage['saved_usd'] > 0
    untouched = await status(b.tenants[1])
    assert untouched['requests'] == untouched['memory_hits'] == untouched['cache_hits'] == untouched['cost_usd'] == 0
    assert await b.memories.list('tank', str(b.tenants[1]), 'client') == []
    foreign = await b.tank.run_route(req.model_copy(update={'tenant_id': b.tenants[1]}))
    assert foreign.content.strip().rstrip('.').upper() == 'UNKNOWN'
    assert foreign.rung != 4 and foreign.engine['memory_hits'] == 0
    assert 'Paris' not in json.dumps(await b.memories.list('tank', str(b.tenants[1]), 'client'))
    print('ENGINE_PROOF ' + json.dumps({'cost_usd': {str(i): answers[i-1].cost_usd for i in (1,2,5,10,20)},
        'requests': 20, 'cache_hits': usage['cache_hits'], 'memory_hits': usage['memory_hits'],
        'receipts': len({a.ledger_id for a in answers}), 'paid_calls': 0, 'models': sorted(set(calls))}))
