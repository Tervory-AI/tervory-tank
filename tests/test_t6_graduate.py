"""T6: graduate a task from a paid model to plain code. No database and no network."""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import graduate
import skala

ROOT = Path(__file__).resolve().parents[1]
EXTRACT = ROOT / "tank" / "skills" / "base.extract"
SCHEMA = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)


def _policy(**overrides: object) -> dict:
    base = {
        "task_type": "base.extract",
        "model": "luna",
        "candidate_model": "skill:base.extract@2.0.0",
        "previous_model": None,
        "rung": 1,
        "eval_threshold": 0.97,
        "min_shadow_samples": 30,
        "max_reject_rate": 0.05,
        "auto_promote": True,
        "field_floors": {},
        "semantic_cache": False,
        "promoted_at": None,
        "shadow_rate": 1,
    }
    base.update(overrides)
    return base


def _evidence(**overrides: object) -> graduate.Evidence:
    evidence = graduate.Evidence(
        samples=30,
        agreement=0.99,
        fields={"categories": 0.99, "services": 0.98, "people": 1.0},
        rejected=0,
        judged=20,
    )
    for key, value in overrides.items():
        setattr(evidence, key, value)
    return evidence


def _load_run(package: Path):
    path = package / "run.py"
    spec = importlib.util.spec_from_file_location(package.parent.name.replace(".", "_") + "_" + package.name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.run


class Boom:
    async def model(self, *_args: object, **_kwargs: object) -> str:
        raise AssertionError("code candidate called a model")


class ScriptedModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls = 0

    async def model(self, *_args: object, **_kwargs: object) -> str:
        self.calls += 1
        return self.content


def test_search_proposes_the_cheapest_model_that_clears_the_bar() -> None:
    roster = [
        graduate.Quote("mite", 0.0001),
        graduate.Quote("luna", 0.0004),
        graduate.Quote("sol", 0.002),
        graduate.Quote("astra", 0.01),
    ]
    result = graduate.search(
        serving="astra",
        roster=roster,
        screens={"mite": 0.42, "luna": 0.99, "sol": 0.995},
        calls_30d=1000,
        serving_cost=0.01,
        threshold=0.97,
        min_samples=30,
    )
    assert len(roster) == 4
    assert result.proposed == "luna"
    assert result.proposed != "mite"
    by_name = {row.name: row for row in result.ranked}
    assert [row.name for row in result.ranked] == ["mite", "luna", "sol"]
    assert by_name["mite"].status == "dropped"
    assert by_name["luna"].status != "dropped"
    assert by_name["luna"].monthly_saving_usd is not None
    assert by_name["sol"].monthly_saving_usd is not None
    assert by_name["luna"].monthly_saving_usd > by_name["sol"].monthly_saving_usd


def test_a_cheaper_model_still_in_shadow_blocks_a_dearer_one() -> None:
    roster = [
        graduate.Quote("mite", 0.0001),
        graduate.Quote("luna", 0.0004),
        graduate.Quote("astra", 0.01),
    ]
    result = graduate.search(
        serving="astra",
        roster=roster,
        screens={"mite": 0.99, "luna": 0.99},
        shadows={"mite": (10, 0.99)},
        min_samples=30,
        threshold=0.97,
    )
    assert result.proposed == "mite"
    assert result.next_shadow == "mite"
    assert "luna" not in {row.name for row in result.ranked if row.status == "cleared"}


def test_live_failure_drops_a_cheap_model_and_proposes_the_next() -> None:
    roster = [
        graduate.Quote("mite", 0.0001),
        graduate.Quote("luna", 0.0004),
        graduate.Quote("astra", 0.01),
    ]
    result = graduate.search(
        serving="astra",
        roster=roster,
        screens={"mite": 0.99, "luna": 0.99},
        shadows={"mite": (30, 0.40), "luna": (30, 0.99)},
        min_samples=30,
        threshold=0.97,
    )
    assert result.proposed == "luna"
    assert next(row.status for row in result.ranked if row.name == "mite") == "dropped"


def test_code_skill_and_paid_tool_use_the_same_search() -> None:
    roster = [
        graduate.Quote("tool:brave", 0.02, kind="tool"),
        graduate.Quote("luna", 0.01, kind="model"),
        graduate.Quote("skill:base.find_site@1.0.0", 0.0, kind="code"),
    ]
    result = graduate.search(
        serving="tool:brave",
        roster=roster,
        screens={"luna": 0.40, "skill:base.find_site@1.0.0": 0.99},
        threshold=0.97,
    )
    assert result.proposed == "skill:base.find_site@1.0.0"
    assert next(row.status for row in result.ranked if row.name == "luna") == "dropped"


def test_code_is_screened_even_when_it_is_not_cheaper_than_a_free_route() -> None:
    roster = [
        graduate.Quote("skill:base.extract@1.0.0", 0.0, kind="code"),
        graduate.Quote("skill:base.extract@2.0.0", 0.0, kind="code"),
    ]
    result = graduate.search(
        serving="skill:base.extract@1.0.0",
        roster=roster,
        screens={"skill:base.extract@2.0.0": 0.99},
        threshold=0.97,
    )
    assert result.proposed == "skill:base.extract@2.0.0"


def test_field_agreement_ids_numbers_and_sets() -> None:
    primary = {"id": "A-1", "price": 10.0, "tags": ["wool", "hat"], "note": "ok"}
    close = {"id": "A-1", "price": 10.05, "tags": ["hat", "wool"], "note": "ok"}
    compared = graduate.compare(json.dumps(primary), json.dumps(close), tolerance=0.01)
    assert compared.method == "fields"
    assert compared.fields["id"] == 1.0
    assert compared.fields["price"] == 1.0
    assert compared.fields["tags"] == 1.0
    assert compared.agreement == 1.0
    far = dict(close, id="A-2", price=12.0, tags=["coat"])
    missed = graduate.compare(primary, far, tolerance=0.01)
    assert missed.method == "fields"
    assert missed.fields["id"] == 0.0
    assert missed.fields["price"] == 0.0
    assert missed.fields["tags"] < 1.0


def test_free_text_is_not_scored_as_fields() -> None:
    compared = graduate.compare("a short paragraph", "another paragraph")
    assert compared.method == "text"
    assert compared.agreement is None
    assert compared.fields == {}


def test_code_candidate_must_be_approved_and_model_free() -> None:
    assert graduate.code_candidate_problem(
        "skill:base.extract@2.0.0", state="approved", task_type=None, on_disk=True,
    ) is None
    assert "model" in (graduate.code_candidate_problem(
        "skill:base.extract@1.0.0", state="approved", task_type="base.extract", on_disk=True,
    ) or "")
    assert "approved" in (graduate.code_candidate_problem(
        "skill:base.extract@2.0.0", state="staging", task_type=None, on_disk=True,
    ) or "")
    assert graduate.code_candidate_problem("luna", state=None, task_type=None, on_disk=False) is None
    assert graduate.parse_skill("skill:base.extract@2.0.0") == ("base.extract", "2.0.0")


def test_promotion_holds_below_the_bar() -> None:
    policy = _policy(candidate_model="flash-lite")
    too_few = graduate.apply(policy, _evidence(samples=10), NOW)
    assert too_few.action == "hold"
    assert too_few.reason == "too few shadow samples"
    assert too_few.policy["model"] == "luna"
    low = graduate.apply(policy, _evidence(agreement=0.90), NOW)
    assert low.action == "hold"
    assert low.reason == "agreement is below the bar"
    weak_field = graduate.apply(policy, _evidence(fields={"categories": 0.50, "services": 0.99}), NOW)
    assert weak_field.action == "hold"
    assert weak_field.reason == "categories is below its floor"
    rejected = graduate.apply(policy, _evidence(rejected=2, judged=10), NOW)
    assert rejected.action == "hold"
    assert rejected.reason == "client rejections are above the bar"
    waiting = graduate.promote_if_proven(policy, _evidence(), NOW, automatic=True)
    assert waiting.action == "promote"
    assert waiting.policy["model"] == "flash-lite"
    manual = graduate.promote_if_proven({**policy, "auto_promote": False}, _evidence(samples=5), NOW, automatic=False)
    assert manual.action == "hold"
    assert manual.policy["model"] == "luna"


def test_promotion_happens_by_itself_above_the_bar() -> None:
    policy = _policy(candidate_model="flash-lite")
    move = graduate.apply(policy, _evidence(), NOW)
    assert move.action == "promote"
    assert move.policy["model"] == "flash-lite"
    assert move.policy["previous_model"] == "luna"
    assert move.policy["candidate_model"] is None
    assert move.policy["rung"] == 1
    assert move.policy["shadow_rate"] == 0
    assert move.policy["semantic_cache"] is False
    held = graduate.apply({**policy, "auto_promote": False}, _evidence(), NOW)
    assert held.action == "hold"
    assert held.reason == "proven, waiting for a person"
    assert held.policy["model"] == "luna"
    clicked = graduate.promote_if_proven({**policy, "auto_promote": False}, _evidence(), NOW, automatic=False)
    assert clicked.action == "promote"
    assert clicked.policy["model"] == "flash-lite"


def test_code_and_semantic_cache_stay_out_of_the_model() -> None:
    proven = _evidence()
    for automatic in (True, False):
        skill = graduate.promote_if_proven(_policy(), proven, NOW, automatic=automatic)
        assert skill.action == "promote"
        assert skill.reason is None
        assert skill.policy["model"] == "skill:base.extract@2.0.0"
        assert skill.policy["candidate_model"] is None
        cache = graduate.promote_if_proven(_policy(candidate_model="cache:semantic"), proven, NOW, automatic=automatic)
        assert cache.action == "hold"
        assert cache.reason == graduate.ROUTER_BLOCK
        assert cache.policy["model"] == "luna"
        assert cache.policy["semantic_cache"] is False
    auto = graduate.apply(_policy(), proven, NOW)
    assert auto.action == "promote" and auto.policy["rung"] == 3


def test_quality_drop_rolls_back_by_itself() -> None:
    promoted = _policy(
        model="flash-lite",
        candidate_model=None,
        previous_model="luna",
        rung=1,
        promoted_at=NOW - timedelta(days=2),
    )
    slipped = graduate.apply(promoted, graduate.Evidence(live_agreement=0.40, rejected=0, judged=0), NOW)
    assert slipped.action == "rollback"
    assert slipped.policy["model"] == "luna"
    assert slipped.policy["previous_model"] is None
    assert slipped.policy["rung"] == 1
    assert slipped.policy["promoted_at"] is None
    assert "agreement" in (slipped.reason or "")
    rejected = graduate.apply(promoted, graduate.Evidence(live_agreement=0.99, rejected=3, judged=10), NOW)
    assert rejected.action == "rollback"
    assert "rejection" in (rejected.reason or "")
    stale = graduate.apply(
        {**promoted, "promoted_at": NOW - timedelta(days=8)},
        graduate.Evidence(live_agreement=0.10, rejected=9, judged=10),
        NOW,
    )
    assert stale.action == "hold"


def test_semantic_cache_respects_threshold_and_tenant_scope() -> None:
    rows = [{"tenant_id": "tenant-a", "vector": [1.0, 0.0], "content": "the stored answer"}]
    hit = graduate.semantic_lookup([1.0, 0.0], rows, tenant_id="tenant-a", scope="tenant")
    assert hit is not None and hit["content"] == "the stored answer" and hit["similarity"] == 1.0
    near = [0.96, (1 - 0.96 ** 2) ** 0.5]
    assert graduate.cosine([1.0, 0.0], near) < graduate.SEMANTIC_THRESHOLD
    assert graduate.semantic_lookup(near, rows, tenant_id="tenant-a", scope="tenant") is None
    assert graduate.semantic_lookup([1.0, 0.0], rows, tenant_id="tenant-b", scope="tenant") is None
    shared = graduate.semantic_lookup([1.0, 0.0], rows, tenant_id="tenant-b", scope="platform")
    assert shared is not None and shared["content"] == "the stored answer"
    assert graduate.semantic_lookup([1.0, 0.0], rows, tenant_id="tenant-a", scope="none") is None
    policy = _policy(candidate_model="cache:semantic", semantic_cache=False)
    held = graduate.apply(policy, _evidence(samples=3, agreement=0.99), NOW)
    assert held.action == "hold"
    assert held.policy["model"] == "luna"
    assert held.policy["semantic_cache"] is False
    moved = graduate.apply(policy, _evidence(), NOW)
    assert moved.action == "hold"
    assert moved.reason == graduate.ROUTER_BLOCK
    assert moved.policy["model"] == "luna"
    assert moved.policy["rung"] == 1
    assert moved.policy["semantic_cache"] is False
    manual = graduate.promote_if_proven(policy, _evidence(), NOW, automatic=False)
    assert manual.action == "hold"
    assert manual.policy["model"] == "luna"


def test_shadow_budget_stops_paid_calls_and_never_stops_code() -> None:
    assert graduate.budget_open(0.99, 1.0, code=False) is True
    assert graduate.budget_open(1.0, 1.0, code=False) is False
    assert graduate.budget_open(5.0, 1.0, code=True) is True


def test_research_runs_when_the_roster_or_price_changes_or_a_month_passes() -> None:
    assert graduate.research_reason(None, NOW, "roster", "price", None, None) == "never searched"
    assert graduate.research_reason(NOW, NOW, "roster", "price", "roster", "price") is None
    assert graduate.research_reason(NOW, NOW, "new", "price", "roster", "price") == "roster changed"
    assert graduate.research_reason(NOW, NOW, "roster", "new", "roster", "price") == "price changed"
    assert graduate.research_reason(NOW - timedelta(days=30), NOW, "roster", "price", "roster", "price") == "monthly"


def test_roster_file_prices_rank_luna_under_astra() -> None:
    quotes = graduate.load_price_roster(ROOT / "litellm" / "config.yaml")
    by_name = {quote.name: quote.price for quote in quotes}
    assert by_name["luna"] < by_name["astra"]
    names, prices = graduate.fingerprints(quotes)
    assert names != prices


def test_ladder_shows_paid_then_cheaper_then_code() -> None:
    steps = graduate.ladder_from_policy(
        model="luna",
        previous_model=None,
        candidate_model="skill:base.extract@2.0.0",
        calls_30d=400,
        prim_cost=0.002,
        cand_cost=0.0,
        shadow_n=34,
        shadow_agreement=0.98,
        ranked=[{
            "name": "skill:base.extract@2.0.0",
            "kind": "code",
            "shadow_n": 34,
            "shadow_agreement": 0.98,
            "cost_per_call": 0.0,
        }, {
            "name": "flash-lite",
            "kind": "model",
            "shadow_n": 12,
            "shadow_agreement": 0.91,
            "cost_per_call": 0.0004,
        }],
    )
    assert [step["label"] for step in steps] == ["Paid model", "Cheaper model", "Code"]
    assert steps[0]["name"] == "luna" and steps[0]["current"] is True
    assert steps[0]["samples"] == 400 and steps[0]["cost_per_call"] == 0.002
    assert steps[1]["name"] == "flash-lite" and steps[1]["agreement"] == 0.91
    assert steps[2]["name"] == "skill:base.extract@2.0.0"
    assert steps[2]["samples"] == 34 and steps[2]["agreement"] == 0.98
    assert steps[2]["cost_per_call"] == 0.0
    assert steps[2]["monthly_saving_usd"] == pytest.approx(0.8)
    promoted = graduate.ladder_from_policy(
        model="skill:base.extract@2.0.0",
        previous_model="luna",
        candidate_model=None,
        calls_30d=400,
        prim_cost=0.002,
        cand_cost=None,
        shadow_n=0,
        shadow_agreement=None,
    )
    assert promoted[0]["name"] == "luna" and promoted[0]["current"] is False
    assert promoted[2]["name"] == "skill:base.extract@2.0.0" and promoted[2]["current"] is True


@pytest.mark.asyncio
async def test_shadows_extract_model_against_code_and_reports_fields() -> None:
    run_model = _load_run(EXTRACT / "1.0.0")
    run_code = _load_run(EXTRACT / "2.0.0")
    cases = [
        {
            "name": "ridgeview",
            "input": {
                "name": "Ridgeview Firearms",
                "text": (
                    "Welcome to Ridgeview Firearms, Springfield's family-owned gun shop since 1998. "
                    "We stock handguns, rifles, shotguns and ammunition, and offer gunsmithing, "
                    "FFL transfers and concealed-carry classes. Owner Mark Ridge is a certified NRA instructor."
                ),
            },
            "model": json.dumps({
                "categories": ["handguns", "rifles", "shotguns", "ammunition"],
                "services": ["gunsmithing", "FFL transfers", "concealed-carry classes"],
                "description": "Family-owned gun shop.",
                "people": [{"name": "Mark Ridge", "role": "Owner"}],
                "explicit": True,
            }),
        },
        {
            "name": "jsonld-local",
            "input": {
                "name": "Trail Counter",
                "text": "Trail Counter sells gear for day hikes and keeps maps at the front desk. Visit the shop.",
                "fixture": "jsonld-local.html",
            },
            "model": json.dumps({
                "categories": ["Water bottles", "Trail maps"],
                "services": [],
                "description": "Maps and bottles for the trail.",
                "people": [],
                "explicit": True,
            }),
        },
    ]
    report = []
    model_calls = 0
    for case in cases:
        scripted = ScriptedModel(case["model"])
        primary = await run_model(case["input"], scripted)
        code = await run_code(case["input"], Boom())
        compared = graduate.compare(primary, code)
        assert compared.method == "fields"
        assert compared.agreement is not None
        assert 0.0 <= compared.agreement <= 1.0
        assert compared.fields
        assert all(0.0 <= score <= 1.0 for score in compared.fields.values())
        model_calls += scripted.calls
        report.append({
            "name": case["name"],
            "agreement": compared.agreement,
            "fields": compared.fields,
        })
    assert model_calls == 2
    ridge = report[0]["fields"]
    assert ridge["categories"] == 1.0
    assert ridge["people"] == 1.0
    assert "categories" in report[1]["fields"]
    pkg = skala.load_packages(ROOT / "tank" / "skills")[("base.extract", "2.0.0")]
    assert pkg.task_type is None


@pytest.mark.asyncio
async def test_a_proven_skill_can_be_served_at_rung_three() -> None:
    move = graduate.apply(_policy(), _evidence(), NOW)
    assert move.action == "promote"
    assert move.policy["model"] == "skill:base.extract@2.0.0"
    assert move.policy["rung"] == 3
    manual = graduate.promote_if_proven(_policy(), _evidence(), NOW, automatic=False)
    assert manual.action == "promote"


@pytest.mark.asyncio
async def test_a_model_answer_still_counts_one_call() -> None:
    calls = 0

    async def llm(model: str, _payload: dict) -> tuple[str, float]:
        nonlocal calls
        calls += 1
        assert model == "luna"
        return "hello", 0.01

    async def run_code(_model: str, _payload: dict) -> str:
        raise AssertionError("code runner used for a model")

    result = await graduate.answer("luna", {"text": "hi"}, llm=llm, run_code=run_code)
    assert calls == 1
    assert result.model_calls == 1
    assert result.cost_usd == 0.01


def test_schema_and_console_carry_the_ladder() -> None:
    assert "ADD COLUMN IF NOT EXISTS auto_promote" in SCHEMA
    assert "ADD COLUMN IF NOT EXISTS fields" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS tank.graduation_rank" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS tank.shadow_spend" in SCHEMA
    assert "CREATE TABLE IF NOT EXISTS tank.search_state" in SCHEMA
    assert "TANK_SHADOW_BUDGET_USD" in (ROOT / ".env.example").read_text(encoding="utf-8")
    console = (ROOT / "workspace" / "app" / "admin" / "console.tsx").read_text(encoding="utf-8")
    admin = (ROOT / "workspace" / "lib" / "admin.ts").read_text(encoding="utf-8")
    assert "Cost per call" in console
    assert "Monthly saving" in console
    assert "Agreement" in console
    assert "Samples" in console
    assert "ladders" in console
    assert "/v1/graduation" in admin
    main = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    assert "/v1/graduation/{task_type}/search" in main
    assert "/v1/graduation/{task_type}/auto" in main
    assert "method=\"fields\"" in main or 'method = "fields"' in main or "compared.method" in main
