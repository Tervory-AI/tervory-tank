from decimal import Decimal
import json
from types import SimpleNamespace

import pytest
from training_jobs import run, train
import tervor_registry
from test_train1 import database as _database
from test_tervor_round_one import fixture_bundle

database = _database


@pytest.mark.asyncio
async def test_no_spend_cap_means_no_quote_or_job(monkeypatch):
    monkeypatch.setenv('HF_ORG', 'fixture')
    monkeypatch.setenv('HF_TOKEN', 'fixture')
    monkeypatch.delenv('HF_TRAIN_MAX_USD', raising=False)
    result = await run.run(SimpleNamespace(submit=False, receipt=None, agent='base'))
    assert result == {'status': 'not_configured', 'settings': ['HF_TRAIN_MAX_USD']}


@pytest.mark.asyncio
@pytest.mark.parametrize('product', ['zenas','base','tiger'])
async def test_bundled_job_uses_private_identity_cap_and_exact_billing_receipt(database, monkeypatch, tmp_path, product):
    import sys
    pool, _ = database
    for key, value in {'HF_ORG':'fixture','HF_TOKEN':'fixture', 'TANK_REGION':'us-east',
        'HF_TRAIN_BASE_MODEL':'fixture/base','HF_TRAIN_BASE_REVISION':'a'*40,'HF_TRAIN_MAX_USD':'3'}.items():
        monkeypatch.setenv(key, value)
    data = fixture_bundle(product)
    path = tmp_path/'bundle.json'
    path.write_text(json.dumps(data))
    uploaded, jobs = {}, []
    class API:
        def list_jobs_hardware(self):
            return [SimpleNamespace(name='a10g-small',unit_label='minute',unit_cost_micro_usd=16667)]
        def create_repo(self, **kwargs):
            assert kwargs['private'] is True
        def model_info(self, repo):
            return SimpleNamespace(private=True)
        def upload_file(self, **kwargs):
            uploaded[kwargs['path_in_repo']] = kwargs['path_or_fileobj']
        def run_uv_job(self, script, **kwargs):
            jobs.append(kwargs)
            assert set(kwargs['secrets']) == {'HF_TOKEN'}
            assert 'DATABASE_URL' not in kwargs['env']
            assert kwargs['timeout'] == 7200 and kwargs['env']['TRAIN_AGENT'] == product
            assert kwargs['env']['OUTPUT_REPO'] == f'fixture/tervor-lite-1.0-{product}-20261107'
            assert set(uploaded) == {'training-config.json','training-bundle.json'}
            return SimpleNamespace(id='fixture-job')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=lambda **kwargs: API()))
    args = SimpleNamespace(submit=True, dry_run=False, receipt=None, job_id='', minutes=120,
                           agent=product, day='2026-11-07', bundle=path, model_version='tervor-lite-1.0')
    args.submit, args.dry_run = False, True
    preview = await run.run(args)
    assert preview['dry_run'] and preview['training_rows'] == 20 and preview['gold_rows'] == 200
    assert preview['model_id'] == f'tervor-lite-1.0-{product}-20261107'
    assert jobs == [] and uploaded == {}
    args.submit, args.dry_run = True, False
    result = await run.run(args)
    assert result['cost_usd'] == Decimal('2.000040') and len(jobs) == 1
    assert json.loads(uploaded['training-bundle.json']) == data
    rows, gold = train.load_tervor_bundle(path, product)
    assert len(rows) == 20 and len(gold) == 200
    async with pool.acquire() as conn:
        model_id = f'tervor-lite-1.0-{product}-20261107'
        metadata = await tervor_registry.get(conn, run.PLATFORM, model_id)
        assert metadata['data_hashes'] == sorted([data['training']['sha256'], data['gold']['sha256']])
        before = await conn.fetch('SELECT * FROM tank.policy ORDER BY task_type,tenant_id')
        await run.record_receipt(conn, 'fixture-job', Decimal('1.50'), {'method':'tervor_gold_pending'})
        await run.record_receipt(conn, 'fixture-job', Decimal('1.50'))
        assert await conn.fetchval('SELECT model FROM tank.ledger') == model_id
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger') == 1
        assert await conn.fetch('SELECT * FROM tank.policy ORDER BY task_type,tenant_id') == before
    with pytest.raises(ValueError, match='already has a job'):
        await run.run(args)
    assert len(jobs) == 1


def test_gpu_bundle_refuses_tenant_tampering_even_with_recomputed_hash(tmp_path):
    data = fixture_bundle('base')
    data['training']['rows'][0]['tenant_id'] = '00000000-0000-0000-0000-000000000002'
    data['training']['sha256'] = tervor_registry.digest(data['training']['rows'])
    data['sha256'] = tervor_registry.digest([data['training'],data['gold']])
    path = tmp_path/'bad.json'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='Unsafe training'):
        train.load_tervor_bundle(path, 'base')


@pytest.mark.asyncio
async def test_bundle_cannot_relabel_another_products_held_out_input(database):
    import gold
    pool, _ = database
    data = fixture_bundle('base')
    async with pool.acquire() as conn:
        await gold.add_candidate(conn, tenant=run.PLATFORM, skill='tiger.extract', agent='tiger',
            value=data['training']['rows'][0]['input'], expected='held back', source='public',
            ref='other product gold', holdout=True)
        with pytest.raises(ValueError, match='Gold input'):
            await run.check_database_holdouts(conn, data, 'base', 'us-east')
