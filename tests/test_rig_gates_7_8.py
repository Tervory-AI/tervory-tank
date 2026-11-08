"""Gates 7+8 offline: memory bracket, corrections, isolation, repeat cost, controls."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents"))
sys.path.insert(0, str(ROOT / "vendor" / "tervory-tank" / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "vendor" / "tervory-tank"))

from rig_memory_fakes import FakeMemory, FIXED_FAKE_PER_CALL
from gates_memory import (
    MEMORY_OFF_KIND,
    MEMORY_OFF_SOURCE,
    MEMORY_OFF_TEXT,
    apply_corrections,
    build_memory_text,
    memory_enabled,
    memory_off_from_rows,
    owned_memory_row,
    run_with_memory,
    select_tenant_user_memories,
    task_input_fingerprint,
)
from memory_api import attach_memory_routes
from rig_brain_client import brain_enabled


@pytest.fixture(autouse=True)
def opted_in_memory(monkeypatch):
    # These unit scenarios explicitly exercise opt-in behavior, never deployment defaults.
    monkeypatch.setenv("RIG_MEMORY_ENABLED", "true")


FIXED_COST = dict(FIXED_FAKE_PER_CALL)


def _paid_result(tag: str = "run") -> dict:
    return {
        **FIXED_COST,
        "result": {
            "past_builds": [tag],
            "store_preferences": ["prefer-in-stock"],
            "approved_parts": ["barrel-16"],
            "approved_fits": ["optic-low"],
            "quotes": ["q-100"],
            "rejected_designs": ["over-budget"],
        },
    }


@pytest.mark.asyncio
async def test_product_request_brain_route_receipt_then_memory():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "rig.build"

    async def paid(task):
        return {
            "cost_usd": 0.05,
            "tokens_in": 10,
            "tokens_out": 3,
            "result": {
                "past_builds": ["ar15-budget"],
                "store_preferences": ["local-pickup"],
                "approved_parts": ["lower-a"],
                "approved_fits": ["stock-b"],
                "quotes": ["quote-1"],
                "rejected_designs": ["magpul-too-dear"],
            },
        }

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"query": "build a budget AR", "store": "acme"},
        paid_call=paid,
    )
    assert [step["action"] for step in receipt["steps"]] == [
        "recall",
        "brain_route",
        "remember",
    ]
    assert receipt["paid_calls"] == 1 and receipt["cost_usd"] == 0.05
    assert receipt["tokens_in"] == 10 and receipt["tokens_out"] == 3
    assert memory.remembers == 1 and memory.rows[0]["tenant_id"] == tenant
    assert memory.rows[0]["meta"]["user_id"] == user
    assert "builds=ar15-budget" in memory.rows[0]["text"]
    assert "parts=lower-a" in memory.rows[0]["text"]
    assert "rejected=magpul-too-dear" in memory.rows[0]["text"]


@pytest.mark.asyncio
async def test_correction_applies_next_time_with_no_paid_call():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "rig.fit"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            **FIXED_COST,
            "result": {
                "approved_fits": ["rail-high"],
                "correction": "prefer-low-mount",
                "past_builds": ["fit-1"],
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"query": "optic fit", "product_id": "p1"},
        paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1

    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"query": "optic fit", "product_id": "p1"},
        paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert "prefer-low-mount" in second["result"]["applied_corrections"]
    assert "apply_correction" in [step["action"] for step in second["steps"]]


@pytest.mark.asyncio
async def test_second_user_and_second_tenant_see_nothing():
    memory = FakeMemory()
    tenant_a, user_a = str(uuid4()), str(uuid4())
    tenant_b, user_b = str(uuid4()), str(uuid4())

    await memory.remember(
        tenant_a,
        build_memory_text(summary="private build", past_builds=["private-build"]),
        "rig.build",
        "rig:task:private",
        meta={"user_id": user_a, "task_key": "private"},
    )
    foreign = select_tenant_user_memories(memory.rows, tenant_id=tenant_b, user_id=user_b)
    other_user = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_b)
    owner = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_a)
    assert foreign == [] and other_user == [] and len(owner) == 1

    async def paid(_task):
        return {**FIXED_COST, "result": {"past_builds": ["x"]}}

    outsider = await run_with_memory(
        memory,
        tenant_id=tenant_b,
        user_id=user_b,
        task_key="private",
        task={"query": "Other"},
        paid_call=paid,
    )
    assert outsider["answered_from_memory"] is False
    assert outsider["paid_calls"] == 1


@pytest.mark.asyncio
async def test_uncorrected_identical_task_paid_calls_one_then_zero():
    """Fixed fake per-call cost/tokens; exact repeat makes ZERO paid calls."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "rig.quote"
    task = {"query": "quote lower", "store": "acme"}
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        # Fixed per-call fixture amounts — never vary by call count.
        return {
            "cost_usd": 0.05,
            "tokens_in": 10,
            "tokens_out": 3,
            "result": {
                "quotes": ["quote-fixed"],
                "past_builds": ["q1"],
                "store_preferences": ["email-quotes"],
                "approved_parts": ["lower"],
                "approved_fits": ["none"],
                "rejected_designs": ["none"],
            },
        }

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["cost_usd"] == 0.05 and first["tokens_in"] == 10 and first["tokens_out"] == 3

    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert second["would_have_cost"]["cost_usd"] == 0.05
    assert second["would_have_cost"]["tokens_in"] == 10
    assert second["would_have_cost"]["tokens_out"] == 3
    assert "exact_repeat_from_memory" in [s["action"] for s in second["steps"]]

    # Changed input must miss and pay again.
    third = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"query": "quote upper", "store": "acme"},
        paid_call=paid,
    )
    assert third["paid_calls"] == 1 and paid_calls == 2
    assert third["cost_usd"] == 0.05 and third["tokens_in"] == 10 and third["tokens_out"] == 3


