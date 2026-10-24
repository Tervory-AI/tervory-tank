"""Real PostgreSQL: bounded spend, replay safety, tenant scope and paid pause."""
import asyncio
import json
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import controls
import rig_forge_routes
from test_train1 import database as _database

database = _database


async def setup(pool, rt, monkeypatch):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_RIG", key)
    monkeypatch.setattr(controls, "db", lambda: pool)
    app = FastAPI()
    app.include_router(rig_forge_routes.build_router(rt))
    tenant, job = uuid.uuid4(), uuid.uuid4()
    await pool.execute("""INSERT INTO tank.rig_forge_limits
        (tenant_id,method,enabled,image,flavor,hour_usd,billing_quantum_seconds,max_seconds,max_job_usd,total_budget_usd)
        VALUES($1,'trellis2',true,$2,'a10g-small',1,60,600,1,1)""", tenant,
        "ghcr.io/tervory-ai/rig-forge-trellis2@sha256:" + "a" * 64)
    body = {"tenant_id": str(tenant), "job_id": str(job), "home_region": "us-east"}
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank",
                              headers={"X-Tank-Key": key})
    return client, body


@pytest.mark.asyncio
async def test_reservations_replay_claim_once_and_complete_on_real_postgres(database, monkeypatch):
    pool, rt = database
    client, body = await setup(pool, rt, monkeypatch)
    reserve = {**body, "method": "trellis2", "timeout_seconds": 600, "cost_cap_usd": "1"}
    async with client:
        first = await client.post("/v1/agents/rig/forge/reserve", json=reserve)
        assert first.status_code == 200, first.text
        assert first.json()["reserved_usd"] == "0.166667"
        assert (await client.post("/v1/agents/rig/forge/reserve", json=reserve)).json() == first.json()
        assert (await client.post("/v1/agents/rig/forge/reserve", json={**reserve, "timeout_seconds": 601})).status_code == 409
        claims = await asyncio.gather(*[client.post("/v1/agents/rig/forge/claim", json=body) for _ in range(2)])
        assert sorted(response.status_code for response in claims) == [200, 409]
        finish = {**body, "provider_job_id": "stub-job-1", "outcome": "delivered"}
        receipt = await client.post("/v1/agents/rig/forge/complete", json=finish)
        assert receipt.status_code == 200, receipt.text
        assert receipt.json()["cost_basis"] == "upper_bound"
        assert (await client.post("/v1/agents/rig/forge/complete", json=finish)).json() == receipt.json()
        assert (await client.post("/v1/agents/rig/forge/complete", json={**finish, "outcome": "failed"})).status_code == 409
    row = await pool.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND task_id=$2",
                             uuid.UUID(body["tenant_id"]), uuid.UUID(body["job_id"]))
    assert row["vendor"] == "huggingface_jobs" and row["cost_usd"] > 0
    await pool.execute((Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text())
    assert await pool.fetchval("SELECT count(*) FROM tank.rig_forge_jobs WHERE tenant_id=$1", uuid.UUID(body["tenant_id"])) == 1


@pytest.mark.asyncio
async def test_missing_config_cost_caps_tenant_auth_and_paid_pause(database, monkeypatch):
    pool, rt = database
    client, body = await setup(pool, rt, monkeypatch)
    reserve = {**body, "method": "trellis2", "timeout_seconds": 600, "cost_cap_usd": "1"}
    async with client:
        url = "/v1/agents/rig/forge/reserve"
        for change in ({"timeout_seconds": 601}, {"cost_cap_usd": "0.01"}, {"cost_cap_usd": "2"}):
            assert (await client.post(url, json={**reserve, **change})).status_code == 409
        assert (await client.post(url, json=reserve, headers={"X-Tank-Key": ""})).status_code == 401
        assert (await client.post(url, json={**reserve, "tenant_id": str(uuid.uuid4())})).status_code == 503
        assert (await client.post(url, json={**reserve, "provider_token": "forbidden"})).status_code == 422
        assert (await client.post("/v1/agents/rig/forge/claim", json={**body, "tenant_id": str(uuid.uuid4())})).status_code == 404
        await pool.execute("INSERT INTO tank.controls(tenant_id,name,value,updated_by) VALUES($1,'paid_paused',true,'fixture') ON CONFLICT (tenant_id,name) DO UPDATE SET value=true", controls.PLATFORM)
        assert (await client.post(url, json=reserve)).status_code == 503
    assert await pool.fetchval("SELECT count(*) FROM tank.rig_forge_jobs") == 0


@pytest.mark.asyncio
async def test_total_budget_is_atomic_and_failed_jobs_keep_reservations(database, monkeypatch):
    pool, rt = database
    client, body = await setup(pool, rt, monkeypatch)
    await pool.execute("UPDATE tank.rig_forge_limits SET total_budget_usd=1,max_job_usd=1,hour_usd=6 WHERE tenant_id=$1", uuid.UUID(body["tenant_id"]))
    reserve = {**body, "method": "trellis2", "timeout_seconds": 600, "cost_cap_usd": "1"}
    async with client:
        results = await asyncio.gather(*[client.post("/v1/agents/rig/forge/reserve", json={**reserve, "job_id": str(uuid.uuid4())}) for _ in range(2)])
        assert sorted(r.status_code for r in results) == [200, 409]
        approved = next(r.json() for r in results if r.status_code == 200)
        scope = {**body, "job_id": approved["job_id"]}
        assert (await client.post("/v1/agents/rig/forge/claim", json=scope)).status_code == 200
        assert (await client.post("/v1/agents/rig/forge/complete", json={**scope,"outcome":"unverified","provider_job_id":"unknown"})).status_code == 200
        assert (await client.post("/v1/agents/rig/forge/reserve", json=reserve)).status_code == 409


@pytest.mark.asyncio
async def test_free_step_receipts_are_idempotent_and_tenant_scoped(database, monkeypatch):
    pool, rt = database
    client, body = await setup(pool, rt, monkeypatch)
    step = {**body, "stage": "model_check", "outcome": "failed"}
    async with client:
        response = await client.post("/v1/agents/rig/forge/steps", json=step)
        assert response.status_code == 200
        assert (await client.post("/v1/agents/rig/forge/steps", json=step)).json() == response.json()
        assert (await client.post("/v1/agents/rig/forge/steps", json={**step,"outcome":"delivered"})).status_code == 409
    receipt = await pool.fetchval("SELECT receipt FROM tank.agent_receipts WHERE tenant_id=$1 AND ledger_id=$2",
                                 uuid.UUID(body["tenant_id"]), uuid.UUID(response.json()["ledger_id"]))
    assert json.loads(receipt)["outcome"] == "failed"
