"""Gates 7+8 offline: memory bracket, corrections, isolation, repeat cost.

All cost and token figures here are FAKE FIXTURE values (fixed per paid call).
They are not billing, not provider spend, and not a live measurement.
"""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "radix"))

from radix_memory_fakes import FakeMemory, FIXED_FAKE_PER_CALL
from gates_memory import (
    MemoryControlError,
    apply_corrections,
    apply_memory_forget,
    build_memory_text,
    run_with_memory,
    select_tenant_user_memories,
    set_memory_control,
    view_memories,
)
from radix_brain import brain_enabled


@pytest.mark.asyncio
async def test_product_request_brain_route_receipt_then_memory():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "scan-site"

    async def paid(task):
        return {
            "cost_usd": 0.12,
            "tokens_in": 40,
            "tokens_out": 12,
            "result": {
                "sites_scanned": ["example.test"],
                "findings": ["open-redirect"],
                "fixes": ["add-allowlist"],
                "accepted_risks": ["info-banner"],
                "false_positives": ["cdn-noise"],
            },
        }

    receipt = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "example.test"}, paid_call=paid,
    )
    assert [step["action"] for step in receipt["steps"]] == ["recall", "brain_route", "remember"]
    assert receipt["paid_calls"] == 1 and receipt["cost_usd"] == 0.12
    assert receipt["tokens_in"] == 40 and receipt["tokens_out"] == 12
    assert memory.remembers == 1 and memory.rows[0]["tenant_id"] == tenant
    assert memory.rows[0]["meta"]["user_id"] == user
    text = memory.rows[0]["text"]
    assert "sites_scanned=example.test" in text
    assert "findings=open-redirect" in text
    assert "fixes=add-allowlist" in text
    assert "accepted_risks=info-banner" in text
    assert "false_positives=cdn-noise" in text


@pytest.mark.asyncio
async def test_correction_applies_next_time_with_no_paid_call():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "scan-source-retry"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.2, "tokens_in": 50, "tokens_out": 20,
            "result": {
                "sites_scanned": ["beta.test"],
                "findings": ["csrf"],
                "fixes": ["token-header"],
                "correction": "mark-csrf-false-positive",
                "accepted_risks": ["none"],
                "false_positives": ["none"],
            },
        }

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "beta.test"}, paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1

    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "beta.test"}, paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert "mark-csrf-false-positive" in second["result"]["applied_corrections"]
    assert "apply_correction" in [step["action"] for step in second["steps"]]


@pytest.mark.asyncio
async def test_second_user_and_second_tenant_see_nothing():
    memory = FakeMemory()
    tenant_a, user_a = str(uuid4()), str(uuid4())
    tenant_b, user_b = str(uuid4()), str(uuid4())

    await memory.remember(
        tenant_a,
        build_memory_text(summary="Radix task private", correction="keep-private",
                          outcome="private", sites_scanned=["x"], findings=["y"],
                          fixes=["z"], accepted_risks=["none"], false_positives=["none"],
                          receipt="cost=0"),
        "radix.correction", "radix:task:private",
        meta={"user_id": user_a, "task_key": "private"},
    )
    foreign = select_tenant_user_memories(memory.rows, tenant_id=tenant_b, user_id=user_b)
    other_user = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_b)
    owner = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_a)
    assert foreign == [] and other_user == [] and len(owner) == 1

    async def paid(_task):
        return {"cost_usd": 0.01, "tokens_in": 1, "tokens_out": 1,
                "result": {"sites_scanned": ["other"], "findings": ["x"], "fixes": ["y"],
                           "accepted_risks": ["none"], "false_positives": ["none"]}}

    outsider = await run_with_memory(
        memory, tenant_id=tenant_b, user_id=user_b, task_key="private",
        task={"site": "other"}, paid_call=paid,
    )
    assert outsider["answered_from_memory"] is False and outsider["paid_calls"] == 1


