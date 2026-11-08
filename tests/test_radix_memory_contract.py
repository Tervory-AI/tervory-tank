"""Historical Radix leak regressions now exercise the integrated real Hermes SQL app."""
from __future__ import annotations

import hashlib
import math
import os
import subprocess
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
SOURCE = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
from gates78.conftest import gate78_database, gate78_memory, sql_memory
__all__ = ["gate78_database", "gate78_memory", "sql_memory"]

TENANT_A = str(uuid4())
TENANT_B = str(uuid4())
USER_A = "placeholder-user-a"
USER_B = "placeholder-user-b"
RADIX_KEY = "placeholder-radix-agent-key"
OTHER_AGENT_KEY = "placeholder-other-agent-key"
PLACEHOLDER_WORKSPACE_KEY = "placeholder-workspace-key"

HERMES_AUTH_HEADER = "X-Tank-Key"
HERMES_AGENT_KEY_ENV_PREFIX = "TANK_KEY_"
HERMES_PLACEHOLDER_WORKSPACE_KEY_ENV = "TANK_API_KEY"


class StubEmbedder:
    def embed(self, text: str) -> list[float]:
        if text.startswith("alpha near"):
            return [0.98, math.sqrt(max(0.0, 1.0 - 0.98 * 0.98)), 0.0, 0.0]
        digest = hashlib.sha256(text.encode()).digest()
        vals = [((digest[i] / 255.0) * 2) - 1 for i in range(4)]
        norm = math.sqrt(sum(v * v for v in vals)) or 1.0
        return [v / norm for v in vals]


def _install_key_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith("TANK_KEY_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TANK_KEY_RADIX", RADIX_KEY)
    monkeypatch.setenv("TANK_KEY_TIGER", OTHER_AGENT_KEY)
    monkeypatch.setenv("TANK_API_KEY", PLACEHOLDER_WORKSPACE_KEY)
    monkeypatch.setenv("HERMES_URL", "http://hermes-contract-test")
    monkeypatch.setenv("TANK_KEY", RADIX_KEY)
    monkeypatch.setenv("AGENT_NAME", "radix")


@pytest_asyncio.fixture
async def current_stack(monkeypatch, gate78_memory):
    from chassis.memory import MemoryClient
    stack = await gate78_memory("radix")
    _install_key_env(monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=stack.app), base_url="http://hermes-contract-test") as http:
        client = MemoryClient(base_url="http://hermes-contract-test", api_key=RADIX_KEY, agent="radix", http=http)
        yield {"label": "CURRENT SOURCE", "client": client, "http": http, "MemoryClient": MemoryClient, "app": stack.app}


@pytest_asyncio.fixture
async def patched_stack(current_stack):
    # Retain the historical regression cases against integrated SQL, without patching code.
    return {**current_stack, "label": "INTEGRATED"}


@pytest.mark.asyncio
async def test_CURRENT_write_recall_forget_own_key(current_stack):
    s = current_stack
    assert s["label"] == "CURRENT SOURCE"
    client = s["client"]
    saved = await client.remember(
        TENANT_A, "alpha finding", "radix.finding", "radix:task:x",
        user_id=USER_A, meta={"task_key": "x"},
    )
    assert saved.get("id")
    recalled = await client.recall(TENANT_A, "alpha", kind="radix.finding", limit=8, user_id=USER_A)
    assert any(r.get("id") == saved["id"] for r in recalled)
    await client.forget(saved["id"], TENANT_A, user_id=USER_A)
    after = await client.recall(TENANT_A, "alpha", kind="radix.finding", limit=8, user_id=USER_A)
    assert all(r.get("id") != saved["id"] for r in after)


@pytest.mark.asyncio
async def test_CURRENT_own_key_only_wrong_agent_and_workspace_refused(current_stack):
    s = current_stack
    http = s["http"]
    MemoryClient = s["MemoryClient"]
    # Other agent key cannot write into radix's collection by naming agent=radix.
    cross = await http.post(
        "/memories",
        headers={HERMES_AUTH_HEADER: OTHER_AGENT_KEY},
        json={
            "tenant_id": TENANT_A,
            "text": "nope",
            "kind": "radix.finding",
            "source": "radix:task:x",
            "agent": "radix",
            "meta": {"user_id": USER_A},
        },
    )
    assert cross.status_code == 403, cross.text
    shared = await http.post(
        "/memories",
        headers={HERMES_AUTH_HEADER: PLACEHOLDER_WORKSPACE_KEY},
        json={
            "tenant_id": TENANT_A,
            "text": "nope",
            "kind": "radix.finding",
            "source": "radix:task:x",
            "meta": {"user_id": USER_A},
        },
    )
    assert shared.status_code == 403, shared.text
    workspace = MemoryClient(
        base_url="http://hermes-contract-test",
        api_key=PLACEHOLDER_WORKSPACE_KEY,
        agent="radix",
        http=http,
    )
    with pytest.raises(RuntimeError):
        await workspace.remember(
            TENANT_A, "nope", "radix.finding", "radix:task:workspace",
            user_id=USER_A,
        )


@pytest.mark.asyncio
async def test_CURRENT_bad_kind_and_tenant_scope(current_stack):
    s = current_stack
    http = s["http"]
    client = s["client"]
    bad_kind = await http.post(
        "/memories",
        headers={HERMES_AUTH_HEADER: RADIX_KEY},
        json={
            "tenant_id": TENANT_A,
            "text": "x",
            "kind": "BAD KIND",
            "source": "radix:task:x",
            "meta": {"user_id": USER_A},
        },
    )
    assert bad_kind.status_code == 422
    await client.remember(
        TENANT_A, "tenant-a only", "radix.finding", "radix:task:a",
        user_id=USER_A, meta={"task_key": "a"},
    )
    other = await client.recall(TENANT_B, "tenant-a", kind="radix.finding", limit=8, user_id=USER_A)
    assert other == []


