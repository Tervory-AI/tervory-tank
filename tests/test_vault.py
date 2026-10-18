"""Plugins vaults: isolation, encryption, write-only secrets, the on/off switch, feeds.

No database and no network. The production store is Postgres behind Tank.
These tests use the in-memory store and the HTTP routes mounted alone.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

import vault  # noqa: E402
from feeds.keys import configure_vault, feed_key, key_is_set  # noqa: E402
from feeds.vault_client import refresh  # noqa: E402
from vault import (  # noqa: E402
    OFF_MESSAGE,
    PLATFORM_TENANT,
    Actor,
    MemoryVaultStore,
    VaultService,
    apply_lab_dev_fixture,
    feed_is_on,
    inspect_upload,
    install_store,
    open_secret,
    router,
    seal,
)

SECRET = "vault-secret-value-9f3a"
OTHER = "another-secret-value-22"
KEY = bytes.fromhex("ab" * 32)
TENANT_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
TENANT_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
PDF = b"%PDF-1.1\n1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n2 0 obj<< /Type /Pages /Count 1 /Kids [3 0 R] >>endobj\n3 0 obj<< /Type /Page /Parent 2 0 R >>endobj\n%%EOF"


def _run(coro):
    return asyncio.run(coro)


def _service() -> VaultService:
    return VaultService(MemoryVaultStore(), keys=lambda: KEY)


def _user(squad: str = "market_lab") -> Actor:
    return Actor("user", "user_clerk", squad)


def _agent(name: str) -> Actor:
    return Actor("agent", name, name)


def _admin() -> Actor:
    return Actor("admin", "user_founder", None)


def _xlsx() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as package:
        package.writestr("xl/workbook.xml", "<workbook></workbook>")
        package.writestr(
            "xl/worksheets/sheet1.xml",
            "<worksheet><sheetData><row r=\"1\"></row><row r=\"2\"></row></sheetData></worksheet>",
        )
    return buf.getvalue()


def test_squad_vaults_default_off_and_tank_vault_stays_on():
    service = _service()

    async def check() -> None:
        for vault_id in vault.SQUAD_VAULTS.values():
            assert await service.is_on(vault_id) is False
        assert await service.is_on(vault.TANK_VAULT) is True
        with pytest.raises(vault.VaultError):
            await service.set_switch(_admin(), vault.TANK_VAULT, False)
        assert await service.is_on(vault.TANK_VAULT) is True

    _run(check())
    schema = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
    main = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    assert "INSERT INTO tank.vault_switch" not in schema
    assert "apply_lab_dev_fixture(" not in main
    assert 'PLATFORM_TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")' in main
    assert PLATFORM_TENANT == "00000000-0000-0000-0000-000000000001"


def test_dev_fixture_turns_only_lab_on_and_audits_it():
    service = _service()

    async def check() -> None:
        await apply_lab_dev_fixture(service)
        assert await service.is_on("lab.vault") is True
        assert await service.is_on("tiger.vault") is False
        trail = await service.audit(_admin(), "lab.vault")
        assert trail["audit"][0]["action"] == "switch"
        assert trail["audit"][0]["detail"] == "on"
        assert SECRET not in json.dumps(trail)

    _run(check())


def test_off_vault_returns_nothing_and_refuses_writes():
    service = _service()

    async def check() -> None:
        with pytest.raises(vault.VaultOff):
            await service.save_secret(_user(), "lab.vault", TENANT_A, "FRED_API_KEY", "FRED", SECRET)
        assert service.store.secrets == {}
        with pytest.raises(vault.VaultOff):
            await service.plugins(_user(), "lab.vault", TENANT_A)
        await service.set_switch(_admin(), "lab.vault", True)
        await service.save_secret(_user(), "lab.vault", TENANT_A, "FRED_API_KEY", "FRED", SECRET)
        await service.set_switch(_admin(), "lab.vault", False)
        with pytest.raises(vault.VaultOff):
            await service.plugins(_user(), "lab.vault", TENANT_A)
        with pytest.raises(vault.VaultOff):
            await service.resolve(_agent("market_lab"), "lab.vault", TENANT_A, "FRED_API_KEY")
        trail = await service.audit(_admin(), "lab.vault")
        details = [row["detail"] for row in trail["audit"]]
        assert "off" in details
        assert "on" in details
        blob = json.dumps(trail)
        assert SECRET not in blob

    _run(check())


def test_encryption_round_trip_and_write_only_list():
    service = _service()

    async def check() -> None:
        await service.set_switch(_admin(), "lab.vault", True)
        saved = await service.save_secret(_user(), "lab.vault", TENANT_A, "FRED_API_KEY", "Freight index", SECRET)
        assert saved["mask"] == "••••••••"
        assert "value" not in saved
        listed = await service.plugins(_user(), "lab.vault", TENANT_A)
        blob = json.dumps(listed)
        assert SECRET not in blob
        assert listed["secrets"][0]["name"] == "FRED_API_KEY"
        assert listed["secrets"][0]["purpose"] == "Freight index"
        assert listed["secrets"][0]["mask"] == "••••••••"
        assert await service.resolve(_agent("market_lab"), "lab.vault", TENANT_A, "FRED_API_KEY") == SECRET
        await service.save_secret(_user(), "lab.vault", TENANT_A, "FRED_API_KEY", "Freight index", OTHER)
        assert await service.resolve(_user(), "lab.vault", TENANT_A, "FRED_API_KEY") == OTHER
        again = json.dumps(await service.plugins(_user(), "lab.vault", TENANT_A))
        assert OTHER not in again
        assert SECRET not in again
        await service.remove_secret(_user(), "lab.vault", TENANT_A, "FRED_API_KEY")
        assert await service.resolve(_agent("market_lab"), "lab.vault", TENANT_A, "FRED_API_KEY") is None

    _run(check())
    nonce, ciphertext = seal(KEY, TENANT_A, "lab.vault", "FRED_API_KEY", SECRET)
    assert SECRET.encode() not in ciphertext
    assert open_secret(KEY, TENANT_A, "lab.vault", "FRED_API_KEY", nonce, ciphertext) == SECRET
    with pytest.raises(vault.VaultError):
        open_secret(KEY, TENANT_A, "tiger.vault", "FRED_API_KEY", nonce, ciphertext)


def test_secret_is_not_logged_or_written_into_the_audit():
    service = _service()
    records: list[str] = []
    handler = logging.Handler()
    handler.emit = lambda record: records.append(record.getMessage())  # type: ignore[method-assign]
    vault.log.addHandler(handler)
    vault.log.setLevel(logging.INFO)

    async def check() -> None:
        await service.set_switch(_admin(), "lab.vault", True)
        await service.save_secret(_user(), "tiger.vault", TENANT_A, "X", "nope", SECRET)

    try:
        with pytest.raises(vault.VaultError):
            _run(check())
        _run(service.set_switch(_admin(), "tiger.vault", True))

        async def save() -> None:
            await service.save_secret(_user("tiger"), "tiger.vault", TENANT_A, "Supplier", "Supplier key", SECRET)

        _run(save())
    finally:
        vault.log.removeHandler(handler)
    blob = "\n".join(records)
    assert SECRET not in blob
    trail = _run(service.audit(_admin(), "tiger.vault"))
    assert SECRET not in json.dumps(trail)


def test_vault_isolation_between_squads_and_tenants():
    service = _service()

    async def check() -> None:
        await service.set_switch(_admin(), "lab.vault", True)
        await service.set_switch(_admin(), "tiger.vault", True)
        await service.save_secret(_user("market_lab"), "lab.vault", TENANT_A, "FRED_API_KEY", "FRED", SECRET)
        await service.save_secret(_user("market_lab"), "lab.vault", TENANT_B, "FRED_API_KEY", "FRED", OTHER)
        await service.save_secret(_user("tiger"), "tiger.vault", TENANT_A, "BRAVE_API_KEY", "Search", "tiger-secret-value-77")
        lab = await service.plugins(_user("market_lab"), "lab.vault", TENANT_A)
        assert [row["name"] for row in lab["secrets"]] == ["FRED_API_KEY"]
        other = await service.plugins(_agent("market_lab"), "lab.vault", TENANT_B)
        assert json.dumps(other).count(OTHER) == 0
        assert await service.resolve(_agent("market_lab"), "lab.vault", TENANT_B, "FRED_API_KEY") == OTHER
        with pytest.raises(vault.VaultError):
            await service.plugins(_agent("market_lab"), "tiger.vault", TENANT_A)
        with pytest.raises(vault.VaultError):
            await service.plugins(_user("market_lab"), "tiger.vault", TENANT_A)
        with pytest.raises(vault.VaultError):
            await service.resolve(_agent("tiger"), "lab.vault", TENANT_A, "FRED_API_KEY")
        with pytest.raises(vault.VaultError):
            await service.plugins(_user("market_lab"), vault.TANK_VAULT, TENANT_A)
        with pytest.raises(vault.VaultError):
            await service.save_secret(_agent("market_lab"), "lab.vault", TENANT_A, "EIA_API_KEY", "EIA", SECRET)

    _run(check())


def test_tank_vault_is_only_for_tank():
    service = _service()

    async def check() -> None:
        await service.admin_save_platform_secret(_admin(), "PERPLEXITY_API_KEY", "Search", SECRET)
        assert await service.platform_secret("PERPLEXITY_API_KEY") == SECRET
        listed = await service.admin_plugins(_admin())
        assert SECRET not in json.dumps(listed)
        assert listed["secrets"][0]["mask"] == "••••••••"
        with pytest.raises(vault.VaultError):
            await service.resolve(_agent("market_lab"), vault.TANK_VAULT, PLATFORM_TENANT, "PERPLEXITY_API_KEY")

    _run(check())


def test_mcp_token_is_write_only():
    service = _service()

    async def check() -> None:
        await service.set_switch(_admin(), "lab.vault", True)
        saved = await service.add_connection(
            _user(),
            "lab.vault",
            TENANT_A,
            "Catalogue",
            "https://supplier.example/mcp",
            "token",
            SECRET,
        )
        assert saved["has_token"] is True
        assert "token" not in saved or saved.get("token") is None
        listed = await service.plugins(_user(), "lab.vault", TENANT_A)
        blob = json.dumps(listed)
        assert SECRET not in blob
        assert "mcp:" not in blob
        assert listed["connections"][0]["has_token"] is True
        token_name = next(iter(service.store.secrets))[2]
        assert await service.resolve(_agent("market_lab"), "lab.vault", TENANT_A, token_name) == SECRET

    _run(check())


def test_upload_type_limits():
    csv_meta = inspect_upload("prices.csv", b"sku,price\nA,1\nB,2\n")
    assert csv_meta["row_count"] == 3
    assert csv_meta["media_type"] == "text/csv"
    xlsx_meta = inspect_upload("book.xlsx", _xlsx())
    assert xlsx_meta["row_count"] == 2
    pdf_meta = inspect_upload("note.pdf", PDF)
    assert pdf_meta["page_count"] == 1
    with pytest.raises(vault.VaultError, match="Only CSV, XLSX, and PDF"):
        inspect_upload("pic.png", b"\x89PNG\r\n")
    with pytest.raises(vault.VaultError, match="Only CSV, XLSX, and PDF"):
        inspect_upload("note.pdf", b"not a pdf")
    with pytest.raises(vault.VaultError, match="larger than 8 MB"):
        inspect_upload("big.csv", b"a" * (vault.MAX_FILE_BYTES + 1))

    service = _service()

    async def saved() -> None:
        await service.set_switch(_admin(), "lab.vault", True)
        meta = await service.add_file(_user(), "lab.vault", TENANT_A, "prices.csv", b"sku,price\nA,1\n")
        assert "content" not in meta
        assert meta["rows"] == 2
        listed = await service.plugins(_user(), "lab.vault", TENANT_A)
        assert "content" not in json.dumps(listed)
        assert listed["files"][0]["name"] == "prices.csv"

    _run(saved())


def test_feed_on_off_from_env_or_vault_or_neither(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert feed_is_on(key_name="FRED_API_KEY", env_present=False, vault_on=False, vault_has_key=False) is False
    assert feed_is_on(key_name="FRED_API_KEY", env_present=False, vault_on=False, vault_has_key=True) is False
    assert feed_is_on(key_name="FRED_API_KEY", env_present=False, vault_on=True, vault_has_key=False) is False
    assert feed_is_on(key_name="FRED_API_KEY", env_present=True, vault_on=False, vault_has_key=False) is True
    assert feed_is_on(key_name="FRED_API_KEY", env_present=False, vault_on=True, vault_has_key=True) is True
    assert feed_is_on(key_name="", env_present=False, vault_on=False, vault_has_key=False) is True

    calls: list[str] = []
    configure_vault(enabled=False, names=["FRED_API_KEY"], resolver=lambda name: calls.append(name) or SECRET)
    assert key_is_set("FRED_API_KEY") is False
    assert feed_key("FRED_API_KEY") == ""
    assert calls == []

    configure_vault(enabled=True, names=["FRED_API_KEY"], resolver=lambda name: calls.append(name) or SECRET)
    assert key_is_set("FRED_API_KEY") is True
    assert feed_key("FRED_API_KEY") == SECRET
    assert calls == ["FRED_API_KEY"]

    monkeypatch.setenv("FRED_API_KEY", "env-secret-value-88")
    assert feed_key("FRED_API_KEY") == "env-secret-value-88"
    assert calls == ["FRED_API_KEY"]
    configure_vault(enabled=False)
    assert key_is_set("FRED_API_KEY") is True
    monkeypatch.delenv("FRED_API_KEY", raising=False)
    assert key_is_set("FRED_API_KEY") is False


def test_vault_client_fail_closed_and_does_not_keep_a_secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TANK_URL", "http://tank.test")
    monkeypatch.setenv("TANK_KEY", "lab-agent-key")
    monkeypatch.setenv("FEEDS_TENANT_ID", TENANT_A)
    monkeypatch.delenv("EIA_API_KEY", raising=False)

    class Response:
        def __init__(self, payload: dict) -> None:
            self._raw = json.dumps(payload).encode()

        def read(self) -> bytes:
            return self._raw

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    def opener(request, timeout=5):  # noqa: ARG001
        if request.get_method() == "GET":
            return Response({"enabled": True, "secrets": [{"name": "EIA_API_KEY", "value": SECRET}]})
        return Response({"found": True, "value": SECRET})

    refresh(opener)
    assert key_is_set("EIA_API_KEY") is True
    assert feed_key("EIA_API_KEY") == SECRET

    def broken(request, timeout=5):  # noqa: ARG001
        raise OSError("down")

    refresh(broken)
    assert key_is_set("EIA_API_KEY") is False
    assert feed_key("EIA_API_KEY") == ""


def test_http_routes_hide_secrets_and_enforce_the_switch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TANK_API_KEY", "workspace-test-key")
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", "lab-agent-key")
    monkeypatch.setenv("TANK_KEY_TIGER", "tiger-agent-key")
    monkeypatch.setenv("VAULT_MASTER_KEY", "ab" * 32)
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "user_founder")
    install_store(MemoryVaultStore())
    client = TestClient(FastAPI())
    client.app.include_router(router)
    user = {"x-tank-key": "workspace-test-key", "x-tervory-user": "user_clerk", "x-tervory-squad": "market_lab"}
    admin = {"x-tank-key": "workspace-test-key", "x-tervory-admin": "user_founder"}
    lab = {"x-tank-key": "lab-agent-key"}
    tiger = {"x-tank-key": "tiger-agent-key"}

    off = client.get(f"/v1/vaults/lab.vault/plugins?tenant_id={TENANT_A}", headers=user)
    assert off.status_code == 200
    assert off.json()["enabled"] is False
    assert off.json()["message"] == OFF_MESSAGE
    assert off.json()["secrets"] == []
    refused = client.post(
        "/v1/vaults/lab.vault/secrets",
        headers=user,
        json={"tenant_id": TENANT_A, "name": "FRED_API_KEY", "purpose": "FRED", "value": SECRET},
    )
    assert refused.status_code == 403
    assert SECRET not in refused.text

    turned = client.post("/v1/admin/vaults/lab.vault/switch", headers=admin, json={"enabled": True})
    assert turned.status_code == 200
    assert turned.json()["enabled"] is True
    denied = client.post("/v1/admin/vaults/lab.vault/switch", headers=user, json={"enabled": False})
    assert denied.status_code == 404

    saved = client.post(
        "/v1/vaults/lab.vault/secrets",
        headers=user,
        json={"tenant_id": TENANT_A, "name": "FRED_API_KEY", "purpose": "FRED", "value": SECRET},
    )
    assert saved.status_code == 200
    assert SECRET not in saved.text
    listed = client.get(f"/v1/vaults/lab.vault/plugins?tenant_id={TENANT_A}", headers=user)
    assert SECRET not in listed.text
    assert listed.json()["secrets"][0]["mask"] == "••••••••"
    assert "value" not in listed.json()["secrets"][0]

    resolved = client.post(
        "/v1/vaults/lab.vault/secrets/resolve",
        headers=lab,
        json={"tenant_id": TENANT_A, "name": "FRED_API_KEY"},
    )
    assert resolved.json()["value"] == SECRET
    blocked = client.post(
        "/v1/vaults/tiger.vault/secrets/resolve",
        headers=lab,
        json={"tenant_id": TENANT_A, "name": "FRED_API_KEY"},
    )
    assert blocked.status_code == 403
    assert SECRET not in blocked.text
    agent_write = client.post(
        "/v1/vaults/lab.vault/secrets",
        headers=lab,
        json={"tenant_id": TENANT_A, "name": "EIA_API_KEY", "purpose": "EIA", "value": SECRET},
    )
    assert agent_write.status_code == 403
    tank_read = client.post(
        "/v1/vaults/tank.vault/secrets/resolve",
        headers=tiger,
        json={"tenant_id": PLATFORM_TENANT, "name": "PERPLEXITY_API_KEY"},
    )
    assert tank_read.status_code == 403

    echo = client.post(
        "/v1/vaults/lab.vault/secrets",
        headers={**user, "content-type": "application/json"},
        content=SECRET,
    )
    assert echo.status_code == 400
    assert SECRET not in echo.text

    uploaded = client.post(
        f"/v1/vaults/lab.vault/files?tenant_id={TENANT_A}",
        headers=user,
        files={"file": ("pic.png", b"\x89PNG", "image/png")},
    )
    assert uploaded.status_code == 400
    assert "Only CSV, XLSX, and PDF" in uploaded.text
    good = client.post(
        f"/v1/vaults/lab.vault/files?tenant_id={TENANT_A}",
        headers=user,
        files={"file": ("prices.csv", b"sku,price\nA,1\n", "text/csv")},
    )
    assert good.status_code == 200
    assert good.json()["files"][0]["rows"] == 2
    assert "content" not in good.text

    audit = client.get("/v1/admin/vaults/lab.vault/audit", headers=admin)
    assert audit.status_code == 200
    assert any(row["action"] == "switch" for row in audit.json()["audit"])
    assert SECRET not in audit.text

    client.post("/v1/admin/vaults/lab.vault/switch", headers=admin, json={"enabled": False})
    hidden = client.get(f"/v1/vaults/lab.vault/plugins?tenant_id={TENANT_A}", headers=user)
    assert hidden.json()["secrets"] == []
    assert hidden.json()["files"] == []
    assert "FRED_API_KEY" not in hidden.text
    assert "prices.csv" not in hidden.text
