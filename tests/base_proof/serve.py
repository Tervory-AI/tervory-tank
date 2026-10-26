"""Local fixture Tank API, used only by the reproducible Workspace proof."""
import os
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "tank"), str(ROOT / "tests")]
from base_product_fixtures import fixture_app  # noqa: E402

os.environ["TANK_API_KEY"] = "local-fixture"
app, store = fixture_app()


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
