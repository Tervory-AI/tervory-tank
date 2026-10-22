"""RIG-2: real PostgreSQL receipts, paid pause and approved-skill boundaries."""
import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

import agent_skills
import rig_brain_routes
from test_train1 import database as _database

database = _database


@pytest.mark.asyncio
async def test_step_receipts_are_idempotent_tenant_scoped_and_readable(database, monkeypatch):
    pool, rt = database
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_RIG", key)
    app = FastAPI()
    app.include_router(rig_brain_routes.build_router(rt))
    app.include_router(agent_skills.build_router(rt))
    body = {"id": str(uuid.uuid4()), "tenant_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4()),
            "home_region": "us-east", "action": "recall", "status": "done", "count": 2}
    headers = {"X-Tank-Key": key, "X-Home-Region": "us-east"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
        for _ in range(2):
            response = await client.post("/v1/agents/rig/steps", json=body, headers=headers)
            assert response.status_code == 200
            assert response.json()["ledger_id"] == body["id"]
        assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE id=$1", uuid.UUID(body["id"])) == 1
        for change in ({"tenant_id": str(uuid.uuid4())}, {"task_id": str(uuid.uuid4())}, {"count": 3}):
            assert (await client.post("/v1/agents/rig/steps", json={**body, **change}, headers=headers)).status_code == 409
        assert (await client.post("/v1/agents/rig/steps", json=body)).status_code == 401
        assert (await client.post("/v1/agents/rig/steps", json={**body, "url": "https://example.com"}, headers=headers)).status_code == 422
        own = await client.get("/v1/agents/rig/receipts", params={k: body[k] for k in ("tenant_id", "task_id")}, headers=headers)
        assert len(own.json()["receipts"]) == 1
        other = await client.get("/v1/agents/rig/receipts", params={"tenant_id": str(uuid.uuid4()), "task_id": body["task_id"]}, headers=headers)
        assert other.json() == {"receipts": []}


@pytest.mark.asyncio
async def test_rig_chat_uses_rig_policy_pause_and_real_ledger(database, monkeypatch):
    pool, rt = database
    rig_key, base_key = uuid.uuid4().hex, uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_RIG", rig_key)
    monkeypatch.setenv("TANK_KEY_BASE", base_key)
    monkeypatch.setattr(agent_skills.controls, "db", lambda: pool)
    async def policy(task, tenant):
        assert task == "agent.rig.think"
        return dict(await pool.fetchrow("SELECT * FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", task))
    async def roster():
        return [{"model_name": "luna", "litellm_params": {"model": "openai/fixture"},
                 "model_info": {"input_cost_per_token": .001, "output_cost_per_token": .002}}]
    rt.load_policy, rt._roster_models = policy, roster
    rt.model_call_refusal = lambda *a, **kw: None
    rt.graduate = SimpleNamespace(router_cannot_serve=lambda model: False)
    rt.LITELLM_URL, rt.LITELLM_MASTER_KEY = "http://model.invalid", uuid.uuid4().hex
    app = FastAPI()
    app.include_router(agent_skills.build_router(rt))
    original, calls = httpx.AsyncClient, []
    def gateway(request):
        sent = json.loads(request.content)
        calls.append(sent)
        assert sent["model"] == "luna"
        return httpx.Response(200, json={"choices": [{"message": {"role": "assistant", "content": "Catalogue evidence"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})
    monkeypatch.setattr(agent_skills.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(gateway)))
    tenant, task = uuid.uuid4(), uuid.uuid4()
    headers = {"X-Tank-Key": rig_key, "X-Tenant-ID": str(tenant), "X-Task-ID": str(task), "X-Home-Region": "us-east"}
    body = {"messages": [{"role": "user", "content": "A sample catalogue question"}], "model": "ignored"}
    async with original(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
        assert (await client.post("/v1/agents/rig/chat/completions", json=body, headers={**headers, "X-Tank-Key": base_key})).status_code == 401
        assert (await client.post("/v1/agents/rig/chat/completions", json=body, headers={**headers, "X-Home-Region": "za"})).status_code == 403
        assert not calls
        response = await client.post("/v1/agents/rig/chat/completions", json=body, headers=headers)
        assert response.status_code == 200
        receipt = response.json()["receipt"]
        assert receipt["room"] == "rig" and receipt["task_type"] == "agent.rig.think"
        row = await pool.fetchrow("SELECT * FROM tank.ledger WHERE id=$1", uuid.UUID(receipt["ledger_id"]))
        assert row["agent"] == "rig" and row["tenant_id"] == tenant and row["task_id"] == task
        assert row["task_type"] == "agent.rig.think" and row["cost_usd"] > 0
        stored = await pool.fetchval("SELECT receipt FROM tank.agent_receipts WHERE ledger_id=$1 AND tenant_id=$2", row["id"], tenant)
        assert json.loads(stored) == receipt
        await pool.execute("INSERT INTO tank.controls(tenant_id,name,value,updated_by) VALUES($1,'paid_paused',true,'fixture') ON CONFLICT (tenant_id,name) DO UPDATE SET value=true", agent_skills.controls.PLATFORM)
        assert (await client.post("/v1/agents/rig/chat/completions", json=body, headers=headers)).status_code == 503
        assert len(calls) == 1
        assert await pool.fetchval("SELECT count(*) FROM tank.control_log WHERE task='agent.rig.think'") == 1


@pytest.mark.asyncio
async def test_rig_only_exports_approved_present_rig_skills(database, tmp_path):
    pool, rt = database
    for name, agent, state, present in [("rig.search", "rig", "approved", True), ("rig.candidate", "rig", "candidate", True),
            ("rig.retired", "rig", "retired", True), ("rig.absent", "rig", "approved", False), ("base.search", "base", "approved", True)]:
        await pool.execute("INSERT INTO tank.skills(id,version,agent,state,present) VALUES($1,'1.0.0',$2,$3,$4)", name, agent, state, present)
    rt.get_package = lambda ident, version: SimpleNamespace(id=ident, version=version, agent="rig", description="Catalogue search", path=tmp_path, input_schema={})
    result = await agent_skills.export_skills(rt, uuid.uuid4(), "us-east", room="rig")
    assert result["room"] == "rig"
    assert [s["id"] for s in result["skills"]] == ["rig.search"]


@pytest.mark.asyncio
async def test_rig_seed_is_before_models_marker_and_does_not_overwrite_policy(database):
    pool, _ = database
    schema = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
    assert schema.index("'agent.rig.think'") < schema.index("-- MODELS-2:")
    await pool.execute("UPDATE tank.policy SET model='founder-choice' WHERE task_type='agent.rig.think'")
    await pool.execute(schema)
    assert await pool.fetchval("SELECT model FROM tank.policy WHERE task_type='agent.rig.think' AND tenant_id IS NULL") == "founder-choice"