@pytest.mark.asyncio
async def test_per_user_memory_off_and_forget():
    memory = FakeMemory()
    tenant = str(uuid4())
    user_a, user_b = str(uuid4()), str(uuid4())
    task_key = "rig.build"
    task = {"query": "shared"}
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {**FIXED_COST, "result": {"past_builds": ["shared"]}}

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_a, task_key=task_key, task=task, paid_call=paid
    )
    assert first["paid_calls"] == 1

    await memory.remember(
        tenant,
        build_memory_text(summary=MEMORY_OFF_TEXT, receipt="control=off"),
        MEMORY_OFF_KIND,
        MEMORY_OFF_SOURCE,
        meta={"user_id": user_a, "task_key": "memory_control", "control": "off"},
    )
    assert memory_off_from_rows(memory.rows, tenant_id=tenant, user_id=user_a) is True

    off_a = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_a, task_key=task_key, task=task, paid_call=paid
    )
    assert off_a["paid_calls"] == 1 and off_a["answered_from_memory"] is False

    first_b = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_b, task_key=task_key, task=task, paid_call=paid
    )
    assert first_b["paid_calls"] == 1
    second_b = await run_with_memory(
        memory, tenant_id=tenant, user_id=user_b, task_key=task_key, task=task, paid_call=paid
    )
    assert second_b["answered_from_memory"] is True and second_b["paid_calls"] == 0


def test_brain_switch_defaults_and_url(monkeypatch):
    monkeypatch.delenv("RIG_BRAIN_ENABLED", raising=False)
    monkeypatch.delenv("RIG_BRAIN_URL", raising=False)
    # t9u: NOTHING SWITCHES ON — default false; opt-in compose profile separate.
    assert brain_enabled() is False
    import rig_brain_client
    assert not hasattr(rig_brain_client, "brain_url")
    assert "delegate_task" in (ROOT / "agents/rig/rig_brain_client.py").read_text()
    monkeypatch.setenv("RIG_BRAIN_ENABLED", "true")
    assert brain_enabled() is True
    monkeypatch.setenv("RIG_BRAIN_ENABLED", "false")
    assert brain_enabled() is False


