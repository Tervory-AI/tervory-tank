"""Only brain-approved jobs may cross the credentialed brain-to-Tank boundary."""
import json
import uuid

import httpx
import pytest
from fastapi import FastAPI

from agents.rig.rig_brain import forge


def job(method="photogrammetry"):
    return {"tenant_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4()), "home_region": "us-east",
            "method": method, "inputs": [f"photo{i}.png" for i in range(50)], "unit_mm": 1,
            "dimensions_mm": [20, 30, 40], "timeout_seconds": 600, "cost_cap_usd": "1"}


@pytest.fixture
def boundary(monkeypatch, tmp_path):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("TANK_URL", "http://tank:8000")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    async def peers():
        return {"10.0.0.2"}
    monkeypatch.setattr(forge, "forge_addresses", peers)
    app = FastAPI()
    app.include_router(forge.router)
    original, calls = httpx.AsyncClient, []
    def backend(request):
        calls.append(request)
        if request.url.host == "rig-forge":
            assert "x-tank-key" not in request.headers and "authorization" not in request.headers
            return httpx.Response(202, json={"status": "queued"})
        assert request.url.host == "tank" and request.headers["x-tank-key"] == key
        return httpx.Response(200, json={"recorded": True})
    monkeypatch.setattr(forge.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(backend)))
    def client(host="10.0.0.2"):
        return original(transport=httpx.ASGITransport(app=app, client=(host, 123)), base_url="http://brain")
    return client, key, calls


@pytest.mark.asyncio
async def test_brain_checks_auth_region_and_immutable_job_before_forwarding(boundary):
    clients, key, calls = boundary
    body = job()
    async with clients() as client:
        assert (await client.post("/forge/jobs", json={})).status_code == 401
        assert (await client.post("/forge/jobs", json={"home_region": "za"}, headers={"X-Tank-Key": key})).status_code == 403
        assert not calls
        for _ in range(2):
            assert (await client.post("/forge/jobs", json=body, headers={"X-Tank-Key": key})).status_code == 202
        assert (await client.post("/forge/jobs", json={**body, "cost_cap_usd": "2"}, headers={"X-Tank-Key": key})).status_code == 409
    assert len(calls) == 2
    # Read through a new database connection: approval survives a brain restart.
    assert forge.approval(forge.Scope(**{k: body[k] for k in ("tenant_id", "job_id", "home_region")})).method == body["method"]


@pytest.mark.asyncio
async def test_forge_peer_cannot_invent_scope_or_change_approved_budget(boundary):
    clients, key, calls = boundary
    body = job()
    scope = {k: body[k] for k in ("tenant_id", "job_id", "home_region")}
    reserve = {**scope, **{k: body[k] for k in ("method", "timeout_seconds", "cost_cap_usd")}}
    async with clients() as client:
        assert (await client.post("/forge/relay/reserve", json=reserve)).status_code == 403
        assert not calls
        assert (await client.post("/forge/jobs", json=body, headers={"X-Tank-Key": key})).status_code == 202
        calls.clear()
        for changes in ({"tenant_id": str(uuid.uuid4())}, {"job_id": str(uuid.uuid4())},
                        {"method": "trellis2"}, {"timeout_seconds": 3600}, {"cost_cap_usd": "2"}):
            assert (await client.post("/forge/relay/reserve", json={**reserve, **changes})).status_code == 403
        assert (await client.post("/forge/relay/reserve", json={**reserve, "unexpected": "ignored?"})).status_code == 422
        assert not calls
        assert (await client.post("/forge/relay/reserve", json=reserve)).status_code == 200
    async with clients("10.0.0.8") as client:
        assert (await client.post("/forge/relay/claim", json=scope, headers={"X-Forwarded-For": "10.0.0.2"})).status_code == 401
    assert len(calls) == 1 and json.loads(calls[0].content) == reserve


@pytest.mark.asyncio
async def test_cpu_job_cannot_claim_gpu_and_unknown_jobs_cannot_record_steps(boundary):
    clients, key, calls = boundary
    body = job("scan")
    scope = {k: body[k] for k in ("tenant_id", "job_id", "home_region")}
    async with clients() as client:
        assert (await client.post("/forge/relay/steps", json={**scope, "stage": "intake", "outcome": "delivered"})).status_code == 403
        await client.post("/forge/jobs", json=body, headers={"X-Tank-Key": key})
        calls.clear()
        assert (await client.post("/forge/relay/claim", json=scope)).status_code == 403
        assert (await client.post("/forge/relay/steps", json={**scope, "stage": "gpu_submit", "outcome": "delivered"})).status_code == 403
        assert not calls
        assert (await client.post("/forge/relay/steps", json={**scope, "stage": "intake", "outcome": "delivered"})).status_code == 200
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_trellis_default_off_in_brain(boundary, monkeypatch):
    clients, key, calls = boundary
    monkeypatch.delenv("RIG_FORGE_TRELLIS_ENABLED", raising=False)
    async with clients() as client:
        result = await client.post("/forge/jobs", json=job("trellis2"), headers={"X-Tank-Key": key})
    assert result.status_code == 503 and not calls
