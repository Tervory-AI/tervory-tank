"""Market Lab box. Fixtures only: no database server and no network."""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import re
import sys
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

from chassis.cron import is_due  # noqa: E402
from core.jobs import perform_opportunities, perform_refresh, perform_research, perform_resolve  # noqa: E402
from core.ledger import SCHEMA, MemoryLedger, schema_sql  # noqa: E402
from core.pure import (  # noqa: E402
    correct_prediction,
    gap_score,
    make_prediction,
    resolve_prediction,
    series_fetch,
    surge_detect,
)

FIXTURES = ROOT / "tests" / "fixtures" / "feeds"
TENANT = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
NOW = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
BANNED = re.compile(
    r"\b(firearms?|ammunition|ammo|handguns?|rifles?|pistols?|shotguns?|primers?|propellants?|nics|atf)\b",
    re.IGNORECASE,
)
COMPONENTS = ("demand_idx", "supply_idx", "gap", "saturation", "reachability", "trend", "rank")

AREAS = [
    {
        "area": "thin",
        "segment": "retail",
        "population": 100000,
        "demand": [{"date": "2026-01-01", "value": 100}],
        "supply": [{"date": "2026-01-01", "value": 10}],
        "competitors": 1,
        "reachable": 80,
        "targets": 100,
        "fit": 1,
        "size": 100,
    },
    {
        "area": "hot",
        "segment": "retail",
        "population": 100000,
        "demand": [{"date": "2026-01-01", "value": 40}],
        "supply": [{"date": "2026-01-01", "value": 80}],
        "competitors": 10,
        "reachable": 50,
        "targets": 100,
        "fit": 0.4,
        "size": 400,
    },
]


def _areas() -> list[dict]:
    return [
        {
            "area": "thin",
            "segment": "retail",
            "population": 100000,
            "demand": [{"date": "2025-01-01", "value": 40}, {"date": "2026-01-01", "value": 100}],
            "supply": [{"date": "2025-01-01", "value": 10}, {"date": "2026-01-01", "value": 10}],
            "competitors": 1,
            "reachable": 80,
            "targets": 100,
        },
        {
            "area": "hot",
            "segment": "retail",
            "population": 100000,
            "demand": [{"date": "2025-01-01", "value": 100}, {"date": "2026-01-01", "value": 40}],
            "supply": [{"date": "2025-01-01", "value": 80}, {"date": "2026-01-01", "value": 80}],
            "competitors": 10,
            "reachable": 50,
            "targets": 100,
        },
    ]


def test_gap_score_ranks_thin_supply_above_a_hot_spot() -> None:
    scored = gap_score({"areas": AREAS})
    assert scored["top_area"] == "thin"
    assert scored["hot_area"] == "hot"
    assert scored["top_recommendation"] == "increase"
    assert scored["hot_recommendation"] == "reduce"
    thin, hot = scored["ranked"]
    assert thin["rank"] == 1 and hot["rank"] == 2
    assert thin["gap"] > hot["gap"]
    for row in scored["ranked"]:
        for key in COMPONENTS:
            assert key in row
        assert set(row["trend"]) == {"m3", "m6", "m12"}
        assert "recommendation" in row
    assert thin["demand_idx"] == 100.0
    assert thin["supply_idx"] == 12.5
    assert thin["gap"] == 87.5
    assert thin["saturation"] == 0.1125
    assert thin["reachability"] == 0.8
    assert thin["per_capita"] is True


def test_gap_trend_over_twelve_months_is_visible() -> None:
    thin = next(row for row in gap_score({"areas": _areas()})["ranked"] if row["area"] == "thin")
    assert thin["trend"]["m12"] == 60.0
    assert thin["recommendation"] == "increase"


def test_surge_in_fixture_points_raises_an_event() -> None:
    points = [{"date": f"2024-{month:02d}-01", "value": 10} for month in range(1, 7)]
    points.append({"date": "2024-07-01", "value": 40})
    events = surge_detect({"points": points})["events"]
    assert events == [{"date": "2024-07-01", "kind": "surge", "size": 3.0, "z": None, "pct": 3.0}]


