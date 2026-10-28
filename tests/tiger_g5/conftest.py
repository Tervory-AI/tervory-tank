"""Disposable loopback PostgreSQL only. No deployment data or settings."""
import os
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest
import pytest_asyncio

from test_tiger import ROOT
from chassis.db import ensure_schema
from watch import MemoryStore, PgStore, ensure_tables


@pytest_asyncio.fixture
async def database():
    dsn = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not dsn:
        pytest.skip("Disposable local Postgres is required")
    parsed = urlsplit(dsn)
    assert parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    name = "tiger_g5_test_" + uuid4().hex
    admin = await asyncpg.connect(dsn)
    await admin.execute('CREATE DATABASE "' + name + '"')
    pool = None
    try:
        pool = await asyncpg.create_pool(urlunsplit(parsed._replace(path="/" + name)), min_size=1, max_size=4)
        async with pool.acquire() as conn:
            await ensure_schema(conn, "tiger")
            await ensure_tables(conn)
            await conn.execute((ROOT / "agents/rig/schema.sql").read_text())
            await conn.execute("""CREATE SCHEMA tank;
                CREATE TABLE tank.access_feed_links (tenant_id uuid NOT NULL,url text NOT NULL,sku text NOT NULL,
                    PRIMARY KEY(tenant_id,url))""")
        yield pool
    finally:
        if pool:
            await pool.close()
        await admin.execute('DROP DATABASE "' + name + '"')
        await admin.close()


@pytest.fixture(params=["memory", "postgres"])
def store(request):
    if request.param == "memory":
        return MemoryStore()
    return PgStore(request.getfixturevalue("database"))
