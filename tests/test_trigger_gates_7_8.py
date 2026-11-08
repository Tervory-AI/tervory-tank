"""Gates 7+8 offline: memory bracket, corrections, isolation, repeat cost."""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest
import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "trigger"))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "vendor" / "tervory-tank" / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "vendor" / "tervory-tank"))

from trigger.gates_memory import (
    FakeMemory,
    apply_corrections,
    attach_capped_recall,
    build_memory_text,
    categories_from_memories,
    MEMORY_OFF_KIND,
    MEMORY_OFF_SOURCE,
    MEMORY_OFF_TEXT,
    memory_off_from_rows,
    owned_memory_row,
    estimate_tokens,
    memory_enabled,
    recall_token_budget,
    run_with_memory,
    select_tenant_user_memories,
    summarise_recall,
    task_input_fingerprint,
)
from trigger_brain import brain_enabled, brain_then_route


FIXED_COST = {"cost_usd": 0.05, "tokens_in": 10, "tokens_out": 3}


def _paid_result(tag: str = "run") -> dict:
    return {
        **FIXED_COST,
        "result": {
            "deal_history": [tag],
            "conversation_context": ["repeat-safe"],
            "tone": ["neutral"],
            "contact_id": "costed",
        },
    }


@pytest.mark.asyncio
async def test_product_request_brain_route_receipt_then_memory():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "contact-acme-deal"

    async def paid(task):
        return {
            "cost_usd": 0.12,
            "tokens_in": 40,
            "tokens_out": 12,
            "result": {
                "contact_id": "acme",
                "deal_history": ["quoted-500"],
                "conversation_context": ["asked-about-shipping"],
                "objections": ["price-too-high"],
                "tone": ["direct"],
                "handover_notes": ["wants-human-followup"],
            },
        }

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"contact_id": "acme", "text": "Follow up on the quote"},
        paid_call=paid,
    )
    assert [step["action"] for step in receipt["steps"]] == [
        "recall",
        "recall_cap",
        "brain_route",
        "remember",
    ]
    assert receipt["paid_calls"] == 1 and receipt["cost_usd"] == 0.12
    assert receipt["tokens_in"] == 40 and receipt["tokens_out"] == 12
    assert memory.remembers == 1 and memory.rows[0]["tenant_id"] == tenant
    assert memory.rows[0]["meta"]["user_id"] == user
    assert "deal=quoted-500" in memory.rows[0]["text"]
    assert "objections=price-too-high" in memory.rows[0]["text"]
    assert "handover=wants-human-followup" in memory.rows[0]["text"]


@pytest.mark.asyncio
async def test_correction_applies_next_time_with_no_paid_call():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "contact-beta-retry"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.2,
            "tokens_in": 50,
            "tokens_out": 20,
            "result": {
                "contact_id": "beta",
                "deal_history": ["demo-booked"],
                "conversation_context": ["asked-timeline"],
                "correction": "prefer-email-not-phone",
                "tone": ["calm"],
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"contact_id": "beta", "text": "When can we start?"},
        paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1

    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"contact_id": "beta", "text": "When can we start?"},
        paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert "prefer-email-not-phone" in second["result"]["applied_corrections"]
    assert "apply_correction" in [step["action"] for step in second["steps"]]


@pytest.mark.asyncio
async def test_second_user_and_second_tenant_see_nothing():
    memory = FakeMemory()
    tenant_a, user_a = str(uuid4()), str(uuid4())
    tenant_b, user_b = str(uuid4()), str(uuid4())

    await memory.remember(
        tenant_a,
        build_memory_text(summary="Trigger task private", correction="keep-private"),
        "trigger.correction",
        "trigger:task:private",
        meta={"user_id": user_a, "task_key": "private"},
    )
    foreign = select_tenant_user_memories(memory.rows, tenant_id=tenant_b, user_id=user_b)
    other_user = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_b)
    owner = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_a)
    assert foreign == [] and other_user == [] and len(owner) == 1

    async def paid(_task):
        return {
            "cost_usd": 0.01,
            "tokens_in": 1,
            "tokens_out": 1,
            "result": {"deal_history": ["x"], "conversation_context": ["y"]},
        }

    outsider = await run_with_memory(
        memory,
        tenant_id=tenant_b,
        user_id=user_b,
        task_key="private",
        task={"contact_id": "other", "text": "Hello"},
        paid_call=paid,
    )
    assert outsider["answered_from_memory"] is False
    assert outsider["paid_calls"] == 1

    # Exact same inputs from a different user must not get the memory hit.
    paid_calls = 0

    async def paid_fixed(task):
        nonlocal paid_calls
        paid_calls += 1
        return _paid_result("isolation")

    owner_first = await run_with_memory(
        memory,
        tenant_id=tenant_a,
        user_id=user_a,
        task_key="shared-key",
        task={"contact_id": "shared", "text": "Same inputs"},
        paid_call=paid_fixed,
    )
    assert owner_first["paid_calls"] == 1 and paid_calls == 1
    other = await run_with_memory(
        memory,
        tenant_id=tenant_a,
        user_id=user_b,
        task_key="shared-key",
        task={"contact_id": "shared", "text": "Same inputs"},
        paid_call=paid_fixed,
    )
    assert other["answered_from_memory"] is False
    assert other["paid_calls"] == 1
    assert paid_calls == 2


