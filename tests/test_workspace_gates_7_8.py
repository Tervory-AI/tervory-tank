"""Gates 7+8 offline: memory bracket, controls, auth scope, exact repeat, non-empty fields."""
from __future__ import annotations
from copy import deepcopy
from types import SimpleNamespace

import importlib.util
import json
import os
import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]

def _load(name: str, rel: str):
    path = ROOT / "integrations" / "workspace" / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_gates = _load("integrations.workspace.gates_memory", "gates_memory.py")
_request = _load("integrations.workspace.request_path", "request_path.py")
FIXED_FAKE_PER_CALL = _gates.FIXED_FAKE_PER_CALL
FakeMemory = _gates.FakeMemory
MemoryControlError = _gates.MemoryControlError
MemoryOutageError = _gates.MemoryOutageError
MemoryScopeError = _gates.MemoryScopeError
apply_corrections = _gates.apply_corrections
apply_memory_edit = _gates.apply_memory_edit
apply_memory_forget = _gates.apply_memory_forget
assert_remember_fields_nonempty = _gates.assert_remember_fields_nonempty
build_memory_text = _gates.build_memory_text
identical_reuse_from_memories = _gates.identical_reuse_from_memories
is_cache_eligible = _gates.is_cache_eligible
is_memory_service_outage = _gates.is_memory_service_outage
memory_enabled = _gates.memory_enabled
normalize_memory_control = _gates.normalize_memory_control
persist_invalidate_identical_receipts = _gates.persist_invalidate_identical_receipts
refuse_client_impersonation = _gates.refuse_client_impersonation
apply_memory_view = _gates.apply_memory_view
load_owned_memory = _gates.load_owned_memory
product_to_tank_agent_memory = _gates.product_to_tank_agent_memory
require_authenticated_scope = _gates.require_authenticated_scope
resolve_memory_control = _gates.resolve_memory_control
run_with_memory = _gates.run_with_memory
select_tenant_user_memories = _gates.select_tenant_user_memories
set_memory_control = _gates.set_memory_control
task_input_fingerprint = _gates.task_input_fingerprint
run_chat_request = _request.run_chat_request
run_task_request = _request.run_task_request


@pytest.mark.asyncio
async def test_product_request_tank_route_receipt_then_memory():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "project-board-summary"

    async def paid(task):
        return {
            "cost_usd": 0.12,
            "tokens_in": 40,
            "tokens_out": 12,
            "result": {
                "conversations": ["asked-for-status"],
                "preferences": ["short-answers"],
                "projects": ["board-alpha"],
                "files": ["roadmap.csv"],
                "outcome": "board-summarized",
            },
        }

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"title": "Summarize board", "request": "What is open?"},
        paid_call=paid,
        memory_control="edit",
    )
    assert [step["action"] for step in receipt["steps"]] == [
        "recall",
        "cache_eligible",
        "tank_agent",
        "remember",
    ]
    assert receipt["paid_calls"] == 1 and receipt["cost_usd"] == 0.12
    assert receipt["tokens_in"] == 40 and receipt["tokens_out"] == 12
    assert memory.remembers == 1 and memory.rows[0]["tenant_id"] == tenant
    assert memory.rows[0]["meta"]["user_id"] == user
    assert memory.rows[0]["meta"]["input_fingerprint"] == task_input_fingerprint(
        {"title": "Summarize board", "request": "What is open?"}
    )
    assert isinstance(memory.rows[0]["meta"]["reusable_result"], dict)
    assert "conversation=asked-for-status" in memory.rows[0]["text"]
    assert "preferences=short-answers" in memory.rows[0]["text"]
    assert "projects=board-alpha" in memory.rows[0]["text"]
    assert "files=roadmap.csv" in memory.rows[0]["text"]
    assert "outcome=board-summarized" in memory.rows[0]["text"]


@pytest.mark.asyncio
async def test_correction_applies_next_time_with_no_paid_call():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "project-retry-tone"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": 0.2,
            "tokens_in": 50,
            "tokens_out": 20,
            "result": {
                "conversations": ["asked-timeline"],
                "preferences": ["email-only"],
                "projects": ["beta"],
                "correction": "prefer-bullet-lists",
                "outcome": "timeline-answer",
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"title": "Timeline", "request": "When can we start?"},
        paid_call=paid,
        memory_control="edit",
    )
    assert first["paid_calls"] == 1 and paid_calls == 1

    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"title": "Timeline", "request": "When can we start?"},
        paid_call=paid,
        memory_control="edit",
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert "prefer-bullet-lists" in second["result"]["applied_corrections"]
    assert "apply_correction" in [step["action"] for step in second["steps"]]
    assert "identical_reuse" not in [step["action"] for step in second["steps"]]


