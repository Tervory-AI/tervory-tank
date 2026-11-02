"""Identity backups reuse encrypted streaming/archive code with fixed ZA scope."""
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from ops import restore_drill  # noqa: F401 (existing backup module path setup)
import backup


def test_identity_dump_uses_only_its_own_fixed_database_and_setting(monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'za')
    monkeypatch.setenv('POSTGRES_ZITADEL_PASSWORD', 'offline-password-marker')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://unused-external-setting')
    monkeypatch.setattr(backup.shutil, 'which', lambda _: '/offline/tool')
    monkeypatch.setattr(backup, 'recipient_value', lambda: 'offline-public-recipient')
    env, recipient = backup.identity_dump_configuration()
    assert recipient == 'offline-public-recipient'
    assert {k: env[k] for k in ['PGHOST', 'PGPORT', 'PGDATABASE', 'PGUSER', 'PGPASSWORD', 'PGSSLMODE']} == {
        'PGHOST': 'identity-postgres', 'PGPORT': '5432', 'PGDATABASE': 'zitadel', 'PGUSER': 'zitadel',
        'PGPASSWORD': 'offline-password-marker', 'PGSSLMODE': 'disable'}
    assert 'DATABASE_URL' not in env and 'R2_SECRET_ACCESS_KEY_ZENAS' not in env
    monkeypatch.setenv('TANK_REGION', 'us-east')
    with pytest.raises(backup.StorageError, match='ZA only'):
        backup.identity_dump_configuration()


@pytest.mark.asyncio
async def test_identity_backup_keeps_existing_encryption_and_own_archive_label(monkeypatch):
    monkeypatch.setenv('TANK_REGION', 'za')
    calls = []
    class Store:
        def __init__(self, owner):
            assert owner == 'zenas'
        def _prefix(self, tenant, category, *, public):
            assert public is True and category == 'backups'
            calls.append('scope')
        async def close(self):
            calls.append('close')
    async def encrypt(path, *, identity=False):
        assert calls == ['scope'] and identity is True
        path.write_bytes(b'offline-encrypted-marker')
        calls.append('encrypted')
    async def archive(store, path, category, **kwargs):
        assert path.read_bytes() == b'offline-encrypted-marker'
        assert kwargs['label'] == 'identity/database.dump.age'
        assert kwargs['public'] is True
        calls.append('archive')
        return {'key': 'offline-complete-identity-manifest'}
    monkeypatch.setattr(backup, 'Storage', Store)
    monkeypatch.setattr(backup, 'encrypted_dump', encrypt)
    monkeypatch.setattr(backup, 'archive_file', archive)
    assert (await backup.backup_once('zenas', identity=True))['key'] == 'offline-complete-identity-manifest'
    assert calls == ['scope', 'encrypted', 'archive', 'close']
    monkeypatch.setenv('TANK_REGION', 'us-east')
    with pytest.raises(backup.StorageError):
        await backup.backup_once('zenas', identity=True)
    with pytest.raises(backup.StorageError):
        await backup.backup_once('uploads', identity=True)
