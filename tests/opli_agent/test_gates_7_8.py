"""Gates 7+8 offline: memory bracket, free steps, controls, isolation, costs."""
from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "opli"))
sys.path.insert(0, str(ROOT / "integrations" / "tank"))

from fixed_fake import FIXED_FAKE_PER_CALL
from agents.opli.gates_memory import (
    FakeMemory,
    MemoryScopeError,
    apply_corrections,
    apply_memory_edit,
    apply_memory_forget,
    assert_remember_fields_nonempty,
    brain_enabled,
    build_memory_text,
    identical_reuse_from_memories,
    memory_enabled,
    product_to_tank_agent_memory,
    run_with_memory,
    select_tenant_user_memories,
    set_memory_control,
    task_input_hash,
    view_memories,
)
from agents.opli.request_path import run_code_request


def _fixed_paid_result(**result_fields):
    return {
        "cost_usd": FIXED_FAKE_PER_CALL["cost_usd"],
        "tokens_in": FIXED_FAKE_PER_CALL["tokens_in"],
        "tokens_out": FIXED_FAKE_PER_CALL["tokens_out"],
        "result": result_fields,
    }


@pytest.mark.asyncio
async def test_product_request_tank_route_receipt_then_memory():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "repo-map-summary"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(
            repo="acme/app",
            repo_map=["src/", "tests/"],
            conventions=["pytest-first"],
            commands=["npm test"],
            fixes=["pin-node-22"],
            decisions=["no-product-brain"],
            outcome="mapped",
        )

    receipt = await run_with_memory(
        memory,
        tenant_id=tenant,
        user_id=user,
        task_key=task_key,
        task={"title": "Summarize repo", "request": "What lives where?", "repo": "acme/app"},
        paid_call=paid,
    )
    assert [step["action"] for step in receipt["steps"]] == ["recall", "tank_route", "remember"]
    assert receipt["paid_calls"] == 1 and paid_calls == 1
    assert receipt["cost_usd"] == pytest.approx(FIXED_FAKE_PER_CALL["cost_usd"])
    assert receipt["tokens_in"] == FIXED_FAKE_PER_CALL["tokens_in"]
    assert receipt["tokens_out"] == FIXED_FAKE_PER_CALL["tokens_out"]
    assert receipt["brain_enabled"] is False and brain_enabled() is False
    assert memory.remembers == 1
    assert memory.rows[0]["meta"]["input_hash"] == task_input_hash(
        {"title": "Summarize repo", "request": "What lives where?", "repo": "acme/app"}
    )
    assert "repo_map=src/,tests/" in memory.rows[0]["text"]
    assert "outcome=mapped" in memory.rows[0]["text"]
    assert "receipt=cost=" in memory.rows[0]["text"]


@pytest.mark.asyncio
async def test_correction_applies_next_time_with_no_paid_call():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "repo-retry-lint"
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(
            repo="acme/app",
            repo_map=["src/"],
            conventions=["ruff"],
            commands=["ruff check"],
            correction="prefer-ruff-over-flake8",
            outcome="linted",
        )

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"title": "Lint", "request": "Fix lint", "repo": "acme/app"}, paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"title": "Lint", "request": "Fix lint", "repo": "acme/app"}, paid_call=paid,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert "prefer-ruff-over-flake8" in second["result"]["applied_corrections"]
    assert "apply_correction" in [step["action"] for step in second["steps"]]


