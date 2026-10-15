"""B3b: page HTML and the engine id reach the code skills, and the console reads Base's table.

No database and no network. Skill versions 1.0.0 and 2.0.0 both run through the pipeline.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")
os.environ.setdefault("TERVORY_ADMIN_USER_IDS", "user_founder")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "base"))
sys.path.insert(0, str(ROOT / "tank"))

import admin  # noqa: E402
import skala  # noqa: E402
from pipeline import answer_from_code, enrich_one  # noqa: E402

SKILLS = ROOT / "tank" / "skills"
HTML_CAP = 400 * 1024
SITE = "https://acme.example"
ABOUT = f"{SITE}/about"
PAD = "The counter is open and the register is staffed. " * 8
HOME = f"""<!DOCTYPE html>
<html>
<head>
  <meta name="description" content="Counter sales and transfers for the neighborhood.">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Store",
    "name": "Acme Counter",
    "makesOffer": [
      {{"@type": "Offer", "itemOffered": {{"@type": "Product", "category": "Handguns"}}}}
    ]
  }}
  </script>
</head>
<body>
  <a href="/about">About</a>
  <p>HOME-PAGE-MARKER 200 employees keep the doors open at the counter every week.</p>
  <p>{PAD}</p>
</body>
</html>
"""
ABOUT_PAGE = """<!DOCTYPE html>
<html><body>
  <p>ABOUT-PAGE-MARKER Reach the desk at about@acme.example or (512) 555-0199.</p>
