"""Explicit neutral sample server for cloud development. Never mounted by app.py.

PYTHONPATH=agents/rig uvicorn rigbox.quotes.sample:app --port 8001
Uses in-memory data and a recording sender. It makes no external requests.
"""

from contextlib import asynccontextmanager
import os

from fastapi import FastAPI

from rigbox.api import mount
from rigbox.quotes.api import mount as mount_quotes
from rigbox.quotes.hosting import mount as mount_widget
from rigbox.quotes.service import QuoteService
from rigbox.quotes.store import MemoryQuotes
from rigbox.service import RecordingHandoff, hash_key
from rigbox.store import MemoryStore

TENANT = "44444444-4444-4444-8444-444444444444"
KEY = "rk_pub_neutral_sample"


async def seed(store, tenant: str = TENANT, *, sample: bool = True):
    for sku, name, category, price in [
        ("CORE-1", "Core One", "core", 100),
        ("PART-A", "Part Alpha", "part", 20),
        ("PART-B", "Part Beta", "part", 30),
        ("PART-DRAFT", "Unapproved Part", "part", 15),
    ]:
        await store.upsert_product(tenant, {
            "sku": sku, "id": sku, "name": name, "brand": "Sample", "category": category,
            "price": price, "currency": "ZAR", "image_url": "", "active": True,
            "attributes": {"sample": sample, "summary": "Neutral stand-in product"},
        })
    for part in ("PART-A", "PART-B", "PART-DRAFT"):
        await store.upsert_fit(tenant, {"part_sku": part, "fits_sku": "CORE-1", "rule": {},
            "source": "import" if part != "PART-DRAFT" else "suggested",
            "approved": part != "PART-DRAFT", "note": "Sample approved mounting point"})
    await store.set_template(tenant, "core", {"tiers": [
        {"tier": "essential", "label": "A simple setup", "roles": [{"role": "Part", "category": "part"}]},
    ]})
    await store.put_retailer(tenant, "rig4-neutral-sample", None, None, "Sample retailer")
    await store.put_key(tenant, hash_key(KEY), "publishable",
                        [os.environ.get("RIG_SAMPLE_ORIGIN", "http://127.0.0.1:8001")])


@asynccontextmanager
async def lifespan(application: FastAPI):
    store = MemoryStore()
    await seed(store)
    application.state.rig = QuoteService(store, None, RecordingHandoff(), MemoryQuotes(store))
    os.environ.setdefault("RIG_WIDGET_PUBLISHABLE_KEY", KEY)
    yield


app = FastAPI(lifespan=lifespan)
mount(app)
mount_quotes(app)
mount_widget(app)


@app.get("/health")
async def health():
    return {"ok": True, "sample": True}
