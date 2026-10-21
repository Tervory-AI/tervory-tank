"""Actual Tank/room HTTP authentication, action boundaries and secret-safe errors."""
import asyncio
import base64
import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
import yaml

os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import main as tank  # noqa: E402
import ghost_routes  # noqa: E402
from agents.ghost.app import create_app  # noqa: E402
from agents.ghost.investigate import Investigator  # noqa: E402
from agents.ghost.models import Observation  # noqa: E402
from agents.ghost.store import Store  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def gateway(monkeypatch):
    conn = AsyncMock()
    conn.fetchrow.return_value = {"status": "pending"}
    conn.fetchval.return_value = uuid.uuid4()

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    monkeypatch.setattr(tank, "_pool", Pool())
    monkeypatch.setattr(tank, "_agent_keys_synced", True)
    monkeypatch.setattr(tank, "TANK_API_KEY", "workspace-test")
    monkeypatch.setenv("TANK_API_KEY", "workspace-test")
    monkeypatch.setenv("TANK_KEY_GHOST", "ghost-test")
    monkeypatch.setenv("TANK_KEY_RADIX", "radix-test")
    monkeypatch.setenv("TANK_KEY_BASE", "base-test")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-test")
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(tank.app.state, "ghost_recovery_backend", None, raising=False)
    return conn


@pytest.mark.asyncio
async def test_ghost_cannot_access_admin_policy_or_other_rooms(gateway):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
        for path in ("/v1/workers", "/v1/ledger/summary", "/v1/ghost/incidents", "/v1/admin/counters", "/v1/skala/test/approve"):
            response = await client.get(path, headers={"X-Tank-Key": "ghost-test"})
            assert response.status_code in {403, 404, 405}
        for key in ("base-test", "workspace-test", ""):
            response = await client.post("/v1/ghost/check", headers={"X-Tank-Key": key}, json={"target": "tank", "signal": "health"})
            assert response.status_code in {401, 403}
        response = await client.post("/v1/ghost/check", headers={"X-Tank-Key": "ghost-test"}, json={"target": "tank", "signal": "health"})
        assert response.status_code == 200 and response.json()["failing"] is False