def test_xlsx_upload_reads_dated_points() -> None:
    blob = _xlsx([["date", "value"], ["2024-05-01", "8"], ["2024-06-01", "9"]])
    fetched = series_fetch(
        {
            "adapter": "xlsx",
            "series_id": "upload:sheet",
            "source": "upload",
            "fetched_at": "2026-10-14T00:00:00+00:00",
            "xlsx": base64.b64encode(blob).decode("ascii"),
        }
    )
    assert fetched["points"] == [{"date": "2024-05-01", "value": 8.0}, {"date": "2024-06-01", "value": 9.0}]
    assert fetched["stored"] is True


@pytest.mark.asyncio
async def test_listing_counts_store_and_fred_does_not() -> None:
    ledger = MemoryLedger()
    body = {"observations": [{"date": "2024-01-01", "value": "3.5"}, {"date": "2024-02-01", "value": "."}]}
    first = await perform_refresh(
        tenant_id=TENANT,
        engine="ffl",
        ledger=ledger,
        fixtures=str(FIXTURES),
        fred_bodies={"PCOPPUSDM": body, "PZINCUSDM": body, "PLEADUSDM": body, "TSIFRGHT": body},
        live=False,
        now=NOW,
    )
    assert first["listings_stored"] == 4
    assert first["fred_stored"] == 0
    assert len(first["fred"]) == 4
    assert all(item["stored"] is False for item in first["fred"])
    assert ledger.points
    assert all("fred" not in item["series_id"] for item in ledger.points)
    assert ledger.refused
    second = await perform_refresh(
        tenant_id=TENANT,
        engine="ffl",
        ledger=ledger,
        fixtures=str(FIXTURES),
        fred_bodies={"PCOPPUSDM": body},
        live=False,
        now=NOW,
    )
    assert second["listings_stored"] == 0
    assert len(ledger.points_for(TENANT)) == 4
    assert ledger.points_for(OTHER) == []


@pytest.mark.asyncio
async def test_fred_stays_off_when_the_key_is_missing(monkeypatch, capsys) -> None:
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    class _Client:
        def __init__(self, *_args, **_kwargs) -> None:
            raise AssertionError("fred was called")

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    ledger = MemoryLedger()
    result = await perform_refresh(
        tenant_id=TENANT,
        engine="ffl",
        ledger=ledger,
        fixtures=str(FIXTURES),
        live=True,
        now=NOW,
    )
    assert result["fred_stored"] == 0
    assert len(result["fred"]) == 4
    assert {item["state"] for item in result["fred"]} == {"off"}
    assert {item["note"] for item in result["fred"]} == {"needs key FRED_API_KEY"}
    assert all(item["points"] == 0 and item["stored"] is False for item in result["fred"])
    assert all("fred" not in item["series_id"] for item in ledger.points)
    captured = capsys.readouterr()
    assert "Traceback" not in captured.out
    assert "Traceback" not in captured.err
    blob = json.dumps(result)
    assert "FRED_API_KEY" in blob
    assert "api_key" not in blob