@pytest.mark.asyncio
async def test_same_task_twice_reports_cost_and_tokens_each_run():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "scan-cost-twice"
    paid_calls = 0
    fixed = FIXED_FAKE_PER_CALL

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        # Fixed per-call fixture price: never 0.05 × call count.
        return {
            **fixed,
            "result": {"sites_scanned": ["costed.test"], "findings": ["none"],
                       "fixes": ["none"], "accepted_risks": ["none"], "false_positives": ["none"]},
        }

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "costed.test"}, paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["cost_usd"] == fixed["cost_usd"]
    assert first["tokens_in"] == fixed["tokens_in"] and first["tokens_out"] == fixed["tokens_out"]
    assert first["answered_from_memory"] is False

    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "costed.test"}, paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert second["would_have_cost"] == fixed["cost_usd"]
    assert "answer_from_memory" in [step["action"] for step in second["steps"]]

    third = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "costed.test", "mode": "deep"}, paid_call=paid,
    )
    assert third["paid_calls"] == 1 and paid_calls == 2
    assert third["cost_usd"] == fixed["cost_usd"]
    assert third["tokens_in"] == fixed["tokens_in"] and third["tokens_out"] == fixed["tokens_out"]

    other_user = await run_with_memory(
        memory, tenant_id=tenant, user_id=str(uuid4()), task_key=task_key,
        task={"site": "costed.test"}, paid_call=paid,
    )
    other_tenant = await run_with_memory(
        memory, tenant_id=str(uuid4()), user_id=user, task_key=task_key,
        task={"site": "costed.test"}, paid_call=paid,
    )
    assert other_user["paid_calls"] == 1 and other_tenant["paid_calls"] == 1
    assert other_user["answered_from_memory"] is False
    assert other_tenant["answered_from_memory"] is False
    assert paid_calls == 4

    fourth_off = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "costed.test"}, paid_call=paid, memory_control="off",
    )
    assert fourth_off["paid_calls"] == 1 and paid_calls == 5
    assert fourth_off["cost_usd"] == fixed["cost_usd"]
    assert "memory_off" in [step["action"] for step in fourth_off["steps"]]


@pytest.mark.asyncio
async def test_memory_off_for_one_user_does_not_affect_other():
    memory = FakeMemory()
    tenant = str(uuid4())
    user_a, user_b = str(uuid4()), str(uuid4())
    task_key = "scan-cost-twice"
    paid_calls = 0
    fixed = FIXED_FAKE_PER_CALL

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {**fixed, "result": {"sites_scanned": ["shared"], "findings": ["none"],
                                    "fixes": ["none"], "accepted_risks": ["none"],
                                    "false_positives": ["none"]}}

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_a, task_key=task_key,
        task={"site": "shared"}, paid_call=paid,
    )
    assert first["paid_calls"] == 1
    await set_memory_control(memory, tenant_id=tenant, user_id=user_a, control="off")
    off_a = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_a, task_key=task_key,
        task={"site": "shared"}, paid_call=paid,
    )
    assert off_a["paid_calls"] == 1 and off_a["answered_from_memory"] is False

    first_b = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_b, task_key=task_key,
        task={"site": "shared"}, paid_call=paid,
    )
    assert first_b["paid_calls"] == 1
    second_b = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_b, task_key=task_key,
        task={"site": "shared"}, paid_call=paid,
    )
    assert second_b["answered_from_memory"] is True and second_b["paid_calls"] == 0
    viewed_a = await view_memories(memory, tenant_id=tenant, user_id=user_a, task_key=task_key)
    assert viewed_a["memory_control"] == "off" and viewed_a["memories"] == []


@pytest.mark.asyncio
async def test_memory_controls_view_edit_forget():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    fixed = FIXED_FAKE_PER_CALL

    async def paid(_task):
        return {**fixed, "result": {"sites_scanned": ["s"], "findings": ["f"],
                                    "fixes": ["x"], "accepted_risks": ["none"],
                                    "false_positives": ["none"]}}

    viewed = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="scan-view",
        task={"site": "View"}, paid_call=paid, memory_control="view",
    )
    assert viewed["paid_calls"] == 1 and memory.remembers == 0

    edited = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="scan-edit",
        task={"site": "Edit"}, paid_call=paid, memory_control="edit",
    )
    assert edited["paid_calls"] == 1 and memory.remembers == 1
    mid = memory.rows[0]["id"]
    with pytest.raises(MemoryControlError):
        await apply_memory_forget(
            memory, memory_id=mid, tenant_id=tenant, user_id=user, memory_control="edit",
        )
    await apply_memory_forget(
        memory, memory_id=mid, tenant_id=tenant, user_id=user, memory_control="forget",
    )
    assert memory.forgets == 1 and memory.rows == []


