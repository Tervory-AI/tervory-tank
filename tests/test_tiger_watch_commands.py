"""TG1: placeholder watches in an in-process Tiger room; no outside services."""

from trigger_signin_fakes import set_founders
import copy
import importlib.util
import json
import socket
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import command
import httpx
import pytest
import pytest_asyncio
import tiger_watch_commands
from fastapi import Depends, FastAPI, HTTPException
from test_tiger_competitors import database as database, postgres as postgres
from trigger_commands import CONFIRMED
from watch import MemoryStore, dispatch_tenant

ROOT = Path(__file__).resolve().parents[1]
TENANT = UUID("11111111-1111-4111-8111-111111111111")
OTHER = UUID("22222222-2222-4222-8222-222222222222")
URL = "https://placeholder.example/product"
FOREIGN = "https://placeholder.example/foreign"
PREFIX = "/v1/command/tiger/watches"
CHANGES = ("pause", "resume", "remove", "bulk")


@pytest_asyncio.fixture
async def runtime(monkeypatch):
    monkeypatch.setenv("TANK_KEY", "placeholder-room-key")
    monkeypatch.setenv("TANK_KEY_TIGER", "placeholder-room-key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://placeholder@127.0.0.1/placeholder")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "placeholder-litellm-key")
    monkeypatch.setenv("TANK_API_KEY", "placeholder-tank-key")
    set_founders(monkeypatch, "placeholder-founder")
    import main
    spec = importlib.util.spec_from_file_location("placeholder_tg1_room", ROOT / "agents/tiger/app.py")
    agent = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, agent)
    spec.loader.exec_module(agent)
    store = MemoryStore()
    monkeypatch.setattr(agent, "_store", lambda: store)
    rt = SimpleNamespace(main=main, store=store, calls=[], race=False,
                         actor=command.Actor(TENANT, "placeholder-user", False, frozenset({"tiger"})))
    pool = SimpleNamespace(fetchval=AsyncMock(side_effect=lambda *args: uuid4()))
    rt.receipt = pool.fetchval
    monkeypatch.setattr(main, "pool", lambda: pool)
    monkeypatch.setattr(main, "box_region", lambda: "us-east")
    monkeypatch.setattr(main, "TANK_API_KEY", "placeholder-tank-key")

    async def legacy_home(sql, tenant):
        assert sql == "SELECT home_region FROM tank.tenants WHERE tenant_id=$1"
        assert tenant == rt.actor.tenant_id
        return None  # Explicitly unonboarded fixture actors retain their own box.

    @asynccontextmanager
    async def acquire():
        yield SimpleNamespace(fetch=AsyncMock(return_value=[{"agent": "tiger"}]), fetchval=legacy_home)
    monkeypatch.setattr(command, "db", lambda: SimpleNamespace(acquire=acquire))
    # The room's actual public-address checker runs; DNS answers are entirely local.
    real_dns = socket.getaddrinfo
    def dns(host, *args, **kwargs):
        if host in {"localhost", "127.0.0.1", "::1"}:
            return real_dns(host, *args, **kwargs)
        address = "10.0.0.1" if host == "private.placeholder.example" else (host if ":" in host or host.replace(".", "").isdigit() else "8.8.8.8")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
    monkeypatch.setattr(socket, "getaddrinfo", dns)
    for tenant, url in ((TENANT, URL), (OTHER, URL), (OTHER, FOREIGN)):
        await store.create_watch(agent._fields(agent.WatchIn(tenant_id=tenant, url=url, label="placeholder watch", every="1d"), False))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=agent.app), base_url="http://placeholder-room", headers={"X-Tank-Key": "placeholder-room-key"}) as room_client:
        class Relay:
            async def request(self, method, url, **kwargs):
                path = urlsplit(url).path
                rt.calls.append((method, path, kwargs["params"], kwargs["content"]))
                if rt.race and method == "POST":
                    rt.race = False
                    await room_client.request(method, path, **{k: kwargs[k] for k in ("params", "content", "headers")})
                response = await room_client.request(method, path, **{k: kwargs[k] for k in ("params", "content", "headers")})
                if method == "GET" and path == "/watchlist":
                    # Simulate a leaky room: Tank must still filter other tenants.
                    data = response.json()
                    data["watches"] += await store.list_watches(str(OTHER))
                    return httpx.Response(200, json=data)
                return response
        monkeypatch.setattr(main, "_http", Relay())
        app = FastAPI()
        app.include_router(tiger_watch_commands.build_router())
        app.include_router(command.router)
        app.add_api_route("/v1/tiger/watchlist", main.tiger_create_watch, methods=["POST"], dependencies=[Depends(main.require_key)])
        app.dependency_overrides[command.identity] = lambda: rt.actor
        monkeypatch.setattr(main, "app", app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder-tank") as client:
            rt.client = client
            yield rt


async def confirmed(rt, operation, args):
    tool = "tiger.watch." + operation
    action = command.validate_action(command.PlannedAction(tool=tool, arguments=args), rt.actor)
    token = CONFIRMED.set((rt.actor.tenant_id, rt.actor.user_id, uuid4(), tool, action.arguments))
    try:
        return await rt.client.post(PREFIX + "/" + operation, json=action.arguments)
    finally:
        CONFIRMED.reset(token)


@pytest.mark.asyncio
async def test_list_scopes_leaky_room_and_records_tiger_code_receipt(runtime):
    response = await runtime.client.get(PREFIX)
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert [(row["name"], row["url"]) for row in data["items"]] == [("placeholder watch", URL)]
    assert data["items"][0]["enabled"] is True and data["items"][0]["every"] == "1d"
    assert data["cost_usd"] == 0 and UUID(data["ledger_id"])
    sql, *values = runtime.receipt.call_args.args
    assert "3,'code',0,0,0" in sql and values == [TENANT, "us-east", "tiger.watches", None, "tiger"]
    assert (await runtime.client.get(PREFIX, params={"tenant_id": str(OTHER)})).status_code == 403
    assert runtime.receipt.await_count == 1
    runtime.actor = command.Actor(uuid4(), "placeholder-empty", False, frozenset({"tiger"}))
    assert (await runtime.client.get(PREFIX)).json()["total"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", CHANGES)
async def test_every_change_requires_confirmation_before_room_call(runtime, operation):
    args = {"pages": [URL]} if operation == "bulk" else {"url": URL}
    assert (await runtime.client.post(PREFIX + "/" + operation, json=args)).status_code == 409
    assert runtime.calls == []
    runtime.receipt.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", CHANGES)
async def test_foreign_confirmation_is_not_authority(runtime, operation):
    args = {"pages": [URL], "every": "1d"} if operation == "bulk" else {"url": URL}
    token = CONFIRMED.set((OTHER, runtime.actor.user_id, uuid4(), "tiger.watch." + operation, args))
    try:
        assert (await runtime.client.post(PREFIX + "/" + operation, json=args)).status_code == 409
    finally:
        CONFIRMED.reset(token)
    assert runtime.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ("pause", "resume", "remove"))
async def test_changes_target_only_exact_owned_url(runtime, operation):
    other_rows = copy.deepcopy(await runtime.store.list_watches(str(OTHER)))
    if operation == "resume":
        runtime.store.watches[0]["enabled"] = False
    for missing in (FOREIGN, URL + "/", URL + "?placeholder=1"):
        assert (await confirmed(runtime, operation, {"url": missing})).status_code == 404
    response = await confirmed(runtime, operation, {"url": URL})
    assert response.status_code == 200 and response.json()["url"] == URL
    own = await runtime.store.get_watch(str(TENANT), URL)
    assert (own is None) if operation == "remove" else (own["enabled"] is (operation == "resume"))
    assert await runtime.store.list_watches(str(OTHER)) == other_rows
    assert runtime.receipt.await_count == 1


@pytest.mark.asyncio
async def test_pause_excludes_dispatch_and_resume_restores_it(runtime):
    await confirmed(runtime, "pause", {"url": URL})
    assert await runtime.store.enabled_watches(str(TENANT)) == []
    now = datetime.now(timezone.utc)
    assert await dispatch_tenant(runtime.store, str(TENANT), now) == {"queued": []}
    assert runtime.store.jobs == []
    await confirmed(runtime, "resume", {"url": URL})
    assert await dispatch_tenant(runtime.store, str(TENANT), now) == {"queued": [URL]}
    assert len(runtime.store.jobs) == 1


@pytest.mark.asyncio
async def test_bulk_creates_five_daily_watches_counts_duplicates_and_foreign_url(runtime):
    pages = [f"https://placeholder.example/new-{i}" for i in range(4)] + [FOREIGN]
    response = await confirmed(runtime, "bulk", {"pages": [URL, *pages, pages[0]]})
    assert response.status_code == 200, response.text
    assert response.json()["total"] == 5 and response.json()["count"] == 2
    created = [row for row in await runtime.store.list_watches(str(TENANT)) if row["url"] in pages]
    assert len(created) == 5 and all(row["every"] == "1d" for row in created)
    assert all(row["enabled"] and row["threshold"] == "0" and row["label"] == row["engine"] == "" for row in created)
    assert all(all(row[key] for key in ("alert_price", "alert_stock", "alert_new_product", "alert_below_cost", "alert_market_gap")) for row in created)
    assert len([call for call in runtime.calls if call[0] == "POST"]) == 5
    again = (await confirmed(runtime, "bulk", {"pages": pages})).json()
    assert again["total"] == 0 and again["count"] == 5 and again["cost_usd"] == 0


@pytest.mark.asyncio
async def test_duplicate_created_concurrently_does_not_abort_bulk(runtime):
    runtime.race = True
    data = (await confirmed(runtime, "bulk", {"pages": [FOREIGN, "https://placeholder.example/new"]})).json()
    assert (data["total"], data["count"]) == (1, 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("pages", ([], [URL] * 51, ["file:///placeholder"], ["ftp://placeholder.example"], ["https://placeholder:placeholder@placeholder.example"]))
async def test_bulk_argument_refusals_do_not_call_room(runtime, pages):
    assert (await runtime.client.post(PREFIX + "/bulk", json={"pages": pages})).status_code == 422
    assert runtime.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ("http://127.0.0.1/placeholder", "http://10.0.0.1/placeholder", "http://169.254.169.254/placeholder", "http://[::1]/placeholder", "http://[::ffff:127.0.0.1]/placeholder", "http://private.placeholder.example/placeholder"))
async def test_bulk_private_addresses_are_refused_by_room_checker(runtime, url):
    before = copy.deepcopy(runtime.store.watches)
    response = await confirmed(runtime, "bulk", {"pages": [url]})
    assert response.status_code == 400 and response.json()["detail"] == "url not allowed"
    assert runtime.store.watches == before
    runtime.receipt.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ("tiger.watch", "tiger.watch.bulk"))
