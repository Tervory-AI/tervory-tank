"""Encrypted nightly database archives. No plaintext dump reaches disk or R2.

Requires existing pg_dump and age executables and a public age recipient. The
private restore key is never needed here. Scheduling this process is a separate
cloud deployment operation; --nightly runs at 02:00 UTC, --once runs once.
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
from urllib.parse import unquote, urlsplit

from r2_archive import PLATFORM_TENANT, Storage, StorageError, archive_file


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


def dump_configuration() -> tuple[dict[str, str], str]:
    recipient = os.environ.get('R2_BACKUP_RECIPIENT', '')
    if re.fullmatch(r'age1[023456789acdefghjklmnpqrstuvwxyz]{58}', recipient) is None:
        raise StorageError('R2_BACKUP_RECIPIENT must be a public age recipient')
    env = backup_environment()
    if not shutil.which('pg_dump') or not shutil.which('age'):
        raise StorageError('Backup requires pg_dump and age on this cloud worker')
    return env, recipient


async def encrypted_dump(target: Path) -> None:
    env, recipient = dump_configuration()
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


async def backup_once(owner: str = 'uploads') -> dict:
    assert_backup_owner(owner)
    public = backup_public(owner)
    store = Storage(owner)
    try:
        # Region / platform check before launching pg_dump.
        store._prefix(PLATFORM_TENANT, 'backups', public=public)
        with tempfile.TemporaryDirectory(prefix='tervory-encrypted-backup-') as directory:
            path = Path(directory) / 'database.dump.age'
            await encrypted_dump(path)
            return await archive_file(
                store, path, 'backups', tenant_id=PLATFORM_TENANT,
                public=public, label='database.dump.age')
    finally:
        await store.close()


async def main(owner: str, nightly: bool) -> None:
    assert_backup_owner(owner)
    public = backup_public(owner)
    # Fail at worker start, not silently after waiting for the first night.
    store = Storage(owner)
    try:
        store._prefix(PLATFORM_TENANT, 'backups', public=public)
        dump_configuration()
    finally:
        await store.close()
    while True:
        if nightly:
            now = datetime.now(timezone.utc)
            next_run = now.replace(hour=2, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            await asyncio.sleep((next_run - now).total_seconds())
        result = await backup_once(owner)
        print(json.dumps({'bucket': result['bucket'], 'key': result['key'], 'size_bytes': result['size_bytes']}), flush=True)
        if not nightly:
            return


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--owner', choices=['uploads', 'zenas'], default='uploads')
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--once', action='store_true')
    mode.add_argument('--nightly', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(main(args.owner, args.nightly))
    except Exception:
        raise SystemExit('Encrypted backup failed; no complete backup was confirmed. Check worker configuration.') from None