def test_fingerprint_and_secrets():
    a = task_input_fingerprint({"query": "x", "store": "s"})
    b = task_input_fingerprint({"query": "x", "store": "s"})
    c = task_input_fingerprint({"query": "y", "store": "s"})
    assert a == b and a != c
    with pytest.raises(ValueError):
        build_memory_text(summary="leak api_key=should-fail")
    corrected = apply_corrections({"query": "A"}, ["use-oem"])
    assert corrected["applied_corrections"] == ["use-oem"]


def test_memory_enabled_env(monkeypatch):
    monkeypatch.delenv("RIG_MEMORY_ENABLED", raising=False)
    assert memory_enabled() is False
    monkeypatch.setenv("RIG_MEMORY_ENABLED", "true")
    assert memory_enabled() is True
    monkeypatch.setenv("RIG_MEMORY_ENABLED", "off")
    assert memory_enabled() is False


def _snapshot(memory):
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
    return {"RIG_MEMORY_ENABLED": os.environ.get("RIG_MEMORY_ENABLED")}


def _fixture_key() -> str:
    import secrets
    return "fixture-" + secrets.token_hex(16)


def _make_app(memory, key: str, monkeypatch):
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_KEY_RIG", key)
    app = FastAPI()
    class Nonces:
        pool = object()
        seen = set()
        async def claim(self, tenant, nonce, expires):
            if (tenant, nonce) in self.seen:
                return False
            self.seen.add((tenant, nonce))
            return True
    nonces = Nonces()
    app.state.pool = nonces.pool
    app.state.product_nonce_stores = {"rig": nonces}
    app.state.memory = memory
    attach_memory_routes(app)
    return app


async def _signed_request(client, key, *, method, path, tenant, user, json_body=None, params=None):
    body = b""
    if json_body is not None:
        body = json.dumps(json_body, separators=(",", ":"), sort_keys=True).encode()
    from chassis.user_assertion import HEADER, SignedUser, sign_assertion
    target = httpx.URL("http://rig" + path, params=params).raw_path.decode()
    headers = {"X-Tervory-Tenant": str(tenant), HEADER: sign_assertion("rig", SignedUser(str(tenant), str(user), "member"),
                                     method, target, body, key=key)}
    if method.upper() == "GET":
        return await client.get(path, params=params, headers=headers)
    headers = {**headers, "Content-Type": "application/json"}
    return await client.request(method.upper(), path, params=params, headers=headers, content=body)


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
    """8 denial cases: 4 ops x other-user / other-tenant; store/settings unchanged."""
    key = _fixture_key()
    memory = FakeMemory()
    owner_tenant, other_tenant = uuid4(), uuid4()
    owner_user, other_user = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        str(owner_tenant),
        build_memory_text(summary="owner-private", past_builds=["keep"]),
        "rig.build",
        "rig:task:own",
        meta={"user_id": owner_user, "task_key": "own"},
    )
    await memory.remember(
        str(owner_tenant),
        build_memory_text(summary="receipt-row", receipt="cost=0"),
        "rig.receipt",
        "rig:task:own",
        meta={"user_id": owner_user, "task_key": "own"},
    )
    app = _make_app(memory, key, monkeypatch)
    before = _snapshot(memory)
    before_settings = _settings_snapshot()

    if other_kind == "user":
        signed_tenant, signed_user = owner_tenant, other_user
        target_tenant, spoof_user = owner_tenant, owner_user
    else:
        signed_tenant, signed_user = other_tenant, owner_user
        target_tenant, spoof_user = owner_tenant, owner_user

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://room") as client:
        if control == "view":
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
                    "kind": "rig.build",
                    "source": "rig:task:own",
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

    assert response.status_code == 403, response.text
    assert _snapshot(memory) == before
    assert _settings_snapshot() == before_settings
    assert any(r["id"] == saved["id"] for r in memory.rows)
    assert memory.forgets == 0
    assert not any("hijack" in str(r.get("text", "")) for r in memory.rows)


