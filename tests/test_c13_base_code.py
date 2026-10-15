"""C13: base.extract@2.0.0 and base.business_data@2.0.0 are pure code.

The 1.0.0 evals still pass, HTML fixtures pass with no network, and neither
package can call a model. Agreement against the saved model answers is printed
for the PR. Tank's live learning corpus (tank.transcripts) is not in this checkout.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest
import skala

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "tank" / "skills"
EXTRACT = SKILLS / "base.extract"
BUSINESS = SKILLS / "base.business_data"
FIELDS = {
    "base.extract": ("categories", "services", "description", "people"),
    "base.business_data": ("size_band", "revenue_band", "business_model", "naics"),
}
INDUSTRY = re.compile(
    r"handguns?|firearms?|ammunit|ammo|rifles?|shotguns?|gunsmith|ffl|nra|pistols?|"
    r"revolvers?|suppressors?|cerakote|sporting|451110|332994|\batf\b",
    re.I,
)


class BoomCtx:
    async def model(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("2.0.0 called a model")


def _load_run(package: Path):
    path = package / "run.py"
    spec = importlib.util.spec_from_file_location(package.parent.name.replace(".", "_") + package.name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


def _cases(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.append(json.loads(line))
    return rows


def _norm_item(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(str(value.get("name") or "").lower().split())
    return " ".join(str(value).lower().split())


def _tokens(value: object) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _blank(value: object) -> bool:
    return value in (None, "", [], {})


def _field_agreement(got: object, want: object) -> float:
    if isinstance(want, list) or isinstance(got, list):
        return _jaccard(
            {_norm_item(item) for item in (got or []) if _norm_item(item)},
            {_norm_item(item) for item in (want or []) if _norm_item(item)},
        )
    if _blank(got) and _blank(want):
        return 1.0
    if _blank(got) or _blank(want):
        return 0.0
    if _norm_item(got) == _norm_item(want):
        return 1.0
    return _jaccard(_tokens(got), _tokens(want))


def _pct(score: float) -> str:
    return f"{score * 100:.1f}%"


async def _score_package(skill_id: str, version: str) -> tuple[int, int]:
    pkg = skala.load_packages(SKILLS)[(skill_id, version)]
    run = _load_run(pkg.path)
    passed = 0
    for case in pkg.cases:
        output = await run(case.get("input") or {}, BoomCtx())
        ok, why = skala.score_case(case.get("expected") or {}, output, case.get("tolerance") or "exact")
        assert ok, f"{pkg.ref} / {case.get('name')}: {why}"
        passed += 1
    return passed, len(pkg.cases)


def test_packages_have_no_task_type() -> None:
    for skill_id in ("base.extract", "base.business_data"):
        meta = (SKILLS / skill_id / "2.0.0" / "skill.yaml").read_text(encoding="utf-8")
        assert "task_type" not in meta
        source = (SKILLS / skill_id / "2.0.0" / "run.py").read_text(encoding="utf-8")
        assert "task_type" not in source
        assert "ctx.model" not in source
        assert ".model(" not in source
        assert not INDUSTRY.search(source), INDUSTRY.search(source).group(0) if INDUSTRY.search(source) else ""


@pytest.mark.asyncio
async def test_v1_extract_cases_pass() -> None:
    run = _load_run(EXTRACT / "2.0.0")
    cases = _cases(EXTRACT / "1.0.0" / "evals" / "cases.jsonl")
    passed = 0
    for case in cases:
        output = await run(case["input"], BoomCtx())
        ok, why = skala.score_case(case.get("expected") or {}, output, case.get("tolerance") or "exact")
        assert ok, f"{case.get('name')}: {why}"
        passed += 1
    assert passed / len(cases) >= 0.8


@pytest.mark.asyncio
async def test_v1_business_cases_pass_when_engine_supplies_tables() -> None:
    run = _load_run(BUSINESS / "2.0.0")
    cases = _cases(BUSINESS / "1.0.0" / "evals" / "cases.jsonl")
    passed = 0
    for case in cases:
        payload = dict(case["input"])
        payload["engine"] = "ffl"
        payload["_today"] = "2026-10-14"
        output = await run(payload, BoomCtx())
        assert output["confidence"] <= 60
        ok, why = skala.score_case(case.get("expected") or {}, output, case.get("tolerance") or "exact")
        assert ok, f"{case.get('name')}: {why} { {k: output.get(k) for k in ('size_band', 'business_model', 'naics', 'confidence')} }"
        passed += 1
    assert passed / len(cases) >= 0.8


@pytest.mark.asyncio
async def test_v2_cases_pass_at_threshold() -> None:
    for skill_id in ("base.extract", "base.business_data"):
        passed, total = await _score_package(skill_id, "2.0.0")
        pkg = skala.load_packages(SKILLS)[(skill_id, "2.0.0")]
        assert total >= 10
        assert passed / total >= pkg.eval_threshold


def test_each_skill_has_at_least_ten_html_fixtures() -> None:
    for skill_id in ("base.extract", "base.business_data"):
        fixtures = list((SKILLS / skill_id / "2.0.0" / "evals" / "fixtures").glob("*.html"))
        assert len(fixtures) >= 10
        names = {case.get("name") for case in _cases(SKILLS / skill_id / "2.0.0" / "evals" / "cases.jsonl")}
        used = 0
        for case in _cases(SKILLS / skill_id / "2.0.0" / "evals" / "cases.jsonl"):
            if (case.get("input") or {}).get("fixture"):
                used += 1
        assert used >= 10, names


@pytest.mark.asyncio
async def test_structured_data_beats_later_sources_and_empty_stays_empty() -> None:
    run = _load_run(EXTRACT / "2.0.0")
    won = await run({"name": "Lock Co", "text": "", "fixture": "jsonld-wins.html", "engine": "ffl"}, BoomCtx())
    assert won["categories"] == ["Safes"]
    assert won["fields"]["categories"]["method"] == "jsonld"
    bare = await run({"name": "Gift", "text": "", "fixture": "vocabulary-prose.html"}, BoomCtx())
    assert bare["categories"] == []
    armed = await run({"name": "Gift", "text": "", "fixture": "vocabulary-prose.html", "engine": "ffl"}, BoomCtx())
    assert "optics" in {item.lower() for item in armed["categories"]}
    assert armed["fields"]["categories"]["method"] == "vocabulary"
    hours = await run({"name": "Front", "text": "", "fixture": "hours-only.html"}, BoomCtx())
    assert hours["opening_hours"] == ["Mo-Fr 09:00-17:00"]
    assert hours["categories"] == []
    micro = await run({"name": "Canvas", "text": "", "fixture": "microdata-store.html"}, BoomCtx())
    assert micro["opening_hours"] == ["Tu-Su 11:00-18:00"]
    assert micro["fields"]["categories"]["method"] == "microdata"
    team = await run({"name": "Team", "text": "", "fixture": "team-cards.html"}, BoomCtx())
    names = {person["name"] for person in team["people"]}
    assert names == {"Ada Lowe", "Ben Holt"}


@pytest.mark.asyncio
async def test_business_confidence_is_capped_and_labelled() -> None:
    run = _load_run(BUSINESS / "2.0.0")
    for case in _cases(BUSINESS / "2.0.0" / "evals" / "cases.jsonl"):
        output = await run(case["input"], BoomCtx())
        assert output["confidence"] <= 60
        assert output["estimate"] is True
        assert str(output["basis"]).lower().startswith("estimate")
        for field in output["fields"].values():
            assert field["confidence"] <= 60


@pytest.mark.asyncio
async def test_page_signals_come_from_the_html_fixture() -> None:
    """Size and model move only when the saved page is read."""
    run = _load_run(BUSINESS / "2.0.0")
    payload = {
        "name": "Acme",
        "description": "Precision components.",
        "categories": ["barrels"],
        "services": ["supply"],
        "engine": "ffl",
        "_today": "2026-10-14",
    }
    without = await run(payload, BoomCtx())
    with_page = await run({**payload, "fixture": "sixty.html"}, BoomCtx())
    assert without["business_model"] != "manufacturer"
    assert with_page["business_model"] == "manufacturer"
    assert with_page["size_band"] == "51-200"
    assert without["size_band"] != "51-200"


@pytest.mark.asyncio
async def test_agreement_report_against_saved_model_answers(capsys: pytest.CaptureFixture[str]) -> None:
    lines = [
        "C13 agreement report",
        "Source: saved model answers checked in beside the fixtures.",
        "Tank's learning corpus (tank.transcripts) is not in this checkout, so there are no live rows to score.",
    ]
    for skill_id in ("base.extract", "base.business_data"):
        package = SKILLS / skill_id / "2.0.0"
        by_name = {case.get("name"): case for case in _cases(package / "evals" / "cases.jsonl")}
        saved = _cases(package / "evals" / "saved_model_answers.jsonl")
        run = _load_run(package)
        totals = {field: 0.0 for field in FIELDS[skill_id]}
        counted = {field: 0 for field in FIELDS[skill_id]}
        used = 0
        for row in saved:
            case = by_name.get(row.get("name"))
            if case is None:
                continue
            output = await run(case.get("input") or {}, BoomCtx())
            answer = row.get("answer") or {}
            used += 1
            for field in FIELDS[skill_id]:
                if field not in answer:
                    continue
                totals[field] += _field_agreement(output.get(field), answer.get(field))
                counted[field] += 1
        assert used >= 10
        lines.append(f"{skill_id}@2.0.0 vs saved model answers (n={used})")
        for field in FIELDS[skill_id]:
            assert counted[field] == used
            lines.append(f"  {field}: {_pct(totals[field] / counted[field])}")
    report = "\n".join(lines)
    print(report)
    captured = capsys.readouterr().out
    assert "C13 agreement report" in captured
    for field in ("categories", "services", "description", "people", "size_band", "revenue_band", "business_model", "naics"):
        assert field in captured
