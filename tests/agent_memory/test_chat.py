"""The existing chat SSE endpoint saves the memory ID and real zero-cost receipt."""
import json
import sys
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import command
import memory_routes
from test_command import command_pool as command_pool_fixture
from test_agent_memory_records import Encoder, memory as memory_fixture
from hermes.service import create_app
from hermes.store import InMemoryStore

command_pool = command_pool_fixture
memory = memory_fixture


@pytest.mark.asyncio
async def test_remember_chat_sse_saves_id_receipt_and_inspectable_record(memory, command_pool, monkeypatch):
    m = memory
    monkeypatch.setenv("TANK_API_KEY", "dummy-offline")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "offline-founder")

    async def forbidden(*args, **kwargs):
        pytest.fail("Remember must not call a model")

    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(
        TANK_API_KEY="dummy-offline", pool=lambda: command_pool,
        box_region=lambda: "us-east", Message=object, RouteRequest=object,
        run_route=forbidden,
    ))
    monkeypatch.setattr(command, "db", lambda: command_pool)
    app = FastAPI()
    app.include_router(command.router)
    app.include_router(memory_routes.router)
    hermes = create_app(InMemoryStore(), Encoder(), records=m.records)
    headers = {"X-Tank-Key": "dummy-offline", "X-Tervory-User": "offline-founder",
               "X-Tervory-Tenant": m.tenant}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=hermes), base_url="http://hermes") as h:
        async def proxy(method, path, actor, *, body=None, params=None):
            response = await h.request(method, path, json=body, params=params, headers={
                "X-Tank-Key": "dummy-offline", "X-Tervory-Admin": actor,
            })
            if not response.is_success:
                raise HTTPException(response.status_code, response.json()["detail"])
            return response.json()

        monkeypatch.setattr(memory_routes, "hermes", proxy)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank", headers=headers) as t:
            thread = (await t.post("/v1/command/threads", json={})).json()["thread_id"]
            path = "/v1/command/threads/" + thread
            response = await t.post(path + "/turn", json={"text": f"Remember for {m.agent} that offline deliveries arrive Tuesday."})
            assert response.status_code == 200 and "event: done" in response.text
            assert "event: error" not in response.text
            events = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]
            receipt = next(event for event in events if "rows" in event)
            assert receipt["totals"]["cost_usd"] == 0
            saved = (await t.get(path)).json()
            message = saved["messages"][-1]
            claim, identity = message["content"].split("\n\n")
            assert claim == "offline deliveries arrive Tuesday."
            assert message["role"] == "assistant" and message["repeatable"] is True
            expected_id = uuid.uuid5(uuid.UUID(message["message_id"]), "memory:" + m.agent)
            assert uuid.UUID(identity) == expected_id
            assert any(event.get("text") == message["content"] for event in events)
            inspected = await t.get("/v1/memory/records/" + identity)
            assert inspected.status_code == 200
            assert inspected.json()["id"] == identity
            assert inspected.json()["claim"] == claim
            assert inspected.json()["tenant_id"] == m.tenant
            ledger = await command_pool.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2",
                                                uuid.UUID(receipt["rows"][0]["ledger_id"]), uuid.UUID(m.tenant))
            assert ledger["cost_usd"] == 0 and ledger["tokens_in"] == ledger["tokens_out"] == 0
            assert ledger["task_id"] == uuid.UUID(message["message_id"])
            for tenant in (m.tenant, m.other):
                denied = await t.get("/v1/memory/records/" + identity, headers={
                    "X-Tervory-User": "offline-client", "X-Tervory-Tenant": tenant,
                })
                assert denied.status_code == 404