@pytest.mark.asyncio
async def test_second_user_and_second_tenant_see_nothing():
    memory = FakeMemory()
    tenant_a, user_a = str(uuid4()), str(uuid4())
    tenant_b, user_b = str(uuid4()), str(uuid4())
    task = {"title": "Private", "request": "Hello"}
    fingerprint = task_input_fingerprint(task)

    await memory.remember(
        tenant_a,
        build_memory_text(summary="Workspace task private", correction="keep-private"),
        "workspace.correction",
        "workspace:task:private",
        meta={"user_id": user_a, "task_key": "private", "input_fingerprint": fingerprint},
    )
    await memory.remember(
        tenant_a,
        build_memory_text(summary="Workspace task private", receipt="cost=0.05", outcome="owner-only"),
        "workspace.receipt",
        "workspace:task:private",
        meta={
            "user_id": user_a,
            "task_key": "private",
            "input_fingerprint": fingerprint,
            "reusable_result": {"projects": ["owner-only"], "conversations": ["private"]},
        },
    )
    foreign = select_tenant_user_memories(memory.rows, tenant_id=tenant_b, user_id=user_b)
    other_user = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_b)
    owner = select_tenant_user_memories(memory.rows, tenant_id=tenant_a, user_id=user_a)
    assert foreign == [] and other_user == [] and len(owner) == 2
    assert (
        identical_reuse_from_memories(foreign, task_key="private", input_fingerprint=fingerprint)
        is None
    )

    async def paid(_task):
        return {
            "cost_usd": 0.01,
            "tokens_in": 1,
            "tokens_out": 1,
            "result": {"conversations": ["x"], "projects": ["y"], "outcome": "fresh"},
        }

    outsider = await run_with_memory(
        memory,
        tenant_id=tenant_b,
        user_id=user_b,
        task_key="private",
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    assert outsider["answered_from_memory"] is False
    assert outsider["paid_calls"] == 1

    other_user_run = await run_with_memory(
        memory,
        tenant_id=tenant_a,
        user_id=user_b,
        task_key="private",
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    assert other_user_run["answered_from_memory"] is False
    assert other_user_run["paid_calls"] == 1


@pytest.mark.asyncio
async def test_same_task_twice_reports_cost_and_tokens_each_run():
    """Identical uncorrected repeat: fixed fake per-call price; second pays nothing."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "project-cost-twice"
    paid_calls = 0
    fixed = dict(FIXED_FAKE_PER_CALL)
    task = {"title": "Costed", "request": "Status?", "task_type": "tier0.answer"}

    async def paid(task_arg):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": fixed["cost_usd"],
            "tokens_in": fixed["tokens_in"],
            "tokens_out": fixed["tokens_out"],
            "result": {
                "conversations": ["run-1"],
                "projects": ["costed"],
                "files": ["notes.md"],
                "outcome": "status-ok",
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="edit",
    )

    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["cost_usd"] == fixed["cost_usd"]
    assert first["tokens_in"] == fixed["tokens_in"]
    assert first["tokens_out"] == fixed["tokens_out"]
    assert first["answered_from_memory"] is False

    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["cost_usd"] == 0.0
    assert second["tokens_in"] == 0
    assert second["tokens_out"] == 0
    assert second["answered_from_memory"] is True
    assert second["would_have_cost_usd"] == fixed["cost_usd"]
    assert second["would_have_tokens_in"] == fixed["tokens_in"]
    assert second["would_have_tokens_out"] == fixed["tokens_out"]
    assert "identical_reuse" in [step["action"] for step in second["steps"]]
    assert "apply_correction" not in [step["action"] for step in second["steps"]]
    assert "tank_agent" not in [step["action"] for step in second["steps"]]
    assert second["result"]["projects"] == ["costed"]
    assert second["cache_eligible"] is True
    assert memory.remembers == 1

    changed = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"title": "Costed", "request": "Different question?", "task_type": "tier0.answer"},
        paid_call=paid,
        memory_control="edit",
    )
    assert changed["paid_calls"] == 1 and paid_calls == 2
    assert changed["cost_usd"] == fixed["cost_usd"]
    assert changed["tokens_in"] == fixed["tokens_in"]
    assert changed["tokens_out"] == fixed["tokens_out"]
    assert changed["answered_from_memory"] is False


@pytest.mark.asyncio
async def test_memory_off_exact_repeat_still_pays(monkeypatch):
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "project-cost-twice"
    task = {"title": "Costed", "request": "Status?", "task_type": "tier0.answer"}
    fixed = dict(FIXED_FAKE_PER_CALL)
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": fixed["cost_usd"],
            "tokens_in": fixed["tokens_in"],
            "tokens_out": fixed["tokens_out"],
            "result": {"projects": ["z"], "outcome": "paid"},
        }

    await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    assert paid_calls == 1 and memory.remembers == 1

    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="off")
    control = await resolve_memory_control(memory, tenant_id=tenant, user_id=user)
    assert control == "off"

    repeat = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
    )
    assert repeat["memory_control"] == "off"
    assert repeat["paid_calls"] == 1 and paid_calls == 2
    assert repeat["cost_usd"] == fixed["cost_usd"]
    assert [step["action"] for step in repeat["steps"]] == ["memory_off", "tank_agent"]


def test_apply_corrections_secret_refusal_and_memory_switch():
    corrected = apply_corrections({"title": "A"}, ["use-saved-preference"])
    assert corrected["applied_corrections"] == ["use-saved-preference"]
    assert corrected["answered_from_memory"] is True
    with pytest.raises(ValueError):
        build_memory_text(summary="leak api_key=should-fail")
    previous = os.environ.pop("WORKSPACE_MEMORY_ENABLED", None)
    try:
        assert memory_enabled() is False
    finally:
        if previous is not None:
            os.environ["WORKSPACE_MEMORY_ENABLED"] = previous
    assert is_cache_eligible("project-cost-twice") is True
    assert is_cache_eligible("compose-draft", {"task_type": "workspace.draft"}) is False
    assert task_input_fingerprint({"title": "A", "request": "1"}) != task_input_fingerprint(
        {"title": "A", "request": "2"}
    )


@pytest.mark.asyncio
async def test_forget_and_memory_off_skip_store(monkeypatch):
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    saved = await memory.remember(
        tenant,
        build_memory_text(summary="Workspace task drop", correction="forget-me"),
        "workspace.correction",
        "workspace:task:drop",
        meta={"user_id": user, "task_key": "drop"},
    )
    await apply_memory_forget(
        memory, memory_id=saved["id"], tenant_id=tenant, user_id=user, memory_control="forget"
    )
    assert memory.forgets == 1
    assert select_tenant_user_memories(memory.rows, tenant_id=tenant, user_id=user) == []

    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="off")
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {"cost_usd": 0.02, "tokens_in": 2, "tokens_out": 1, "result": {"projects": ["z"], "outcome": "go"}}

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="drop",
        task={"title": "Off", "request": "Go"},
        paid_call=paid,
    )
    assert receipt["memory_control"] == "off"
    assert receipt["paid_calls"] == 1 and paid_calls == 1
    assert [step["action"] for step in receipt["steps"]] == ["memory_off", "tank_agent"]


def test_auth_scope_refuses_empty_tenant_user_and_tenant_as_user():
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id="", user_id="user-a")
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id="tenant-a", user_id="")
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id="tenant-a", user_id="tenant-a")
    tenant, user = require_authenticated_scope(tenant_id="tenant-a", user_id="user-a")
    assert tenant == "tenant-a" and user == "user-a"


@pytest.mark.asyncio
async def test_run_with_memory_refuses_missing_user_without_paid_or_remember():
    memory = FakeMemory()
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {"cost_usd": 1.0, "tokens_in": 1, "tokens_out": 1, "result": {"outcome": "x"}}

    with pytest.raises(MemoryScopeError):
        await run_with_memory(
            memory,
            tenant_id=str(uuid4()),
            user_id="",
            task_key="no-user",
            task={"title": "X", "request": "Y"},
            paid_call=paid,
        )
    assert paid_calls == 0 and memory.remembers == 0 and memory.recalls == 0


@pytest.mark.asyncio
async def test_memory_controls_view_edit_forget_and_invalidation():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid_calls = 0
    fixed = dict(FIXED_FAKE_PER_CALL)

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            **fixed,
            "result": {
                "conversations": ["c1"],
                "projects": ["p1"],
                "files": ["f1"],
                "outcome": "view-edit",
            },
        }

    # view: recalls but refuses remember
    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="controls",
        task={"title": "C", "request": "R", "task_type": "tier0.answer"},
        paid_call=paid,
        memory_control="view",
    )
    assert first["paid_calls"] == 1 and memory.remembers == 0
    assert any(s["action"] == "remember_skipped" for s in first["steps"])
    with pytest.raises(MemoryControlError):
        await apply_memory_forget(
            memory, memory_id="mem-1", tenant_id=tenant, user_id=user, memory_control="view"
        )

    # edit: remembers, refuses forget
    second = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="controls-edit",
        task={"title": "C2", "request": "R2", "task_type": "tier0.answer"},
        paid_call=paid,
        memory_control="edit",
    )
    assert memory.remembers == 1
    assert any(s["action"] == "remember" for s in second["steps"])
    with pytest.raises(MemoryControlError):
        await apply_memory_forget(
            memory,
            memory_id=memory.rows[0]["id"],
            tenant_id=tenant,
            user_id=user,
            memory_control="edit",
        )

    # Per-tenant+user live control via memory corridor
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="off")
    assert await resolve_memory_control(memory, tenant_id=tenant, user_id=user) == "off"
    assert normalize_memory_control("FORGET") == "forget"

    # forget deletes owned row; cross-user fails closed
    saved = await memory.remember(
        tenant,
        build_memory_text(summary="owner-row", outcome="keep"),
        "workspace.task",
        "workspace:task:owner",
        meta={"user_id": user, "task_key": "owner"},
    )
    await apply_memory_forget(
        memory, memory_id=saved["id"], tenant_id=tenant, user_id=user, memory_control="forget"
    )
    assert memory.forgets == 1
    other = str(uuid4())
    again = await memory.remember(
        tenant,
        build_memory_text(summary="owner-only", outcome="private"),
        "workspace.task",
        "workspace:task:owner2",
        meta={"user_id": user, "task_key": "owner2"},
    )
    with pytest.raises(MemoryScopeError):
        await apply_memory_forget(
            memory, memory_id=again["id"], tenant_id=tenant, user_id=other, memory_control="forget"
        )


@pytest.mark.asyncio
async def test_correction_invalidates_prior_identical_receipt():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task = {"title": "Same", "request": "Q", "task_type": "tier0.answer"}
    task_key = "invalidate-me"
    paid_calls = 0

    async def paid(task_arg):
        nonlocal paid_calls
        paid_calls += 1
        result = {
            "conversations": ["c"],
            "projects": ["p"],
            "files": ["f"],
            "outcome": f"run-{paid_calls}",
        }
        if paid_calls == 2:
            result["correction"] = "use-new-tone"
        return {**FIXED_FAKE_PER_CALL, "result": result}

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid, memory_control="edit"
    )
    assert first["paid_calls"] == 1
    # Force a correction store on second paid path by wiping reusable then paying with correction
    memory.rows[0]["meta"]["reusable_result"] = None
    memory.rows[0]["meta"]["invalidated"] = True
    corrected = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid, memory_control="edit"
    )
    assert corrected["paid_calls"] == 1 and paid_calls == 2
    third = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid, memory_control="edit"
    )
    assert third["paid_calls"] == 0 and paid_calls == 2
    assert "apply_correction" in [s["action"] for s in third["steps"]]


def test_remembered_fields_are_never_hardcoded_empty():
    with pytest.raises(ValueError):
        assert_remember_fields_nonempty({"summary": ""})
    with pytest.raises(ValueError):
        assert_remember_fields_nonempty({"projects": []})
    with pytest.raises(ValueError):
        assert_remember_fields_nonempty({"meta": {}})
    with pytest.raises(ValueError):
        assert_remember_fields_nonempty({"outcome": None, "summary": None})
    with pytest.raises(ValueError):
        build_memory_text()
    ok = assert_remember_fields_nonempty(
        {"summary": "Workspace task x", "outcome": "done", "projects": ["alpha"], "empty": None}
    )
    assert "empty" not in ok
    assert ok["projects"] == ["alpha"]


@pytest.mark.asyncio
async def test_remember_payload_fields_are_non_empty_after_paid_run():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())

    async def paid(_task):
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": ["asked"],
                "preferences": ["short"],
                "projects": ["board"],
                "files": ["a.csv"],
                "outcome": "summarized",
            },
        }

    await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="nonempty",
        task={"title": "T", "request": "R", "task_type": "tier0.answer"},
        paid_call=paid,
        memory_control="edit",
    )
    row = memory.rows[0]
    assert row["text"].strip()
    assert "outcome=summarized" in row["text"]
    assert "projects=board" in row["text"]
    assert "files=a.csv" in row["text"]
    assert "conversation=asked" in row["text"]
    assert "preferences=short" in row["text"]
    assert "receipt=" in row["text"]
    reusable = row["meta"]["reusable_result"]
    assert isinstance(reusable, dict) and reusable
    for key in ("conversations", "preferences", "projects", "files", "outcome"):
        assert reusable.get(key) not in (None, "", [], {})


@pytest.mark.asyncio
async def test_chat_and_task_request_paths_use_free_steps_then_tank_agent():
    """Proves request_path call chain for chat + tasks corridors."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid = {"n": 0}

    async def tank_route(task):
        paid["n"] += 1
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": [task["request"][:40]],
                "projects": ["chat"],
                "files": ["chat-thread"],
                "outcome": "chat-answer",
                "route": {"content": "hello", "cost_usd": FIXED_FAKE_PER_CALL["cost_usd"]},
            },
        }

    async def tank_create(task):
        paid["n"] += 1
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": [task["request"][:40]],
                "projects": [task["title"]],
                "files": ["task-board"],
                "outcome": "task-created",
                "task": {"id": "task-1", "title": task["title"]},
            },
        }

    first = await run_chat_request(
        memory,
        tenant_id=tenant,
        user_id=user,
        messages=[{"role": "user", "content": "What is open?"}],
        tank_route=tank_route,
        memory_control="edit",
    )
    assert first["paid_calls"] == 1 and paid["n"] == 1
    assert "tank_agent" in [s["action"] for s in first["steps"]]
    assert "recall" in [s["action"] for s in first["steps"]]

    second = await run_chat_request(
        memory,
        tenant_id=tenant,
        user_id=user,
        messages=[{"role": "user", "content": "What is open?"}],
        tank_route=tank_route,
        memory_control="edit",
    )
    assert second["paid_calls"] == 0 and paid["n"] == 1
    assert second["cost_usd"] == 0.0 and second["answered_from_memory"] is True

    task_first = await run_task_request(
        memory,
        tenant_id=tenant,
        user_id=user,
        title="Board",
        request="Summarize",
        tank_create=tank_create,
        memory_control="edit",
    )
    assert task_first["paid_calls"] == 1 and paid["n"] == 2
    task_second = await run_task_request(
        memory,
        tenant_id=tenant,
        user_id=user,
        title="Board",
        request="Summarize",
        tank_create=tank_create,
        memory_control="edit",
    )
    assert task_second["paid_calls"] == 0 and paid["n"] == 2
    assert task_second["tokens_in"] == 0 and task_second["tokens_out"] == 0

    # product_to_tank_agent_memory alias
    alias = await product_to_tank_agent_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="alias",
        task={"title": "A", "request": "B", "task_type": "tier0.answer"},
        tank_agent_call=tank_create,
        memory_control="edit",
    )
    assert alias["paid_calls"] == 1


