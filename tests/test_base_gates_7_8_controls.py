"""Additional gates 7+8 checks: fail-closed user scope, controls, identical repeat.

New file only — does not edit tests/test_base_gates_7_8.py.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from base_memory_fixtures import (
    FakeMemory,
    pilot_fixture_first_usage,
    pilot_fixture_identical_repeat_usage,
    pilot_fixture_repeat_usage_after_correction,
)
from gates_memory import (
    MemoryControlError,
    MemoryScopeError,
    apply_memory_forget,
    build_memory_text,
    normalize_memory_control,
    product_to_brain_tank_memory,
    require_authenticated_user_id,
    resolve_authenticated_user_id,
    run_with_memory,
    usage_from_model_receipts,
)


def test_missing_user_id_fails_closed_for_memory_scope():
    assert resolve_authenticated_user_id({}, "tenant-a") is None
    assert resolve_authenticated_user_id({"user_id": ""}, "tenant-a") is None
    assert resolve_authenticated_user_id({"requested_by": None}, "tenant-a") is None
    # Refuse synthetic tenant-as-user identity.
    assert resolve_authenticated_user_id({"user_id": "tenant-a"}, "tenant-a") is None
    with pytest.raises(MemoryScopeError):
        require_authenticated_user_id(None, tenant_id="tenant-a")
    with pytest.raises(MemoryScopeError):
        require_authenticated_user_id("tenant-a", tenant_id="tenant-a")


@pytest.mark.asyncio
async def test_run_with_memory_refuses_missing_user_id_without_paid_or_remember():
    memory = FakeMemory()
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {"cost_usd": 1.0, "tokens_in": 1, "tokens_out": 1, "result": {"verified": ["x"]}}

    with pytest.raises(MemoryScopeError):
        await run_with_memory(
            memory,
            tenant_id=str(uuid4()),
            user_id="",
            task_key="no-user",
            task={"name": "X"},
            paid_call=paid,
        )
    assert paid_calls == 0
    assert memory.remembers == 0 and memory.recalls == 0


@pytest.mark.asyncio
async def test_memory_control_off_skips_recall_and_remember_but_still_pays():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    await memory.remember(
        tenant,
        build_memory_text(summary="Base task control-off-batch", correction="should-not-apply"),
        "base.correction",
        "base:task:control-off-batch",
        meta={"user_id": user, "task_key": "control-off-batch"},
    )
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {"cost_usd": 0.03, "tokens_in": 9, "tokens_out": 2, "result": {"verified": ["fresh"]}}

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="control-off-batch",
        task={"name": "Fresh"},
        paid_call=paid,
        memory_control="off",
    )
    assert paid_calls == 1 and receipt["paid_calls"] == 1
    assert receipt["answered_from_memory"] is False
    assert "memory_off" in [s["action"] for s in receipt["steps"]]
    assert memory.recalls == 0
    # off must not remember either (no memory leak / write)
    assert memory.remembers == 1  # only the seed row above


@pytest.mark.asyncio
async def test_memory_control_view_recalls_but_refuses_remember_and_forget():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.04,
            "tokens_in": 11,
            "tokens_out": 3,
            "result": {"verified": ["v1"], "sources": ["code"]},
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="view-batch",
        task={"name": "View"},
        paid_call=paid,
        memory_control="view",
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert memory.remembers == 0
    assert any(s["action"] == "remember_skipped" for s in first["steps"])
    with pytest.raises(MemoryControlError):
        await apply_memory_forget(
            memory, memory_id="mem-1", tenant_id=tenant, user_id=user, memory_control="view"
        )


@pytest.mark.asyncio
async def test_memory_control_edit_remembers_but_refuses_forget():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())

    async def paid(_task):
        return {
            "cost_usd": 0.01,
            "tokens_in": 5,
            "tokens_out": 1,
            "result": {"verified": ["e1"]},
        }

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="edit-batch",
        task={"name": "Edit"},
        paid_call=paid,
        memory_control="edit",
    )
    assert memory.remembers == 1
    assert any(s["action"] == "remember" for s in receipt["steps"])
    with pytest.raises(MemoryControlError):
        await apply_memory_forget(
            memory,
            memory_id=memory.rows[0]["id"],
            tenant_id=tenant,
            user_id=user,
            memory_control="edit",
        )


@pytest.mark.asyncio
async def test_memory_control_forget_deletes_row():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        tenant,
        build_memory_text(summary="forget-me"),
        "base.task",
        "base:task:forget",
        meta={"user_id": user, "task_key": "forget"},
    )
    await apply_memory_forget(
        memory,
        memory_id=saved["id"],
        tenant_id=tenant,
        user_id=user,
        memory_control="forget",
    )
    assert memory.forgets == 1
    assert memory.rows == []
    assert normalize_memory_control("FORGET") == "forget"

    # Cross-user forget within same tenant fails closed (no delete).
    other = str(uuid4())
    again = await memory.remember(
        tenant,
        build_memory_text(summary="owner-only"),
        "base.task",
        "base:task:owner",
        meta={"user_id": user, "task_key": "owner"},
    )
    with pytest.raises(MemoryScopeError):
        await apply_memory_forget(
            memory,
            memory_id=again["id"],
            tenant_id=tenant,
            user_id=other,
            memory_control="forget",
        )
    assert any(row["id"] == again["id"] for row in memory.rows)


@pytest.mark.asyncio
async def test_identical_unmodified_task_second_run_zero_paid_calls():
    """Same unmodified task twice: second pays nothing. Not a correction path."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "identical-batch"
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.00056,
            "tokens_in": 400,
            "tokens_out": 80,
            "result": {"verified": ["same"], "sources": ["fixture"], "checkpoint": "once"},
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Same"},
        paid_call=paid,
        memory_control="edit",
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["cost_usd"] == pytest.approx(0.00056)
    assert first["tokens_in"] == 400 and first["tokens_out"] == 80

    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Same"},
        paid_call=paid,
        memory_control="edit",
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0
    assert second["tokens_in"] == second["tokens_out"] == 0
    assert "identical_reuse" in [s["action"] for s in second["steps"]]
    assert "apply_correction" not in [s["action"] for s in second["steps"]]
    assert second["result"]["reuse"] == "identical_receipt"


