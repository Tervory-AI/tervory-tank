import copy
from dataclasses import replace
import os
import py_compile
from types import SimpleNamespace

import pytest
import skala
from test_skala_approval_safety import package, evaluation, reason


@pytest.mark.parametrize('asset', ['rules.json', 'templates/prompt.txt', 'weights.bin', 'skill.yaml'])
@pytest.mark.parametrize('operation', ['edit', 'add', 'delete'])
def test_runtime_asset_changes_invalidate_approval(tmp_path, asset, operation):
    pkg = package(tmp_path)
    path = pkg.path / asset
    path.parent.mkdir(parents=True, exist_ok=True)
    if operation != 'add':
        path.write_bytes(b'original')
    evidence = evaluation(pkg)
    if operation == 'delete':
        path.unlink()
    else:
        path.write_bytes(b'changed')
    assert 'does not match' in reason(pkg, runs=[evidence])


@pytest.mark.parametrize('metadata,value', [
    ('input_schema', {'type': 'object'}), ('output_schema', {'type': 'string'}),
    ('agent', 'tiger'), ('description', 'changed'),
])
def test_metadata_changes_invalidate_approval(tmp_path, metadata, value):
    pkg = package(tmp_path)
    evidence = evaluation(pkg)
    assert 'does not match' in reason(replace(pkg, **{metadata: value}), runs=[evidence])


def test_generated_bytecode_does_not_invalidate_evidence(tmp_path):
    pkg = package(tmp_path)
    evidence = evaluation(pkg)
    py_compile.compile(str(pkg.path / 'run.py'), doraise=True)
    assert reason(pkg, runs=[evidence]) is None


@pytest.mark.asyncio
async def test_candidate_same_size_same_timestamp_edit_executes_new_source(tmp_path):
    pkg = package(tmp_path)
    path = pkg.path / 'run.py'
    path.write_text("async def run(payload, ctx):\n    return {'answer': 1}\n")
    stat = path.stat()
    py_compile.compile(str(path), doraise=True)
    assert (await skala.run_skill(pkg, {}, SimpleNamespace()))['answer'] == 1
    path.write_text("async def run(payload, ctx):\n    return {'answer': 2}\n")
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert (await skala.run_skill(pkg, {}, SimpleNamespace()))['answer'] == 2


@pytest.mark.parametrize('corruption', ['missing', 'duplicate', 'failed', 'score'])
def test_earlier_model_runs_must_have_complete_matching_evidence(tmp_path, corruption):
    pkg = package(tmp_path, model=True)
    good = evaluation(pkg)
    bad = copy.deepcopy(good)
    if corruption == 'missing':
        bad['details'].pop()
    elif corruption == 'duplicate':
        bad['details'][0] = bad['details'][1]
    elif corruption == 'failed':
        bad['details'][0]['passed'] = False
    else:
        bad['score'] = .8
    assert skala.passing_runs(pkg, [good, bad, good]) == 1
    assert '1/3 runs' in reason(pkg, runs=[good, bad, good])
