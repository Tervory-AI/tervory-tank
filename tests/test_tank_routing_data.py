"""Offline routing data contracts: disposable SQL and a gateway stub only."""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql://placeholder@127.0.0.1/placeholder")
os.environ.setdefault("LITELLM_MASTER_KEY", "placeholder")
os.environ.setdefault("TANK_API_KEY", "placeholder")

import bench
import command
import main
import routing_data
import skala_revalidation
from gold import PLATFORM_TENANT
from test_train1 import database as database

TASK = "routing.placeholder"
TENANT = UUID("00000000-0000-0000-0000-000000000081")
OTHER = UUID("00000000-0000-0000-0000-000000000082")
ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def routing(database, monkeypatch):
    db, _ = database
    monkeypatch.setattr(main, "_pool", db)
    monkeypatch.setattr(main, "_http", None)
    monkeypatch.setattr(main, "_roster_cache", None)
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", "")
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(routing_data, "_CACHE", None)
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="kimi-lite", priority="urgent"))
    return db


async def read(db, tenant=None):
    return dict(await db.fetchrow("SELECT * FROM tank.policy WHERE task_type=$1 AND tenant_id IS NOT DISTINCT FROM $2", TASK, tenant))


async def approve(db, name="base.placeholder"):
    await db.execute("""INSERT INTO tank.skills(id,version,agent,rung,task_type,state)
        VALUES($1,'1.0.0','base',1,$2,'approved')""", name, TASK)


async def jobs(db, swap=None):
    return [dict(row) for row in await db.fetch("""SELECT * FROM tank.skill_revalidations
        WHERE tenant_id=$1 AND task_type=$2 AND ($3::uuid IS NULL OR swap_id=$3) ORDER BY skill_id""",
        PLATFORM_TENANT, TASK, swap)]


async def result(job, passed=True):
    token = skala_revalidation.ACTIVE.set(job)
    try:
        return await skala_revalidation.record(main, {"score": int(passed), "threshold": 1,
            "eligible": True, "passed": int(passed), "total": 1, "cost_usd": 0, "details": []})
    finally:
        skala_revalidation.ACTIVE.reset(token)


async def dispatch(policy=None, model="kimi-lite", generation=None, offpeak=False, text="placeholder", box="us-east"):
    return await routing_data.dispatch(main, policy=policy or {}, model=model,
        generation=generation or {}, offpeak=offpeak, text=text,
        refusal_args={"tenant_id": str(TENANT), "box": box, "task_type": TASK,
                      "caller": None, "skill": None, "pool_read": False})


@pytest.mark.asyncio
async def test_lists_config_null_explicit_empty_and_dispatch_exceptions(routing):
    assert (await dispatch({"fallbacks": ["luna", "haiku"]}))["fallbacks"] == ["luna", "haiku"]
    assert (await dispatch({"fallbacks": None}))["fallbacks"] == ["luna", "haiku", "flash-lite", "grok", "flash"]
    assert (await dispatch({"fallbacks": []}))["fallbacks"] == []
    assert "fallbacks" not in await dispatch(generation={"disable_fallbacks": True})
    assert await dispatch(offpeak=True) == {"disable_fallbacks": True}


@pytest.mark.asyncio
async def test_provider_and_identifier_filters_use_the_primary_arguments(routing, monkeypatch):
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({str(TENANT): ["kimi-lite", "haiku", "novita"]}))
    assert (await dispatch())["fallbacks"] == ["haiku"]
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", "")
    monkeypatch.setenv("ZA_HOSTED_MODELS", "haiku")
    args = {"fallbacks": ["luna", "haiku"]}
    assert (await dispatch(args, model="haiku", text="placeholder ID 8001015009087", box="za"))["fallbacks"] == ["haiku"]


@pytest.mark.asyncio
async def test_restricted_tenant_pins_direct_even_on_override_or_offpeak(routing, monkeypatch):
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({str(TENANT): ["kimi-lite", "haiku"]}))
    for generation, offpeak in [({}, False), ({"disable_fallbacks": True}, False), ({}, True)]:
        body = await dispatch(generation=generation, offpeak=offpeak)
        assert body == {"model": "kimi-lite-direct", "disable_fallbacks": True}
    chain = await dispatch({"fallbacks": ["kimi-lite"]}, model="haiku")
    assert chain["fallbacks"] == [{"model": "kimi-lite-direct", "disable_fallbacks": True}]


