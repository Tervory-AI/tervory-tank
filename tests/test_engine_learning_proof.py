"""The 20-run graduation proof: real Tank HTTP, disposable PostgreSQL, fake model calls."""
import pytest

import engine_learning_world as world
import test_tank_tenant_boundaries

# Re-export the disposable-database fixture under its own name (an assignment, not an import).
boundary = test_tank_tenant_boundaries.boundary


def switch_on(monkeypatch, *names):
    for name in names:
        monkeypatch.setenv(name, 'true')


async def status(b, tenant):
    response = await b.client.get('/v1/engine/status', params={'tenant_id': str(tenant)}, headers=b.founder)
    assert response.status_code == 200, response.text
    return next(r for r in response.json()['tasks'] if r['task_type'] == b.task_type)


@pytest.mark.asyncio
async def test_same_task_twenty_times_pays_once_then_learns_to_zero(boundary, monkeypatch):
    switch_on(monkeypatch, 'ENGINE_LEARNING_REPLAY_ENABLED', 'ENGINE_STATUS_NUMBERS_ENABLED', 'ENGINE_ROLLBACK_ENABLED')
    b = await world.build(boundary, monkeypatch)
    tenant, other = b.tenants
    # The tenant's earlier accepted paid traffic: 200 distinct requests by another user.
    await world.record_history(b, tenant, 200)
    candidate = {'tenant_id': str(tenant), 'task_type': b.task_type, 'model': world.TRAINED, 'checkpoint': 'a' * 64}
    response = await b.client.post('/v1/engine/candidates', json=candidate, headers=b.founder)
    assert response.status_code == 200, response.text
    runs = []
    for i in range(20):
        if i == 3:
            learned = await b.client.post('/v1/engine/learn', headers=b.founder,
                                          json={'tenant_id': str(tenant), 'task_type': b.task_type, 'limit': 200})
            assert learned.status_code == 200, learned.text
            graduation = learned.json()
        runs.append(await world.route(b, tenant))
    first, second, third = runs[:3]
    assert first['model'] == world.PAID and first['cost_usd'] > 0 and first['engine']['memory_hits'] == 0
    assert second['engine']['memory_hits'] == 1 and second['rung'] != 4 and second['cost_usd'] > 0
    assert third['rung'] == 4 and third['cost_usd'] == 0 and third['engine']['memory_hits'] == 1
    assert graduation['state'] == 'graduated' and graduation['samples'] == 200 and graduation['agreement'] == 1
    assert graduation['serving_model'] == world.TRAINED
    assert runs[3]['model'] == world.TRAINED and runs[3]['cost_usd'] == 0
    assert all(run['cost_usd'] == 0 for run in runs[3:])
    assert all(run['cost_usd'] == 0 and run['model'] in {world.TRAINED} for run in runs[9:])
    assert sum(1 for run in runs if run['cost_usd'] > 0) == 2
    mine = await status(b, tenant)
    learning = mine['learning']
    assert mine['rung'] == learning['serving_rung'] == 'local trained'
    assert learning['graduations'] == 1 and learning['rollbacks'] == 0
    assert learning['shadows_run']['replayed'] == 200
    assert learning['proof']['samples'] == 200 and learning['proof']['agreement'] == 1
    assert learning['cache_hits_by_layer']['C2'] >= 2 and learning['cache_hits_by_layer']['C1'] + learning['cache_hits_unlabelled'] >= 1
    assert learning['savings']['saved_usd'] > 0
    # A second tenant sees nothing of the first tenant's memory, cache or graduation.
    foreign = await world.route(b, other)
    assert foreign['model'] == world.PAID and foreign['cost_usd'] > 0
    assert foreign['engine']['memory_hits'] == 0 and foreign['rung'] != 4
    theirs = (await status(b, other))['learning']
    assert theirs['graduations'] == 0 and theirs['shadows_run'] == {'live': 0, 'replayed': 0}
    assert theirs['proof'] is None and theirs['cache_hits_by_layer']['C2'] == 0


