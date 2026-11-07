import ast
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from tervor_training_fixtures import configured_base as configured_base

from tiger_sheet.patch_source import module, source
from test_tiger_competitors import database as database, postgres as postgres


@pytest.fixture
def trainer():
    return module('tank/training_jobs/train.py')


def row(index, holdout=False):
    return {'region': 'us-east', 'public': True, 'client_matter': False, 'scope': 'platform',
            'holdout': holdout, 'active': True, 'task_type': 'tiger.price_extract',
            'input': {'html': '<p>placeholder ' + str(index) + '</p>', 'url': f'https://placeholder.example/item/{index}'},
            'output': {'items': [{'price': '10.00', 'currency': 'USD'}]},
            'currency': 'USD', 'unit': 'item', 'batch_id': 'placeholder-reviewed-batch'}


@pytest.fixture
def hub(tmp_path, monkeypatch):
    train_rows, held_rows = [row(i) for i in range(60)], [row(100, True), row(101, True)]
    files = {'snapshots/us-east/2026-11-07.jsonl': train_rows, 'holdouts/us-east/2026-11-07.jsonl': held_rows}
    requests = []
    class Missing(Exception):
        pass
    def download(repo, path, **kwargs):
        requests.append((repo, path, kwargs))
        if path not in files:
            raise Missing()
        target = tmp_path/path.replace('/', '-')
        target.write_text(''.join(json.dumps(item) + '\n' for item in files[path]))
        return str(target)
    api = SimpleNamespace(dataset_info=lambda repo: SimpleNamespace(private=True, sha='placeholder-revision'))
    package, errors = ModuleType('huggingface_hub'), ModuleType('huggingface_hub.errors')
    package.hf_hub_download, package.HfApi = download, lambda **kwargs: api
    errors.EntryNotFoundError = Missing
    monkeypatch.setitem(sys.modules, 'huggingface_hub', package)
    monkeypatch.setitem(sys.modules, 'huggingface_hub.errors', errors)
    return api, files, requests


def test_training_snapshot_keeps_gold_out_and_pins_both_regions(trainer, hub):
    api, files, requests = hub
    train, held = trainer.tiger_data(api, 'placeholder-org', '2026-11-07', revision='placeholder-frozen')
    assert len(train) == 60 and len(held) == 2
    assert not any(item['holdout'] for item in train) and all(item['holdout'] for item in held)
    assert all(request[2]['revision'] == 'placeholder-frozen' for request in requests)
    assert trainer.context_length('tiger') == 4096


@pytest.mark.parametrize('change', ['private', 'inactive', 'tenant', 'holdout', 'overlap', 'same_page', 'unchecked_image', 'no_holdout'])
def test_unsafe_or_leaking_training_data_refused(trainer, hub, change):
    api, files, _ = hub
    first = files['snapshots/us-east/2026-11-07.jsonl'][0]
    if change == 'private': first['public'] = False
    if change == 'inactive': first['active'] = False
    if change == 'tenant': first['tenant_id'] = str(uuid4())
    if change == 'holdout': first['holdout'] = True
    if change == 'unchecked_image': first['input']['png_base64'] = 'placeholder'
    if change == 'overlap': files['holdouts/us-east/2026-11-07.jsonl'][0]['input'] = deepcopy(first['input'])
    if change == 'same_page': files['holdouts/us-east/2026-11-07.jsonl'][0]['input']['url'] = first['input']['url'] + '?capture=next'
    if change == 'no_holdout': files['holdouts/us-east/2026-11-07.jsonl'] = []
    with pytest.raises(ValueError):
        trainer.tiger_data(api, 'placeholder-org', '2026-11-07')


def test_price_eval_compares_only_labelled_fields_and_never_guesses(trainer):
    gold = [row(1, True)]
    good = {'items': [{'name': 'extra real field', 'price': 10, 'currency': 'usd'}]}
    assert trainer.score_prices(gold, [good])['eligible']
    for bad in ['not JSON', {'items': [{'price': 'NaN', 'currency': 'USD'}]},
                {'items': [{'price': 11, 'currency': 'USD'}]}, {'items': []},
                {'items': [{'price': 10, 'currency': 'EUR'}]}]:
        result = trainer.score_prices(gold, [bad])
        assert not result['eligible'] and result['passed'] == 0
    with pytest.raises(ValueError):
        trainer.score_prices([], [])