@pytest.mark.asyncio
async def test_second_user_and_second_tenant_see_nothing():
    memory = FakeMemory()
    tenant_a, user_a = str(uuid4()), str(uuid4())
    tenant_b, user_b = str(uuid4()), str(uuid4())
    task = {"title": "Private", "request": "Status?", "repo": "acme/private"}
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(
            repo="acme/private", repo_map=["src/"], commands=["npm test"],
            fixes=["keep-private"], outcome="ok",
        )

    seed = await run_with_memory(
        memory, tenant_id=tenant_a, user_id=user_a, task_key="private", task=task, paid_call=paid,
    )
    assert seed["paid_calls"] == 1
    other_user = await run_with_memory(
        memory, tenant_id=tenant_a, user_id=user_b, task_key="private", task=task, paid_call=paid,
    )
    assert other_user["answered_from_memory"] is False and other_user["paid_calls"] == 1
    other_tenant = await run_with_memory(
        memory, tenant_id=tenant_b, user_id=user_b, task_key="private", task=task, paid_call=paid,
    )
    assert other_tenant["answered_from_memory"] is False and other_tenant["paid_calls"] == 1
    assert paid_calls == 3


@pytest.mark.asyncio
async def test_same_task_twice_reports_cost_and_tokens_each_run():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task_key = "repo-cost-twice"
    task = {"title": "Costed", "request": "Status?", "repo": "acme/app", "task_type": "repo-cost-twice"}
    paid_calls = 0
    fixed = FIXED_FAKE_PER_CALL

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(
            repo="acme/app", repo_map=["src/"], commands=["npm test"],
            fixes=["cached-map"], outcome="status",
        )

    first = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid,
    )
    second = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key, task=task, paid_call=paid,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert first["cost_usd"] == pytest.approx(fixed["cost_usd"])
    assert first["tokens_in"] == fixed["tokens_in"] and first["tokens_out"] == fixed["tokens_out"]
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["tokens_out"] == 0
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0 and second["paid_calls"] == 0
    assert second.get("would_have_cost_usd") == pytest.approx(fixed["cost_usd"])
    assert "identical_reuse" in [s["action"] for s in second["steps"]]
    changed = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key=task_key,
        task={"title": "Costed", "request": "Status? changed", "repo": "acme/app", "task_type": "repo-cost-twice"},
        paid_call=paid,
    )
    assert changed["paid_calls"] == 1 and paid_calls == 2
    assert changed["cost_usd"] == pytest.approx(fixed["cost_usd"])


@pytest.mark.asyncio
async def test_forget_and_memory_off_skip_store(monkeypatch):
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    task = {"title": "Drop", "request": "Go", "repo": "acme/drop", "task_type": "repo-map-summary"}
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(repo="acme/drop", commands=["npm test"], fixes=["seed"], outcome="seeded")

    seed = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="drop", task=task, paid_call=paid,
    )
    assert seed["paid_calls"] == 1
    memory_id = memory.rows[0]["id"]
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="forget")
    await apply_memory_forget(
        memory, memory_id=memory_id, tenant_id=tenant, user_id=user, memory_control="forget"
    )
    assert memory.forgets == 1
    after_forget = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="drop", task=task, paid_call=paid,
    )
    assert after_forget["paid_calls"] == 1 and after_forget["answered_from_memory"] is False

    remembers_before = memory.remembers
    off = await run_with_memory(
        memory, tenant_id=tenant, user_id=user, task_key="drop", task=task, paid_call=paid,
        memory_control="off",
    )
    assert off["memory_enabled"] is False
    assert off["paid_calls"] == 1
    assert [step["action"] for step in off["steps"]] == ["memory_off", "tank_route"]
    assert memory.remembers == remembers_before  # off path never stores


