"""Local fixture Tank API, used only by the reproducible Workspace proof."""
import os
from decimal import Decimal
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tank"), str(ROOT / "tests")]
from base_product_fixtures import AT, fixture_app  # noqa: E402

os.environ["TANK_API_KEY"] = "local-fixture"
app, store = fixture_app()

original_dispatch = store.dispatch

async def dispatch_with_price_examples(tenant):
    before = len(store.rows[tenant])
    await original_dispatch(tenant)
    new_rows = store.rows[tenant][before:]
    from base_evidence import row_fields
    for row in new_rows:
        row["profile"]["phone"]["value"] = "+15125550101"
        row["passes"]["2b"]["field_observations"][1]["phones"] = ["5125550101"]
        if row["licence_type"] == "unspecified":
            row["passes"]["2b"]["access_error"] = {"status": "blocked", "url": "https://upload.example/"}
        row["fields"] = row_fields(row)
    if new_rows:
        # Explicit offline examples: one priced search and one unpriced search.
        # No provider is called and these rows never enter a real ledger.
        for status, amount in (("set", Decimal("0.000792")), ("not_set", Decimal(0))):
            store.receipts[tenant].append({"id": uuid.uuid4(), "record_id": new_rows[0]["record_id"], "ts": AT,
                "rung": 1, "vendor": "brave.search", "units": 1, "cost_usd": amount, "cost_status": status, "outcome": "delivered"})

store.dispatch = dispatch_with_price_examples



@app.get("/v1/base/batches")
async def batches(tenant_id: uuid.UUID):
    return [{"batch": row["batch"], "started": "2026-10-26", "total": row["records_count"], "done": row["records_count"],
             "failed": 0, "pending": 0, "with_site": row["records_count"], "with_email": row["records_count"]}
            for row in await store.campaigns(tenant_id)]


@app.get("/v1/base/records")
async def records(tenant_id: uuid.UUID, batch: str | None = None, offset: int = 0, limit: int = 50):
    rows = await store.results(tenant_id)
    return [row for row in rows if not batch or row["batch"] == batch][offset:offset + limit]


@app.get("/v1/skala")
async def skills():
    return []


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8141)
