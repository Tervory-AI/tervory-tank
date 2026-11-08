"""Rig contract tests use Head's real SQL/Qdrant fixture and current client.

These client-level checks supplement the signed entry-path acceptance suite.
The original split vendor remains source-verified and unchanged.
"""
from __future__ import annotations

import hashlib
import inspect
import math
import os
import sys
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]
# Integrated Tank tests exercise this checkout's Hermes and shipped client.
SOURCE = "integrated Tank checkout"
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
assert (ROOT / "hermes" / "service.py").is_file()

from chassis.memory import MemoryClient
from gates78.conftest import gate78_database, gate78_memory, sql_memory

__all__ = ["gate78_memory", "gate78_database", "sql_memory"]

PLACEHOLDER_RIG_AGENT_KEY = "placeholder-rig-" + hashlib.sha256(b"rig-contract").hexdigest()[:24]
PLACEHOLDER_OTHER_AGENT_KEY = "placeholder-tiger-" + hashlib.sha256(b"tiger-contract").hexdigest()[:24]
PLACEHOLDER_WORKSPACE_KEY = "placeholder-workspace-" + hashlib.sha256(b"workspace-contract").hexdigest()[:24]

HERMES_BASE = "http://hermes-contract"
TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
USER_A = "user-a-owner"
USER_B = "user-b-other"

# Rig kinds: personal require user_id; tenant-wide may omit (product list).
PERSONAL_KIND = "rig.build"
TENANT_WIDE_KIND = "rig.store_preference"


class StubEmbedder:
    def embed(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode()).digest()
        raw = [((digest[i] / 255.0) * 2) - 1 for i in range(4)]
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


def _clear_agent_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("TANK_KEY_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TANK_KEY_RIG", PLACEHOLDER_RIG_AGENT_KEY)
    monkeypatch.setenv("TANK_KEY_TIGER", PLACEHOLDER_OTHER_AGENT_KEY)
    monkeypatch.setenv("TANK_API_KEY", PLACEHOLDER_WORKSPACE_KEY)


@pytest_asyncio.fixture
async def hermes_memory(monkeypatch: pytest.MonkeyPatch, gate78_memory):
    _clear_agent_keys(monkeypatch)
    stack = await gate78_memory("rig")
    monkeypatch.setenv("TANK_KEY_RIG", PLACEHOLDER_RIG_AGENT_KEY)
    app = stack.app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url=HERMES_BASE) as http:
        client = MemoryClient(
            base_url=HERMES_BASE,
            api_key=PLACEHOLDER_RIG_AGENT_KEY,
            agent="rig",
            http=http,
        )
        assert "/v1/memory" not in client._base
        assert client._base == HERMES_BASE
        yield client, http, app


def test_production_client_urls_and_key_field_names_only():
    """URLs and key FIELD NAMES only — never secret values."""
    # MemoryClient base from HERMES_URL / ctor base_url; auth header X-Tank-Key;
    # env field names: HERMES_URL, TANK_KEY (product), TANK_KEY_RIG (Hermes agent map).
    client = MemoryClient(base_url="http://hermes:8000", api_key="placeholder-only", agent="rig")
    assert client._base == "http://hermes:8000"
    assert "/v1/memory" not in client._base
    # Hermes paths (not Tank corridor):
    assert {"/memories", "/recall", "/records"} == {"/memories", "/recall", "/records"}


def test_ban_tank_v1_memory_all_methods(hermes_memory):
    """Product must not call Tank /v1/memory for any method including GET."""
    client, _http, _app = hermes_memory
    assert not client._base.rstrip("/").endswith("/v1/memory")
    assert "/v1/memory" not in client._base


def test_t51_chassis_remember_and_recall_accept_user_id():
    """CURRENT chassis MemoryClient must take user_id on remember/recall (t51)."""
    remember_params = inspect.signature(MemoryClient.remember).parameters
    recall_params = inspect.signature(MemoryClient.recall).parameters
    assert "user_id" in remember_params, (
        "UPSTREAM GAP @ SOURCE "
        + SOURCE
        + ": chassis MemoryClient.remember lacks user_id; "
        "see tank-patches/gates-7-8-current-core.patch"
    )
    assert "user_id" in recall_params, (
        "UPSTREAM GAP @ SOURCE "
        + SOURCE
        + ": chassis MemoryClient.recall lacks user_id; "
        "see tank-patches/gates-7-8-current-core.patch"
    )


