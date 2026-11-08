"""Coding trainer/data readiness, with all provider/model/fit boundaries faked."""
from copy import deepcopy
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest
from tank.training_jobs import coding, run, train
from tank import tervor_code as baseline
from tank.tervor_registry import digest


def reseal(data):
    for snapshot, field in ((data['training'], 'rows'), (data['gold'], 'cases'),
            (data['coding']['validation'], 'rows'), (data['coding']['evaluation_holdouts'], 'rows')):
        snapshot['count'] = len(snapshot[field])
        snapshot['sha256'] = digest(snapshot[field])
    data['sha256'] = digest([data['training'], data['gold']])
    data['coding']['sha256'] = digest({k: v for k, v in data['coding'].items() if k != 'sha256'})
    return data


def structural_bundle():
    """200 artificial test-only holdouts; never a claim of reviewed production gold."""
    data = coding.fixture_bundle()
    for i in range(195):
        value = {'files': {f'fixture_{i}.py': f'fixture_{i} = 0\n'}}
        expected = {'files': {f'fixture_{i}.py': f'fixture_{i} = 1\n'}}
        source = dict(kind='synthetic', reference=f'test-only-heldout-{i}', revision='1',
            licence='evaluation-only', provider='synthetic-fixture', files=value['files'])
        source['sha256'] = baseline.source_hash(source)
        source['provenance_sha256'] = baseline.provenance_hash(source)
        data['gold']['cases'].append(dict(input=value, expected=expected, task_type='opli.bug_fix', holdout=True))
        data['coding']['provenance'].append(dict(split='gold', input_sha256=digest(value),
            output_sha256=digest(expected), source=source))
    data['coding']['selection'] = dict(base_model='fixture/coding-base', base_revision='a'*40,
        licence='test-only licence', licence_evidence='test-only licence record',
        founder_approval='test-only approval record', hardware='a10g-small', hardware_fit_evidence='test-only fit record')
    return reseal(data)


def write_bundle(tmp_path, data):
    path = tmp_path / 'bundle.json'
    path.write_text(json.dumps(data))
    return path


def test_real_public_training_and_validation_are_separate_from_all_holdouts():
    data = coding.fixture_bundle()
    rows, validation = train.coding_partitions(data)
    samples, valid_samples = train.coding_samples(data)
    assert len(rows) == len(validation) == len(samples) == len(valid_samples) == 1
    assert rows[0]['licence'] == 'MIT' and validation[0]['licence'] == 'BSD-3-Clause'
    assert rows[0]['source'] != validation[0]['source']
    assert all(row['provider'] == 'public-code' for row in rows + validation)
    assert data['gold']['count'] == 5 and data['coding']['evaluation_holdouts']['count'] == 2
    assert 'add_one' in samples[0]['completion'][0]['content']
    assert 'normalize_file_permissions' in valid_samples[0]['completion'][0]['content']
    all_holdouts = [case['input'] for case in data['gold']['cases']]
    all_holdouts += [row['input'] for row in data['coding']['evaluation_holdouts']['rows']]
    assert not {digest(v) for v in all_holdouts} & {digest(r['input']) for r in rows + validation}


@pytest.mark.parametrize('change', ['tenant', 'region', 'holdout', 'public_licence', 'source_hash',
    'duplicate_input', 'source_family', 'synthetic_validation', 'nonpublic_completion', 'unused_provenance'])
