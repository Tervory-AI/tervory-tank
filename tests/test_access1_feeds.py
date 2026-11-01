"""Official feeds and private numeric portal reads never enter model extraction."""
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/_chassis"))
sys.path.insert(0, str(ROOT / "agents/tiger"))
from watch import MemoryStore, DomainLimiter, run_check  # noqa: E402


@pytest.mark.asyncio
async def test_feed_outranks_scrape_and_model():
    tenant = str(uuid.uuid4()); store = MemoryStore()
    watch = {"tenant_id": tenant, "url": "https://dealer.example/product", "threshold": "0"}
    async def forbidden(*args): raise AssertionError("Feed must be used first")
    async def feed(owner, url):
        assert owner == tenant and url == watch["url"]
        return {"found": True, "item": {"name": "Desk lamp", "price": "12.50", "quantity": "7", "currency": "USD"}, "receipt": {"source": "dealer_api", "row_count": 40}}
    result = await run_check(store, tenant, watch, "tiger", forbidden, forbidden, forbidden, forbidden, DomainLimiter(0), feed=feed)
    assert result["price"] == "12.50" and result["method"] == "official_feed"
    assert result["receipt"]["row_count"] == 40
    assert not await store.latest_observation(str(uuid.uuid4()), watch["url"])


@pytest.mark.asyncio
async def test_private_portal_never_calls_extract_ocr_or_shared_training():
    tenant = str(uuid.uuid4()); store = MemoryStore()
    watch = {"tenant_id": tenant, "url": "https://dealer.example/product", "threshold": "0"}
    async def forbidden(*args): raise AssertionError("Private data must stay in plain code")
    async def render(*args): return {"ok": True, "portal_item": {"price": "12.50", "quantity": "7", "currency": "USD"}, "html": ""}
    async def robots(*args): return ""
    result = await run_check(store, tenant, watch, "tiger", render, forbidden, forbidden, robots, DomainLimiter(0))
    assert result["price"] is None and result["receipt"]["private"]
    assert result["observation"]["issue"] == "missing_name" and result["alerts"] == []
