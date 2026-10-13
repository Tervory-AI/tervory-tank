"""Licence gate, no network, and no industry words outside the engine."""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

from feeds.catalog import sources  # noqa: E402
from feeds.licence import LicenceBlocked, require_copy  # noqa: E402
from feeds.live import census_population_urls, federal_register_url, legiscan_urls  # noqa: E402

BANNED = re.compile(
    r"\b(firearms?|ammunition|ammo|handguns?|long_guns?|rifles?|pistols?|shotguns?|primers?|propellants?|nics)\b",
    re.IGNORECASE,
)


def test_link_only_source_cannot_copy() -> None:
    fred = next(item for item in sources("ffl") if item.id == "fred_tsifrght")
    try:
        require_copy(fred)
    except LicenceBlocked:
        return
    raise AssertionError("FRED copy was allowed")


def test_census_and_legiscan_urls_are_shaped_without_a_request() -> None:
    census = census_population_urls("secret-key", [2023])
    assert any("for=state:*" in url and "secret-key" in url for _, url in census)
    assert any("for=county:*" in url for _, url in census)
    assert census[0][1].startswith("https://api.census.gov/")
    bills = legiscan_urls("secret-key", ["topic"], states=("CA",))
    assert bills[0][1].startswith("https://api.legiscan.com/?")
    assert "op=getSearch" in bills[0][1]
    assert "state=CA" in bills[0][1]
    register = federal_register_url(["example-agency"])
    assert register.startswith("https://www.federalregister.gov/api/v1/documents.json?")
    assert "example-agency" in register


def test_backfill_does_not_open_a_socket(tmp_path: Path, monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise AssertionError("network")

    monkeypatch.setattr("urllib.request.urlopen", boom)
    from feeds.cli import main

    target = "sqlite:///" + str(tmp_path / "feeds.sqlite")
    fixtures = str(ROOT / "tests" / "fixtures" / "feeds")
    assert main(["run", "--backfill", "--fixtures", fixtures, "--db", target, "--engine", "ffl"]) == 0


def test_runner_reads_only_the_fixture_directory() -> None:
    from feeds.runner import fixture_roots

    roots = fixture_roots("/tmp/only-this")
    assert [path.as_posix() for path in roots] == ["/tmp/only-this"]
    packaged = ROOT / "agents" / "market_lab" / "feeds" / "engines" / "ffl" / "fixtures"
    assert not packaged.exists()


def test_failed_source_keeps_no_partial_rows(tmp_path: Path) -> None:
    from feeds import adapters
    from feeds.cli import main

    real = adapters.ADAPTERS["eia"]

    def boom(source, reader, store, *, backfill):
        store.ensure_series(source.id, "bad", "bad", "x", "national", "US", "weekly")
        store.put_point(f"{source.id}:bad", "2024-01-01", 1, "v1")
        raise RuntimeError("boom")

    adapters.ADAPTERS["eia"] = boom
    target = tmp_path / "feeds.sqlite"
    try:
        assert main([
            "run",
            "--source",
            "eia_diesel",
            "--backfill",
            "--fixtures",
            str(ROOT / "tests" / "fixtures" / "feeds"),
            "--db",
            "sqlite:///" + str(target),
            "--engine",
            "ffl",
        ]) == 0
    finally:
        adapters.ADAPTERS["eia"] = real
    conn = sqlite3.connect(target)
    assert conn.execute("SELECT COUNT(*) FROM points").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM series").fetchone()[0] == 0
    error = conn.execute("SELECT error FROM fetch_runs").fetchone()[0]
    assert "boom" in error
    assert conn.execute("SELECT COUNT(*) FROM feed_sources").fetchone()[0] == 1


def test_industry_words_stay_in_the_engine() -> None:
    roots = [ROOT / "agents" / "market_lab" / "feeds", ROOT / "tests"]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if "engines/ffl" in path.as_posix():
                continue
            if path.suffix not in {".py", ".sql", ".json", ".csv", ".html", ".tsv", ".md"}:
                continue
            if path.name == "test_feeds_boundaries.py":
                continue
            if path.name.startswith("test_") and "feeds" not in path.name:
                continue
            text = path.read_text(encoding="utf-8")
            if BANNED.search(text):
                offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []
