"""Apply the additive schema twice and exercise real tenant-scoped delivery state."""

import asyncio
from datetime import date, datetime

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
            assert await quotes.pending(TENANT) == []
            await quotes.retry_now(TENANT, "req_sample")
            assert await quotes.claim(TENANT, "req_sample")
            await quotes.finish(TENANT, "req_sample", None)
            assert not await quotes.pending(TENANT)
            assert await quotes.status(TENANT, "req_sample") == {
                "status": "sent", "error": None, "attempts": 2, "next_attempt_at": None}
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


@pytest.mark.asyncio
async def test_replicas_retry_exhaustion_and_settled_search_receipts():
    from uuid import UUID
    from rigbox.quotes.limits import PgRateLimits

    admin = _admin_url()
    name = "rig4b_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=10)
        try:
            store = PgStore(pool)
            await store.apply_schema()
            limits = [PgRateLimits(pool), PgRateLimits(pool)]
            # Keep the small concurrent burst within one database clock window.
            async with pool.acquire() as conn:
                seconds = float(await conn.fetchval("SELECT extract(epoch FROM clock_timestamp()) % 60"))
            if seconds > 55:
                await asyncio.sleep(60 - seconds + 0.05)
            outcomes = await asyncio.gather(*(limits[i % 2].consume(TENANT, "192.0.2.1",
                "/v1/rig/quote" if i % 2 else "/v1/rig/link-quote") for i in range(10)))
            assert sum(outcome.retry_after == 0 for outcome in outcomes) == 5
            assert (await PgRateLimits(pool).consume(TENANT, "192.0.2.1", "/v1/rig/quote")).retry_after > 0
            assert (await limits[0].consume(TENANT, "192.0.2.2", "/v1/rig/quote")).retry_after == 0
            assert (await limits[0].consume(OTHER, "192.0.2.1", "/v1/rig/quote")).retry_after == 0
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT hits FROM agent_rig.rate_counts WHERE tenant_id=$1 AND route='quotes' AND client_hash=''::bytea", UUID(TENANT)) == 6
                rows = await conn.fetch("SELECT client_hash FROM agent_rig.rate_counts WHERE tenant_id=$1", UUID(TENANT))
                assert all(len(row["client_hash"]) in (0, 32) for row in rows)
                await conn.execute("UPDATE agent_rig.rate_counts SET hits=600 WHERE tenant_id=$1 AND route='quotes' AND client_hash=''::bytea", UUID(TENANT))
            assert (await limits[1].consume(TENANT, "192.0.2.3", "/v1/rig/quote")).hold
            # Holds remain bounded per shopper and persist across replicas.
            for _ in range(4):
                held = await limits[0].consume(TENANT, "192.0.2.3", "/v1/rig/link-quote")
                assert held.hold and held.retry_after == 0
            assert (await limits[1].consume(TENANT, "192.0.2.3", "/v1/rig/quote")).retry_after > 0
            assert (await limits[1].consume(TENANT, "192.0.2.3", "/v1/rig/search")).retry_after == 0

            quotes = PgQuotes(pool)
            await quotes.create(TENANT, {"id": "held", "payload": {}, "contact": {}}, hold=True)
            assert (await quotes.analytics(TENANT, date.min))["quotes"] == 0
            assert await quotes.claim(TENANT, "held") is None
            assert (await PgQuotes(pool).attention(TENANT))[0]["error"] == "tenant_quote_limit"
            assert not await quotes.attention(OTHER)
            await quotes.retry_now(TENANT, "held")
            assert await quotes.claim(TENANT, "held") is None
            await asyncio.gather(*(PgQuotes(pool).retry_now(TENANT, "held", resume=True) for _ in range(10)))
            assert (await quotes.analytics(TENANT, date.min))["quotes"] == 1
            assert (await quotes.claim(TENANT, "held"))["_attempt"] == 1
            await quotes.finish(TENANT, "held", None, 1)
            receipt = str(uuid4())
            accepted = await asyncio.gather(*(quotes.settled_search(TENANT, receipt, True) for _ in range(10)))
            assert accepted.count(True) == 1
            assert (await quotes.analytics(TENANT, date.min))["searches"] == 1
            assert (await quotes.analytics(TENANT, date.min))["no_results"] == 1
            assert (await quotes.analytics(OTHER, date.min))["searches"] == 0
            await quotes.create(TENANT, {"id": "bounded", "payload": {}, "contact": {}})
            for attempt in range(1, 7):
                row = await quotes.claim(TENANT, "bounded")
                assert row["_attempt"] == attempt
                await quotes.finish(TENANT, "bounded", "not_configured", attempt)
                assert not await quotes.pending(TENANT)
                if attempt < 6:
                    async with pool.acquire() as conn:
                        delay = await conn.fetchval("SELECT extract(epoch FROM next_attempt_at-updated_at) FROM agent_rig.quote_handoffs WHERE tenant_id=$1 AND quote_id='bounded'", UUID(TENANT))
                        assert float(delay) == 300 * 2 ** (attempt - 1)
                await quotes.retry_now(TENANT, "bounded")
            assert (await quotes.status(TENANT, "bounded"))["status"] == "needs_person"
            assert await quotes.claim(TENANT, "bounded") is None
            await quotes.retry_now(TENANT, "bounded", resume=True)
            assert (await quotes.claim(TENANT, "bounded"))["_attempt"] == 1
            # A stale attempt cannot overwrite a newer worker's result.
            await quotes.finish(TENANT, "bounded", None, 2)
            assert (await quotes.status(TENANT, "bounded"))["status"] == "sending"
            async with pool.acquire() as conn:
                await conn.execute("UPDATE agent_rig.quote_handoffs SET attempts=6, updated_at=now()-interval '6 minutes' WHERE tenant_id=$1 AND quote_id='bounded'", UUID(TENANT))
            assert not await quotes.pending(TENANT)
            assert (await quotes.status(TENANT, "bounded"))["status"] == "needs_person"
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_retention_purge_job_cascade_and_tenant_isolation(monkeypatch):
    import sys
    from pathlib import Path
    from uuid import UUID
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "_chassis"))
    from chassis.db import ensure_schema
    from rigbox.quotes.schedules import refresh
    from rigbox.quotes.store import retention_days

    monkeypatch.setenv("RIG_QUOTE_RETENTION_DAYS", "7")
    assert retention_days() == 7
    admin = _admin_url()
    name = "rig4_retention_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=5)
        try:
            store, quotes = PgStore(pool), PgQuotes(pool)
            await store.apply_schema()
            await store.put_retailer(TENANT, slug="retention", email=None, webhook=None)
            for tenant, quote_id in ((TENANT, "old"), (OTHER, "other_old"), (TENANT, "recent"), (TENANT, "active")):
                await quotes.create(tenant, {"id": quote_id, "payload": {"note": "contact note"},
                                             "contact": {"name": "Sample", "email": "sample@example.com"}})
            async with pool.acquire() as conn:
                await ensure_schema(conn, "rig")
                await conn.execute("UPDATE agent_rig.quotes SET created_at=now()-interval '8 days' WHERE id <> 'recent'")
                await conn.execute("UPDATE agent_rig.quote_handoffs SET status='sending', updated_at=now() WHERE quote_id='active'")
            await store.apply_schema()  # Re-running additive setup keeps rows.
            async with pool.acquire() as conn:
                # The FK is declared ON DELETE CASCADE by CREATE TABLE.
                assert await conn.fetchval("""SELECT confdeltype FROM pg_constraint
                    WHERE conrelid='agent_rig.quote_handoffs'::regclass
                    AND conname='quote_handoffs_quote_id_fkey'""") in (b"c", "c")
            assert await quotes.status(TENANT, "old") is not None  # Re-setup preserves rows.
            assert await quotes.claim(TENANT, "old") is None  # No expired delivery before purge.
            assert await quotes.purge(TENANT) == 1
            assert await quotes.status(TENANT, "old") is None  # Handoff cascaded.
            async with pool.acquire() as conn:
                handoffs = """SELECT count(*) FROM agent_rig.quote_handoffs WHERE tenant_id=$1 AND quote_id=$2"""
                assert await conn.fetchval(handoffs, UUID(TENANT), "old") == 0  # Deleted quote's handoff row is gone.
                assert await conn.fetchval(handoffs, UUID(OTHER), "other_old") == 1  # Other tenant untouched.
            assert await quotes.status(OTHER, "other_old") is not None
            assert await quotes.status(TENANT, "recent") is not None
            assert await quotes.status(TENANT, "active") is not None
            assert await refresh(pool, store, "rig") == 1
            assert await quotes.status(OTHER, "other_old") is None  # Removed retailer still expires.
            assert (await quotes.analytics(TENANT, date.min))["quotes"] == 3
            assert await quotes.purge(TENANT) == 0
            async with pool.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM agent_rig.quotes WHERE tenant_id=$1", UUID(TENANT)) == 2
                await conn.execute("UPDATE agent_rig.quote_handoffs SET updated_at=now()-interval '6 minutes' WHERE quote_id='active'")
            assert await quotes.purge(TENANT) == 1
            assert await quotes.status(TENANT, "active") is None
            assert await quotes.purge(OTHER) == 0
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_postgres_attention_keyset_paging_with_ties_removal_and_tenant_scope():
    from uuid import UUID
    admin = _admin_url()
    name = "rig4_pages_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=2)
        try:
            await PgStore(pool).apply_schema()
            quotes = PgQuotes(pool)
            for index in range(205):
                await quotes.create(TENANT, {"id": f"held_{index:03}", "payload": {}, "contact": {}}, hold=True)
            await quotes.create(OTHER, {"id": "other_held", "payload": {}, "contact": {}}, hold=True)
            async with pool.acquire() as conn:
                await conn.execute("UPDATE agent_rig.quotes SET created_at='2026-01-01T00:00:00Z' WHERE tenant_id=$1", UUID(TENANT))
            assert (await quotes.analytics(TENANT, date.min))["quotes"] == 0
            first = await quotes.attention(TENANT)
            assert len(first) == 100
            await quotes.retry_now(TENANT, "held_000", resume=True)
            second = await quotes.attention(TENANT, after=(datetime.fromisoformat(first[-1]["created_at"]), first[-1]["request_id"]))
            third = await quotes.attention(TENANT, after=(datetime.fromisoformat(second[-1]["created_at"]), second[-1]["request_id"]))
            assert len(second) == 100 and len(third) == 5
            assert [row["request_id"] for row in first + second + third] == [f"held_{index:03}" for index in range(205)]
            assert [row["request_id"] for row in await quotes.attention(OTHER)] == ["other_held"]
            assert (await quotes.analytics(TENANT, date.min))["quotes"] == 1
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.parametrize("value", ["0", "-1", "366", "invalid"])
def test_retention_cannot_be_unbounded(monkeypatch, value):
    from rigbox.quotes.store import retention_days
    monkeypatch.setenv("RIG_QUOTE_RETENTION_DAYS", value)
    with pytest.raises(ValueError, match="RIG_QUOTE_RETENTION_DAYS"):
        retention_days()


@pytest.mark.asyncio
async def test_retry_discovery_picks_up_retailers_added_after_startup():
    import sys
    from pathlib import Path
    from uuid import UUID
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "_chassis"))
    from chassis.db import ensure_schema
    from rigbox.quotes.schedules import refresh

    admin = _admin_url()
    name = "rig4b_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=2)
        try:
            store = PgStore(pool)
            await store.apply_schema()
            async with pool.acquire() as conn:
                await ensure_schema(conn, "rig")
            assert await refresh(pool, store, "rig") == 0
            await store.put_retailer(TENANT, "first", None, None, "Sample")
            assert await refresh(pool, store, "rig") == 1
            await store.put_retailer(OTHER, "second", None, None, "Another sample")
            assert await refresh(pool, store, "rig") == 2
            assert await refresh(pool, store, "rig") == 2
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT tenant_id, cron, kind FROM agent_rig.schedules ORDER BY tenant_id")
                assert [row["tenant_id"] for row in rows] == [UUID(TENANT), UUID(OTHER)]
                assert all(row["cron"] == "*/5 * * * *" and row["kind"] == "retry_quotes" for row in rows)
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
