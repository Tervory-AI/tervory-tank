"""List/records cross-user disclosure regressions (Opli-reported list gap).

Recall can be isolated while list still returns another user's personal rows.
These tests exercise HTTP /records → Records.list SQL and FakeMemory.records.
Personal HTTP calls carry the lifecycle-bound identity MemoryClient attaches.
"""
from __future__ import annotations

import httpx
import pytest

from hermes_lifecycle import personal_headers
from test_agent_memory_records import memory as memory_fixture, Encoder

memory = memory_fixture
KEY = "placeholder-agent-key"


async def _post_personal(client, tenant, text, kind, user, source):
    body = {
        "tenant_id": tenant,
        "text": text,
        "kind": kind,
        "source": source,
        "user_id": user,
        "meta": {"user_id": user},
    }
    headers, raw = personal_headers(KEY, "POST", "/memories", tenant=tenant, user=user, body=body)
    return await client.post("/memories", headers=headers, content=raw)


async def _get_records(client, tenant, user=None, **params):
    q = {"tenant_id": tenant, **params}
    if user is not None:
        q["user_id"] = user
        headers, _ = personal_headers(KEY, "GET", "/records", tenant=tenant, user=user)
    else:
        headers = {"X-Tank-Key": KEY}
    return await client.get("/records", headers=headers, params=q)


@pytest.mark.asyncio
async def test_http_list_two_users_one_tenant_never_leaks(memory, monkeypatch):
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    from hermes.user_scope import TENANT_WIDE_KINDS

    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), KEY)
    monkeypatch.setitem(TENANT_WIDE_KINDS, m.agent, frozenset({"placeholder.shared", "opli.repo_map"}))
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        a = (await _post_personal(client, m.tenant, "placeholder list-a", "placeholder.personal",
                                  "placeholder-user-a", "https://placeholder.example/a")).json()
        b = (await _post_personal(client, m.tenant, "placeholder list-b", "placeholder.personal",
                                  "placeholder-user-b", "https://placeholder.example/b")).json()
        shared = (await client.post("/memories", headers={"X-Tank-Key": KEY}, json={
            "tenant_id": m.tenant, "text": "placeholder list-shared", "kind": "placeholder.shared",
            "source": "https://placeholder.example/s",
        })).json()
        for i in range(25):
            await _post_personal(client, m.tenant, f"placeholder list-b-pad-{i}", "placeholder.personal",
                                 "placeholder-user-b", "https://placeholder.example/p")

        page = (await _get_records(client, m.tenant, "placeholder-user-a", limit=10, offset=0)).json()["memories"]
        ids = {row["id"] for row in page}
        owners = {(row.get("meta") or {}).get("user_id") for row in page}
        assert a["id"] in ids
        assert shared["id"] in ids
        assert b["id"] not in ids
        assert "placeholder-user-b" not in owners

        full = (await _get_records(client, m.tenant, "placeholder-user-a", limit=50)).json()["memories"]
        assert b["id"] not in {row["id"] for row in full}
        assert all(
            (row.get("meta") or {}).get("user_id") in (None, "placeholder-user-a")
            or row["kind"] in {"placeholder.shared", "opli.repo_map"}
            for row in full
        )

        bare = (await _get_records(client, m.tenant, limit=50)).json()["memories"]
        bare_ids = {row["id"] for row in bare}
        assert a["id"] not in bare_ids and b["id"] not in bare_ids
        assert shared["id"] in bare_ids

        spoof_list = (await _get_records(client, m.tenant, "placeholder-user-a", limit=50)).json()["memories"]
        assert b["id"] not in {row["id"] for row in spoof_list}

        for offset in (0, 10, 20):
            chunk = (await _get_records(client, m.tenant, "placeholder-user-a", limit=5, offset=offset)).json()["memories"]
            assert b["id"] not in {row["id"] for row in chunk}
            assert "placeholder-user-b" not in {(row.get("meta") or {}).get("user_id") for row in chunk}


@pytest.mark.asyncio
async def test_fake_memory_records_matches_recall_isolation_not_tenant_dump():
    """Opli FakeMemory: recall was filtered; unscoped records() used to dump all personal rows."""
    from agents.opli.gates_memory import FakeMemory, TENANT_WIDE_KINDS

    assert "opli.repo_map" in TENANT_WIDE_KINDS
    mem = FakeMemory()
    await mem.remember("t1", "A private row", "opli.receipt", "s", user_id="user-a", meta={"user_id": "user-a"})
    await mem.remember("t1", "B private row", "opli.receipt", "s", user_id="user-b", meta={"user_id": "user-b"})
    await mem.remember("t1", "shared map", "opli.repo_map", "s")

    scoped = await mem.records("t1", user_id="user-a")
    ids = {r["id"] for r in scoped}
    assert any(r.get("meta", {}).get("user_id") == "user-a" for r in scoped)
    assert not any(r.get("meta", {}).get("user_id") == "user-b" for r in scoped)
    assert any(r["kind"] == "opli.repo_map" for r in scoped)

    bare = await mem.records("t1")
    assert all((r.get("meta") or {}).get("user_id") in (None, "") or r["kind"] in TENANT_WIDE_KINDS for r in bare)
    assert any(r["kind"] == "opli.repo_map" for r in bare)
    assert not any(r.get("meta", {}).get("user_id") == "user-a" for r in bare)


@pytest.mark.asyncio
async def test_require_owned_record_does_not_scan_raw_rows_for_other_users():
    from agents.opli.gates_memory import FakeMemory, MemoryScopeError, require_owned_record

    mem = FakeMemory()
    a = await mem.remember("t1", "A private row", "opli.receipt", "s", user_id="user-a", meta={"user_id": "user-a"})
    b = await mem.remember("t1", "B private row", "opli.receipt", "s", user_id="user-b", meta={"user_id": "user-b"})
    owned = await require_owned_record(mem, memory_id=a["id"], tenant_id="t1", user_id="user-a")
    assert owned["id"] == a["id"]
    with pytest.raises(MemoryScopeError):
        await require_owned_record(mem, memory_id=b["id"], tenant_id="t1", user_id="user-a")