@pytest.mark.asyncio
async def test_same_task_twice_reports_cost_and_tokens_each_run():
    """Per-run figures: first pays fixed fixture; identical repeat is $0 from memory;
    a near-repeat (different input) still pays and costs no more than run 1.
    """
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "contact-cost-twice"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        # Fixed per-call price — never 0.05 × call count.
        return _paid_result(f"run-{paid_calls}")

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"contact_id": "costed", "text": "Status?"},
        paid_call=paid,
    )
    assert first["cost_usd"] == 0.05 and first["tokens_in"] == 10 and first["tokens_out"] == 3
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["answered_from_memory"] is False

    # Uncorrected identical repeat: zero paid calls, zero incremental model cost/tokens.
    paid_before_repeat = paid_calls
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"contact_id": "costed", "text": "Status?"},
        paid_call=paid,
    )
    assert second["answered_from_memory"] is True
    assert second["paid_calls"] == 0
    assert paid_calls - paid_before_repeat == 0
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert second["would_have_cost"]["cost_usd"] == 0.05
    assert second["would_have_cost"]["tokens_in"] == 10
    assert second["would_have_cost"]["tokens_out"] == 3
    assert "exact_repeat_from_memory" in [step["action"] for step in second["steps"]]

    # Near-repeat (different input) still pays; per-run cost ≤ first run.
    paid_before_near = paid_calls
    near = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"contact_id": "costed", "text": "Status update with new detail?"},
        paid_call=paid,
    )
    assert near["answered_from_memory"] is False
    assert near["paid_calls"] == 1
    assert paid_calls - paid_before_near == 1
    assert near["cost_usd"] == 0.05 and near["tokens_in"] == 10 and near["tokens_out"] == 3
    assert near["cost_usd"] <= first["cost_usd"]
    assert near["tokens_in"] <= first["tokens_in"]
    assert near["tokens_out"] <= first["tokens_out"]
    # Fingerprints differ for near-repeat.
    assert task_input_fingerprint({"contact_id": "costed", "text": "Status?"}) != (
        task_input_fingerprint({"contact_id": "costed", "text": "Status update with new detail?"})
    )

    # With memory switched off, the identical repeat is not served from memory.
    import os
    assert memory_enabled() is True
    os.environ["TRIGGER_MEMORY_ENABLED"] = "false"
    try:
        assert memory_enabled() is False
        paid_before_off = paid_calls
        off = await run_with_memory(
            memory,
            tenant_id=tenant,
            user_id=user,
            task_key=task_key,
            task={"contact_id": "costed", "text": "Status?"},
            paid_call=paid,
        )
        assert off["memory_enabled"] is False
        assert off["answered_from_memory"] is False
        assert off["paid_calls"] == 1
        assert paid_calls - paid_before_off == 1
        assert off["cost_usd"] == 0.05 and off["tokens_in"] == 10 and off["tokens_out"] == 3
    finally:
        os.environ.pop("TRIGGER_MEMORY_ENABLED", None)
        assert memory_enabled() is False


def test_recall_cap_never_dearer_than_budget():
    budget = recall_token_budget()
    rows = [
        {
            "id": f"m{i}",
            "kind": "trigger.context",
            "text": ("past entry about the deal " * 40) + str(i),
            "meta": {"task_key": "t", "contact_id": "c"},
        }
        for i in range(20)
    ]
    summary = summarise_recall(rows, budget=budget)
    assert estimate_tokens(summary) <= budget
    capped = attach_capped_recall(
        {"contact_id": "c", "text": "hello"},
        rows,
        task_key="t",
        budget=budget,
    )
    assert capped["memory_context_tokens"] <= budget
    assert capped["memory_context_billed"] is False


def test_apply_corrections_and_secret_refusal():
    corrected = apply_corrections({"contact_id": "A"}, ["use-saved-tone"])
    assert corrected["applied_corrections"] == ["use-saved-tone"]
    assert corrected["answered_from_memory"] is True
    with pytest.raises(ValueError):
        build_memory_text(summary="leak api_key=should-fail")


def test_direct_brain_remains_unavailable_even_with_switch(monkeypatch):
    monkeypatch.setenv("TRIGGER_BRAIN_ENABLED", "true")
    assert brain_enabled() is False