@pytest.mark.asyncio
async def test_correction_repeat_is_separate_from_identical_reuse():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "correction-separate"
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.2,
            "tokens_in": 50,
            "tokens_out": 20,
            "result": {
                "verified": ["c1"],
                "correction": "prefer-public-alias",
                "checkpoint": "first",
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Alias"},
        paid_call=paid,
    )
    assert first["paid_calls"] == 1
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Alias"},
        paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert "apply_correction" in [s["action"] for s in second["steps"]]
    assert "identical_reuse" not in [s["action"] for s in second["steps"]]
    assert "prefer-public-alias" in second["result"]["applied_corrections"]


def test_pilot_fixture_first_identical_and_corrected_are_distinct_fake_offline():
    first = pilot_fixture_first_usage()
    identical = pilot_fixture_identical_repeat_usage()
    corrected = pilot_fixture_repeat_usage_after_correction()
    assert first == {"cost_usd": 0.00056, "tokens_in": 400, "tokens_out": 80, "tokens_total": 480}
    assert identical == {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}
    assert corrected == {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}
    # Evidence is summed from pilot/receipt.json model_receipts (fake), not invented totals.
    from base_memory_fixtures import PILOT_FIXTURE_MODEL_RECEIPTS

    assert usage_from_model_receipts(list(PILOT_FIXTURE_MODEL_RECEIPTS)) == first


