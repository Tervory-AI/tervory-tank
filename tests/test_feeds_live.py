"""Live feed behaviour, fixtures only. No socket."""

from __future__ import annotations

import hashlib
import sqlite3
import sys
import urllib.error
import urllib.parse
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

from feeds.adapters import ingest_alerts, ingest_climate, ingest_legiscan, parse_state_month_pdf  # noqa: E402
from feeds.catalog import sources  # noqa: E402
from feeds.cli import main  # noqa: E402
from feeds.db import apply_schema, connect  # noqa: E402
from feeds.fetch import _live_listing  # noqa: E402
from feeds.live import USER_AGENT, PoliteClient, complete_listing_link, safe_failure  # noqa: E402
from feeds.models import SourceSpec  # noqa: E402
from feeds.reader import FixtureReader  # noqa: E402
from feeds.runner import format_status  # noqa: E402
from feeds.store import Store  # noqa: E402

PDF = ROOT / "tests" / "fixtures" / "feeds_c12b" / "state_month.pdf"
HEADER = (
    "LIC_REGN\tLIC_DIST\tLIC_CNTY\tLIC_TYPE\tLIC_XPRDTE\tLIC_SEQN\t"
    "PREMISE_STATE\tPREMISE_ZIP_CODE\n"
)
MONTH_ONE = (
    HEADER
    + "1\t59\t037\t01\t6A\t00001\tCA\t90001\n"
    + "1\t59\t037\t01\t6A\t00002\tCA\t90001\n"
)
MONTH_TWO = (
    HEADER
    + "1\t59\t037\t01\t7B\t00001\tCA\t90001\n"
    + "5\t75\t201\t01\t6A\t00009\tTX\t77001\n"
)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        yield self._body

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False

    def close(self) -> None:
        return None


def _db(tmp_path: Path) -> str:
    return "sqlite:///" + str(tmp_path / "feeds.sqlite")


def _store(tmp_path: Path) -> tuple[str, object]:
    target = _db(tmp_path)
    conn = connect(target)
    apply_schema(conn)
    return target, Store(conn)


def _spec(source_id: str) -> SourceSpec:
    return next(item for item in sources("ffl") if item.id == source_id)


def _value(conn: sqlite3.Connection, ref: str, date: str) -> str | None:
    row = conn.execute(
        """
        SELECT value FROM points p JOIN series s ON s.id = p.series_id
        WHERE s.ref = ? AND p.date = ?
        """,
        (ref, date),
    ).fetchone()
    if row is None:
        return None
    return str(row[0])


def test_engine_is_required_and_not_imported_by_core() -> None:
    with pytest.raises(SystemExit):
        sources("")
    with pytest.raises(SystemExit):
        main(["status"])
    text = (ROOT / "agents" / "market_lab" / "feeds" / "catalog.py").read_text(encoding="utf-8")
    assert "engines.ffl" not in text
    assert "import lists" not in text
    assert _spec("listing_counts").adapter == "listing"


def test_return_to_an_earlier_value_is_a_new_vintage(tmp_path: Path) -> None:
    _target, store = _store(tmp_path)
    series = store.ensure_series("demo", "ref", "Demo", "units", "national", "US", "monthly")
    assert store.put_point(series, "2024-01-01", 1, "r") is True
    assert store.put_point(series, "2024-01-01", 2, "r") is True
    assert store.put_point(series, "2024-01-01", 1, "r") is True
    assert store.put_point(series, "2024-01-01", 1, "r") is False
    rows = store.conn.execute(
        "SELECT revision, value FROM points ORDER BY revision"
    ).fetchall()
    assert [(row["revision"], str(row["value"])) for row in rows] == [
        ("r", "1"),
        ("r#2", "2"),
        ("r#3", "1"),
    ]


