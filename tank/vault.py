"""Plugins vaults. Tank is the only door.

Eleven vaults: lab.vault, tisan.vault, tiger.vault, base.vault, rig.vault,
zenas.vault, tervory.vault, radix.vault, skala.vault, library.vault, and
tank.vault. Squad pages and squad agents call these routes. They do not
open the database themselves.

tank.vault holds platform secrets Tank uses on a squad's behalf (a model
key such as Perplexity). It is always on. No squad route can read it.
skala.vault is Skala's own Plugins vault, the same as the other squad vaults.
library.vault is a separate skills library. It is not skala.vault. Approved
skills live there. Another squad may link to one and transfer a copy into
its own vault. It cannot rewrite the library, read another squad's vault,
or read tank.vault. While library.vault is off, nothing links and nothing
transfers.
The other vaults are off until a founder turns one on. While a vault is off,
reads return an empty list and writes are refused, so nothing in it
reaches an agent or a feed.

Secrets are AES-256-GCM with VAULT_MASTER_KEY. A list returns the name, what
the key unlocks, when it was saved, and a mask. The value is not returned,
logged, or written to the audit trail. Files live in Postgres (bytea), not
in the repo. Every item row is scoped by tenant_id.

Production startup does not turn a squad vault on. Tests call
apply_lab_dev_fixture. A founder turns one on with
POST /v1/admin/vaults/<vault>/switch and {"enabled": true}.
"""

from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import logging
import os
import re
import uuid
import zipfile
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from fastapi import APIRouter, HTTPException, Request

log = logging.getLogger("tank.vault")

OFF_MESSAGE = "This vault is off. Turn it on in Tank."
MASK = "••••••••"
PLATFORM_TENANT = "00000000-0000-0000-0000-000000000001"
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SECRET_CHARS = 4096

# Squad id (the agent id) -> vault. tank.vault is not in this map.
SQUAD_VAULTS: dict[str, str] = {
    "market_lab": "lab.vault",
    "tisan": "tisan.vault",
    "tiger": "tiger.vault",
    "base": "base.vault",
    "rig": "rig.vault",
    "zenas": "zenas.vault",
    "tervory": "tervory.vault",
    "radix": "radix.vault",
    "skala": "skala.vault",
}
TANK_VAULT = "tank.vault"
# Skills library. Not a squad Plugins vault, and not skala.vault.
LIBRARY_VAULT = "library.vault"
LIBRARY_OWNER = "skala"
VAULT_SQUAD = {vault_id: squad for squad, vault_id in SQUAD_VAULTS.items()}
ALL_VAULTS = tuple(SQUAD_VAULTS.values()) + (LIBRARY_VAULT, TANK_VAULT)

_SKILL_ID = re.compile(r"^[a-z][a-z0-9._-]{0,80}$")
_SKILL_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._-]{0,40}$")

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:@-]{0,79}$")
_SECRET_QUERY = re.compile(r"(?i)(api_key|apikey|access_token|token|key)=")
_PDF_PAGE = re.compile(rb"/Type\s*/Page(?!s)")
_XLSX_ROW = re.compile(r"<row[\s>]")

_PRIVATE = {"value", "token", "ciphertext", "nonce", "bytes", "content", "plaintext", "secret"}


class VaultError(Exception):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(message)


class VaultOff(VaultError):
    def __init__(self) -> None:
        super().__init__(403, OFF_MESSAGE)


def feed_is_on(*, key_name: str, env_present: bool, vault_on: bool, vault_has_key: bool) -> bool:
    """A keyed feed is on when Coolify has the key, or the squad vault is on and holds it.

    A vault that is off contributes nothing, even if a row is stored.
    """
    if not key_name:
        return True
    if env_present:
        return True
    return bool(vault_on and vault_has_key)


def master_key() -> bytes:
    """32-byte key from VAULT_MASTER_KEY (hex). The value is never logged."""
    raw = os.environ.get("VAULT_MASTER_KEY", "").strip()
    if len(raw) != 64 or any(ch not in "0123456789abcdefABCDEF" for ch in raw):
        raise VaultError(503, "Vault encryption is not configured.")
    return bytes.fromhex(raw)


def _aad(tenant_id: str, vault_id: str, name: str) -> bytes:
    return f"{tenant_id}|{vault_id}|{name}".encode()


def seal(key: bytes, tenant_id: str, vault_id: str, name: str, value: str) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, value.encode(), _aad(tenant_id, vault_id, name))
    return nonce, ciphertext


def open_secret(key: bytes, tenant_id: str, vault_id: str, name: str, nonce: bytes, ciphertext: bytes) -> str:
    try:
        raw = AESGCM(key).decrypt(nonce, ciphertext, _aad(tenant_id, vault_id, name))
    except Exception as exc:
        raise VaultError(500, "The secret could not be read.") from exc
    return raw.decode()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _same(left: bytes, right: bytes) -> bool:
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def _agent_hashes() -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for env_name, env_val in os.environ.items():
        if not env_name.startswith("TANK_KEY_"):
            continue
        value = env_val.strip()
        if not value:
            continue
        agent = env_name[len("TANK_KEY_") :].lower()
        if not agent or not all(ch.isalnum() or ch == "_" for ch in agent):
            continue
        found[agent] = hashlib.sha256(value.encode()).digest()
    return found


def match_caller(tank_key: str) -> tuple[str, str] | None:
    """('user', '') for the Workspace key, or ('agent', agent id). Never logs the key."""
    if not tank_key or not tank_key.strip():
        return None
    try:
        presented = tank_key.encode()
    except UnicodeError:
        return None
    expected = os.environ.get("TANK_API_KEY", "")
    if expected.strip() and _same(presented, expected.encode()):
        return ("user", "")
    digest = hashlib.sha256(presented).digest()
    for agent, hashed in _agent_hashes().items():
        if _same(hashed, digest):
            return ("agent", agent)
    return None


def founder_ok(tank_key: str, user_id: str) -> bool:
    expected = os.environ.get("TANK_API_KEY", "")
    if not expected or not tank_key or not user_id:
        return False
    try:
        if not hmac.compare_digest(tank_key.encode(), expected.encode()):
            return False
    except Exception:
        return False
    allowed = {part.strip() for part in os.environ.get("TERVORY_ADMIN_USER_IDS", "").split(",") if part.strip()}
    return user_id in allowed


class Actor:
    def __init__(self, kind: str, actor_id: str, squad: str | None) -> None:
        self.kind = kind
        self.id = actor_id
        self.squad = squad


def _clean_name(name: str) -> str:
    text = " ".join(name.split())
    if not _NAME.match(text):
        raise VaultError(400, "Use a short name made of letters, numbers, and spaces.")
    return text


def _clean_purpose(purpose: str, value: str) -> str:
    text = " ".join(purpose.split())
    if value and len(value) >= 8 and value in text:
        raise VaultError(400, "The description must not contain the key.")
    if len(text) > 240:
        raise VaultError(400, "The description is too long.")
    return text or "Saved key"


