"""List/records cross-user disclosure regressions (Opli-reported list gap).

Recall can be isolated while list still returns another user's personal rows.
These tests exercise HTTP /records → Records.list SQL and FakeMemory.records.
"""
from __future__ import annotations

import os
import uuid

import httpx
import pytest
import pytest_asyncio

from test_agent_memory_records import memory as memory_fixture, Encoder

memory = memory_fixture


@pytest.mark.asyncio
async def test_http_list_two_users_one_tenant_never_leaks(memory, monkeypatch):
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    from hermes.user_scope import TENANT_WIDE_KINDS

    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), "placeholder-agent-key")
    monkeypatch.setitem(TENANT_WIDE_KINDS, m.agent, frozenset({"placeholder.shared", "opli.repo_map"}))
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    headers = {"X-Tank-Key": "placeholder-agent-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        a = (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder list-a", "kind": "placeholder.personal",
            "source": "https://placeholder.example/a", "user_id": "placeholder-user-a",
            "meta": {"user_id": "placeholder-user-a"},
        })).json()
        b = (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder list-b", "kind": "placeholder.personal",
            "source": "https://placeholder.example/b", "user_id": "placeholder-user-b",
            "meta": {"user_id": "placeholder-user-b"},
        })).json()
        shared = (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder list-shared", "kind": "placeholder.shared",
            "source": "https://placeholder.example/s",
        })).json()
        # Pad B so pagination cannot hide a leak behind limit.
        for i in range(25):
            await client.post("/memories", headers=headers, json={
                "tenant_id": m.tenant, "text": f"placeholder list-b-pad-{i}", "kind": "placeholder.personal",
                "source": "https://placeholder.example/p", "user_id": "placeholder-user-b",
                "meta": {"user_id": "placeholder-user-b"},
            })

        # Explicit personal scope for A.
        page = (await client.get("/records", headers=headers, params={
            "tenant_id": m.tenant, "user_id": "placeholder-user-a", "limit": 10, "offset": 0,
        })).json()["memories"]
        ids = {row["id"] for row in page}
        owners = {(row.get("meta") or {}).get("user_id") for row in page}
        assert a["id"] in ids
        assert shared["id"] in ids
        assert b["id"] not in ids
        assert "placeholder-user-b" not in owners

        # Omitted kind/filter (default list): still no B.
        full = (await client.get("/records", headers=headers, params={
            "tenant_id": m.tenant, "user_id": "placeholder-user-a", "limit": 50,
        })).json()["memories"]
        assert b["id"] not in {row["id"] for row in full}
        assert all(
            (row.get("meta") or {}).get("user_id") in (None, "placeholder-user-a")
            or row["kind"] in {"placeholder.shared", "opli.repo_map"}
            for row in full
        )

        # Omitted user_id: fail-closed to declared tenant-wide only.
        bare = (await client.get("/records", headers=headers, params={
            "tenant_id": m.tenant, "limit": 50,
        })).json()["memories"]
        bare_ids = {row["id"] for row in bare}
        assert a["id"] not in bare_ids and b["id"] not in bare_ids
        assert shared["id"] in bare_ids

        # Meta spoof on write already refused; list ignores forged query user for ownership
        # of rows — user-a still cannot see B.
        spoof_list = (await client.get("/records", headers=headers, params={
            "tenant_id": m.tenant, "user_id": "placeholder-user-a", "limit": 50,
        })).json()["memories"]
        assert b["id"] not in {row["id"] for row in spoof_list}

        # Pagination offsets must not surface B.
        for offset in (0, 10, 20):
            chunk = (await client.get("/records", headers=headers, params={
                "tenant_id": m.tenant, "user_id": "placeholder-user-a", "limit": 5, "offset": offset,
            })).json()["memories"]
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

    recalled = await mem.recall("t1", "private", user_id="user-a")
    listed = await mem.records("t1", user_id="user-a")
    assert [r["text"] for r in recalled] == ["A private row"]
    assert [r["text"] for r in listed] == ["A private row", "shared map"]
    assert all(r["text"] != "B private row" for r in listed)

    # Fail closed when list omits user: tenant-wide only, never A+B personal dump.
    bare = await mem.records("t1")
    assert [r["text"] for r in bare] == ["shared map"]


@pytest.mark.asyncio
async def test_require_owned_record_does_not_scan_raw_rows_for_other_users():
    from agents.opli.gates_memory import FakeMemory, require_owned_record, MemoryScopeError

    mem = FakeMemory()
    a = await mem.remember("t1", "A private row", "opli.receipt", "s", user_id="user-a", meta={"user_id": "user-a"})
    b = await mem.remember("t1", "B private row", "opli.receipt", "s", user_id="user-b", meta={"user_id": "user-b"})
    owned = await require_owned_record(mem, memory_id=a["id"], tenant_id="t1", user_id="user-a")
    assert owned["id"] == a["id"]
    with pytest.raises(MemoryScopeError):
        await require_owned_record(mem, memory_id=b["id"], tenant_id="t1", user_id="user-a")
