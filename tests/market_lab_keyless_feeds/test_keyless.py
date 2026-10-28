"""Saved-response tests: no publisher, search engine or model is contacted."""
import io
import json
import socket
import sys
import urllib.error
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "agents/market_lab"), str(ROOT / "agents/_chassis")]
from core.feed_links import source_for
from core.evidence import answer, document, document_page
from core.jobs import perform_refresh
from core.ledger import MemoryLedger
from feeds.adapters import ADAPTERS
from feeds.catalog import sources
from feeds.collect import EvidenceClient, collect
from feeds.db import apply_schema, connect
from feeds.fetch import MemoryReader
from feeds.keyless import MAX_BYTES, check_feed_url, comtrade_url, public_link
from feeds.live import BlockedSite, PoliteClient
from feeds.reader import FixtureReader
from feeds.store import Store
from market_lab_routes import build_router

FIXTURES = ROOT / "tests/market_lab_keyless_feeds/fixtures"
ALL_FEEDS = ROOT / "tests/fixtures/feeds"
OWNER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
FEED_URL = "https://www.federalreserve.gov/feeds/press_all.xml"


def rss():
    return source_for({"id": OWNER, "url": FEED_URL, "label": "Federal Reserve", "cadence": "daily"})


def spec(name):
    return next(source for source in sources("ffl") if source.id == name)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*_args, **_kwargs):
        raise AssertionError("offline test attempted network access")
    monkeypatch.setattr(socket, "create_connection", fail)
    monkeypatch.setattr(socket, "getaddrinfo", fail)


def store_for(source):
    conn = connect(":memory:")
    apply_schema(conn)
    store = Store(conn)
    store.upsert_source(source)
    return store


@pytest.mark.parametrize("filename,count", [("feed.xml", 20), ("atom.xml", 18)])
def test_recorded_rss_and_atom_keep_links_dates_and_deduplicate(filename, count):
    source = replace(rss(), config={"files": [filename]})
    store = store_for(source)
    try:
        reader = FixtureReader([FIXTURES])
        assert ADAPTERS["rss"](source, reader, store, backfill=True) == count
        assert ADAPTERS["rss"](source, reader, store, backfill=False) == 0
        rows = store.conn.execute("SELECT * FROM events").fetchall()
        assert len(rows) == count
        assert all(row["title"] and row["url"].startswith("https://") for row in rows)
        assert all(datetime.fromisoformat(row["fetched_at"]).tzinfo for row in rows)
        assert all("<" not in row["body"] for row in rows)
    finally:
        store.conn.close()


def test_comtrade_recording_keeps_eight_values_and_source_times():
    result = collect(spec("comtrade_preview"), fixtures=str(ALL_FEEDS), backfill=True, client=EvidenceClient())
    recorded = json.loads((ALL_FEEDS / "comtrade_preview.json").read_text())["data"]
    assert result["note"] == ""
    assert len(result["points"]) == 8
    assert sorted(float(row["value"]) for row in result["points"]) == sorted(row["primaryValue"] for row in recorded)
    assert all(row["url"] == spec("comtrade_preview").url and row["fetched_at"] for row in result["points"])
    assert "maxRecords=500" in comtrade_url(spec("comtrade_preview"))
    assert "key" not in comtrade_url(spec("comtrade_preview"))


@pytest.mark.parametrize("mutation", ["reporterCode", "cmdCode", "partnerCode", "flowCode", "primaryValue", "limit"])
def test_comtrade_rejects_unexpected_series_or_unbounded_preview(mutation):
    source = spec("comtrade_preview")
    data = json.loads((ALL_FEEDS / "comtrade_preview.json").read_text())
    if mutation == "limit":
        data["data"] = data["data"] * 70
    else:
        data["data"][0][mutation] = "NaN" if mutation == "primaryValue" else "invalid"
    store = store_for(source)
    try:
        with pytest.raises(ValueError):
            ADAPTERS[source.adapter](source, MemoryReader(json.dumps(data)), store, backfill=True)
    finally:
        store.conn.close()


def test_search_stores_only_public_result_urls_and_never_search_page_urls():
    source = spec("searxng")
    store = store_for(source)
    data = json.loads((ALL_FEEDS / "searxng.json").read_text())
    data["results"].extend([{**data["results"][0], "url": "http://127.0.0.1/private"},
                            {**data["results"][0], "url": "https://example.com/?token=placeholder"}])
    try:
        assert ADAPTERS[source.adapter](source, MemoryReader(json.dumps(data)), store, backfill=True) == 2
        rows = store.conn.execute("SELECT * FROM events").fetchall()
        assert {row["url"] for row in rows} == {item["url"] for item in data["results"][:2]}
        assert all(row["fetched_at"] for row in rows)
    finally:
        store.conn.close()


@pytest.mark.parametrize("url", ["http://localhost/feed", "http://127.0.0.1/feed", "http://10.0.0.1/feed",
    "http://169.254.169.254/latest", "http://tank/feed", "ftp://example.com/feed", "https://user@example.com/feed",
    "https://example.com/?api_key=placeholder", "https://example.com:8080/feed", "http://[::1]/feed"])
def test_feed_subscription_rejects_private_credentials_and_non_web_addresses(url):
    with pytest.raises(ValueError):
        check_feed_url(url)