@pytest.mark.asyncio
async def test_code_skill_free_step_before_paid():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {**FIXED_FAKE_PER_CALL, "result": {"sites_scanned": ["x"], "findings": ["y"],
                                                  "fixes": ["z"], "accepted_risks": ["none"],
                                                  "false_positives": ["none"]}}

    async def code_free(_task):
        return {"result": {"sites_scanned": ["from-code"], "findings": ["static"],
                           "fixes": ["none"], "accepted_risks": ["none"], "false_positives": ["none"]}}

    receipt = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="scan-code",
        task={"site": "Code"}, paid_call=paid, code_free=code_free,
    )
    assert paid_calls == 0 and receipt["paid_calls"] == 0
    assert receipt["result"]["sites_scanned"] == ["from-code"]
    assert [s["action"] for s in receipt["steps"]] == ["code_skill", "code_free_done"]


def test_remembered_fields_refuse_empty_and_secrets():
    with pytest.raises(ValueError, match="empty remembered field"):
        build_memory_text(summary="", sites_scanned=["q"])
    with pytest.raises(ValueError):
        build_memory_text(summary="leak api_key=should-fail")
    corrected = apply_corrections({"site": "A"}, ["ignore-cdn"])
    assert corrected["applied_corrections"] == ["ignore-cdn"]


def test_brain_switch_defaults_and_url(monkeypatch):
    # Private discovery moved to Tank; the room only needs its existing switch.
    import radix_brain
    monkeypatch.delenv("RADIX_BRAIN_ENABLED", raising=False)
    assert brain_enabled() is False
    assert not hasattr(radix_brain, "brain_url")
    monkeypatch.setenv("RADIX_BRAIN_ENABLED", "true")
    assert brain_enabled() is True
    monkeypatch.setenv("RADIX_BRAIN_ENABLED", "false")
    assert brain_enabled() is False


def test_unknown_accounting_preserves_tank_reservation_without_claiming_a_bill():
    from radix_brain import accounting
    receipt = {"cost_status": "unknown_upper_bound", "cost_usd": .05,
               "tokens_in": 10, "tokens_out": 3, "ledger_id": "placeholder-ledger",
               "baseline_cost_usd": .06}
    result = accounting(receipt)
    assert result["tank_receipt"] == receipt
    assert result["cost_usd"] is None and result["tokens_in"] is None and result["tokens_out"] is None
    assert result["ledger_id"] == receipt["ledger_id"] and result["would_have_cost"] == .06
    delivered = accounting({**receipt, "cost_status": "reported"})
    assert (delivered["cost_usd"], delivered["tokens_in"], delivered["tokens_out"]) == (.05, 10, 3)


@pytest.mark.asyncio
async def test_memory_outage_answers_without_memory_never_serves_repeat():
    """Point 8: Hermes outage → answer without memory; receipt marks unavailable."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "scan-site"
    paid_calls = 0
    fixed = FIXED_FAKE_PER_CALL

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": fixed["cost_usd"],
            "tokens_in": fixed["tokens_in"],
            "tokens_out": fixed["tokens_out"],
            "result": {
                "sites_scanned": [task["site"]],
                "findings": ["live"],
                "fixes": ["none-applied"],
                "accepted_risks": ["none"],
                "false_positives": ["none"],
            },
        }

    # Seed a repeatable receipt then break recall.
    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "a.test"}, paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1

    async def boom(*args, **kwargs):
        raise RuntimeError("hermes answered 503 memory store unreachable")

    memory.recall = boom
    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"site": "a.test"}, paid_call=paid,
    )
    assert second.get("memory_unavailable") is True
    assert second["answered_from_memory"] is False
    assert second["paid_calls"] == 1 and paid_calls == 2
    assert second["cost_usd"] == fixed["cost_usd"]


@pytest.mark.asyncio
async def test_missing_invalid_scope_refused_offline():
    """Point 8: missing/invalid tenant or user is refused (not an outage)."""
    from gates_memory import MemoryScopeError, require_authenticated_scope

    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id=None, user_id="u")
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id="t", user_id="")
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id="t", user_id="t")  # tenant-as-user
