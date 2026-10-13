"""Founder console: proven status, margin, the paid-work list, and a hidden door.

These tests use fixtures. They do not need a database or the network.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")
os.environ.setdefault("TERVORY_ADMIN_USER_IDS", "user_founder")

import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tank"))

import admin  # noqa: E402

T = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
NOW = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
DAY = date(2026, 10, 1)
TODAY = date(2026, 10, 13)


def _calls(rung: int, cost: float, n: int, cache: bool = False) -> list[dict]:
    return [
        {
            "ts": NOW,
            "tenant_id": T,
            "agent": "tiger",
            "task_type": "reason.brief",
            "rung": rung,
            "model": "sonnet",
            "cost_usd": cost,
            "cache_hit": cache,
        }
        for _ in range(n)
    ]


def _rows(table: dict) -> list[dict]:
    return [
        {
            "day": key[0],
            "tenant_id": key[1],
            "agent": key[2],
            "task_type": key[3],
            "rung": key[4],
            "model": key[5],
            **value,
        }
        for key, value in table.items()
    ]


def test_independence_and_margin_on_a_fixture_ledger():
    ledger = _calls(1, 1.0, 4) + _calls(4, 0.0, 6, cache=True)
    prices = [{
        "outcome_type": "base.record_enriched",
        "tenant_id": None,
        "unit_price": 2,
        "effective_from": "2026-01-01T00:00:00+00:00",
        "effective_to": None,
    }]
    outcomes = [{
        "ts": NOW,
        "tenant_id": T,
        "agent": "base",
        "outcome_type": "base.record_enriched",
        "quantity": 5,
        "ledger_ids": [],
    }]
    proven = {("reason.brief", "sonnet", 4)}
    call_map = admin.aggregate_calls(ledger)
    outcome_map = admin.aggregate_outcomes(outcomes, prices, {})
    once = admin.merge_econ({}, call_map, outcome_map, proven, None)
    twice = admin.merge_econ(once, call_map, outcome_map, proven, None)
    assert once == twice
    summary = admin._accumulate(_rows(twice), None, None)
    assert summary["calls"] == 10
    assert summary["independence_pct"] == 60
    assert summary["off_paid_pct"] == 60
    assert summary["proven_pct"] == 60
    assert summary["spend_usd"] == 4
    assert summary["booked_usd"] == 10
    assert summary["outcomes"] == 5
    assert summary["margin_pct"] == 60
    assert summary["cost_per_outcome"] == 0.8


def test_rollup_is_idempotent_and_keeps_older_days():
    old = date(2026, 1, 1)
    old_key = (old, T, "tiger", "reason.brief", 1, "sonnet")
    new_key = (DAY, T, "tiger", "reason.brief", 1, "sonnet")
    existing = {old_key: {"calls": 5, "cost": 5.0, "cache_hits": 0, "outcomes": 0.0, "booked": 0.0, "proven_calls": 0}}
    updates = {new_key: {"calls": 2, "cost": 2.0, "cache_hits": 0}}
    once = admin.merge_econ(existing, updates, {}, set(), DAY)
    twice = admin.merge_econ(once, updates, {}, set(), DAY)
    assert once == twice
    assert twice[old_key]["calls"] == 5
    assert twice[new_key]["calls"] == 2


def test_shadow_spend_is_money_but_not_a_client_call():
    rows = _calls(1, 1.0, 1) + [{
        "ts": NOW,
        "tenant_id": T,
        "agent": "tank",
        "task_type": "reason.brief#shadow",
        "rung": 1,
        "model": "haiku",
        "cost_usd": 0.25,
        "cache_hit": False,
    }]
    grouped = admin.aggregate_calls(rows)
    calls = sum(slot["calls"] for slot in grouped.values())
    spend = sum(slot["cost"] for slot in grouped.values())
    assert calls == 1
    assert spend == 1.25


def test_evals_passed_but_too_few_shadow_samples_are_not_proven():
    evidence = admin.build_route_evidence(
        policies=[{
            "task_type": "reason.brief", "model": "haiku", "rung": 1,
            "eval_threshold": 0.97, "min_shadow_samples": 30, "max_reject_rate": 0.05,
        }],
        skills=[{
            "task_type": "reason.brief", "last_eval_score": 0.99, "eval_threshold": 0.97,
            "updated_at": "2026-10-01T00:00:00+00:00",
        }],
        shadows=[{"task_type": "reason.brief", "candidate_model": "haiku", "n": 10, "agreement": 0.99}],
        feedback=[],
        routes={("reason.brief", "haiku", 1)},
        previous={},
        now=NOW,
    )
    assert evidence[0]["proven"] is False
    assert evidence[0]["flag"] is None
    exact = admin.build_route_evidence(
        policies=[{
            "task_type": "reason.brief", "model": "haiku", "rung": 1,
            "eval_threshold": 0.97, "min_shadow_samples": 30, "max_reject_rate": 0.05,
        }],
        skills=[{
            "task_type": "reason.brief", "last_eval_score": 0.97, "eval_threshold": 0.97,
            "updated_at": "2026-10-01T00:00:00+00:00",
        }],
        shadows=[{"task_type": "reason.brief", "candidate_model": "haiku", "n": 34, "agreement": 0.97}],
        feedback=[{"task_type": "reason.brief", "model": "haiku", "accepted": 19, "rejected": 1}],
        routes={("reason.brief", "haiku", 1)},
        previous={},
        now=NOW,
    )
    assert exact[0]["proven"] is True
    assert admin.is_proven(
        eval_passed=True, shadow_applies=True, shadow_n=10, shadow_agreement=0.99,
        min_shadow_samples=30, agreement_threshold=0.97, rejected=0, judged=0, max_reject_rate=0.05,
    ) is False


def test_enough_evidence_is_proven_until_rejections_rise():
    common = dict(
        policies=[{
            "task_type": "reason.brief", "model": "haiku", "rung": 1,
            "eval_threshold": 0.97, "min_shadow_samples": 30, "max_reject_rate": 0.05,
        }],
        skills=[{
            "task_type": "reason.brief", "last_eval_score": 0.99, "eval_threshold": 0.97,
            "updated_at": "2026-10-01T00:00:00+00:00",
        }],
        shadows=[{"task_type": "reason.brief", "candidate_model": "haiku", "n": 40, "agreement": 0.99}],
        routes={("reason.brief", "haiku", 1)},
        now=NOW,
    )
    held = admin.build_route_evidence(
        **common,
        feedback=[{"task_type": "reason.brief", "model": "haiku", "accepted": 20, "rejected": 0}],
        previous={},
    )
    assert held[0]["proven"] is True
    lost = admin.build_route_evidence(
        **common,
        feedback=[{"task_type": "reason.brief", "model": "haiku", "accepted": 8, "rejected": 2}],
        previous={("reason.brief", "haiku", 1): {"proven_at": NOW, "lost_at": None}},
    )
    assert lost[0]["proven"] is False
    assert lost[0]["flag"] == "client rejections are above the threshold"
    assert lost[0]["lost_at"] == NOW


def test_a_newer_failing_skill_version_removes_proven_status():
    evidence = admin.build_route_evidence(
        policies=[{
            "task_type": "reason.brief", "model": "haiku", "rung": 1,
            "eval_threshold": 0.97, "min_shadow_samples": 30, "max_reject_rate": 0.05,
        }],
        skills=[
            {
                "task_type": "reason.brief", "last_eval_score": 0.99, "eval_threshold": 0.97,
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "task_type": "reason.brief", "last_eval_score": 0.4, "eval_threshold": 0.97,
                "updated_at": "2026-10-01T00:00:00+00:00",
            },
        ],
        shadows=[{"task_type": "reason.brief", "candidate_model": "haiku", "n": 40, "agreement": 0.99}],
        feedback=[],
        routes={("reason.brief", "haiku", 1)},
        previous={("reason.brief", "haiku", 1): {"proven_at": NOW, "lost_at": None}},
        now=NOW,
    )
    assert evidence[0]["proven"] is False
    assert evidence[0]["flag"] == "evals have not passed"


def test_code_route_does_not_need_shadow_samples():
    evidence = admin.build_route_evidence(
        policies=[{
            "task_type": "base.find_site", "model": "code", "rung": 3,
            "eval_threshold": 0.95, "min_shadow_samples": 30, "max_reject_rate": 0.05,
        }],
        skills=[{
            "task_type": "base.find_site", "last_eval_score": 0.99, "eval_threshold": 0.95,
            "updated_at": "2026-10-01T00:00:00+00:00",
        }],
        shadows=[],
        feedback=[],
        routes={("base.find_site", "code", 3)},
        previous={},
        now=NOW,
    )
    assert evidence[0]["proven"] is True


def test_focus_list_ranks_spend_and_status():
    policies = [
        {"task_type": "tier0.answer", "model": "haiku", "rung": 1, "candidate_model": None, "eval_threshold": 0.97, "min_shadow_samples": 30},
        {"task_type": "base.extract", "model": "haiku", "rung": 1, "candidate_model": "sonnet", "eval_threshold": 0.97, "min_shadow_samples": 30},
        {"task_type": "reason.brief", "model": "sonnet", "rung": 1, "candidate_model": "haiku", "eval_threshold": 0.97, "min_shadow_samples": 30},
        {"task_type": "tier0.draft", "model": "haiku", "rung": 1, "candidate_model": None, "eval_threshold": 0.97, "min_shadow_samples": 30},
    ]
    shadows = [
        {"task_type": "base.extract", "candidate_model": "sonnet", "n": 10, "agreement": 0.99},
        {"task_type": "reason.brief", "candidate_model": "haiku", "n": 30, "agreement": 0.99},
    ]
    evidence = [{"task_type": "tier0.draft", "model": "haiku", "rung": 1, "proven": True, "eval_score": 0.99, "acceptance_rate": 1}]

    def row(task: str, spend: float) -> dict:
        return {
            "day": TODAY, "tenant_id": T, "agent": "base", "task_type": task, "rung": 1, "model": "haiku",
            "calls": 10, "cost": spend, "cache_hits": 0, "outcomes": 0, "booked": 0, "proven_calls": 0,
        }

    ranked = admin.focus_list(
        policies,
        [row("tier0.answer", 10), row("base.extract", 50), row("reason.brief", 30), row("tier0.draft", 5)],
        shadows,
        evidence,
        TODAY,
        30,
    )
    assert [item["task_type"] for item in ranked] == ["base.extract", "reason.brief", "tier0.answer", "tier0.draft"]
    assert [item["status"] for item in ranked] == ["testing", "ready to promote", "unproven", "proven"]
    assert ranked[0]["next_step"] == "keep testing: 10 of 30 samples"
    assert ranked[1]["next_step"] == "ready to promote"
    assert ranked[2]["next_step"] == "unproven: set a shadow candidate"
    assert ranked[0]["share_of_paid_spend_pct"] == 52.63
    assert ranked[1]["share_of_paid_spend_pct"] == 31.58
    assert ranked[2]["share_of_paid_spend_pct"] == 10.53


def test_base_backfill_is_one_outcome_per_done_record():
    records = [
        {"id": "1", "tenant_id": T, "status": "done", "updated_at": NOW},
        {"id": "2", "tenant_id": T, "status": "done", "updated_at": NOW},
        {"id": "3", "tenant_id": T, "status": "queued", "updated_at": NOW},
        {"id": "1", "tenant_id": T, "status": "done", "updated_at": NOW},
    ]
    first = admin.base_outcome_rows(records, set())
    assert len(first) == 2
    assert {row["ref"] for row in first} == {"1", "2"}
    assert all(row["outcome_type"] == "base.record_enriched" and row["quantity"] == 1 and row["agent"] == "base" for row in first)
    again = admin.base_outcome_rows(records, {("base.record_enriched", row["ref"]) for row in first})
    assert again == []


def test_price_changes_append_a_row():
    old = [{
        "outcome_type": "base.record_enriched", "tenant_id": None, "unit_price": 1,
        "effective_from": "2026-01-01T00:00:00+00:00", "effective_to": None,
    }]
    new = admin.append_price(old, {
        "outcome_type": "base.record_enriched", "tenant_id": None, "unit_price": 2,
        "effective_from": "2026-06-01T00:00:00+00:00", "effective_to": None,
    })
    assert old[0]["unit_price"] == 1
    assert len(new) == 2
    assert admin.unit_price(new, "base.record_enriched", None, "2026-03-01T00:00:00+00:00") == 1
    assert admin.unit_price(new, "base.record_enriched", None, "2026-07-01T00:00:00+00:00") == 2
    both = admin.append_price(new, {
        "outcome_type": "base.record_enriched", "tenant_id": T, "unit_price": 9,
        "effective_from": "2026-01-01T00:00:00+00:00", "effective_to": None,
    })
    assert admin.unit_price(both, "base.record_enriched", T, "2026-07-01T00:00:00+00:00") == 9
    assert admin.unit_price(both, "base.record_enriched", None, "2026-07-01T00:00:00+00:00") == 2


def test_schema_additions_are_idempotent():
    sql = (Path(__file__).resolve().parents[1] / "tank" / "schema.sql").read_text()
    for name in ("tank.price_book", "tank.outcomes", "tank.econ_daily", "tank.route_evidence"):
        assert f"CREATE TABLE IF NOT EXISTS {name}" in sql
    assert "ADD COLUMN IF NOT EXISTS min_shadow_samples" in sql
    assert "ADD COLUMN IF NOT EXISTS max_reject_rate" in sql
    assert "DROP " not in sql.upper()
    assert "RENAME " not in sql.upper()


def test_allowlist_matches_stripped_ids_only():
    os.environ["TERVORY_ADMIN_USER_IDS"] = " user_founder , user_other "
    assert admin.founder_allowed("test", "user_founder")
    assert admin.founder_allowed("test", "user_other")
    assert not admin.founder_allowed("test", "user_nope")
    assert not admin.founder_allowed("wrong", "user_founder")
    assert not admin.founder_allowed("test", "")
    os.environ["TERVORY_ADMIN_USER_IDS"] = ""
    assert not admin.founder_allowed("test", "user_founder")
    os.environ["TERVORY_ADMIN_USER_IDS"] = "user_founder"


def test_non_admin_gets_404_on_every_admin_endpoint():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    os.environ["TANK_API_KEY"] = "test"
    os.environ["TERVORY_ADMIN_USER_IDS"] = "user_founder"
    app = FastAPI()
    app.include_router(admin.router)
    client = TestClient(app)
    body = {"outcome_type": "base.record_enriched", "unit_price": 1}
    seen: set[tuple[str, str]] = set()
    for route in admin.router.routes:
        for method in getattr(route, "methods", set()):
            if method in {"HEAD", "OPTIONS"}:
                continue
            seen.add((method, route.path))
            for headers in (
                {},
                {"x-tank-key": "test", "x-tervory-admin": "user_nope"},
                {"x-tank-key": "wrong", "x-tervory-admin": "user_founder"},
            ):
                res = client.request(method, route.path, headers=headers, json=body)
                assert res.status_code == 404, (method, route.path, headers, res.status_code)
    assert {
        ("GET", "/v1/admin/counters"),
        ("GET", "/v1/admin/series"),
        ("GET", "/v1/admin/graduations"),
        ("GET", "/v1/admin/focus"),
        ("GET", "/v1/admin/price_book"),
        ("PUT", "/v1/admin/price_book"),
    } <= seen


def test_founder_is_not_hidden():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    os.environ["TANK_API_KEY"] = "test"
    os.environ["TERVORY_ADMIN_USER_IDS"] = "user_founder"
    app = FastAPI()
    app.include_router(admin.router)
    client = TestClient(app, raise_server_exceptions=False)
    res = client.get("/v1/admin/counters", headers={"x-tank-key": "test", "x-tervory-admin": "user_founder"})
    assert res.status_code != 404