async def test_invalid_interval_is_refused_before_room_call(runtime, tool):
    args = {"url": URL} if tool == "tiger.watch" else {"pages": [URL]}
    with pytest.raises(HTTPException) as error:
        action = command.validate_action(command.PlannedAction(tool=tool, arguments={**args, "every": "2d"}), runtime.actor)
        await command.dispatch_action(action, runtime.actor)
    assert error.value.status_code == 422 and runtime.calls == []
    if tool.endswith("bulk"):
        assert (await runtime.client.post(PREFIX + "/bulk", json={**args, "every": "2d"})).status_code == 422
        assert runtime.calls == []


@pytest.mark.asyncio
async def test_single_watch_default_reaches_actual_room(runtime):
    action = command.validate_action(command.PlannedAction(tool="tiger.watch", arguments={"url": FOREIGN}), runtime.actor)
    assert action.arguments["every"] == "1d"
    status, data = await command.dispatch_action(action, runtime.actor)
    assert status == 201 and data["every"] == "1d"
    assert (await runtime.store.get_watch(str(TENANT), FOREIGN))["every"] == "1d"


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ("tiger.watches", *("tiger.watch." + op for op in CHANGES)))
async def test_no_squad_cannot_access_watch_commands(runtime, tool):
    runtime.actor = command.Actor(TENANT, "placeholder-user", False, frozenset())
    operation = tool.rsplit(".", 1)[1]
    response = await runtime.client.get(PREFIX) if tool == "tiger.watches" else await runtime.client.post(
        PREFIX + "/" + operation, json={"pages": [URL]} if operation == "bulk" else {"url": URL})
    assert response.status_code == 403 and runtime.calls == []


