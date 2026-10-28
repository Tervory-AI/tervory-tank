"""Offline recorded-response proof; no fixture is a live-data fallback."""
import io
import json
import sys
import urllib.error
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents/market_lab"))
from feeds.adapters import ADAPTERS
from feeds.catalog import sources
from feeds.collect import EvidenceClient, collect
from feeds.db import apply_schema, connect
from feeds.fetch import MemoryReader, fetch_source
from feeds.live import BlockedSite, PoliteClient, USER_AGENT
from feeds.reader import FixtureReader
from feeds.store import Store
from feeds.runner import run as run_feeds
from core.evidence import answer, document, document_page, save_check
from core.ledger import MemoryLedger
from core.jobs import perform_refresh

FIXTURES = ROOT / "tests/fixtures/feeds"
OWNER = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"


def spec():
    return next(source for source in sources("ffl") if source.id == "sec_edgar")


@pytest.fixture
def store():
    conn = connect(":memory:")
    apply_schema(conn)
    db = Store(conn)
    db.upsert_source(spec())
    yield db
    conn.close()


def test_sec_recordings_deduplicate_and_keep_exact_citations(store):
    run = ADAPTERS[spec().adapter]
    assert run(spec(), FixtureReader([FIXTURES]), store, backfill=True) == 2000
    assert run(spec(), FixtureReader([FIXTURES]), store, backfill=False) == 0
    rows = store.conn.execute("SELECT * FROM events").fetchall()
    assert len(rows) == 2000
    for row in rows:
        assert row["url"].startswith("https://www.sec.gov/Archives/edgar/data/")
        assert row["url"].endswith("-index.html")
        assert datetime.fromisoformat(row["fetched_at"]).tzinfo
        assert row["kind"] == "filing"
    first = json.loads((FIXTURES / "sec_edgar/ruger.json").read_text())["filings"]["recent"]["accessionNumber"][0]
    assert any(row["url"] == f"https://www.sec.gov/Archives/edgar/data/95029/{first.replace('-', '')}/{first}-index.html" for row in rows)


class Response(io.BytesIO):
    status = 200


def test_sec_live_path_only_reads_named_filers_and_retains_download_provenance():
    calls = []
    def opener(request, **kwargs):
        calls.append(request)
        filename = {"https://data.sec.gov/submissions/CIK0000095029.json": "ruger.json",
                    "https://data.sec.gov/submissions/CIK0001092796.json": "swbi.json"}[request.full_url]
        return Response((FIXTURES / "sec_edgar" / filename).read_bytes())
    result = collect(spec(), fixtures=None, backfill=True,
                     client=EvidenceClient(PoliteClient(opener=opener, delay=0)))
    assert not result["note"]
    assert len(result["events"]) == 2000
    assert len(calls) == len(result["downloads"]) == 2
    assert all(call.get_header("User-agent") == USER_AGENT for call in calls)
    assert all(len(item["sha256"]) == 64 for item in result["downloads"])


@pytest.mark.parametrize("mutation", ["columns", "cik", "accession", "date", "name", "form"])
def test_sec_rejects_incomplete_or_false_citations(store, mutation):
    payload = json.loads((FIXTURES / "sec_edgar/ruger.json").read_text())
    recent = payload["filings"]["recent"]
    if mutation == "columns": recent["filingDate"].pop()
    if mutation == "cik": payload["cik"] = "1"
    if mutation == "accession": recent["accessionNumber"][0] = "https://other.test/"
    if mutation == "date": recent["filingDate"][0] = "2026-02-30"
    if mutation == "name": payload["name"] = ""
    if mutation == "form": recent["form"][0] = ""
    with pytest.raises(ValueError):
        ADAPTERS[spec().adapter](spec(), MemoryReader(json.dumps(payload)), store, backfill=True)
    assert store.conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0


