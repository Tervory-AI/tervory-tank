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

@pytest.mark.parametrize('change', [{'scope': 'client'}, {'public': False}, {'public': None}, {'holdout': True}, {'holdout': None}, {'client_matter': True}, {'region': 'za'}, {'tenant_id': 'any'}])
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

@pytest.mark.asyncio
async def test_actual_export_payload_cannot_contain_private_rows(database, monkeypatch):
    import secrets
    pool, _ = database
    monkeypatch.setenv('HF_TOKEN', secrets.token_urlsafe(24))
    monkeypatch.setenv('HF_ORG', 'fixture')
    async with pool.acquire() as conn:
        for n, (tenant, public, client) in enumerate([(PLATFORM_TENANT, True, False), (PLATFORM_TENANT, False, False), (uuid.uuid4(), True, False), (PLATFORM_TENANT, True, True)]):
            await training.save_pair(conn, tenant=tenant, agent='base', task='base.fixture', value={'n': n}, output={'ok': True},
                                     approved_by='fixture', source='gold', ref=str(n), public=public, client_matter=client)
    captured = []
    async def upload(client, org, agent, day, rows, region):
        load('train').validate_rows(rows)  # Any forbidden row fails the export test.
        captured.extend(rows)
    monkeypatch.setattr(training, 'upload_dataset', upload)
    result = await training.export_once()
    assert result['exported'] == 1
    assert [r['input'] for r in captured] == [{'n': 0}]

@pytest.mark.asyncio
@pytest.mark.parametrize('submit,cap,expected_jobs', [(False,'50',0), (True,'50',1), (True,'1',0)])
async def test_launcher_estimates_before_any_submission_and_passes_secrets_only(monkeypatch, capsys, submit, cap, expected_jobs):
    import secrets
    import sys
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    token = secrets.token_urlsafe(24)
    monkeypatch.setenv('HF_TOKEN', token)
    monkeypatch.setenv('HF_ORG', 'fixture')
    monkeypatch.setenv('HF_TRAIN_MAX_USD', cap)
    monkeypatch.setenv('TANK_REGION', 'us-east')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://fixture.invalid/fixture')
    jobs, repos = [], []
    def launch(script, **kwargs):
        assert kwargs['timeout'] == 7200
        assert kwargs['secrets'] == {'HF_TOKEN': token}
        assert token not in str(kwargs['env'])
        assert 'DATABASE_URL' not in kwargs['secrets']
        assert Path(script).name == 'train.py'
        jobs.append(kwargs)
        return SimpleNamespace(id='fixture-job')
    api = SimpleNamespace(list_jobs_hardware=lambda: [SimpleNamespace(name='a10g-small',unit_label='minute',unit_cost_micro_usd=16667)],
                          create_repo=lambda **kw: repos.append(kw), model_info=lambda repo: SimpleNamespace(private=True), run_uv_job=launch)
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=lambda **kw: api))
    import asyncpg
    conn = SimpleNamespace(execute=AsyncMock(), close=AsyncMock())
    monkeypatch.setattr(asyncpg, 'connect', AsyncMock(return_value=conn))
    args = SimpleNamespace(receipt=None, minutes=120, submit=submit, day='2026-10-20')
    if cap == '1':
        with pytest.raises(ValueError):
            await load('run').run(args)
    else:
        await load('run').run(args)
    assert len(jobs) == expected_jobs
    assert len(repos) == expected_jobs
    assert all(r['private'] is True for r in repos)
    assert token not in capsys.readouterr().out


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [{'public': False}, {'public': None}, {'holdout': True}, {'holdout': None},
                                    {'scope': 'client'}, {'tenant_id': 'private'}, {'region': 'za'}])
async def test_upload_rejects_unsafe_rows_before_network(change):
    from unittest.mock import AsyncMock
    client = AsyncMock()
    row = dict(public=True, holdout=False, active=True, client_matter=False, scope='platform',
               region='us-east', task_type='base.fixture', input={}, output={})
    with pytest.raises(ValueError, match='Unsafe training export'):
        await training.upload_dataset(client, 'fixture', 'base', '2026-10-20', [row, row | change])
    client.post.assert_not_called()
    client.get.assert_not_called()


@pytest.mark.asyncio
async def test_legacy_ledger_and_package_pairs_stay_private_after_upgrade(database, monkeypatch):
    import secrets
    pool, _ = database
    monkeypatch.setenv('HF_TOKEN', secrets.token_urlsafe(24))
    monkeypatch.setenv('HF_ORG', 'fixture')
    async with pool.acquire() as conn:
        # Reproduce the pre-upgrade table only in this disposable test database.
        await conn.execute('ALTER TABLE tank.training_pairs DROP COLUMN public')
        for source in ('ledger', 'package'):
            for held in (False, True):
                await conn.execute("""INSERT INTO tank.training_pairs
                    (tenant_id,agent,task_type,region,input,output,approved_by,source,source_ref,holdout)
                    VALUES ($1,'base','base.fixture','us-east',$2::jsonb,'{}','fixture',$3,$4,$5)""",
                    PLATFORM_TENANT, training.encoded({'source': source, 'held': held}), source, str(held), held)
        schema = (ROOT / 'tank/schema.sql').read_text()
        await conn.execute(schema)
        await conn.execute(schema)
        legacy = await conn.fetch('SELECT public,holdout FROM tank.training_pairs')
        assert len(legacy) == 4 and all(row['public'] is False for row in legacy)
        assert sum(row['holdout'] for row in legacy) == 2
        # Even explicitly public legacy provenance must still exclude holdouts.
        for source in ('ledger', 'package'):
            for held in (False, True):
                await training.save_pair(conn, tenant=PLATFORM_TENANT, agent='base', task='base.fixture',
                    value={'public_source': source, 'held': held}, output={}, approved_by='fixture',
                    source=source, ref='public-' + str(held), public=True, holdout=held)
    captured = []
    async def upload(client, org, agent, day, rows, region):
        load('train').validate_rows(rows)
        captured.extend(rows)
    monkeypatch.setattr(training, 'upload_dataset', upload)
    result = await training.export_once()
    assert result['exported'] == 2
    assert {row['input']['public_source'] for row in captured} == {'ledger', 'package'}
    assert all(row['public'] is True and row['holdout'] is False and row['input']['held'] is False for row in captured)
