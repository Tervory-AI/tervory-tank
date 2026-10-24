"""Exercise preview -> server confirmation -> import against real PostgreSQL."""

import asyncio
import json
import secrets
from uuid import UUID

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import access
from command import Actor
from test_rig_feeds_retailer import ROOT, SAMPLES, SITE, TENANT, OTHER, prepared


@pytest_asyncio.fixture
async def mapping_pool(monkeypatch):
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    admin = _admin_url()
    name = "rig_mapping_" + secrets.token_hex(6)
    await _create_database(admin, name)
    pool = await asyncpg.create_pool(_database_url(admin, name))
    try:
        async with pool.acquire() as conn:
            for _ in range(2):
                await conn.execute((ROOT / "tank/schema.sql").read_text())
        monkeypatch.setattr(access, "db", lambda: pool)
        yield pool
    finally:
        await pool.close()
        await _drop_database(admin, name)


async def confirm_feed(actor, data):
    """Use the actual HTTP handlers, including their validation and saved preview."""
    app = FastAPI()
    app.include_router(access.router)
    app.dependency_overrides[access.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/v1/access/rig/admin/mapping", json={"data": data or {}})
        assert response.status_code == 200, response.text
        preview = response.json()
        data = {**data, "columns": preview["columns"]}
        response = await client.post("/v1/access/rig/admin/confirm-mapping", json={"data": {**data, "preview_id": preview["preview_id"]}})
        assert response.status_code == 200, response.text
    return data


@pytest.mark.asyncio
async def test_confirmation_is_bound_consumed_and_required_for_import(mapping_pool, monkeypatch):
    from rigbox.retailer_server import create_retailer_app
    actor = Actor(UUID(TENANT), "admin", False, frozenset({"rig"}))
    original = actor
    app = FastAPI()
    app.include_router(access.router)
    app.dependency_overrides[access.identity] = lambda: actor
    retailer = await prepared()
    control = secrets.token_hex(32)
    monkeypatch.setenv("RIG_RETAILER_KEY", control)
    room = create_retailer_app(retailer.service)
    async def dispatch(who, operation, data=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room), base_url="http://private") as client:
            response = await client.post("/internal/retailer/" + operation, headers={"x-rig-retailer-key": control},
                                        json={"tenant_id": str(who.tenant_id), "data": data or {}})
            response.raise_for_status()
            return response.json()
    monkeypatch.setattr(access, "rig_request", dispatch)
    data = {"distributor": "catalogue", "site": SITE, "feed_id": "main", "format": "csv", "source": "ftp_export",
            "currency": "USD", "country": "US", "price_basis": "cost", "contents": (SAMPLES / "us-distributor.csv").read_text()}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        async def post(operation, payload):
            return await client.post("/v1/access/rig/admin/" + operation, json={"data": payload})
        assert (await post("import", {**data, "mapping_confirmed": True})).status_code == 422
        assert (await post("import", data)).status_code == 422
        assert (await post("mapping", {k: v for k, v in data.items() if k != "currency"})).status_code == 422
        preview = (await post("mapping", data)).json()
        assert not await retailer.store.products(TENANT)
        confirmed = {**data, "columns": preview["columns"], "preview_id": preview["preview_id"]}
        assert (await post("confirm-mapping", {**confirmed, "preview_id": str(UUID(int=1))})).status_code == 422
        for who in [Actor(UUID(OTHER), "admin", False, frozenset({"rig"})), Actor(UUID(TENANT), "other-admin", False, frozenset({"rig"}))]:
            actor = who
            assert (await post("confirm-mapping", confirmed)).status_code == 422
        actor = original
        for change in [{"country": "NZ"}, {"currency": "NZD"}, {"price_basis": "selling"}, {"feed_id": "other"},
                       {"distributor": "zanders"}, {"site": "https://other.example"}, {"contents": data["contents"] + "\n"},
                       {"columns": {**preview["columns"], "price": "invented"}}, {"columns": {"sku": "SKU"}}]:
            assert (await post("confirm-mapping", {**confirmed, **change})).status_code == 422
        assert (await post("import", data)).status_code == 422
        async with mapping_pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tank.rig_feed_settings WHERE tenant_id=$1", actor.tenant_id) == 0
            value = await conn.fetchval("SELECT preview FROM tank.rig_feed_previews WHERE tenant_id=$1 AND id=$2", actor.tenant_id, UUID(preview["preview_id"]))
            assert "US-LAMP" not in value and "20.00" not in value and "contents" not in value
        async def failed_receipt(*args, **kwargs):
            raise RuntimeError("Synthetic receipt failure")
        with monkeypatch.context() as patch:
            patch.setattr(access, "receipt", failed_receipt)
            with pytest.raises(RuntimeError, match="Synthetic receipt failure"):
                await post("confirm-mapping", confirmed)
        async with mapping_pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tank.rig_feed_settings WHERE tenant_id=$1", actor.tenant_id) == 0
            assert await conn.fetchval("SELECT count(*) FROM tank.rig_feed_previews WHERE tenant_id=$1 AND id=$2",
                                       actor.tenant_id, UUID(preview["preview_id"])) == 1
        # Concurrent confirmation consumes the preview exactly once.
        results = await asyncio.gather(post("confirm-mapping", confirmed), post("confirm-mapping", confirmed))
        assert sorted(r.status_code for r in results) == [200, 422]
        assert (await post("import", data)).json()["receipt"]["added"] == 1
        assert (await post("import", {**data, "currency": "NZD"})).status_code == 422
        assert (await post("import", {**data, "columns": {"price": "SKU"}})).status_code == 422
        assert (await post("import", data)).json()["receipt"]["updated"] == 1
        actor = Actor(UUID(OTHER), "admin", False, frozenset({"rig"}))
        assert (await post("import", data)).status_code == 422
        actor = original
        expired = (await post("mapping", data)).json()
        async with mapping_pool.acquire() as conn:
            await conn.execute("UPDATE tank.rig_feed_previews SET expires_at=now()-interval '1 second' WHERE tenant_id=$1 AND id=$2",
                               actor.tenant_id, UUID(expired["preview_id"]))
        assert (await post("confirm-mapping", {**confirmed, "preview_id": expired["preview_id"]})).status_code == 422
        panel = (await client.get("/v1/access/rig/admin")).json()
        assert panel["feeds"][0]["mapping_confirmed"] is True
        assert "confirmation_version" not in json.dumps(panel) and "connection_source" not in json.dumps(panel)
        async with mapping_pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tank.access_receipts WHERE tenant_id=$1 AND action='feed_mapping_confirmed'", actor.tenant_id) == 1
            # A pre-review row with the old client flag is not server confirmation.
            await conn.execute("UPDATE tank.rig_feed_settings SET settings=$2::jsonb WHERE tenant_id=$1",
                               actor.tenant_id, json.dumps({"mapping_confirmed": True}))
        assert (await post("import", data)).status_code == 422