@pytest.mark.asyncio
async def test_categories_populated_from_memory_on_paid_path():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    await memory.remember(
        tenant,
        build_memory_text(
            deal_history=["quoted-500"],
            conversation_context=["asked-shipping"],
            objections=["price-too-high"],
            tone=["direct"],
            handover_notes=["wants-human"],
        ),
        "trigger.receipt",
        "trigger:task:contact-acme",
        meta={"user_id": user, "task_key": "contact-acme", "contact_id": "acme"},
    )
    seen = {}

    async def paid(task):
        seen["categories"] = task.get("memory_categories")
        return {
            **FIXED_COST,
            "result": {
                "deal_history": list((task.get("memory_categories") or {}).get("deal_history") or []),
                "conversation_context": list((task.get("memory_categories") or {}).get("conversation_context") or [])
                + ["new-turn"],
                "objections": list((task.get("memory_categories") or {}).get("objections") or []),
                "tone": list((task.get("memory_categories") or {}).get("tone") or []),
                "handover_notes": list((task.get("memory_categories") or {}).get("handover_notes") or []),
                "contact_id": "acme",
                "text": "draft",
            },
        }

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="contact-acme",
        task={"contact_id": "acme", "text": "Follow up again"},
        paid_call=paid,
    )
    assert receipt["paid_calls"] == 1
    assert "quoted-500" in seen["categories"]["deal_history"]
    assert "price-too-high" in seen["categories"]["objections"]
    assert "wants-human" in seen["categories"]["handover_notes"]
    assert "quoted-500" in receipt["result"]["deal_history"]
    assert "price-too-high" in receipt["result"]["objections"]
    assert "wants-human" in receipt["result"]["handover_notes"]


def test_categories_from_memories_parses_markers():
    rows = [{
        "text": "deal=a,b; context=c; objections=d; tone=e; handover=f",
        "meta": {},
        "kind": "trigger.receipt",
        "tenant_id": "t",
    }]
    cats = categories_from_memories(rows)
    assert cats["deal_history"] == ["a", "b"]
    assert cats["conversation_context"] == ["c"]
    assert cats["objections"] == ["d"]
    assert cats["tone"] == ["e"]
    assert cats["handover_notes"] == ["f"]


@pytest.mark.asyncio
async def test_memory_route_uses_only_tank_even_with_brain_switch(monkeypatch):
    monkeypatch.setenv("TRIGGER_BRAIN_ENABLED", "true")
    calls = []
    tenant = str(uuid4())
    messages = [{"role": "user", "content": "placeholder draft"}]

    class NoDirectHTTP:
        async def get(self, *args, **kwargs):
            raise AssertionError("Product must not call a brain directly")

        async def post(self, *args, **kwargs):
            raise AssertionError("Product must not submit a second model task")

    class FakeTank:
        async def route(self, tenant_id, task_type, request_messages):
            calls.append((tenant_id, task_type, request_messages))
            return {"content": "draft-from-tank", "ledger_id": "placeholder-ledger",
                    "cost_usd": 0.05, "baseline_cost_usd": 0.06}

    routed = await brain_then_route(
        NoDirectHTTP(), FakeTank(), tenant_id=tenant,
        task_type="trigger.write", messages=messages,
    )
    assert calls == [(tenant, "trigger.write", messages)]
    assert routed["content"] == "draft-from-tank"
    assert routed["ledger_id"] == "placeholder-ledger"
    assert routed["cost_usd"] == 0.05
    assert routed["baseline_cost_usd"] == 0.06
    assert routed["brain"] == {"enabled": False, "free_first": True, "code_first": True}


@pytest.mark.asyncio
async def test_write_passes_memory_and_user_populates_categories(monkeypatch):
    """Production write() wiring: memory + user_id engage the bracket."""
    import importlib
    svc = importlib.import_module("trigger.service")

    memory = FakeMemory()
    tenant = uuid4()
    user = str(uuid4())
    await memory.remember(
        str(tenant),
        build_memory_text(deal_history=["prior-deal"], objections=["too-slow"], handover_notes=["call-back"]),
        "trigger.receipt",
        "trigger:task:z",
        meta={"user_id": user, "task_key": "z", "contact_id": "z"},
    )

    class FakeStore:
        def __init__(self, pool):
            self.pool = pool
        async def get(self, tenant_id):
            return None

    class FakeTank:
        async def route(self, tenant_id, task_type, messages):
            return {
                "content": "ok-draft",
                "ledger_id": "L1",
                "cost_usd": 0.05,
                "tokens_in": 10,
                "tokens_out": 3,
                "model": "m",
                "baseline_cost_usd": 0.05,
            }

    class FakeHTTP:
        async def get(self, url, params=None):
            class Resp:
                status_code = 200
                def raise_for_status(self):
                    return None
                def json(self):
                    return {"ok": True, "room": "trigger"}
            return Resp()
        async def post(self, url, json=None):
            class Resp:
                status_code = 404
            return Resp()

    async def fake_check(text, voice, http, tank=None, tenant_id=None):
        return {"ok": True, "issues": []}

    monkeypatch.setattr(svc, "check", fake_check)
    monkeypatch.setattr(svc, "check_limit", lambda report, text, fmt: report)
    monkeypatch.setattr(svc, "report_text", lambda report: "ok")
    monkeypatch.setattr(svc, "VoiceStore", FakeStore)
    monkeypatch.setattr(svc, "legal_request", lambda body: False)

    body = svc.WriteIn(tenant_id=tenant, text="Please follow up with Z", contact_id="z", user_id=user)
    out = await svc.write(
        body, FakeStore(None), FakeTank(), FakeHTTP(), FakeTank(),
        memory=memory, user_id=user, contact_key="z",
    )
    assert out["text"] == "ok-draft"
    receipt = out["memory_receipt"]
    assert receipt["paid_calls"] == 1
    assert "prior-deal" in receipt["result"]["deal_history"]
    assert "too-slow" in receipt["result"]["objections"]
    assert "call-back" in receipt["result"]["handover_notes"]