@pytest.mark.asyncio
async def test_product_path_usage_comes_from_tank_receipts_not_fixture_constants(monkeypatch):
    """Paid path must surface Tank receipt sums from invoke_brain_task."""
    monkeypatch.setenv("BASE_BRAIN_URL", "http://base-brain.test")
    tenant, task, user = str(uuid4()), str(uuid4()), str(uuid4())

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class FakeHTTP:
        async def post(self, url, headers=None, json=None, **kwargs):
            return FakeResponse(200, {
                "tenant_id": tenant,
                "task_id": task,
                "status": "done",
                "steps": [{"action": "pipeline_run"}],
                "model_receipts": [],
            })

        async def get(self, url, headers=None, params=None, **kwargs):
            return FakeResponse(200, {
                "tenant_id": tenant,
                "task_id": task,
                "status": "done",
                "steps": [{"action": "pipeline_run"}],
                "model_receipts": [],
            })

    class FakeSkills:
        def __init__(self):
            self._base = "http://tank.test"
            self._http = self

        def _headers(self):
            return {"X-Tank-Key": "placeholder"}

        async def get(self, url, headers=None, params=None, timeout=None, **kwargs):
            assert "/v1/agents/base/receipts" in url
            return FakeResponse(200, {
                "receipts": [
                    {"cost_usd": 0.001, "tokens_in": 10, "tokens_out": 4},
                    {"cost_usd": 0.002, "tokens_in": 20, "tokens_out": 6},
                ]
            })

    import brain_route as route_mod

    class _AsyncCM:
        def __init__(self, http):
            self.http = http

        async def __aenter__(self):
            return self.http

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(route_mod.httpx, "AsyncClient", lambda timeout=30: _AsyncCM(FakeHTTP()))
    from brain_route import invoke_brain_task

    skills = FakeSkills()
    memory = FakeMemory()

    async def brain_tank_call(_task):
        return await invoke_brain_task(
            skills,
            tenant_id=tenant,
            task_id=task,
            batch="tank-sum",
            count=1,
            user_id=user,
        )

    receipt = await product_to_brain_tank_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="tank-sum",
        task={"batch": "tank-sum", "task_id": task},
        brain_tank_call=brain_tank_call,
    )
    assert receipt["cost_usd"] == pytest.approx(0.003)
    assert receipt["tokens_in"] == 30 and receipt["tokens_out"] == 10
    # Must not be the pilot fixture constant 0.00056 / 400 / 80.
    assert receipt["cost_usd"] != pytest.approx(0.00056)


FIXED_FAKE_PAID = {"cost_usd": 0.00056, "tokens_in": 400, "tokens_out": 80}


def _fixed_paid_factory(counter: dict):
    """Fixed per-call fake Tank price — never call-index dependent."""

    async def paid(_task):
        counter["n"] += 1
        return {
            "cost_usd": FIXED_FAKE_PAID["cost_usd"],
            "tokens_in": FIXED_FAKE_PAID["tokens_in"],
            "tokens_out": FIXED_FAKE_PAID["tokens_out"],
            "result": {"verified": ["fixed"], "sources": ["tank-receipts"], "checkpoint": "paid"},
        }

    return paid


@pytest.mark.asyncio
async def test_reuse_key_requires_same_tenant_user_task_key_and_input_hash():
    from gates_memory import task_input_hash

    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "hash-batch"
    counter = {"n": 0}
    paid = _fixed_paid_factory(counter)
    task_a = {"name": "Alpha", "count": 2}
    task_b = {"name": "Beta", "count": 2}  # changed input
    assert task_input_hash(task_a) != task_input_hash(task_b)

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task_a,
        paid_call=paid,
    )
    assert first["paid_calls"] == 1 and counter["n"] == 1
    assert first["cost_usd"] == pytest.approx(FIXED_FAKE_PAID["cost_usd"])
    assert first["tokens_in"] == FIXED_FAKE_PAID["tokens_in"]
    assert first["tokens_out"] == FIXED_FAKE_PAID["tokens_out"]

    # Identical: same tenant, user, task_key, input hash → incremental paid_calls=0
    identical = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task_a,
        paid_call=paid,
    )
    assert identical["paid_calls"] == 0 and counter["n"] == 1
    assert identical["cost_usd"] == 0.0
    assert identical["tokens_in"] == identical["tokens_out"] == 0
    assert "identical_reuse" in [s["action"] for s in identical["steps"]]
    # Short-circuit: brain/Tank paid_call not invoked on reuse.
    assert not any(s["action"] == "brain_route" for s in identical["steps"])

    # Changed input → miss (must pay again at the SAME fixed per-call price).
    changed = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task_b,
        paid_call=paid,
    )
    assert changed["paid_calls"] == 1 and counter["n"] == 2
    assert changed["cost_usd"] == pytest.approx(FIXED_FAKE_PAID["cost_usd"])
    assert changed["tokens_in"] == FIXED_FAKE_PAID["tokens_in"]
    assert changed["tokens_out"] == FIXED_FAKE_PAID["tokens_out"]
    assert changed["answered_from_memory"] is False