def test_workspace_gates_ts_and_routes_wire_call_chain():
    """Static proof: chat/tasks routes import workspace-gates; call chain documented."""
    gates = (ROOT / "workspace" / "lib" / "workspace-gates.ts").read_text()
    chat = (ROOT / "workspace" / "app" / "api" / "chat" / "route.ts").read_text()
    tasks = (ROOT / "workspace" / "app" / "api" / "tasks" / "route.ts").read_text()
    workspace_py = (ROOT / "integrations" / "tank" / "workspace.py").read_text()
    request_path = (ROOT / "integrations" / "workspace" / "request_path.py").read_text()
    memory_api = (ROOT / "workspace" / "app" / "api" / "memory" / "route.ts").read_text()
    entry_api = (ROOT / "workspace" / "app" / "api" / "memory" / "entry" / "[id]" / "route.ts").read_text()

    assert "chatWithMemory" in chat and 'from "@/lib/workspace-gates"' in chat
    assert "createTaskWithMemory" in tasks and 'from "@/lib/workspace-gates"' in tasks
    assert "Signed-in tenant and user required" in chat
    assert "Signed-in tenant and user required" in tasks
    assert "/v1/command/workspace/chat" in gates
    assert "/v1/command/workspace/" in gates
    assert "_run_chat_with_memory" in workspace_py
    assert "_run_task_create_with_memory" in workspace_py
    assert "run_chat_request" in request_path and "run_task_request" in request_path
    assert "product_to_tank_agent_memory" in request_path
    assert "free: code_skill" in gates or "code_skill → recall" in gates
    # Auth refuses; memory outage degrades with memory_unavailable marker
    assert "memory unavailable" in gates or "memory_unavailable" in gates
    assert "refuseEmptyScope" in gates
    assert "memoryUnavailableBracket" in gates or "memory_unavailable" in gates
    assert "_load_memory_bracket" in workspace_py
    assert "_memory_unavailable_bracket" in workspace_py
    assert "MemoryOutageError" in workspace_py or "memory unavailable" in workspace_py
    # Authenticated memory controls API
    assert "viewWorkspaceMemory" in memory_api and "setWorkspaceMemoryControl" in memory_api
    assert "editWorkspaceMemory" in entry_api and "forgetWorkspaceMemory" in entry_api
    assert "memory.edit" in workspace_py