</body></html>
"""
RAW = {
    "name": "Acme Counter",
    "city": "Austin",
    "state": "TX",
    "phone": "512-555-0100",
    "address": "1 Main St",
    "zip": "78701",
    "website": SITE,
}
ENGINE_IN = {"licence_number": "1-23-456-78-9A-12345", "licence_type": "01"}


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _cases(version: str) -> list[dict]:
    path = SKILLS / "base.scrape_site" / version / "evals" / "cases.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


SCRAPE = _load("scrape_120", SKILLS / "base.scrape_site" / "1.2.0" / "run.py")
EXTRACT_V1 = _load("extract_100", SKILLS / "base.extract" / "1.0.0" / "run.py")
EXTRACT_V2 = _load("extract_200", SKILLS / "base.extract" / "2.0.0" / "run.py")
BUSINESS_V1 = _load("business_100", SKILLS / "base.business_data" / "1.0.0" / "run.py")
BUSINESS_V2 = _load("business_200", SKILLS / "base.business_data" / "2.0.0" / "run.py")


class Page:
    def __init__(self, text: str = "", status: int = 200, content_type: str = "text/html; charset=utf-8", body: dict | None = None) -> None:
        self.text = text
        self.status_code = status
        self.headers = {"content-type": content_type}
        self._body = body or {}

    def json(self) -> dict:
        return self._body


class Site:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages

    async def get(self, url: str, **_kwargs: object) -> Page:
        text = self.pages.get(url)
        if text is None:
            return Page("", 404, "text/plain")
        return Page(text)

    async def post(self, *_args: object, **_kwargs: object) -> Page:
        raise AssertionError("no browser call")


class Ctx:
    def __init__(self, http: object, env: dict | None = None) -> None:
        self.http = http
        self.env = env or {}
        self.model_calls = 0

    async def model(self, *_args: object, **_kwargs: object) -> str:
        self.model_calls += 1
        raise AssertionError("model called")


class ModelCtx:
    def __init__(self, replies: dict[str, str]) -> None:
        self.replies = replies
        self.calls: list[str] = []

    async def model(self, _messages: object, task_type: str, **_kwargs: object) -> str:
        self.calls.append(task_type)
        return self.replies[task_type]


def _stamp(out: dict, ref: str, cost: float | None) -> dict:
    """Shape Tank gives the pipeline: skill ref, and a cost only when a model ran."""
    stamped = dict(out)
    stamped["_skill"] = ref
    stamped.setdefault("_ms", 1)
    if cost is not None:
        stamped["_cost_usd"] = cost
    return stamped


def _scripted(skill_id: str, payload: dict) -> dict:
    base = {"_skill": f"{skill_id}@1.0.0", "_ms": 1, "_cost_usd": 0.0}
    if skill_id == "base.normalize":
        name = str(payload.get("name") or "")
        return {
            **base,
            "fields": {
                "name": {"value": name, "source": "input", "confidence": 90},
                "city": {"value": payload.get("city"), "source": "input", "confidence": 90},
                "state": {"value": str(payload.get("state") or "").upper(), "source": "input", "confidence": 95},
                "phone": {"value": payload.get("phone"), "source": "input", "confidence": 80},
                "street": {"value": payload.get("address"), "source": "input", "confidence": 80},
                "zip": {"value": payload.get("zip"), "source": "input", "confidence": 90},
            },
        }
    if skill_id == "base.resolve":
        return {**base, "match": None, "verdict": "new", "score": 0}
    if skill_id == "base.find_site":
        return {**base, "website": {"value": payload.get("website") or SITE, "source": "input", "confidence": 100}}
    if skill_id == "base.contacts":
        return {**base, "confidence": 0}
    if skill_id == "base.socials":
        return {**base, "count": 0, "profiles": [], "presence": "none", "confidence": 0}
    if skill_id == "base.verify":
        return {**base, "confidence": 70, "tier": "review", "flags": [], "layers": ["site"], "checks": {"name": True}}
    if skill_id == "ffl.profile":
        return {**base, "licence_number": ENGINE_IN["licence_number"], "licence_type": "01", "segment": "retail"}
    raise AssertionError(skill_id)


def test_code_answers_stay_labelled_when_tank_stamps_a_zero_cost() -> None:
    assert answer_from_code("base.extract@2.0.0", {"_cost_usd": 0})
    assert answer_from_code("base.business_data@2.0.0", {"_cost_usd": 0.0})
    assert answer_from_code("base.extract@1.0.0", {})
    assert answer_from_code("base.extract@1.0.0", {"_cost_usd": None})
    assert answer_from_code("base.extract@1.0.0", {"_cost_usd": 0.002}) is False
    assert answer_from_code("base.extract@1.2.0", {"_cost_usd": 0}) is False


def test_scrape_1_2_0_returns_joined_html_capped_at_400_kb() -> None:
    previous = (SKILLS / "base.scrape_site" / "1.1.0" / "run.py").read_text(encoding="utf-8")
    assert "HTML_CAP" not in previous
    assert "ctx.model" not in (SKILLS / "base.scrape_site" / "1.2.0" / "run.py").read_text(encoding="utf-8")

    old_cases = _cases("1.1.0")
    new_cases = _cases("1.2.0")
    assert [case["name"] for case in new_cases[: len(old_cases)]] == [case["name"] for case in old_cases]
    added = new_cases[len(old_cases) :]
    assert len(added) == 3
    assert all("html" in case["expected"] for case in added)

    async def check() -> None:
        ctx = Ctx(Site({}))
        for case in added:
            if case["input"]["website"] == "https://example.com":
                continue
            output = await SCRAPE.run(case["input"], ctx)
            ok, why = skala.score_case(case["expected"], output, case["tolerance"])
            assert ok, why
            assert "html" in output
            assert len(output["html"].encode("utf-8")) <= HTML_CAP

        small = await SCRAPE.run({"website": SITE}, Ctx(Site({SITE: HOME, ABOUT: ABOUT_PAGE})))
        assert small["via"] == "fetch"
        assert small["pages"] == [SITE, ABOUT]
        assert "HOME-PAGE-MARKER" in small["html"]
        assert "ABOUT-PAGE-MARKER" in small["html"]
        assert "application/ld+json" in small["html"]
        assert "about@acme.example" in small["emails"]
        assert "+15125550199" in small["phones"]
        assert len(small["text"]) >= 40
        assert len(small["html"].encode("utf-8")) <= HTML_CAP

        huge_home = (
            "<html><body><a href='/about'>About</a> HOME-MARKER"
            + ("x" * (HTML_CAP + 80))
            + "</body></html>"
        )
        huge_about = "<html><body>ABOUT-MARKER <a href='mailto:tail@acme.example'>mail</a></body></html>"
        huge = await SCRAPE.run({"website": SITE}, Ctx(Site({SITE: huge_home, ABOUT: huge_about})))
        assert huge["pages"] == [SITE, ABOUT]
        assert "tail@acme.example" in huge["emails"]
        assert "HOME-MARKER" in huge["html"]
        assert "ABOUT-MARKER" not in huge["html"]
        assert len(huge["html"].encode("utf-8")) <= HTML_CAP
        assert ctx.model_calls == 0

    asyncio.run(check())


def _run_record(extract_run, business_run, ctx: Ctx | ModelCtx, refs: dict[str, str], costs: dict[str, float | None]):
    seen: dict[str, dict] = {}

    async def call(skill_id: str, payload: dict) -> dict:
        seen[skill_id] = payload
        if skill_id == "base.scrape_site":
            out = await SCRAPE.run(payload, Ctx(Site({SITE: HOME, ABOUT: ABOUT_PAGE})))
            return _stamp(out, refs[skill_id], costs.get(skill_id))
        if skill_id == "base.extract":
            out = await extract_run(payload, ctx)
            return _stamp(out, refs[skill_id], costs.get(skill_id))
        if skill_id == "base.business_data":
            out = await business_run(payload, ctx)
            return _stamp(out, refs[skill_id], costs.get(skill_id))
        return _scripted(skill_id, payload)

    outcome = asyncio.run(enrich_one(RAW, ENGINE_IN, [], "ffl", call, refs))
    return outcome, seen


def test_jsonld_page_fills_categories_size_and_naics_for_free() -> None:
    """The live shape: Tank stamps _cost_usd 0 and the skill ref is 2.x."""
    refs = {
        "base.scrape_site": "base.scrape_site@1.2.0",
        "base.extract": "base.extract@2.0.0",
        "base.business_data": "base.business_data@2.0.0",
    }
    costs = {"base.scrape_site": 0.0, "base.extract": 0.0, "base.business_data": 0.0}
    ctx = Ctx(None)
    outcome, seen = _run_record(EXTRACT_V2.run, BUSINESS_V2.run, ctx, refs, costs)

    assert outcome.status == "done"
    assert outcome.error is None
    assert outcome.cost_usd == 0
    assert "skipped" not in outcome.passes["2c"]
    assert "skipped" not in outcome.passes["5"]
    assert outcome.passes["2c"]["cost_usd"] == 0
    assert outcome.passes["5"]["cost_usd"] == 0
    assert outcome.passes["2c"]["skill"] == "base.extract@2.0.0"
    assert outcome.passes["5"]["skill"] == "base.business_data@2.0.0"
    assert ctx.model_calls == 0

    extract_in = seen["base.extract"]
    assert extract_in["engine"] == "ffl"
    assert "Handguns" in extract_in["html"]
    assert "ABOUT-PAGE-MARKER" in extract_in["html"]
    assert "application/ld+json" in extract_in["html"]
    business_in = seen["base.business_data"]
    assert business_in["engine"] == "ffl"
    assert "200 employees" in business_in["html"]
    assert business_in["categories"] == ["Handguns"]

    profile = outcome.profile
    assert profile["categories"] == {"value": ["Handguns"], "source": "site:code", "confidence": profile["categories"]["confidence"]}
    assert profile["categories"]["confidence"] > 0
    assert profile["size_band"]["value"] == "200+"
    assert profile["size_band"]["source"] == "site:code"
    assert profile["naics"] == {"value": "451110", "source": "site:code", "confidence": profile["naics"]["confidence"]}
    assert profile["naics_label"]["value"] == "Sporting goods stores"
    assert profile["naics_label"]["source"] == "site:code"
    assert profile["revenue_band"]["source"] == "site:code"


def test_version_1_0_0_accepts_the_extra_fields_and_stays_a_model_answer() -> None:
    refs = {
        "base.scrape_site": "base.scrape_site@1.1.0",
        "base.extract": "base.extract@1.0.0",
        "base.business_data": "base.business_data@1.0.0",
    }
    costs = {"base.scrape_site": 0.0, "base.extract": 0.002, "base.business_data": 0.003}
    ctx = ModelCtx({
        "base.extract": json.dumps({
            "categories": ["rifles"],
            "services": ["sales"],
            "description": "A shop that sells rifles to local customers.",
            "people": [{"name": "Ada", "role": "owner"}],
            "explicit": True,
        }),
        "base.business_data": json.dumps({
            "size_band": "2-10",
            "revenue_band": "<$500k",
            "business_model": "retail",
            "naics": "451110",
            "naics_label": "Sporting goods stores",
            "basis": "site",
            "sure": True,
        }),
    })
    outcome, seen = _run_record(EXTRACT_V1.run, BUSINESS_V1.run, ctx, refs, costs)

    assert outcome.status == "done"
    assert outcome.error is None
    assert "skipped" not in outcome.passes["2c"]
    assert "skipped" not in outcome.passes["5"]
    assert ctx.calls == ["base.extract", "base.business_data"]
    assert seen["base.extract"]["html"]
    assert seen["base.extract"]["engine"] == "ffl"
    assert seen["base.business_data"]["engine"] == "ffl"
    assert "html" in seen["base.business_data"]
    assert outcome.profile["categories"]["source"] == "site:model"
    assert outcome.profile["categories"]["value"] == ["rifles"]
    assert outcome.profile["size_band"]["source"] == "model:estimate"
    assert outcome.profile["naics"]["source"] == "model:estimate"
    assert outcome.passes["2c"]["skill"] == "base.extract@1.0.0"
    assert outcome.cost_usd == 0.005


def test_a_code_answer_with_no_cost_field_is_still_site_code() -> None:
    """1.x ref, no _cost_usd: the pipeline still treats it as code."""
    refs = {
        "base.scrape_site": "base.scrape_site@1.2.0",
        "base.extract": "base.extract@1.0.0",
        "base.business_data": "base.business_data@1.0.0",
    }
    ctx = Ctx(None)
    outcome, _seen = _run_record(EXTRACT_V2.run, BUSINESS_V2.run, ctx, refs, {})
    assert outcome.status == "done"
    assert outcome.cost_usd == 0
    assert outcome.profile["categories"]["source"] == "site:code"
    assert outcome.profile["size_band"]["source"] == "site:code"
    assert outcome.profile["naics"]["source"] == "site:code"
    assert ctx.model_calls == 0


def test_founder_console_counts_rows_in_agent_base() -> None:
    sql = admin.BASE_BACKFILL_SQL
    source = (ROOT / "tank" / "admin.py").read_text(encoding="utf-8")
    assert "FROM agent_base.records" in sql
    assert "FROM base.records" not in source
    assert "INSERT INTO tank.outcomes" in sql
    assert "INSERT INTO agent_base" not in sql
    assert "UPDATE" not in sql
    assert "DELETE" not in sql
    for column in ("updated_at", "tenant_id", "status = 'done'", "id::text"):
        assert column in sql

    rows = [
        {"id": "row-done-1", "tenant_id": "t", "status": "done", "updated_at": "2026-10-14T00:00:00+00:00"},
        {"id": "row-queued", "tenant_id": "t", "status": "queued", "updated_at": "2026-10-14T00:00:00+00:00"},
        {"id": "row-done-2", "tenant_id": "t", "status": "done", "updated_at": "2026-10-15T00:00:00+00:00"},
    ]
    counted = admin.base_outcome_rows(rows, set())
    assert [row["ref"] for row in counted] == ["row-done-1", "row-done-2"]
    assert all(row["outcome_type"] == "base.record_enriched" and row["quantity"] == 1 for row in counted)


def test_pipeline_does_not_call_a_model() -> None:
    source = (ROOT / "agents" / "base" / "pipeline.py").read_text(encoding="utf-8")
    assert ".model(" not in source
    assert "ctx.model" not in source
