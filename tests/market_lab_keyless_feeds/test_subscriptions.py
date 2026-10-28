"""Offline scheduling/isolation tests on an optional disposable local Postgres."""
import os
import socket
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "agents/market_lab"), str(ROOT / "agents/_chassis")]
from chassis.db import ensure_schema
from core.feed_links import build_router, refresh_links
from core.ledger import PostgresLedger


@pytest.mark.asyncio
async def test_daily_weekly_jobs_and_removal_are_tenant_scoped(monkeypatch):
    target = os.environ.get("DATABASE_URL", "")
    parts = urlsplit(target)
    if parts.hostname not in {"localhost", "127.0.0.1"} or not parts.path.endswith("_test"):
        pytest.skip("requires an explicitly selected loopback *_test Postgres")
    import asyncpg
    conn = await asyncpg.connect(target)
    txn = conn.transaction()
    await txn.start()
    try:
        await ensure_schema(conn, "market_lab")
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        owner, other, daily, weekly = (uuid4() for _ in range(4))
        monkeypatch.setattr(socket, "getaddrinfo", lambda *_: [(2, 1, 6, "", ("93.184.216.34", 443))])
        monkeypatch.setenv("TANK_REGION", "us-east")
        @asynccontextmanager
        async def context():
            yield ledger
        app = FastAPI()
        app.include_router(build_router(key_ok=lambda key: key == "placeholder-room-key", ledger_context=context, engine="ffl"))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://room") as client:
            async def call(method, path, tenant=owner, data=None):
                return await client.request(method, "/market/feeds" + path,
                    params={"tenant_id": str(tenant), "region": "us-east"}, json=data,
                    headers={"x-tank-key": "placeholder-room-key"})
            for ident, frequency, tail in ((daily, "daily", ""), (weekly, "weekly", "?format=xml")):
                response = await call("PUT", "/" + str(ident), data={"url": "https://www.federalreserve.gov/feeds/press_all.xml" + tail,
                                     "label": "Federal Reserve", "frequency": frequency})
                assert response.status_code == 200, response.text
            assert (await call("GET", "", tenant=other)).json()["links"] == []
            assert await conn.fetchval("SELECT count(*) FROM agent_market_lab.schedules WHERE tenant_id=$1 AND kind='feed_links'", owner) == 1
            assert await conn.fetchval("SELECT count(*) FROM agent_market_lab.jobs WHERE tenant_id=$1 AND kind='feed_links' AND status='queued'", owner) == 2
            assert await conn.fetchval("SELECT count(*) FROM agent_market_lab.jobs WHERE tenant_id=$1 AND kind='feed_links'", other) == 0
            now = datetime.now(timezone.utc) + timedelta(seconds=1)
            fixtures = str(ROOT / "tests/market_lab_keyless_feeds/fixtures")
            async def refresh(at, tenant=owner):
                return await refresh_links(ledger, str(tenant), "ffl", now=at, fixtures=fixtures)
            assert len((await refresh(now))["feeds"]) == 2
            assert (await refresh(now + timedelta(hours=23)))["feeds"] == []
            assert len((await refresh(now + timedelta(days=1)))["feeds"]) == 1
            assert (await refresh(now + timedelta(days=8), tenant=other))["feeds"] == []
            assert (await call("DELETE", "/" + str(daily), tenant=other)).status_code == 200
            assert len((await call("GET", "")).json()["links"]) == 2
            assert (await call("DELETE", "/" + str(daily))).status_code == 200
            remaining = (await refresh(now + timedelta(days=8)))["feeds"]
            assert len(remaining) == 1 and remaining[0]["source_id"] == "rss_" + str(weekly)
            assert await conn.fetchval("SELECT count(*) FROM agent_market_lab.feed_documents WHERE tenant_id=$1 AND source_id=$2", owner, "rss_" + str(daily)) == 0
            assert await conn.fetchval("SELECT count(*) FROM agent_market_lab.feed_checks WHERE tenant_id=$1 AND source_id=$2", owner, "rss_" + str(daily)) == 0
            assert await conn.fetchval("SELECT count(*) FROM agent_market_lab.feed_documents WHERE tenant_id=$1", other) == 0
    finally:
        await txn.rollback()
        await conn.close()