@pytest.mark.asyncio
async def test_changed_user_and_tenant_miss_reuse_isolation():
    memory = FakeMemory()
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    user_a, user_b = str(uuid4()), str(uuid4())
    task_key = "iso-batch"
    task = {"name": "SameInput", "count": 1}
    counter = {"n": 0}
    paid = _fixed_paid_factory(counter)

    first = await run_with_memory(
        memory,
        tenant_id=tenant_a,
        user_id=user_a,
        task_key=task_key,
        task=task,
        paid_call=paid,
    )
    assert first["paid_calls"] == 1 and counter["n"] == 1

    other_user = await run_with_memory(
        memory,
        tenant_id=tenant_a,
        user_id=user_b,
        task_key=task_key,
        task=task,
        paid_call=paid,
    )
    assert other_user["paid_calls"] == 1 and counter["n"] == 2
    assert other_user["cost_usd"] == pytest.approx(FIXED_FAKE_PAID["cost_usd"])
    assert other_user["answered_from_memory"] is False

    other_tenant = await run_with_memory(
        memory,
        tenant_id=tenant_b,
        user_id=user_a,
        task_key=task_key,
        task=task,
        paid_call=paid,
    )
    assert other_tenant["paid_calls"] == 1 and counter["n"] == 3
    assert other_tenant["cost_usd"] == pytest.approx(FIXED_FAKE_PAID["cost_usd"])
    assert other_tenant["answered_from_memory"] is False


@pytest.mark.asyncio
async def test_correction_overrides_and_invalidates_stale_identical_result():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "corr-invalidate"
    task = {"name": "Stale", "count": 1}
    counter = {"n": 0}

    async def paid_then_correct(_task):
        counter["n"] += 1
        if counter["n"] == 1:
            return {
                "cost_usd": FIXED_FAKE_PAID["cost_usd"],
                "tokens_in": FIXED_FAKE_PAID["tokens_in"],
                "tokens_out": FIXED_FAKE_PAID["tokens_out"],
                "result": {"verified": ["stale"], "sources": ["tank"], "checkpoint": "one"},
            }
        return {
            "cost_usd": FIXED_FAKE_PAID["cost_usd"],
            "tokens_in": FIXED_FAKE_PAID["tokens_in"],
            "tokens_out": FIXED_FAKE_PAID["tokens_out"],
            "result": {
                "verified": ["fresh"],
                "correction": "prefer-public-alias",
                "checkpoint": "two",
            },
        }

    # First paid stores identical-reusable receipt.
    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid_then_correct,
    )
    assert first["paid_calls"] == 1 and counter["n"] == 1

    # Second paid stores a correction (invalidates stale identical).
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Stale", "count": 2},  # different input forces pay
        paid_call=paid_then_correct,
    )
    assert second["paid_calls"] == 1 and counter["n"] == 2
    assert (second["result"] or {}).get("correction") == "prefer-public-alias"

    # Same original input now hits correction override, not stale identical reuse.
    third = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid_then_correct,
    )
    assert third["paid_calls"] == 0 and counter["n"] == 2
    assert third["answered_from_memory"] is True
    assert "apply_correction" in [s["action"] for s in third["steps"]]
    assert "identical_reuse" not in [s["action"] for s in third["steps"]]
    assert third["cost_usd"] == 0.0
    assert third["tokens_in"] == third["tokens_out"] == 0


@pytest.mark.asyncio
async def test_off_and_forget_honored_without_task_side_effect_forget():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "control-honor"
    task = {"name": "Ctrl", "count": 1}
    counter = {"n": 0}
    paid = _fixed_paid_factory(counter)

    # Seed a reusable receipt under edit.
    seeded = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    assert seeded["paid_calls"] == 1 and memory.remembers == 1
    mem_id = memory.rows[0]["id"]

    # off: must not recall/reuse; pays at fixed price; does not remember; does not forget.
    off = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="off",
    )
    assert off["paid_calls"] == 1 and counter["n"] == 2
    assert off["cost_usd"] == pytest.approx(FIXED_FAKE_PAID["cost_usd"])
    assert memory.forgets == 0
    assert "memory_off" in [s["action"] for s in off["steps"]]

    # Task path with control=forget still must NOT delete as a side effect.
    before = list(memory.rows)
    under_forget = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="forget",
    )
    # May identical-reuse (forget allows recall); must not auto-delete.
    assert memory.forgets == 0
    assert len(memory.rows) >= len(before)
    assert under_forget["paid_calls"] in (0, 1)

    # Explicit forget honored only via apply_memory_forget.
    await apply_memory_forget(
        memory,
        memory_id=mem_id,
        tenant_id=tenant,
        user_id=user,
        memory_control="forget",
    )
    assert memory.forgets == 1
    assert all(row["id"] != mem_id for row in memory.rows)


