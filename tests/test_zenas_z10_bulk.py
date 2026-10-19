"""Z10: CourtListener back catalogue from the quarterly bulk files.

Saved slices of the 2026-09-30 bulk CSVs. No live network. No API key in a
URL, a header on the bulk read, or a log.

Every opinion row is that case's own row from the opinions file, in opinion
id order. Robinson Quality Constructors (175448) and Callaway (2756371) come
before the commercial keeps. Robinson's row has text and a citation and no
commercial words. Callaway's row has text and the citations file has no row
for it, so the load counts it as no text. Regional Care (2756657) and Sheriff
(5243701) are the commercial keeps. Njie's own opinion says "customs", which
would keep it, and Sexton's own opinion says "firearm", so neither is the
not-commercial case.
"""

from __future__ import annotations

import asyncio
import bz2
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.zenas.pool.adapters.courtlistener_bulk import (  # noqa: E402
    BulkState,
    be_polite,
    bulk_cap,
    choose_snapshot,
    iter_csv_bytes,
    load_bulk,
    progress_line,
)
from agents.zenas.pool.catalogue import CATALOGUE  # noqa: E402
from agents.zenas.pool.ingest import ingest_snapshot  # noqa: E402
from agents.zenas.pool.licence import FetchNotConfigured  # noqa: E402
from agents.zenas.pool.nightly import courtlistener_night  # noqa: E402
from agents.zenas.pool.store import MemoryStore, PostgresStore  # noqa: E402

BULK = ROOT / "tests" / "fixtures" / "courtlistener" / "bulk"
DAY = "2026-09-30"
ON = date(2026, 10, 19)
WHEN = datetime(2026, 10, 19, tzinfo=timezone.utc)
NS = "http://s3.amazonaws.com/doc/2006-03-01/"


def _source():
    return next(item for item in CATALOGUE if item.source_id == "courtlistener")


def _files() -> dict[str, bytes]:
    files = {
        f"bulk-data/courts-{DAY}.csv.bz2": bz2.compress((BULK / f"courts-{DAY}.csv").read_bytes()),
        f"bulk-data/dockets-{DAY}.csv": (BULK / f"dockets-{DAY}.csv").read_bytes(),
        f"bulk-data/opinion-clusters-{DAY}.csv": (BULK / f"opinion-clusters-{DAY}.csv").read_bytes(),
        f"bulk-data/opinions-{DAY}.csv": (BULK / f"opinions-{DAY}.csv").read_bytes(),
        f"bulk-data/citations-{DAY}.csv": (BULK / f"citations-{DAY}.csv").read_bytes(),
        f"bulk-data/schema-{DAY}.sql": (BULK / f"schema-{DAY}.sql").read_bytes(),
    }
    # An older snapshot is listed and must not be chosen.
    files["bulk-data/courts-2026-06-30.csv"] = b"id\nold\n"
    return files


def _listing(keys: list[str]) -> bytes:
    contents = "".join(f"<Contents><Key>{key}</Key></Contents>" for key in keys)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<ListBucketResult xmlns="{NS}"><IsTruncated>false</IsTruncated>'
        f"{contents}</ListBucketResult>"
    )
    return xml.encode()


def _bulk_get(calls: list[tuple[str, dict]]):
    files = _files()

    async def get(url: str, headers: dict) -> bytes:
        calls.append((url, dict(headers)))
        assert "token=" not in url.lower()
        assert "api_key=" not in url.lower()
        assert "Authorization" not in headers
        if "list-type=" in url:
            return _listing(list(files))
        for key, payload in files.items():
            if key in url:
                return payload
        raise AssertionError(url)

    return get


def _citations(blobs: list[bytes]) -> set[str]:
    found: set[str] = set()
    for blob in blobs:
        payload = json.loads(blob)
        for row in payload["results"]:
            found.add(row["citations"][0])
    return found


def test_latest_snapshot_date_is_preferred():
    keys = list(_files())
    chosen = choose_snapshot(keys)
    assert chosen is not None
    assert chosen.day == DAY
    assert set(chosen.files) >= {"courts", "dockets", "clusters", "opinions", "schema"}


def test_bz2_csv_is_read_from_memory_not_a_path():
    raw = bz2.compress(b"id,court_id\n1,ca9\n")
    rows = list(iter_csv_bytes(raw, "courts.csv.bz2"))
    assert rows == [["id", "court_id"], ["1", "ca9"]]


