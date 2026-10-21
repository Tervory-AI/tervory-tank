"""AGENT-1 protocol and accounting tests; all gateway traffic is mocked."""
import json
import uuid
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

import agent_skills as route


class Pool:
    def __init__(self):
        self.rows = []

    @asynccontextmanager
    async def acquire(self):
        yield self

    @asynccontextmanager
    async def transaction(self):
        yield

    async def execute(self, sql, *args):
        self.rows.append((sql, args))


@pytest.fixture
def setup(monkeypatch):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_BASE", key)
    pool = Pool()

    async def policy(task, tenant):
        assert task == "agent.base.think"
        return {"model": "serving", "baseline_model": "baseline", "rung": 1, "priority": "standard", "max_tokens_out": 100}

    async def roster():
        return [{"model_name": "baseline", "model_info": {"input_cost_per_token": 0.001, "output_cost_per_token": 0.002}}]

    tank = SimpleNamespace(pool=lambda: pool, load_policy=policy, _roster_models=roster,
                           box_region=lambda: "us-east", graduate=SimpleNamespace(router_cannot_serve=lambda m: False),
                           LITELLM_URL="http://gateway.invalid", LITELLM_MASTER_KEY=uuid.uuid4().hex)
    app = FastAPI()
    app.include_router(route.build_router(tank))
    return app, tank, pool, key


@pytest.mark.asyncio
async def test_tool_calls_policy_room_key_and_durable_receipt(setup, monkeypatch):
    app, tank, pool, key = setup
    original = httpx.AsyncClient
    sent = []

    def gateway(request):
        sent.append(json.loads(request.content))
        assert request.headers["authorization"] == "Bearer " + tank.LITELLM_MASTER_KEY
        return httpx.Response(200, headers={"x-litellm-response-cost": "0.01", "x-litellm-model-group": "serving"}, json={
            "choices": [{"index": 0, "message": {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call1", "type": "function", "function": {"name": "pipeline", "arguments": "{}"}}]},
                "finish_reason": "tool_calls"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    monkeypatch.setattr(route.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(gateway)))
    tenant = str(uuid.uuid4())
    async with original(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
        response = await client.post("/v1/agents/base/chat/completions", headers={"Authorization": "Bearer " + key, "X-Tenant-ID": tenant},
            json={"model": "cannot-override-policy", "messages": [{"role": "user", "content": "Plan"}], "max_tokens": 500,
                  "tools": [{"type": "function", "function": {"name": "pipeline", "parameters": {"type": "object"}}}]})
    assert response.status_code == 200
    assert sent[0]["model"] == "serving" and sent[0]["max_tokens"] == 100
    assert sent[0]["tools"][0]["function"]["name"] == "pipeline"
    data = response.json()
    assert data["choices"][0]["message"]["tool_calls"][0]["id"] == "call1"
    assert data["receipt"]["baseline_cost_usd"] == 0.02
    assert data["receipt"]["tenant_id"] == tenant
    assert len(pool.rows) == 2 and pool.rows[0][1][1] == uuid.UUID(tenant)


@pytest.mark.asyncio
@pytest.mark.parametrize("room,authorized,region,expected", [
    ("tiger", True, "us-east", 403), ("base", False, "us-east", 401), ("base", True, "za", 403),
])
async def test_rejects_other_room_key_and_region_before_work(setup, room, authorized, region, expected):
    app, _, pool, key = setup
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
        result = await client.post(f"/v1/agents/{room}/chat/completions", json={"messages": [{"role": "user", "content": "Plan"}]},
            headers={"Authorization": "Bearer " + (key if authorized else uuid.uuid4().hex),
                     "X-Tenant-ID": str(uuid.uuid4()), "X-Home-Region": region})
    assert result.status_code == expected
    assert pool.rows == []


def test_stream_keeps_tools_and_receipt():
    result = {"id": "chatcmpl-one", "created": 1, "model": "policy", "usage": {}, "receipt": {"ledger_id": "one"},
              "choices": [{"message": {"role": "assistant", "tool_calls": [{"id": "call", "function": {"name": "pipeline", "arguments": "{}"}}]}, "finish_reason": "tool_calls"}]}
    chunks = list(route.stream_completion(result))
    assert '"index": 0' in chunks[0]
    assert '"receipt"' in chunks[-2]
    assert chunks[-1] == "data: [DONE]\n\n"
