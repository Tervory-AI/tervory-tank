"""Founder status starts at zero and includes proof spend without crossing tenants."""
import json
import uuid

import pytest

from test_engine_ladder import setup_engine
from test_tank_tenant_boundaries import boundary  # noqa: F401


@pytest.mark.asyncio
async def test_engine_status_day_zero_costs_and_tenant_scope(boundary, monkeypatch):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    headers = b.native_headers('founder-fixture', 'org_admin')
    async def status(tenant):
        response = await b.client.get('/v1/engine/status', params={'tenant_id': str(tenant)}, headers=headers)
        assert response.status_code == 200, response.text
        return next(r for r in response.json()['tasks'] if r['task_type'] == req.task_type)
    assert (await b.client.get('/v1/engine/status', params={'tenant_id': str(req.tenant_id)})).status_code in {401, 403, 404}
    zero = await status(req.tenant_id)
    assert zero['model'] is None and zero['rung'] == 'unselected'
    metrics = ('requests', 'memory_hits', 'cache_hits', 'graduations', 'cost_usd', 'evaluation_cost_usd', 'would_have_cost_usd', 'saved_usd')
    assert all(zero[k] == 0 for k in metrics)
    async with b.pool.acquire() as conn:
        await conn.execute('''INSERT INTO tank.engine_state(tenant_id,region,task_type,model,revision)
            VALUES($1,'us-east',$2,'local','fixture')''', req.tenant_id, req.task_type)
        for i, (tenant, task, cost) in enumerate([(req.tenant_id, req.task_type, .01),
                (req.tenant_id, req.task_type+'#engine-eval', .02), (b.tenants[1], req.task_type, 100)]):
            ident = uuid.uuid4()
            await conn.execute('''INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,model,cost_usd,cache_hit)
                VALUES($1,$2,'us-east','tank',$3,'local',$4,$5)''', ident, tenant, task, cost, i == 0)
            if i == 0:
                await conn.execute('''INSERT INTO tank.engine_receipts(tenant_id,region,task_type,ledger_id,detail)
                    VALUES($1,'us-east',$2,$3,$4::jsonb)''', tenant, task, ident,
                    json.dumps({'memory_hits': 2, 'would_have_cost_usd': .1}))
        await conn.execute('''INSERT INTO tank.engine_graduations
            (tenant_id,region,task_type,model,revision,previous_model,samples,agreement)
            VALUES($1,'us-east',$2,'local','fixture','luna',200,1)''', req.tenant_id, req.task_type)
    row = await status(req.tenant_id)
    assert row['rung'] == 'local small' and row['model'] == 'local'
    assert row['requests'] == row['memory_hits'] == row['cache_hits'] == row['graduations'] == 1
    assert row['cost_usd'] == .03 and row['evaluation_cost_usd'] == .02
    assert row['would_have_cost_usd'] == .1 and row['saved_usd'] == pytest.approx(.07)
    foreign = await status(b.tenants[1])
    assert foreign['cost_usd'] == 100 and foreign['memory_hits'] == foreign['cache_hits'] == foreign['graduations'] == 0
