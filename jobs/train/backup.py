"""Encrypted nightly database and Qdrant archives. No plaintext reaches disk or R2.

Requires existing pg_dump and age executables, a public age recipient, and (for
Qdrant) the internal Qdrant URL plus API key. The private restore key is never
needed here. Scheduling this process is a separate cloud deployment operation;
--nightly runs at 02:00 UTC, --once runs once.
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import quote, unquote, urlsplit

import httpx

from r2_archive import PLATFORM_TENANT, Storage, StorageError, archive_file

_COLLECTION = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]*$')
_AGE_RECIPIENT = re.compile(r'^age1[023456789acdefghjklmnpqrstuvwxyz]{58}$')


def tool_environment() -> dict[str, str]:
    """Subprocesses receive no model, Tank, HF or R2 credentials."""
    return {key: os.environ[key] for key in ("PATH", "LANG", "LC_ALL", "TZ") if key in os.environ}


def backup_environment() -> dict[str, str]:
    try:
        parsed = urlsplit(os.environ.get('DATABASE_URL', ''))
        if parsed.scheme not in {'postgres', 'postgresql'} or not parsed.hostname or not parsed.username or not parsed.path.strip('/'):
            raise ValueError('invalid database configuration')
        if parsed.query or parsed.fragment:
            raise ValueError('unsupported database options')
        tls = {key: os.environ[key] for key in ('PGSSLMODE', 'PGSSLROOTCERT', 'PGSSLCERT', 'PGSSLKEY') if key in os.environ}
        return {**tool_environment(), **tls, 'PGHOST': parsed.hostname, 'PGPORT': str(parsed.port or 5432),
                'PGUSER': unquote(parsed.username), 'PGPASSWORD': unquote(parsed.password or ''),
                'PGDATABASE': unquote(parsed.path[1:])}
    except ValueError:
        raise StorageError('DATABASE_URL is missing or invalid for backup') from None


def recipient_value() -> str:
    recipient = os.environ.get('R2_BACKUP_RECIPIENT', '')
    if _AGE_RECIPIENT.fullmatch(recipient) is None:
        raise StorageError('R2_BACKUP_RECIPIENT must be a public age recipient')
    return recipient


def dump_configuration() -> tuple[dict[str, str], str]:
    recipient = recipient_value()
    env = backup_environment()
    if not shutil.which('pg_dump') or not shutil.which('age'):
        raise StorageError('Backup requires pg_dump and age on this cloud worker')
    return env, recipient


def qdrant_configuration() -> tuple[str, str, str]:
    """Internal Qdrant only. Public recipients stay; the private age identity never enters."""
    recipient = recipient_value()
    if not shutil.which('age'):
        raise StorageError('Backup requires age on this cloud worker')
    parsed = urlsplit(os.environ.get('QDRANT_URL', ''))
    if (parsed.scheme != 'http' or parsed.hostname != 'qdrant'
            or (parsed.port or 6333) != 6333 or parsed.path not in ('', '/')
            or parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise StorageError('QDRANT_URL is missing or invalid for backup')
    api_key = os.environ.get('QDRANT_API_KEY', '')
    if not api_key or any(ord(c) < 33 or ord(c) > 126 for c in api_key):
        raise StorageError('QDRANT_API_KEY is missing or invalid')
    return 'http://qdrant:6333', api_key, recipient


def collection_name(name: str) -> str:
    if not isinstance(name, str) or _COLLECTION.fullmatch(name) is None or len(name) > 255:
        raise StorageError('Invalid Qdrant collection name')
    return name


def identity_dump_configuration() -> tuple[dict[str, str], str]:
    if os.environ.get('TANK_REGION') != 'za':
        raise StorageError('Identity backups run on ZA only')
    password = os.environ.get('POSTGRES_ZITADEL_PASSWORD', '')
    if not password or not shutil.which('pg_dump') or not shutil.which('age'):
        raise StorageError('Identity backup settings or tools are missing')
    env = {**tool_environment(), 'PGHOST': 'identity-postgres', 'PGPORT': '5432',
           'PGDATABASE': 'zitadel', 'PGUSER': 'zitadel', 'PGPASSWORD': password,
           'PGSSLMODE': 'disable'}
    return env, recipient_value()


async def encrypted_dump(target: Path, *, identity: bool = False) -> None:
    env, recipient = identity_dump_configuration() if identity else dump_configuration()
    read_fd, write_fd = os.pipe()
    children = []
    try:
        with target.open('wb') as output:
            encrypt = await asyncio.create_subprocess_exec(
                'age', '--encrypt', '--recipient', recipient,
                stdin=read_fd, stdout=output, stderr=asyncio.subprocess.DEVNULL,
                env=tool_environment())
            children.append(encrypt)
            os.close(read_fd)
            read_fd = -1
            dump = await asyncio.create_subprocess_exec(
                'pg_dump', '--format=custom', '--no-password',
                stdout=write_fd, stderr=asyncio.subprocess.DEVNULL, env=env)
            children.append(dump)
            os.close(write_fd)
            write_fd = -1
            codes = await asyncio.wait_for(asyncio.gather(*(child.wait() for child in children)), timeout=3600)
            if any(codes):
                raise StorageError('Database dump or encryption failed; no backup was uploaded')
        if not target.stat().st_size:
            raise StorageError('Encrypted backup is empty')
    finally:
        for fd in (read_fd, write_fd):
            if fd >= 0:
                os.close(fd)
        for child in children:
            if child.returncode is None:
                child.kill()
                await child.wait()


def backup_public(owner: str) -> bool:
    """Boston uploads backups stay private. ZA Zenas platform backups use the
    public platform prefix so encrypted dumps may leave the box into the
    founder ZA bucket only (tervory-zenas-za)."""
    return owner == 'zenas'


def assert_backup_owner(owner: str) -> None:
    if owner == 'uploads':
        return
    if owner == 'zenas':
        if os.environ.get('TANK_REGION', '') != 'za':
            raise StorageError('Zenas database backups require TANK_REGION=za')
        return
    raise StorageError('Database backups use UPLOADS or ZA Zenas only')


async def encrypted_qdrant_snapshot(collection: str, target: Path) -> None:
    """Create one collection snapshot, stream it through age, delete the remote snapshot."""
    base, api_key, recipient = qdrant_configuration()
    name = collection_name(collection)
    headers = {'api-key': api_key}
    snapshot_name = None
    read_fd = write_fd = -1
    encrypt = None
    async with httpx.AsyncClient(base_url=base, headers=headers, timeout=3600,
                                 trust_env=False, follow_redirects=False) as client:
        try:
            created = await client.post(f'/collections/{quote(name, safe="")}/snapshots')
            if created.status_code >= 400:
                raise StorageError('Qdrant snapshot create failed')
            try:
                snapshot_name = created.json()['result']['name']
            except (KeyError, TypeError, ValueError):
                raise StorageError('Qdrant snapshot create failed') from None
            if not isinstance(snapshot_name, str) or not snapshot_name or len(snapshot_name) > 512:
                raise StorageError('Qdrant snapshot create failed')
            snap_path = f'/collections/{quote(name, safe="")}/snapshots/{quote(snapshot_name, safe="")}'
            read_fd, write_fd = os.pipe()
            with target.open('wb') as output:
                encrypt = await asyncio.create_subprocess_exec(
                    'age', '--encrypt', '--recipient', recipient,
                    stdin=read_fd, stdout=output, stderr=asyncio.subprocess.DEVNULL,
                    env=tool_environment())
                os.close(read_fd)
                read_fd = -1
                try:
                    async with client.stream('GET', snap_path) as response:
                        if response.status_code >= 400:
                            raise StorageError('Qdrant snapshot download failed')
                        async for chunk in response.aiter_bytes(1024 * 1024):
                            await asyncio.to_thread(os.write, write_fd, chunk)
                finally:
                    if write_fd >= 0:
                        os.close(write_fd)
                        write_fd = -1
                code = await asyncio.wait_for(encrypt.wait(), timeout=3600)
                encrypt = None
                if code:
                    raise StorageError('Qdrant snapshot encryption failed')
            if not target.stat().st_size:
                raise StorageError('Encrypted Qdrant backup is empty')
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            if write_fd >= 0:
                os.close(write_fd)
            if encrypt is not None and encrypt.returncode is None:
                encrypt.kill()
                await encrypt.wait()
            if snapshot_name is not None:
                try:
                    await client.delete(
                        f'/collections/{quote(name, safe="")}/snapshots/{quote(snapshot_name, safe="")}')
                except httpx.HTTPError:
                    pass


async def backup_once(owner: str = 'uploads', *, identity: bool = False) -> dict:
    assert_backup_owner(owner)
    if identity and (owner != 'zenas' or os.environ.get('TANK_REGION') != 'za'):
        raise StorageError('Identity backup owner must be ZA Zenas')
    public = backup_public(owner)
    store = Storage(owner)
    try:
        # Region / platform check before launching pg_dump.
        store._prefix(PLATFORM_TENANT, 'backups', public=public)
        with tempfile.TemporaryDirectory(prefix='tervory-encrypted-backup-') as directory:
            path = Path(directory) / 'database.dump.age'
            await encrypted_dump(path, identity=True) if identity else await encrypted_dump(path)
            return await archive_file(
                store, path, 'backups', tenant_id=PLATFORM_TENANT,
                public=public, label='identity/database.dump.age' if identity else 'database.dump.age')
    finally:
        await store.close()


async def list_qdrant_collections() -> list[str]:
    base, api_key, _recipient = qdrant_configuration()
    async with httpx.AsyncClient(base_url=base, headers={'api-key': api_key}, timeout=60,
                                 trust_env=False, follow_redirects=False) as client:
        response = await client.get('/collections')
        if response.status_code >= 400:
            raise StorageError('Qdrant collection list failed')
        try:
            names = [collection_name(item['name']) for item in response.json()['result']['collections']]
        except (KeyError, TypeError, ValueError, StorageError):
            raise StorageError('Qdrant collection list failed') from None
        return sorted(names)


async def qdrant_backup_once(owner: str = 'uploads') -> list[dict]:
    # Boston UPLOADS stays private; ZA Zenas (TANK_REGION=za) uses the platform
    # prefix in tervory-zenas-za, the same as its database dump.
    assert_backup_owner(owner)
    public = backup_public(owner)
    store = Storage(owner)
    try:
        store._prefix(PLATFORM_TENANT, 'backups', public=public)
        collections = await list_qdrant_collections()
        results = []
        with tempfile.TemporaryDirectory(prefix='tervory-encrypted-qdrant-') as directory:
            root = Path(directory)
            for name in collections:
                path = root / f'{name}.snapshot.age'
                await encrypted_qdrant_snapshot(name, path)
                archived = await archive_file(
                    store, path, 'backups', tenant_id=PLATFORM_TENANT,
                    public=public, label=f'qdrant/{name}.snapshot.age')
                results.append({
                    'collection': name,
                    'bucket': archived['bucket'],
                    'key': archived['key'],
                    'size_bytes': archived['size_bytes'],
                })
                path.unlink(missing_ok=True)
        return results
    finally:
        await store.close()


def _print_result(payload: dict) -> None:
    print(json.dumps(payload), flush=True)


async def main(owner: str, nightly: bool, target: str = 'all', *, identity: bool = False) -> None:
    assert_backup_owner(owner)
    public = backup_public(owner)
    if identity and (target != 'database' or owner != 'zenas' or os.environ.get('TANK_REGION') != 'za'):
        raise StorageError('Identity backup requires ZA Zenas database target')
    if target not in {'database', 'qdrant', 'all'}:
        raise StorageError('Backup target is invalid')
    # Fail at worker start, not silently after waiting for the first night.
    store = Storage(owner)
    try:
        store._prefix(PLATFORM_TENANT, 'backups', public=public)
        if target in {'database', 'all'}:
            identity_dump_configuration() if identity else dump_configuration()
        if target in {'qdrant', 'all'}:
            qdrant_configuration()
    finally:
        await store.close()
    while True:
        if nightly:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())
        if target in {'database', 'all'}:
            result = await backup_once(owner, identity=True) if identity else await backup_once(owner)
            _print_result({'kind': 'database', 'bucket': result['bucket'],
                           'key': result['key'], 'size_bytes': result['size_bytes']})
        if target in {'qdrant', 'all'}:
            for item in await qdrant_backup_once(owner):
                _print_result({'kind': 'qdrant', **item})
        if not nightly:
            return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', choices=['uploads', 'zenas'], default='uploads')
    parser.add_argument('--target', choices=['database', 'qdrant', 'all'], default='all')
    parser.add_argument('--identity', action='store_true', help='ZA identity database only')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--nightly', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(main(args.owner, args.nightly, args.target, identity=args.identity))
    except Exception:
        raise SystemExit('Encrypted backup failed; no complete backup was confirmed. Check worker configuration.') from None
