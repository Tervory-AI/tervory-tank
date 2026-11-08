"""t51 offline: personal vs tenant-wide scope via FakeMemory (proposed Hermes SQL).

FakeMemory simulates the UNAPPLIED chassis/Hermes user_id filter. These tests
prove the product only passes Actor.user_id and that positive own-user and
tenant-wide-to-both cases work under the proposed shared behaviour. They are
NOT a pass of the CURRENT pinned Hermes (see test_radix_memory_contract.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "radix"))

from radix_memory_fakes import FakeMemory
from radix_memory import (
    MemoryScopeError,
    TENANT_WIDE_KINDS,
    build_memory_text,
    recall_for_actor,
    remember_for_actor,
    require_authenticated_scope,
)


TENANT = "11111111-1111-4111-8111-111111111111"
OTHER_TENANT = "22222222-2222-4222-8222-222222222222"
USER_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
USER_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _personal_text(tag: str) -> str:
    return build_memory_text(
        summary=f"Radix {tag}", outcome=tag, sites_scanned=[f"{tag}.test"],
        findings=[tag], fixes=["none"], accepted_risks=["none"],
        false_positives=["none"], receipt="cost=0",
    )


@pytest.mark.asyncio
async def test_two_users_personal_recall_isolated_under_proposed_scope():
    memory = FakeMemory()
    await remember_for_actor(
        memory, tenant_id=TENANT, user_id=USER_A, text=_personal_text("a-only"),
        kind="radix.finding", source="radix:task:a",
        meta={"task_key": "a"},
    )
    await remember_for_actor(
        memory, tenant_id=TENANT, user_id=USER_B, text=_personal_text("b-only"),
        kind="radix.finding", source="radix:task:b",
        meta={"task_key": "b"},
    )
    a_rows = await recall_for_actor(
        memory, tenant_id=TENANT, user_id=USER_A, query="a-only", kind="radix.finding",
    )
    b_rows = await recall_for_actor(
        memory, tenant_id=TENANT, user_id=USER_B, query="b-only", kind="radix.finding",
    )
    assert len(a_rows) == 1 and (a_rows[0].get("meta") or {}).get("user_id") == USER_A
    assert len(b_rows) == 1 and (b_rows[0].get("meta") or {}).get("user_id") == USER_B
    assert await recall_for_actor(
        memory, tenant_id=TENANT, user_id=USER_A, query="b-only", kind="radix.finding",
    ) == []
    assert await recall_for_actor(
        memory, tenant_id=TENANT, user_id=USER_B, query="a-only", kind="radix.finding",
    ) == []


@pytest.mark.asyncio
async def test_tenant_wide_reaches_both_when_declared(monkeypatch):
    import radix_memory as gm
    monkeypatch.setattr(gm, "TENANT_WIDE_KINDS", frozenset({"radix.site_scan"}))
    memory = FakeMemory()
    # Tenant-wide write: no user_id in meta.
    await memory.remember(
        TENANT, _personal_text("shared-scan"), "radix.site_scan", "radix:task:shared",
        meta={"task_key": "shared"}, tenant_wide=True,
    )
    for user in (USER_A, USER_B):
        rows = await recall_for_actor(
            memory, tenant_id=TENANT, user_id=user, query="shared-scan",
            kind="radix.site_scan",
        )
        assert len(rows) == 1
        assert not (rows[0].get("meta") or {}).get("user_id")


@pytest.mark.asyncio
async def test_missing_user_on_personal_kind_refused():
    memory = FakeMemory()
    with pytest.raises((MemoryScopeError, ValueError)):
        await remember_for_actor(
            memory, tenant_id=TENANT, user_id="", text=_personal_text("x"),
            kind="radix.finding", source="radix:task:x",
        )
    with pytest.raises(ValueError, match="missing user_id"):
        await memory.remember(
            TENANT, _personal_text("x"), "radix.finding", "radix:task:x", meta={},
        )


@pytest.mark.asyncio
async def test_tenant_walls_still_hold():
    memory = FakeMemory()
    await remember_for_actor(
        memory, tenant_id=TENANT, user_id=USER_A, text=_personal_text("wall"),
        kind="radix.fix", source="radix:task:wall", meta={"task_key": "wall"},
    )
    assert await recall_for_actor(
        memory, tenant_id=OTHER_TENANT, user_id=USER_A, query="wall", kind="radix.fix",
    ) == []


def test_product_does_not_declare_filtering_helpers_as_tenant_wide_default():
    # Default: no Radix kinds are tenant-wide; personal is the rule.
    assert TENANT_WIDE_KINDS == frozenset()
    tenant, user = require_authenticated_scope(tenant_id=TENANT, user_id=USER_A)
    assert tenant == TENANT and user == USER_A
