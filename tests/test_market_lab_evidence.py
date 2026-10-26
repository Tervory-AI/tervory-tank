"""Launch path: collection, isolation, immutable citations and truthful status.

Saved inputs only. These tests are not evidence of a live client session.
"""
import asyncio
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI, HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
sys.path.insert(0, str(ROOT / "tank"))
from core.evidence import answer, document, document_page, latest_checks, overview, save_check
from core.jobs import perform_refresh
from core.ledger import MemoryLedger
from engines.ffl.engine import plan
from feeds.collect import EvidenceClient, collect, public_url
from feeds.catalog import sources
from feeds.published import commodity_rows, table_rows
from market_lab_routes import build_router

OWNER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
FIXTURES = ROOT / "tests/fixtures/feeds"


@pytest.mark.asyncio
async def test_every_public_feed_has_rows_but_fixtures_never_appear_in_the_client_path():
    ledger = MemoryLedger()
    result = await perform_refresh(tenant_id=OWNER, engine="ffl", ledger=ledger, fixtures=str(FIXTURES))
    by_source = {row["source_id"]: row for row in result["feeds"]}
    assert all(by_source[source]["rows"] > 0 for source in plan()["feeds"])
    assert all(by_source[source]["rows"] == 0 for source in plan()["linked_pages"])
    assert (await overview(ledger, OWNER, "ffl"))["on_count"] == 0
    assert (await overview(ledger, OWNER, "ffl", fixtures=True))["on_count"] == len(plan()["feeds"])
    assert (await overview(ledger, OTHER, "ffl", fixtures=True))["on_count"] == 0
    assert await document(ledger, OTHER, by_source["check_counts"]["document_id"], fixtures=True) is None
    assert await document(ledger, OWNER, by_source["check_counts"]["document_id"]) is None


@pytest.mark.asyncio
async def test_each_figure_links_to_an_exact_immutable_stored_row():
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=OWNER, engine="ffl", ledger=ledger, fixtures=str(FIXTURES))
    result = await answer(ledger, OWNER, "What are the latest population figures?", fixtures=True)
    assert result["facts"]
    assert (await answer(ledger, OTHER, "population", fixtures=True))["facts"] == []
    for fact in result["facts"]:
        href = fact["href"]
        assert href.startswith("/market-lab/sources/")
        ident = href.split("/")[-1].split("?")[0]
        index = int(href.split("#point-")[1])
        doc = await document(ledger, OWNER, ident, fixtures=True)
        point = doc["points"][index]
        page = await document_page(ledger, OWNER, ident, fixtures=True)
        shown = page["points"][index]
        assert shown["geo_name"] == point["title"].removeprefix("Population, ")
        assert shown["geo"] == point["geo"]  # Raw provenance remains unchanged.
        assert point["title"] in fact["text"]
        assert point["date"] in fact["text"]
        assert point["value"] in fact["text"].replace(",", "")
        before = json.dumps(doc, sort_keys=True)
        await perform_refresh(tenant_id=OWNER, engine="ffl", source="census_population", ledger=ledger, fixtures=str(FIXTURES))
        assert json.dumps(await document(ledger, OWNER, ident, fixtures=True), sort_keys=True) == before
    assert not (await answer(ledger, OWNER, "unrelated avocado harvest", fixtures=True))["facts"]


@pytest.mark.asyncio
async def test_failed_last_run_turns_off_without_destroying_old_documents():
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=OWNER, engine="ffl", source="check_counts", ledger=ledger, fixtures=str(FIXTURES))
    check = (await latest_checks(ledger, OWNER, fixtures=True))[0]
    old = await document(ledger, OWNER, check["document_id"], fixtures=True)
    await save_check(ledger, OWNER, {"source_id": "check_counts", "points": [], "events": [], "fixture": True,
                                   "note": "Off, source could not be read"}, at=datetime.now(timezone.utc))
    assert (await overview(ledger, OWNER, "ffl", fixtures=True))["on_count"] == 0
    assert not (await answer(ledger, OWNER, "check counts", fixtures=True))["facts"]
    assert await document(ledger, OWNER, check["document_id"], fixtures=True) == old


@pytest.mark.asyncio
async def test_removed_observations_are_not_reused_in_answers():
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=OWNER, engine="ffl", source="census_population", ledger=ledger, fixtures=str(FIXTURES))
    assert (await answer(ledger, OWNER, "population", fixtures=True))["facts"]
    for batch_id in list(ledger.pool.batches):
        ledger.remove_batch(OWNER, batch_id)
    assert not (await answer(ledger, OWNER, "population", fixtures=True))["facts"]