async def reject(b, tenant, ledger_id):
    body = {'tenant_id': str(tenant), 'feedback': 'rejected', 'verdict': 'wrong', 'note': 'wrong label'}
    response = await b.client.post(f'/v1/ledger/{ledger_id}/feedback', json=body)
    assert response.status_code == 200, response.text


@pytest.mark.asyncio
async def test_two_hundred_recorded_requests_step_down_two_rungs_then_roll_back(boundary, monkeypatch):
    switch_on(monkeypatch, 'ENGINE_LEARNING_REPLAY_ENABLED', 'ENGINE_STATUS_NUMBERS_ENABLED')
    b = await world.build(boundary, monkeypatch)
    tenant, other = b.tenants
    await world.record_history(b, tenant, 200)
    before = await world.route(b, tenant, 'Classify: a refund was charged twice.')
    assert before['model'] == world.PAID and before['engine']['rung'] == 'frontier' and before['cost_usd'] > 0
    # The small local rung now answers like the paid rung and the tenant adds a gold case
    # (a new eval revision). Passing gold alone may not move an established task.
    b.models.right.add('local')
    async with b.pool.acquire() as conn:
        await conn.execute('''INSERT INTO tank.evals(tenant_id,task_type,input,expected)
            VALUES($1,$2,'{"text":"Classify a double charge"}','"billing"')''', tenant, b.task_type)
    assert (await world.route(b, tenant, 'Classify: a card was billed twice.'))['model'] == world.PAID
    learned = await b.client.post('/v1/engine/learn', headers=b.founder,
                                  json={'tenant_id': str(tenant), 'task_type': b.task_type})
    assert learned.status_code == 200, learned.text
    result = learned.json()
    assert result['state'] == 'graduated' and result['model'] == 'local' and result['samples'] == 200
    assert result['serving_model'] == 'local' and result['serving_rung'] == 'local small'
    ladder = ('frontier', 'open-weight', 'local large', 'local small')
    assert ladder.index(result['serving_rung']) - ladder.index(before['engine']['rung']) >= 2
    served = [await world.route(b, tenant, f'Classify: invoice {i} was billed twice.') for i in range(10)]
    assert all(r['model'] == 'local' and r['cost_usd'] == 0 for r in served)
    # One rejected live answer in ten is above the 5% ceiling. Unset setting: main keeps serving.
    await reject(b, tenant, served[0]['ledger_id'])
    held = await world.route(b, tenant, 'Classify: order 77 was billed twice.')
    assert held['model'] == 'local'
    assert (await status(b, tenant))['learning']['rollbacks'] == 0
    switch_on(monkeypatch, 'ENGINE_ROLLBACK_ENABLED')
    back = await world.route(b, tenant, 'Classify: order 78 was billed twice.')
    assert back['model'] == world.PAID and back['cost_usd'] > 0
    learning = (await status(b, tenant))['learning']
    assert learning['rollbacks'] == 1 and learning['graduations'] == 1
    assert learning['serving_rung'] == 'frontier'
    # The rollback is recorded, so the slipped rung never silently returns.
    monkeypatch.delenv('ENGINE_ROLLBACK_ENABLED')
    again = await world.route(b, tenant, 'Classify: order 79 was billed twice.')
    assert again['model'] == world.PAID
    async with b.pool.acquire() as conn:
        reason = await conn.fetchval('SELECT rollback_reason FROM tank.engine_graduations WHERE tenant_id=$1', tenant)
        assert reason == 'client rejections are above the bar'
        assert await conn.fetchval('SELECT count(*) FROM tank.engine_graduations WHERE tenant_id=$1', other) == 0
    # The other tenant has no established rung; its own gold picks its own rung, untouched by this rollback.
    theirs = await world.route(b, other, 'Classify: order 80 was billed twice.')
    assert theirs['model'] == 'local' and theirs['engine']['memory_hits'] == 0
    foreign = (await status(b, other))['learning']
    assert foreign['graduations'] == foreign['rollbacks'] == 0 and foreign['proof'] is None
