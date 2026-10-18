"""Feed keys: on when set, off when missing. No live network."""

from __future__ import annotations

import sqlite3
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

from feeds.cli import main  # noqa: E402
from feeds.db import apply_schema, connect  # noqa: E402
from feeds.keys import KEY_NAMES, redact  # noqa: E402
from feeds.live import PoliteClient  # noqa: E402
from feeds.runner import format_status, run, scheduled, status  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "feeds" / "eia" / "diesel.json"
SECRET = "dummy-feed-key"
KEYED_OFF = (
    "census_population",
    "census_trade",
    "legiscan",
    "eia_diesel",
    "noaa_climate",
    "fred_tsifrght",
    "fred_pcoppusdm",
)
STAYS_ON = (
    "listing_counts",
    "check_counts",
    "federal_register",
    "noaa_alerts",
    "world_bank_commodities",
    "ups_hazmat",
)
BLOCKED_HOSTS = (
    "api.census.gov",
    "api.legiscan.com",
    "api.eia.gov",
    "www.ncei.noaa.gov",
    "api.stlouisfed.org",
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


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in KEY_NAMES:
        monkeypatch.delenv(name, raising=False)


def _connect(target: str) -> sqlite3.Connection:
    conn = sqlite3.connect(target[len("sqlite:///") :])
    conn.row_factory = sqlite3.Row
    return conn


def test_key_names_are_wired_and_empty_in_the_example() -> None:
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    compose = (ROOT / "agents" / "market_lab" / "docker-compose.yml").read_text(encoding="utf-8")
    for name in KEY_NAMES:
        assert f"{name}=" in example
        assert f"{name}: ${{{name}:-}}" in compose
        line = next(item for item in example.splitlines() if item.startswith(f"{name}="))
        assert line.split("=", 1)[1].strip().startswith("#") or line.split("=", 1)[1].strip() == ""


def test_missing_keys_are_not_scheduled(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    chosen = set(scheduled("ffl"))
    assert set(KEYED_OFF).isdisjoint(chosen)
    assert set(STAYS_ON) <= chosen
    monkeypatch.setenv("CENSUS_API_KEY", SECRET)
    chosen = set(scheduled("ffl"))
    assert "census_population" in chosen
    assert "census_trade" in chosen
    assert "eia_diesel" not in chosen
    assert "noaa_alerts" in chosen


def test_status_says_off_needs_key_and_a_live_pass_does_not_call(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    target = _db(tmp_path)
    rows = status(target, engine="ffl")
    by_id = {row["id"]: row for row in rows}
    for source_id in KEYED_OFF:
        assert by_id[source_id]["state"] == "off"
        assert by_id[source_id]["enabled"] == 0
        assert by_id[source_id]["key_set"] is False
        assert str(by_id[source_id]["note"]).startswith("needs key ")
    assert by_id["eia_diesel"]["note"] == "needs key EIA_API_KEY"
    assert by_id["fred_tsifrght"]["note"] == "needs key FRED_API_KEY"
    assert by_id["fred_tsifrght"]["mode"] == "linked"
    assert by_id["noaa_alerts"]["state"] == "on"
    assert by_id["noaa_alerts"]["note"] == ""
    text = format_status(rows)
    assert "state=off" in text
    assert "needs key EIA_API_KEY" in text
    assert "key_set=no" in text
    assert SECRET not in text

    hosts: list[str] = []

    def opener(request, timeout=60):
        hosts.append(urlsplit(request.full_url).hostname or "")
        return FakeResponse(b"{}")

    run(
        target,
        engine="ffl",
        live=True,
        client=PoliteClient(delay=0, backoff=0, retries=1, opener=opener),
    )
    assert set(BLOCKED_HOSTS).isdisjoint(hosts)
    conn = _connect(target)
    called = {
        row["source_id"]
        for row in conn.execute("SELECT source_id, error FROM fetch_runs")
        if row["source_id"] in KEYED_OFF
    }
    assert called == set()
    report = format_status(status(target, engine="ffl"))
    assert "needs key EIA_API_KEY" in report
    assert "Traceback" not in report
    assert SECRET not in report


def test_keyed_feed_returns_the_source_numbers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("EIA_API_KEY", SECRET)
    target = _db(tmp_path)
    urls: list[str] = []

    def opener(request, timeout=60):
        urls.append(request.full_url)
        return FakeResponse(FIXTURE.read_bytes())

    monkeypatch.setattr("urllib.request.urlopen", opener)
    assert main(["run", "--live", "--source", "eia_diesel", "--engine", "ffl", "--db", target]) == 0
    assert urls and all(SECRET in url and "api_key=" in url for url in urls)
    conn = _connect(target)
    points = conn.execute(
        """
        SELECT p.date, p.value
        FROM points p JOIN series s ON s.id = p.series_id
        WHERE s.source_id = 'eia_diesel'
        ORDER BY p.date
        """
    ).fetchall()
    assert [(row["date"], Decimal(str(row["value"]))) for row in points] == [
        ("2024-01-08", Decimal("3.828")),
        ("2024-01-15", Decimal("3.860")),
    ]
    error = conn.execute(
        "SELECT error FROM fetch_runs WHERE source_id = 'eia_diesel'"
    ).fetchone()[0]
    assert error is None
    dump = " ".join(
        "" if value is None else str(value)
        for row in conn.execute("SELECT * FROM feed_sources")
        for value in row
    )
    dump += " ".join(
        "" if value is None else str(value)
        for row in conn.execute("SELECT * FROM fetch_runs")
        for value in row
    )
    assert SECRET not in dump
    text = format_status(status(target, engine="ffl"))
    assert "eia_diesel" in text
    assert "state=on" in text
    assert "key=EIA_API_KEY" in text
    assert "key_set=yes" in text
    assert SECRET not in text


def test_named_source_without_a_key_stays_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("EIA_API_KEY", "   ")

    def opener(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("urllib.request.urlopen", opener)
    target = _db(tmp_path)
    assert main(["run", "--live", "--source", "eia_diesel", "--engine", "ffl", "--db", target]) == 0
    conn = _connect(target)
    assert conn.execute("SELECT COUNT(*) FROM fetch_runs").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM points").fetchone()[0] == 0
    row = conn.execute("SELECT enabled, key_name FROM feed_sources WHERE id = 'eia_diesel'").fetchone()
    assert row["enabled"] == 0
    assert row["key_name"] == "EIA_API_KEY"
    captured = capsys.readouterr()
    assert "state=off" in captured.out
    assert "needs key EIA_API_KEY" in captured.out
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err


def test_stored_error_does_not_keep_the_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("EIA_API_KEY", SECRET)

    def boom(*_args, **_kwargs):
        raise RuntimeError(f"failed https://api.eia.gov/v2/?api_key={SECRET} {SECRET}")

    monkeypatch.setattr("feeds.runner.fetch_source", boom)
    target = _db(tmp_path)
    run(target, engine="ffl", source="eia_diesel", live=True)
    conn = _connect(target)
    error = conn.execute("SELECT error FROM fetch_runs").fetchone()[0]
    assert SECRET not in error
    assert "api_key=" not in error
    assert "api.eia.gov" in error
    assert redact(f"token={SECRET} and {SECRET}") == "token=REDACTED and REDACTED"


def test_key_columns_arrive_on_an_older_table(tmp_path: Path) -> None:
    target = _db(tmp_path)
    conn = connect(target)
    conn.execute(
        """
        CREATE TABLE market_lab.feed_sources (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            url TEXT NOT NULL,
            licence TEXT NOT NULL,
            terms_checked_at TEXT NOT NULL,
            cadence TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    apply_schema(conn)
    apply_schema(conn)
    columns = {
        row[1]
        for row in conn.execute("PRAGMA market_lab.table_info(feed_sources)")
    }
    assert {"key_name", "key_required"} <= columns