def test_gate6_patch_packages_memory_bracket_modules():
    """The shipped image contains both product-specific namespaces and the shared client."""
    from command_tools import workspace
    from command_tools._workspace import gates_memory, request_path
    assert workspace._load_memory_bracket() == (gates_memory, request_path)
    for name in ("gates_memory.py", "request_path.py", "memory_client.py"):
        source = (ROOT / "integrations/workspace" / name).read_text()
        shipped = (ROOT / "tank/command_tools/_workspace" / name).read_text()
        assert shipped == source.replace("integrations.workspace", "command_tools._workspace")
    assert (ROOT / "tank/command_tools/_shared_memory.py").read_bytes() == (ROOT / "agents/_chassis/chassis/memory.py").read_bytes()
    assert "_load_memory_bracket" in (ROOT / "tank/command_tools/workspace.py").read_text()
    assert "_direct" not in (ROOT / "tank/command_tools/workspace.py").read_text()


@pytest.mark.asyncio
async def test_auth_scope_refusal_no_paid_call_and_nothing_remembered():
    """(a) Missing/invalid tenant/user or scope error refuses: paid_calls=0, nothing remembered."""
    memory = FakeMemory()
    paid = {"n": 0}

    async def tank(_task):
        paid["n"] += 1
        return {**FIXED_FAKE_PER_CALL, "result": {"outcome": "should-not-run"}}

    for tenant, user in [("", "u1"), (None, "u1"), ("t1", ""), ("t1", None), ("same", "same")]:
        with pytest.raises(MemoryScopeError):
            await run_with_memory(
                memory,
                tenant_id=tenant,
                user_id=user,
                task_key="tier0.answer",
                task={"title": "Q", "request": "R", "task_type": "tier0.answer"},
                paid_call=tank,
                memory_control="edit",
            )
    assert paid["n"] == 0 and memory.remembers == 0 and memory.recalls == 0

    # Tank command path also refuses before any paid create_task.
    import importlib
    import sys
    from fastapi import HTTPException

    workspace_path = ROOT / "integrations" / "tank" / "workspace.py"
    spec = importlib.util.spec_from_file_location("workspace_tools_auth_refuse", workspace_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    async def create_task(_body):
        paid["n"] += 1
        return {"id": "nope"}

    main_mod = SimpleNamespace(
        create_task=create_task,
        TaskCreate=lambda **kw: SimpleNamespace(**kw),
        Message=lambda **kw: kw,
        memory=FakeMemory(),
        app=None,
    )
    args = SimpleNamespace(title="T", request="R", task_type="tier0.answer", memory_control=None)
    with pytest.raises(HTTPException) as raised:
        await mod._run_task_create_with_memory(
            SimpleNamespace(tenant_id="", user_id="user-1"), args, main_mod
        )
    assert raised.value.status_code == 401
    assert paid["n"] == 0 and main_mod.memory.remembers == 0


@pytest.mark.asyncio
async def test_memory_outage_answers_via_tank_marks_unavailable_no_reuse_no_remember(monkeypatch):
    """(b) Outage: Tank path answers, receipt says memory unavailable, no identical_reuse, no remember."""
    import importlib
    import sys

    workspace_path = ROOT / "integrations" / "tank" / "workspace.py"
    spec = importlib.util.spec_from_file_location("workspace_tools_outage", workspace_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)

    # Seed a stored reusable result that must NOT be served during outage.
    tenant, user = str(uuid4()), str(uuid4())
    stored = FakeMemory()
    task = {"title": "Q", "request": "same-input", "task_type": "tier0.answer"}
    assert task_input_fingerprint(task)

    async def seed_paid(_task):
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": ["c"],
                "projects": ["p"],
                "files": ["f"],
                "outcome": "stored-answer",
                "preferences": ["brief"],
            },
        }

    seeded = await run_with_memory(
        stored,
        tenant_id=tenant,
        user_id=user,
        task_key="tier0.answer",
        task=task,
        paid_call=seed_paid,
        memory_control="edit",
    )
    assert seeded["paid_calls"] == 1
    assert isinstance(stored.rows[0]["meta"]["reusable_result"], dict)

    class OutageMemory(FakeMemory):
        async def recall(self, *args, **kwargs):
            raise RuntimeError("hermes unreachable")

        async def remember(self, *args, **kwargs):
            raise RuntimeError("hermes unreachable")

    outage = OutageMemory()
    outage.rows = deepcopy(stored.rows)
    paid = {"n": 0}

    async def create_task(body):
        paid["n"] += 1
        return {
            "id": "tank-job",
            "status": "queued",
            "cost_usd": FIXED_FAKE_PER_CALL["cost_usd"],
            "tokens_in": FIXED_FAKE_PER_CALL["tokens_in"],
            "tokens_out": FIXED_FAKE_PER_CALL["tokens_out"],
            "title": body.title,
        }

    main_mod = SimpleNamespace(
        create_task=create_task,
        TaskCreate=lambda **kw: SimpleNamespace(**kw),
        Message=lambda **kw: SimpleNamespace(**kw),
        memory=outage,
        app=None,
    )
    actor = SimpleNamespace(tenant_id=tenant, user_id=user)
    args = SimpleNamespace(
        title=task["title"], request=task["request"], task_type="tier0.answer", memory_control=None
    )
    result = await mod._run_task_create_with_memory(actor, args, main_mod)
    bracket = result["memory_bracket"]
    assert paid["n"] == 1
    assert bracket["memory_unavailable"] is True
    assert bracket["memory_status"] == "memory unavailable"
    assert bracket["answered_from_memory"] is False
    assert bracket.get("identical_reuse") is False
    assert "identical_reuse" not in [s.get("action") for s in bracket["steps"]]
    assert outage.remembers == 0  # OutageMemory.remember raises; nothing persisted via store either
    # Stored reusable_result must not have been returned as the answer.
    assert result.get("outcome") != "stored-answer" or result.get("id") == "tank-job"

    # Missing memory client is also an outage (answers via Tank, marks unavailable).
    paid["n"] = 0
    main_mod.memory = None
    result2 = await mod._run_task_create_with_memory(actor, args, main_mod)
    assert paid["n"] == 1
    assert result2["memory_bracket"]["memory_unavailable"] is True
    assert result2["memory_bracket"]["memory_status"] == "memory unavailable"

    # Bracket import failure is an outage.
    paid["n"] = 0

    def boom():
        raise mod._BracketImportError("Workspace memory bracket unavailable: forced")

    monkeypatch.setattr(mod, "_load_memory_bracket", boom)
    result3 = await mod._run_task_create_with_memory(actor, args, main_mod)
    assert paid["n"] == 1
    assert result3["memory_bracket"]["memory_unavailable"] is True
    assert "identical_reuse" not in [s.get("action") for s in result3["memory_bracket"]["steps"]]


