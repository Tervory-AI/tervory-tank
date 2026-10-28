"""Verify all document DELETEs on disposable Postgres, then roll back test rows."""
import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from core.document_read import extract
from core.documents import accept, forget
from core.ledger import PostgresLedger


async def counts(conn, tenant, file_id):
    return dict(await conn.fetchrow("""
        SELECT
          (SELECT count(*) FROM agent_market_lab.points p JOIN agent_market_lab.series s ON p.series_id=s.id
             WHERE s.tenant_id=$1 AND s.source=$2) AS points,
          (SELECT count(*) FROM agent_market_lab.events p JOIN agent_market_lab.series s ON p.series_id=s.id
             WHERE s.tenant_id=$1 AND s.source=$2) AS events,
          (SELECT count(*) FROM agent_market_lab.batch_points WHERE tenant_id=$1 AND source=$2) AS batch_points,
          (SELECT count(*) FROM agent_market_lab.batches WHERE tenant_id=$1 AND source=$2) AS batches,
          (SELECT count(*) FROM agent_market_lab.series WHERE tenant_id=$1 AND source=$2) AS series,
          (SELECT count(*) FROM agent_market_lab.uploaded_files WHERE tenant_id=$1 AND id=$3) AS uploaded_files
    """, UUID(tenant), "upload:" + file_id, UUID(file_id)))


async def main():
    target = os.environ.get("DATABASE_URL", "")
    parsed = urlsplit(target)
    if parsed.hostname not in {"localhost", "127.0.0.1"} or not parsed.path.endswith("_test"):
        raise RuntimeError("Requires an explicitly selected loopback *_test database")
    conn = await asyncpg.connect(target)
    transaction = conn.transaction()
    await transaction.start()
    try:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        owner, other, file_id, kept_id = (str(uuid4()) for _ in range(4))
        rows = b"date,value,unit,series\n2026-09-01,100,cartons,inventory\n2026-09-08,110,cartons,inventory\n"
        for tenant, ident in ((owner, file_id), (owner, kept_id), (other, file_id)):
            await accept(ledger, tenant, ident, "inventory.csv", extract("inventory.csv", rows), region="us-east")
            await ledger.save_event(tenant + ":upload:" + ident + ":0", tenant,
                                    {"date": "2026-09-08", "kind": "changed", "size": 1})
        before = await counts(conn, owner, file_id)
        assert before == {"points": 2, "events": 1, "batch_points": 2, "batches": 1, "series": 1, "uploaded_files": 1}
        kept_before = await counts(conn, owner, kept_id)
        other_before = await counts(conn, other, file_id)
        assert kept_before == other_before == before
        await forget(ledger, owner, file_id)
        after = await counts(conn, owner, file_id)
        assert after == dict.fromkeys(before, 0)
        assert await counts(conn, owner, kept_id) == kept_before
        assert await counts(conn, other, file_id) == other_before
        await forget(ledger, owner, file_id)
        assert await counts(conn, owner, file_id) == after
        result = {"before": before, "after": after, "same_tenant_other_file_preserved": True,
                  "other_tenant_same_file_id_preserved": True, "repeat_delete_safe": True, "result": "passed"}
    finally:
        await transaction.rollback()
        await conn.close()
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