@pytest.mark.asyncio
@pytest.mark.parametrize("names", [
    ["missing-placeholder"], ["build-placeholder"], ["skill:placeholder"], ["cache:placeholder"],
    ["tool:placeholder"], ["routellm:placeholder"], ["kimi-lite"], ["haiku", "haiku"],
    ["sonnet", "luna"], ["luna", "haiku", "flash-lite", "grok", "flash", "grok-top", "sol", "sonnet"],
])
async def test_put_and_confirm_preparation_refuse_each_bad_list(routing, names):
    with pytest.raises(HTTPException) as error:
        await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="kimi-lite", fallbacks=names))
    assert error.value.status_code == 422
    actor = command.Actor(TENANT, "founder-placeholder", True)
    async with routing.acquire() as conn:
        with pytest.raises(HTTPException) as error:
            await command.policy_fallbacks_prepare(conn, {"task_type": TASK, "fallbacks": names}, actor)
    assert error.value.status_code == 422
    assert (await read(routing))["fallbacks"] is None


@pytest.mark.asyncio
async def test_shared_swap_releases_only_after_every_pass_and_keeps_approval(routing):
    await approve(routing)
    await approve(routing, "base.placeholder-two")
    answer = await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="sol", fallbacks=["haiku"]))
    assert answer == {"ok": True, "held": True}
    row = await read(routing)
    swap = row["held_swap_id"]
    assert row["model"] == "kimi-lite" and row["fallbacks"] is None
    pending = await jobs(routing)
    assert len(pending) == 2 and {j["swap_id"] for j in pending} == {swap}
    await result(pending[0])
    assert (await read(routing))["model"] == "kimi-lite"
    await result(pending[1])
    row = await read(routing)
    assert row["model"] == "sol" and row["fallbacks"] == ["haiku"] and row["held_policy"] is None
    assert await routing.fetchval("SELECT count(*) FROM tank.skills WHERE task_type=$1 AND state='approved'", TASK) == 2
    actions = await routing.fetch("SELECT action,detail FROM tank.policy_log WHERE task_type=$1 ORDER BY created_at", TASK)
    assert [r["action"] for r in actions] == ["held", "released"]
    assert {json.loads(r["detail"])["swap_id"] for r in actions} == {str(swap)}


@pytest.mark.asyncio
async def test_failure_clears_hold_without_demotion_and_newer_swap_wins(routing):
    await approve(routing)
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="sol"))
    old = (await jobs(routing))[0]
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="astra"))
    current = await read(routing)
    new = (await jobs(routing, current["held_swap_id"]))[0]
    await result(old)
    assert (await read(routing))["model"] == "kimi-lite"
    assert (await read(routing))["held_swap_id"] == new["swap_id"]
    await result(new, False)
    assert (await read(routing))["model"] == "kimi-lite" and (await read(routing))["held_policy"] is None
    assert await routing.fetchval("SELECT state FROM tank.skills WHERE id='base.placeholder'") == "approved"
    assert await routing.fetchval("SELECT action FROM tank.policy_log WHERE task_type=$1 ORDER BY created_at DESC LIMIT 1", TASK) == "hold_failed"


@pytest.mark.asyncio
async def test_new_tenant_uses_default_columns_until_release_and_is_isolated(routing):
    await approve(routing)
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, tenant_id=TENANT, model="sol", max_tokens_out=333))
    row = await read(routing, TENANT)
    assert row["model"] == "kimi-lite" and row["max_tokens_out"] == 1024 and row["priority"] == "urgent"
    await result((await jobs(routing))[0])
    assert (await read(routing, TENANT))["model"] == "sol"
    assert (await read(routing, TENANT))["max_tokens_out"] == 333
    assert (await read(routing))["model"] == "kimi-lite"
    assert await routing.fetchval("SELECT count(*) FROM tank.policy WHERE task_type=$1 AND tenant_id=$2", TASK, OTHER) == 0


@pytest.mark.asyncio
async def test_both_rollbacks_cancel_holds_and_old_jobs_cannot_release(routing):
    await approve(routing)
    for automatic in (False, True):
        await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="sol"))
        job = (await jobs(routing, (await read(routing))["held_swap_id"]))[0]
        if automatic:
            before = await read(routing)
            move = main.graduate.Move("rollback", {**before, "model": "kimi-lite", "rung": 1}, "placeholder")
            async with routing.acquire() as conn:
                async with conn.transaction():
                    await main._apply_move(conn, move, before, "founder-placeholder")
        else:
            assert (await main.rollback(TASK, main.PromoteBody(by="founder-placeholder")))["model"] == "kimi-lite"
        assert (await read(routing))["held_swap_id"] is None
        await result(job)
        assert (await read(routing))["model"] == "kimi-lite"
    assert len(await jobs(routing)) == 2