@pytest.mark.asyncio
async def test_run_with_memory_outage_raises_and_never_reuses():
    """Outage during recall raises MemoryOutageError before identical_reuse or remember."""
    from integrations.workspace.gates_memory import MemoryOutageError

    class BoomRecall(FakeMemory):
        async def recall(self, *args, **kwargs):
            raise TimeoutError("memory timed out")

    memory = BoomRecall()
    # Plant a row that would otherwise be reusable if recall succeeded from a sibling store —
    # this instance's recall always fails, so run_with_memory must raise outage.
    paid = {"n": 0}

    async def tank(_task):
        paid["n"] += 1
        return {**FIXED_FAKE_PER_CALL, "result": {"outcome": "x", "conversations": ["c"], "projects": ["p"], "files": ["f"]}}

    with pytest.raises(MemoryOutageError):
        await run_with_memory(
            memory,
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            task_key="tier0.answer",
            task={"title": "Q", "request": "R", "task_type": "tier0.answer"},
            paid_call=tank,
            memory_control="edit",
        )
    assert paid["n"] == 0 and memory.remembers == 0


def test_workspace_gates_ts_auth_refuse_and_outage_degrade_static():
    """TS: auth/scope refuse; memory outage falls back to route/createTask with memory_unavailable."""
    gates = (ROOT / "workspace" / "lib" / "workspace-gates.ts").read_text()
    assert "refuseEmptyScope" in gates
    assert "isAuthOrScopeFailure" in gates
    assert "isMemoryOutageFailure" in gates
    assert "memory_unavailable" in gates
    assert 'memory_status: "memory unavailable"' in gates or "memory unavailable" in gates
    assert "await route(" in gates
    assert "await createTask(" in gates
    # Auth path still throws InputError (no paid call at this layer for empty scope).
    assert 'throw new InputError("Signed-in tenant required.")' in gates
    assert 'throw new InputError("Signed-in user required.")' in gates
    assert "classifyWorkspaceCommandFailure" in gates
    # Narrow outage mapping: non-Error and TypeError must NOT become outage.
    outage_fn = gates.split("function isMemoryOutageFailure")[1].split("export function classifyWorkspaceCommandFailure")[0]
    assert "if (!(err instanceof Error)) return false;" in outage_fn
    assert 'name === "TypeError"' in outage_fn
    assert 'name === "MemoryOutageError"' in outage_fn or 'name === "MemoryUnavailable"' in outage_fn
    assert 'msg.includes("econnrefused")' in outage_fn
    assert 'msg.includes("fetch")' not in outage_fn
    # Broad bare "memory" heuristic removed (keep only "memory unavailable").
    assert 'msg.includes("memory")' not in outage_fn.replace('msg.includes("memory unavailable")', "")


