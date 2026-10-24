"""Radix scan follow-up: tank/agent_skills.py passes room and task type as bound parameters.

room_key() already allows only base or rig, so this was safe. These tests keep it safe if
that guard ever moves: a hostile room value never reaches SQL text, and every write stays
tied to the tenant. All gateway and database traffic is faked.
"""
import ast
import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import agent_skills as route

HOSTILE = ["base'); DELETE FROM tank.ledger; --", "rig' OR '1'='1", "Base", "tiger", "", None, 7]


class Pool:
    def __init__(self):
        self.rows = []
        self.fetched = []

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetchval(self, sql, *args):
        if "tank.standard_model_for" in sql:
            return "baseline"
        return False

    async def execute(self, sql, *args):
        self.rows.append((sql, args))

    async def fetch(self, sql, *args):
        self.fetched.append((sql, args))
        return []


@pytest.fixture
def setup(monkeypatch):
    keys = {room: uuid.uuid4().hex for room in ("base", "rig")}
    for room, key in keys.items():
        monkeypatch.setenv("TANK_KEY_" + room.upper(), key)
    pool = Pool()
    monkeypatch.setattr(route.controls, "db", lambda: pool)

    async def policy(task, tenant):
        return {"model": "serving", "baseline_model": "baseline", "rung": 1, "priority": "standard", "max_tokens_out": 100}

    async def roster():
        return [{"model_name": name, "litellm_params": {"model": "openai/gpt-fixture"},
                 "model_info": {"input_cost_per_token": 0.001, "output_cost_per_token": 0.002}} for name in ("baseline", "serving")]

    tank = SimpleNamespace(pool=lambda: pool, load_policy=policy, _roster_models=roster, box_region=lambda: "us-east",
                           model_call_refusal=lambda *a, **kw: None, graduate=SimpleNamespace(router_cannot_serve=lambda m: False),
                           LITELLM_URL="http://gateway.invalid", LITELLM_MASTER_KEY=uuid.uuid4().hex)
    original = httpx.AsyncClient

    def gateway(request):
        return httpx.Response(200, headers={"x-litellm-response-cost": "0.01", "x-litellm-model-group": "serving"}, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    monkeypatch.setattr(route.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(gateway)))
    app = FastAPI()
    app.include_router(route.build_router(tank))
    return app, tank, pool, keys, original


@pytest.mark.asyncio
@pytest.mark.parametrize("room", ["base", "rig"])
async def test_room_and_task_type_are_bound_parameters_and_rows_carry_the_tenant(setup, room):
    app, _tank, pool, keys, original = setup
    tenant = uuid.uuid4()
    async with original(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
        response = await client.post(f"/v1/agents/{room}/chat/completions",
                                     headers={"Authorization": "Bearer " + keys[room], "X-Tenant-ID": str(tenant)},
                                     json={"messages": [{"role": "user", "content": "Plan"}]})
    assert response.status_code == 200
    ledger, transcript, receipt = pool.rows
    task_type = f"agent.{room}.think"
    for sql, args in pool.rows:
        assert "'base'" not in sql and "'rig'" not in sql and "think'" not in sql
        assert args[1] == tenant  # every write is the caller's tenant
    assert "tenant_id" in ledger[0] and ledger[1][13:] == (room, task_type)
    assert transcript[1][4] == task_type and "$5" in transcript[0]
    assert receipt[1][3] == room and json.loads(receipt[1][2])["room"] == room


@pytest.mark.asyncio
@pytest.mark.parametrize("room", HOSTILE)
async def test_hostile_room_never_reaches_sql(setup, room):
    _app, tank, pool, _keys, _original = setup
    with pytest.raises(HTTPException) as refused:
        route.room_text(room)
    assert refused.value.status_code == 403
    with pytest.raises(HTTPException):
        await route.complete(tank, route.Chat(messages=[{"role": "user", "content": "x"}]), uuid.uuid4(), None, "us-east", room=room)
    with pytest.raises(HTTPException):
        await route.export_skills(tank, uuid.uuid4(), "us-east", room=room)
    assert pool.rows == [] and pool.fetched == []


@pytest.mark.asyncio
async def test_reads_bind_room_and_filter_by_tenant(setup):
    app, tank, pool, keys, original = setup
    tenant = uuid.uuid4()
    await route.export_skills(tank, tenant, "us-east", room="rig")
    sql, args = pool.fetched[-1]
    assert "s.agent=$3" in sql and "a.tenant_id=$1" in sql and args == (tenant, "us-east", "rig")
    async with original(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
        response = await client.get("/v1/agents/base/receipts", params={"tenant_id": str(tenant), "task_id": str(uuid.uuid4())},
                                    headers={"Authorization": "Bearer " + keys["base"]})
    assert response.status_code == 200
    sql, args = pool.fetched[-1]
    assert "r.room=$3" in sql and "r.tenant_id=$1 AND l.tenant_id=$1" in sql and args[0] == tenant and args[2] == "base"


def test_no_sql_text_is_built_from_room_or_task_type():
    source = Path(route.__file__).read_text(encoding="utf-8")
    assert ".replace(\"'base'\"" not in source
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.JoinedStr):
            names = {sub.id for part in node.values if isinstance(part, ast.FormattedValue)
                     for sub in ast.walk(part.value) if isinstance(sub, ast.Name)}
            text = "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
            if names & {"room", "task_type"}:
                assert not any(word in text.upper() for word in ("SELECT", "INSERT", "WHERE", "VALUES")), text
