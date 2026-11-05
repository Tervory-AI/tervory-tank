"""Run real import/scheduler code with fixture sources and an isolated database."""
import asyncio
from contextlib import asynccontextmanager
import json
from unittest.mock import AsyncMock
from uuid import uuid4

import asyncpg
import httpx
import pytest

from test_rig_feeds import ROOT, TENANT, SHOP, WOO, MERCHANT
from rigbox.feed_runtime import fetch
from rigbox.service import Service
from rigbox.store import MemoryStore, PgStore

OTHER = "22222222-2222-4222-8222-222222222222"
URL = "https://supplier.example/catalogue"
FIELDS = "sku,name,brand,category,price,image_url"
VALUES = "DESK-1,Desk,North,furniture,25.00,https://supplier.example/desk.png"
ROW = dict(zip(FIELDS.split(","), VALUES.split(",")))


def source(kind):
    return {
        "shopify": json.dumps(SHOP).encode(), "woocommerce": json.dumps(WOO).encode(),
        "google": MERCHANT.encode(), "csv": (FIELDS + "\n" + VALUES + "\n").encode(),
        "tsv": (FIELDS + "\n" + VALUES + "\n").replace(",", "\t").encode(),
        "json": json.dumps([ROW]).encode(),
        "xml": ("<catalogue><product>" + "".join(f"<{k}>{v}</{k}>" for k, v in ROW.items()) + "</product></catalogue>").encode(),
        "xlsx": (ROOT / "tests/fixtures/rig_feed_formats/distributor.xlsx").read_bytes(),
    }[kind]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["shopify", "woocommerce", "google", "csv", "tsv", "json", "xml", "xlsx"])
async def test_every_registered_format_refreshes_with_tenant_receipt(kind):
    store = MemoryStore()
    await store.put_feed(TENANT, kind, URL, "USD")
    service = Service(store)
    body = source(kind)
    first = (await service.pull_feeds(TENANT, AsyncMock(return_value=body)))[0]
    assert not first["rejected"] and first["added"] > 0
    second = (await service.pull_feeds(TENANT, AsyncMock(return_value=body)))[0]
    assert second["added"] == 0 and second["updated"] == first["added"]
    assert len(await store.receipts(TENANT)) == 2
    assert (await store.receipts(TENANT))[0]["updated"] == first["added"]
    assert await store.products(OTHER) == await store.receipts(OTHER) == []
    assert URL not in json.dumps(await store.receipts(TENANT))


@pytest.mark.asyncio
async def test_failed_source_does_not_block_next_feed_or_leak_response():
    store = MemoryStore()
    await store.put_feed(TENANT, "csv", URL + "/failed", "USD")
    await store.put_feed(TENANT, "csv", URL, "USD")
    async def read(url):
        if url.endswith("failed"):
            raise ValueError("placeholder-private-response")
        return source("csv")
    reports = await Service(store).pull_feeds(TENANT, read)
    assert reports[0]["rejected"] == [{"row": 0, "reason": "feed unavailable"}]
    assert reports[1]["added"] == 1
    assert len(await store.receipts(TENANT)) == 2
    assert "placeholder-private-response" not in json.dumps(reports + await store.receipts(TENANT))


@pytest.mark.asyncio
async def test_bad_file_preserves_catalogue_and_receipt_failure_rolls_back():
    store = MemoryStore()
    await store.put_feed(TENANT, "csv", URL, "USD")
    service = Service(store)
    await service.pull_feeds(TENANT, AsyncMock(return_value=source("csv")))
    before = await store.products(TENANT)
    bad = source("csv") + b"BROKEN,,,,,\n"
    report = (await service.pull_feeds(TENANT, AsyncMock(return_value=bad)))[0]
    assert report["rejected"] and report["added"] == report["updated"] == 0
    assert await store.products(TENANT) == before
    original = store.save_feed_receipt
    store.save_feed_receipt = AsyncMock(side_effect=RuntimeError("receipt unavailable"))
    with pytest.raises(RuntimeError):
        await service.pull_feeds(TENANT, AsyncMock(return_value=source("csv").replace(b"25.00", b"30.00")))
    store.save_feed_receipt = original
    assert await store.products(TENANT) == before