@pytest.mark.asyncio
async def test_all_commands_use_code_planner_without_room_or_model(runtime, monkeypatch):
    model = AsyncMock(side_effect=AssertionError("placeholder model must not run"))
    monkeypatch.setattr(runtime.main, "run_route", model)
    for tool, suffix in (("tiger.watches", ""), ("tiger.watch.pause", " " + URL), ("tiger.watch.resume", " " + URL),
                         ("tiger.watch.remove", " " + URL), ("tiger.watch.bulk", " " + URL + "\n" + FOREIGN)):
        planned = await command.route_turn(runtime.actor, [{"role": "user", "content": tool + suffix}])
        action = json.loads(planned.content)["actions"][0]
        assert action["tool"] == tool
        if tool.endswith("bulk"):
            assert action["arguments"] == {"pages": [URL, FOREIGN], "every": "1d"}
    model.assert_not_awaited()
    assert runtime.calls == []


@pytest.mark.asyncio
async def test_real_cards_confirm_paid_bulk_and_code_changes_once(runtime, database, monkeypatch):
    import trigger_commands
    monkeypatch.setattr(runtime.main, "pool", lambda: database)
    monkeypatch.setattr(command, "db", lambda: database)
    await database.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'tiger','placeholder-founder')", TENANT)
    dispatch = AsyncMock(wraps=trigger_commands.dispatch_confirmed)
    monkeypatch.setattr(trigger_commands, "dispatch_confirmed", dispatch)
    paid = AsyncMock()
    monkeypatch.setattr(__import__("controls"), "refuse_paid", paid)
    thread = (await runtime.client.post("/v1/command/threads", json={"title": "placeholder watches"})).json()["thread_id"]
    plans = [("tiger.watches", {}), ("tiger.watch.pause", {"url": URL}), ("tiger.watch.resume", {"url": URL}),
             ("tiger.watch.remove", {"url": URL}), ("tiger.watch.bulk", {"pages": [URL, FOREIGN]})]
    for tool, args in plans:
        before = len(runtime.calls)
        response = await runtime.client.post(f"/v1/command/threads/{thread}/actions", json={"tool": tool, "arguments": args})
        assert response.status_code == 200, response.text
        card = response.json()
        assert card["status"] == "pending" and len(runtime.calls) == before
        assert card["kind"] == (command.ADAPTERS["tiger.watch"].kind if tool.endswith("bulk") else "other")
        route = "/v1/command/cards/" + card["card_id"]
        previous = dispatch.await_count
        response = await runtime.client.post(route, json={"action": "confirm"})
        assert response.status_code == 200, response.text
        confirmed_card = response.json()
        assert confirmed_card["status"] == "confirmed" and confirmed_card["receipt_status"] == "recorded", confirmed_card
        assert confirmed_card["result"]["cost_usd"] == 0
        assert dispatch.await_count == previous + (tool != "tiger.watches")
        after = len(runtime.calls)
        assert (await runtime.client.post(route, json={"action": "confirm"})).json() == confirmed_card
        assert len(runtime.calls) == after
    paid.assert_awaited_once_with(task="tiger.watch.bulk", path="command.confirm")
    rows = await database.fetch("SELECT agent,task_type,cost_usd FROM tank.ledger WHERE tenant_id=$1", TENANT)
    assert len(rows) == 5 and {row["task_type"] for row in rows} == {tool for tool, _ in plans}
    assert all(row["agent"] == "tiger" and row["cost_usd"] == 0 for row in rows)
    assert all(row["every"] == "1d" for row in await runtime.store.list_watches(str(TENANT)))


def test_interval_choices_match_existing_tiger_page_and_paid_kind_matches_single():
    import re
    from typing import get_args
    choices = re.findall(r'value: "([^"]+)"', (ROOT / "workspace/app/tiger/copy.ts").read_text())
    assert list(get_args(command.WatchArgs.model_fields["every"].annotation)) == choices
    assert list(get_args(tiger_watch_commands.BulkArgs.model_fields["every"].annotation)) == choices
    assert command.ADAPTERS["tiger.watch.bulk"].paid is command.ADAPTERS["tiger.watch"].paid is True
