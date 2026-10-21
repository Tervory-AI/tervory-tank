"""Archive local snapshots in the owning room before an optional HF export.

Run on that room's cloud box. Large files are split into bounded objects; a
manifest is written last, so interrupted uploads never look like complete
snapshots. No R2 credentials are sent to a Hugging Face job.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import uuid

_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT / 'agents' / '_chassis'))
from chassis.storage import MAX_OBJECT_BYTES, PLATFORM_TENANT, Storage, StorageError, safe_name  # noqa: E402


async def archive_file(store: Storage, path: Path, category: str, *, tenant_id: str,
                       public: bool = False, label: str = 'snapshot') -> dict:
    safe_name(label)
    # Validate the entire destination before opening a source or writing a part.
    store._prefix(tenant_id, category, public=public)
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d/%H%M%S')
    name = f'{stamp}-{uuid.uuid4().hex}/{label}'
    parts = []
    digest = hashlib.sha256()
    with path.open('rb') as source:
        while chunk := await asyncio.to_thread(source.read, MAX_OBJECT_BYTES):
            digest.update(chunk)
            part_name = f'{name}/part-{len(parts):06d}'
            await store.put(tenant_id, category, part_name, chunk, public=public)
            parts.append({'name': part_name, 'size_bytes': len(chunk), 'sha256': hashlib.sha256(chunk).hexdigest()})
    manifest = {'version': 1, 'parts': parts, 'sha256': digest.hexdigest(),
                'size_bytes': sum(p['size_bytes'] for p in parts)}
    manifest_name = f'{name}/manifest.json'
    key = await store.put(tenant_id, category, manifest_name,
                          json.dumps(manifest, sort_keys=True).encode(), public=public)
    # A backup/snapshot succeeds only after its dated completion marker is listed.
    listing = await store.objects(tenant_id, category, public=public)
    if not any(item['key'] == key for item in listing):
        raise StorageError('Archive completion marker was not found')
    return {'bucket': store.bucket, 'key': key, **manifest}


async def run(args) -> dict:
    store = Storage(args.room)
    try:
        return await archive_file(store, Path(args.file), args.category,
                                  tenant_id=args.tenant_id, public=args.public,
                                  label=Path(args.file).name)
    finally:
        await store.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--room', required=True)
    parser.add_argument('--category', choices=['datasets', 'work', 'screenshots', 'gold', 'bench', 'training'], required=True)
    parser.add_argument('--tenant-id', default=PLATFORM_TENANT)
    parser.add_argument('--public', action='store_true')
    parser.add_argument('file')
    try:
        result = asyncio.run(run(parser.parse_args()))
        print(json.dumps({'bucket': result['bucket'], 'key': result['key'], 'size_bytes': result['size_bytes']}))
    except Exception:
        raise SystemExit('Storage archive failed; check configuration and source file. No complete snapshot was confirmed.') from None


async def restore_archive(store: Storage, manifest_name: str, destination: Path, category: str,
                          *, tenant_id: str, public: bool = False) -> None:
    """Reassemble and verify an archive atomically; backups stay encrypted."""
    import tempfile
    manifest_name = safe_name(manifest_name)
    if not manifest_name.endswith('/manifest.json'):
        raise StorageError('Invalid archive manifest name')
    try:
        manifest = json.loads(await store.get(tenant_id, category, manifest_name, public=public))
        parts = manifest['parts']
        if manifest['version'] != 1 or not isinstance(parts, list):
            raise ValueError('invalid manifest')
        prefix = manifest_name.removesuffix('manifest.json')
        for index, part in enumerate(parts):
            if part['name'] != f'{prefix}part-{index:06d}' or type(part['size_bytes']) is not int:
                raise ValueError('invalid part')
    except (ValueError, KeyError, TypeError):
        raise StorageError('Invalid archive manifest') from None
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as output:
            temporary = Path(output.name)
            digest = hashlib.sha256()
            size = 0
            for part in parts:
                data = await store.get(tenant_id, category, part['name'], public=public)
                if len(data) != part['size_bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                    raise StorageError('Archive part integrity check failed')
                digest.update(data)
                size += len(data)
                await asyncio.to_thread(output.write, data)
        if size != manifest['size_bytes'] or digest.hexdigest() != manifest['sha256']:
            raise StorageError('Archive integrity check failed')
        temporary.replace(destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