@pytest.mark.asyncio
async def test_fred_live_read_returns_source_numbers_and_stores_nothing(monkeypatch, capsys) -> None:
    secret = "dummy-feed-key"
    monkeypatch.setenv("FRED_API_KEY", secret)
    body = {
        "observations": [
            {"date": "2024-01-01", "value": "3.5"},
            {"date": "2024-02-01", "value": "."},
            {"date": "2024-03-01", "value": "4.25"},
        ]
    }
    seen: list[dict] = []

    class _Response:
        status_code = 200

        def json(self) -> dict:
            return body

    class _Client:
        def __init__(self, *_args, **_kwargs) -> None:
            return None

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        async def get(self, url: str, params: dict | None = None) -> _Response:
            assert url == "https://api.stlouisfed.org/fred/series/observations"
            assert params is not None
            assert params["api_key"] == secret
            assert params["file_type"] == "json"
            seen.append(dict(params))
            return _Response()

    monkeypatch.setattr("httpx.AsyncClient", _Client)
    ledger = MemoryLedger()
    captured_points: list[dict] = []
    original = ledger.save_points

    def save_points(series_id, tenant_id, points, *, stored, source):
        captured_points.append(
            {"series_id": series_id, "points": points, "stored": stored, "source": source}
        )
        return original(series_id, tenant_id, points, stored=stored, source=source)

    ledger.save_points = save_points  # type: ignore[method-assign]
    result = await perform_refresh(
        tenant_id=TENANT,
        engine="ffl",
        ledger=ledger,
        fixtures=str(FIXTURES),
        live=True,
        now=NOW,
    )
    assert [item["series_id"] for item in seen] == ["PCOPPUSDM", "PZINCUSDM", "PLEADUSDM", "TSIFRGHT"]
    fred_saves = [item for item in captured_points if item["source"] == "fred"]
    assert len(fred_saves) == 4
    assert all(item["stored"] is False for item in fred_saves)
    assert fred_saves[0]["points"] == [
        {"date": "2024-01-01", "value": 3.5},
        {"date": "2024-03-01", "value": 4.25},
    ]
    assert result["fred_stored"] == 0
    assert all(item["state"] == "on" and item["stored"] is False for item in result["fred"])
    assert all(item["points"] == 2 for item in result["fred"])
    assert all("fred" not in item["series_id"] for item in ledger.points)
    blob = json.dumps(result)
    assert secret not in blob
    assert "3.5" not in blob
    assert "4.25" not in blob
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


@pytest.mark.asyncio
async def test_refresh_refuses_to_open_the_network() -> None:
    with pytest.raises(RuntimeError, match="network"):
        await perform_refresh(
            tenant_id=TENANT,
            engine="ffl",
            ledger=MemoryLedger(),
            fixtures=None,
            live=False,
            now=NOW,
        )


def test_prediction_made_today_resolves_on_a_fake_clock() -> None:
    made = make_prediction(
        tenant_id=TENANT,
        statement="thin / retail: response rate above 5% in 90 days",
        metric_series_id="response:thin:retail",
        comparator="gt",
        target=5,
        resolve_by=NOW,
        made_at=NOW,
        rationale="increase marketing",
        sources=[{"url": "https://example.com/evidence", "date": "2026-10-14"}],
        prediction_id="made-today",
    )
    points = [{"date": "2026-10-14", "value": 9}]
    assert resolve_prediction(made, points, NOW - timedelta(days=1)) is None
    resolved = resolve_prediction(made, points, NOW)
    assert resolved is not None
    assert resolved["outcome"] == "hit"
    assert resolved["score"] == 1.0
    assert resolved["id"] != made["id"]
    assert made["outcome"] is None
    assert made["statement"] == resolved["statement"]
    assert made["target"] == resolved["target"]
    missed = resolve_prediction(
        make_prediction(
            tenant_id=TENANT,
            statement="thin / retail: response rate above 5% in 90 days",
            metric_series_id="response:thin:retail",
            comparator="gt",
            target=5,
            resolve_by=NOW,
            made_at=NOW,
            rationale="increase marketing",
        ),
        [{"date": "2026-10-14", "value": 4}],
        NOW,
    )
    assert missed is not None and missed["outcome"] == "miss" and missed["score"] == 0.0
    corrected = correct_prediction(made, statement="thin / retail: response rate above 8% in 90 days", target=8)
    assert corrected["id"] != made["id"]
    assert made["statement"].endswith("5% in 90 days")
    assert any(item.get("corrects") == made["id"] for item in corrected["sources"])