def test_recomputed_outer_hash_cannot_hide_unsafe_coding_data(change):
    data = deepcopy(coding.fixture_bundle())
    row = data['coding']['validation']['rows'][0]
    record = next(r for r in data['coding']['provenance'] if r['split'] == 'validation')
    if change == 'tenant':
        row['tenant_id'] = '00000000-0000-0000-0000-000000000002'
    elif change == 'region':
        data['coding']['region'] = 'za'
    elif change == 'holdout':
        row['holdout'] = True
    elif change == 'public_licence':
        record['source']['licence_text'] = 'unverified replacement'
    elif change == 'source_hash':
        record['source']['files']['extra.py'] = 'changed\n'
    elif change == 'duplicate_input':
        row['input'] = data['gold']['cases'][0]['input']
        record['input_sha256'] = digest(row['input'])
    elif change == 'source_family':
        source = record['source']
        source['reference'] = data['training']['rows'][0]['source']
        row['source'] = source['reference']
        source['provenance_sha256'] = baseline.provenance_hash(source)
    elif change == 'synthetic_validation':
        source = record['source']
        source.update(kind='synthetic', provider='synthetic-fixture')
        source['provenance_sha256'] = baseline.provenance_hash(source)
    elif change == 'nonpublic_completion':
        row['output']['files']['permissions.py'] = 'provider_generated_private_completion\n'
        record['output_sha256'] = digest(row['output'])
    else:
        data['coding']['provenance'].append(dict(split='unused', input_sha256='a'*64, output_sha256='b'*64))
    reseal(data)
    with pytest.raises(ValueError):
        train.coding_partitions(data)


@pytest.mark.asyncio
async def test_existing_entrypoint_dry_run_is_offline_and_ignores_ambient_checkpoint(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline dry-run crossed a provider, model or database boundary')
    monkeypatch.setattr(socket, 'socket', forbidden)
    monkeypatch.setattr(train, 'fit', forbidden)
    monkeypatch.setenv('HF_TRAIN_BASE_MODEL', 'not-approval/ambient')
    monkeypatch.setenv('TANK_REGION', 'us-east')
    args = SimpleNamespace(agent='opli', dry_run=True, submit=False, receipt=None, job_id='',
        bundle=None, model_version='', day='')
    result = await run.run(args)
    assert result['status'] == 'blocked' and result['paid_jobs'] == result['provider_requests'] == 0
    assert result['counts'] == {'training': 1, 'fit_validation': 1, 'gold': 5, 'evaluation_only': 2}
    assert result['selection_approval'] == 'not_established'
    assert all(item['status'] == 'missing' and item['value'] is None for item in result['selection'].values())
    assert result['cost_usd'] is None and result['gold_gate']['missing'] == 195
    assert result['trainer']['actual_fit_called'] is False
    args.submit = True
    with pytest.raises(ValueError, match='Dry run cannot submit'):
        await run.run(args)
    args.submit = False
    monkeypatch.setenv('TANK_REGION', 'za')
    with pytest.raises(ValueError, match='US region'):
        await run.run(args)


def test_production_loader_keeps_existing_200_gold_and_selection_gates(tmp_path, monkeypatch):
    path = write_bundle(tmp_path, coding.fixture_bundle())
    with pytest.raises(ValueError, match='Invalid training or gold'):
        train.load_coding_bundle(path)
    data = structural_bundle()
    path = write_bundle(tmp_path, data)
    loaded = train.load_coding_bundle(path)
    assert loaded == data
    with pytest.raises(ValueError, match='does not match'):
        train.coding_selection(data, 'different/base', 'b'*40)
    data['coding']['selection']['founder_approval'] = None
    reseal(data)
    with pytest.raises(ValueError, match='Explicit coding base'):
        train.coding_selection(data, 'fixture/coding-base', 'a'*40)
    monkeypatch.setenv('HF_TRAIN_MAX_USD', '100')
    monkeypatch.setenv('HF_TRAIN_BASE_MODEL', 'fixture/coding-base')
    monkeypatch.setenv('HF_TRAIN_BASE_REVISION', 'a'*40)
    path = write_bundle(tmp_path, structural_bundle())
    args = SimpleNamespace(bundle=path, model_version='tervor-code-1.0', day='2026-11-08', receipt=None, job_id='')
    prepared, metadata = run.prepare_bundle(args, 'opli')
    assert prepared['coding']['validation']['count'] == 1
    assert metadata['id'] == 'tervor-code-1.0-opli-20261108'
    assert metadata['model_card']['licence_evidence'] == 'test-only licence record'
    assert metadata['scores'] == {}
    monkeypatch.setenv('HF_TRAIN_MAX_USD', '101')
    with pytest.raises(ValueError, match='USD 100 ceiling'):
        run.prepare_bundle(args, 'opli')


@pytest.mark.asyncio
async def test_database_heldout_guard_also_checks_fit_validation():
    data = coding.fixture_bundle()
    forbidden = data['coding']['validation']['rows'][0]['input']
    class Conn:
        async def fetch(self, query, *args):
            assert args[0] == run.PLATFORM and args[1] == 'us-east'
            return [{'input': forbidden}]
    with pytest.raises(ValueError, match='Gold input'):
        await run.check_database_holdouts(Conn(), data, 'opli', 'us-east')


def test_actual_trainer_entrypoint_consumes_explicit_partitions_with_fake_fit(tmp_path, monkeypatch):
    data = structural_bundle()
    path = write_bundle(tmp_path, data)
    for key, value in dict(HF_TOKEN='fixture-only', HF_ORG='fixture', OUTPUT_REPO='fixture/tervor-code-1.0-opli-20261108',
        TRAIN_DAY='2026-11-08', TRAIN_AGENT='opli', TERVOR_TRAIN_BUNDLE_PATH=str(path),
        HF_TRAIN_BASE_MODEL='fixture/coding-base', HF_TRAIN_BASE_REVISION='a'*40).items():
        monkeypatch.setenv(key, value)
    calls, uploads = [], []
    def fake_fit(base, revision, training, validation, **kwargs):
        calls.append((base, revision, training, validation, kwargs))
        return SimpleNamespace(), {'eval_loss': 0.125}
    class API:
        def model_info(self, repo):
            return SimpleNamespace(private=True)
        def upload_folder(self, **kwargs):
            uploads.append(kwargs)  # Fake only: no upload/model job/provider call.
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=lambda **kw: API()))
    monkeypatch.setattr(train, 'fit', fake_fit)
    output = tmp_path / 'lora'
    output.mkdir()
    monkeypatch.setattr(train, 'Path', lambda p: output / Path(p).name if str(p).startswith('/tmp/lora/') else Path(p))
    train.main()
    assert len(calls) == len(uploads) == 1
    base, revision, training, validation, options = calls[0]
    assert base == 'fixture/coding-base' and revision == 'a'*40 and options['max_length'] == 4096
    assert len(training) == len(validation) == 1
    assert 'add_one' in training[0]['completion'][0]['content']
    assert 'normalize_file_permissions' in validation[0]['completion'][0]['content']
    assert json.loads((output / 'holdout.json').read_text()) == {
        'method': 'tervor_gold_pending', 'gold_holdout': True, 'n': 200, 'eligible': False}


