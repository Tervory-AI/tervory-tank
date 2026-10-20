"""No live GPU, HF credentials or client exports are needed to validate training."""
from decimal import Decimal
import importlib.util
from pathlib import Path
import uuid
import pytest
import training
from gold import PLATFORM_TENANT
from test_train1 import database as _database

database = _database
ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'jobs/train' / f'{name}.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

@pytest.mark.parametrize('rate,minutes,cap', [('1',51,'50'), ('NaN',2,'50'), ('1',-1,'50'), ('1',2,'-1')])
def test_refuses_bad_or_over_budget_job(rate, minutes, cap):
    with pytest.raises(ValueError):
        load('run').estimate(Decimal(rate), minutes, Decimal(cap))


def test_accepts_capped_estimate():
    assert load('run').estimate(Decimal('0.025'), 120, Decimal('50')) == Decimal('3')

@pytest.mark.parametrize('change', [{'tenant_id': uuid.uuid4()}, {'public': False}, {'client_matter': True},
                                    {'region': 'za'}, {'holdout': True}, {'active': False}])
def test_private_or_za_never_exports(change):
    row = dict(tenant_id=PLATFORM_TENANT, public=True, client_matter=False, region='us-east', holdout=False, active=True)
    assert training.exportable(row)
    assert not training.exportable(row | change)

@pytest.mark.parametrize('change', [{'scope': 'client'}, {'public': False}, {'client_matter': True}, {'region': 'za'}, {'tenant_id': 'any'}])
def test_training_aborts_if_export_contains_one_private_row(change):
    row = dict(public=True, client_matter=False, scope='platform', region='us-east', holdout=False,
               active=True, task_type='base.fixture', input={}, output={})
    load('train').validate_rows([row])
    with pytest.raises(ValueError):
        load('train').validate_rows([row, row | change])

@pytest.mark.asyncio
async def test_billed_receipt_is_recorded_once_and_estimate_is_not_spend(database):
    pool, _ = database
    mod = load('run')
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.training_jobs(id,tenant_id,region,model_repo,estimated_usd) VALUES ('fixture',$1,'us-east','fixture/model',50)", PLATFORM_TENANT)
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger') == 0
        await mod.record_receipt(conn, 'fixture', Decimal('2.125'))
        await mod.record_receipt(conn, 'fixture', Decimal('2.125'))
        assert await conn.fetchval('SELECT sum(cost_usd) FROM tank.ledger') == Decimal('2.125')
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger') == 1
        with pytest.raises(ValueError):
            await mod.record_receipt(conn, 'fixture', Decimal('3'))
        with pytest.raises(ValueError):
            await mod.record_receipt(conn, 'unknown', Decimal('3'))