@pytest.mark.asyncio
async def test_live_catalog_is_used_without_a_config_file(routing, monkeypatch, tmp_path):
    asked = []
    def respond(request):
        asked.append(request.url.path)
        if request.url.path == "/model/info":
            return httpx.Response(200, json={"data": [
                {"model_name": "kimi-lite", "model_info": {"id": "placeholder-direct"}},
                {"model_name": "kimi-lite", "model_info": {"id": "placeholder-hf", "host": "novita"}}]})
        return httpx.Response(200, json={"current_values": {"fallbacks": [{"kimi-lite": ["haiku"]}]}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        monkeypatch.setattr(main, "_http", client)
        monkeypatch.setattr(main, "_roster_path", lambda: tmp_path / "placeholder-missing.yaml")
        assert (await dispatch())["fallbacks"] == ["haiku"]
        monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({str(TENANT): ["kimi-lite"]}))
        assert await dispatch() == {"model": "placeholder-direct", "disable_fallbacks": True}
    assert asked == ["/model/info", "/router/settings"]


@pytest.mark.asyncio
async def test_roster_price_book_and_quotes_keep_first_deployment(routing):
    import yaml
    import graduate
    rows = yaml.safe_load((ROOT / "litellm/config.yaml").read_text())["model_list"]
    names = [r["name"] for r in await main.list_models()]
    assert names.count("kimi-lite") == 1
    assert bench.price_book(rows)["kimi-lite"]["input"] == __import__("decimal").Decimal("0.00000095")
    quotes = graduate.quotes_from_roster(rows)
    assert [q.name for q in quotes].count("kimi-lite") == 1


@pytest.fixture
def gateway(monkeypatch):
    bodies = []
    class Gateway:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            bodies.append(kwargs["json"])
            return httpx.Response(200, headers={"x-litellm-response-cost": "0.0000042", "content-type": "application/json",
                "x-litellm-model-group": kwargs["json"]["model"]},
                json={"choices": [{"message": {"content": "placeholder answer"}}],
                      "usage": {"prompt_tokens": 1, "completion_tokens": 1}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(main.httpx, "AsyncClient", Gateway)
    return bodies


@pytest.mark.asyncio
async def test_gateway_receipt_keeps_generation_and_batch_compatibility(routing, gateway):
    import execution_receipt
    import batch_providers
    bodies = gateway
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="kimi-lite", priority="urgent", fallbacks=["haiku"]))
    req = main.RouteRequest(tenant_id=TENANT, agent="base", task_type=TASK,
                           messages=[main.Message(role="user", content="placeholder question")])
    answer = await main.run_route(req)
    # Tank admits configured fallback seats individually; the gateway may not
    # spend on an invisible fallback while fulfilling this request.
    assert bodies[0]["disable_fallbacks"] is True and "fallbacks" not in bodies[0]
    assert (await read(routing))["fallbacks"] == ["haiku"]
    assert answer.cost_usd == 0.0000042
    ledger = await routing.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", answer.ledger_id, TENANT)
    assert float(ledger["cost_usd"]) == 0.0000042
    expected = execution_receipt.capture(ledger_id=str(answer.ledger_id), tenant_id=str(TENANT),
        task_type=TASK, requested_model="kimi-lite", answered_model="kimi-lite",
        dispatched={"max_tokens": 1024, "disable_fallbacks": True}, headers={}, response={}, delivered=True)
    assert answer.execution["dispatched_settings_hash"] == expected["dispatched_settings_hash"]
    assert answer.execution["dispatched_settings_hash"] is not None
    await main.put_policy("command.turn", main.PolicyRow(task_type="command.turn", model="kimi-lite", priority="urgent"))
    await main.run_route(req.model_copy(update={"task_type": "command.turn"}), model_override="haiku")
    assert "fallbacks" not in bodies[-1] and bodies[-1]["disable_fallbacks"] is True
    await main.run_route(req, _paid_limit=1.0)
    assert "fallbacks" not in bodies[-1] and bodies[-1]["disable_fallbacks"] is True
    queued = req.model_copy(update={"priority": "offpeak"})
    await main.run_route(queued, _offpeak_dispatch=True)
    assert "fallbacks" not in bodies[-1] and bodies[-1]["disable_fallbacks"] is True
    generation = {}
    assert batch_providers.compatible({"provider": "anthropic", "native": "placeholder"}, req.model_dump()["messages"], generation)
    assert generation == {}


@pytest.mark.asyncio
async def test_founder_policy_read_and_confirmed_edit_are_scoped_with_code_receipts(routing):
    founder = command.Actor(TENANT, "founder-placeholder", True)
    ordinary = command.Actor(TENANT, "ordinary-placeholder", False)
    for tool in ("tank.policy", "tank.policy.fallbacks"):
        with pytest.raises(HTTPException):
            command.require_tool(ordinary, tool)
        assert tool in command.ADAPTERS and tool in command.FOUNDER_TOOLS
    before = await command.tank_policy(TASK, False, founder)
    assert before["model"] == "kimi-lite" and before["fallbacks"] is None and before["held"] is None
    await command.tank_policy_fallbacks(command.PolicyFallbackArgs(task_type=TASK, fallbacks=["haiku"]), founder)
    after = await command.tank_policy(TASK, False, founder)
    assert after["fallbacks"] == ["haiku"] and after["tenant_id"] == TENANT
    assert (await read(routing))["fallbacks"] is None
    assert await routing.fetchval("SELECT count(*) FROM tank.policy WHERE task_type=$1 AND tenant_id=$2", TASK, OTHER) == 0
    receipts = await routing.fetch("SELECT cost_usd,rung FROM tank.ledger WHERE tenant_id=$1 AND id=ANY($2::uuid[])",
        TENANT, [UUID(before["ledger_id"]), UUID(after["ledger_id"])])
    assert len(receipts) == 2 and all(r["cost_usd"] == 0 and r["rung"] == 3 for r in receipts)
    await approve(routing)
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, tenant_id=TENANT, model="sol"))
    held = await command.tank_policy(TASK, False, founder)
    assert held["model"] == "kimi-lite" and held["held"]["model"] == "sol"
    assert held["held"]["done"] == 0 and held["held"]["total"] == 1


