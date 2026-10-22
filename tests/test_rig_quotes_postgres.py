"""Apply the additive schema twice and exercise real tenant-scoped delivery state."""

import asyncio
from datetime import date

import asyncpg
import pytest

from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
from test_rig_quotes import OTHER, TENANT
from rigbox.quotes.store import PgQuotes
from rigbox.store import PgStore
from uuid import uuid4


@pytest.mark.asyncio
async def test_delivery_claims_schema_reapply_and_counts():
    admin = _admin_url()
    name = "rig4_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=5)
        try:
            store = PgStore(pool)
            await store.apply_schema()
            await store.apply_schema()
            quotes = PgQuotes(pool)
            await quotes.create(TENANT, {"id": "req_sample", "payload": {"kind": "link"}, "contact": {}})
            assert await quotes.status(OTHER, "req_sample") is None
            assert await quotes.claim(OTHER, "req_sample") is None
            claims = await asyncio.gather(quotes.claim(TENANT, "req_sample"), quotes.claim(TENANT, "req_sample"))
            assert sum(claim is not None for claim in claims) == 1
            await quotes.finish(TENANT, "req_sample", "not_configured")
            assert await quotes.pending(TENANT) == ["req_sample"]
            assert await quotes.claim(TENANT, "req_sample")
            await quotes.finish(TENANT, "req_sample", None)
            assert not await quotes.pending(TENANT)
            assert await quotes.status(TENANT, "req_sample") == {"status": "sent", "error": None}
            assert await quotes.claim(TENANT, "req_sample") is None
            await asyncio.gather(*(quotes.count(TENANT, "searches") for _ in range(10)))
            counts = await quotes.analytics(TENANT, date.min)
            assert counts["quotes"] == 1 and counts["searches"] == 10
            assert set((await quotes.analytics(OTHER, date.min)).values()) == {0}
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT sent_at IS NOT NULL FROM agent_rig.quotes WHERE id='req_sample'")
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