@pytest.mark.asyncio
@pytest.mark.parametrize("flaw", ["unsigned", "wrong_sig", "missing_user"])
async def test_memory_controls_refuse_forged_or_missing_identity(flaw, monkeypatch):
    key = _fixture_key()
    memory = FakeMemory()
    tenant = uuid4()
    owner = str(uuid4())
    saved = await memory.remember(
        str(tenant), build_memory_text(summary="owner-private"),
        "rig.build", "rig:task:own", meta={"user_id": owner},
    )
    app = _make_app(memory, key, monkeypatch)
    before = _snapshot(memory)
    body = json.dumps({
        "tenant_id": str(tenant),
        "memory_id": saved["id"],
        "user_id": owner,
    }, separators=(",", ":"), sort_keys=True).encode()
    path = "/memory/forget"
    ts = str(int(time.time()))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://room") as client:
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
            headers = {
                "X-Tank-Key": key,
                "X-Lifecycle-Timestamp": ts,
                "X-Lifecycle-Signature": hmac.new(
                    key.encode(),
                    f"{ts}\nPOST\n{path}\n{tenant}\n\n".encode() + body,
                    hashlib.sha256,
                ).hexdigest(),
                "X-Tervory-Tenant": str(tenant),
                "X-Tervory-User": "",
                "Content-Type": "application/json",
            }
        response = await client.post(path, headers=headers, content=body)

    assert response.status_code == 401, response.text
    assert _snapshot(memory) == before
    assert memory.forgets == 0