@pytest.mark.asyncio
async def test_cache_revision_changes_once_for_new_columns(routing):
    row = await read(routing)
    req = main.RouteRequest(tenant_id=TENANT, agent="base", task_type=TASK,
        messages=[main.Message(role="user", content="placeholder")])
    messages = [{"role": "user", "content": "placeholder"}]
    old = {k: v for k, v in row.items() if k not in {"fallbacks", "held_policy", "held_swap_id", "held_at"}}
    before = main._cache_identity(req, old, messages, 1024, None)
    after = main._cache_identity(req, row, messages, 1024, None)
    assert before[0] != after[0] and before[1:] == after[1:]
    assert after == main._cache_identity(req, row, messages, 1024, None)


@pytest.mark.asyncio
async def test_promote_replaces_an_existing_hold_and_reports_it(routing, monkeypatch):
    await approve(routing)
    monkeypatch.setattr(main, "_load_evidence", AsyncMock(return_value=main.graduate.Evidence(samples=300, agreement=1)))
    for candidate in ("sol", "astra"):
        await routing.execute("UPDATE tank.policy SET candidate_model=$2,shadow_rate=1 WHERE task_type=$1 AND tenant_id IS NULL", TASK, candidate)
        answer = await main.promote(TASK, main.PromoteBody(by="founder-placeholder"))
        assert answer["held"] is True and answer["model"] == candidate
        assert (await read(routing))["model"] == "kimi-lite"
    pending = await jobs(routing)
    assert len(pending) == 2 and len({j["swap_id"] for j in pending}) == 2
    old = next(j for j in pending if j["model"] == "sol")
    new = next(j for j in pending if j["model"] == "astra")
    await result(old)
    assert (await read(routing))["model"] == "kimi-lite"
    await result(new)
    assert (await read(routing))["model"] == "astra"
    assert (await main.rollback(TASK, main.PromoteBody()))["model"] == "kimi-lite"
    assert len(await jobs(routing)) == 2


@pytest.mark.asyncio
async def test_training_copy_while_held_never_inherits_the_default_swap(routing):
    import training
    from uuid import uuid4
    await approve(routing)
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="sol"))
    swap = (await read(routing))["held_swap_id"]
    ledger = uuid4()
    await routing.execute("""INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,
        feedback,feedback_by,cost_usd,accept_after) VALUES($1,$2,'us-east','base',$3,1,'kimi-lite',
        'rejected','founder-placeholder',0,now()-interval '1 day')""", ledger, TENANT, TASK)
    await routing.execute("""INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
        VALUES($1,$2,$3,'[{"role":"user","content":"placeholder"}]','{"text":"placeholder answer"}')""", ledger, TENANT, TASK)
    async with routing.acquire() as conn:
        await training.collect_ledger(conn, TENANT)
    row = await read(routing, TENANT)
    assert row["model"] == "kimi-lite" and row["held_swap_id"] is None and row["shadow_rate"] > 0
    assert (await read(routing))["held_swap_id"] == swap
    assert len(await jobs(routing)) == 1


