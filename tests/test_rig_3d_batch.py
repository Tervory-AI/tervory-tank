"""Offline intake preserves provenance and never invents fit, approval or rights."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))

from rigbox.three_d.batch import plan, CommandError
from rigbox.three_d.command import write_file


@pytest.fixture
def source(tmp_path):
    subprocess.run(['git', 'init', '-q', str(tmp_path)], check=True)
    photo = tmp_path / 'public/images/shared.jpg'
    photo.parent.mkdir(parents=True); photo.write_bytes(b'\xff\xd8\xffneutral-photo')
    (tmp_path / 'catalogue.json').write_text(json.dumps({'collection': [
        {'slug': slug, 'name': name, 'image': '/images/shared.jpg', 'price': 'not exported'}
        for slug, name in [('lamp', 'Desk lamp'), ('stand', 'Lamp stand')]]}))
    (tmp_path / 'scan.obj').write_text('# measured input supplied by operator\n')
    subprocess.run(['git', '-C', str(tmp_path), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(tmp_path), '-c', 'user.name=Offline', '-c',
                    'user.email=offline@example.invalid', 'commit', '-qm', 'input'], check=True)
    revision = subprocess.check_output(['git', '-C', str(tmp_path), 'rev-parse', 'HEAD'], text=True).strip()
    recipe = {'source': {'revision': revision, 'catalogue': 'catalogue.json'},
              'products': ['lamp', 'stand'], 'public_origin': 'https://shop.example',
              'rights_evidence': ['Appearance reference only']}
    return tmp_path, recipe


def test_deduplicates_bytes_without_losing_product_associations_or_inventing_skus(source):
    root, recipe = source
    result = plan(root, recipe)
    assert len(result['assets']) == 1 and len(result['products']) == 2
    for row in result['products']:
        assert row['photo_sha256'] == result['assets'][0]['sha256']
        assert row['sku'] is None and row['geometry'] == 'missing'
        assert row['approval'] == 'not_reviewed' and row['training']['status'] == 'not_authorized'
        assert 'request' not in row and 'price' not in row
    assert result['products'][0]['catalogue_pointer'] != result['products'][1]['catalogue_pointer']


def test_immutable_resume_retains_old_checkpoint(source, tmp_path):
    root, recipe = source
    output = tmp_path / 'checkpoints'; output.mkdir()
    data = json.dumps(plan(root, recipe), sort_keys=True).encode()
    name = hashlib.sha256(data).hexdigest() + '.json'
    write_file(output, name, data); write_file(output, name, data)
    assert len(list(output.iterdir())) == 1
    with pytest.raises(CommandError):
        write_file(output, name, b'changed approval')
    assert (output / name).read_bytes() == data


@pytest.mark.parametrize('change', ['revision', 'duplicate', 'missing', 'too_many', 'traversal', 'symlink', 'dirty'])
def test_rejects_ambiguous_or_changed_source(source, change):
    root, recipe = source
    if change == 'revision': recipe['source']['revision'] = '0' * 40
    elif change == 'duplicate': recipe['products'] = ['lamp', 'lamp']
    elif change == 'missing': recipe['products'] = ['missing']
    elif change == 'too_many': recipe['products'] = [str(n) for n in range(6)]
    elif change == 'traversal': recipe['source']['catalogue'] = '../catalogue.json'
    elif change == 'symlink':
        target = root / 'public/images/shared.jpg'; target.unlink(); target.symlink_to(root / 'scan.obj')
    else: (root / 'public/images/shared.jpg').write_bytes(b'changed')
    with pytest.raises(CommandError): plan(root, recipe)


def preparation():
    return {'tenant_id': '11111111-1111-4111-8111-111111111111', 'home_region': 'us-east',
        'sku': 'LAMP-REAL', 'mapping_evidence': 'approved catalogue mapping receipt',
        'measurement_evidence': 'operator measurement record', 'scan_path': 'scan.obj',
        'unit_mm': 1, 'dimensions_mm': [20, 30, 40],
        'anchors': {'mount': {'position_mm': [0, 0, 0], 'quaternion': [0, 0, 0, 1]}}}


def test_measured_scan_uses_existing_zero_cost_contract_and_stable_identity(source):
    root, recipe = source
    prep = preparation()
    first = plan(root, recipe, {'lamp': prep})['products'][0]
    repeated = plan(root, recipe, {'lamp': prep})['products'][0]
    assert first == repeated and first['request']['method'] == 'scan'
    assert first['request']['cost_cap_usd'] == '0'
    UUID(first['request']['job_id'])
    assert first['approval'] == 'not_reviewed' and first['training']['status'] == 'not_authorized'
    changed = {**prep, 'dimensions_mm': [21, 30, 40]}
    assert plan(root, recipe, {'lamp': changed})['products'][0]['request']['job_id'] != first['request']['job_id']
    with pytest.raises(CommandError): plan(root, recipe, {'lamp': prep, 'stand': prep})
    with pytest.raises(CommandError): plan(root, recipe, {'lamp': {**prep, 'anchors': {}}})
    with pytest.raises(CommandError): plan(root, recipe, {'lamp': {**prep, 'measurement_evidence': ''}})


def test_preserves_rejected_review_without_turning_it_into_approval_or_training(source):
    root, recipe = source
    prep = preparation()
    outcome = {'outcome': 'rejected', 'artifact_sha256': 'a' * 64, 'evidence': 'human review record',
               'checks': {'scale': False, 'appearance': True, 'attachment_points': False}}
    prep['review_outcome'] = outcome
    row = plan(root, recipe, {'lamp': prep})['products'][0]
    assert row['review_outcome'] == outcome
    assert row['approval'] == 'not_reviewed' and row['training']['status'] == 'not_authorized'
