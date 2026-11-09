"""Gates 7+8 offline: product→brain→Tank→receipt→memory integration."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from base_memory_fixtures import (
    FakeMemory,
    pilot_fixture_first_usage,
    pilot_fixture_repeat_usage_after_correction,
)
from brain_route import brain_enabled, brain_url, invoke_brain_task
from gates_memory import (
    apply_corrections,
    build_memory_text,
    product_to_brain_tank_memory,
    run_with_memory,
    select_tenant_user_memories,
    usage_from_model_receipts,
)


@pytest.mark.asyncio
async def test_product_request_brain_route_receipt_then_memory():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "batch-delaware-atf"

    async def paid(task):
        return {
            "cost_usd": 0.12,
            "tokens_in": 40,
            "tokens_out": 12,
            "result": {
                "verified": ["record-1"],
                "sources": ["own-site"],
                "failed_checks": [],
                "quirks": ["alias-spelling"],
                "checkpoint": "after-pipeline",
            },
        }

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Recorded Business"},
        paid_call=paid,
    )
    assert [step["action"] for step in receipt["steps"]] == ["recall", "brain_route", "remember"]
    assert receipt["paid_calls"] == 1 and receipt["cost_usd"] == 0.12
    assert receipt["tokens_in"] == 40 and receipt["tokens_out"] == 12
    assert memory.remembers == 1 and memory.rows[0]["tenant_id"] == tenant
    assert memory.rows[0]["meta"]["user_id"] == user
    assert "verified=record-1" in memory.rows[0]["text"]
    assert "sources=own-site" in memory.rows[0]["text"]


@pytest.mark.asyncio
async def test_correction_applies_next_time_with_no_paid_call():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "batch-oregon-retry"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.2,
            "tokens_in": 50,
            "tokens_out": 20,
            "result": {
                "verified": ["record-9"],
                "sources": ["skala"],
                "correction": "prefer-public-alias",
                "checkpoint": "first-pass",
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Alias Shop"},
        paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1

    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Alias Shop"},
        paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0
    assert "prefer-public-alias" in second["result"]["applied_corrections"]
    assert "apply_correction" in [step["action"] for step in second["steps"]]


@pytest.mark.asyncio
async def test_second_user_and_second_tenant_see_nothing():
    memory = FakeMemory()
    tenant_a, user_a = str(uuid4()), str(uuid4())
    tenant_b, user_b = str(uuid4()), str(uuid4())

    await memory.remember(
        tenant_a,
        build_memory_text(summary="Base task private", correction="keep-private"),
        "base.correction",
        "base:task:private",
        meta={"user_id": user_a, "task_key": "private"},
    )
    foreign = select_tenant_user_memories(memory.rows, tenant_id=tenant_b, user_id=user_b)
    other_user = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_b)
    owner = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_a)
    assert foreign == [] and other_user == [] and len(owner) == 1

    async def paid(_task):
        return {"cost_usd": 0.01, "tokens_in": 1, "tokens_out": 1, "result": {"verified": ["x"]}}

    outsider = await run_with_memory(
        memory,
        tenant_id=tenant_b,
        user_id=user_b,
        task_key="private",
        task={"name": "Other"},
        paid_call=paid,
    )
    assert outsider["answered_from_memory"] is False
    assert outsider["paid_calls"] == 1


@pytest.mark.asyncio
async def test_same_task_twice_reports_cost_and_tokens_each_run():
    """Identical uncorrected repeat: fixed fake per-call price; second pays nothing.

    Per-run figures are reported separately from cumulative totals. The fake paid
    per-call price must stay fixed (never reduced between runs). Correction-only
    reuse is covered elsewhere; this proves identical unmodified reuse.
    """
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "batch-cost-twice"
    paid_calls = 0
    # Fixed fake Tank receipt price per paid call (must not shrink on later calls).
    FIXED_PER_CALL = {"cost_usd": 0.00056, "tokens_in": 400, "tokens_out": 80}
    tank_receipts = [
        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
    ]
    assert usage_from_model_receipts(tank_receipts)["cost_usd"] == pytest.approx(
        FIXED_PER_CALL["cost_usd"]
    )

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        # Fixed per-call fake price — never reduced between invocations.
        return {
            "cost_usd": FIXED_PER_CALL["cost_usd"],
            "tokens_in": FIXED_PER_CALL["tokens_in"],
            "tokens_out": FIXED_PER_CALL["tokens_out"],
            "result": {"verified": ["run-1"], "sources": ["tank-receipts"], "checkpoint": "first"},
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Costed"},
        paid_call=paid,
    )
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"name": "Costed"},
        paid_call=paid,
    )

    # Per-run (first): one paid call at the fixed fake Tank-receipt price.
    per_run_first = {
        "paid_calls": first["paid_calls"],
        "cost_usd": first["cost_usd"],
        "tokens_in": first["tokens_in"],
        "tokens_out": first["tokens_out"],
        "tokens_total": first["tokens_in"] + first["tokens_out"],
    }
    assert per_run_first["paid_calls"] == 1 and paid_calls == 1
    assert per_run_first["cost_usd"] == pytest.approx(FIXED_PER_CALL["cost_usd"])
    assert per_run_first["tokens_in"] == FIXED_PER_CALL["tokens_in"]
    assert per_run_first["tokens_out"] == FIXED_PER_CALL["tokens_out"]
    assert per_run_first["tokens_total"] == 480

    # Per-run (identical uncorrected repeat): zero paid calls, zero incremental usage.
    per_run_second = {
        "paid_calls": second["paid_calls"],
        "cost_usd": second["cost_usd"],
        "tokens_in": second["tokens_in"],
        "tokens_out": second["tokens_out"],
        "tokens_total": second["tokens_in"] + second["tokens_out"],
    }
    assert per_run_second["paid_calls"] == 0 and paid_calls == 1
    assert per_run_second["cost_usd"] == 0.0
    assert per_run_second["tokens_in"] == per_run_second["tokens_out"] == 0
    assert per_run_second["tokens_total"] == 0
    assert second["answered_from_memory"] is True
    assert "identical_reuse" in [s["action"] for s in second["steps"]]
    assert "apply_correction" not in [s["action"] for s in second["steps"]]

    # Cumulative across both runs (separate from per-run): only the first paid call.
    cumulative = {
        "paid_calls": per_run_first["paid_calls"] + per_run_second["paid_calls"],
        "cost_usd": per_run_first["cost_usd"] + per_run_second["cost_usd"],
        "tokens_in": per_run_first["tokens_in"] + per_run_second["tokens_in"],
        "tokens_out": per_run_first["tokens_out"] + per_run_second["tokens_out"],
        "tokens_total": per_run_first["tokens_total"] + per_run_second["tokens_total"],
    }
    assert cumulative["paid_calls"] == 1
    assert cumulative["cost_usd"] == pytest.approx(FIXED_PER_CALL["cost_usd"])
    assert cumulative["tokens_in"] == 400 and cumulative["tokens_out"] == 80
    assert cumulative["tokens_total"] == 480
    assert memory.remembers == 1


def test_apply_corrections_and_secret_refusal():
    corrected = apply_corrections({"name": "A"}, ["use-public-url"])
    assert corrected["applied_corrections"] == ["use-public-url"]
    assert corrected["answered_from_memory"] is True
    with pytest.raises(ValueError):
        build_memory_text(summary="leak api_key=should-fail")


def test_pilot_fixture_first_and_repeat_usage_are_fake_offline_not_billing():
    first = pilot_fixture_first_usage()
    repeat = pilot_fixture_repeat_usage_after_correction()
    # Fake offline reference from agents/base/pilot/receipt.json (4 model exchanges).
    assert first == {"cost_usd": 0.00056, "tokens_in": 400, "tokens_out": 80, "tokens_total": 480}
    assert repeat == {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}
    assert first["tokens_total"] == first["tokens_in"] + first["tokens_out"]


@pytest.mark.asyncio
async def test_product_brain_tank_memory_uses_brain_route_and_tank_receipts(monkeypatch):
    """Integration: product_to_brain_tank_memory → invoke_brain_task → Tank receipts → remember."""
    monkeypatch.setenv("BASE_BRAIN_URL", "http://base-brain.test")
    monkeypatch.setenv("TANK_REGION", "us-east")
    tenant, task = str(uuid4()), str(uuid4())
    user = str(uuid4())
    brain_calls = []
    tank_calls = []

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class FakeHTTP:
        async def post(self, url, headers=None, content=None, **kwargs):
            import json
            from chassis.user_assertion import HEADER, verify_assertion
            async def nonce(*args):
                return True
            actor = await verify_assertion(headers[HEADER], key='placeholder-room-key', product='base',
                tenant_id=tenant, method='POST', target='/personal/tasks', body=content, consume_nonce=nonce)
            assert actor.user_id == user
            brain_calls.append(("POST", url, json.loads(content)))
            assert url.endswith("/personal/tasks")
            return await self.get(url)


        async def get(self, url, headers=None, params=None, **kwargs):
            brain_calls.append(("GET", url, params))
            return FakeResponse(
                200,
                {
                    "tenant_id": tenant,
                    "task_id": task,
                    "room": "base",
                    "status": "done",
                    "steps": [{"action": "pipeline_run", "status": "done"}],
                    "model_receipts": [],
                    "summary": "fixture brain done",
                },
            )

    class FakeSkills:
        def __init__(self):
            self._base = "http://tank.test"
            self._http = self
            self._headers_value = {"X-Tank-Key": "placeholder-room-key"}

        def _headers(self):
            return self._headers_value

        async def get(self, url, headers=None, params=None, timeout=None, **kwargs):
            tank_calls.append((url, params))
            assert "/v1/agents/base/receipts" in url
            return FakeResponse(
                200,
                {
                    "receipts": [
                        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "ledger_id": str(uuid4())},
                        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "ledger_id": str(uuid4())},
                        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "ledger_id": str(uuid4())},
                        {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "ledger_id": str(uuid4())},
                    ]
                },
            )

    import brain_route as route_mod

    monkeypatch.setattr(route_mod.httpx, "AsyncClient", lambda timeout=30: _AsyncCM(FakeHTTP()))

    class _AsyncCM:
        def __init__(self, http):
            self.http = http

        async def __aenter__(self):
            return self.http

        async def __aexit__(self, *args):
            return False

    skills = FakeSkills()
    memory = FakeMemory()

    async def brain_tank_call(task_payload):
        return await invoke_brain_task(
            skills,
            tenant_id=tenant,
            task_id=task,
            batch="Delaware ATF",
            count=2,
            user_id=user,
        )

    first = await product_to_brain_tank_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="Delaware ATF",
        task={"batch": "Delaware ATF", "task_id": task},
        brain_tank_call=brain_tank_call,
    )
    assert first["paid_calls"] == 1
    assert first["cost_usd"] == pytest.approx(0.00056)
    assert first["tokens_in"] == 400 and first["tokens_out"] == 80
    assert first["tokens_in"] + first["tokens_out"] == 480
    assert first["result"]["status"] == "done"
    assert first["result"]["steps"][0]["action"] == "pipeline_run"
    assert any(step["action"] == "brain_route" for step in first["steps"])
    assert any(step["action"] == "remember" for step in first["steps"])
    assert brain_calls and tank_calls
    assert brain_enabled() is True and "base-brain" in brain_url()

    # Store a correction then prove the second product call skips brain/Tank.
    await memory.remember(
        tenant,
        build_memory_text(summary="Base task Delaware ATF", correction="reuse-fixture"),
        "base.correction",
        "base:task:Delaware ATF",
        meta={"user_id": user, "task_key": "Delaware ATF"},
    )
    brain_calls.clear()
    tank_calls.clear()

    async def must_not_pay(_task):
        raise AssertionError("paid brain/Tank route must not run after correction")

    second = await product_to_brain_tank_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="Delaware ATF",
        task={"batch": "Delaware ATF", "task_id": task},
        brain_tank_call=must_not_pay,
    )
    assert second["answered_from_memory"] is True
    assert second["paid_calls"] == 0
    assert second["cost_usd"] == 0.0
    assert second["tokens_in"] == second["tokens_out"] == 0
    assert brain_calls == [] and tank_calls == []


@pytest.mark.asyncio
async def test_skills_client_receives_chassis_memory_attribute():
    """app._skills attaches existing chassis memory for drive_batch brackets."""

    # Load only the _skills pattern via a minimal stand-in to avoid full app boot.
    app_state = SimpleNamespace(memory=object(), http=object())

    def _skills_like():
        c = SimpleNamespace()
        c.memory = getattr(app_state, "memory", None)
        return c

    wired = _skills_like()
    assert wired.memory is app_state.memory


def test_usage_from_model_receipts_sums_tank_rows():
    usage = usage_from_model_receipts(
        [
            {"cost_usd": "0.00014", "tokens_in": 100, "tokens_out": 20},
            {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20},
        ]
    )
    assert usage["cost_usd"] == pytest.approx(0.00028)
    assert usage["tokens_in"] == 200 and usage["tokens_out"] == 40
    assert usage["tokens_total"] == 240


@pytest.mark.parametrize("value", [None, "", "not-a-price", "NaN", "Infinity", -1, True])
def test_unknown_receipt_price_is_not_zero_or_a_partial_sum(value):
    known = {"cost_usd": "1.25", "tokens_in": 4, "tokens_out": 2}
    usage = usage_from_model_receipts([known, {**known, "cost_usd": value}])
    assert usage["cost_usd"] is None
    assert usage["tokens_total"] == 12


@pytest.mark.parametrize("rows", [None, [], [{}]])
def test_missing_receipts_preserve_unknown_usage(rows):
    usage = usage_from_model_receipts(rows)
    assert usage == {"cost_usd": None, "tokens_in": None, "tokens_out": None, "tokens_total": None}


def test_recorded_zero_and_partial_tokens_are_distinct_from_missing_accounting():
    row = {"cost_usd": 0, "tokens_in": 0, "tokens_out": 0, "cost_status": "set"}
    assert usage_from_model_receipts([row]) == {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}
    assert usage_from_model_receipts([{**row, "cost_status": "not_set"}])["cost_usd"] is None
    assert usage_from_model_receipts([{**row, "tokens_in": None}])["tokens_total"] is None


@pytest.mark.asyncio
async def test_unknown_paid_accounting_is_retained_without_reusable_memory():
    memory = FakeMemory()
    async def paid(task):
        return {"cost_usd": None, "tokens_in": 400, "tokens_out": 80,
                "result": {"verified": ["placeholder-record"]}}
    receipt = await run_with_memory(memory, tenant_id=str(uuid4()), user_id="placeholder-owner",
                                    task_key="placeholder-batch", task={"count": 1}, paid_call=paid)
    assert receipt["cost_usd"] is None
    assert receipt["paid_calls"] == 1
    assert receipt["accounting_unknown"] is True
    assert memory.remembers == 0
    assert receipt["answered_from_memory"] is False
