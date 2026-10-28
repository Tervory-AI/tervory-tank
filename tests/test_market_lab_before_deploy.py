"""Market Lab checks before deploy. Fixtures only: no database server, no network, no feed keys.

The rows are the Market Lab lines on Agent tests:
- a copied number matches the saved source, and a blank source adds no number
- surge and shift on planted past series: 80%+ of the labeled moves are caught, and any other hit is listed
- a research citation is a passage we were given; a URL the model typed is dropped
- a research question with no passages makes no model call and costs nothing
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sqlite3
import subprocess
import sys
from types import SimpleNamespace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "market_lab"))

from core.pure import research_answer, shift_detect, surge_detect  # noqa: E402
from feeds.cli import main  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "feeds"
CATCH_BAR = 0.8

# Planted series, not a history a person checked. A labeled move is one step
# after six flat months. A quiet series never moves. A near miss moves 10%.
_FLAT = [100.0] * 6


def _months(start: date, values: list[float]) -> list[dict[str, object]]:
    points: list[dict[str, object]] = []
    year, month = start.year, start.month
    for value in values:
        points.append({"date": f"{year:04d}-{month:02d}-01", "value": value})
        month += 1
        if month > 12:
            month = 1
            year += 1
    return points


def _labeled_series() -> tuple[list[dict[str, object]], list[dict[str, str]]]:
    """Ten labeled moves, plus series that must stay quiet."""
    start = date(2020, 1, 1)
    cases: list[tuple[str, list[float], str | None]] = [
        ("up-a", _FLAT + [200.0], "surge"),
        ("up-b", _FLAT + [180.0], "surge"),
        ("up-c", _FLAT + [150.0], "surge"),
        ("up-d", _FLAT + [130.0], "surge"),
        ("up-e", _FLAT + [250.0], "surge"),
        ("up-f", _FLAT + [400.0], "surge"),
        ("up-g", _FLAT + [160.0], "surge"),
        ("up-h", _FLAT + [220.0], "surge"),
        ("down-a", _FLAT + [50.0], "drop"),
        ("down-b", _FLAT + [40.0], "drop"),
        ("quiet-a", [100.0] * 12, None),
        ("quiet-b", [40.0] * 12, None),
        ("quiet-c", [7.0] * 12, None),
        ("near-a", _FLAT + [110.0], None),
        ("near-b", _FLAT + [90.0], None),
    ]
    series: list[dict[str, object]] = []
    known: list[dict[str, str]] = []
    for name, values, kind in cases:
        points = _months(start, values)
        series.append({"id": name, "points": points})
        if kind:
            known.append({"id": name, "date": str(points[-1]["date"]), "kind": kind})
    return series, known


def _score(
    detected: list[dict[str, str]],
    known: list[dict[str, str]],
) -> tuple[float, list[dict[str, str]], list[dict[str, str]]]:
    known_keys = {(item["id"], item["date"], item["kind"]) for item in known}
    detected_keys = {(item["id"], item["date"], item["kind"]) for item in detected}
    caught = known_keys & detected_keys
    missed = [
        {"id": item_id, "date": stamp, "kind": kind}
        for item_id, stamp, kind in sorted(known_keys - detected_keys)
    ]
    false_alarms = [
        {"id": item_id, "date": stamp, "kind": kind}
        for item_id, stamp, kind in sorted(detected_keys - known_keys)
    ]
    recall = len(caught) / len(known_keys)
    return recall, false_alarms, missed


def test_surge_and_shift_catch_labeled_moves_and_list_false_alarms() -> None:
    series, known = _labeled_series()
    surge_hits: list[dict[str, str]] = []
    areas: list[dict[str, object]] = []
    for item in series:
        name = str(item["id"])
        events = surge_detect({"points": item["points"]})["events"]
        for event in events:
            surge_hits.append({"id": name, "date": event["date"], "kind": event["kind"]})
        areas.append({"area": name, "segment": "all", "gap": item["points"]})

    surge_recall, surge_false, surge_missed = _score(surge_hits, known)
    assert surge_recall >= CATCH_BAR, {
        "recall": surge_recall,
        "missed": surge_missed,
        "false_alarms": surge_false,
    }
    assert surge_false == [], surge_false

    shift_known = [
        {
            "id": item["id"],
            "date": item["date"],
            "kind": "bottleneck" if item["kind"] == "surge" else "saturating",
        }
        for item in known
    ]
    shift_hits = [
        {"id": str(event["area"]), "date": event["date"], "kind": event["kind"]}
        for event in shift_detect({"areas": areas})["events"]
    ]
    shift_recall, shift_false, shift_missed = _score(shift_hits, shift_known)
    assert shift_recall >= CATCH_BAR, {
        "recall": shift_recall,
        "missed": shift_missed,
        "false_alarms": shift_false,
    }
    assert shift_false == [], shift_false


class _ChargingModel:
    """A model that would bill if research called it. The no-passages path must not."""

    def __init__(self) -> None:
        self.calls = 0
        self.cost_usd = 0.0

    async def model(self, *_args: object, **_kwargs: object) -> str:
        self.calls += 1
        self.cost_usd += 0.03
        return "CLAIM: made up\nURL: https://example.com/made-up\nDATE: 2026-01-01\n"

    async def route(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        self.calls += 1
        self.cost_usd += 0.03
        return {"content": "made up", "cost_usd": 0.03}


def _load_named(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_research_with_no_passages_makes_no_model_call_and_costs_nothing(monkeypatch) -> None:
    """An unconfigured web research rung returns no sources at zero model cost."""
    skill_run = _load_named(
        "market_research_run_no_sources",
        ROOT / "tank" / "skills" / "market.research" / "1.0.0" / "run.py",
    ).run
    sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
    if str(ROOT / "agents" / "market_lab") not in sys.path:
        sys.path.insert(0, str(ROOT / "agents" / "market_lab"))
    from chassis.jobs import JobContext  # noqa: E402
    from core import research_adapter

    async def unconfigured(*_args):
        return None

    monkeypatch.setattr(research_adapter, "research_web", unconfigured)

    research = _load_named(
        "market_lab_research_app",
        ROOT / "agents" / "market_lab" / "app.py",
    ).research

    async def check() -> None:
        for payload in (
            {"question": "Why did diesel move?"},
            {"question": "Why did diesel move?", "passages": None},
            {"question": "Why did diesel move?", "passages": []},
        ):
            ctx = _ChargingModel()
            result = await skill_run(payload, ctx)
            assert ctx.calls == 0
            assert ctx.cost_usd == 0
            assert result["answer"] == "no sources yet"
            assert result["citations"] == []
            assert result["cost_usd"] == 0

        cited = _ChargingModel()
        kept = await skill_run(
            {
                "question": "Why did the series move?",
                "passages": [
                    {"claim": "A rate rose.", "url": "https://example.com/rates", "date": "2026-01-15"}
                ],
            },
            cited,
        )
        assert cited.calls == 0
        assert cited.cost_usd == 0
        assert kept["citations"] == [
            {"claim": "A rate rose.", "url": "https://example.com/rates", "date": "2026-01-15"}
        ]
        assert kept["answer"] == "A rate rose."

        for job_input in (
            {"question": "Why did diesel move?"},
            {"question": "Why did diesel move?", "passages": None},
            {"question": "Why did diesel move?", "passages": []},
        ):
            tank = _ChargingModel()
            job = JobContext(
                agent="market_lab",
                tenant_id="00000000-0000-0000-0000-000000000001",
                job_id="job",
                kind="research",
                input=job_input,
                files=None,
                tank=tank,
                memory=None,
                browser=None,
            )
            answer = await research(job)
            assert tank.calls == 0
            assert tank.cost_usd == 0
            assert answer == {"answer": "no sources yet", "citations": [], "cost_usd": 0}

    asyncio.run(check())


@pytest.mark.parametrize("question,key", [("", "test-room"), ("   ", "test-room"),
                                         ("Public question", None), ("Public question", "  ")])
def test_empty_or_unconfigured_research_keeps_no_sources_without_tank(monkeypatch, question, key):
    sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
    from core import research_adapter

    if key is None:
        monkeypatch.delenv("TANK_KEY", raising=False)
    else:
        monkeypatch.setenv("TANK_KEY", key)

    def no_network(**_):
        raise AssertionError("empty or unconfigured research contacted Tank")

    monkeypatch.setattr(research_adapter.httpx, "AsyncClient", no_network)
    research = _load_named("market_lab_no_research_config", ROOT / "agents/market_lab/app.py").research
    ctx = SimpleNamespace(input={"question": question}, tenant_id="00000000-0000-0000-0000-000000000001")
    assert asyncio.run(research(ctx)) == {"answer": "no sources yet", "citations": [], "cost_usd": 0}
    assert asyncio.run(research_adapter.research_if_promoted(ctx.tenant_id, question)) is None


def test_research_drops_a_source_the_model_made_up() -> None:
    invented = (
        "CLAIM: Diesel hit nine dollars.\n"
        "URL: https://example.com/invented\n"
        "DATE: 2026-02-01\n"
    )
    bare = research_answer({"question": "Why did diesel move?", "model_text": invented})
    assert bare["citations"] == []
    assert bare["answer"] == ""
    assert "invented" not in bare["answer"]

    kept = research_answer(
        {
            "question": "Why did the series move?",
            "passages": [{"claim": "A rate rose.", "url": "https://example.com/rates", "date": "2026-01-15"}],
            "model_text": invented,
        }
    )
    assert kept["citations"] == [
        {"claim": "A rate rose.", "url": "https://example.com/rates", "date": "2026-01-15"}
    ]
    assert "nine dollars" not in kept["answer"]
    assert "https://example.com/invented" not in kept["answer"]


def _db(tmp_path: Path) -> str:
    return "sqlite:///" + str(tmp_path / "feeds.sqlite")


def _connect(target: str) -> sqlite3.Connection:
    conn = sqlite3.connect(target[len("sqlite:///") :])
    conn.row_factory = sqlite3.Row
    return conn


def _stored(conn: sqlite3.Connection, source_id: str) -> set[tuple[str, Decimal]]:
    rows = conn.execute(
        """
        SELECT p.date AS date, p.value AS value
        FROM points p
        JOIN series s ON s.id = p.series_id
        WHERE s.source_id = ?
        """,
        (source_id,),
    ).fetchall()
    return {(str(row["date"]), Decimal(str(row["value"]))) for row in rows}


def test_copied_numbers_match_the_saved_source_and_fred_is_not_stored(tmp_path: Path) -> None:
    target = _db(tmp_path)
    assert main(["run", "--backfill", "--fixtures", str(FIXTURES), "--db", target, "--engine", "ffl"]) == 0
    conn = _connect(target)

    diesel = json.loads((FIXTURES / "eia" / "diesel.json").read_text(encoding="utf-8"))
    expected_diesel = {
        (str(row["period"])[:10], Decimal(str(row["value"])))
        for row in diesel["response"]["data"]
    }
    assert _stored(conn, "eia_diesel") == expected_diesel

    commodities = json.loads((FIXTURES / "world_bank" / "commodities.json").read_text(encoding="utf-8"))
    wanted = {"PCOPPUSDM", "PZINCUSDM", "PLEADUSDM", "PCOTTINDUSDM"}
    expected_prices = {
        Decimal(str(row["value"]))
        for row in commodities[1]
        if str((row.get("indicator") or {}).get("id") or "") in wanted
    }
    stored_prices = {value for _date, value in _stored(conn, "world_bank_commodities")}
    assert stored_prices == expected_prices
    assert Decimal("1") not in stored_prices

    stored_text = " ".join(str(row["value"]) for row in conn.execute("SELECT value FROM points"))
    assert "424242" not in stored_text


def test_page_parsers_copy_the_fixture_number() -> None:
    script = r"""