@pytest.mark.asyncio
async def test_look_is_founder_only_and_reaches_room_without_tenant_override(gateway, monkeypatch):
    seen = []

    def upstream(request):
        seen.append(request)
        return httpx.Response(200, json={"id": "issue-test", "state": "open"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as http:
        monkeypatch.setattr(tank, "_http", http)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
            body = {"target": "workspace", "signal": "health"}
            denied = await client.post("/v1/ghost/look", json=body, headers={"X-Tank-Key": "workspace-test"})
            assert denied.status_code == 404 and not seen
            ok = await client.post("/v1/ghost/look", json=body, headers={"X-Tank-Key": "workspace-test", "X-Tervory-Admin": "founder-test"})
            assert ok.status_code == 200
    assert seen[0].url == "http://agent-ghost:8000/look"
    assert seen[0].headers["X-Tank-Key"] == "ghost-test"


@pytest.mark.asyncio
async def test_recovery_refuses_writes_and_missing_integration_with_receipts(gateway, monkeypatch):
    record = AsyncMock(return_value={"ledger_id": "receipt-test", "recorded": True})
    monkeypatch.setattr(ghost_routes, "action_receipt", record)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
        headers = {"X-Tank-Key": "ghost-test"}
        for action in ("database_write", "change_key", "merge", "restart_anything"):
            response = await client.post("/v1/ghost/actions", headers=headers, json={"id": str(uuid.uuid4()), "target": "tank", "action": action})
            assert response.status_code == 422
        response = await client.post("/v1/ghost/actions", headers=headers, json={"id": str(uuid.uuid4()), "target": "workspace", "action": "restart_crashed_room"})
        assert response.status_code == 403
        response = await client.post("/v1/ghost/actions", headers=headers, json={"id": str(uuid.uuid4()), "target": "base", "action": "restart_crashed_room"})
        assert response.status_code == 503 and "No action" in response.text
    assert record.await_count >= 8


@pytest.mark.asyncio
async def test_recovery_rechecks_state_and_never_repeats_uncertain_action(gateway, monkeypatch):
    backend = SimpleNamespace(observe=AsyncMock(return_value={"state": "crashed", "revision": "same-revision"}), execute=AsyncMock(side_effect=TimeoutError))
    monkeypatch.setattr(tank.app.state, "ghost_recovery_backend", backend)
    monkeypatch.setattr(ghost_routes, "action_receipt", AsyncMock(return_value={"ledger_id": "receipt-test"}))
    identity = str(uuid.uuid4())
    body = {"id": identity, "target": "base", "action": "restart_crashed_room"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
        first = await client.post("/v1/ghost/actions", headers={"X-Tank-Key": "ghost-test"}, json=body)
        assert first.status_code == 502
        assert gateway.execute.call_args.args[-1] == "uncertain"
        gateway.fetchrow.side_effect = [None, {"action": body["action"], "target": "base", "status": "uncertain"}]
        second = await client.post("/v1/ghost/actions", headers={"X-Tank-Key": "ghost-test"}, json=body)
        assert second.status_code == 200 and second.json()["status"] == "uncertain"
        backend.execute.assert_awaited_once_with("restart_crashed_room", "base", "same-revision", identity)


@pytest.mark.asyncio
async def test_radix_handoff_is_sealed_and_results_only_contain_counts(gateway, monkeypatch):
    seen = []
    scan_id = str(uuid.uuid4())

    def upstream(request):
        seen.append(request)
        if request.method == "POST":
            return httpx.Response(201, json={"id": scan_id})
        return httpx.Response(200, json={"status": "done", "result": {"critical": 1, "findings": [{"text": "private evidence"}]}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as http:
        monkeypatch.setattr(tank, "_http", http)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
            queued = await client.post("/v1/ghost/radix", headers={"X-Tank-Key": "ghost-test"}, json={"archive": base64.b64encode(b"PK\x03\x04fixture").decode()})
            assert queued.status_code == 200
            result = await client.get("/v1/ghost/radix", headers={"X-Tank-Key": "ghost-test"}, params={"id": scan_id})
            assert result.json()["critical"] == 1 and "private evidence" not in result.text
    assert seen[0].url.host == "agent-radix"
    assert seen[0].headers["X-Tank-Key"] == "radix-test"
    assert "tenant_id=00000000-0000-0000-0000-000000000001" in str(seen[1].url)


@pytest.mark.asyncio
async def test_room_rejects_extra_fields_without_echoing_them(tmp_path, monkeypatch):
    monkeypatch.setenv("TANK_KEY", "ghost-test")
    app = create_app()
    store = Store(tmp_path / "room.sqlite3")
    probes = AsyncMock()
    probes.reproduce.return_value = Observation(target="workspace", signal="health", failing=True)
    app.state.store, app.state.lock = store, asyncio.Lock()
    app.state.investigator = Investigator(store, probes, AsyncMock())
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://ghost") as client:
            denied = await client.post("/look", json={"target": "workspace"})
            assert denied.status_code == 404
            bad = await client.post("/look", headers={"X-Tank-Key": "ghost-test"}, json={"target": "workspace", "raw_logs": "private evidence"})
            assert bad.status_code == 422 and "private evidence" not in bad.text
            good = await client.post("/look", headers={"X-Tank-Key": "ghost-test"}, json={"target": "workspace"})
            assert good.status_code == 200 and good.json()["state"] == "needs_review"
    finally:
        store.close()


def test_compose_isolation_and_no_production_control_credentials():
    main = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    joined = {name for name, service in main["services"].items() if "tervory-gw-ghost" in service.get("networks", [])}
    assert joined == {"tank", "postgres"}
    room = yaml.safe_load((ROOT / "agents/ghost/docker-compose.yml").read_text())
    for service in room["services"].values():
        assert service["networks"] == ["gw"]
        assert service["cap_drop"] == ["ALL"]
        assert not any(key in service.get("environment", {}) for key in ("DATABASE_URL", "COOLIFY_TOKEN", "GITHUB_TOKEN", "LITELLM_MASTER_KEY", "TANK_API_KEY"))
        assert not any("docker.sock" in str(v) for v in service.get("volumes", []))
    assert room["networks"]["gw"] == {"external": True, "name": "tervory-gw-ghost"}