def _clean_secret(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VaultError(400, "Add a key first. Nothing was stored.")
    if len(value) > MAX_SECRET_CHARS:
        raise VaultError(400, "That key is too long. Nothing was stored.")
    if len(value) >= 8 and value in name:
        raise VaultError(400, "The name must not contain the key.")
    return value


def _http_url(value: str) -> str:
    url = value.strip()
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise VaultError(400, "Use an http or https link.")
    if parsed.username or parsed.password or _SECRET_QUERY.search(url):
        raise VaultError(400, "The link must not include a key.")
    if len(url) > 2000:
        raise VaultError(400, "That link is too long.")
    return url


def _frequency(value: str) -> str:
    text = value.strip().lower()
    if text in {"daily", "day"}:
        return "daily"
    if text in {"weekly", "week"}:
        return "weekly"
    raise VaultError(400, "Choose daily or weekly.")


def _auth_type(value: str) -> str:
    text = value.strip().lower().replace("_", " ")
    if text in {"provider", "provider sign-in", "sign-in", "signin"}:
        return "provider"
    if text == "token":
        return "token"
    raise VaultError(400, "Choose provider sign-in or a token.")


def _tenant(value: str) -> str:
    try:
        return str(uuid.UUID(value))
    except (TypeError, ValueError):
        raise VaultError(400, "A workspace is required.") from None


def inspect_upload(filename: str, content: bytes) -> dict[str, Any]:
    """Accept CSV, XLSX, and PDF. Count rows or pages. Refuse anything else."""
    if not content:
        raise VaultError(400, "That file is empty. Nothing was saved.")
    if len(content) > MAX_FILE_BYTES:
        raise VaultError(400, "That file is larger than 8 MB. Nothing was saved.")
    base = os.path.basename(filename or "").replace("\\", "/").split("/")[-1].strip()
    if not base or base in {".", ".."} or len(base) > 200:
        raise VaultError(400, "That file needs a short name. Nothing was saved.")
    suffix = base.rsplit(".", 1)[-1].lower() if "." in base else ""
    if suffix == "csv":
        if b"\x00" in content[:8192]:
            raise VaultError(400, "Only CSV, XLSX, and PDF files can be uploaded.")
        text = content.decode("utf-8-sig", errors="replace")
        rows = sum(1 for _ in csv.reader(io.StringIO(text)))
        return {
            "name": base,
            "media_type": "text/csv",
            "size_bytes": len(content),
            "row_count": rows,
            "page_count": None,
            "status": "ready",
        }
    if suffix == "xlsx":
        if not content.startswith(b"PK"):
            raise VaultError(400, "Only CSV, XLSX, and PDF files can be uploaded.")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as package:
                names = package.namelist()
                if "xl/workbook.xml" not in names:
                    raise VaultError(400, "Only CSV, XLSX, and PDF files can be uploaded.")
                total = 0
                for sheet in names:
                    if sheet.startswith("xl/worksheets/") and sheet.endswith(".xml"):
                        xml = package.read(sheet).decode("utf-8", errors="replace")
                        total += len(_XLSX_ROW.findall(xml))
        except VaultError:
            raise
        except (zipfile.BadZipFile, OSError):
            raise VaultError(400, "Only CSV, XLSX, and PDF files can be uploaded.") from None
        return {
            "name": base,
            "media_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "size_bytes": len(content),
            "row_count": total,
            "page_count": None,
            "status": "ready",
        }
    if suffix == "pdf":
        if not content.startswith(b"%PDF"):
            raise VaultError(400, "Only CSV, XLSX, and PDF files can be uploaded.")
        return {
            "name": base,
            "media_type": "application/pdf",
            "size_bytes": len(content),
            "row_count": None,
            "page_count": len(_PDF_PAGE.findall(content)),
            "status": "ready",
        }
    raise VaultError(400, "Only CSV, XLSX, and PDF files can be uploaded.")


class VaultStore(Protocol):
    async def get_switch(self, vault_id: str) -> bool | None: ...
    async def set_switch(self, vault_id: str, enabled: bool, actor: str) -> None: ...
    async def upsert_secret(self, row: dict[str, Any]) -> str: ...
    async def delete_secret(self, tenant_id: str, vault_id: str, name: str) -> bool: ...
    async def list_secrets(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]: ...
    async def get_secret(self, tenant_id: str, vault_id: str, name: str) -> dict[str, Any] | None: ...
    async def add_file(self, row: dict[str, Any]) -> None: ...
    async def list_files(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]: ...
    async def delete_file(self, tenant_id: str, vault_id: str, file_id: str) -> bool: ...
    async def add_link(self, row: dict[str, Any]) -> None: ...
    async def list_links(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]: ...
    async def delete_link(self, tenant_id: str, vault_id: str, link_id: str) -> bool: ...
    async def add_connection(self, row: dict[str, Any]) -> None: ...
    async def list_connections(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]: ...
    async def get_connection(self, tenant_id: str, vault_id: str, connection_id: str) -> dict[str, Any] | None: ...
    async def delete_connection(self, tenant_id: str, vault_id: str, connection_id: str) -> bool: ...
    async def add_audit(self, row: dict[str, Any]) -> None: ...
    async def list_audit(self, vault_id: str, limit: int) -> list[dict[str, Any]]: ...
    async def upsert_library_skill(self, row: dict[str, Any]) -> None: ...
    async def get_library_skill(self, tenant_id: str, skill_id: str, version: str) -> dict[str, Any] | None: ...
    async def list_library_skills(self, tenant_id: str) -> list[dict[str, Any]]: ...
    async def add_library_link(self, row: dict[str, Any]) -> None: ...
    async def list_library_links(self, tenant_id: str, squad: str) -> list[dict[str, Any]]: ...


class MemoryVaultStore:
    """In-memory store for tests. Production uses PostgresVaultStore."""

    def __init__(self) -> None:
        self.switches: dict[str, bool] = {}
        self.secrets: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.files: dict[str, dict[str, Any]] = {}
        self.links: dict[str, dict[str, Any]] = {}
        self.connections: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, Any]] = []
        self.library_skills: dict[tuple[str, str, str], dict[str, Any]] = {}
        self.library_links: dict[str, dict[str, Any]] = {}

    async def get_switch(self, vault_id: str) -> bool | None:
        if vault_id not in self.switches:
            return None
        return self.switches[vault_id]

    async def set_switch(self, vault_id: str, enabled: bool, actor: str) -> None:
        self.switches[vault_id] = enabled
        del actor

    async def upsert_secret(self, row: dict[str, Any]) -> str:
        key = (row["tenant_id"], row["vault_id"], row["name"])
        action = "replace" if key in self.secrets else "add"
        if action == "replace":
            row = {**row, "created_at": self.secrets[key]["created_at"]}
        self.secrets[key] = row
        return action

    async def delete_secret(self, tenant_id: str, vault_id: str, name: str) -> bool:
        return self.secrets.pop((tenant_id, vault_id, name), None) is not None

    async def list_secrets(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        rows = [row for (tenant, vault, _name), row in self.secrets.items() if tenant == tenant_id and vault == vault_id]
        return [
            {"name": row["name"], "purpose": row["purpose"], "mask": row["mask"], "saved_at": row["updated_at"]}
            for row in sorted(rows, key=lambda item: item["updated_at"], reverse=True)
        ]

    async def get_secret(self, tenant_id: str, vault_id: str, name: str) -> dict[str, Any] | None:
        row = self.secrets.get((tenant_id, vault_id, name))
        if row is None:
            return None
        return {"name": row["name"], "nonce": row["nonce"], "ciphertext": row["ciphertext"]}

    async def add_file(self, row: dict[str, Any]) -> None:
        self.files[row["id"]] = row

    async def list_files(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.files.values() if row["tenant_id"] == tenant_id and row["vault_id"] == vault_id]
        return [_public_file(row) for row in sorted(rows, key=lambda item: item["uploaded_at"], reverse=True)]

    async def delete_file(self, tenant_id: str, vault_id: str, file_id: str) -> bool:
        row = self.files.get(file_id)
        if row is None or row["tenant_id"] != tenant_id or row["vault_id"] != vault_id:
            return False
        del self.files[file_id]
        return True

    async def add_link(self, row: dict[str, Any]) -> None:
        self.links[row["id"]] = row

    async def list_links(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.links.values() if row["tenant_id"] == tenant_id and row["vault_id"] == vault_id]
        return [_public_link(row) for row in sorted(rows, key=lambda item: item["created_at"], reverse=True)]

    async def delete_link(self, tenant_id: str, vault_id: str, link_id: str) -> bool:
        row = self.links.get(link_id)
        if row is None or row["tenant_id"] != tenant_id or row["vault_id"] != vault_id:
            return False
        del self.links[link_id]
        return True

    async def add_connection(self, row: dict[str, Any]) -> None:
        self.connections[row["id"]] = row

    async def list_connections(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        rows = [row for row in self.connections.values() if row["tenant_id"] == tenant_id and row["vault_id"] == vault_id]
        return [_public_connection(row) for row in sorted(rows, key=lambda item: item["created_at"], reverse=True)]

    async def get_connection(self, tenant_id: str, vault_id: str, connection_id: str) -> dict[str, Any] | None:
        row = self.connections.get(connection_id)
        if row is None or row["tenant_id"] != tenant_id or row["vault_id"] != vault_id:
            return None
        return row

    async def delete_connection(self, tenant_id: str, vault_id: str, connection_id: str) -> bool:
        row = await self.get_connection(tenant_id, vault_id, connection_id)
        if row is None:
            return False
        del self.connections[connection_id]
        return True

    async def add_audit(self, row: dict[str, Any]) -> None:
        self.audit.append(row)

    async def list_audit(self, vault_id: str, limit: int) -> list[dict[str, Any]]:
        rows = [row for row in self.audit if row["vault_id"] == vault_id]
        return list(reversed(rows[-limit:]))

    async def upsert_library_skill(self, row: dict[str, Any]) -> None:
        self.library_skills[(row["tenant_id"], row["skill_id"], row["version"])] = row

    async def get_library_skill(self, tenant_id: str, skill_id: str, version: str) -> dict[str, Any] | None:
        row = self.library_skills.get((tenant_id, skill_id, version))
        return None if row is None else dict(row)

    async def list_library_skills(self, tenant_id: str) -> list[dict[str, Any]]:
        rows = [row for (tenant, _skill, _version), row in self.library_skills.items() if tenant == tenant_id]
        return [_public_library_skill(row) for row in sorted(rows, key=lambda item: (item["skill_id"], item["version"]))]

    async def add_library_link(self, row: dict[str, Any]) -> None:
        self.library_links[row["id"]] = row

    async def list_library_links(self, tenant_id: str, squad: str) -> list[dict[str, Any]]:
        rows = [
            row for row in self.library_links.values()
            if row["tenant_id"] == tenant_id and row["squad"] == squad
        ]
        return [_public_library_link(row) for row in sorted(rows, key=lambda item: item["created_at"], reverse=True)]


def _public_library_skill(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_id": row["skill_id"],
        "version": row["version"],
        "agent": row["agent"],
        "description": row["description"],
        "published_at": row["published_at"],
    }


def _public_library_link(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "squad": row["squad"],
        "vault": row["vault_id"],
        "skill_id": row["skill_id"],
        "version": row["version"],
        "created_at": row["created_at"],
    }


def _public_file(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "type": row["media_type"],
        "size": row["size_bytes"],
        "rows": row["row_count"],
        "pages": row["page_count"],
        "uploaded_at": row["uploaded_at"],
        "status": row["status"],
    }


def _public_link(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "url": row["url"],
        "label": row["label"],
        "frequency": row["frequency"],
        "last_checked": row["last_checked"],
        "status": row["status"],
    }


def _public_connection(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "server_url": row["server_url"],
        "auth_type": row["auth_type"],
        "status": row["status"],
        "last_used": row["last_used"],
        "has_token": bool(row.get("token_name")),
    }


class PostgresVaultStore:
    """Postgres store. File bytes sit in tank.vault_file, not in the repo."""

    def __init__(self, pool_getter: Callable[[], Any]) -> None:
        self._pool = pool_getter

    async def get_switch(self, vault_id: str) -> bool | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow("SELECT enabled FROM tank.vault_switch WHERE vault_id = $1", vault_id)
        if row is None:
            return None
        return bool(row["enabled"])

    async def set_switch(self, vault_id: str, enabled: bool, actor: str) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.vault_switch (vault_id, enabled, updated_at, updated_by)
                VALUES ($1, $2, now(), $3)
                ON CONFLICT (vault_id) DO UPDATE
                SET enabled = EXCLUDED.enabled, updated_at = now(), updated_by = EXCLUDED.updated_by
                """,
                vault_id,
                enabled,
                actor,
            )

    async def upsert_secret(self, row: dict[str, Any]) -> str:
        async with self._pool().acquire() as conn:
            existing = await conn.fetchrow(
                """
                SELECT 1 FROM tank.vault_secret
                WHERE tenant_id = $1::uuid AND vault_id = $2 AND name = $3
                """,
                row["tenant_id"],
                row["vault_id"],
                row["name"],
            )
            await conn.execute(
                """
                INSERT INTO tank.vault_secret
                    (tenant_id, vault_id, name, purpose, nonce, ciphertext, mask, created_at, updated_at, updated_by)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (tenant_id, vault_id, name) DO UPDATE
                SET purpose = EXCLUDED.purpose, nonce = EXCLUDED.nonce, ciphertext = EXCLUDED.ciphertext,
                    mask = EXCLUDED.mask, updated_at = EXCLUDED.updated_at, updated_by = EXCLUDED.updated_by
                """,
                row["tenant_id"],
                row["vault_id"],
                row["name"],
                row["purpose"],
                row["nonce"],
                row["ciphertext"],
                row["mask"],
                row["created_at"],
                row["updated_at"],
                row["updated_by"],
            )
        return "replace" if existing else "add"

    async def delete_secret(self, tenant_id: str, vault_id: str, name: str) -> bool:
        async with self._pool().acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tank.vault_secret WHERE tenant_id = $1::uuid AND vault_id = $2 AND name = $3",
                tenant_id,
                vault_id,
                name,
            )
        return result.endswith("1")

    async def list_secrets(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT name, purpose, mask, updated_at
                FROM tank.vault_secret
                WHERE tenant_id = $1::uuid AND vault_id = $2
                ORDER BY updated_at DESC
                """,
                tenant_id,
                vault_id,
            )
        return [
            {"name": row["name"], "purpose": row["purpose"], "mask": row["mask"], "saved_at": row["updated_at"]}
            for row in rows
        ]

    async def get_secret(self, tenant_id: str, vault_id: str, name: str) -> dict[str, Any] | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT name, nonce, ciphertext FROM tank.vault_secret
                WHERE tenant_id = $1::uuid AND vault_id = $2 AND name = $3
                """,
                tenant_id,
                vault_id,
                name,
            )
        if row is None:
            return None
        return {"name": row["name"], "nonce": bytes(row["nonce"]), "ciphertext": bytes(row["ciphertext"])}

    async def add_file(self, row: dict[str, Any]) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.vault_file
                    (id, tenant_id, vault_id, name, media_type, size_bytes, row_count, page_count, status, bytes, uploaded_at, uploaded_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                row["id"],
                row["tenant_id"],
                row["vault_id"],
                row["name"],
                row["media_type"],
                row["size_bytes"],
                row["row_count"],
                row["page_count"],
                row["status"],
                row["content"],
                row["uploaded_at"],
                row["uploaded_by"],
            )

    async def list_files(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, media_type, size_bytes, row_count, page_count, status, uploaded_at
                FROM tank.vault_file
                WHERE tenant_id = $1::uuid AND vault_id = $2
                ORDER BY uploaded_at DESC
                """,
                tenant_id,
                vault_id,
            )
        return [
            {
                "id": str(row["id"]),
                "name": row["name"],
                "type": row["media_type"],
                "size": row["size_bytes"],
                "rows": row["row_count"],
                "pages": row["page_count"],
                "uploaded_at": row["uploaded_at"],
                "status": row["status"],
            }
            for row in rows
        ]

    async def delete_file(self, tenant_id: str, vault_id: str, file_id: str) -> bool:
        async with self._pool().acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tank.vault_file WHERE id = $1::uuid AND tenant_id = $2::uuid AND vault_id = $3",
                file_id,
                tenant_id,
                vault_id,
            )
        return result.endswith("1")

    async def add_link(self, row: dict[str, Any]) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.vault_link
                    (id, tenant_id, vault_id, url, label, frequency, last_checked, status, created_at, created_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10)
                """,
                row["id"],
                row["tenant_id"],
                row["vault_id"],
                row["url"],
                row["label"],
                row["frequency"],
                row["last_checked"],
                row["status"],
                row["created_at"],
                row["created_by"],
            )

    async def list_links(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, url, label, frequency, last_checked, status
                FROM tank.vault_link
                WHERE tenant_id = $1::uuid AND vault_id = $2
                ORDER BY created_at DESC
                """,
                tenant_id,
                vault_id,
            )
        return [
            {
                "id": str(row["id"]),
                "url": row["url"],
                "label": row["label"],
                "frequency": row["frequency"],
                "last_checked": row["last_checked"],
                "status": row["status"],
            }
            for row in rows
        ]

    async def delete_link(self, tenant_id: str, vault_id: str, link_id: str) -> bool:
        async with self._pool().acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tank.vault_link WHERE id = $1::uuid AND tenant_id = $2::uuid AND vault_id = $3",
                link_id,
                tenant_id,
                vault_id,
            )
        return result.endswith("1")

    async def add_connection(self, row: dict[str, Any]) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.vault_mcp
                    (id, tenant_id, vault_id, name, server_url, auth_type, token_name, status, last_used, created_at, created_by)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                row["id"],
                row["tenant_id"],
                row["vault_id"],
                row["name"],
                row["server_url"],
                row["auth_type"],
                row.get("token_name"),
                row["status"],
                row["last_used"],
                row["created_at"],
                row["created_by"],
            )

    async def list_connections(self, tenant_id: str, vault_id: str) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, name, server_url, auth_type, token_name, status, last_used
                FROM tank.vault_mcp
                WHERE tenant_id = $1::uuid AND vault_id = $2
                ORDER BY created_at DESC
                """,
                tenant_id,
                vault_id,
            )
        return [_connection_from_row(row) for row in rows]

    async def get_connection(self, tenant_id: str, vault_id: str, connection_id: str) -> dict[str, Any] | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, name, token_name FROM tank.vault_mcp
                WHERE id = $1::uuid AND tenant_id = $2::uuid AND vault_id = $3
                """,
                connection_id,
                tenant_id,
                vault_id,
            )
        if row is None:
            return None
        return {"id": str(row["id"]), "name": row["name"], "token_name": row["token_name"]}

    async def delete_connection(self, tenant_id: str, vault_id: str, connection_id: str) -> bool:
        async with self._pool().acquire() as conn:
            result = await conn.execute(
                "DELETE FROM tank.vault_mcp WHERE id = $1::uuid AND tenant_id = $2::uuid AND vault_id = $3",
                connection_id,
                tenant_id,
                vault_id,
            )
        return result.endswith("1")

    async def add_audit(self, row: dict[str, Any]) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.vault_audit (tenant_id, vault_id, actor, action, item_kind, item_name, detail)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
                """,
                row["tenant_id"],
                row["vault_id"],
                row["actor"],
                row["action"],
                row["item_kind"],
                row["item_name"],
                row["detail"],
            )

    async def list_audit(self, vault_id: str, limit: int) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT ts, tenant_id, vault_id, actor, action, item_kind, item_name, detail
                FROM tank.vault_audit
                WHERE vault_id = $1
                ORDER BY ts DESC
                LIMIT $2
                """,
                vault_id,
                limit,
            )
        return [
            {
                "ts": row["ts"],
                "tenant_id": str(row["tenant_id"]),
                "vault_id": row["vault_id"],
                "actor": row["actor"],
                "action": row["action"],
                "item_kind": row["item_kind"],
                "item_name": row["item_name"],
                "detail": row["detail"],
            }
            for row in rows
        ]

    async def upsert_library_skill(self, row: dict[str, Any]) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.library_skill
                    (tenant_id, skill_id, version, agent, description, published_by, published_at)
                VALUES ($1::uuid, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (tenant_id, skill_id, version) DO UPDATE
                SET agent = EXCLUDED.agent, description = EXCLUDED.description,
                    published_by = EXCLUDED.published_by, published_at = EXCLUDED.published_at
                """,
                row["tenant_id"],
                row["skill_id"],
                row["version"],
                row["agent"],
                row["description"],
                row["published_by"],
                row["published_at"],
            )

    async def get_library_skill(self, tenant_id: str, skill_id: str, version: str) -> dict[str, Any] | None:
        async with self._pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT skill_id, version, agent, description, published_at
                FROM tank.library_skill
                WHERE tenant_id = $1::uuid AND skill_id = $2 AND version = $3
                """,
                tenant_id,
                skill_id,
                version,
            )
        if row is None:
            return None
        return {
            "skill_id": row["skill_id"],
            "version": row["version"],
            "agent": row["agent"],
            "description": row["description"],
            "published_at": row["published_at"],
        }

    async def list_library_skills(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT skill_id, version, agent, description, published_at
                FROM tank.library_skill
                WHERE tenant_id = $1::uuid
                ORDER BY skill_id, version
                """,
                tenant_id,
            )
        return [_public_library_skill(dict(row)) for row in rows]

    async def add_library_link(self, row: dict[str, Any]) -> None:
        async with self._pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tank.library_link
                    (id, tenant_id, squad, vault_id, skill_id, version, created_by, created_at)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $7, $8)
                """,
                row["id"],
                row["tenant_id"],
                row["squad"],
                row["vault_id"],
                row["skill_id"],
                row["version"],
                row["created_by"],
                row["created_at"],
            )

    async def list_library_links(self, tenant_id: str, squad: str) -> list[dict[str, Any]]:
        async with self._pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, squad, vault_id, skill_id, version, created_at
                FROM tank.library_link
                WHERE tenant_id = $1::uuid AND squad = $2
                ORDER BY created_at DESC
                """,
                tenant_id,
                squad,
            )
        return [
            _public_library_link(
                {
                    "id": str(row["id"]),
                    "squad": row["squad"],
                    "vault_id": row["vault_id"],
                    "skill_id": row["skill_id"],
                    "version": row["version"],
                    "created_at": row["created_at"],
                }
            )
            for row in rows
        ]


def _connection_from_row(row: Any) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "server_url": row["server_url"],
        "auth_type": row["auth_type"],
        "status": row["status"],
        "last_used": row["last_used"],
        "has_token": bool(row["token_name"]),
    }


class VaultService:
    def __init__(self, store: VaultStore, *, keys: Callable[[], bytes] | None = None) -> None:
        self.store = store
        self._keys = keys or master_key

    async def is_on(self, vault_id: str) -> bool:
        if vault_id == TANK_VAULT:
            return True
        if vault_id not in VAULT_SQUAD and vault_id != LIBRARY_VAULT:
            raise VaultError(404, "Unknown vault.")
        stored = await self.store.get_switch(vault_id)
        return bool(stored)

    def _gate(self, actor: Actor, vault_id: str, *, write: bool) -> None:
        if vault_id not in ALL_VAULTS:
            raise VaultError(404, "Unknown vault.")
        if vault_id == TANK_VAULT:
            if actor.kind == "tank":
                return
            raise VaultError(403, "tank.vault is not open to squads.")
        # library.vault's Plugins routes belong to Skala. Other squads use
        # link and transfer, which never open this vault's secrets.
        expected = LIBRARY_OWNER if vault_id == LIBRARY_VAULT else VAULT_SQUAD[vault_id]
        if actor.kind == "agent":
            if actor.squad != expected:
                raise VaultError(403, "This squad cannot read that vault.")
            if write:
                raise VaultError(403, "Only a signed-in user can change Plugins.")
        elif actor.kind == "user":
            if actor.squad != expected or not actor.id:
                raise VaultError(403, "This squad cannot read that vault.")
        else:
            raise VaultError(403, "This squad cannot read that vault.")

    async def _require_on(self, vault_id: str) -> None:
        if not await self.is_on(vault_id):
            raise VaultOff()

    async def plugins(self, actor: Actor, vault_id: str, tenant_id: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=False)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        secrets = [
            row
            for row in await self.store.list_secrets(tenant_id, vault_id)
            if not str(row["name"]).startswith("mcp:")
        ]
        files = await self.store.list_files(tenant_id, vault_id)
        links = await self.store.list_links(tenant_id, vault_id)
        connections = await self.store.list_connections(tenant_id, vault_id)
        return _stamp(_plugins_body(vault_id, True, None, secrets, files, links, connections))

    async def save_secret(self, actor: Actor, vault_id: str, tenant_id: str, name: str, purpose: str, value: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        name = _clean_name(name)
        value = _clean_secret(value, name)
        purpose = _clean_purpose(purpose, value)
        nonce, ciphertext = seal(self._keys(), tenant_id, vault_id, name, value)
        action = await self.store.upsert_secret(
            {
                "tenant_id": tenant_id,
                "vault_id": vault_id,
                "name": name,
                "purpose": purpose,
                "nonce": nonce,
                "ciphertext": ciphertext,
                "mask": MASK,
                "created_at": _now(),
                "updated_at": _now(),
                "updated_by": actor.id,
            }
        )
        await self._audit(tenant_id, vault_id, actor.id, action, "secret", name, purpose, leaked=value)
        log.info("vault %s secret %s %s", vault_id, action, name)
        return {"ok": True, "replaced": action == "replace", "name": name, "mask": MASK}

    async def remove_secret(self, actor: Actor, vault_id: str, tenant_id: str, name: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        name = _clean_name(name)
        if not await self.store.delete_secret(tenant_id, vault_id, name):
            raise VaultError(404, "That key is not in this vault.")
        await self._audit(tenant_id, vault_id, actor.id, "remove", "secret", name, "")
        log.info("vault %s secret remove %s", vault_id, name)
        return {"ok": True}

    async def resolve(self, actor: Actor, vault_id: str, tenant_id: str, name: str) -> str | None:
        """Server-side read for a feed or for Tank itself. Squad lists never call this."""
        self._gate(actor, vault_id, write=False)
        await self._require_on(vault_id)
        tenant_id = PLATFORM_TENANT if vault_id == TANK_VAULT else _tenant(tenant_id)
        name = _clean_name(name)
        row = await self.store.get_secret(tenant_id, vault_id, name)
        if row is None:
            return None
        return open_secret(self._keys(), tenant_id, vault_id, name, row["nonce"], row["ciphertext"])

    async def platform_secret(self, name: str) -> str | None:
        """Tank's own read of tank.vault. There is no squad route to this."""
        return await self.resolve(Actor("tank", "tank", None), TANK_VAULT, PLATFORM_TENANT, name)

    async def add_file(self, actor: Actor, vault_id: str, tenant_id: str, filename: str, content: bytes) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        meta = inspect_upload(filename, content)
        row = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "vault_id": vault_id,
            "uploaded_at": _now(),
            "uploaded_by": actor.id,
            "content": content,
            **meta,
        }
        await self.store.add_file(row)
        await self._audit(tenant_id, vault_id, actor.id, "add", "file", meta["name"], meta["media_type"])
        log.info("vault %s file add %s", vault_id, meta["name"])
        return _dates(_public_file(row))

    async def remove_file(self, actor: Actor, vault_id: str, tenant_id: str, file_id: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        if not await self.store.delete_file(tenant_id, vault_id, file_id):
            raise VaultError(404, "That file is not in this vault.")
        await self._audit(tenant_id, vault_id, actor.id, "remove", "file", file_id, "")
        log.info("vault %s file remove %s", vault_id, file_id)
        return {"ok": True}

    async def add_link(self, actor: Actor, vault_id: str, tenant_id: str, url: str, label: str, frequency: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        url = _http_url(url)
        label = " ".join(label.split())[:120] or urlsplit(url).hostname or url
        frequency = _frequency(frequency)
        row = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "vault_id": vault_id,
            "url": url,
            "label": label,
            "frequency": frequency,
            "last_checked": None,
            "status": "not checked",
            "created_at": _now(),
            "created_by": actor.id,
        }
        await self.store.add_link(row)
        await self._audit(tenant_id, vault_id, actor.id, "add", "link", label, frequency)
        log.info("vault %s link add %s", vault_id, label)
        return _dates(_public_link(row))

    async def remove_link(self, actor: Actor, vault_id: str, tenant_id: str, link_id: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        if not await self.store.delete_link(tenant_id, vault_id, link_id):
            raise VaultError(404, "That link is not in this vault.")
        await self._audit(tenant_id, vault_id, actor.id, "remove", "link", link_id, "")
        return {"ok": True}

    async def add_connection(
        self,
        actor: Actor,
        vault_id: str,
        tenant_id: str,
        name: str,
        server_url: str,
        auth_type: str,
        token: str,
    ) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        name = _clean_name(name)
        server_url = _http_url(server_url)
        auth_type = _auth_type(auth_type)
        connection_id = str(uuid.uuid4())
        token_name = None
        if auth_type == "token":
            token = _clean_secret(token, name)
            token_name = f"mcp:{connection_id}"
            nonce, ciphertext = seal(self._keys(), tenant_id, vault_id, token_name, token)
            await self.store.upsert_secret(
                {
                    "tenant_id": tenant_id,
                    "vault_id": vault_id,
                    "name": token_name,
                    "purpose": f"MCP connection token for {name}",
                    "nonce": nonce,
                    "ciphertext": ciphertext,
                    "mask": MASK,
                    "created_at": _now(),
                    "updated_at": _now(),
                    "updated_by": actor.id,
                }
            )
            await self._audit(tenant_id, vault_id, actor.id, "add", "secret", token_name, "MCP connection token", leaked=token)
        row = {
            "id": connection_id,
            "tenant_id": tenant_id,
            "vault_id": vault_id,
            "name": name,
            "server_url": server_url,
            "auth_type": auth_type,
            "token_name": token_name,
            "status": "saved",
            "last_used": None,
            "created_at": _now(),
            "created_by": actor.id,
        }
        await self.store.add_connection(row)
        await self._audit(tenant_id, vault_id, actor.id, "add", "mcp", name, auth_type)
        log.info("vault %s mcp add %s", vault_id, name)
        return _dates(_public_connection(row))

    async def remove_connection(self, actor: Actor, vault_id: str, tenant_id: str, connection_id: str) -> dict[str, Any]:
        self._gate(actor, vault_id, write=True)
        await self._require_on(vault_id)
        tenant_id = _tenant(tenant_id)
        row = await self.store.get_connection(tenant_id, vault_id, connection_id)
        if row is None:
            raise VaultError(404, "That connection is not in this vault.")
        await self.store.delete_connection(tenant_id, vault_id, connection_id)
        token_name = row.get("token_name")
        if token_name:
            await self.store.delete_secret(tenant_id, vault_id, token_name)
            await self._audit(tenant_id, vault_id, actor.id, "remove", "secret", token_name, "")
        await self._audit(tenant_id, vault_id, actor.id, "remove", "mcp", row["name"], "")
        return {"ok": True}

    def _known_squad(self, actor: Actor) -> str:
        if actor.kind not in {"user", "agent"} or not actor.squad or actor.squad not in SQUAD_VAULTS:
            raise VaultError(403, "This squad cannot read that vault.")
        if actor.kind == "user" and not actor.id:
            raise VaultError(403, "This squad cannot read that vault.")
        return actor.squad

    def _own_vault(self, squad: str) -> str:
        vault_id = SQUAD_VAULTS.get(squad)
        if not vault_id or vault_id in {TANK_VAULT, LIBRARY_VAULT} or VAULT_SQUAD.get(vault_id) != squad:
            raise VaultError(403, "This squad cannot read that vault.")
        return vault_id

    def _skill_ref(self, skill_id: str, version: str) -> tuple[str, str]:
        skill = skill_id.strip()
        ver = version.strip()
        if not _SKILL_ID.match(skill) or not _SKILL_VERSION.match(ver):
            raise VaultError(400, "That skill is not in the library.")
        return skill, ver

    async def publish_library_skill(
        self,
        actor: Actor,
        skill_id: str,
        version: str,
        agent: str,
        description: str,
        state: str,
    ) -> dict[str, Any]:
        """Skala puts an approved skill in the library. Other squads cannot rewrite it."""
        if actor.kind != "user" or actor.squad != LIBRARY_OWNER or not actor.id:
            raise VaultError(403, "This squad cannot rewrite the library.")
        await self._require_on(LIBRARY_VAULT)
        if state != "approved":
            raise VaultError(400, "Only an approved skill can live in the library.")
        skill, ver = self._skill_ref(skill_id, version)
        agent_name = " ".join(str(agent).split())[:80]
        if not agent_name:
            raise VaultError(400, "Say which agent the skill belongs to.")
        text = " ".join(str(description).split())[:500]
        row = {
            "tenant_id": PLATFORM_TENANT,
            "skill_id": skill,
            "version": ver,
            "agent": agent_name,
            "description": text,
            "published_by": actor.id,
            "published_at": _now(),
        }
        await self.store.upsert_library_skill(row)
        await self._audit(PLATFORM_TENANT, LIBRARY_VAULT, actor.id, "add", "skill", f"{skill}@{ver}", agent_name)
        return _dates(_public_library_skill(row))

    async def library(self, actor: Actor, tenant_id: str) -> dict[str, Any]:
        squad = self._known_squad(actor)
        tenant_id = _tenant(tenant_id)
        if not await self.is_on(LIBRARY_VAULT):
            return {
                "vault": LIBRARY_VAULT,
                "enabled": False,
                "message": OFF_MESSAGE,
                "skills": [],
                "links": [],
            }
        skills = await self.store.list_library_skills(PLATFORM_TENANT)
        links = await self.store.list_library_links(tenant_id, squad)
        return {
            "vault": LIBRARY_VAULT,
            "enabled": True,
            "message": None,
            "skills": [_dates(row) for row in skills],
            "links": [_dates(row) for row in links],
        }

    async def link_library_skill(self, actor: Actor, tenant_id: str, skill_id: str, version: str) -> dict[str, Any]:
        """Point the caller's own vault at a library skill. Does not change the library."""
        squad = self._known_squad(actor)
        await self._require_on(LIBRARY_VAULT)
        tenant_id = _tenant(tenant_id)
        skill, ver = self._skill_ref(skill_id, version)
        own = self._own_vault(squad)
        held = await self.store.get_library_skill(PLATFORM_TENANT, skill, ver)
        if held is None:
            raise VaultError(404, "That skill is not in the library.")
        before = dict(held)
        row = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "squad": squad,
            "vault_id": own,
            "skill_id": skill,
            "version": ver,
            "created_by": actor.id,
            "created_at": _now(),
        }
        await self.store.add_library_link(row)
        after = await self.store.get_library_skill(PLATFORM_TENANT, skill, ver)
        if after is None or after.get("description") != before.get("description") or after.get("agent") != before.get("agent"):
            raise VaultError(403, "This squad cannot rewrite the library.")
        await self._audit(tenant_id, LIBRARY_VAULT, actor.id, "link", "skill", f"{skill}@{ver}", squad)
        return _dates(_public_library_link(row))

    async def transfer_library_skill(self, actor: Actor, tenant_id: str, skill_id: str, version: str) -> dict[str, Any]:
        """Copy an approved library skill into the caller's own vault. Nowhere else."""
        squad = self._known_squad(actor)
        await self._require_on(LIBRARY_VAULT)
        tenant_id = _tenant(tenant_id)
        skill, ver = self._skill_ref(skill_id, version)
        own = self._own_vault(squad)
        if not await self.is_on(own):
            raise VaultOff()
        held = await self.store.get_library_skill(PLATFORM_TENANT, skill, ver)
        if held is None:
            raise VaultError(404, "That skill is not in the library.")
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["skill_id", "version", "agent", "description"])
        writer.writerow([held["skill_id"], held["version"], held["agent"], held["description"]])
        content = buf.getvalue().encode()
        meta = inspect_upload(f"{skill}-{ver}.csv", content)
        file_row = {
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "vault_id": own,
            "uploaded_at": _now(),
            "uploaded_by": actor.id,
            "content": content,
            **meta,
        }
        await self.store.add_file(file_row)
        await self._audit(tenant_id, own, actor.id, "transfer", "skill", f"{skill}@{ver}", LIBRARY_VAULT)
        return {"ok": True, "vault": own, "file": _dates(_public_file(file_row))}

    async def set_switch(self, actor: Actor, vault_id: str, enabled: bool) -> dict[str, Any]:
        if actor.kind != "admin" or not actor.id:
            raise VaultError(404, "not found")
        if vault_id not in ALL_VAULTS:
            raise VaultError(404, "Unknown vault.")
        if vault_id == TANK_VAULT and not enabled:
            await self._audit(PLATFORM_TENANT, TANK_VAULT, actor.id, "switch", "switch", TANK_VAULT, "refused off")
            raise VaultError(400, "tank.vault stays on.")
        if vault_id != TANK_VAULT:
            await self.store.set_switch(vault_id, enabled, actor.id)
        detail = "on" if enabled else "off"
        await self._audit(PLATFORM_TENANT, vault_id, actor.id, "switch", "switch", vault_id, detail)
        log.info("vault %s switch %s", vault_id, detail)
        return {"vault": vault_id, "enabled": True if vault_id == TANK_VAULT else enabled}

    async def switches(self, actor: Actor) -> dict[str, Any]:
        if actor.kind != "admin":
            raise VaultError(404, "not found")
        rows = []
        for vault_id in ALL_VAULTS:
            rows.append(
                {
                    "vault": vault_id,
                    "squad": VAULT_SQUAD.get(vault_id),
                    "enabled": await self.is_on(vault_id),
                }
            )
        return {"vaults": rows}

    async def admin_save_platform_secret(self, actor: Actor, name: str, purpose: str, value: str) -> dict[str, Any]:
        if actor.kind != "admin":
            raise VaultError(404, "not found")
        name = _clean_name(name)
        value = _clean_secret(value, name)
        purpose = _clean_purpose(purpose, value)
        nonce, ciphertext = seal(self._keys(), PLATFORM_TENANT, TANK_VAULT, name, value)
        action = await self.store.upsert_secret(
            {
                "tenant_id": PLATFORM_TENANT,
                "vault_id": TANK_VAULT,
                "name": name,
                "purpose": purpose,
                "nonce": nonce,
                "ciphertext": ciphertext,
                "mask": MASK,
                "created_at": _now(),
                "updated_at": _now(),
                "updated_by": actor.id,
            }
        )
        await self._audit(PLATFORM_TENANT, TANK_VAULT, actor.id, action, "secret", name, purpose, leaked=value)
        log.info("vault %s secret %s %s", TANK_VAULT, action, name)
        return {"ok": True, "replaced": action == "replace", "name": name, "mask": MASK}

    async def admin_plugins(self, actor: Actor) -> dict[str, Any]:
        if actor.kind != "admin":
            raise VaultError(404, "not found")
        secrets = await self.store.list_secrets(PLATFORM_TENANT, TANK_VAULT)
        return _stamp(_plugins_body(TANK_VAULT, True, None, secrets, [], [], []))

    async def audit(self, actor: Actor, vault_id: str, limit: int = 100) -> dict[str, Any]:
        if actor.kind != "admin":
            raise VaultError(404, "not found")
        if vault_id not in ALL_VAULTS:
            raise VaultError(404, "Unknown vault.")
        rows = await self.store.list_audit(vault_id, max(1, min(limit, 200)))
        return {"vault": vault_id, "audit": [_dates(row) for row in rows]}

    async def _audit(
        self,
        tenant_id: str,
        vault_id: str,
        actor: str,
        action: str,
        kind: str,
        name: str,
        detail: str,
        *,
        leaked: str = "",
    ) -> None:
        if leaked and leaked in detail:
            detail = detail.replace(leaked, "")
        if leaked and leaked in name:
            name = "redacted"
        await self.store.add_audit(
            {
                "tenant_id": tenant_id,
                "vault_id": vault_id,
                "actor": actor,
                "action": action,
                "item_kind": kind,
                "item_name": name,
                "detail": detail,
                "ts": _now(),
            }
        )