@pytest.mark.asyncio
async def test_authenticated_memory_edit_forget_off_and_cross_tenant_refused():
    """Item 2: content edit, forget, off; another user/tenant cannot view/edit/forget."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    other_user, other_tenant = str(uuid4()), str(uuid4())

    async def paid(task):
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": ["hello"],
                "projects": ["p1"],
                "files": ["f1"],
                "outcome": "answered",
                "preferences": ["brief"],
            },
        }

    first = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="tier0.answer",
        task={"title": "Q", "request": "same", "task_type": "tier0.answer"},
        paid_call=paid,
        memory_control="edit",
    )
    assert first["paid_calls"] == 1 and memory.remembers == 1
    memory_id = memory.rows[0]["id"]
    original_text = memory.rows[0]["text"]

    # Content edit changes the stored text (not just a permission mode).
    edited = await apply_memory_edit(
        memory,
        memory_id=memory_id,
        tenant_id=tenant,
        user_id=user,
        text="Edited summary for the board; outcome=revised",
    )
    assert edited["updated"] is True
    assert memory.rows[0]["text"] == "Edited summary for the board; outcome=revised"
    assert memory.rows[0]["text"] != original_text
    assert memory.rows[0]["meta"].get("edited") is True
    assert memory.rows[0]["meta"].get("reusable_result") is None

    # Other user cannot edit / forget / see via scoped select.
    with pytest.raises(MemoryScopeError):
        await apply_memory_edit(
            memory,
            memory_id=memory_id,
            tenant_id=tenant,
            user_id=other_user,
            text="hijack",
        )
    with pytest.raises(MemoryScopeError):
        await apply_memory_forget(
            memory,
            memory_id=memory_id,
            tenant_id=tenant,
            user_id=other_user,
            memory_control="forget",
        )
    with pytest.raises(MemoryScopeError):
        await apply_memory_edit(
            memory,
            memory_id=memory_id,
            tenant_id=other_tenant,
            user_id=user,
            text="hijack",
        )

    # Off: switch and confirm resolve
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="off")
    assert await resolve_memory_control(memory, tenant_id=tenant, user_id=user) == "off"

    # Forget by owner after re-enabling forget control
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="forget")
    await apply_memory_forget(
        memory,
        memory_id=memory_id,
        tenant_id=tenant,
        user_id=user,
        memory_control="forget",
    )
    assert all(row["id"] != memory_id for row in memory.rows)


@pytest.mark.asyncio
async def test_durable_invalidation_survives_fresh_memory_instances():
    """Item 3: after correction/edit/forget, a FRESH store does not serve old reusable_result."""

    store_rows: list = []

    def fresh() -> FakeMemory:
        mem = FakeMemory()
        mem.rows = deepcopy(store_rows)
        return mem

    def persist(mem: FakeMemory) -> None:
        store_rows.clear()
        store_rows.extend(deepcopy(mem.rows))

    tenant, user = str(uuid4()), str(uuid4())
    task = {"title": "Q", "request": "same-input", "task_type": "tier0.answer"}
    task_key = "tier0.answer"
    fingerprint = task_input_fingerprint(task)

    async def paid(_task):
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": ["c"],
                "projects": ["p"],
                "files": ["f"],
                "outcome": "first-answer",
                "preferences": ["brief"],
            },
        }

    mem = fresh()
    first = await run_with_memory(
        mem,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    assert first["paid_calls"] == 1
    assert isinstance(mem.rows[0]["meta"]["reusable_result"], dict)
    persist(mem)
    assert store_rows[0]["id"]

    # Fresh instance still serves identical reuse before invalidation.
    mem2 = fresh()
    hit = identical_reuse_from_memories(
        await mem2.recall(tenant, task_key, user_id=user),
        task_key=task_key,
        input_fingerprint=fingerprint,
    )
    assert hit is not None and hit["result"]["outcome"] == "first-answer"

    # Correction path durably invalidates.
    mem3 = fresh()
    await mem3.remember(
        tenant,
        "correction=use-shorter-tone",
        "workspace.correction",
        f"workspace:task:{task_key}",
        user_id=user,
        meta={"user_id": user, "task_key": task_key},
    )
    paid_calls = {"n": 0}

    async def paid2(_task):
        paid_calls["n"] += 1
        return {**FIXED_FAKE_PER_CALL, "result": {"outcome": "should-not-matter", "conversations": ["x"], "projects": ["p"], "files": ["f"]}}

    corrected = await run_with_memory(
        mem3,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid2,
        memory_control="edit",
    )
    assert corrected["paid_calls"] == 0 and paid_calls["n"] == 0
    persist(mem3)

    mem4 = fresh()
    assert (
        identical_reuse_from_memories(
            await mem4.recall(tenant, task_key, user_id=user),
            task_key=task_key,
            input_fingerprint=fingerprint,
        )
        is None
    )

    # Edit path: seed a fresh receipt then edit content; fresh store must not reuse.
    store_rows.clear()
    mem5 = fresh()
    await run_with_memory(
        mem5,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="edit",
    )
    persist(mem5)
    mid = store_rows[0]["id"]
    mem6 = fresh()
    await apply_memory_edit(
        mem6,
        memory_id=mid,
        tenant_id=tenant,
        user_id=user,
        text="Edited board note; outcome=revised-after-edit",
    )
    persist(mem6)
    mem7 = fresh()
    assert (
        identical_reuse_from_memories(
            await mem7.recall(tenant, task_key, user_id=user),
            task_key=task_key,
            input_fingerprint=fingerprint,
        )
        is None
    )

    # Forget path: after forget, fresh store has no reusable receipt.
    store_rows.clear()
    mem8 = fresh()
    await run_with_memory(
        mem8,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task=task,
        paid_call=paid,
        memory_control="forget",
    )
    persist(mem8)
    mid2 = store_rows[0]["id"]
    mem9 = fresh()
    await apply_memory_forget(
        mem9,
        memory_id=mid2,
        tenant_id=tenant,
        user_id=user,
        memory_control="forget",
    )
    persist(mem9)
    mem10 = fresh()
    assert (
        identical_reuse_from_memories(
            await mem10.recall(tenant, task_key, user_id=user),
            task_key=task_key,
            input_fingerprint=fingerprint,
        )
        is None
    )
    assert all(row.get("id") != mid2 for row in mem10.rows)




def _snapshot_memory(memory: FakeMemory) -> bytes:
    """Durable store contents only (not ephemeral recall counters)."""
    return json.dumps({"rows": memory.rows}, sort_keys=True, default=str).encode()


def _snapshot_settings(memory: FakeMemory) -> bytes:
    """Per-tenant+user memory_control preference rows only."""
    settings = [
        row
        for row in memory.rows
        if row.get("kind") == "workspace.preference"
        and str(row.get("source", "")).startswith("workspace:memory_control")
    ]
    return json.dumps({"settings": settings}, sort_keys=True, default=str).encode()


def _snapshot_receipts(memory: FakeMemory) -> bytes:
    """Remembered workspace.receipt / correction rows (reusable outcomes)."""
    receipts = [
        row
        for row in memory.rows
        if row.get("kind") in {"workspace.receipt", "workspace.correction"}
    ]
    return json.dumps({"receipts": receipts}, sort_keys=True, default=str).encode()


def _load_workspace_tools(module_name: str):
    import importlib
    import sys

    workspace_path = ROOT / "integrations" / "tank" / "workspace.py"
    spec = importlib.util.spec_from_file_location(module_name, workspace_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


async def _seed_victim_receipt(memory: FakeMemory, tenant: str, user: str) -> str:
    async def paid(_task):
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {
                "conversations": ["victim"],
                "projects": ["board"],
                "files": ["a.md"],
                "outcome": "victim-outcome",
                "preferences": ["brief"],
            },
        }

    await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key="tier0.answer",
        task={"title": "Q", "request": "same", "task_type": "tier0.answer"},
        paid_call=paid,
        memory_control="edit",
    )
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="edit")
    return memory.rows[0]["id"]


CONTROL_CASES = [
    ("view", "same_tenant_other_user"),
    ("view", "other_tenant"),
    ("edit", "same_tenant_other_user"),
    ("edit", "other_tenant"),
    ("forget", "same_tenant_other_user"),
    ("forget", "other_tenant"),
    ("off", "same_tenant_other_user"),
    ("off", "other_tenant"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("control,scope", CONTROL_CASES, ids=[f"{c}-{s}" for c, s in CONTROL_CASES])
async def test_memory_control_denies_foreign_tenant_user(control: str, scope: str):
    """8 cases: each control refuses other user (same tenant) and other tenant; store unchanged."""
    from fastapi import HTTPException

    mod = _load_workspace_tools(f"workspace_tools_deny_{control}_{scope}")
    memory = FakeMemory()
    victim_tenant, victim_user = str(uuid4()), str(uuid4())
    if scope == "same_tenant_other_user":
        attacker_tenant, attacker_user = victim_tenant, str(uuid4())
    else:
        attacker_tenant, attacker_user = str(uuid4()), str(uuid4())

    victim_memory_id = await _seed_victim_receipt(memory, victim_tenant, victim_user)
    before_store = _snapshot_memory(memory)
    before_settings = _snapshot_settings(memory)
    before_receipts = _snapshot_receipts(memory)
    before_control = await resolve_memory_control(
        memory, tenant_id=victim_tenant, user_id=victim_user
    )
    assert before_control == "edit"
    assert before_receipts  # seeded receipt must be present to prove it stayed

    # Real command handlers in integrations/tank/workspace.py (not bare helpers).
    main_mod = SimpleNamespace(memory=memory, app=None)
    attacker = SimpleNamespace(tenant_id=attacker_tenant, user_id=attacker_user)
    # Switch-off has no target memory_id: attempt uses forged victim identity claims.
    # View/edit/forget: attacker session targets the victim's memory_id (ownership check).
    forged = {
        "tenant_id": victim_tenant,
        "user_id": victim_user,
        "x-tervory-tenant": victim_tenant,
        "x-tervory-user": victim_user,
    }

    with pytest.raises(HTTPException) as raised:
        if control == "view":
            args = SimpleNamespace(
                task_key="tier0.answer",
                memory_id=victim_memory_id,
                memory_control="view",
            )
            await mod._run_memory_view(attacker, args, main_mod, raw={})
        elif control == "edit":
            args = SimpleNamespace(
                memory_id=victim_memory_id,
                text="hijacked text",
                memory_control="edit",
            )
            await mod._run_memory_edit(attacker, args, main_mod, raw={})
        elif control == "forget":
            args = SimpleNamespace(memory_id=victim_memory_id, memory_control="forget")
            await mod._run_memory_forget(attacker, args, main_mod, raw={})
        elif control == "off":
            args = SimpleNamespace(control="off")
            await mod._run_memory_control(attacker, args, main_mod, raw=forged)
        else:
            raise AssertionError(control)

    assert raised.value.status_code in {401, 403}
    detail = str(raised.value.detail).lower()
    assert "memory unavailable" not in detail
    assert "unavailable" not in detail or "impersonation" in detail or "refused" in detail
    # Byte-identical full-store, settings, and receipt snapshots before and after.
    assert _snapshot_memory(memory) == before_store
    assert _snapshot_settings(memory) == before_settings
    assert _snapshot_receipts(memory) == before_receipts
    assert (
        await resolve_memory_control(memory, tenant_id=victim_tenant, user_id=victim_user)
        == before_control
    )


@pytest.mark.asyncio
async def test_forged_tenant_user_header_cannot_impersonate_via_execute():
    """Forged tenant_id/user_id/header cannot impersonate; scope refusal ≠ outage."""
    from fastapi import HTTPException

    mod = _load_workspace_tools("workspace_tools_forge_headers")
    memory = FakeMemory()
    victim_tenant, victim_user = str(uuid4()), str(uuid4())
    attacker_tenant, attacker_user = str(uuid4()), str(uuid4())
    victim_memory_id = await _seed_victim_receipt(memory, victim_tenant, victim_user)
    before = _snapshot_memory(memory)
    before_control = await resolve_memory_control(
        memory, tenant_id=victim_tenant, user_id=victim_user
    )

    main_mod = SimpleNamespace(memory=memory, app=None)
    attacker = SimpleNamespace(tenant_id=attacker_tenant, user_id=attacker_user)
    args = SimpleNamespace(memory_id=victim_memory_id, text="forged-edit", memory_control="edit")
    claims = {
        "tenant_id": victim_tenant,
        "user_id": victim_user,
        "x-tervory-tenant": victim_tenant,
        "x-tervory-user": victim_user,
    }
    with pytest.raises(HTTPException) as raised:
        await mod._run_memory_edit(attacker, args, main_mod, raw=claims)
    assert raised.value.status_code == 403
    assert "memory unavailable" not in str(raised.value.detail).lower()
    assert "impersonation refused" in str(raised.value.detail).lower()
    assert _snapshot_memory(memory) == before
    assert (
        await resolve_memory_control(memory, tenant_id=victim_tenant, user_id=victim_user)
        == before_control
    )


@pytest.mark.asyncio
async def test_scope_refusal_never_marked_memory_unavailable_or_answered_via_tank():
    """Scope/auth refusal must not degrade into the memory-outage Tank path."""
    from fastapi import HTTPException

    mod = _load_workspace_tools("workspace_tools_scope_vs_outage")
    paid = {"n": 0}

    async def create_task(_body):
        paid["n"] += 1
        return {"id": "should-not-run"}

    async def route(**_kwargs):
        paid["n"] += 1
        return {"content": "should-not-run"}

    memory = FakeMemory()
    main_mod = SimpleNamespace(
        memory=memory,
        app=None,
        create_task=create_task,
        route=route,
        TaskCreate=lambda **kw: SimpleNamespace(**kw),
        Message=lambda **kw: kw,
    )
    # Empty user → scope refusal on chat/task, never outage degrade.
    with pytest.raises(HTTPException) as raised:
        await mod._run_task_create_with_memory(
            SimpleNamespace(tenant_id=str(uuid4()), user_id=""),
            SimpleNamespace(title="T", request="R", task_type="tier0.answer", memory_control=None),
            main_mod,
        )
    assert raised.value.status_code == 401
    assert paid["n"] == 0
    assert "memory unavailable" not in str(raised.value.detail).lower()

    # Foreign memory edit is 403 scope, not outage bracket.
    victim_tenant, victim_user = str(uuid4()), str(uuid4())
    mid = await _seed_victim_receipt(memory, victim_tenant, victim_user)
    before = _snapshot_memory(memory)
    with pytest.raises(HTTPException) as raised2:
        await mod._run_memory_edit(
            SimpleNamespace(tenant_id=str(uuid4()), user_id=str(uuid4())),
            SimpleNamespace(memory_id=mid, text="x", memory_control="edit"),
            main_mod,
            raw={},
        )
    assert raised2.value.status_code == 403
    assert "memory unavailable" not in str(raised2.value.detail).lower()
    assert paid["n"] == 0
    assert _snapshot_memory(memory) == before


def test_memory_api_routes_refuse_forged_identity_static_and_helper():
    """Authenticated API uses currentTenant + refuseClientImpersonation before controls."""
    route = (ROOT / "workspace" / "app" / "api" / "memory" / "route.ts").read_text()
    entry = (ROOT / "workspace" / "app" / "api" / "memory" / "entry" / "[id]" / "route.ts").read_text()
    session = (ROOT / "workspace" / "lib" / "memory-session.ts").read_text()
    assert "refuseClientImpersonation" in route and "currentTenant" in route
    assert "refuseClientImpersonation" in entry
    assert "impersonation refused" in session
    assert "x-tervory-tenant" in session and "x-tervory-user" in session
    gates = (ROOT / "workspace" / "lib" / "workspace-gates.ts").read_text()
    assert "viewWorkspaceMemory" in route and "setWorkspaceMemoryControl" in route
    assert "memory.view" in gates and "memory.control" in gates
    assert "memory.edit" in gates and "memory.forget" in gates
    with pytest.raises(MemoryScopeError):
        refuse_client_impersonation(
            session_tenant_id="t-session",
            session_user_id="u-session",
            claimed_tenant_id="t-other",
            claimed_user_id="u-session",
        )


def test_is_memory_service_outage_narrow_mapping():
    """Only typed/availability errors map to outage; TypeError/KeyError/bugs do not."""
    assert is_memory_service_outage(MemoryOutageError("down")) is True
    assert is_memory_service_outage(TimeoutError("memory timed out")) is True
    assert is_memory_service_outage(ConnectionError("connection refused")) is True
    assert is_memory_service_outage(RuntimeError("hermes unreachable")) is True
    assert is_memory_service_outage(RuntimeError("hermes answered 503")) is True
    assert is_memory_service_outage(TypeError("'NoneType' object is not subscriptable")) is False
    assert is_memory_service_outage(KeyError("missing")) is False
    assert is_memory_service_outage(AttributeError("no attr")) is False
    assert is_memory_service_outage(AssertionError("bug")) is False
    assert is_memory_service_outage(ValueError("bad arg")) is False
    assert is_memory_service_outage(MemoryScopeError("scope")) is False


@pytest.mark.asyncio
async def test_typeerror_inside_bracket_is_not_outage_and_makes_no_paid_call():
    """A TypeError/KeyError inside recall propagates; no paid Tank call, no outage degrade."""

    class BugRecall(FakeMemory):
        async def recall(self, *args, **kwargs):
            raise TypeError("'NoneType' object is not subscriptable")

    paid = {"n": 0}

    async def tank(_task):
        paid["n"] += 1
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {"outcome": "x", "conversations": ["c"], "projects": ["p"], "files": ["f"]},
        }

    with pytest.raises(TypeError):
        await run_with_memory(
            BugRecall(),
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            task_key="tier0.answer",
            task={"title": "Q", "request": "R", "task_type": "tier0.answer"},
            paid_call=tank,
            memory_control="edit",
        )
    assert paid["n"] == 0

    class KeyBug(FakeMemory):
        async def recall(self, *args, **kwargs):
            raise KeyError("bug-key")

    with pytest.raises(KeyError):
        await run_with_memory(
            KeyBug(),
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            task_key="tier0.answer",
            task={"title": "Q", "request": "R", "task_type": "tier0.answer"},
            paid_call=tank,
            memory_control="edit",
        )
    assert paid["n"] == 0


@pytest.mark.asyncio
async def test_typed_memory_outage_error_is_treated_as_outage():
    """Explicit MemoryOutageError from recall is the outage path (raises before paid)."""

    class TypedOutage(FakeMemory):
        async def recall(self, *args, **kwargs):
            raise MemoryOutageError("memory service 503")

    paid = {"n": 0}

    async def tank(_task):
        paid["n"] += 1
        return {
            **FIXED_FAKE_PER_CALL,
            "result": {"outcome": "x", "conversations": ["c"], "projects": ["p"], "files": ["f"]},
        }

    with pytest.raises(MemoryOutageError):
        await run_with_memory(
            TypedOutage(),
            tenant_id=str(uuid4()),
            user_id=str(uuid4()),
            task_key="tier0.answer",
            task={"title": "Q", "request": "R", "task_type": "tier0.answer"},
            paid_call=tank,
            memory_control="edit",
        )
    assert paid["n"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["task", "chat"])
async def test_remember_failure_after_paid_returns_unavailable_receipt_no_retry(path: str):
    """When remember fails after a paid call: paid_n==1, no reuse stored, receipt marked unavailable."""
    mod = _load_workspace_tools(f"workspace_tools_postpaid_{path}")
    tenant, user = str(uuid4()), str(uuid4())

    class RememberBoom(FakeMemory):
        async def remember(self, *args, **kwargs):
            raise MemoryOutageError("hermes answered 503")

    memory = RememberBoom()
    paid = {"n": 0}

    async def create_task(body):
        paid["n"] += 1
        return {
            "id": "tank-job",
            "status": "queued",
            "cost_usd": FIXED_FAKE_PER_CALL["cost_usd"],
            "tokens_in": FIXED_FAKE_PER_CALL["tokens_in"],
            "tokens_out": FIXED_FAKE_PER_CALL["tokens_out"],
            "title": getattr(body, "title", "T"),
            "result": {
                "task": {
                    "id": "tank-job",
                    "conversations": ["c"],
                    "projects": ["p"],
                    "files": ["f"],
                    "outcome": "paid-once",
                    "preferences": ["brief"],
                }
            },
        }

    async def route(**_kwargs):
        paid["n"] += 1
        return {
            "content": "paid-once",
            "cost_usd": FIXED_FAKE_PER_CALL["cost_usd"],
            "tokens_in": FIXED_FAKE_PER_CALL["tokens_in"],
            "tokens_out": FIXED_FAKE_PER_CALL["tokens_out"],
            "result": {
                "route": {
                    "content": "paid-once",
                    "conversations": ["c"],
                    "projects": ["p"],
                    "files": ["f"],
                    "outcome": "paid-once",
                    "preferences": ["brief"],
                }
            },
        }

    main_mod = SimpleNamespace(
        memory=memory,
        app=None,
        create_task=create_task,
        route=route,
        TaskCreate=lambda **kw: SimpleNamespace(**kw),
        Message=lambda **kw: kw,
    )
    actor = SimpleNamespace(tenant_id=tenant, user_id=user)

    if path == "task":
        result = await mod._run_task_create_with_memory(
            actor,
            SimpleNamespace(
                title="Q", request="same", task_type="tier0.answer", memory_control="edit"
            ),
            main_mod,
        )
    else:
        result = await mod._run_chat_with_memory(
            actor,
            SimpleNamespace(
                messages=[{"role": "user", "content": "same"}],
                task_type="tier0.answer",
                memory_control="edit",
            ),
            main_mod,
        )

    bracket = result["memory_bracket"]
    assert paid["n"] == 1, f"must not re-pay after remember outage; paid_n={paid['n']}"
    assert bracket["paid_calls"] == 1
    assert bracket["memory_unavailable"] is True
    assert bracket["memory_status"] == "memory unavailable"
    assert bracket["answered_from_memory"] is False
    assert "identical_reuse" not in [s.get("action") for s in bracket["steps"]]
    assert any(
        s.get("action") == "memory_unavailable" and s.get("after") == "paid"
        for s in bracket["steps"]
    )
    assert memory.remembers == 0
    assert _snapshot_receipts(memory) == json.dumps({"receipts": []}, sort_keys=True).encode()
    # Identical repeat must NOT be free — nothing was remembered.
    paid["n"] = 0
    if path == "task":
        result2 = await mod._run_task_create_with_memory(
            actor,
            SimpleNamespace(
                title="Q", request="same", task_type="tier0.answer", memory_control="edit"
            ),
            main_mod,
        )
    else:
        result2 = await mod._run_chat_with_memory(
            actor,
            SimpleNamespace(
                messages=[{"role": "user", "content": "same"}],
                task_type="tier0.answer",
                memory_control="edit",
            ),
            main_mod,
        )
    assert paid["n"] == 1
    assert result2["memory_bracket"]["answered_from_memory"] is False
    assert "identical_reuse" not in [s.get("action") for s in result2["memory_bracket"]["steps"]]


def test_classify_workspace_command_failure_ts_unit_via_node():
    """TS unit: TypeError/non-Error → error; typed outage/503/timeout → outage; auth → auth."""
    import subprocess

    script_path = ROOT / "tests" / "_classify_outage_unit.cjs"
    script_path.write_text(
        """const fs = require("fs");