@pytest.mark.asyncio
async def test_memory_controls_view_edit_forget_and_off(monkeypatch):
    from trigger.gates_memory import FakeMemory, memory_enabled, select_tenant_user_memories, build_memory_text

    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        tenant,
        build_memory_text(summary="keep me", deal_history=["d1"]),
        "trigger.deal",
        "trigger:task:c1",
        meta={"user_id": user, "task_key": "c1"},
    )
    rows = select_tenant_user_memories(memory.rows, tenant_id=tenant, user_id=user)
    assert len(rows) == 1 and rows[0]["id"] == saved["id"]

    # edit via remember
    edited = await memory.remember(
        tenant,
        build_memory_text(summary="edited", deal_history=["d2"]),
        "trigger.deal",
        "trigger:task:c1",
        meta={"user_id": user, "task_key": "c1", "edited": True},
    )
    assert edited["id"] != saved["id"]
    assert any(r["meta"].get("edited") for r in memory.rows)

    # forget: FakeMemory has no forget — add one for the offline contract
    async def forget(memory_id, tenant_id):
        memory.rows[:] = [r for r in memory.rows if not (r["id"] == memory_id and r["tenant_id"] == str(tenant_id))]

    memory.forget = forget
    await memory.forget(saved["id"], tenant)
    assert all(r["id"] != saved["id"] for r in memory.rows)

    import os
    os.environ["TRIGGER_MEMORY_ENABLED"] = "off"
    try:
        assert memory_enabled() is False
    finally:
        os.environ.pop("TRIGGER_MEMORY_ENABLED", None)




def _snapshot(memory):
    import json
    return json.dumps(
        {
            "rows": memory.rows,
            "remembers": getattr(memory, "remembers", None),
            "forgets": getattr(memory, "forgets", None),
            "recalls": getattr(memory, "recalls", None),
        },
        sort_keys=True,
        default=str,
    )


def _settings_snapshot():
    import os
    return {"TRIGGER_MEMORY_ENABLED": os.environ.get("TRIGGER_MEMORY_ENABLED")}


def _fixture_key() -> str:
    """Test-only room key generated inside the test process; never a real secret."""
    import secrets
    return "placeholder-" + secrets.token_hex(16)


def _sign_headers(key: str, *, method: str, path: str, tenant, user, body: bytes = b""):
    from product_identity import sign, User, HEADER
    token = sign("trigger", User(str(tenant), str(user), "member"), method, path, body, key=key)
    return {"X-Tank-Key": key, HEADER: token}