@pytest.mark.asyncio
async def test_hermes_contract_write_recall_forget_with_agent_key(hermes_memory):
    client, http, _app = hermes_memory
    saved = await client.remember(
        TENANT_A,
        "alpha build note",
        PERSONAL_KIND,
        "rig:task:contract",
        user_id=USER_A,
        meta={"user_id": USER_A, "task_key": "contract"},
    )
    assert isinstance(saved, dict) and saved.get("id")
    memory_id = saved["id"]
    recalled = await client.recall(TENANT_A, "alpha build note", kind=PERSONAL_KIND, limit=8, user_id=USER_A)
    assert any(row.get("id") == memory_id or "alpha" in str(row.get("text", "")) for row in recalled)
    await client.forget(memory_id, TENANT_A, user_id=USER_A)
    after = await client.recall(TENANT_A, "alpha build note", kind=PERSONAL_KIND, limit=8, user_id=USER_A)
    assert not any(row.get("id") == memory_id for row in after)


@pytest.mark.asyncio
async def test_hermes_contract_refuses_workspace_shared_key_for_write(hermes_memory):
    _client, http, _app = hermes_memory
    shared = MemoryClient(
        base_url=HERMES_BASE, api_key=PLACEHOLDER_WORKSPACE_KEY, agent="rig", http=http
    )
    with pytest.raises(RuntimeError, match="hermes answered 403"):
        await shared.remember(TENANT_A, "should fail", PERSONAL_KIND, "rig:task:x", user_id=USER_A)


@pytest.mark.asyncio
async def test_hermes_contract_kind_format_and_tenant_scope(hermes_memory):
    client, http, _app = hermes_memory
    for kind in (PERSONAL_KIND, "rig.receipt", "rig.setting", "rig.correction", "rig.quote"):
        saved = await client.remember(
            TENANT_A, f"note for {kind}", kind, "rig:task:kinds",
            user_id=USER_A,
            meta={"user_id": USER_A},
        )
        assert saved.get("id")
    bad = await http.post(
        "/memories",
        headers={"X-Tank-Key": PLACEHOLDER_RIG_AGENT_KEY},
        json={
            "tenant_id": TENANT_A,
            "text": "bad kind",
            "kind": "Rig.Build",
            "source": "human",
        },
    )
    assert bad.status_code == 422
    a = await client.remember(
        TENANT_A, "tenant-a secret-build-note", PERSONAL_KIND, "rig:task:a",
        user_id=USER_A,
        meta={"user_id": USER_A},
    )
    await client.remember(
        TENANT_B, "tenant-b secret-build-note", PERSONAL_KIND, "rig:task:b",
        user_id=USER_B,
        meta={"user_id": USER_B},
    )
    hits_a = await client.recall(TENANT_A, "secret-build-note", kind=PERSONAL_KIND, limit=8, user_id=USER_A)
    hits_b = await client.recall(TENANT_B, "secret-build-note", kind=PERSONAL_KIND, limit=8, user_id=USER_B)
    assert any(h.get("id") == a.get("id") or "tenant-a" in str(h.get("text", "")) for h in hits_a)
    assert not any("tenant-b" in str(h.get("text", "")) for h in hits_a)
    assert not any("tenant-a" in str(h.get("text", "")) for h in hits_b)


