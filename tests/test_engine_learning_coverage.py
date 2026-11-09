"""Shadow coverage, status numbers and unset-setting compatibility at Tank's HTTP boundary."""
import asyncio
import random

import pytest

import engine_learning_world as world
import test_tank_tenant_boundaries

# Re-export the disposable-database fixture under its own name (an assignment, not an import).
boundary = test_tank_tenant_boundaries.boundary
SETTINGS = ('ENGINE_SHADOW_COVERAGE_ENABLED', 'ENGINE_STATUS_NUMBERS_ENABLED',
            'ENGINE_ROLLBACK_ENABLED', 'ENGINE_LEARNING_REPLAY_ENABLED')
NOT_TRUE = (None, '', 'false', '1', 'TRUE', 'yes', ' true')


def setting(monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)


async def settle(b):
    while b.tank._background:
        await asyncio.gather(*list(b.tank._background), return_exceptions=True)


async def shadows(b, tenant):
    async with b.pool.acquire() as conn:
        return [dict(r) for r in await conn.fetch('''SELECT primary_model,candidate_model,candidate_cost_usd
            FROM tank.shadow WHERE tenant_id=$1 ORDER BY candidate_model''', tenant)]


@pytest.mark.asyncio
async def test_listing_gives_every_task_type_a_cheaper_rung_from_the_roster(boundary, monkeypatch):
    b = await world.build(boundary, monkeypatch)
    tenant, other = b.tenants
    async with b.pool.acquire() as conn:
        for task, model in (('engine.sol', 'sol'), ('engine.open', 'llama'), ('engine.large', 'local-large'),
                            ('engine.small', 'local')):
            await conn.execute("INSERT INTO tank.policy(task_type,model,system_prompt) VALUES($1,$2,'')", task, model)
        await conn.execute("INSERT INTO tank.policy(task_type,model,system_prompt) VALUES('fixture.boundary','local','')")
        await conn.execute("INSERT INTO tank.policy(tenant_id,task_type,model,system_prompt) VALUES($1,'engine.private','luna','')", tenant)
    path = '/v1/engine/shadow-coverage'
    monkeypatch.setenv('ENGINE_SHADOW_COVERAGE_ENABLED', 'true')
    assert (await b.client.get(path, params={'tenant_id': str(tenant)})).status_code in {401, 403, 404}
    member = b.native_headers('member-fixture', 'member', tenant)
    assert (await b.client.get(path, params={'tenant_id': str(tenant)}, headers=member)).status_code in {401, 403, 404}
    response = await b.client.get(path, params={'tenant_id': str(tenant)}, headers=b.founder)
    assert response.status_code == 200, response.text
    rows = {r['task_type']: r for r in response.json()['tasks']}
    expected = {
        'engine.classify': ('frontier', 'llama-small', 'open-weight', True),
        'engine.sol': ('frontier', 'llama-small', 'open-weight', True),
        'engine.open': ('open-weight', 'local-large', 'local large', False),
        'engine.large': ('local large', 'local', 'local small', False),
        # The tenant's own approved code skill is the next rung below local.
        'fixture.boundary': ('local small', 'skill:base.private0@1.0.0', 'code', False),
        'engine.private': ('frontier', 'llama-small', 'open-weight', True),
    }
    for task, (rung, candidate, candidate_rung, metered) in expected.items():
        row = rows[task]
        assert (row['rung'], row['candidate'], row['candidate_rung'], row['metered']) == (rung, candidate, candidate_rung, metered), row
    assert rows['engine.small']['candidate'] is None and rows['engine.small']['reason']
    theirs = await b.client.get(path, params={'tenant_id': str(other)}, headers=b.founder)
    assert theirs.status_code == 200
    foreign = {r['task_type']: r for r in theirs.json()['tasks']}
    assert 'engine.private' not in foreign
    # Another tenant's private skill is never offered as this tenant's candidate.
    assert foreign['fixture.boundary']['candidate'] == 'skill:base.private1@1.0.0'
    # Offline local rungs are never offered; there is no default model to fall back to.
    monkeypatch.delenv('ENGINE_LOCAL_URL')
    rows = {r['task_type']: r for r in (await b.client.get(path, params={'tenant_id': str(tenant)}, headers=b.founder)).json()['tasks']}
    assert rows['engine.open']['candidate'] is None and rows['engine.large']['candidate'] != 'local'


