"""Coding data preparation; offline dry-run never imports an HF client or fits."""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import sys

TANK_ROOT = Path(__file__).resolve().parents[1]
if str(TANK_ROOT) not in sys.path:
    sys.path.insert(0, str(TANK_ROOT))
if __package__ == 'tank.training_jobs':
    from .. import tervor_code as baseline
    from ..tervor_registry import digest, identity, manifest
else:
    import tervor_code as baseline
    from tervor_registry import digest, identity, manifest
import tervor_dataset
from . import train

SELECTION_FIELDS = ('base_model', 'base_revision', 'licence', 'licence_evidence',
                    'founder_approval', 'hardware', 'hardware_fit_evidence')


def sealed(value: dict) -> dict:
    return dict(value, sha256=digest(value))


def read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a bounded coding bundle file')
    with path.open('rb') as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Coding bundle exceeds the bounded size')
    return json.loads(raw)


def fixture_bundle() -> dict:
    data = baseline.load()
    prepared = baseline.shared_bundle(data)
    public_dir = baseline.FIXTURES.parent / 'public-validation'
    public = read(public_dir / 'record.json')
    raw = (public_dir / 'flit-common.py.txt').read_text()
    licence = (public_dir / 'flit-LICENSE.txt').read_text()
    if (hashlib.sha256(raw.encode()).hexdigest() != public['raw_sha256']
            or hashlib.sha256(licence.encode()).hexdigest() != public['licence_sha256']
            or public['function_source'] not in raw):
        raise ValueError('Public validation evidence hash mismatch')
    source = dict(kind='public', reference=public['reference'], revision=public['revision'],
        licence=public['licence'], provider='public-code', files={public['path']: raw},
        licence_text=licence, licence_sha256=public['licence_sha256'])
    source['sha256'] = baseline.source_hash(source)
    source['provenance_sha256'] = baseline.provenance_hash(source)
    fragment = public['function_source']
    row = tervor_dataset.row(tenant=baseline.PLATFORM, product='opli', kind='public',
        source=source['reference'], provider=source['provider'], licence=source['licence'],
        source_ref=source['revision'] + ':' + source['sha256'], task_type='opli.bug_fix',
        input={'instruction': 'Restore the pinned upstream permission normalization function.',
               'files': {'permissions.py': fragment.replace('(st_mode | 0o644) & ~0o133', 'st_mode')}},
        output={'files': {'permissions.py': fragment}, 'commands': []})
    held = [case['input'] for case in data['cases'] if case['split'] != 'train']
    held += [item['input'] for item in prepared['training']['rows']]
    validation = tervor_dataset.build(baseline.PLATFORM, 'opli', [row], gold_inputs=held)
    evaluation = dict(tenant_id=baseline.PLATFORM, product='opli', **baseline.snapshots(data)['validation'])
    records = []
    for case in data['cases']:
        origin = deepcopy(case['source'])
        if origin['kind'] == 'public':
            origin['licence_text'] = (baseline.FIXTURES.parent / 'sampleproject-LICENSE.txt').read_text()
        records.append(dict(split={'validation': 'evaluation'}.get(case['split'], case['split']),
            input_sha256=digest(case['input']), output_sha256=digest(case['expected']), source=origin))
    records.append(dict(split='validation', input_sha256=digest(row['input']),
                        output_sha256=digest(row['output']), source=source))
    prepared['coding'] = sealed(dict(schema=1, region='us-east', validation=validation,
        evaluation_holdouts=evaluation, provenance=records,
        selection={field: None for field in SELECTION_FIELDS}))
    train.coding_partitions(prepared)
    return prepared


def selection(data: dict) -> dict:
    value = data['coding']['selection']
    if (set(value) != set(SELECTION_FIELDS) or any(value[field] is not None and (
            not isinstance(value[field], str) or len(value[field]) > 2000) for field in SELECTION_FIELDS)):
        raise ValueError('Coding selection must declare all required evidence fields')
    return {field: dict(value=value[field], status='missing' if not (value[field] or '').strip() else 'supplied_unverified')
            for field in SELECTION_FIELDS}


def dry_run(path: Path | None = None, *, version='tervor-code-1.0', day='2026-11-08', region='us-east') -> dict:
    if region != 'us-east' or not re.fullmatch(r'tervor-code-(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', version):
        raise ValueError('Coding preparation requires the US region and a Tervor Code version')
    data = read(path) if path else fixture_bundle()
    training, validation = train.coding_samples(data)
    chosen = selection(data)
    missing = [field for field, item in chosen.items() if item['status'] == 'missing']
    gold_count = data['gold']['count']
    return dict(schema=1, status='blocked', phase='coding_training_preflight', product='opli',
        model_code='tervor-code', proposed_id=identity(version, 'opli', day), selection=chosen,
        selection_approval='not_established', base_plan_evidence='tervory-build/MODEL.md: a Qwen coder base; exact choice undecided',
        missing_selections=missing, region=data['coding']['region'],
        counts=dict(training=len(training), fit_validation=len(validation), gold=gold_count,
                    evaluation_only=data['coding']['evaluation_holdouts']['count']),
        data_hashes=dict(training=data['training']['sha256'], validation=data['coding']['validation']['sha256'],
                         gold=data['gold']['sha256'], coding=data['coding']['sha256']),
        bundle_sha256=digest(data), samples_sha256=digest([training, validation]),
        source_hashes=dict(adapter=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                           trainer=hashlib.sha256(Path(train.__file__).read_bytes()).hexdigest()),
        trainer=dict(entrypoint='tank/training_jobs/train.py', callable='fit', agent='opli',
                     context_limit=train.context_length('opli'), actual_fit_called=False),
        gold_gate=dict(required=200, present=gold_count, missing=max(0, 200-gold_count),
                       independent_review_and_quality_not_proven=True),
        cost_usd=None, cost_reason='Checkpoint, licence approval, hardware fit, quote and runtime not established',
        budget_ceiling_usd=100, paid_jobs=0, provider_requests=0, submitted=False,
        eligible=False, model_quality_measured=False, arbitrary_python_grading=False)


def prepare(args) -> tuple[dict, dict]:
    if not args.bundle or not args.model_version.startswith('tervor-code-'):
        raise ValueError('Opli requires a coding bundle and Tervor Code version')
    data = train.load_coding_bundle(args.bundle)
    chosen = train.coding_selection(data, os.environ['HF_TRAIN_BASE_MODEL'], os.environ['HF_TRAIN_BASE_REVISION'])
    cap = Decimal(os.environ['HF_TRAIN_MAX_USD'])
    if not cap.is_finite() or not 0 < cap <= 100:
        raise ValueError('Coding training must stay within the founder USD 100 ceiling')
    value = manifest(version=args.model_version, product='opli', trained_on=args.day,
        data_hashes=[data['training']['sha256'], data['gold']['sha256'], data['coding']['sha256']],
        model_card=dict(source=chosen['base_model'], base=chosen['base_model'],
            base_revision=chosen['base_revision'], licence=chosen['licence'],
            licence_evidence=chosen['licence_evidence'], founder_approval=chosen['founder_approval'],
            hardware=chosen['hardware'], hardware_fit_evidence=chosen['hardware_fit_evidence']), scores={}, rung='own-trained')
    return data, value