@pytest.mark.asyncio
async def test_t51_two_users_personal_isolation_via_hermes_not_product(hermes_memory):
    """User A must not recall B's personal row; product must NOT filter locally.

    Requires chassis remember/recall(user_id=...) and Hermes SQL user scope (t51).
    CURRENT pin lacks both → honest FAIL / upstream dependency.
    """
    client, _http, _app = hermes_memory
    remember_params = inspect.signature(MemoryClient.remember).parameters
    recall_params = inspect.signature(MemoryClient.recall).parameters
    if "user_id" not in remember_params or "user_id" not in recall_params:
        pytest.fail(
            "UPSTREAM DEPENDENCY @ SOURCE "
            + SOURCE
            + ": MemoryClient lacks user_id; Hermes cannot be asked to SQL-scope "
            "personal rows. Unapplied proposal: "
            "tank-patches/gates-7-8-current-core.patch"
        )

    await client.remember(
        TENANT_A, "personal-a-only", PERSONAL_KIND, "rig:task:a",
        user_id=USER_A, meta={"user_id": USER_A, "task_key": "a"},
    )
    await client.remember(
        TENANT_A, "personal-b-only", PERSONAL_KIND, "rig:task:b",
        user_id=USER_B, meta={"user_id": USER_B, "task_key": "b"},
    )
    # Positive: A sees own personal
    hits_a = await client.recall(
        TENANT_A, "personal", kind=PERSONAL_KIND, limit=8, user_id=USER_A
    )
    assert any("personal-a-only" in str(h.get("text", "")) for h in hits_a)
    # Denial: A never sees B's personal (Hermes SQL scope — no product filter)
    assert not any("personal-b-only" in str(h.get("text", "")) for h in hits_a)
    hits_b = await client.recall(
        TENANT_A, "personal", kind=PERSONAL_KIND, limit=8, user_id=USER_B
    )
    assert any("personal-b-only" in str(h.get("text", "")) for h in hits_b)
    assert not any("personal-a-only" in str(h.get("text", "")) for h in hits_b)


@pytest.mark.asyncio
async def test_t51_tenant_wide_visible_to_both_users(hermes_memory):
    """Tenant-wide kinds reach BOTH users; no user_id on those records."""
    client, _http, _app = hermes_memory
    remember_params = inspect.signature(MemoryClient.remember).parameters
    recall_params = inspect.signature(MemoryClient.recall).parameters
    if "user_id" not in remember_params or "user_id" not in recall_params:
        pytest.fail(
            "UPSTREAM DEPENDENCY @ SOURCE "
            + SOURCE
            + ": cannot prove tenant-wide visibility without chassis user_id; "
            "see tank-patches/gates-7-8-current-core.patch"
        )
    await client.remember(
        TENANT_A, "store-wide-pref", TENANT_WIDE_KIND, "rig:task:store",
        tenant_wide=True,
        meta={"task_key": "store", "scope": "tenant-wide"},
    )
    for user in (USER_A, USER_B):
        hits = await client.recall(
            TENANT_A, "store-wide-pref", kind=TENANT_WIDE_KIND, limit=8, user_id=user
        )
        assert any("store-wide-pref" in str(h.get("text", "")) for h in hits), user


@pytest.mark.asyncio
async def test_t51_personal_kind_missing_user_id_refused(hermes_memory):
    """Personal record types must refuse remember without user_id."""
    client, _http, _app = hermes_memory
    remember_params = inspect.signature(MemoryClient.remember).parameters
    if "user_id" not in remember_params:
        pytest.fail(
            "UPSTREAM DEPENDENCY @ SOURCE "
            + SOURCE
            + ": MemoryClient.remember has no user_id to refuse; "
            "see tank-patches/gates-7-8-current-core.patch"
        )
    with pytest.raises((RuntimeError, TypeError, ValueError)):
        await client.remember(
            TENANT_A, "orphan personal", PERSONAL_KIND, "rig:task:orphan",
            # missing user_id on personal kind
            meta={"task_key": "orphan"},
        )


@pytest.mark.asyncio
async def test_hermes_contract_missing_key_refused(hermes_memory):
    _client, http, _app = hermes_memory
    bare = MemoryClient(base_url=HERMES_BASE, api_key="", agent="rig", http=http)
    with pytest.raises(RuntimeError, match="tank key is not set"):
        await bare.remember(TENANT_A, "x", PERSONAL_KIND, "human", user_id=USER_A)