@pytest.mark.asyncio
async def test_paid_shadow_stays_in_budget_and_local_shadow_is_unlimited(boundary, monkeypatch):
    b = await world.build(boundary, monkeypatch)
    tenant, other = b.tenants
    monkeypatch.setattr(random, 'random', lambda: 0.0)
    monkeypatch.setenv('TANK_SHADOW_BUDGET_USD', '0')
    for value in NOT_TRUE:
        setting(monkeypatch, 'ENGINE_SHADOW_COVERAGE_ENABLED', value)
        await world.route(b, tenant, f'Classify: unset {value!r} was charged twice.')
        await settle(b)
    assert await shadows(b, tenant) == []
    monkeypatch.setenv('ENGINE_SHADOW_COVERAGE_ENABLED', 'true')
    paid = await world.route(b, tenant, 'Classify: budget closed, charged twice.')
    await settle(b)
    assert paid['model'] == world.PAID and await shadows(b, tenant) == []
    monkeypatch.setenv('TANK_SHADOW_BUDGET_USD', '1')
    await world.route(b, tenant, 'Classify: budget open, charged twice.')
    await settle(b)
    rows = await shadows(b, tenant)
    assert [(r['primary_model'], r['candidate_model']) for r in rows] == [(world.PAID, 'llama-small')]
    assert rows[0]['candidate_cost_usd'] > 0
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT spent_usd FROM tank.shadow_spend WHERE task_type=$1", b.task_type) > 0
    # The other tenant serves the large local rung; its free local shadow runs with no budget left.
    b.models.right.add('local-large')
    monkeypatch.setenv('TANK_SHADOW_BUDGET_USD', '0')
    served = await world.route(b, other, 'Classify: local, charged twice.')
    await settle(b)
    assert served['model'] == 'local-large' and served['cost_usd'] == 0
    assert [(r['primary_model'], r['candidate_model']) for r in await shadows(b, other)] == [('local-large', 'local')]
    assert len(await shadows(b, tenant)) == 1
    monkeypatch.setenv('ENGINE_STATUS_NUMBERS_ENABLED', 'true')
    response = await b.client.get('/v1/engine/status', params={'tenant_id': str(other)}, headers=b.founder)
    row = next(r for r in response.json()['tasks'] if r['task_type'] == b.task_type)
    assert row['learning']['shadows_run']['live'] == 1
    assert row['learning']['live_shadow_agreement'][0]['candidate'] == 'local'


@pytest.mark.asyncio
async def test_unset_settings_answer_exactly_like_main(boundary, monkeypatch):
    b = await world.build(boundary, monkeypatch)
    tenant = b.tenants[0]
    await world.route(b, tenant)
    unknown = '/v1/engine/not-a-route'
    for value in NOT_TRUE:
        for name in SETTINGS:
            setting(monkeypatch, name, value)
        for headers in ({}, b.founder):
            baseline = await b.client.get(unknown, params={'tenant_id': str(tenant)}, headers=headers)
            for method, path in (('GET', '/v1/engine/shadow-coverage'), ('POST', '/v1/engine/learn')):
                response = await b.client.request(method, path, params={'tenant_id': str(tenant)}, headers=headers,
                    json={'tenant_id': str(tenant), 'task_type': b.task_type} if method == 'POST' else None)
                assert (response.status_code, response.json()) == (baseline.status_code, baseline.json()) == (404, {'detail': 'Not Found'})
        response = await b.client.get('/v1/engine/status', params={'tenant_id': str(tenant)}, headers=b.founder)
        assert response.status_code == 200
        assert all('learning' not in row for row in response.json()['tasks'])
        if value is None:
            first = response.json()
        else:
            assert response.json() == first
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.shadow') == 0
        assert await conn.fetchval('SELECT count(*) FROM tank.engine_graduations WHERE rolled_back_at IS NOT NULL') == 0