@pytest.mark.asyncio
async def test_resolve_job_appends_one_row_and_stops() -> None:
    ledger = MemoryLedger()
    made = make_prediction(
        tenant_id=TENANT,
        statement="thin / retail: response rate above 5% in 90 days",
        metric_series_id="response:thin:retail",
        comparator="gt",
        target=5,
        resolve_by=NOW,
        made_at=NOW,
        rationale="increase marketing",
        prediction_id="made-today",
    )
    ledger.save_prediction(made)
    points = {"response:thin:retail": [{"date": "2026-10-14", "value": 9}]}
    first = await perform_resolve(tenant_id=TENANT, ledger=ledger, points_by_series=points, now=NOW)
    assert first["resolved"] == 1
    assert first["outcomes"][0]["outcome"] == "hit"
    assert len(ledger.predictions_for(TENANT)) == 2
    assert ledger.predictions_for(TENANT)[0]["outcome"] is None
    second = await perform_resolve(tenant_id=TENANT, ledger=ledger, points_by_series=points, now=NOW)
    assert second["resolved"] == 0
    assert len(ledger.predictions_for(TENANT)) == 2
    with pytest.raises(RuntimeError, match="append-only"):
        ledger.save_prediction(made)


@pytest.mark.asyncio
async def test_opportunities_recommend_and_rank_products() -> None:
    ledger = MemoryLedger()
    remembered: list[tuple] = []

    class Memory:
        async def remember(self, tenant_id: str, text: str, kind: str, source: str) -> dict:
            remembered.append((tenant_id, text, kind, source))
            return {"seen": 1}

    result = await perform_opportunities(
        tenant_id=TENANT,
        engine="ffl",
        ledger=ledger,
        areas=AREAS,
        signals={"thin": {"no_website": True, "size": 100}, "hot": {"web_shop": True, "size": 400}},
        memory=Memory(),
        now=NOW,
    )
    assert result["top_area"] == "thin"
    assert result["products"][0]["product"] == "tisan"
    assert result["products"][0]["rank"] == 1
    assert all(item["area"] != "hot" for item in result["products"])
    assert ledger.opportunities[0]["evidence"]["recommendation"] == "increase marketing"
    statements = [row["statement"] for row in ledger.predictions]
    assert any(text.startswith("thin / retail: response rate above 5%") for text in statements)
    assert ledger.reports[0]["answer"].startswith("1. thin / retail / tisan")
    assert remembered and remembered[0][2] == "report"
    assert ledger.predictions_for(OTHER) == []


@pytest.mark.asyncio
async def test_research_stores_citations_and_remembers_them() -> None:
    ledger = MemoryLedger()
    remembered: list[tuple] = []

    class Memory:
        async def remember(self, tenant_id: str, text: str, kind: str, source: str) -> dict:
            remembered.append((tenant_id, text, kind, source))
            return {"seen": 1}

    answer = await perform_research(
        tenant_id=TENANT,
        ledger=ledger,
        question="Why did the series move?",
        passages=[{"claim": "A rate rose.", "url": "https://example.com/rates", "date": "2026-01-15"}],
        memory=Memory(),
        now=NOW,
    )
    assert answer["citations"][0]["url"] == "https://example.com/rates"
    assert answer["citations"][0]["date"] == "2026-01-15"
    assert ledger.reports[0]["tenant_id"] == TENANT
    assert remembered[0][3] == "https://example.com/rates"


def _market_app():
    path = ROOT / "agents" / "market_lab" / "app.py"
    spec = importlib.util.spec_from_file_location("market_lab_box_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def test_schedules_load_listings_and_read_fred() -> None:
    app = _market_app()

    kinds = {item["kind"]: item for item in app.state.schedules}
    assert {"ping", "refresh", "opportunities", "resolve"} <= set(kinds)
    assert kinds["refresh"]["cron"] == "20 6 * * *"
    assert kinds["refresh"]["input"]["engine"] == "ffl"
    morning = datetime(2026, 10, 14, 6, 20, tzinfo=timezone.utc)
    next_day = datetime(2026, 10, 15, 6, 20, tzinfo=timezone.utc)
    assert is_due(kinds["refresh"]["cron"], morning, None)
    assert is_due(kinds["refresh"]["cron"], next_day, morning)
    first = datetime(2026, 11, 1, 6, 40, tzinfo=timezone.utc)
    assert is_due(kinds["opportunities"]["cron"], first, None)
    assert not is_due(kinds["opportunities"]["cron"], first + timedelta(days=1), None)
    assert is_due(kinds["resolve"]["cron"], datetime(2026, 10, 14, 7, 10, tzinfo=timezone.utc), None)


def test_schema_is_additive_and_predictions_are_not_updated() -> None:
    text = schema_sql()
    assert f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}" in text
    for table in ("series", "points", "events", "opportunities", "predictions", "reports"):
        assert f"CREATE TABLE IF NOT EXISTS {SCHEMA}.{table}" in text
    lowered = text.lower()
    assert "drop table" not in lowered
    assert "drop column" not in lowered
    assert "update " not in lowered
    for column in (
        "demand_idx",
        "supply_idx",
        "gap",
        "saturation",
        "reachability",
        "trend",
        "rank",
        "evidence",
        "metric_series_id",
        "resolve_by",
        "outcome",
        "score",
    ):
        assert column in text