def test_cap_defaults_to_50000_and_the_read_is_low_priority(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ZENAS_CL_BULK_MAX", raising=False)
    assert bulk_cap() == 50_000
    monkeypatch.setenv("ZENAS_CL_BULK_MAX", "3")
    assert bulk_cap() == 3
    calls: list[int] = []
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr("agents.zenas.pool.adapters.courtlistener_bulk.os.nice", lambda level: calls.append(level))
    import agents.zenas.pool.adapters.courtlistener_bulk as bulk

    bulk._NICE_DONE = False
    be_polite()
    assert calls == [19]
    bulk._NICE_DONE = False


def test_fixture_keeps_commercial_cases_and_drops_the_rest(monkeypatch: pytest.MonkeyPatch):
    asyncio.run(_fixture(monkeypatch))


async def _fixture(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ZENAS_CL_BULK_MAX", "50")
    calls: list[tuple[str, dict]] = []
    result = await load_bulk(_bulk_get(calls), state=BulkState())
    assert result.snapshot == DAY
    assert result.cursor == f"cl-bulk:{DAY}:done"
    assert _citations(result.blobs) == {"175 A.D. 882", "586 F. App'x 297"}
    kept = [row for blob in result.blobs for row in json.loads(blob)["results"]]
    by_cite = {row["citations"][0]: row for row in kept}
    sheriff = by_cite["175 A.D. 882"]
    assert sheriff["case_name"].startswith("Sheriff")
    assert "insurance" in sheriff["case_name"].lower()
    assert sheriff["plain_text"]
    regional = by_cite["586 F. App'x 297"]
    assert regional["docket_number"] == "12-16538"
    assert regional["court_id"] == "ca9"
    names = " ".join(row["case_name"] for row in kept)
    assert "Walker" not in names
    assert "Samuels" not in names
    assert "John Does" not in names
    assert "Njie" not in names
    assert "Sexton" not in names
    assert "Callaway" not in names
    assert "Robinson" not in names
    assert result.skips["criminal"] >= 2
    assert result.skips["not-appellate"] >= 1
    assert result.skips["not-commercial"] >= 1
    assert result.skips["no-text"] >= 1
    line = progress_line(result.snapshot, result.file_label, result.rows_read, result.cases_kept, result.skips)
    assert line.startswith(f"snapshot {DAY}; file opinions; rows read ")
    assert "cases kept 2" in line
    assert "skipped not our court" in line
    assert "criminal" in line and "not commercial" in line and "no text" in line
    assert all("s3-us-west-2.amazonaws.com" in url for url, _headers in calls)
    assert not any(url.startswith("https://www.courtlistener.com/api/") for url, _headers in calls)


def test_a_stopped_run_resumes_without_duplicates(monkeypatch: pytest.MonkeyPatch):
    asyncio.run(_resume(monkeypatch))


async def _resume(monkeypatch: pytest.MonkeyPatch):
    # The cap counts opinions that have text. Robinson and Callaway are read
    # before Regional Care, so the first commercial case is the third.
    monkeypatch.setenv("ZENAS_CL_BULK_MAX", "3")
    first = await load_bulk(_bulk_get([]), state=BulkState())
    assert _citations(first.blobs) == {"586 F. App'x 297"}
    assert first.cursor == f"cl-bulk:{DAY}:opinions:2756657"
    # A new process: empty memory, same cursor. The opinion already stored is not emitted.
    second = await load_bulk(_bulk_get([]), resume=first.cursor, state=BulkState())
    assert "586 F. App'x 297" not in _citations(second.blobs)
    assert "175 A.D. 882" in _citations(second.blobs)
    source = _source()
    store = MemoryStore(home_region="us-east")
    await ingest_snapshot(store, source, first.blobs, on=ON, region="us-east")
    await ingest_snapshot(store, source, second.blobs, on=ON, region="us-east")
    assert len(store.docs) == 2
    again = await load_bulk(_bulk_get([]), state=BulkState())
    await ingest_snapshot(store, source, again.blobs, on=ON, region="us-east")
    assert len(store.docs) == 2


def test_api_updates_ask_only_for_dates_after_the_snapshot(monkeypatch: pytest.MonkeyPatch):
    asyncio.run(_api_after(monkeypatch))


async def _api_after(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ZENAS_CL_BULK_MAX", "50")
    monkeypatch.setenv("COURTLISTENER_MIN_INTERVAL", "0")
    monkeypatch.setenv("COURTLISTENER_MAX_PAGES", "2")
    marker = "marker-" + ("d" * 16)
    monkeypatch.setenv("COURTLISTENER_API_TOKEN", marker)
    calls: list[tuple[str, dict]] = []
    files = _files()

    async def get(url: str, headers: dict) -> bytes:
        calls.append((url, dict(headers)))
        assert marker not in url
        assert "token=" not in url.lower()
        if "list-type=" in url or "s3-us-west-2.amazonaws.com" in url:
            assert "Authorization" not in headers
            if "list-type=" in url:
                return _listing(list(files))
            for key, payload in files.items():
                if key in url:
                    return payload
            raise AssertionError(url)
        assert headers.get("Authorization") == f"Token {marker}"
        assert f"filed_after={DAY}" in url
        assert "filed_before" not in url
        return b'{"results":[],"next":null}'

    source = _source()
    store = MemoryStore(home_region="us-east")
    await courtlistener_night(
        store,
        source,
        on=ON,
        when=WHEN,
        http_get=get,
        embedder=None,
        index=None,
        region="us-east",
    )
    api_calls = [url for url, _headers in calls if "/api/" in url]
    assert api_calls
    assert all(f"filed_after={DAY}" in url for url in api_calls)
    assert all(marker not in url for url in api_calls)
    row = (await store.status_rows())[0]
    assert row["last_status"] == "ok"
    assert f"snapshot {DAY}" in row["detail"]
    assert "cases kept" in row["detail"]
    dumped = json.dumps(await store.status_rows())
    assert marker not in dumped


def test_bulk_refuses_the_za_box(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("TANK_REGION", "za")

    async def get(url, headers):
        raise AssertionError("za must not read the bulk files")

    with pytest.raises(FetchNotConfigured, match="US box"):
        asyncio.run(load_bulk(get, state=BulkState()))


def test_progress_line_is_what_the_feeds_page_shows():
    board = (ROOT / "workspace/app/zenas/feeds/board.tsx").read_text()
    assert 'row.id === "courtlistener"' in board
    assert 'row.detail.includes("snapshot ")' in board
    line = progress_line(DAY, "opinions", 40, 2, {"not-appellate": 1, "criminal": 2, "not-commercial": 1, "no-text": 2})
    assert line == (
        f"snapshot {DAY}; file opinions; rows read 40; cases kept 2; "
        "skipped not our court 1, criminal 2, not commercial 1, no text 2"
    )


def _database_url() -> str:
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL", "").strip()
    if url:
        return url
    if os.environ.get("GITHUB_ACTIONS"):
        pytest.fail("POOL_SCHEMA_DATABASE_URL is not set")
    pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    return ""


def test_schema_applies_on_empty_again_and_over_main_with_agent_roles():
    asyncio.run(_schema())


async def _schema() -> None:
    import asyncpg

    sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
    from agents.zenas.pool.store import schema_statements
    from chassis.roles import statements_for

    main = (ROOT / "tests/fixtures/zenas_pool_schema_main.sql").read_text(encoding="utf-8")
    conn = await asyncpg.connect(_database_url())
    try:
        await conn.execute("DROP SCHEMA IF EXISTS zenas_pool CASCADE")
        store = PostgresStore(conn, home_region="us-east")
        await store.apply_schema()
        await store.apply_schema()
        names = await _tables(conn)
        assert {"cl_bulk_files", "cl_bulk_ids", "sources", "checkpoints"} <= names

        await conn.execute("DROP SCHEMA IF EXISTS zenas_pool CASCADE")
        for statement in statements_for("zenas", "z10-schema-password"):
            await conn.execute(statement)
        for statement in _sql_statements(main):
            await conn.execute(statement)
        await conn.execute(
            """
            INSERT INTO zenas_pool.sources (
                source_id, name, region, jurisdiction, licence, terms, bulk_use, store_full_text
            ) VALUES (
                'courtlistener', 'CourtListener', 'us-east', 'us',
                'Public domain.', 'Bulk files are free of known copyright restrictions.', 'allowed', true
            )
            """
        )
        await store.apply_schema()
        await store.apply_schema()
        names = await _tables(conn)
        assert {"cl_bulk_files", "cl_bulk_ids"} <= names
        kept = await conn.fetchval("SELECT count(*) FROM zenas_pool.sources WHERE source_id = 'courtlistener'")
        assert kept == 1
        owner = await conn.fetchval(
            """
            SELECT r.rolname
            FROM pg_namespace n
            JOIN pg_roles r ON r.oid = n.nspowner
            WHERE n.nspname = 'zenas_pool'
            """
        )
        assert owner == "agent_zenas"
        assert any("cl_bulk_files" in statement for statement in schema_statements())
    finally:
        await conn.execute("DROP SCHEMA IF EXISTS zenas_pool CASCADE")
        await conn.close()


async def _tables(conn) -> set[str]:
    rows = await conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'zenas_pool'
        """
    )
    return {row["table_name"] for row in rows}


def _sql_statements(text: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.endswith(";"):
            parts.append("\n".join(buf).strip())
            buf = []
    if buf:
        parts.append("\n".join(buf).strip())
    return parts