def test_declared_private_holdout_and_extra_private_training_metadata_are_rejected():
    for change in ('private_holdout', 'private_training_marker'):
        data = deepcopy(coding.fixture_bundle())
        if change == 'private_holdout':
            record = next(r for r in data['coding']['provenance'] if r['split'] == 'gold')
            record['source']['kind'] = 'tenant'
            record['source']['provenance_sha256'] = baseline.provenance_hash(record['source'])
        else:
            data['training']['rows'][0]['client_matter'] = True
        reseal(data)
        with pytest.raises(ValueError):
            train.coding_partitions(data)


def test_coding_gate_is_bound_to_the_exact_data_validated(tmp_path, monkeypatch):
    path = write_bundle(tmp_path, structural_bundle())
    monkeypatch.setattr(train, 'load_tervor_bundle', lambda *args: ([], []))
    with pytest.raises(ValueError, match='changed during validation'):
        train.load_coding_bundle(path)


def test_checked_in_preflight_manifest_is_exact_and_selection_stays_missing():
    import hashlib
    path = Path(__file__).parents[1] / 'docs/models/evidence/tervor-code-training-preflight-2026-11-08.json'
    value = json.loads(path.read_text())
    assert value == coding.dry_run()
    assert value['source_hashes']['trainer'] == hashlib.sha256(Path(train.__file__).read_bytes()).hexdigest()
    assert value['status'] == 'blocked' and value['submitted'] is False
    assert all(item == {'status': 'missing', 'value': None} for item in value['selection'].values())