def _service_block(compose: str, name: str) -> str:
    lines = compose.splitlines()
    start = next(index for index, line in enumerate(lines) if line == f"  {name}:")
    chunk: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("  ") and not line.startswith("   "):
            break
        chunk.append(line)
    return "\n".join(chunk)


def test_room_files_and_main_compose_add_the_corridor() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count("TANK_KEY_MARKET_LAB: ${TANK_KEY_MARKET_LAB:-}") == 2
    assert "AGENT_DB_PASSWORD_MARKET_LAB: ${AGENT_DB_PASSWORD_MARKET_LAB:-}" in compose
    assert "name: tervory-gw-market_lab" in compose
    for service in ("redis", "qdrant", "litellm", "searxng", "tiger", "workspace", "agent-roles"):
        assert "tervory-gw-market_lab" not in _service_block(compose, service)
    for service in ("postgres", "hermes", "tank"):
        assert "tervory-gw-market_lab" in _service_block(compose, service)
    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "TANK_KEY_MARKET_LAB=" in example
    assert "AGENT_DB_PASSWORD_MARKET_LAB=" in example
    agent = (ROOT / "agents" / "market_lab" / "docker-compose.yml").read_text(encoding="utf-8")
    assert "name: tervory-gw-market_lab" in agent
    assert "postgresql://agent_market_lab:" in agent
    assert "TANK_KEY: ${TANK_KEY_MARKET_LAB:-}" in agent
    assert "HERMES_URL: http://hermes:8000" in agent
    assert "POSTGRES_PASSWORD" not in agent
    assert "POSTGRES_USER" not in agent
    dockerfile = (ROOT / "agents" / "market_lab" / "Dockerfile").read_text(encoding="utf-8")
    assert "market_lab/feeds/requirements.txt" in dockerfile
    pure = (ROOT / "agents" / "market_lab" / "core" / "pure.py").read_bytes()
    bundled = (ROOT / "tank" / "skills" / "market.series_fetch" / "1.0.0" / "pure.py").read_bytes()
    assert pure == bundled


def test_core_has_no_industry_words_outside_the_engine() -> None:
    roots = [ROOT / "agents" / "market_lab"]
    roots.extend(path for path in (ROOT / "tank" / "skills").glob("market.*") if path.is_dir())
    hits: list[str] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".sql", ".yml", ".yaml", ".md", ".jsonl"}:
                continue
            if "feeds" in path.parts or ("engines" in path.parts and "ffl" in path.parts):
                continue
            text = path.read_text(encoding="utf-8")
            if BANNED.search(text):
                hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def _xlsx(rows: list[list[str]]) -> bytes:
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    sheet_rows: list[str] = []
    for index, row in enumerate(rows, start=1):
        cells = []
        for col, value in enumerate(row):
            letter = chr(ord("A") + col)
            cells.append(f'<c r="{letter}{index}" t="inlineStr"><is><t>{value}</t></is></c>')
        sheet_rows.append(f'<row r="{index}">{"".join(cells)}</row>')
    sheet = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<worksheet xmlns="{ns}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>'
    )
    content_types = """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as book:
        book.writestr("[Content_Types].xml", content_types)
        book.writestr("_rels/.rels", rels)
        book.writestr("xl/workbook.xml", workbook)
        book.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        book.writestr("xl/worksheets/sheet1.xml", sheet)
    return blob.getvalue()
