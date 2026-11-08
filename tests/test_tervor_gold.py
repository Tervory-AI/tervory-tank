from copy import deepcopy
from uuid import uuid4

import pytest
import gold
import tervor_gold
import tervor_dataset
from test_train1 import database as _database
from test_tervor_dataset import example

database = _database


@pytest.mark.asyncio
@pytest.mark.parametrize('product', tervor_gold.FIRST_PRODUCTS)
async def test_product_gold_snapshot_is_held_back_scoped_and_sealed(database, product):
    pool, _ = database
    tenant, other = uuid4(), uuid4()
    async with pool.acquire() as conn:
        for scope in (tenant, other):
            ident = await gold.add_candidate(conn, tenant=scope, skill=product + '.extract', agent=product,
                value={'text': 'held-out fixture'}, expected={'answer': 'reviewed'},
                source='public corpus', ref='fixture', holdout=True)
            await conn.execute("UPDATE tank.gold_examples SET status='checked',checked_by='fixture' WHERE id=$1", ident)
        result = await tervor_gold.snapshot(conn, tenant, product, 'us-east')
        cases = tervor_gold.verify(result, tenant, product)
        assert len(cases) == 1
        assert cases[0]['holdout'] is True
        assert result == await tervor_gold.snapshot(conn, tenant, product, 'us-east')
        assert (await tervor_gold.snapshot(conn, uuid4(), product, 'us-east'))['count'] == 0
        with pytest.raises(ValueError, match='tenant and product'):
            tervor_gold.verify(result, other, product)
        altered = deepcopy(result)
        altered['cases'][0]['expected'] = 'changed'
        with pytest.raises(ValueError, match='integrity'):
            tervor_gold.verify(altered, tenant, product)
        with pytest.raises(ValueError, match='Gold input'):
            await tervor_dataset.collect(conn, tenant, 'base', 'us-east',
                public_rows=[example(tenant, input={'text': 'held-out fixture'}, output='different label')])


@pytest.mark.asyncio
async def test_heldout_training_pair_blocks_copied_corpus_and_unreviewed_gold_is_not_eval(database):
    import training
    pool, _ = database
    tenant = uuid4()
    async with pool.acquire() as conn:
        await training.save_pair(conn, tenant=tenant, agent='tiger', task='tiger.extract',
            value={'text': 'fixture'}, output='answer', approved_by='fixture', source='gold', ref='held', holdout=True)
        with pytest.raises(ValueError, match='Gold input'):
            await tervor_dataset.collect(conn, tenant, 'base', 'us-east', public_rows=[example(tenant)])
        await gold.add_candidate(conn, tenant=tenant, skill='base.extract', agent='base',
            value={'text': 'unreviewed'}, expected='answer', source='fixture', ref='pending', holdout=True)
        empty = await tervor_gold.snapshot(conn, tenant, 'base', 'us-east')
        assert empty['count'] == 0
        with pytest.raises(ValueError, match='nonempty gold'):
            tervor_gold.verify(empty, tenant, 'base')
        assert {'text': 'unreviewed'} in await tervor_gold.forbidden_inputs(conn, tenant, 'us-east')