@pytest.mark.asyncio
async def test_one_failure_drops_the_hold_even_while_another_job_is_pending(routing):
    await approve(routing)
    await approve(routing, "base.placeholder-two")
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="sol"))
    first, second = await jobs(routing)
    await result(first, False)
    assert (await read(routing))["held_swap_id"] is None and (await read(routing))["model"] == "kimi-lite"
    await result(second)
    assert (await read(routing))["model"] == "kimi-lite"


@pytest.mark.asyncio
async def test_foreground_receipts_use_old_model_until_all_jobs_pass(routing, gateway):
    await approve(routing)
    await approve(routing, "base.placeholder-two")
    await main.put_policy(TASK, main.PolicyRow(task_type=TASK, model="sol"))
    request = main.RouteRequest(tenant_id=TENANT, agent="base", task_type=TASK, priority="urgent",
        messages=[main.Message(role="user", content="placeholder live-path question")])
    first, second = await jobs(routing)
    before = await main.run_route(request)
    assert gateway[-1]["model"] == before.model == "kimi-lite"
    await result(first)
    midway = await main.run_route(request)
    assert gateway[-1]["model"] == midway.model == "kimi-lite"
    await result(second)
    after = await main.run_route(request)
    assert gateway[-1]["model"] == after.model == "sol"
    receipts = await routing.fetch("SELECT id,model FROM tank.ledger WHERE tenant_id=$1 AND id=ANY($2::uuid[])",
        TENANT, [before.ledger_id, midway.ledger_id, after.ledger_id])
    assert {row["id"]: row["model"] for row in receipts} == {
        before.ledger_id: "kimi-lite", midway.ledger_id: "kimi-lite", after.ledger_id: "sol"}


@pytest.mark.asyncio
async def test_restricted_foreground_body_cannot_select_the_second_host(routing, gateway, monkeypatch):
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({str(TENANT): ["kimi-lite"]}))
    request = main.RouteRequest(tenant_id=TENANT, agent="base", task_type=TASK, priority="urgent",
        messages=[main.Message(role="user", content="placeholder")])
    answer = await main.run_route(request)
    assert gateway[-1]["model"] == "kimi-lite-direct" and gateway[-1]["disable_fallbacks"] is True
    assert "fallbacks" not in gateway[-1] and answer.model == "kimi-lite"
    assert answer.execution["model"] == "kimi-lite"


@pytest.mark.asyncio
async def test_policy_confirm_card_shows_exact_data_through_existing_fields(routing, monkeypatch):
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-placeholder")
    monkeypatch.setattr(main, "TANK_API_KEY", "placeholder")
    headers = {"x-tank-key": "placeholder", "x-tervory-tenant": str(TENANT), "x-tervory-user": "founder-placeholder"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://placeholder", headers=headers) as client:
        thread = (await client.post("/v1/command/threads", json={})).json()["thread_id"]
        args = {"task_type": TASK, "fallbacks": ["haiku"], "default": True}
        proposed = await client.post(f"/v1/command/threads/{thread}/actions",
            json={"tool": "tank.policy.fallbacks", "arguments": args})
        assert proposed.status_code == 200, proposed.text
        card = proposed.json()
        assert card["status"] == "pending" and json.loads(card["arguments"]["brief_markdown"]) == args
        assert (await read(routing))["fallbacks"] is None
        confirmed = await client.post(f"/v1/command/cards/{card['card_id']}", json={"action": "confirm"})
        assert confirmed.status_code == 200, confirmed.text
        assert (await read(routing))["fallbacks"] == ["haiku"]
        read_card = await client.post(f"/v1/command/threads/{thread}/actions",
            json={"tool": "tank.policy", "arguments": {"task_type": TASK, "default": True}})
        assert read_card.status_code == 200, read_card.text
        read_id = read_card.json()["card_id"]
        reply = await client.post(f"/v1/command/cards/{read_id}", json={"action": "confirm"})
        assert reply.status_code == 200, reply.text
        snapshot = (await client.get(f"/v1/command/threads/{thread}")).json()
        data = next(card for card in snapshot["cards"] if card["card_id"] == read_id)["result"]
        shown = json.loads(data["text"])
        assert shown["model"] == "kimi-lite" and shown["fallbacks"] == ["haiku"]