def test_missing_keys_never_start_a_fetch(monkeypatch):
    monkeypatch.delenv("EIA_API_KEY", raising=False)
    source = next(item for item in sources("ffl") if item.id == "eia_diesel")
    class NoNetwork:
        def get(self, *args, **kwargs):
            raise AssertionError("must not fetch")
    result = collect(source, fixtures=None, backfill=True, client=NoNetwork())
    assert result["note"] == "Off, needs key"
    assert result["points"] == []


def test_public_read_does_not_require_a_robots_fetch():
    from feeds.live import PoliteClient, USER_AGENT
    calls = []
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self): return b'{"saved":true}'
    def opener(request, **kwargs):
        calls.append(request)
        return Response()
    client = EvidenceClient(PoliteClient(opener=opener, delay=0))
    assert client.get_text("https://data.publisher.test/public") == '{"saved":true}'
    assert [call.full_url for call in calls] == ["https://data.publisher.test/public"]
    assert calls[0].get_header("User-agent") == USER_AGENT
    assert len(client.documents[0]["sha256"]) == 64
    assert public_url("https://data.publisher.test/table?key=unused#frag") == "https://data.publisher.test/table"
    with pytest.raises(ValueError): public_url("http://localhost/private")


def test_published_headings_and_dates_are_required():
    config = {"headings": {"date": ["month"], "value": ["total_teu"]}, "geo": "Port"}
    assert list(table_rows([[["month", "total_teu"], ["2024-01", "1,234"], ["unknown", "999"]]], config)) == [("2024-01-01", "Port", "1234")]
    columns = {"copper": {"ref": "copper", "unit": "USD/metric ton"}}
    assert list(commodity_rows([[["", "Copper"], ["2024M01", "8000.50"], ["missing", "9000"]]], columns)) == [(columns["copper"], "2024-01-01", "8000.50")]


@pytest.mark.asyncio
async def test_tank_corridor_enforces_auth_operation_and_tenant_shape():
    calls = []
    async def require_key():
        raise HTTPException(401, "unauthorized")
    class Client:
        async def post(self, url, **kwargs):
            calls.append(kwargs["json"])
            return httpx.Response(200, json={"feeds": [], "on_count": 0})
    tank = SimpleNamespace(require_key=require_key, shared_http=lambda: Client())
    app = FastAPI()
    app.include_router(build_router(tank))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.post("/v1/market-lab/overview", json={"tenant_id": OWNER})).status_code == 401
        app.dependency_overrides[require_key] = lambda: None
        assert (await client.post("/v1/market-lab/overview", json={})).status_code == 422
        assert (await client.post("/v1/market-lab/overview", json={"tenant_id": OWNER, "fixtures": "anything"})).status_code == 422
        assert (await client.post("/v1/market-lab/unknown", json={"tenant_id": OWNER})).status_code == 404
    assert calls == []


@pytest.mark.asyncio
async def test_live_adapter_interface_stores_saved_notices_with_download_identity():
    """Exercise the live interface using a saved response, never the network."""
    class SavedClient:
        documents = []
        def get_text(self, url, headers=None):
            self.documents.append({"url": public_url(url), "sha256": "fixture-digest"})
            return (FIXTURES / "noaa/alerts.json").read_text()
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=OWNER, engine="ffl", source="noaa_alerts", ledger=ledger, live=True, client=SavedClient())
    data = await overview(ledger, OWNER, "ffl")
    assert data["on_count"] == 1
    check = next(feed for feed in data["feeds"] if feed["id"] == "noaa_alerts")
    saved = await document(ledger, OWNER, check["document_id"])
    assert saved["events"]
    assert saved["downloads"][0]["url"].startswith("https://api.weather.gov/")
    assert saved["fixture"] is False  # the memory-only ledger has no production connection


