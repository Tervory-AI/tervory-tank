"""Offline, bounded case-study intake. Never uploads, submits, approves or trains."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from uuid import UUID, uuid5

from .command import CommandError, read_file, write_file
from .contracts import Anchor, Review, NAME


def local_file(root, name, maximum):
    relative = Path(name)
    if relative.is_absolute() or '..' in relative.parts:
        raise CommandError('Use repository-relative input paths.')
    path = root / relative
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise CommandError('Input paths must not contain symlinks.')
    data = read_file(path, maximum)
    expected = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD:' + str(relative)], stderr=subprocess.DEVNULL).strip()
    actual = subprocess.check_output(['git', '-C', str(root), 'hash-object', '--stdin'], input=data).strip()
    if actual != expected:
        raise CommandError('Source bytes differ from the pinned revision.')
    return data


def plan(root, recipe, preparations=None):
    """Hash source bytes once; keep every product association and rights decision.

    Optional preparations are operator-supplied measured scan records, never
    inferred from photographs. The exported requests use Forge's CPU contract.
    There is deliberately no network client or execution/approval option.
    """
    root = Path(root).resolve()
    revision = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    source = recipe['source']
    if revision != source['revision']:
        raise CommandError('The source revision does not match the reviewed recipe.')
    selected = recipe['products']
    if not 1 <= len(selected) <= 5 or len(set(selected)) != len(selected):
        raise CommandError('Select one to five different catalogue slugs.')
    catalogue_bytes = local_file(root, source['catalogue'], 5_000_000)
    rows = json.loads(catalogue_bytes)['collection']
    preparations = preparations or {}
    if set(preparations) - set(selected):
        raise CommandError('Preparation must belong to a selected product.')
    assets, products, assigned = {}, [], set()
    for slug in selected:
        matches = [(i, row) for i, row in enumerate(rows) if row['slug'] == slug]
        if len(matches) != 1:
            raise CommandError('Each selected slug must have exactly one catalogue row.')
        index, row = matches[0]
        image = row.get('image', '')
        if not image.startswith('/images/') or '?' in image or '#' in image:
            raise CommandError('Choose a local published product photograph.')
        path = 'public' + image
        data = local_file(root, path, 25_000_000)
        digest = hashlib.sha256(data).hexdigest()
        asset = assets.setdefault(digest, {'sha256': digest, 'bytes': len(data), 'paths': []})
        if path not in asset['paths']:
            asset['paths'].append(path)
        record = {
            'source_slug': slug, 'name': row['name'], 'sku': None,
            'catalogue_pointer': f'/collection/{index}', 'photo_sha256': digest,
            'photo_path': path, 'public_photo_url': recipe['public_origin'] + image,
            'appearance': 'reference_only', 'geometry': 'missing',
            'approval': 'not_reviewed', 'training': {'status': 'not_authorized', 'evidence': []},
            'blockers': ['authoritative_sku_mapping', 'measured_scan_and_units',
                         'measured_dimensions_and_anchors', 'human_review'],
        }
        preparation = preparations.get(slug)
        if preparation:
            # Reuse strict existing contracts; a valid draft request is not approval.
            from agents.rig.forge.service import Job
            sku = preparation['sku']
            if not re.fullmatch(NAME, sku):
                raise CommandError('Use the authoritative catalogue SKU.')
            tenant = UUID(preparation['tenant_id'])
            if (tenant, sku) in assigned:
                raise CommandError('A SKU may occur only once per tenant in this batch.')
            assigned.add((tenant, sku))
            if not preparation['mapping_evidence'] or not preparation['measurement_evidence']:
                raise CommandError('Supply SKU mapping and measurement evidence.')
            anchors = {name: Anchor.model_validate(value).model_dump(mode='json')
                       for name, value in preparation['anchors'].items()}
            if not anchors or any(not re.fullmatch(NAME, name) for name in anchors):
                raise CommandError('Supply measured attachment points.')
            scan = local_file(root, preparation['scan_path'], 256_000_000)
            scan_hash = hashlib.sha256(scan).hexdigest()
            identity = json.dumps({'sku': sku, 'scan': scan_hash, 'anchors': anchors,
                'dimensions': preparation['dimensions_mm'], 'unit_mm': preparation['unit_mm']}, sort_keys=True)
            job_id = uuid5(tenant, identity)
            filename = Path(preparation['scan_path']).name
            job = Job(tenant_id=tenant, job_id=job_id, home_region=preparation['home_region'], method='scan',
                      inputs=[filename], unit_mm=preparation['unit_mm'],
                      dimensions_mm=preparation['dimensions_mm'], cost_cap_usd='0')
            record.update(sku=sku, geometry='measured_input_pending_validation',
                scan_sha256=scan_hash, scan_path=preparation['scan_path'], anchors=anchors,
                mapping_evidence=preparation['mapping_evidence'], measurement_evidence=preparation['measurement_evidence'],
                request=job.model_dump(mode='json'), blockers=['cpu_mesh_validation', 'human_review'])
            outcome = preparation.get('review_outcome')
            if outcome:
                # Preserve rejection as well as acceptance; never turns into a serving approval.
                if outcome['outcome'] not in {'accepted', 'rejected'} or not outcome['evidence']:
                    raise CommandError('Review outcomes require an evidence reference.')
                checks = outcome['checks']
                if (set(checks) != set(Review.model_fields) or
                        any(type(value) is not bool for value in checks.values())):
                    raise CommandError('Review checks must record each human decision.')
                if outcome['outcome'] == 'accepted':
                    Review.model_validate(checks)
                elif all(checks.values()):
                    raise CommandError('A rejected review must record a failed check.')
                if len(outcome['artifact_sha256']) != 64 or any(c not in '0123456789abcdef' for c in outcome['artifact_sha256']):
                    raise CommandError('Review outcomes must identify exact artifact bytes.')
                record['review_outcome'] = outcome
        products.append(record)
    return {'contract': 'rig-case-study-intake/1', 'source': {**source,
            'catalogue_sha256': hashlib.sha256(catalogue_bytes).hexdigest()},
            'assets': sorted(assets.values(), key=lambda item: item['sha256']), 'products': products,
            'execution': 'offline_intake_only', 'rights_evidence': recipe['rights_evidence']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--preparations', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads(read_file(args.recipe, 100_000))
    preparations = json.loads(read_file(args.preparations, 1_000_000)) if args.preparations else None
    result = plan(args.source_root, recipe, preparations)
    args.output.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Content-addressed checkpoints are immutable. Resuming identical input is a no-op;
    # changed scans, mappings or outcomes create a new checkpoint, preserving history.
    data = (json.dumps(result, indent=2, sort_keys=True) + '\n').encode()
    name = hashlib.sha256(data).hexdigest() + '.json'
    write_file(args.output, name, data)
    print(json.dumps({'checkpoint': name, 'products': len(result['products']), 'assets': len(result['assets'])}))


if __name__ == '__main__':
    main()