@pytest.mark.asyncio
async def test_product_memory_short_circuits_before_brain_tank_invocation(monkeypatch):
    """answered_from_memory must not invoke invoke_brain_task / Tank receipts."""
    memory = FakeMemory()
    tenant, user, task_id = str(uuid4()), str(uuid4()), str(uuid4())
    task_key = "short-circuit"
    task = {"batch": task_key, "task_id": task_id, "tenant_id": tenant}
    counter = {"n": 0}
    paid = _fixed_paid_factory(counter)

    first = await product_to_brain_tank_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        brain_tank_call=paid,
    )
    assert first["paid_calls"] == 1 and counter["n"] == 1

    async def must_not_reach_brain(_task):
        raise AssertionError("brain/Tank must not run on identical memory reuse")

    second = await product_to_brain_tank_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        brain_tank_call=must_not_reach_brain,
    )
    assert second["paid_calls"] == 0 and counter["n"] == 1
    assert second["cost_usd"] == 0.0
    assert second["tokens_in"] == second["tokens_out"] == 0
    assert "identical_reuse" in [s["action"] for s in second["steps"]]


@pytest.mark.asyncio
async def test_drive_batch_shaped_payload_ignores_fresh_task_uuid():
    """Mirrors base_brain drive_batch business fields + out-of-band task_id."""
    from gates_memory import task_input_hash

    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    counter = {"n": 0}
    paid = _fixed_paid_factory(counter)
    business = {"batch": "Oregon ATF", "count": 10, "engine": "ffl", "preview": False}
    first_task = {**business, "task_id": str(uuid4()), "tenant_id": tenant}
    second_task = {**business, "task_id": str(uuid4()), "tenant_id": tenant}
    assert task_input_hash(first_task) == task_input_hash(second_task)

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="Oregon ATF",
        task=first_task,
        paid_call=paid,
        memory_control="edit",
    )
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="Oregon ATF",
        task=second_task,
        paid_call=paid,
        memory_control="edit",
    )
    assert first["paid_calls"] == 1 and counter["n"] == 1
    assert first["cost_usd"] == pytest.approx(FIXED_FAKE_PAID["cost_usd"])
    assert second["paid_calls"] == 0 and counter["n"] == 1
    assert second["cost_usd"] == 0.0
    assert second["tokens_in"] == second["tokens_out"] == 0


@pytest.mark.asyncio
async def test_chassis_calls_receive_verified_user_before_storage_filtering():
    class ScopedMemory(FakeMemory):
        async def recall(self, tenant_id, query, **kwargs):
            assert kwargs['user_id'] == 'placeholder-owner'
            return await super().recall(tenant_id, query, **kwargs)
        async def remember(self, *args, **kwargs):
            assert kwargs['user_id'] == 'placeholder-owner'
            return await super().remember(*args, **kwargs)
    async def paid(task):
        return {'cost_usd': .00056, 'tokens_in': 400, 'tokens_out': 80, 'result': {'verified': ['placeholder-record'], 'sources': ['placeholder-source']}}
    from gates_memory import run_with_memory
    result = await run_with_memory(ScopedMemory(), tenant_id=str(uuid4()), user_id='placeholder-owner', task_key='placeholder-batch', task={'batch':'placeholder-batch'}, paid_call=paid)
    assert result['paid_calls'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', ['hermes answered 503', 'hermes answered 401', 'hermes answered 403'])
async def test_post_payment_storage_failure_never_dispatches_twice(failure):
    from gates_memory import run_with_memory
    class WriteFailure(FakeMemory):
        async def remember(self, *args, **kwargs):
            raise RuntimeError(failure)
    calls = []
    async def paid(task):
        calls.append(task)
        return {'cost_usd': .00056, 'tokens_in': 400, 'tokens_out': 80, 'result': {'verified': ['placeholder-record']}}
    options = {'tenant_id': str(uuid4()), 'user_id': 'placeholder-owner', 'task_key': 'placeholder-batch', 'task': {'batch':'placeholder-batch'}, 'paid_call': paid}
    if failure.endswith('503'):
        result = await run_with_memory(WriteFailure(), **options)
        assert result['memory_unavailable'] and result['paid_calls'] == 1
        assert result['cost_usd'] == .00056 and result['tokens_in'] == 400 and result['tokens_out'] == 80
    else:
        with pytest.raises(RuntimeError, match=failure):
            await run_with_memory(WriteFailure(), **options)
    assert len(calls) == 1
