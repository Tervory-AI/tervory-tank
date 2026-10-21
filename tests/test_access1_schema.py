"""Exercise real SQL on the isolated Postgres service provided by CI."""
import base64
import os
import uuid
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

import access
from command import Actor


@pytest.mark.asyncio
async def test_access_empty_schema_reapply_and_scoped_routes(monkeypatch):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url: pytest.skip("CI provides isolated Postgres")
    import asyncpg
    admin = await asyncpg.connect(url)
    name = "access_test_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    pool = await asyncpg.create_pool(url, database=name, min_size=1, max_size=5)
    try:
        schema = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
        async with pool.acquire() as conn:
            await conn.execute(schema)
            await conn.execute(schema)
        monkeypatch.setattr(access, "db", lambda: pool)
        for key in ("TANK_VAULT_KEY", "ACCESS_BROWSER_KEY_BASE"):
            monkeypatch.setenv(key, base64.urlsafe_b64encode(os.urandom(32)).decode())
        actor = Actor(uuid.uuid4(), "fixture-owner", True)
        app = FastAPI(); app.include_router(access.router)
        app.dependency_overrides[access.identity] = lambda: actor
        app.dependency_overrides[access.room_identity] = lambda: "tiger"
        async def control(*args): return {"cleared": True}
        monkeypatch.setattr(access, "control", control)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/v1/access/sites", json={"site": "https://dealer.example", "terms": "yes", "rotation_days": 30})
            assert response.status_code == 200
            response = await client.post("/v1/access/credentials", json={"room": "base", "site": "https://dealer.example",
                "username": uuid.uuid4().hex, "password": uuid.uuid4().hex, "dedicated_read_only": True})
            assert response.status_code == 200
            other = uuid.uuid4()
            # Platform terms reveal no other client's sites to a client.
            response = await client.post("/v1/access/sites", json={"site": "https://other-dealer.example", "terms": "unknown"})
            assert response.status_code == 200
            app.dependency_overrides[access.identity] = lambda: Actor(actor.tenant_id, "client", False, frozenset({"base", "tiger"}))
            response = await client.get("/v1/access/connections")
            assert response.json()["policies"] == [] and "other-dealer" not in response.text
            assert response.json()["connections"][0]["site"] == "https://dealer.example"
            app.dependency_overrides[access.identity] = lambda: actor
            # Terms clear settings checks for every affected tenant, not other sites.
            async with pool.acquire() as conn:
                await access.enqueue(conn, actor.tenant_id, "base", "https://dealer.example", "terms_unknown")
                await access.enqueue(conn, other, "base", "https://dealer.example", "terms_unknown")
                await access.enqueue(conn, other, "base", "https://other-dealer.example", "terms_unknown")
            response = await client.post("/v1/access/sites", json={"site": "https://dealer.example", "terms": "yes", "rotation_days": 30})
            assert response.status_code == 200
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM tank.access_queue WHERE tenant_id=$1 AND site='https://dealer.example' AND status='done'", other) == 1
                assert await conn.fetchval("SELECT status FROM tank.access_queue WHERE tenant_id=$1 AND site='https://other-dealer.example'", other) == "waiting"
                await access.enqueue(conn, actor.tenant_id, "base", "https://dealer.example", "rotation_due")
                other_check = await access.enqueue(conn, other, "base", "https://dealer.example", "captcha")
            response = await client.post("/v1/access/credentials", json={"room": "base", "site": "https://dealer.example",
                "username": uuid.uuid4().hex, "password": uuid.uuid4().hex, "dedicated_read_only": True})
            assert response.status_code == 200
            async with pool.acquire() as conn:
                assert not await conn.fetchval("SELECT 1 FROM tank.access_queue WHERE tenant_id=$1 AND site='https://dealer.example' AND status IN ('waiting','handling')", actor.tenant_id)
                assert await conn.fetchval("SELECT status FROM tank.access_queue WHERE tenant_id=$1 AND id=$2", other, uuid.UUID(other_check)) == "waiting"
            # Only a founder can dismiss, including a settings-only check with no live view.
            async with pool.acquire() as conn:
                companion = uuid.UUID(await access.enqueue(conn, other, "base", "https://dealer.example", "human_login", uuid.uuid4()))
                await conn.execute("UPDATE tank.access_queue SET status='handling',handler='another-person',started_at=now() WHERE tenant_id=$1 AND id=$2", other, companion)
                untouched = dict(await conn.fetchrow("SELECT * FROM tank.access_queue WHERE tenant_id=$1 AND id=$2", other, companion))
            app.dependency_overrides[access.identity] = lambda: Actor(other, "client", False, frozenset({"base"}))
            response = await client.post("/v1/access/queue/" + other_check, json={"tenant_id": str(other), "action": "dismiss"})
            assert response.status_code == 403
            app.dependency_overrides[access.identity] = lambda: actor
            response = await client.post("/v1/access/queue/" + other_check, json={"tenant_id": str(other), "action": "dismiss"})
            assert response.status_code == 200 and response.json()["dismissed"]
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT status FROM tank.access_queue WHERE tenant_id=$1 AND id=$2", other, uuid.UUID(other_check)) == "done"
                assert dict(await conn.fetchrow("SELECT * FROM tank.access_queue WHERE tenant_id=$1 AND id=$2", other, companion)) == untouched
            # Browser restart loses handles. Queue refresh releases the old handler.
            async with pool.acquire() as conn:
                stale = uuid.UUID(await access.enqueue(conn, actor.tenant_id, "base", "https://dealer.example", "captcha", uuid.uuid4()))
                await conn.execute("UPDATE tank.access_queue SET status='handling',handler='previous-person',started_at=now() WHERE tenant_id=$1 AND id=$2", actor.tenant_id, stale)
            async def missing(*args): return {"available": False}
            monkeypatch.setattr(access, "control", missing)
            response = await client.get("/v1/access/queue")
            assert response.status_code == 200
            item = next(row for row in response.json() if row["id"] == str(stale))
            assert item["status"] == "waiting" and not item["live_available"] and "browser_handle" not in item
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM tank.access_queue WHERE tenant_id=$1 AND id=$2", actor.tenant_id, stale)
                assert row["handler"] is None and row["started_at"] is None
            monkeypatch.setattr(access, "control", control)
            response = await client.get("/v1/access/connections")
            assert response.status_code == 200 and response.json()["connections"][0]["terms"] == "yes"
            response = await client.post("/v1/access/feeds/import", json={"distributor": "rsr", "site": "https://dealer.example", "source": "ftp_export", "format": "csv", "contents": "sku,price,quantity\nitem-1,12.50,7"})
            assert response.status_code == 200 and response.json()["row_count"] == 1
            response = await client.post("/v1/access/feeds/link", json={"url": "https://dealer.example/product", "sku": "item-1"})
            assert response.status_code == 200
            response = await client.get("/v1/access/feeds/price", params={"tenant_id": str(actor.tenant_id), "site": "https://dealer.example", "url": "https://dealer.example/product"})
            assert response.status_code == 200 and response.json()["found"]
            response = await client.get("/v1/access/feeds/price", params={"tenant_id": str(uuid.uuid4()), "site": "https://dealer.example", "url": "https://dealer.example/product"})
            assert response.status_code == 200 and not response.json()["found"]
            async with pool.acquire() as conn:
                first = await access.enqueue(conn, actor.tenant_id, "base", "https://dealer.example", "captcha", uuid.uuid4())
                second = await access.enqueue(conn, actor.tenant_id, "base", "https://dealer.example", "captcha", uuid.uuid4())
                assert first == second
                await conn.execute(schema)
            response = await client.post("/v1/access/revoke", json={"room": "base", "site": "https://dealer.example"})
            assert response.status_code == 200
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT sealed FROM tank.access_connections WHERE tenant_id=$1 AND room='base' AND site='https://dealer.example'", actor.tenant_id) is None
                assert await conn.fetchval("SELECT count(*) FROM tank.access_receipts WHERE tenant_id=$1", actor.tenant_id) >= 4
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()
