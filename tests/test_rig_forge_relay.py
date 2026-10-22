"""The only credentialed boundary is the brain-to-Tank hop."""
import uuid

import httpx
import pytest
from fastapi import FastAPI

from agents.rig.rig_brain import forge


@pytest.mark.asyncio
async def test_brain_checks_room_and_region_and_never_forwards_key_to_forge(monkeypatch):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    app = FastAPI()
    app.include_router(forge.router)
    original, calls = httpx.AsyncClient, []
    def backend(request):
        calls.append(request)
        assert request.url.host == "rig-forge"
        assert "x-tank-key" not in request.headers and "authorization" not in request.headers
        return httpx.Response(202, json={"status": "queued"})
    monkeypatch.setattr(forge.httpx, "AsyncClient", lambda **kw: original(transport=httpx.MockTransport(backend)))
    async with original(transport=httpx.ASGITransport(app=app), base_url="http://brain") as client:
        assert (await client.post("/forge/jobs", json={})).status_code == 401
        assert (await client.post("/forge/jobs", json={"home_region":"za"}, headers={"X-Tank-Key":key})).status_code == 403
        assert not calls
        assert (await client.post("/forge/jobs", json={"home_region":"us-east"}, headers={"X-Tank-Key":key})).status_code == 202
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_only_forge_peer_can_relay_and_key_goes_only_to_tank(monkeypatch):
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY", key)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("TANK_URL", "http://tank:8000")
    async def peers():return {"10.0.0.2"}
    monkeypatch.setattr(forge,"forge_addresses",peers)
    app = FastAPI()
    app.include_router(forge.router)
    original, calls = httpx.AsyncClient, []
    def backend(request):
        calls.append(request)
        assert request.url.host == "tank" and request.url.path == "/v1/agents/rig/forge/steps"
        assert request.headers["x-tank-key"] == key
        return httpx.Response(200, json={"cost_usd":"0"})
    monkeypatch.setattr(forge.httpx,"AsyncClient",lambda **kw: original(transport=httpx.MockTransport(backend)))
    for host,status in (("10.0.0.8",401),("10.0.0.2",200)):
        async with original(transport=httpx.ASGITransport(app=app,client=(host,123)),base_url="http://brain") as client:
            result=await client.post("/forge/relay/steps",json={"home_region":"us-east"},headers={"X-Forwarded-For":"10.0.0.2"})
            assert result.status_code == status
    assert len(calls)==1