async def _signed_request(client, key, *, method, path, tenant, user, json_body=None, params=None):
    import json as json_lib
    body = b""
    if json_body is not None:
        body = json_lib.dumps(json_body, separators=(",", ":"), sort_keys=True).encode()
    target = str(httpx.URL(path, params=params)) if params else path
    headers = _sign_headers(key, method=method, path=target, tenant=tenant, user=user, body=body)
    if method.upper() == "GET":
        return await client.get(path, params=params, headers=headers)
    headers = {**headers, "Content-Type": "application/json"}
    return await client.request(
        method.upper(), path, params=params, headers=headers, content=body,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "control,other_kind",
    [
        ("view", "user"),
        ("view", "tenant"),
        ("edit", "user"),
        ("edit", "tenant"),
        ("forget", "user"),
        ("forget", "tenant"),
        ("switch", "user"),
        ("switch", "tenant"),
    ],
)
async def test_memory_controls_refuse_foreign_scope_unchanged(control, other_kind, monkeypatch):
    """Each control refuses other-user and other-tenant over signed HTTP; store unchanged."""
    import httpx
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setattr(room.app.state, "missing_settings", [], raising=False)

    memory = FakeMemory()
    owner_tenant, other_tenant = uuid4(), uuid4()
    owner_user, other_user = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        str(owner_tenant),
        build_memory_text(summary="owner-private", deal_history=["keep"]),
        "trigger.deal",
        "trigger:task:own",
        meta={"user_id": owner_user, "task_key": "own"},
    )
    await memory.remember(
        str(owner_tenant),
        build_memory_text(summary="receipt-row", receipt="cost=0"),
        "trigger.receipt",
        "trigger:task:own",
        meta={"user_id": owner_user, "task_key": "own"},
    )
    room.app.state.memory = memory
    before = _snapshot(memory)
    before_settings = _settings_snapshot()

    if other_kind == "user":
        signed_tenant, signed_user = owner_tenant, other_user
        target_tenant, spoof_user = owner_tenant, owner_user
    else:
        signed_tenant, signed_user = other_tenant, owner_user
        target_tenant, spoof_user = owner_tenant, owner_user

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        if control == "view":
            # Signature is for signed_*; request targets owner scope → refuse.
            response = await _signed_request(
                client, key, method="GET", path="/memory/records",
                tenant=signed_tenant, user=signed_user,
                params={"tenant_id": str(target_tenant), "user_id": spoof_user},
            )
        elif control == "edit":
            response = await _signed_request(
                client, key, method="POST", path="/memory/edit",
                tenant=signed_tenant, user=signed_user,
                json_body={
                    "tenant_id": str(target_tenant),
                    "text": build_memory_text(summary="hijack"),
                    "kind": "trigger.deal",
                    "source": "trigger:task:own",
                    "user_id": spoof_user,
                    "memory_id": saved["id"],
                },
            )
        elif control == "forget":
            response = await _signed_request(
                client, key, method="POST", path="/memory/forget",
                tenant=signed_tenant, user=signed_user,
                json_body={
                    "tenant_id": str(target_tenant),
                    "memory_id": saved["id"],
                    "user_id": spoof_user,
                },
            )
        else:
            response = await _signed_request(
                client, key, method="POST", path="/memory/switch",
                tenant=signed_tenant, user=signed_user,
                json_body={
                    "tenant_id": str(target_tenant),
                    "enabled": False,
                    "user_id": spoof_user,
                },
            )

    assert response.status_code == (401 if other_kind == "tenant" else 403), response.text
    assert _snapshot(memory) == before
    assert _settings_snapshot() == before_settings
    assert any(r["id"] == saved["id"] for r in memory.rows)
    assert memory.forgets == 0
    assert not any("hijack" in str(r.get("text", "")) for r in memory.rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("flaw", ["unsigned", "wrong_sig", "other_user"])
async def test_memory_controls_refuse_bad_signatures_unchanged(flaw, monkeypatch):
    """Unsigned, wrongly signed, and signed-for-another-user requests change nothing."""
    import hashlib
    import hmac
    import httpx
    import json as json_lib
    import time
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setattr(room.app.state, "missing_settings", [], raising=False)
    memory = FakeMemory()
    tenant = uuid4()
    owner, other = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        str(tenant), build_memory_text(summary="owner-private"),
        "trigger.deal", "trigger:task:own", meta={"user_id": owner},
    )
    room.app.state.memory = memory
    before = _snapshot(memory)
    body = json_lib.dumps({
        "tenant_id": str(tenant),
        "memory_id": saved["id"],
        "user_id": owner,
    }, separators=(",", ":"), sort_keys=True).encode()
    path = "/memory/forget"
    ts = str(int(time.time()))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        if flaw == "unsigned":
            headers = {
                "X-Tank-Key": key,
                "X-Tervory-Tenant": str(tenant),
                "X-Tervory-User": owner,
                "Content-Type": "application/json",
            }
        elif flaw == "wrong_sig":
            headers = {
                "X-Tank-Key": key,
                "X-Lifecycle-Timestamp": ts,
                "X-Lifecycle-Signature": "0" * 64,
                "X-Tervory-Tenant": str(tenant),
                "X-Tervory-User": owner,
                "Content-Type": "application/json",
            }
        else:
            # Signature binds `other`, but headers/body claim `owner`.
            message = f"{ts}\nPOST\n{path}\n{tenant}\n{other}\n".encode() + body
            headers = {
                "X-Tank-Key": key,
                "X-Lifecycle-Timestamp": ts,
                "X-Lifecycle-Signature": hmac.new(key.encode(), message, hashlib.sha256).hexdigest(),
                "X-Tervory-Tenant": str(tenant),
                "X-Tervory-User": owner,
                "Content-Type": "application/json",
            }
        response = await client.post(path, headers=headers, content=body)

    assert response.status_code == 401, response.text
    assert _snapshot(memory) == before
    assert memory.forgets == 0
    assert any(r["id"] == saved["id"] for r in memory.rows)


@pytest.mark.asyncio
async def test_memory_edit_refuses_other_users_memory_id_same_tenant(monkeypatch):
    """EDIT with another user's memory_id must refuse; no insert."""
    import httpx
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setattr(room.app.state, "missing_settings", [], raising=False)
    memory = FakeMemory()
    tenant = uuid4()
    owner_user, other_user = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        str(tenant), build_memory_text(summary="owner-private"),
        "trigger.deal", "trigger:task:own", meta={"user_id": owner_user},
    )
    room.app.state.memory = memory
    before = _snapshot(memory)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        response = await _signed_request(
            client, key, method="POST", path="/memory/edit",
            tenant=tenant, user=other_user,
            json_body={
                "tenant_id": str(tenant),
                "text": build_memory_text(summary="hijack"),
                "kind": "trigger.deal",
                "source": "trigger:task:own",
                "user_id": other_user,
                "memory_id": saved["id"],
            },
        )
    assert response.status_code == 403, response.text
    assert _snapshot(memory) == before
    assert not any("hijack" in str(r.get("text", "")) for r in memory.rows)