@pytest.mark.asyncio
async def test_free_code_skill_runs_before_tank_and_skips_paid():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid_calls = 0

    async def paid(_task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(outcome="should-not-run")

    async def code_free(task):
        return {"result": {"outcome": "formatted", "commands": ["format"], "repo": task.get("repo")}}

    receipt = await product_to_tank_agent_memory(
        memory, tenant_id=tenant, user_id=user, task_key="format",
        task={"title": "fmt", "request": "format", "repo": "acme/app"},
        tank_agent_call=paid, code_free=code_free,
    )
    assert paid_calls == 0 and receipt["paid_calls"] == 0
    assert [s["action"] for s in receipt["steps"]] == ["code_skill", "code_free_done"]
    assert receipt["result"]["outcome"] == "formatted"


@pytest.mark.asyncio
async def test_code_request_path_free_then_tank():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid_calls = 0

    async def tank_agent(task):
        nonlocal paid_calls
        paid_calls += 1
        return _fixed_paid_result(
            repo=task.get("repo"), commands=["tervory code"], decisions=["tank-code-turn"],
            outcome="answered",
        )

    first = await run_code_request(
        memory, tenant_id=tenant, user_id=user, text="Summarize src", repo="acme/app",
        tank_agent_call=tank_agent,
    )
    assert first["paid_calls"] == 1 and paid_calls == 1
    assert "recall" in [s["action"] for s in first["steps"]]
    assert "tank_route" in [s["action"] for s in first["steps"]]
    assert "remember" in [s["action"] for s in first["steps"]]
    # Exact repeat: free identical reuse before Tank.
    second = await run_code_request(
        memory, tenant_id=tenant, user_id=user, text="Summarize src", repo="acme/app",
        tank_agent_call=tank_agent,
    )
    assert second["paid_calls"] == 0 and paid_calls == 1
    assert second["answered_from_memory"] is True
    assert second["cost_usd"] == 0.0 and second["tokens_in"] == 0
    assert second.get("would_have_cost_usd") == pytest.approx(FIXED_FAKE_PER_CALL["cost_usd"])


@pytest.mark.asyncio
async def test_live_memory_view_edit_forget_and_control():
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="edit")
    saved = await memory.remember(
        tenant,
        build_memory_text(summary="live entry", outcome="kept", repo="acme/app", receipt="cost=0"),
        "opli.task",
        "opli:task:live",
        meta={"user_id": user, "task_key": "live"},
    )
    viewed = await view_memories(memory, tenant_id=tenant, user_id=user, task_key="live")
    assert viewed["memory_control"] == "edit"
    assert any(row["id"] == saved["id"] for row in viewed["memories"])
    edited = await apply_memory_edit(
        memory, memory_id=saved["id"], tenant_id=tenant, user_id=user,
        text=build_memory_text(summary="edited", outcome="changed", repo="acme/app", receipt="cost=0"),
        memory_control="edit",
    )
    assert edited.get("updated") is True
    await set_memory_control(memory, tenant_id=tenant, user_id=user, control="forget")
    await apply_memory_forget(
        memory, memory_id=saved["id"], tenant_id=tenant, user_id=user, memory_control="forget"
    )
    remaining = select_tenant_user_memories(memory.rows, tenant_id=tenant, user_id=user)
    assert all(row["id"] != saved["id"] for row in remaining)
    assert not any(row.get("kind") == "opli.task" for row in remaining)
    # Foreign forget refused
    other = str(uuid4())
    with pytest.raises(MemoryScopeError):
        await apply_memory_forget(
            memory, memory_id="missing", tenant_id=tenant, user_id=other, memory_control="forget"
        )


def test_remembered_fields_never_hardcoded_empty():
    with pytest.raises(ValueError):
        assert_remember_fields_nonempty({"repo_map": [], "outcome": "x"})
    with pytest.raises(ValueError):
        assert_remember_fields_nonempty({"receipt": "", "outcome": "x"})
    with pytest.raises(ValueError):
        build_memory_text()
    cleaned = assert_remember_fields_nonempty({
        "outcome": "done", "repo_map": ["src/"], "receipt": "cost=0.05;tokens_in=10;tokens_out=3",
    })
    assert cleaned["repo_map"] == ["src/"]
    corrected = apply_corrections({"title": "A"}, ["use-saved-convention"])
    assert corrected["applied_corrections"] == ["use-saved-convention"]
    with pytest.raises(ValueError):
        build_memory_text(summary="leak api_key=should-fail")
    assert memory_enabled() is True and brain_enabled() is False
    assert identical_reuse_from_memories([], task_key="k", input_hash="abc") is None
    with pytest.raises(MemoryScopeError):
        from agents.opli.gates_memory import require_authenticated_scope
        require_authenticated_scope(tenant_id="", user_id="u")