@pytest.mark.asyncio
async def test_cancelled_refresh_is_not_reported_as_a_source_failure():
    store = MemoryStore()
    await store.put_feed(TENANT, "csv", URL, "USD")
    with pytest.raises(asyncio.CancelledError):
        await Service(store).pull_feeds(TENANT, AsyncMock(side_effect=asyncio.CancelledError))
    assert await store.receipts(TENANT) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("url", ["http://supplier.example/feed", "https://localhost/feed",
    "https://supplier.example:8443/feed", "https://user:placeholder@ supplier.example/feed",
    "https://supplier.example/feed#fragment"])
async def test_feed_transport_refuses_nonpublic_or_credential_urls(monkeypatch, url):
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "getaddrinfo", AsyncMock(return_value=[(0, 0, 0, "", ("127.0.0.1", 443))]))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: pytest.fail("request escaped"))) as http:
        with pytest.raises(ValueError):
            await fetch(http, url)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [200, 206, 302, 429, 500])
async def test_transport_pins_dns_checks_status_and_preserves_bytes(monkeypatch, status):
    loop = asyncio.get_running_loop()
    resolver = AsyncMock(return_value=[(0, 0, 0, "", ("93.184.215.14", 443))])
    monkeypatch.setattr(loop, "getaddrinfo", resolver)
    def response(request):
        assert request.url.host == "93.184.215.14"
        assert request.headers["host"] == "supplier.example"
        assert request.extensions["sni_hostname"] == "supplier.example"
        return httpx.Response(status, content=source("xlsx"), headers={"location": "http://127.0.0.1/private"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        if status == 200:
            assert await fetch(http, URL) == source("xlsx")
        else:
            with pytest.raises(ValueError):
                await fetch(http, URL)
    resolver.assert_awaited_once()


@pytest.mark.asyncio
async def test_transport_refuses_mixed_dns_and_stream_overflow(monkeypatch):
    import rigbox.feed_runtime as runtime
    loop = asyncio.get_running_loop()
    answers = [(0, 0, 0, "", (ip, 443)) for ip in ("93.184.215.14", "127.0.0.1")]
    monkeypatch.setattr(loop, "getaddrinfo", AsyncMock(return_value=answers))
    hits = []
    def response(request):
        hits.append(request)
        return httpx.Response(200, content=b"12345")
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        with pytest.raises(ValueError):
            await fetch(http, URL)
        assert not hits
        answers.pop()
        monkeypatch.setattr(runtime, "LIMIT", 4)
        with pytest.raises(ValueError):
            await fetch(http, URL)
        assert len(hits) == 1


@pytest.mark.asyncio
async def test_new_feed_only_tenant_gets_nightly_schedule_without_restart():
    from chassis.db import ensure_schema
    from rigbox.quotes.schedules import refresh
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    admin, name = _admin_url(), "rig_finish_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        async with asyncpg.create_pool(_database_url(admin, name)) as pool:
            store = PgStore(pool)
            await store.apply_schema()
            async with pool.acquire() as conn:
                await ensure_schema(conn, "rig")
            assert await refresh(pool, store, "rig") == 0
            await store.put_feed(TENANT, "csv", URL, "USD")
            assert await refresh(pool, store, "rig") == 1
            assert await refresh(pool, store, "rig") == 1
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT tenant_id,cron,kind FROM agent_rig.schedules WHERE kind='pull_feeds'")
            assert [(str(r['tenant_id']), r['cron'], r['kind']) for r in rows] == [(TENANT, '0 3 * * *', 'pull_feeds')]
            result = await Service(store).pull_feeds(TENANT, AsyncMock(return_value=source("csv")))
            assert result[0]["added"] == 1
            assert (await store.receipts(TENANT))[0]["added"] == 1
    finally:
        await _drop_database(admin, name)