def test_status_shows_last_success_rows_and_error(tmp_path: Path) -> None:
    _target, store = _store(tmp_path)
    spec = _spec("eia_diesel")
    store.upsert_source(spec)
    store.finish_run(spec.id, "2024-01-01T00:00:00+00:00", 4, None)
    store.finish_run(spec.id, "2024-02-01T00:00:00+00:00", 0, "boom")
    row = store.status()[0]
    assert row["id"] == spec.id
    assert row["last_success"]
    assert row["success_rows"] == 4
    assert row["last_rows"] == 0
    assert row["last_error"] == "boom"
    text = format_status([row])
    assert "last_success=" in text
    assert "rows=4" in text
    assert "error=boom" in text


def test_listing_streams_a_month_and_keeps_renewal_identity(tmp_path: Path) -> None:
    root = tmp_path / "fixtures"
    (root / "listing").mkdir(parents=True)
    (root / "listing" / "2024-01.tsv").write_text(MONTH_ONE, encoding="utf-8")
    (root / "listing" / "2024-02.tsv").write_text(MONTH_TWO, encoding="utf-8")

    class Spy(FixtureReader):
        def read_text(self, relative: str) -> str:
            if relative.endswith(".tsv"):
                raise AssertionError("loaded the whole month as text")
            return super().read_text(relative)

    spec = replace(
        _spec("listing_counts"),
        config={
            "files": ["listing/2024-01.tsv", "listing/2024-02.tsv"],
            "columns": _spec("listing_counts").config["columns"],
        },
    )
    _target, store = _store(tmp_path)
    from feeds.adapters import run_listing_clean

    inserted = run_listing_clean(spec, Spy([root]), store, backfill=True)
    assert inserted > 0
    conn = store.conn
    assert _value(conn, "new:state:CA", "2024-02-01") in {"0", "0.0"}
    assert _value(conn, "dropped:state:CA", "2024-02-01") in {"1", "1.0"}
    assert _value(conn, "new:state:TX", "2024-02-01") in {"1", "1.0"}
    assert _value(conn, "count:state:CA", "2024-01-01") in {"2", "2.0"}


def test_complete_list_link_ignores_other_files() -> None:
    html = (
        '<a href="/files/0124-ffl-list-alabama.txt">0124-ffl-list-alabama.txt</a>'
        '<a href="/files/0124-ffl-list-complete.txt">0124-ffl-list-complete.txt</a>'
    )
    stamp, url = complete_listing_link(html, "https://example.test/page")
    assert stamp == "2024-01"
    assert url == "https://example.test/files/0124-ffl-list-complete.txt"
    assert complete_listing_link("<p>no file</p>", "https://example.test/page") is None


def test_live_listing_streams_published_months(tmp_path: Path, monkeypatch) -> None:
    class Frozen(datetime):
        @classmethod
        def now(cls, tz: timezone | None = None) -> datetime:
            return datetime(2024, 2, 15, tzinfo=timezone.utc)

    monkeypatch.setattr("feeds.fetch.datetime", Frozen)
    files = {
        "https://files.example/0124-ffl-list-complete.txt": MONTH_ONE,
        "https://files.example/0224-ffl-list-complete.txt": MONTH_TWO,
    }

    class Scripted:
        def __init__(self) -> None:
            self.lines = 0

        def get_text(self, url: str, headers: dict[str, str] | None = None) -> str:
            if url.endswith(".txt"):
                raise AssertionError("full body read")
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
            month = query.get("ffl_date_month[value][month]", ["0"])[0]
            name = "0124" if month == "1" else "0224"
            return f'<a href="https://files.example/{name}-ffl-list-complete.txt">{name}-ffl-list-complete.txt</a>'

        def iter_lines(self, url: str, headers: dict[str, str] | None = None):
            self.lines += 1
            yield from files[url].splitlines(keepends=True)

    spec = replace(
        _spec("listing_counts"),
        config={**_spec("listing_counts").config, "start_year": 2024},
    )
    _target, store = _store(tmp_path)
    client = Scripted()
    inserted = _live_listing(spec, client, store, backfill=True)
    assert inserted > 0
    assert client.lines == 2
    assert _value(store.conn, "dropped:state:CA", "2024-02-01") in {"1", "1.0"}
    assert _value(store.conn, "new:state:CA", "2024-02-01") in {"0", "0.0"}