@pytest.mark.asyncio
async def test_CURRENT_user_id_not_centrally_filtered(current_stack):
    """Retain the original leak regression; the integrated app must now isolate users."""
    s = current_stack
    assert s["label"] == "CURRENT SOURCE"
    client = s["client"]
    await client.remember(
        TENANT_A, "personal A finding", "radix.finding", "radix:task:a",
        user_id=USER_A, meta={"task_key": "a"},
    )
    await client.remember(
        TENANT_A, "personal B finding", "radix.finding", "radix:task:b",
        user_id=USER_B, meta={"task_key": "b"},
    )
    # The original same-tenant leak reproducer must now prove SQL owner isolation.
    for user in (USER_A, USER_B):
        recalled = await client.recall(TENANT_A, "personal", kind="radix.finding", limit=20, user_id=user)
        assert recalled
        assert {(row.get("meta") or {}).get("user_id") for row in recalled} == {user}



@pytest.mark.asyncio
async def test_UNAPPLIED_two_users_personal_isolation_and_tenant_wide(patched_stack):
    """Historical proposal cases now require isolation from integrated Hermes SQL."""
    s = patched_stack
    assert s["label"] == "INTEGRATED"
    client = s["client"]
    wide = ["heartbeat"]
    saved_a = await client.remember(
        TENANT_A, "personal A unique-quartz-nebula", "radix.finding", "radix:task:a",
        user_id=USER_A, meta={"task_key": "a"},
    )
    saved_b = await client.remember(
        TENANT_A, "personal B unique-onyx-cascade", "radix.finding", "radix:task:b",
        user_id=USER_B, meta={"task_key": "b"},
    )
    assert saved_a.get("id") and saved_b.get("id")
    only_a = await client.recall(
        TENANT_A, "unique", limit=16, user_id=USER_A,
    )
    only_b = await client.recall(
        TENANT_A, "unique", limit=16, user_id=USER_B,
    )
    assert only_a and all(
        str((r.get("meta") or {}).get("user_id")) == USER_A or r.get("kind") in wide
        for r in only_a
    )
    assert only_b and all(
        str((r.get("meta") or {}).get("user_id")) == USER_B or r.get("kind") in wide
        for r in only_b
    )
    assert all(
        str((r.get("meta") or {}).get("user_id")) != USER_B
        for r in only_a if r.get("kind") not in wide
    )
    assert all(
        str((r.get("meta") or {}).get("user_id")) != USER_A
        for r in only_b if r.get("kind") not in wide
    )
    notice = await client.remember(
        TENANT_A, "tenant-notice-unique-shared-bulletin", "heartbeat",
        "radix:task:notice", user_id=None, tenant_wide=True, meta={"task_key": "notice"},
    )
    assert notice.get("id")
    for user in (USER_A, USER_B):
        rows = await client.recall(
            TENANT_A, "shared-bulletin", limit=16, user_id=user,
        )
        assert any(r.get("kind") == "heartbeat" for r in rows)
    with pytest.raises((ValueError, RuntimeError, httpx.HTTPError)):
        await client.remember(
            TENANT_A, "missing-user", "radix.finding", "radix:task:missing",
            user_id=None, meta={"task_key": "missing"},
        )
    assert await client.recall(
        TENANT_B, "unique", limit=8, user_id=USER_A,
    ) == []


@pytest.mark.asyncio
async def test_UNAPPLIED_wrong_key_refused_and_bad_kind(patched_stack):
    s = patched_stack
    http = s["http"]
    cross = await http.post(
        "/memories",
        headers={HERMES_AUTH_HEADER: OTHER_AGENT_KEY},
        json={
            "tenant_id": TENANT_A,
            "text": "nope",
            "kind": "radix.finding",
            "source": "radix:task:x",
            "agent": "radix",
            "user_id": USER_A,
            "meta": {},
        },
    )
    assert cross.status_code == 403, cross.text
    bad_kind = await http.post(
        "/memories",
        headers={HERMES_AUTH_HEADER: RADIX_KEY},
        json={
            "tenant_id": TENANT_A,
            "text": "x",
            "kind": "BAD KIND!",
            "source": "radix:task:x",
            "user_id": USER_A,
            "meta": {},
        },
    )
    assert bad_kind.status_code == 422


def test_pinned_source_sha_reported():
    assert len(SOURCE) == 40 and all(c in "0123456789abcdef" for c in SOURCE)


def test_product_never_calls_tank_v1_memory_any_method():
    root = ROOT / "agents" / "radix"
    for path in root.rglob("*.py"):
        body = path.read_text()
        assert "/v1/memory" not in body, path


@pytest.mark.asyncio
async def test_integrated_memory_routes_use_existing_signed_identity(monkeypatch):
    from fastapi import FastAPI
    import radix_memory_routes
    from unittest.mock import AsyncMock
    app = FastAPI()
    app.include_router(radix_memory_routes.build_router())
    transport = AsyncMock(side_effect=AssertionError("Unsigned request must never reach the room"))
    monkeypatch.setattr(radix_memory_routes, "call_room", transport)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        for method, suffix, body in [("GET", "", None), ("POST", "/control", {"control": "off"}),
                ("POST", "/edit", {"memory_id": str(uuid4()), "text": "placeholder"}),
                ("POST", "/forget", {"memory_id": str(uuid4())})]:
            response = await client.request(method, "/v1/radix/memory" + suffix, json=body,
                headers={"X-Tervory-User": USER_A, "X-Tenant-ID": TENANT_A})
            assert response.status_code in {401, 403}, response.text
    transport.assert_not_called()