def _plugins_body(
    vault_id: str,
    enabled: bool,
    message: str | None,
    secrets: list[dict[str, Any]],
    files: list[dict[str, Any]],
    links: list[dict[str, Any]],
    connections: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "vault": vault_id,
        "enabled": enabled,
        "message": message,
        "secrets": [_dates(row) for row in secrets],
        "files": [_dates(row) for row in files],
        "links": [_dates(row) for row in links],
        "connections": [_dates({key: value for key, value in row.items() if key != "token_name"}) for row in connections],
    }


def _dates(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        if key in _PRIVATE:
            continue
        out[key] = _iso(value) if isinstance(value, datetime) else value
    return out


def _stamp(body: dict[str, Any]) -> dict[str, Any]:
    return body


def off_payload(vault_id: str) -> dict[str, Any]:
    return {
        "vault": vault_id,
        "enabled": False,
        "message": OFF_MESSAGE,
        "secrets": [],
        "files": [],
        "links": [],
        "connections": [],
    }


_service: VaultService | None = None


def install_store(store: VaultStore, *, keys: Callable[[], bytes] | None = None) -> VaultService:
    global _service
    _service = VaultService(store, keys=keys)
    return _service


def current_service() -> VaultService:
    if _service is None:
        raise VaultError(503, "Plugins storage is not ready.")
    return _service


async def apply_lab_dev_fixture(service: VaultService, admin_id: str = "dev-fixture") -> None:
    """Turn lab.vault on so Market Lab's Plugins tab can be exercised.

    Production startup does not call this. The other squad vaults stay off.
    """
    await service.set_switch(Actor("admin", admin_id, None), "lab.vault", True)


router = APIRouter()


def _admin_actor(request: Request) -> Actor:
    user_id = request.headers.get("x-tervory-admin", "")
    if not founder_ok(request.headers.get("x-tank-key", ""), user_id):
        raise HTTPException(status_code=404, detail="not found")
    return Actor("admin", user_id.strip(), None)


def _actor(request: Request) -> Actor:
    matched = match_caller(request.headers.get("x-tank-key", ""))
    if matched is None:
        raise HTTPException(status_code=401, detail="missing or invalid X-Tank-Key")
    kind, agent = matched
    if kind == "agent":
        return Actor("agent", agent, agent)
    user_id = request.headers.get("x-tervory-user", "").strip()
    squad = request.headers.get("x-tervory-squad", "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    if squad not in SQUAD_VAULTS:
        raise HTTPException(status_code=403, detail="This squad cannot read that vault.")
    return Actor("user", user_id, squad)


async def _json(request: Request) -> dict[str, Any]:
    raw = await request.body()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="The request could not be read.") from None
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="The request could not be read.")
    return parsed