import { readFileSync } from "node:fs";
import { parseAlerts, parseEcfr, parseEia, parseFred, parseRegister, parseWorldBank } from "./workspace/app/market-lab/parse.ts";

function load(path) {
  return JSON.parse(readFileSync(path, "utf8"));
}

function fail(message) {
  console.error(message);
  process.exit(1);
}

const diesel = load("tests/fixtures/feeds/eia/diesel.json");
const latestDiesel = diesel.response.data.slice().sort((a, b) => a.period.localeCompare(b.period)).at(-1);
const eia = parseEia(diesel);
if (!eia || eia.value !== latestDiesel.value || eia.period !== latestDiesel.period.slice(0, 10)) {
  fail("eia " + JSON.stringify({ eia, latestDiesel }));
}
if (parseEia({ response: { data: [{ period: "2024-01-08", value: null }] } }) !== null) {
  fail("blank eia invented a number");
}

const prices = load("tests/fixtures/feeds/world_bank/commodities.json");
for (const code of ["PCOPPUSDM", "PZINCUSDM", "PLEADUSDM", "PCOTTINDUSDM"]) {
  const row = prices[1].find((item) => item.indicator.id === code);
  const parsed = parseWorldBank(prices, code);
  const raw = typeof row.value === "number" ? String(row.value) : String(row.value).trim();
  if (!parsed || parsed.value !== raw) fail("world bank " + code + " " + JSON.stringify(parsed));
}