def test_opli_memory_module_exposes_live_routes():
    import opli_memory
    assert "opli.code-turn" in opli_memory.CLIENT_TOOLS
    assert "opli.memory.view" in opli_memory.CLIENT_TOOLS
    assert "opli.memory.control" in opli_memory.CLIENT_TOOLS
    assert "opli.memory.edit" in opli_memory.CLIENT_TOOLS
    assert "opli.memory.forget" in opli_memory.CLIENT_TOOLS
    adapters = opli_memory.adapters(type("C", (), {"Adapter": lambda *a, **k: a})())
    assert "/v1/command/opli/code-turn" in str(adapters["opli.code-turn"])


def test_cli_wires_memory_commands_and_code_turn_memory_wrap():
    client = (ROOT / "cli" / "src" / "client.mjs").read_text()
    assert "name === 'memory'" in client
    assert "/v1/command/opli/memory.view" in client
    assert "/v1/command/opli/memory.control" in client
    assert "/v1/command/opli/memory.forget" in client
    assert "/v1/command/opli/memory.edit" in client
    # CLI keeps /threads/{id}/code-turn; tank patch wraps command.code_turn with memory.
    code = (ROOT / "cli" / "src" / "code-mode.mjs").read_text()
    assert "/v1/command/threads/${encodeURIComponent(thread)}/code-turn" in code
    opli = (ROOT / "integrations" / "tank" / "opli_memory.py").read_text()
    assert "code_turn_with_memory" in opli
    assert '@target_router.post("/opli/code-turn")' in opli


@pytest.mark.asyncio
async def test_invalid_scope_refused_before_memory_or_paid():
    memory = FakeMemory()
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {"cost_usd": FIXED_FAKE_PER_CALL["cost_usd"], "tokens_in": 1, "tokens_out": 1, "result": {"outcome": "x"}}

    with pytest.raises(MemoryScopeError):
        await run_with_memory(
            memory, tenant_id="", user_id="u1", task_key="t", task={"title": "x", "task_type": "command.code"},
            paid_call=paid,
        )
    with pytest.raises(MemoryScopeError):
        await run_with_memory(
            memory, tenant_id="00000000-0000-0000-0000-000000000011", user_id="", task_key="t",
            task={"title": "x", "task_type": "command.code"}, paid_call=paid,
        )
    assert paid_calls == 0 and memory.recalls == 0 and memory.remembers == 0


@pytest.mark.asyncio
async def test_memory_outage_answers_without_memory_never_serves_repeat():
    class OutageMemory(FakeMemory):
        async def recall(self, *a, **k):
            raise RuntimeError("hermes answered 503: memory store unreachable")

    memory = OutageMemory()
    paid_calls = 0

    async def paid(task):
        nonlocal paid_calls
        paid_calls += 1
        return {
            "cost_usd": FIXED_FAKE_PER_CALL["cost_usd"],
            "tokens_in": FIXED_FAKE_PER_CALL["tokens_in"],
            "tokens_out": FIXED_FAKE_PER_CALL["tokens_out"],
            "result": {"outcome": "live-after-outage"},
        }

    tenant = "00000000-0000-0000-0000-000000000011"
    receipt = await run_with_memory(
        memory, tenant_id=tenant, user_id="member-1", task_key="outage-task",
        task={"title": "outage", "task_type": "command.code", "n": 1}, paid_call=paid,
    )
    assert receipt.get("memory_unavailable") is True
    assert receipt["answered_from_memory"] is False
    assert receipt["paid_calls"] == 1 and paid_calls == 1
    assert receipt["cost_usd"] == pytest.approx(FIXED_FAKE_PER_CALL["cost_usd"])
    assert "memory_unavailable" in [s["action"] for s in receipt["steps"]]


@pytest.fixture(autouse=True)
def enabled_memory_layer(monkeypatch):
    monkeypatch.setenv("OPLI_MEMORY_ENABLED", "true")
