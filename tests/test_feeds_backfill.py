"""Fixture backfill for Market Lab feeds. No database server and no network."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

FIXTURES = ROOT / "tests" / "fixtures" / "feeds"

from feeds.cli import main  # noqa: E402
from feeds.db import apply_schema, connect  # noqa: E402


def _db(tmp_path: Path) -> str:
    return "sqlite:///" + str(tmp_path / "feeds.sqlite")


def _run(tmp_path: Path) -> str:
    target = _db(tmp_path)
    assert main(["run", "--backfill", "--fixtures", str(FIXTURES), "--db", target]) == 0
    return target


def _connect(target: str) -> sqlite3.Connection:
    path = target[len("sqlite:///") :]
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _dump(conn: sqlite3.Connection) -> str:
    chunks: list[str] = []
    for table in ("feed_sources", "series", "points", "events", "fetch_runs"):
        for row in conn.execute(f"SELECT * FROM {table}"):
            chunks.append(" ".join("" if value is None else str(value) for value in row))
    return "\n".join(chunks)


def _count(conn: sqlite3.Connection, sql: str, params: tuple[object, ...] = ()) -> int:
    return int(conn.execute(sql, params).fetchone()[0])


def test_backfill_fills_points_and_events(tmp_path: Path) -> None:
    conn = _connect(_run(tmp_path))
    errors = conn.execute(
        "SELECT source_id, error FROM fetch_runs WHERE error IS NOT NULL"
    ).fetchall()
    assert errors == []
    assert _count(conn, "SELECT COUNT(*) FROM points") == 43
    assert _count(conn, "SELECT COUNT(*) FROM events") == 5
    assert _count(conn, "SELECT COUNT(*) FROM points p JOIN series s ON s.id = p.series_id WHERE s.source_id = 'listing_counts'") == 18
    assert _count(conn, "SELECT COUNT(*) FROM points p JOIN series s ON s.id = p.series_id WHERE s.source_id = 'census_trade'") == 2
    assert _count(conn, "SELECT COUNT(*) FROM events WHERE source_id = 'federal_register'") == 1
    assert _count(conn, "SELECT COUNT(*) FROM events WHERE source_id = 'ecfr'") == 2
    assert _count(conn, "SELECT COUNT(*) FROM events WHERE source_id = 'legiscan'") == 1
    assert _count(conn, "SELECT COUNT(*) FROM events WHERE source_id = 'noaa_alerts' AND geo = 'CA'") == 1
    texas_new = conn.execute(
        """
        SELECT value FROM points p JOIN series s ON s.id = p.series_id
        WHERE s.ref = 'new:state:TX' AND p.date = '2024-02-01'
        """
    ).fetchone()["value"]
    california_dropped = conn.execute(
        """
        SELECT value FROM points p JOIN series s ON s.id = p.series_id
        WHERE s.ref = 'dropped:state:CA' AND p.date = '2024-02-01'
        """
    ).fetchone()["value"]
    assert str(texas_new) in {"1", "1.0"}
    assert str(california_dropped) in {"1", "1.0"}
    california_new = conn.execute(
        """
        SELECT value FROM points p JOIN series s ON s.id = p.series_id
        WHERE s.ref = 'new:state:CA' AND p.date = '2024-02-01'
        """
    ).fetchone()["value"]
    assert str(california_new) in {"0", "0.0"}
    titles = [row["title"] for row in conn.execute("SELECT title FROM events WHERE source_id = 'ecfr'")]
    assert titles == ["49 CFR 172", "49 CFR 173"] or set(titles) == {"49 CFR 172", "49 CFR 173"}


def test_rerun_adds_nothing_and_keeps_revisions(tmp_path: Path) -> None:
    target = _run(tmp_path)
    conn = _connect(target)
    before = _count(conn, "SELECT COUNT(*) FROM points")
    population = {
        (row["revision"], str(row["value"]))
        for row in conn.execute(
            """
            SELECT p.revision, p.value FROM points p
            JOIN series s ON s.id = p.series_id
            WHERE s.ref = 'population:state:06'
            """
        )
    }
    assert population == {("acs-v1", "100"), ("acs-v2", "110")}
    conn.close()
    assert main(["run", "--backfill", "--fixtures", str(FIXTURES), "--db", target]) == 0
    conn = _connect(target)
    assert _count(conn, "SELECT COUNT(*) FROM points") == before
    assert _count(conn, "SELECT COUNT(*) FROM events") == 5
    kept = {
        (row["revision"], str(row["value"]))
        for row in conn.execute(
            """
            SELECT p.revision, p.value FROM points p
            JOIN series s ON s.id = p.series_id
            WHERE s.ref = 'population:state:06'
            """
        )
    }
    assert kept == population


def test_status_lists_licence_and_linked_sources_store_nothing(tmp_path: Path) -> None:
    target = _run(tmp_path)
    assert main(["status", "--db", target]) == 0
    conn = _connect(target)
    text = _dump(conn)
    assert "424242" not in text
    assert "DO_NOT_COPY_CARRIER_SENTINEL" not in text
    linked = conn.execute(
        "SELECT id, licence FROM feed_sources WHERE licence LIKE 'Linked only.%'"
    ).fetchall()
    assert {row["id"] for row in linked} >= {
        "fred_tsifrght",
        "port_long_beach",
        "port_nynj",
        "ups_hazmat",
        "season_ca",
    }
    for row in linked:
        points = _count(
            conn,
            "SELECT COUNT(*) FROM points p JOIN series s ON s.id = p.series_id WHERE s.source_id = ?",
            (row["id"],),
        )
        events = _count(conn, "SELECT COUNT(*) FROM events WHERE source_id = ?", (row["id"],))
        assert points == 0
        assert events == 0
    assert "public domain" in text
    assert "Creative Commons Attribution 4.0" in text
    assert "2026-10-13" in text


def test_schema_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "schema.sqlite"
    conn = connect("sqlite:///" + str(path))
    apply_schema(conn)
    apply_schema(conn)
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM market_lab.sqlite_master WHERE type = 'table'")
    }
    assert {"feed_sources", "series", "points", "events", "fetch_runs"} <= tables
    conn.close()
    plain = sqlite3.connect(path)
    stored = {row[0] for row in plain.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    assert {"feed_sources", "series", "points", "events", "fetch_runs"} <= stored
    text = (ROOT / "agents" / "market_lab" / "feeds" / "schema.sql").read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS market_lab" in text
    assert "market_lab.feed_sources" in text