@pytest.mark.asyncio
async def test_memory_controls_signed_own_identity_succeeds(monkeypatch):
    """Positive case: request validly signed for the caller's own identity succeeds."""
    import httpx
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setattr(room.app.state, "missing_settings", [], raising=False)
    memory = FakeMemory()
    tenant = uuid4()
    user = str(uuid4())
    saved = await memory.remember(
        str(tenant), build_memory_text(summary="mine"),
        "trigger.deal", "trigger:task:own", meta={"user_id": user},
    )
    room.app.state.memory = memory
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        viewed = await _signed_request(
            client, key, method="GET", path="/memory/records",
            tenant=tenant, user=user,
            params={"tenant_id": str(tenant)},
        )
        assert viewed.status_code == 200, viewed.text
        assert viewed.json()["count"] == 1
        forgotten = await _signed_request(
            client, key, method="POST", path="/memory/forget",
            tenant=tenant, user=user,
            json_body={"tenant_id": str(tenant), "memory_id": saved["id"]},
        )
        assert forgotten.status_code == 200, forgotten.text
    assert not any(r["id"] == saved["id"] for r in memory.rows)


@pytest.mark.asyncio
async def test_memory_switch_off_is_per_signed_in_user(monkeypatch):
    import httpx
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setattr(room.app.state, "missing_settings", [], raising=False)
    memory = FakeMemory()
    tenant = uuid4()
    user_a, user_b = str(uuid4()), str(uuid4())
    await memory.remember(
        str(tenant), build_memory_text(summary="visible"),
        "trigger.deal", "trigger:task:a", meta={"user_id": user_a},
    )
    room.app.state.memory = memory
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        off = await _signed_request(
            client, key, method="POST", path="/memory/switch",
            tenant=tenant, user=user_a,
            json_body={"tenant_id": str(tenant), "enabled": False},
        )
        assert off.status_code == 200, off.text
        assert off.json()["memory_enabled"] is False
        viewed = await _signed_request(
            client, key, method="GET", path="/memory/records",
            tenant=tenant, user=user_a,
            params={"tenant_id": str(tenant)},
        )
        assert viewed.status_code == 200
        assert viewed.json()["memory_enabled"] is False and viewed.json()["count"] == 0
        viewed_b = await _signed_request(
            client, key, method="GET", path="/memory/records",
            tenant=tenant, user=user_b,
            params={"tenant_id": str(tenant)},
        )
        assert viewed_b.status_code == 200
        assert viewed_b.json()["memory_enabled"] is True
        assert viewed_b.json()["count"] == 0



@pytest.mark.asyncio
async def test_per_user_memory_off_blocks_exact_repeat_other_user_unaffected():
    """Per-user switch-off: no recall/remember/exact-repeat for that user; peers unaffected."""
    memory = FakeMemory()
    tenant = str(uuid4())
    user_a, user_b = str(uuid4()), str(uuid4())
    task_key = "deal-status"
    paid_calls = {"n": 0}

    async def paid(task):
        paid_calls["n"] += 1
        return {
            "cost_usd": 0.05,
            "tokens_in": 10,
            "tokens_out": 3,
            "result": {"text": "ok", "approved": True},
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user_a,
        task_key=task_key,
        task={"contact_id": "c1", "text": "Status?"},
        paid_call=paid,
    )
    assert first["paid_calls"] == 1 and first["answered_from_memory"] is False

    await memory.remember(
        tenant,
        MEMORY_OFF_TEXT,
        MEMORY_OFF_KIND,
        MEMORY_OFF_SOURCE,
        meta={"user_id": user_a, "memory_off": True},
    )
    assert memory_off_from_rows(memory.rows, tenant_id=tenant, user_id=user_a) is True
    assert memory_off_from_rows(memory.rows, tenant_id=tenant, user_id=user_b) is False

    before_remembers = memory.remembers
    before_recalls = memory.recalls
    paid_before = paid_calls["n"]
    off = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user_a,
        task_key=task_key,
        task={"contact_id": "c1", "text": "Status?"},
        paid_call=paid,
    )
    assert off["answered_from_memory"] is False
    assert off["paid_calls"] == 1
    assert paid_calls["n"] - paid_before == 1
    assert off["memory_enabled"] is False
    assert any(s.get("action") == "memory_off" for s in off["steps"])
    assert memory.recalls == before_recalls
    assert memory.remembers == before_remembers

    paid_before_b = paid_calls["n"]
    other = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user_b,
        task_key=task_key,
        task={"contact_id": "c1", "text": "Status?"},
        paid_call=paid,
    )
    assert other["memory_enabled"] is True
    assert other["answered_from_memory"] is False
    assert other["paid_calls"] == 1
    assert paid_calls["n"] - paid_before_b == 1

    paid_before_b2 = paid_calls["n"]
    other2 = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user_b,
        task_key=task_key,
        task={"contact_id": "c1", "text": "Status?"},
        paid_call=paid,
    )
    assert other2["answered_from_memory"] is True
    assert other2["paid_calls"] == 0
    assert paid_calls["n"] == paid_before_b2