@pytest.mark.asyncio
async def test_memory_controls_signed_own_identity_succeeds(monkeypatch):
    key = _fixture_key()
    memory = FakeMemory()
    tenant = uuid4()
    user = str(uuid4())
    saved = await memory.remember(
        str(tenant), build_memory_text(summary="mine", past_builds=["b1"]),
        "rig.build", "rig:task:own", meta={"user_id": user},
    )
    app = _make_app(memory, key, monkeypatch)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://room") as client:
        viewed = await _signed_request(
            client, key, method="GET", path="/memory/records",
            tenant=tenant, user=user, params={"tenant_id": str(tenant)},
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


def test_owned_memory_row_helper():
    rows = [{"id": "1", "tenant_id": "t1", "meta": {"user_id": "u1"}}]
    assert owned_memory_row(rows, memory_id="1", tenant_id="t1", user_id="u1")
    assert owned_memory_row(rows, memory_id="1", tenant_id="t1", user_id="u2") is None
    assert owned_memory_row(rows, memory_id="missing", tenant_id="t1", user_id="u1") is None


@pytest.mark.asyncio
async def test_brain_actually_called_when_enabled(monkeypatch):
    from rig_brain_client import brain_then_route

    monkeypatch.setenv("RIG_BRAIN_ENABLED", "true")
    from actor_context import set_verified_actor, reset_verified_actor
    tenant, user = str(uuid4()), "placeholder-owner"
    calls = {"http": 0, "tasks": 0, "route": 0}

    class FakeHttp:
        async def get(self, *args, **kwargs):
            calls["http"] += 1
            raise AssertionError("Private discovery belongs to Tank")

    class FakeTank:
        async def delegate_task(self, actor, run_id, kind, payload, recall):
            calls["tasks"] += 1
            assert actor.tenant_id == tenant and actor.user_id == user and kind == "rig.ask"
            assert payload == {"messages": [{"role": "user", "content": "q"}]}
            return {"result": {"content": "brain-answer"}, "receipt": {
                "task_id": run_id, "status": "done", "model_receipts": [],
                "cost_usd": 0, "tokens_in": 0, "tokens_out": 0}}

        async def route(self, *args):
            calls["route"] += 1
            raise AssertionError("Accepted worker work must not pay twice")

    token = set_verified_actor(tenant_id=tenant, user_id=user)
    try:
        routed = await brain_then_route(FakeHttp(), FakeTank(), tenant_id=tenant,
            task_type="rig.ask", messages=[{"role": "user", "content": "q"}])
    finally:
        reset_verified_actor(token)
    assert calls == {"http": 0, "tasks": 1, "route": 0}
    assert routed["brain"]["called"] is True and routed["brain"]["enabled"] is True
    assert routed["content"] == "brain-answer"


@pytest.mark.asyncio
async def test_brain_not_called_when_disabled(monkeypatch):
    from rig_brain_client import brain_then_route

    monkeypatch.setenv("RIG_BRAIN_ENABLED", "false")
    calls = {"http": 0, "route": 0}

    class FakeHttp:
        async def get(self, *a, **k):
            calls["http"] += 1
            raise AssertionError("brain must stay quiet")

        async def post(self, *a, **k):
            calls["http"] += 1
            raise AssertionError("brain must stay quiet")

    class FakeTank:
        async def route(self, tenant_id, task_type, messages):
            calls["route"] += 1
            return {"content": "tank-only", "cost_usd": 0.05, "tokens_in": 10, "tokens_out": 3}

    routed = await brain_then_route(
        FakeHttp(), FakeTank(), tenant_id=str(uuid4()), task_type="rig.ask",
        messages=[{"role": "user", "content": "q"}],
    )
    assert calls["http"] == 0 and calls["route"] == 1
    assert routed["brain"]["enabled"] is False
    assert routed["brain"]["called"] is False


@pytest.mark.asyncio
async def test_memory_outage_answers_without_memory_never_repeat():
    class BrokenMemory(FakeMemory):
        async def recall(self, *a, **k):
            raise RuntimeError("hermes down")

        async def records(self, *a, **k):
            raise RuntimeError("hermes down")

    memory = BrokenMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {**FIXED_COST, "result": {"past_builds": ["outage"]}}

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="rig.build",
        task={"query": "x"}, paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["memory_status"] == "memory unavailable"
    assert first["answered_from_memory"] is False
    # Second run still cannot serve a stored repeat after outage.
    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="rig.build",
        task={"query": "x"}, paid_call=paid,
    )
    assert second["paid_calls"] == 1 and paid_calls == 2
    assert second["answered_from_memory"] is False
    assert second["memory_status"] == "memory unavailable"


@pytest.mark.asyncio
async def test_missing_tenant_or_user_refused():
    from gates_memory import MemoryScopeError

    memory = FakeMemory()

    async def paid(_task):
        return {**FIXED_COST, "result": {"past_builds": ["x"]}}

    with pytest.raises(MemoryScopeError):
        await run_with_memory(
            memory, tenant_id="", user_id="u", task_key="rig.build",
            task={"query": "x"}, paid_call=paid,
        )
    with pytest.raises(MemoryScopeError):
        await run_with_memory(
            memory, tenant_id=str(uuid4()), user_id="", task_key="rig.build",
            task={"query": "x"}, paid_call=paid,
        )


def test_compose_brain_profile_opt_in():
    import yaml
    cfg = yaml.safe_load((ROOT / "agents/rig/docker-compose.yml").read_text())
    env = cfg["services"]["agent-rig"]["environment"]
    assert env["RIG_BRAIN_ENABLED"] == "${RIG_BRAIN_ENABLED:-false}"
    assert env["RIG_MEMORY_ENABLED"] == "${RIG_MEMORY_ENABLED:-false}"
    assert cfg["services"]["rig-brain"]["profiles"] == ["brain"]
    assert cfg["services"]["rig-sandbox"]["profiles"] == ["brain"]
