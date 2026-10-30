"""Offline regional deployment and encrypted-backup contracts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "jobs/train"))
spec = importlib.util.spec_from_file_location("zenas_docassemble_backup", ROOT / "agents/zenas/docassemble/backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)
NOW = datetime(2026, 10, 28, 4, tzinfo=timezone.utc)


@pytest.mark.parametrize("suffix,region,jurisdiction,volume", [
    ("", "us-east", "us", "docassemble_us_backup"),
    (".za", "za", "za", "docassemble_za_backup"),
])
def test_official_image_private_network_region_storage_and_backup(suffix, region, jurisdiction, volume):
    # 28 Oct: Docassemble is its own Coolify resource, and the Zenas package is baked into the
    # image (no nested read-only mounts, which failed every deploy).
    room = yaml.safe_load((ROOT / f"agents/zenas/docker-compose{suffix}.yml").read_text())
    compose = yaml.safe_load((ROOT / f"agents/zenas/docker-compose.docassemble{suffix}.yml").read_text())
    services = compose["services"]
    service, worker = services["docassemble"], services["docassemble-backup"]
    assert set(room["services"]) == {"agent-zenas", "pool-loader"}
    assert "depends_on" not in room["services"]["agent-zenas"]
    assert room["services"]["agent-zenas"]["environment"]["DOCASSEMBLE_URL"] == "http://docassemble"
    assert room["services"]["agent-zenas"]["environment"]["DOCASSEMBLE_REGION"] == region
    for file in (room, compose):
        assert file["networks"]["assembly"] == {"external": True, "name": "tervory-zenas-assembly"}
    assert "assembly" in room["services"]["agent-zenas"]["networks"]
    assert service["networks"] == {"assembly": {"aliases": ["docassemble"]}}
    assert service["build"] == {"context": ".", "dockerfile": "docassemble/Dockerfile", "args": {"REGION_DIR": jurisdiction}}
    dockerfile = (ROOT / "agents/zenas/docassemble/Dockerfile").read_text()
    assert "FROM jhpyle/docassemble:1.10.14@sha256:5dc6feb56f69a912885ad5652d1754330f37c1a05331c5831e34e9d0c509492d" in dockerfile
    assert "COPY docassemble/${REGION_DIR} ${ZENAS_PKG}/data/questions/region" in dockerfile
    assert "COPY core/drafting.py ${ZENAS_PKG}/legacy.py" in dockerfile
    assert "local3.14/lib/python3.14" in dockerfile
    assert "ports" not in service and "labels" not in service
    # No bind mount of repository files into the image's package directory.
    assert service["volumes"] == [f"{volume}:/usr/share/docassemble/backup"]
    assert service["healthcheck"]["test"][-1] == "http://127.0.0.1/health_check?ready=1"
    assert service["environment"]["TANK_REGION"] == worker["environment"]["TANK_REGION"] == region
    assert service["environment"]["DAUPDATEONSTART"] == "false"
    assert service["environment"]["DAALLOWUPDATES"] == "false"
    assert service["environment"]["DAENABLEPLAYGROUND"] == "false"
    assert service["stop_grace_period"] == "10m"
    assert f"{volume}:/backup:ro" in worker["volumes"]
    assert worker["read_only"] is True and worker["networks"] == ["backup"]
    assert not any("docker.sock" in mount for mount in worker["volumes"])
    assert "TANK_KEY" not in service["environment"] and "LAWS_AFRICA_API_TOKEN" not in service["environment"]
    assert "DATABASE_URL" not in worker["environment"]
    if region == "za":
        assert worker["environment"]["R2_BUCKET"] == "${R2_BUCKET_ZENAS_ZA:-}"
    else:
        assert worker["environment"]["R2_BUCKET"] == "tervory-zenas"


def make_snapshot(root, now=NOW):
    previous = now - timedelta(days=1)
    path = root / previous.strftime("%m-%d")
    for name in ("config/config.yml", "postgres/docassemble"):
        item = path / name
        item.parent.mkdir(parents=True, exist_ok=True)
        item.write_bytes(b"offline snapshot test input")
    (path / "files").mkdir()
    os.utime(path, (previous.timestamp(), previous.timestamp()))
    return path


def test_only_previous_day_complete_snapshot_is_eligible(tmp_path):
    source = make_snapshot(tmp_path)
    assert backup.snapshot(tmp_path, NOW) == source
    (source / "postgres/docassemble").unlink()
    with pytest.raises(backup.StorageError):
        backup.snapshot(tmp_path, NOW)


def test_today_and_stale_previous_year_snapshots_are_rejected(tmp_path):
    today = tmp_path / NOW.strftime("%m-%d")
    today.mkdir()
    with pytest.raises(backup.StorageError):
        backup.snapshot(tmp_path, NOW)
    source = make_snapshot(tmp_path)
    old = (NOW - timedelta(days=365)).timestamp()
    os.utime(source, (old, old))
    with pytest.raises(backup.StorageError):
        backup.snapshot(tmp_path, NOW)


@pytest.mark.asyncio
@pytest.mark.parametrize("region,public", [("us-east", False), ("za", True)])
async def test_backup_encrypts_before_existing_archive_in_the_owning_region(tmp_path, monkeypatch, region, public):
    source = make_snapshot(tmp_path)
    monkeypatch.setattr(backup, "configuration", lambda: (region, "R2_BACKUP_RECIPIENT"))
    calls = []
    class Store:
        bucket = "tervory-zenas-za" if region == "za" else "tervory-zenas"
        def __init__(self, owner):
            assert owner == "zenas"
        def _prefix(self, tenant, category, **kwargs):
            assert category == "backups" and kwargs["public"] is public
            calls.append("region checked")
        async def close(self):
            calls.append("closed")
    async def encrypt(found, target, recipient):
        assert found == source and recipient == "R2_BACKUP_RECIPIENT"
        assert calls == ["region checked"]
        calls.append("encrypted")
        target.write_bytes(b"offline encrypted-stream stub")
    async def archive(store, target, category, **kwargs):
        assert calls[-1] == "encrypted"
        assert target.name == kwargs["label"] == "docassemble.tar.age"
        assert kwargs["public"] is public and category == "backups"
        calls.append("archived")
        return {"bucket": store.bucket, "key": "offline-completion-marker", "size_bytes": target.stat().st_size}
    monkeypatch.setattr(backup, "Storage", Store)
    monkeypatch.setattr(backup, "encrypted_snapshot", encrypt)
    monkeypatch.setattr(backup, "archive_file", archive)
    result = await backup.backup_once(tmp_path, NOW)
    assert result["bucket"] == Store.bucket
    assert calls == ["region checked", "encrypted", "archived", "closed"]


@pytest.mark.asyncio
async def test_encryption_failure_uploads_nothing(tmp_path, monkeypatch):
    make_snapshot(tmp_path)
    monkeypatch.setattr(backup, "configuration", lambda: ("za", "R2_BACKUP_RECIPIENT"))
    store = SimpleNamespace(_prefix=lambda *a, **kw: None, close=AsyncMock())
    monkeypatch.setattr(backup, "Storage", lambda owner: store)
    monkeypatch.setattr(backup, "encrypted_snapshot", AsyncMock(side_effect=backup.StorageError("offline failure")))
    archive = AsyncMock()
    monkeypatch.setattr(backup, "archive_file", archive)
    with pytest.raises(backup.StorageError):
        await backup.backup_once(tmp_path, NOW)
    archive.assert_not_awaited()
    store.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_tar_stream_is_connected_to_age_without_plaintext_spool(tmp_path, monkeypatch):
    source = make_snapshot(tmp_path)
    target = tmp_path / "docassemble.tar.age"
    calls = []
    async def start(*args, **kwargs):
        calls.append((args, kwargs))
        assert not set(kwargs["env"]) & {"DOCASSEMBLE_API_KEY", "R2_SECRET_ACCESS_KEY_ZENAS"}
        if args[0] == "age":
            kwargs["stdout"].write(b"offline ciphertext stub")
        return SimpleNamespace(wait=AsyncMock(return_value=0), returncode=0)
    monkeypatch.setattr(backup.asyncio, "create_subprocess_exec", start)
    await backup.encrypted_snapshot(source, target, "R2_BACKUP_RECIPIENT")
    assert calls[0][0] == ("age", "--encrypt", "--recipient", "R2_BACKUP_RECIPIENT")
    assert calls[1][0] == ("tar", "-C", str(source), "-czf", "-", ".")
    assert isinstance(calls[0][1]["stdin"], int) and isinstance(calls[1][1]["stdout"], int)
    assert target.read_bytes() == b"offline ciphertext stub"