def test_sec_rate_limit_covers_clients_hosts_and_delay_zero(monkeypatch):
    import feeds.live as live
    now = [100.0]
    calls = []
    monkeypatch.setattr(live, "_SEC_LAST", None)
    monkeypatch.setattr(live.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(live.time, "sleep", lambda delay: now.__setitem__(0, now[0] + delay))
    def opener(request, **kwargs):
        calls.append(now[0])
        return Response(b"{}")
    for index in range(12):
        client = PoliteClient(delay=0, opener=opener)
        client.get("https://" + ("www.sec.gov" if index % 2 else "data.sec.gov") + "/public")
    assert all(after - before >= 0.199 for before, after in zip(calls, calls[1:]))


@pytest.mark.parametrize("status", [403, 429])
def test_sec_denial_stops_without_retry_or_fixture_fallback(status):
    calls = []
    def opener(request, **kwargs):
        calls.append(request.full_url)
        raise urllib.error.HTTPError(request.full_url, status, "blocked", None, io.BytesIO())
    client = EvidenceClient(PoliteClient(opener=opener, delay=0))
    result = collect(spec(), fixtures=None, backfill=False, client=client)
    assert result["note"] == "Off, blocked"
    assert not result["events"] and not result["downloads"]
    assert len(calls) == 1
    with pytest.raises(BlockedSite):
        client.get("https://data.sec.gov/submissions/CIK0001092796.json")
    assert len(calls) == 1


def test_sec_wrong_filer_does_not_silently_get_stored(store):
    class Wrong:
        def get_text(self, url):
            return (FIXTURES / "sec_edgar/swbi.json").read_text()
    with pytest.raises(ValueError, match="unexpected SEC filer"):
        fetch_source(spec(), Wrong(), store, backfill=False)
    assert store.conn.execute("SELECT count(*) FROM events").fetchone()[0] == 0


@pytest.mark.asyncio
async def test_sec_answer_links_exact_saved_row_and_is_tenant_isolated():
    ledger = MemoryLedger()
    result = collect(spec(), fixtures=str(FIXTURES), backfill=True, client=EvidenceClient())
    check = await save_check(ledger, OWNER, result, at=datetime.now(timezone.utc))
    response = await answer(ledger, OWNER, "Recent SEC filings from Ruger", fixtures=True)
    assert response["facts"]
    for fact in response["facts"]:
        index = int(fact["href"].split("#event-")[1])
        saved = await document(ledger, OWNER, check["document_id"], fixtures=True)
        row = saved["events"][index]
        assert row["url"].startswith("https://www.sec.gov/Archives/edgar/data/95029/")
        assert row["fetched_at"]
        page = await document_page(ledger, OWNER, check["document_id"], row=index, row_kind="event", fixtures=True)
        assert any(item["url"] == row["url"] for item in page["events"])
    assert not (await answer(ledger, OTHER, "SEC filings", fixtures=True))["facts"]
    assert await document(ledger, OTHER, check["document_id"], fixtures=True) is None
    assert not (await answer(ledger, OWNER, "SEC filings"))["facts"]


def port_spec():
    return next(source for source in sources("ffl") if source.id == "port_nynj")


def test_port_recording_keeps_month_category_and_provenance(store):
    source = port_spec()
    store.upsert_source(source)
    run = ADAPTERS[source.adapter]
    assert run(source, FixtureReader([FIXTURES]), store, backfill=True) == 384
    assert run(source, FixtureReader([FIXTURES]), store, backfill=False) == 0
    rows = store.conn.execute("SELECT p.*, s.title, s.source_id, f.url FROM points p JOIN series s ON p.series_id=s.id JOIN feed_sources f ON s.source_id=f.id").fetchall()
    assert len(rows) == 384
    assert all(row["url"] == source.url and row["fetched_at"] for row in rows)
    assert {row["date"][:4] for row in rows} == {str(year) for year in range(2000, 2016)}
    assert any(row["date"] == "2012-01-01" and "imports" in row["title"] and str(row["value"]) == "228051" for row in rows)


def test_port_pagination_is_stable_and_stops_at_short_page(store):
    from urllib.parse import parse_qs, urlsplit
    source = port_spec()
    store.upsert_source(source)
    rows = json.loads((FIXTURES / "ports/nynj.json").read_text())
    calls = []
    class Pages:
        def get_text(self, url):
            calls.append(url)
            query = parse_qs(urlsplit(url).query)
            assert query["$order"] == [":id"] and query["$limit"] == ["1000"]
            assert query["$offset"] == [str((len(calls) - 1) * 1000)]
            return json.dumps([rows[0]] * 1000 if len(calls) == 1 else rows[1:])
    assert fetch_source(source, Pages(), store, backfill=True) == 384
    assert len(calls) == 2


@pytest.mark.parametrize("field,value", [("volume", "NaN"), ("volume", "-1"), ("month", "unknown"), ("year", ""), ("type", "Unknown")])
def test_port_invalid_rows_fail_without_inventing_values(store, field, value):
    source = port_spec()
    row = json.loads((FIXTURES / "ports/nynj.json").read_text())[0]
    row[field] = value
    with pytest.raises((ValueError, KeyError)):
        ADAPTERS[source.adapter](source, MemoryReader(json.dumps([row])), store, backfill=True)
    assert store.conn.execute("SELECT count(*) FROM points").fetchone()[0] == 0


def test_port_throttling_rolls_back_partial_pages_and_does_not_retry(tmp_path):
    calls = []
    raw = json.loads((FIXTURES / "ports/nynj.json").read_text())[0]
    def opener(request, **kwargs):
        calls.append(request)
        if len(calls) == 1:
            return Response(json.dumps([raw] * 1000).encode())
        raise urllib.error.HTTPError(request.full_url, 429, "throttled", None, io.BytesIO())
    path = str(tmp_path / "proof.sqlite")
    status = run_feeds(path, engine="ffl", source="port_nynj", live=True,
                      client=PoliteClient(opener=opener, delay=0))
    assert len(calls) == 2
    assert status[0]["last_error"] == "blocked"
    conn = connect(path)
    try:
        assert conn.execute("SELECT count(*) FROM points").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_port_answers_cite_published_period_not_fetch_year_and_isolate_tenants():
    ledger = MemoryLedger()
    result = await perform_refresh(tenant_id=OWNER, engine="ffl", source="port_nynj",
                                   fixtures=str(FIXTURES), ledger=ledger)
    check = result["feeds"][0]
    assert not check["note"] and check["rows"] == 384
    response = await answer(ledger, OWNER, "New York container imports in 2015", fixtures=True)
    assert response["facts"]
    saved = await document(ledger, OWNER, check["document_id"], fixtures=True)
    assert saved["url"] == port_spec().url
    for fact in response["facts"]:
        row = saved["points"][int(fact["href"].split("#point-")[1])]
        assert row["date"].startswith("2015-") and row["fetched_at"]
    assert not (await answer(ledger, OWNER, "New York container imports in 2026", fixtures=True))["facts"]
    assert not (await answer(ledger, OWNER, "California container imports in 2015", fixtures=True))["facts"]
    assert not (await answer(ledger, OTHER, "New York container imports in 2015", fixtures=True))["facts"]
    assert await document(ledger, OTHER, check["document_id"], fixtures=True) is None