const alerts = load("tests/fixtures/feeds/noaa/alerts.json");
const parsedAlerts = parseAlerts(alerts);
if (!parsedAlerts || parsedAlerts.count !== alerts.features.length) fail("alerts count");
if (parsedAlerts.example !== alerts.features[0].properties.event) fail("alerts name");

const rules = load("tests/fixtures/feeds/ecfr/title-49.json");
const parsedRules = parseEcfr(rules);
if (!parsedRules || parsedRules.date !== rules.date) fail("ecfr date");

const register = load("tests/fixtures/feeds/federal_register/page.json");
const notices = parseRegister(register);
const titles = new Set(register.results.map((row) => row.title));
if (!notices || notices.notices.length === 0) fail("register empty");
for (const notice of notices.notices) {
  if (!titles.has(notice.title)) fail("register invented " + notice.title);
}

const fred = parseFred(load("tests/fixtures/feeds/fred/not_for_ingest.json"));
if (!fred || fred.value !== "424242") fail("fred parser did not copy the fixture");
if (parseFred({ observations: [{ date: "2024-01-01", value: "." }] }) !== null) fail("blank fred invented a number");
"""
    result = subprocess.run(
        [
            "node",
            "--experimental-strip-types",
            "--import",
            str(ROOT / "tests" / "market_lab_register.mjs"),
            "--input-type=module",
            "-e",
            script,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