def test_owned_memory_row_requires_tenant_and_user():
    rows = [{
        "id": "mem-1",
        "tenant_id": "t1",
        "meta": {"user_id": "u1"},
        "text": "x",
    }]
    assert owned_memory_row(rows, memory_id="mem-1", tenant_id="t1", user_id="u1")["id"] == "mem-1"
    assert owned_memory_row(rows, memory_id="mem-1", tenant_id="t1", user_id="u2") is None
    assert owned_memory_row(rows, memory_id="mem-1", tenant_id="t2", user_id="u1") is None
    assert owned_memory_row(rows, memory_id="missing", tenant_id="t1", user_id="u1") is None


@pytest.mark.asyncio
async def test_post_write_uses_signed_in_actor_not_body_user(monkeypatch):
    import httpx
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    captured = {}

    async def fake_write(body, store, tank, http, skills=None, *, memory=None, user_id=None, contact_key=None):
        captured["user_id"] = user_id
        captured["memory"] = memory
        return {"text": "ok"}

    monkeypatch.setattr(room, "write", fake_write)
    monkeypatch.setattr(room, "VoiceStore", lambda pool: object())
    room.app.state.memory = FakeMemory()
    room.app.state.pool = object()
    room.app.state.tank = object()
    room.app.state.http = object()
    room.app.state.missing_settings = []

    tenant = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        # Body user spoof with signature for trusted-user → scope refuse (403)
        spoof = await _signed_request(
            client, key, method="POST", path="/write",
            tenant=tenant, user="trusted-user",
            json_body={
                "tenant_id": str(tenant),
                "text": "Hello world draft please",
                "contact_id": "c1",
                "user_id": "spoofed",
            },
        )
        assert spoof.status_code == 403, spoof.text
        assert "user_id" not in captured
        ok = await _signed_request(
            client, key, method="POST", path="/write",
            tenant=tenant, user="trusted-user",
            json_body={
                "tenant_id": str(tenant),
                "text": "Hello world draft please",
                "contact_id": "c1",
            },
        )
        assert ok.status_code == 200, ok.text
        assert captured["user_id"] == "trusted-user"



class _OutageMemory(FakeMemory):
    """FakeMemory whose chosen operation fails the way the chassis MemoryClient does."""

    def __init__(self, broken: str, error: BaseException | None = None) -> None:
        super().__init__()
        self.broken = broken
        self.error = error or RuntimeError("hermes unreachable")
        self.records_calls = 0

    async def records(self, *args, **kwargs):
        self.records_calls += 1
        if self.broken == "records":
            raise self.error
        return await super().records(*args, **kwargs)

    async def recall(self, *args, **kwargs):
        if self.broken == "recall":
            self.recalls += 1
            raise self.error
        return await super().recall(*args, **kwargs)

    async def remember(self, *args, **kwargs):
        if self.broken == "remember":
            raise self.error
        return await super().remember(*args, **kwargs)


async def _seed_approved_repeat(memory, tenant, user, task_key, task):
    async def paid(_task):
        return _paid_result("seed")

    broken, memory.broken = memory.broken, ""
    try:
        first = await run_with_memory(
            memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid,
        )
        repeat = await run_with_memory(
            memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid,
        )
    finally:
        memory.broken = broken
    assert first["paid_calls"] == 1 and repeat["answered_from_memory"] is True and repeat["paid_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [RuntimeError("hermes unreachable"), RuntimeError("hermes answered 503"), ConnectionError("down"), TimeoutError()],
    ids=["unreachable", "503", "connection", "timeout"],
)
async def test_memory_outage_on_recall_pays_and_never_serves_stored_repeat(error):
    """Memory outage: the answer comes from the paid route; no stored repeat; nothing remembered."""
    memory = _OutageMemory("recall", error)
    tenant, user, task_key = str(uuid4()), str(uuid4()), "outage-recall"
    task = {"contact_id": "c-out", "text": "Same question?"}
    await _seed_approved_repeat(memory, tenant, user, task_key, task)
    rows_before = len(memory.rows)
    calls = {"n": 0}

    async def paid(_task):
        calls["n"] += 1
        return _paid_result("outage")

    receipt = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid,
    )
    assert receipt["memory_unavailable"] is True
    assert receipt["memory_enabled"] is False
    assert receipt["answered_from_memory"] is False
    assert receipt["paid_calls"] == 1 and calls["n"] == 1
    assert receipt["cost_usd"] == 0.05 and receipt["tokens_in"] == 10 and receipt["tokens_out"] == 3
    assert receipt["result"]["deal_history"] == ["outage"]
    assert receipt["memory_error"] == type(error).__name__
    assert {"action": "memory_off", "reason": "outage"} in receipt["steps"]
    assert "exact_repeat_from_memory" not in [s["action"] for s in receipt["steps"]]
    assert len(memory.rows) == rows_before


@pytest.mark.asyncio
async def test_memory_outage_on_switch_check_does_not_read_as_memory_on():
    """If the per-user switch cannot be read, recall is not attempted and nothing is served or stored."""
    memory = _OutageMemory("records")
    tenant, user, task_key = str(uuid4()), str(uuid4()), "outage-records"
    task = {"contact_id": "c-rec", "text": "Hello?"}
    await _seed_approved_repeat(memory, tenant, user, task_key, task)
    recalls_before, rows_before = memory.recalls, len(memory.rows)

    async def paid(_task):
        return _paid_result("records-down")

    receipt = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid,
    )
    assert receipt["memory_unavailable"] is True
    assert receipt["answered_from_memory"] is False
    assert receipt["paid_calls"] == 1
    assert memory.recalls == recalls_before
    assert len(memory.rows) == rows_before