def test_state_month_pdf_fixture_counts_states_not_the_total() -> None:
    pytest.importorskip("pdfplumber")
    rows = parse_state_month_pdf(PDF.read_bytes())
    found = {(year, month, postal): value for year, month, postal, value in rows}
    assert found[("2024", 1, "CA")] == "10"
    assert found[("2024", 2, "CA")] == "12"
    assert found[("2024", 1, "TX")] == "5"
    assert ("2024", 2, "TX") not in found
    assert "22" not in {value for value in found.values()}


def test_live_pdf_source_reads_the_fixture(tmp_path: Path, monkeypatch) -> None:
    pytest.importorskip("pdfplumber")

    def opener(request, timeout=60):
        return FakeResponse(PDF.read_bytes())

    monkeypatch.setattr("urllib.request.urlopen", opener)
    target = _db(tmp_path)
    assert main(["run", "--live", "--source", "check_counts", "--engine", "ffl", "--db", target]) == 0
    conn = sqlite3.connect(target[len("sqlite:///") :])
    conn.row_factory = sqlite3.Row
    value = conn.execute(
        """
        SELECT value FROM points p JOIN series s ON s.id = p.series_id
        WHERE s.ref = 'total:CA' AND p.date = '2024-01-01'
        """
    ).fetchone()
    assert value is not None
    assert str(value["value"]) in {"10", "10.0"}
    error = conn.execute("SELECT error FROM fetch_runs").fetchone()[0]
    assert error is None


def test_gsom_rows_average_to_the_state(tmp_path: Path) -> None:
    _target, store = _store(tmp_path)
    payload = {
        "metadata": {"resultset": {"offset": 1, "count": 3, "limit": 1000}},
        "results": [
            {"date": "2024-01-01T00:00:00", "datatype": "TAVG", "station": "GHCND:A", "attributes": ",,", "value": 10},
            {"date": "2024-01-01T00:00:00", "datatype": "TAVG", "station": "GHCND:B", "attributes": ",,", "value": 30},
            {"date": "2024-01-01T00:00:00", "datatype": "PRCP", "station": "GHCND:A", "attributes": ",,", "value": 2},
        ],
    }
    assert ingest_climate(_spec("noaa_climate"), store, payload, state="CA", revision="gsom") == 2
    assert _value(store.conn, "TAVG:CA", "2024-01-01") in {"20", "20.0"}
    assert _value(store.conn, "PRCP:CA", "2024-01-01") in {"2", "2.0"}


def test_search_uses_last_action_fields(tmp_path: Path) -> None:
    _target, store = _store(tmp_path)
    payload = {
        "status": "OK",
        "searchresult": {
            "summary": {"count": 1, "page_total": 1},
            "0": {
                "bill_number": "AB 2",
                "state": "CA",
                "title": "Record keeping",
                "last_action": "Sent to committee",
                "last_action_date": "2024-04-01",
                "url": "https://example.test/bill",
            },
        },
    }
    assert ingest_legiscan(_spec("legiscan"), store, payload) == 1
    row = store.conn.execute("SELECT date, title, body FROM events").fetchone()
    assert row["date"] == "2024-04-01"
    assert row["title"] == "AB 2 Sent to committee"
    assert row["body"] == "Record keeping"


def test_marine_zones_are_not_states(tmp_path: Path) -> None:
    _target, store = _store(tmp_path)
    payload = {
        "features": [
            {
                "properties": {
                    "id": "https://example.test/marine",
                    "event": "Special",
                    "headline": "Waters",
                    "sent": "2024-06-01T00:00:00+00:00",
                    "geocode": {"UGC": ["PZZ350"]},
                }
            },
            {
                "properties": {
                    "id": "https://example.test/coast",
                    "event": "Watch",
                    "headline": "Coast",
                    "sent": "2024-06-02T00:00:00+00:00",
                    "geocode": {"UGC": ["PZZ350", "TXZ001"]},
                }
            },
        ]
    }
    assert ingest_alerts(_spec("noaa_alerts"), store, payload) == 1
    geos = [row["geo"] for row in store.conn.execute("SELECT geo FROM events")]
    assert geos == ["TX"]