const src = fs.readFileSync("workspace/lib/workspace-gates.ts", "utf8");
const start = src.indexOf("function isAuthOrScopeFailure");
const end = src.indexOf("function memoryUnavailableBracket");
if (start < 0 || end < 0) throw new Error("helpers missing");
let body = src.slice(start, end);
body = body
  .replace(/export function classifyWorkspaceCommandFailure/g, "function classifyWorkspaceCommandFailure")
  .replace(/: unknown/g, "")
  .replace(/: boolean/g, "")
  .replace(/: "auth" \\| "outage" \\| "error"/g, "");
const prelude = `
  class InputError extends Error {
    constructor(message, status) { super(message); this.name = "InputError"; this.status = status || 400; }
  }
`;
const fn = new Function(prelude + body + "; return classifyWorkspaceCommandFailure;");
const classify = fn();
function check(label, err, expected) {
  const got = classify(err);
  if (got !== expected) throw new Error(label + ": got " + got + " expected " + expected);
}
check("non-error", "string-throw", "error");
check("TypeError", Object.assign(new TypeError("bug"), { name: "TypeError" }), "error");
const typed = new Error("down"); typed.name = "MemoryOutageError";
check("typed outage", typed, "outage");
check("503", new Error("workspace_command_503"), "outage");
check("timeout", new Error("etimedout"), "outage");
check("refused", new Error("econnrefused"), "outage");
check("auth 401", new Error("workspace_command_401"), "auth");
check("auth 403", new Error("workspace_command_403"), "auth");
console.log("classify_ok");
"""
    )
    try:
        proc = subprocess.run(
            ["node", str(script_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert "classify_ok" in proc.stdout
    finally:
        script_path.unlink(missing_ok=True)


def test_lifecycle_request_signing_binds_verified_actor():
    """Point 7: Tank lifecycle HMAC binds tenant+user; unsigned/mismatched refused."""
    import importlib.util
    path = ROOT / "integrations" / "workspace" / "request_signing.py"
    spec = importlib.util.spec_from_file_location("workspace_request_signing", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    key = "fixture-workspace-agent-key-for-signing-tests-only"
    tenant = str(uuid4())
    user = "user-" + uuid4().hex[:8]
    body = b'{"tenant_id":"%s","query":"x"}' % tenant.encode()
    headers = mod.sign_request(
        key=key, method="POST", path="/recall", tenant_id=tenant, user_id=user, body=body
    )
    got_tenant, got_user = mod.verify_signed_actor(
        key=key,
        method="POST",
        path="/recall",
        timestamp=headers["X-Lifecycle-Timestamp"],
        signature=headers["X-Lifecycle-Signature"],
        tenant_header=headers["X-Tervory-Tenant"],
        user_header=headers["X-Tervory-User"],
        body=body,
    )
    assert str(got_tenant) == tenant and got_user == user
    with pytest.raises(PermissionError):
        mod.verify_signed_actor(
            key=key,
            method="POST",
            path="/recall",
            timestamp=headers["X-Lifecycle-Timestamp"],
            signature="0" * 64,
            tenant_header=headers["X-Tervory-Tenant"],
            user_header=headers["X-Tervory-User"],
            body=body,
        )
    with pytest.raises(PermissionError):
        mod.verify_signed_actor(
            key=key,
            method="POST",
            path="/recall",
            timestamp="",
            signature="",
            tenant_header=tenant,
            user_header=user,
            body=body,
        )


@pytest.fixture(autouse=True)
def enabled_memory_layer(monkeypatch):
    monkeypatch.setenv("WORKSPACE_MEMORY_ENABLED", "true")