@pytest.mark.asyncio
async def test_memory_outage_on_remember_keeps_the_paid_answer_and_receipt():
    memory = _OutageMemory("remember")
    tenant, user = str(uuid4()), str(uuid4())

    async def paid(_task):
        return _paid_result("kept")

    receipt = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="outage-remember",
        task={"contact_id": "c-rem", "text": "Write it"}, paid_call=paid,
    )
    assert receipt["paid_calls"] == 1 and receipt["cost_usd"] == 0.05
    assert receipt["result"]["deal_history"] == ["kept"]
    assert receipt["memory_unavailable"] is True
    assert receipt["steps"][-1] == {"action": "remember", "status": "unavailable", "source": "trigger:task:outage-remember"}
    assert memory.rows == []

    # Memory back: the same task pays once more (nothing was stored), then repeats free.
    memory.broken = ""
    again = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="outage-remember",
        task={"contact_id": "c-rem", "text": "Write it"}, paid_call=paid,
    )
    assert again["paid_calls"] == 1 and again["memory_unavailable"] is False
    free = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="outage-remember",
        task={"contact_id": "c-rem", "text": "Write it"}, paid_call=paid,
    )
    assert free["paid_calls"] == 0 and free["answered_from_memory"] is True


@pytest.mark.asyncio
async def test_memory_programming_errors_and_scope_errors_are_not_outages():
    from trigger.gates_memory import MemoryScopeError, require_memory_scope

    async def paid(_task):
        return _paid_result("never")

    broken = _OutageMemory("recall", TypeError("unexpected keyword"))
    with pytest.raises(TypeError):
        await run_with_memory(
            broken, tenant_id=str(uuid4()), user_id="u1", task_key="k", task={"text": "x"}, paid_call=paid,
        )
    for tenant, user in (("", "u1"), (str(uuid4()), ""), (None, "u1"), (str(uuid4()), None), ("  ", "u1")):
        with pytest.raises(MemoryScopeError):
            require_memory_scope(tenant, user)
        with pytest.raises(MemoryScopeError):
            await run_with_memory(
                FakeMemory(), tenant_id=tenant, user_id=user, task_key="k", task={"text": "x"}, paid_call=paid,
            )
    assert require_memory_scope(" t ", " u ") == ("t", "u")


@pytest.mark.asyncio
async def test_post_write_memory_outage_still_drafts_and_flags_it(monkeypatch):
    """/write with Hermes down: 200 with a paid draft, no memory passed on, memory_unavailable set."""
    import httpx
    from trigger import app as room

    key = _fixture_key()
    monkeypatch.setenv("TANK_KEY", key)
    captured = {}

    async def fake_write(body, store, tank, http, skills=None, *, memory=None, user_id=None, contact_key=None):
        captured["memory"] = memory
        captured["user_id"] = user_id
        return {"text": "paid-draft", "cost_usd": 0.05}

    down = _OutageMemory("records")
    monkeypatch.setattr(room, "write", fake_write)
    monkeypatch.setattr(room, "VoiceStore", lambda pool: object())
    room.app.state.memory = down
    room.app.state.pool = object()
    room.app.state.tank = object()
    room.app.state.http = object()
    room.app.state.missing_settings = []

    tenant = uuid4()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=room.app), base_url="http://room"
    ) as client:
        out = await _signed_request(
            client, key, method="POST", path="/write",
            tenant=tenant, user="outage-user",
            json_body={"tenant_id": str(tenant), "text": "Hello world draft please", "contact_id": "c1"},
        )
    assert out.status_code == 200, out.text
    assert out.json()["text"] == "paid-draft"
    assert out.json()["memory_unavailable"] is True
    assert captured["memory"] is None
    assert captured["user_id"] == "outage-user"
    assert down.records_calls == 1


@pytest.fixture(autouse=True)
def enabled_memory_layer(monkeypatch):
    monkeypatch.setenv("TRIGGER_MEMORY_ENABLED", "true")
    monkeypatch.setenv("TRIGGER_BRAIN_ENABLED", "true")


@pytest.fixture(autouse=True)
def assertion_nonce_store(monkeypatch):
    from chassis import user_assertion
    class Nonces:
        def __init__(self, pool, product):
            self.pool, self.used = pool, set()
        async def claim(self, tenant, nonce, expires):
            key = (tenant, nonce)
            if key in self.used:
                return False
            self.used.add(key)
            return True
    monkeypatch.setattr(user_assertion, "PostgresNonces", Nonces)
    from trigger import app as room
    monkeypatch.setattr(room.app.state, "pool", object(), raising=False)
    monkeypatch.setattr(room.app.state, "product_nonce_stores", {}, raising=False)