@pytest.mark.asyncio
async def test_tiger_submission_uses_existing_budget_reservation_and_private_output(trainer, hub, monkeypatch):
    api, _, _ = hub
    submission = []
    api.list_jobs_hardware = lambda: [SimpleNamespace(name='a10g-small', unit_label='minute', unit_cost_micro_usd=10000)]
    api.create_repo = lambda **kwargs: submission.append(('repo', kwargs))
    api.model_info = lambda repo: SimpleNamespace(private=True)
    monkeypatch.setattr(api, 'run_uv_job', lambda *args, **kwargs: submission.append(('job', kwargs)) or SimpleNamespace(id='placeholder-job'), raising=False)
    conn = SimpleNamespace(execute=AsyncMock(), fetchval=AsyncMock(return_value=False), fetch=AsyncMock(return_value=[]), close=AsyncMock())
    import asyncpg
    monkeypatch.setattr(asyncpg, 'connect', AsyncMock(return_value=conn))
    monkeypatch.setitem(sys.modules, 'train', trainer)
    for name, value in {'HF_ORG': 'placeholder-org', 'HF_TOKEN': 'placeholder', 'DATABASE_URL': 'placeholder', 'TANK_REGION': 'us-east'}.items():
        monkeypatch.setenv(name, value)
    runner = module('tank/training_jobs/run.py')
    args = SimpleNamespace(agent='tiger', day='2026-11-07', minutes=120, submit=True, receipt=None, job_id='')
    result = await runner.run(args)
    assert result['status'] == 'running' and result['cost_usd'] == Decimal('1.20')
    assert submission[0][1]['private'] is True and '/tervory-own-tiger-' in submission[0][1]['repo_id']
    env = submission[1][1]['env']
    assert env['TRAIN_AGENT'] == 'tiger' and env['TIGER_DATASET_REVISION'] == 'placeholder-revision'
    assert 'DATABASE_URL' not in env and set(submission[1][1]['secrets']) == {'HF_TOKEN'}
    assert any('INSERT INTO tank.training_jobs' in call.args[0] for call in conn.execute.call_args_list)
    assert conn.fetch.call_args.args[-1] == 'tiger'
    monkeypatch.setenv('HF_TRAIN_MAX_USD', '0.01')
    with pytest.raises(ValueError):
        await runner.run(args)
    assert len(submission) == 2


@pytest.mark.asyncio
async def test_tiger_bill_reconciliation_is_once_and_does_not_change_legal_policy(database):
    runner = module('tank/training_jobs/run.py')
    await database.execute("""INSERT INTO tank.training_jobs(id,tenant_id,region,model_repo,estimated_usd)
        VALUES('placeholder-job',$1,'us-east','placeholder-org/tervory-own-tiger-placeholder',2)""", runner.PLATFORM)
    gate = {'method': 'exact_price_fields', 'n': 2, 'passed': 1, 'agreement': .5, 'gold_holdout': True, 'eligible': False}
    async with database.acquire() as conn:
        before = await conn.fetchval('SELECT count(*) FROM tank.policy')
        ident = await runner.record_receipt(conn, 'placeholder-job', Decimal('1.20'), gate)
        assert await runner.record_receipt(conn, 'placeholder-job', Decimal('1.20'), gate) == ident
        assert await conn.fetchval('SELECT count(*) FROM tank.policy') == before
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE id=$1', ident) == 1
        with pytest.raises(ValueError):
            await runner.record_receipt(conn, 'placeholder-job', Decimal('2'))


@pytest.mark.asyncio
async def test_training_provenance_links_only_tigers_batches(database):
    from datetime import date
    runner = module('tank/training_jobs/run.py')
    for agent in ('base', 'tiger'):
        await database.execute("""INSERT INTO tank.training_snapshot_batches(tenant_id,region,day,agent,batch_id)
            VALUES($1,'us-east',$2,$3,$3||'-placeholder')""", runner.PLATFORM, date(2026, 11, 7), agent)
    async with database.acquire() as conn:
        await runner.link_snapshot_batches(conn, 'placeholder-job', 'placeholder-org/tervory-own-tiger-placeholder',
                                           '2026-11-07', agent='tiger')
        rows = await conn.fetch('SELECT batch_id FROM tank.training_job_batches WHERE job_id=$1', 'placeholder-job')
    assert [item['batch_id'] for item in rows] == ['tiger-placeholder']


