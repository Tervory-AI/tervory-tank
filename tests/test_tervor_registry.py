"""Tervor identities and private evidence, without serving or provider calls."""
from copy import deepcopy
import json
import uuid

import pytest
import tervor_registry as registry
from execution_receipt import capture
from test_train1 import database as _database

database = _database


def sample(**changes):
    values = dict(version='tervor-lite-1.0', product='zenas', trained_on='2026-11-07',
        data_hashes=['a' * 64], model_card={'source': 'fixture/model', 'licence': 'fixture licence',
        'base': 'fixture/base', 'base_revision': 'fixture-revision'}, scores={}, rung='local')
    return registry.manifest(**(values | changes))


@pytest.mark.parametrize('code', sorted(registry.CODES))
def test_codes_and_exact_receipt_identity(code):
    item = sample(version=code + '-12.3')
    assert item['id'] == code + '-12.3-zenas-20261107'
    receipt = capture(ledger_id=str(uuid.uuid4()), tenant_id=str(uuid.uuid4()), task_type='zenas.reasoning',
        requested_model=item['id'], answered_model=item['id'], dispatched={'max_tokens': 30},
        headers={'x-litellm-model-group': item['id']}, response={'model': 'fixture/base'}, delivered=True)
    assert receipt['model'] == receipt['requested_model'] == receipt['upstream_model_group'] == item['id']


@pytest.mark.parametrize('change', [
    {'version': 'tervor-lite-01.0'}, {'version': 'tervor-lite-1'}, {'version': 'other-1.0'},
    {'product': '../zenas'}, {'trained_on': '2026-02-30'}, {'trained_on': '20261107'},
    {'data_hashes': []}, {'data_hashes': ['invalid']}, {'model_card': {'source': 'only'}},
    {'scores': {'correctness': float('nan')}}, {'scores': {'correctness': 1.1}}, {'rung': 'paid'},
    {'rollback': 'tervor-lite-1.0-zenas-20261107'},
])
def test_rejects_invalid_manifest(change):
    with pytest.raises(ValueError):
        sample(**change)


@pytest.mark.asyncio
async def test_private_immutable_registry_and_day_zero(database):
    pool, _ = database
    tenant, other = uuid.uuid4(), uuid.uuid4()
    item = sample()
    async with pool.acquire() as conn:
        policies = await conn.fetch('SELECT * FROM tank.policy ORDER BY task_type,tenant_id')
        assert await registry.list_models(conn, tenant, 'zenas') == []
        assert await registry.register(conn, tenant, item) == item['id']
        assert await registry.register(conn, tenant, item) == item['id']
        assert await registry.get(conn, other, item['id']) is None
        assert await registry.list_models(conn, other, 'zenas') == []
        assert await registry.list_models(conn, tenant, 'zenas') == [item]
        altered = deepcopy(item)
        altered['scores'] = {'correctness': .99}
        with pytest.raises(ValueError, match='different evidence'):
            await registry.register(conn, tenant, altered)
        assert await registry.get(conn, tenant, item['id']) == item
        next_item = sample(version='tervor-lite-1.1', rollback=item['id'])
        with pytest.raises(ValueError, match='same tenant and product'):
            await registry.register(conn, other, next_item)
        with pytest.raises(ValueError, match='same tenant and product'):
            await registry.register(conn, tenant, sample(product='base', rollback=item['id']))
        assert await registry.register(conn, tenant, next_item) == next_item['id']
        with pytest.raises(ValueError, match='different evidence'):
            await registry.register(conn, tenant, sample(trained_on='2026-11-08'))
        assert await conn.fetch('SELECT * FROM tank.policy ORDER BY task_type,tenant_id') == policies
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger') == 0


@pytest.mark.asyncio
async def test_registry_rls_under_existing_tenant_security(database):
    pool, _ = database
    tenant, other = uuid.uuid4(), uuid.uuid4()
    async with pool.acquire() as conn:
        await registry.register(conn, tenant, sample())
        await conn.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
        from pathlib import Path
        schema = (Path(__file__).resolve().parents[1] / 'tank/schema.sql').read_text()
        owned = schema.split('-- BEGIN tervor\n')[1].split('-- END tervor')[0]
        await conn.execute(owned)
        await conn.execute(owned)
        role = 'tervor_' + uuid.uuid4().hex
        await conn.execute(f'CREATE ROLE {role}')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO {role}')
            await conn.execute(f'GRANT SELECT,INSERT ON tank.tervor_models TO {role}')
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE {role}')
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(other))
                assert await conn.fetchval('SELECT count(*) FROM tank.tervor_models') == 0
                await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(tenant))
                assert json.loads(await conn.fetchval('SELECT manifest FROM tank.tervor_models')) == sample()
        finally:
            await conn.execute(f'DROP OWNED BY {role}')
            await conn.execute(f'DROP ROLE {role}')
