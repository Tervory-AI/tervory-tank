"""Optional local database checks; the default test suite needs no server."""
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.evidence import answer, document, document_page, overview
from core.jobs import perform_refresh
from core.ledger import PostgresLedger


@pytest.mark.asyncio
async def test_real_postgres_round_trip_and_tenant_isolation():
    target = os.environ.get("DATABASE_URL")
    if not target:
        pytest.skip("optional local Postgres check")
    url = urlsplit(target)
    if url.hostname not in {"localhost", "127.0.0.1"} or not url.path.endswith("_test"):
        pytest.skip("requires an explicitly selected local test database")
    import asyncpg
    conn = await asyncpg.connect(target)
    transaction = conn.transaction()
    await transaction.start()
    try:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        await ledger.apply_schema()
        owner, other = str(uuid.uuid4()), str(uuid.uuid4())
        result = await perform_refresh(tenant_id=owner, engine="ffl", ledger=ledger, fixtures=str(ROOT / "tests/fixtures/feeds"))
        assert sum(check["rows"] > 0 for check in result["feeds"]) == 16
        assert (await overview(ledger, owner, "ffl", fixtures=True))["on_count"] == 16
        assert (await overview(ledger, other, "ffl", fixtures=True))["on_count"] == 0
        assert (await overview(ledger, owner, "ffl"))["on_count"] == 0
        response = await answer(ledger, owner, "latest population", fixtures=True)
        assert response["facts"]
        ident = response["facts"][0]["href"].split("/")[-1].split("?")[0]
        assert await document(ledger, owner, ident, fixtures=True)
        assert await document(ledger, other, ident, fixtures=True) is None
        assert await document_page(ledger, owner, ident) is None
        assert await document_page(ledger, owner, ident, fixtures=True)
        assert await document_page(ledger, other, ident, fixtures=True) is None
        assert not (await answer(ledger, other, "latest population", fixtures=True))["facts"]
        previous = await document(ledger, owner, ident, fixtures=True)
        await perform_refresh(tenant_id=owner, engine="ffl", ledger=ledger, source="census_population", fixtures=str(ROOT / "tests/fixtures/feeds"))
        assert await document(ledger, owner, ident, fixtures=True) == previous
    finally:
        await transaction.rollback()
        await conn.close()