def test_gpu_entrypoint_trains_only_snapshot_and_writes_separate_gold_gate(trainer, hub, tmp_path, monkeypatch):
    from contextlib import nullcontext
    api, _, _ = hub
    captured = {}
    class Inputs(dict):
        def to(self, device): return self
    class Tokens:
        shape = (1, 2)
        def __getitem__(self, index): return 'placeholder answer'
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs):
            assert kwargs['enable_thinking'] is False
            captured.setdefault('held_prompts', []).append(messages)
            return Inputs(input_ids=Tokens())
        def decode(self, tokens, **kwargs):
            return json.dumps({'items': [{'price': '10', 'currency': 'USD'}]})
    class FakeTrainer:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.processing_class = Tokenizer()
            self.model = SimpleNamespace(device='cpu', eval=lambda: None, generate=lambda **kw: [Tokens()])
        def train(self): captured['trained'] = True
        def evaluate(self): return {'eval_loss': .5}
        def save_model(self, path): (tmp_path/'lora').mkdir()
    dependencies = {
        'datasets': {'Dataset': SimpleNamespace(from_list=lambda rows: rows)},
        'peft': {'LoraConfig': lambda **kwargs: kwargs},
        'trl': {'SFTConfig': lambda **kwargs: kwargs, 'SFTTrainer': FakeTrainer},
        'torch': {'inference_mode': nullcontext},
    }
    for name, fields in dependencies.items():
        fake = ModuleType(name)
        fake.__dict__.update(fields)
        monkeypatch.setitem(sys.modules, name, fake)
    api.model_info = lambda repo: SimpleNamespace(private=True)
    api.upload_folder = lambda **kwargs: captured.update(upload=kwargs)
    monkeypatch.setattr(trainer, 'Path', lambda path: tmp_path/'lora'/path.removeprefix('/tmp/lora/')
                        if str(path).startswith('/tmp/lora/') else Path(path))
    for name, value in {'HF_TOKEN': 'placeholder', 'HF_ORG': 'placeholder-org', 'OUTPUT_REPO': 'placeholder-org/model',
                        'TRAIN_DAY': '2026-11-07', 'TRAIN_AGENT': 'tiger', 'TIGER_DATASET_REVISION': 'placeholder-frozen'}.items():
        monkeypatch.setenv(name, value)
    trainer.main()
    assert captured['trained'] and captured['model'] == 'fixture/training-base'
    assert captured['args']['model_init_kwargs']['revision'] == 'a' * 40
    assert len(captured['train_dataset']) + len(captured['eval_dataset']) == 60
    assert all('/item/100' not in json.dumps(sample) for sample in captured['train_dataset'])
    result = json.loads((tmp_path/'lora/holdout.json').read_text())
    assert result['n'] == 2 and result['eligible'] and result['method'] == 'exact_price_fields'
    assert json.loads((tmp_path/'lora/evaluation.json').read_text())['gold_holdout'] is False
    assert captured['upload']['repo_id'] == 'placeholder-org/model'


@pytest.mark.asyncio
async def test_nightly_export_includes_checked_public_gold_separately(database, monkeypatch):
    import training
    import gold
    from datetime import date
    namespace = dict(training.__dict__)
    parsed = ast.parse(source('tank/training.py'))
    function = next(node for node in parsed.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'export_once')
    exec(compile(ast.Module(body=[function], type_ignores=[]), 'proposed training export', 'exec'), namespace)
    platform = training.PLATFORM_TENANT
    train = row(1)
    await database.execute("""INSERT INTO tank.training_pairs(tenant_id,agent,task_type,region,input,output,
        approved_by,source,source_ref,public,batch_id,currency,unit)
        VALUES($1,'tiger','tiger.price_extract','us-east',$2::jsonb,$3::jsonb,'placeholder-reviewer',
               'gold','placeholder-training',true,'placeholder-batch','USD','item')""",
        platform, json.dumps(train['input']), json.dumps(train['output']))
    for index, (status, public, tenant, auto) in enumerate([
        ('checked', True, platform, False), ('candidate', True, platform, False),
        ('rejected', True, platform, False), ('checked', False, platform, False),
        ('checked', True, uuid4(), False), ('checked', True, platform, True),
    ]):
        item = row(100 + index, True)
        await database.execute("""INSERT INTO tank.gold_examples(tenant_id,region,skill_id,agent,input,expected,
            status,holdout,source,source_ref,input_hash,public,auto_label,batch_id,currency,unit)
            VALUES($1,'us-east','tiger.price_extract','tiger',$2::jsonb,$3::jsonb,$4,true,'placeholder',
                   $5,$5,$6,$7,'placeholder-batch','USD','item')""", tenant, json.dumps(item['input']),
            json.dumps(item['output']), status, str(index), public, auto)
    exported = []
    async def upload(client, org, agent, day, rows, region, held):
        exported.append((rows, held))
    namespace['runtime'] = lambda: SimpleNamespace(box_region=lambda: 'us-east', pool=lambda: database)
    namespace['upload_dataset'] = upload
    monkeypatch.setattr(gold, 'AGENTS', ('tiger',))
    monkeypatch.setenv('HF_TOKEN', 'placeholder')
    monkeypatch.setenv('HF_ORG', 'placeholder-org')
    result = await namespace['export_once'](day=date(2026, 11, 7))
    assert result['exported'] == 1
    assert len(exported) == 1 and len(exported[0][0]) == 1 and len(exported[0][1]) == 1
    assert exported[0][1][0]['input']['url'].endswith('/100')
    assert exported[0][1][0]['holdout'] is True