def _http(exc: VaultError) -> HTTPException:
    return HTTPException(status_code=exc.status, detail=exc.message)


def _tenant_of(request: Request, body: dict[str, Any] | None = None) -> str:
    raw = request.query_params.get("tenant_id") or (body or {}).get("tenant_id") or ""
    return str(raw)


@router.get("/v1/vaults/{vault_id}/plugins")
async def list_plugins(vault_id: str, request: Request) -> dict[str, Any]:
    try:
        return await current_service().plugins(_actor(request), vault_id, _tenant_of(request))
    except VaultOff:
        return off_payload(vault_id)
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/{vault_id}/secrets")
async def post_secret(vault_id: str, request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().save_secret(
            _actor(request),
            vault_id,
            _tenant_of(request, body),
            str(body.get("name") or ""),
            str(body.get("purpose") or ""),
            str(body.get("value") or ""),
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.delete("/v1/vaults/{vault_id}/secrets")
async def delete_secret(vault_id: str, request: Request) -> dict[str, Any]:
    try:
        return await current_service().remove_secret(
            _actor(request),
            vault_id,
            _tenant_of(request),
            request.query_params.get("name") or "",
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/{vault_id}/secrets/resolve")
async def resolve_secret(vault_id: str, request: Request) -> dict[str, Any]:
    """Server-only. Agents and the Workspace server use this for a feed. The browser must not."""
    body = await _json(request)
    try:
        value = await current_service().resolve(
            _actor(request),
            vault_id,
            _tenant_of(request, body),
            str(body.get("name") or ""),
        )
    except VaultOff:
        return {"found": False}
    except VaultError as exc:
        raise _http(exc) from None
    if value is None:
        return {"found": False}
    return {"found": True, "value": value}


@router.post("/v1/vaults/{vault_id}/files")
async def post_files(vault_id: str, request: Request) -> dict[str, Any]:
    form = await request.form()
    uploads = form.getlist("file")
    if not uploads:
        raise HTTPException(status_code=400, detail="Choose a CSV, XLSX, or PDF file. Nothing was saved.")
    if len(uploads) > 10:
        raise HTTPException(status_code=400, detail="Upload up to 10 files at a time. Nothing was saved.")
    saved: list[dict[str, Any]] = []
    try:
        actor = _actor(request)
        tenant_id = _tenant_of(request)
        service = current_service()
        for item in uploads:
            filename = getattr(item, "filename", "") or ""
            content = await item.read()
            saved.append(await service.add_file(actor, vault_id, tenant_id, filename, content))
    except VaultError as exc:
        raise _http(exc) from None
    return {"ok": True, "files": saved}


@router.delete("/v1/vaults/{vault_id}/files/{file_id}")
async def delete_file(vault_id: str, file_id: str, request: Request) -> dict[str, Any]:
    try:
        return await current_service().remove_file(_actor(request), vault_id, _tenant_of(request), file_id)
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/{vault_id}/links")
async def post_link(vault_id: str, request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().add_link(
            _actor(request),
            vault_id,
            _tenant_of(request, body),
            str(body.get("url") or ""),
            str(body.get("label") or ""),
            str(body.get("frequency") or ""),
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.delete("/v1/vaults/{vault_id}/links/{link_id}")
async def delete_link(vault_id: str, link_id: str, request: Request) -> dict[str, Any]:
    try:
        return await current_service().remove_link(_actor(request), vault_id, _tenant_of(request), link_id)
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/{vault_id}/connections")
async def post_connection(vault_id: str, request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().add_connection(
            _actor(request),
            vault_id,
            _tenant_of(request, body),
            str(body.get("name") or ""),
            str(body.get("server_url") or ""),
            str(body.get("auth_type") or ""),
            str(body.get("token") or ""),
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.delete("/v1/vaults/{vault_id}/connections/{connection_id}")
async def delete_connection(vault_id: str, connection_id: str, request: Request) -> dict[str, Any]:
    try:
        return await current_service().remove_connection(_actor(request), vault_id, _tenant_of(request), connection_id)
    except VaultError as exc:
        raise _http(exc) from None


@router.get("/v1/vaults/library.vault/skills")
async def list_library_skills(request: Request) -> dict[str, Any]:
    try:
        return await current_service().library(_actor(request), _tenant_of(request))
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/library.vault/skills")
async def post_library_skill(request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().publish_library_skill(
            _actor(request),
            str(body.get("skill_id") or ""),
            str(body.get("version") or ""),
            str(body.get("agent") or ""),
            str(body.get("description") or ""),
            str(body.get("state") or ""),
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/library.vault/skills/{skill_id}/{version}/link")
async def post_library_link(skill_id: str, version: str, request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().link_library_skill(
            _actor(request), _tenant_of(request, body), skill_id, version
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/vaults/library.vault/skills/{skill_id}/{version}/transfer")
async def post_library_transfer(skill_id: str, version: str, request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().transfer_library_skill(
            _actor(request), _tenant_of(request, body), skill_id, version
        )
    except VaultError as exc:
        raise _http(exc) from None


@router.get("/v1/admin/vaults")
async def admin_list(request: Request) -> dict[str, Any]:
    try:
        return await current_service().switches(_admin_actor(request))
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/admin/vaults/{vault_id}/switch")
async def admin_switch(vault_id: str, request: Request) -> dict[str, Any]:
    body = await _json(request)
    if "enabled" not in body or not isinstance(body["enabled"], bool):
        raise HTTPException(status_code=400, detail="Say whether the vault is on.")
    try:
        return await current_service().set_switch(_admin_actor(request), vault_id, body["enabled"])
    except VaultError as exc:
        raise _http(exc) from None


@router.get("/v1/admin/vaults/{vault_id}/audit")
async def admin_audit(vault_id: str, request: Request) -> dict[str, Any]:
    try:
        limit = int(request.query_params.get("limit") or "100")
    except ValueError:
        limit = 100
    try:
        return await current_service().audit(_admin_actor(request), vault_id, limit)
    except VaultError as exc:
        raise _http(exc) from None


@router.get("/v1/admin/vaults/tank.vault/plugins")
async def admin_tank_plugins(request: Request) -> dict[str, Any]:
    try:
        return await current_service().admin_plugins(_admin_actor(request))
    except VaultError as exc:
        raise _http(exc) from None


@router.post("/v1/admin/vaults/tank.vault/secrets")
async def admin_tank_secret(request: Request) -> dict[str, Any]:
    body = await _json(request)
    try:
        return await current_service().admin_save_platform_secret(
            _admin_actor(request),
            str(body.get("name") or ""),
            str(body.get("purpose") or ""),
            str(body.get("value") or ""),
        )
    except VaultError as exc:
        raise _http(exc) from None
