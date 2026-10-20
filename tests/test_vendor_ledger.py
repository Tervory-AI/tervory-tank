"""Vendor ledger authorization and append-only idempotency, without network."""

import os
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://localhost/test")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import main as tank  # noqa: E402


@pytest.mark.asyncio
async def test_vendor_route_uses_real_key_auth_and_platform_scope(monkeypatch):
    conn = AsyncMock()
    call_id = uuid.uuid4()
    conn.fetchval.return_value = call_id

    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn

    monkeypatch.setattr(tank, "_pool", Pool())
    monkeypatch.setattr(tank, "_agent_keys_synced", True)
    monkeypatch.setattr(tank, "TANK_API_KEY", "workspace-test")
    monkeypatch.setenv("TANK_KEY_BASE", "base-test")
    monkeypatch.setenv("TANK_KEY_TIGER", "tiger-test")
    monkeypatch.setenv("TANK_REGION", "us-east")
    body = {
        "id": str(call_id), "agent": "base", "task_type": "base.context_dev",
        "vendor": "context.dev", "units": 10, "cost_usd": 0,
        "region": "us-east", "outcome": "delivered",
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
        for key, expected in [("", 401), ("bad", 401), ("workspace-test", 403), ("tiger-test", 403)]:
            response = await client.post("/v1/ledger/vendor", json=body, headers={"X-Tank-Key": key})
            assert response.status_code == expected
        for changes, status in [
            ({"tenant_id": str(uuid.uuid4())}, 403), ({"region": "za"}, 403),
            ({"units": -1}, 422), ({"units": "NaN"}, 422), ({"cost_usd": 1}, 422),
            ({"units": None}, 422), ({"outcome": "anything"}, 422),
        ]:
            response = await client.post("/v1/ledger/vendor", json={**body, **changes}, headers={"X-Tank-Key": "base-test"})
            assert response.status_code == status
        conn.fetchval.assert_not_called()
        response = await client.post("/v1/ledger/vendor", json=body, headers={"X-Tank-Key": "base-test"})
        assert response.status_code == 200 and response.json()["ledger_id"] == str(call_id)
        sql, *args = conn.fetchval.call_args.args
        assert "INSERT INTO tank.ledger" in sql and "UPDATE" not in sql
        assert args[1] == tank.PLATFORM_TENANT
        assert args[3:7] == ["base", "base.context_dev", "vendor:context.dev", "context.dev"]
        assert args[7:10] == [10, 0, "delivered"]
        conn.fetchval.side_effect = [None, 1]
        assert (await client.post("/v1/ledger/vendor", json=body, headers={"X-Tank-Key": "base-test"})).status_code == 200
        conn.fetchval.side_effect = [None, None]
        assert (await client.post("/v1/ledger/vendor", json=body, headers={"X-Tank-Key": "base-test"})).status_code == 409
        conn.fetchval.side_effect = None
        conn.fetchval.return_value = call_id
        response = await client.post(
            "/v1/ledger/vendor", json={**body, "units": None, "outcome": "unverified"},
            headers={"X-Tank-Key": "base-test"},
        )
        assert response.status_code == 200
        assert (await client.get("/v1/ledger/summary", headers={"X-Tank-Key": "base-test"})).status_code == 403