def test_page_change_stores_a_hash_and_the_link(tmp_path: Path, monkeypatch) -> None:
    spec = _spec("ups_hazmat")
    secret = b"<html><body>SECRET_PAGE_TEXT_42</body></html>"
    changed = b"<html><body>SECRET_PAGE_TEXT_99</body></html>"
    bodies = [secret, secret, changed]

    def opener(request, timeout=60):
        assert request.get_header("User-agent") == USER_AGENT
        assert "Tervory" in USER_AGENT
        assert "http" in USER_AGENT
        return FakeResponse(bodies.pop(0))

    monkeypatch.setattr("urllib.request.urlopen", opener)
    target = _db(tmp_path)
    args = ["run", "--live", "--source", spec.id, "--engine", "ffl", "--db", target]
    assert main(args) == 0
    assert main(args) == 0
    assert main(args) == 0
    conn = sqlite3.connect(target[len("sqlite:///") :])
    conn.row_factory = sqlite3.Row
    events = conn.execute(
        "SELECT kind, body, url, title FROM events WHERE source_id = ? ORDER BY rowid",
        (spec.id,),
    ).fetchall()
    assert [row["kind"] for row in events] == ["changed", "changed"]
    assert events[0]["body"] == hashlib.sha256(secret).hexdigest()
    assert events[1]["body"] == hashlib.sha256(changed).hexdigest()
    assert events[0]["url"] == spec.url
    assert events[0]["title"] == "changed"
    dump = " ".join("" if value is None else str(value) for row in conn.execute("SELECT * FROM events") for value in row)
    assert "SECRET_PAGE_TEXT_42" not in dump
    assert "SECRET_PAGE_TEXT_99" not in dump


def test_terms_block_skips_the_network(tmp_path: Path, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    target = _db(tmp_path)
    assert main(["run", "--live", "--source", "fred_tsifrght", "--engine", "ffl", "--db", target]) == 0
    conn = sqlite3.connect(target[len("sqlite:///") :])
    error = conn.execute("SELECT error FROM fetch_runs").fetchone()[0]
    assert error == "blocked by terms"


def test_key_never_appears_in_an_error(monkeypatch) -> None:
    secret = "super-secret-value"
    url = "https://api.census.gov/data/2023/acs/acs5?get=NAME&key=" + secret

    def opener(request, timeout=60):
        raise urllib.error.HTTPError(request.full_url, 503, secret, None, None)

    client = PoliteClient(delay=0, backoff=0, retries=3, opener=opener)
    with pytest.raises(RuntimeError) as caught:
        client.get(url)
    message = str(caught.value)
    assert secret not in message
    assert "api.census.gov" in message
    assert "503" in message
    assert secret not in safe_failure(url, RuntimeError(secret))


def test_retries_three_times_with_backoff() -> None:
    slept: list[float] = []
    calls = {"n": 0}

    def opener(request, timeout=60):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.URLError("down")
        return FakeResponse(b"ok")

    client = PoliteClient(delay=0, backoff=1, retries=3, opener=opener, sleep=slept.append)
    assert client.get_text("https://example.test/a") == "ok"
    assert calls["n"] == 3
    assert slept == [1, 2]


def test_same_host_waits_between_requests() -> None:
    slept: list[float] = []

    def opener(request, timeout=60):
        return FakeResponse(b"ok")

    client = PoliteClient(
        delay=2,
        backoff=0,
        retries=1,
        opener=opener,
        sleep=slept.append,
        clock=lambda: 0,
    )
    assert client.get_text("https://example.test/a") == "ok"
    assert slept == []
    assert client.get_text("https://example.test/b") == "ok"
    assert slept == [2]