def test_backfill_follows_saved_alert_pages_and_rejects_foreign_pagination():
    from feeds.db import apply_schema, connect
    from feeds.store import Store
    from feeds.fetch import _live_alerts
    spec = next(source for source in sources("ffl") if source.id == "noaa_alerts")
    class Pages:
        def __init__(self, foreign=False): self.calls = []; self.foreign = foreign
        def get_text(self, url, headers=None):
            self.calls.append(url)
            payload = json.loads((FIXTURES / "noaa/alerts.json").read_text())
            if len(self.calls) == 1:
                payload["pagination"] = {"next": "https://private.invalid/" if self.foreign else "https://api.weather.gov/alerts?cursor=next"}
            return json.dumps(payload)
    conn = connect(":memory:")
    try:
        apply_schema(conn)
        store = Store(conn)
        client = Pages()
        _live_alerts(spec, client, store, backfill=True)
        assert len(client.calls) == 2
        with pytest.raises(RuntimeError, match="pagination"):
            _live_alerts(spec, Pages(True), store, backfill=True)
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_question_area_and_year_are_constraints_not_just_rank_hints():
    ledger = MemoryLedger()
    await perform_refresh(tenant_id=OWNER, engine="ffl", source="listing_counts", ledger=ledger, fixtures=str(FIXTURES))
    result = await answer(ledger, OWNER, "Active listings in California in 2024", fixtures=True)
    assert result["facts"]
    from feeds.geo import state_for_area
    for fact in result["facts"]:
        ident = fact["href"].split("/")[-1].split("?")[0]
        index = int(fact["href"].split("#point-")[1])
        saved = await document(ledger, OWNER, ident, fixtures=True)
        assert state_for_area(saved["points"][index]["geo"]) == "CA"
        assert saved["points"][index]["date"].startswith("2024-")
    assert not (await answer(ledger, OWNER, "Active listings in California in 1990", fixtures=True))["facts"]


@pytest.mark.asyncio
async def test_proxy_to_room_serves_only_the_calling_tenants_stored_document(monkeypatch):
    import uuid
    from core.http import build_router as room_router
    ledger = MemoryLedger()
    await save_check(ledger, OWNER, {
        "source_id": "noaa_alerts", "name": "Weather alerts", "fixture": False,
        "points": [], "events": [{"title": "Saved notice", "body": "Saved source text", "date": "2024-01-01", "kind": "alert", "geo": "CA", "url": "https://api.weather.gov/alerts/saved"}],
        "downloads": [], "note": "",
    }, at=datetime.now(timezone.utc))
    ident = (await latest_checks(ledger, OWNER))[0]["document_id"]
    room_key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", room_key)
    class Context:
        async def __aenter__(self): return ledger
        async def __aexit__(self, *args): return None
    room = FastAPI()
    room.include_router(room_router(key_ok=lambda value: value == room_key, ledger_context=Context))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room)) as downstream:
        async def authenticated_workspace(): return None
        gateway = FastAPI()
        gateway.include_router(build_router(SimpleNamespace(require_key=authenticated_workspace, shared_http=lambda: downstream)))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=gateway), base_url="http://test") as client:
            response = await client.post("/v1/market-lab/document", json={"tenant_id": OWNER, "document_id": ident})
            assert response.status_code == 200
            assert response.json()["events"][0]["body"] == "Saved source text"
            assert response.headers["cache-control"] == "private, no-store"
            denied = await client.post("/v1/market-lab/document", json={"tenant_id": OTHER, "document_id": ident})
            assert denied.status_code == 404
            brief = await client.post("/v1/market-lab/ask", json={"tenant_id": OWNER, "question": "weather alerts"})
            assert brief.status_code == 200 and brief.json()["facts"]


def test_climate_average_spans_pagination_boundaries(monkeypatch):
    from feeds.db import apply_schema, connect
    from feeds.store import Store
    from feeds.fetch import _live_climate
    monkeypatch.setattr("feeds.fetch.require_env", lambda name: "unused-in-saved-transport")
    monkeypatch.setattr("feeds.fetch.STATE_FIPS", {"CA": "06"})
    source = next(item for item in sources("ffl") if item.id == "noaa_climate")
    source = replace(source, config={**source.config, "datatypes": ["TAVG"], "start": "2024-01-01"})
    class Pages:
        def get_text(self, url, headers=None):
            second = "offset=2" in url
            return json.dumps({
                "metadata": {"resultset": {"count": 2, "limit": 1, "offset": 2 if second else 1}},
                "results": [{"station": "second" if second else "first", "datatype": "TAVG", "date": "2024-01-01", "value": 4 if second else 2}],
            })
    conn = connect(":memory:")
    try:
        apply_schema(conn)
        store = Store(conn)
        assert _live_climate(source, Pages(), store, backfill=True) == 1
        rows = conn.execute("SELECT value FROM points").fetchall()
        assert len(rows) == 1 and float(rows[0]["value"]) == 3
    finally:
        conn.close()