def test_dns_check_is_the_shared_tiger_check_and_rejects_mixed_addresses(monkeypatch):
    from chassis import public_urls
    import feeds.keyless as module
    calls = []
    def shared(value):
        calls.append(value)
        return value
    monkeypatch.setattr(public_urls, "check_url", shared)
    assert module.check_feed_url("https://example.com/feed?id=1") == "https://example.com/feed?id=1"
    assert calls == ["https://example.com/feed?id=1"]
    monkeypatch.undo()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_: [(2, 1, 6, "", ("93.184.216.34", 0)), (2, 1, 6, "", ("10.0.0.1", 0))])
    with pytest.raises(ValueError):
        check_feed_url("https://example.com/feed")


def test_every_redirect_is_validated_before_it_opens(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_: [(2, 1, 6, "", ("93.184.216.34", 0))])
    client = EvidenceClient(public_feeds=True)
    redirect = next(handler for handler in client.client.opener.__self__.handlers
                    if isinstance(handler, __import__("urllib.request", fromlist=["HTTPRedirectHandler"]).HTTPRedirectHandler))
    import urllib.request
    request = urllib.request.Request("https://example.com/feed")
    with pytest.raises(ValueError):
        redirect.redirect_request(request, None, 302, "", {}, "http://127.0.0.1/feed")


def test_public_queries_remain_citable_and_oversized_responses_are_rejected():
    assert public_link("https://example.com/article?id=42#section") == "https://example.com/article?id=42"
    client = PoliteClient(opener=lambda *_args, **_kwargs: io.BytesIO(b"x" * (MAX_BYTES + 1)), max_bytes=MAX_BYTES)
    with pytest.raises(RuntimeError):
        client.get("https://example.com/feed")


@pytest.mark.parametrize("body", [b"<html>not a feed</html>", b"<!DOCTYPE rss><rss/>", b"<!ENTITY x 'a'><rss/>"])
def test_nonfeeds_and_entity_declarations_never_become_observations(body):
    store = store_for(rss())
    try:
        with pytest.raises(ValueError):
            ADAPTERS["rss"](rss(), MemoryReader(body), store, backfill=True)
        assert store.conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0
    finally:
        store.conn.close()


@pytest.mark.parametrize("code", [401, 403, 429])
def test_access_boundaries_are_never_retried(code):
    calls = []
    def opener(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, code, "blocked", {}, None)
    client = PoliteClient(opener=opener, sleep=lambda _: None)
    for path in ("feed", "another"):
        with pytest.raises(BlockedSite):
            client.get("https://example.com/" + path)
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_rss_evidence_and_answers_belong_only_to_the_subscribing_tenant():
    ledger = MemoryLedger()
    result = await perform_refresh(tenant_id=OWNER, engine="ffl", ledger=ledger,
        extra_sources=[rss()], fixtures=str(FIXTURES), now=datetime(2026, 10, 28, tzinfo=timezone.utc))
    ident = result["feeds"][0]["document_id"]
    assert result["feeds"][0]["rows"] == 20
    saved = await document(ledger, OWNER, ident, fixtures=True)
    assert saved["url"] == FEED_URL and saved["fetched_at"]
    assert await document(ledger, OTHER, ident, fixtures=True) is None
    assert await document(ledger, OWNER, ident) is None
    question = "Federal Reserve"
    assert (await answer(ledger, OWNER, question, fixtures=True))["facts"]
    assert not (await answer(ledger, OTHER, question, fixtures=True))["facts"]
    page = await document_page(ledger, OWNER, ident, fixtures=True)
    assert all(event["display_url"] == event["url"] for event in page["events"])


def test_keyed_and_unavailable_feeds_stay_off_without_requests(monkeypatch):
    from feeds.keys import KEY_NAMES, missing_key
    for key in KEY_NAMES:
        monkeypatch.delenv(key, raising=False)
    called = []
    class Forbidden:
        def get(self, *args, **kwargs):
            called.append(args)
            raise AssertionError("keyed source opened network")
    for source in sources("ffl"):
        if missing_key(source):
            result = collect(source, fixtures=None, backfill=False, client=Forbidden())
            assert not result["points"] and not result["events"]
    assert not called
    assert not spec("uspto").enabled and spec("uspto").key_name == "USPTO_API_KEY"
    assert not {"marinetraffic", "freightos", "lme", "reddit"} & {s.id for s in sources("ffl")}


@pytest.mark.asyncio
async def test_search_corridor_calls_only_internal_searxng_and_checks_room_region(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", "placeholder-keyless-room-key")
    calls = []
    async def upstream(request):
        calls.append(request)
        assert request.url.host == "searxng" and request.url.path == "/search"
        return httpx.Response(200, json=json.loads((ALL_FEEDS / "searxng.json").read_text()))
    async def workspace_key():
        raise AssertionError("internal route should use room authentication")
    async with httpx.AsyncClient(transport=httpx.MockTransport(upstream)) as upstream_client:
        tank = SimpleNamespace(_http=upstream_client, require_key=workspace_key, box_region=lambda: "us-east",
            call_home=lambda home, _: home, home_region_refusal=lambda home, region: home != region)
        app = FastAPI()
        app.include_router(build_router(tank))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank") as client:
            body = {"tenant_id": OWNER, "question": "Federal Reserve", "home_region": "us-east"}
            assert (await client.post("/v1/market-lab/internal/search", json=body)).status_code == 401
            headers = {"x-tank-key": "placeholder-keyless-room-key"}
            assert (await client.post("/v1/market-lab/internal/search", json={**body, "home_region": "eu"}, headers=headers)).status_code == 403
            response = await client.post("/v1/market-lab/internal/search", json=body, headers=headers)
            assert response.status_code == 200 and len(response.json()["results"]) == 2
            assert response.headers["cache-control"] == "private, no-store"
    assert len(calls) == 1
