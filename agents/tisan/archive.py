"""Archive measured builds through the room's existing private R2 client."""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
import hashlib
import json
import os
import tarfile
from pathlib import Path
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, StrictInt
from chassis.memory import MemoryClient
from chassis.storage import Storage, StorageError

try:
    from agents.tisan import publish
    from agents.tisan.storage import atomic_json, durable_root, tenant_folder
except ModuleNotFoundError:
    import publish
    from storage import atomic_json, durable_root, tenant_folder


class ArchiveArgs(BaseModel):
    model_config = ConfigDict(extra='forbid')
    slug: str = Field(min_length=1, max_length=60, pattern=r'^[a-z0-9]+(?:-[a-z0-9]+)*$')
    build: StrictInt = Field(gt=0, le=2147483647)


async def export(tenant_id: str, payload: dict, *, root: Path | None = None,
                 memory=None, job_id: str | None = None) -> dict:
    tenant = str(UUID(str(tenant_id)))
    body = ArchiveArgs.model_validate(payload)
    root = durable_root(root)
    # Reuse the publisher's archive, manifest, path and R5 receipt validation.
    manifest = publish.stored_build(root, tenant, body.slug, body.build)['manifest']
    folder = tenant_folder(root, 'builds', tenant, body.slug)
    raw = (folder/f'{body.build}.tar.gz').read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    metadata = json.dumps(manifest, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    names = [f'builds/{body.slug}/{body.build}-{digest}.tar.gz',
             f'builds/{body.slug}/{body.build}-{digest}.json']
    store = Storage('tisan')
    try:
        archive_key = await asyncio.wait_for(store.put(tenant, 'work', names[0], raw), timeout=180)
        manifest_key = await asyncio.wait_for(store.put(tenant, 'work', names[1], metadata), timeout=180)
        # An acknowledged PUT alone is not a completed archive receipt.
        if hashlib.sha256(await asyncio.wait_for(store.get(tenant, 'work', names[0]), timeout=180)).hexdigest() != digest:
            raise StorageError('R2 response unavailable')
        if await asyncio.wait_for(store.get(tenant, 'work', names[1]), timeout=180) != metadata:
            raise StorageError('R2 response unavailable')
        result = {'schema': 'tisan.archive/1', 'ok': True, 'tenant_id': tenant,
                  'slug': body.slug, 'build': body.build, 'bucket': store.bucket,
                  'archive_sha256': digest, 'manifest_sha256': hashlib.sha256(metadata).hexdigest(),
                  'objects': [archive_key, manifest_key], 'public': False,
                  'recorded_at': datetime.now(timezone.utc).isoformat()}
    except TimeoutError:
        raise StorageError('R2 is unreachable; no successful operation was confirmed') from None
    finally:
        await store.close()
    receipt = folder/f'{body.build}.archive.json'
    atomic_json(receipt, result)
    absent = [name for name in ('HERMES_URL', 'TANK_KEY') if not os.environ.get(name, '').strip()]
    if memory is None and absent:
        result.update(memory='not_configured', missing_settings=absent)
        atomic_json(receipt, result)
        return result
    try:
        client = memory if memory is not None else MemoryClient(agent='tisan')
        saved = await asyncio.wait_for(client.remember(tenant, json.dumps(result, sort_keys=True), 'build',
            'archive:' + digest, evidence=([str(job_id)] if job_id else []) + [digest],
            confidence=1.0, record_id=str(uuid5(UUID(tenant), 'tisan-archive:' + digest)), index=False), timeout=30)
        result['memory_id'] = str(UUID(saved['id']))
    except Exception:
        # R2 and the durable local receipt remain valid during a Hermes outage.
        result['memory'] = 'unreachable'
    atomic_json(receipt, result)
    return result


async def handle(ctx) -> dict:
    return await export(str(ctx.tenant_id), ctx.input, memory=ctx.memory, job_id=str(ctx.job_id))


def dry_run(tenant_id: str, payload: dict, *, root: Path) -> dict:
    """Validate actual stored bytes; never open R2 or write a success receipt."""
    tenant = str(UUID(str(tenant_id)))
    body = ArchiveArgs.model_validate(payload)
    root = root.resolve()
    stored = publish.stored_build(root, tenant, body.slug, body.build)
    raw = (root / 'builds' / tenant / body.slug / f'{body.build}.tar.gz').read_bytes()
    return {'dry_run': True, 'ready': True, 'uploaded': False, 'tenant_id': tenant,
            'slug': body.slug, 'build': body.build, 'files': len(stored['files']),
            'archive_sha256': hashlib.sha256(raw).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--slug', required=True)
    parser.add_argument('--build', required=True, type=int)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    required = ['DATA_DIR']
    if not args.dry_run:
        required += ['R2_ACCOUNT_ID', 'R2_ACCESS_KEY_ID_TISAN', 'R2_SECRET_ACCESS_KEY_TISAN']
    absent = [name for name in required if not os.environ.get(name, '').strip()]
    if absent:
        parser.exit(1, 'Missing settings: ' + ', '.join(absent) + '\n')
    try:
        payload = {'slug': args.slug, 'build': args.build}
        result = (dry_run(args.tenant, payload, root=Path(os.environ['DATA_DIR'])) if args.dry_run
                  else asyncio.run(export(args.tenant, payload)))
    except StorageError as exc:
        parser.exit(1, str(exc) + '\n')
    except (ValueError, OSError, tarfile.TarError):
        parser.exit(1, 'invalid stored build\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
