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


def _ledger_day(day: date) -> dict:
    return {
        "ts": datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc),
        "tenant_id": T,
        "agent": "tiger",
        "task_type": "reason.brief",
        "rung": 1,
        "model": "haiku",
        "cost_usd": 1.0,
        "cache_hit": False,
    }


def _stored(calls: int, proven: int) -> dict:
    return {
        "calls": calls, "cost": float(calls), "cache_hits": 0,
        "outcomes": 0.0, "booked": 0.0, "proven_calls": proven,
    }


def test_gap_between_rollups_is_filled():
    """Refresh on 3 Oct, next refresh on 10 Oct, and 4–8 Oct are present."""
    early = [_ledger_day(date(2026, 10, d)) for d in (1, 2, 3)]
    first = admin.roll_forward({}, early, {}, set())
    assert date(2026, 10, 4) not in {key[0] for key in first}
    later = early + [_ledger_day(date(2026, 10, d)) for d in range(4, 11)]
    second = admin.roll_forward(first, later, {}, set())
    assert admin.watermark_replace_from({key[0] for key in first}) == date(2026, 10, 2)
    for day_num in range(4, 9):
        key = (date(2026, 10, day_num), T, "tiger", "reason.brief", 1, "haiku")
        assert second[key]["calls"] == 1
    again = admin.roll_forward(second, later, {}, set())
    assert again == second


def test_route_proven_on_oct_10_leaves_oct_1_unproven():
    oct1 = date(2026, 10, 1)
    oct9 = date(2026, 10, 9)
    oct10 = date(2026, 10, 10)

    def key(day: date) -> tuple:
        return (day, T, "tiger", "reason.brief", 1, "haiku")

    existing = {key(oct1): _stored(3, 0), key(oct9): _stored(2, 0)}
    ledger = [_ledger_day(oct9), _ledger_day(oct9), _ledger_day(oct10), _ledger_day(oct10), _ledger_day(oct10)]
    merged = admin.roll_forward(existing, ledger, {}, {("reason.brief", "haiku", 1)})
    assert merged[key(oct1)]["proven_calls"] == 0
    assert merged[key(oct1)]["calls"] == 3
    assert merged[key(oct10)]["calls"] == 3
    assert merged[key(oct10)]["proven_calls"] == 3


def test_reads_do_not_rebuild_and_rollup_sql_is_bounded():
    import inspect

    for name in ("counters", "series", "focus", "graduations", "get_price_book"):
        assert "refresh_econ" not in inspect.getsource(getattr(admin, name))
    assert "ts >= $1::timestamptz" in admin.LEDGER_CALLS_SINCE_SQL
    assert "(timezone('UTC', ts))::date >=" not in admin.LEDGER_CALLS_SINCE_SQL
    assert "INSERT" in admin.BASE_BACKFILL_SQL and "SELECT" in admin.BASE_BACKFILL_SQL
    assert "ON CONFLICT" in admin.BASE_BACKFILL_SQL
    assert admin.REPLACE_WINDOW_SQL == "DELETE FROM tank.econ_daily WHERE day >= $1"
    assert "max(day)" in admin.WATERMARK_SQL
    assert admin.ROLLUP_INTERVAL_SECONDS == 3600
    assert "ts >= $1::timestamptz" in admin.FEEDBACK_SQL
    assert admin.rejection_cutoff(date(2026, 10, 13)) == datetime(2026, 9, 13, tzinfo=timezone.utc)
    main = (Path(__file__).resolve().parents[1] / "tank" / "main.py").read_text()
    assert 'app.include_router(__import__("admin").router)' in main


def test_schema_additions_are_idempotent():
    sql = (Path(__file__).resolve().parents[1] / "tank" / "schema.sql").read_text()
    for name in ("tank.price_book", "tank.outcomes", "tank.econ_daily", "tank.route_evidence", "tank.shadow_pair"):
        assert f"CREATE TABLE IF NOT EXISTS {name}" in sql
    assert "ADD COLUMN IF NOT EXISTS min_shadow_samples" in sql
    assert "ADD COLUMN IF NOT EXISTS max_reject_rate" in sql
    assert "CREATE INDEX IF NOT EXISTS ledger_feedback ON tank.ledger (feedback)" in sql
    assert "CREATE INDEX IF NOT EXISTS ledger_ts ON tank.ledger (ts);" in sql
    assert "ALTER TABLE tank.price_book ADD COLUMN IF NOT EXISTS created_at" in sql
    assert "CREATE TABLE IF NOT EXISTS tank.agent_keys" in sql
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


# ---------- C11b: past booked revenue, price effective date, rollup retry ----------

import asyncio  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

PAST = date(2026, 9, 1)
PAST_TS = datetime(2026, 9, 1, 12, tzinfo=timezone.utc)


def _past_outcome(ledger_ids: list | None = None, ts: datetime = PAST_TS) -> dict:
    return {
        "ts": ts, "tenant_id": T, "agent": "base", "outcome_type": "base.record_enriched",
        "quantity": 1, "ledger_ids": ledger_ids or [],
    }


def _price(effective_from: str, unit: float, created_at: str | None = None) -> dict:
    return {
        "outcome_type": "base.record_enriched", "tenant_id": None, "unit_price": unit,
        "effective_from": effective_from, "effective_to": None, "created_at": created_at,
    }


def test_backdated_price_gives_past_outcomes_booked_revenue():
    """Outcomes on 1 Sep, no price until a price backdated to 1 Aug is saved on 13 Oct."""
    ledger = [_ledger_day(PAST), _ledger_day(date(2026, 10, 12)), _ledger_day(TODAY)]
    outcomes = [_past_outcome(), _past_outcome()]
    first = admin.roll_forward({}, ledger, admin.aggregate_outcomes(outcomes, [], {}), set())
    outcome_key = (PAST, T, "base", "base.record_enriched", 0, "")
    assert first[outcome_key]["outcomes"] == 2
    assert first[outcome_key]["booked"] == 0
    # 1 Sep is far outside the open window (12 Oct onwards) on the next run.
    assert admin.watermark_replace_from({key[0] for key in first}) == date(2026, 10, 12)
    prices = [_price("2026-08-01T00:00:00+00:00", 0.05)]
    second = admin.roll_forward(first, ledger, admin.aggregate_outcomes(outcomes, prices, {}), set())
    assert second[outcome_key]["outcomes"] == 2
    assert second[outcome_key]["booked"] == 0.1
    assert admin.roll_forward(second, ledger, admin.aggregate_outcomes(outcomes, prices, {}), set()) == second


def test_rebuild_leaves_past_proven_calls_alone():
    """The route became proven later. 1 Sep keeps proven_calls 0 while its booked revenue is rebuilt."""
    call_key = (PAST, T, "tiger", "reason.brief", 1, "haiku")
    today_key = (TODAY, T, "tiger", "reason.brief", 1, "haiku")
    existing = {
        call_key: _stored(3, 0),
        (date(2026, 10, 12), T, "tiger", "reason.brief", 1, "haiku"): _stored(1, 0),
    }
    ledger = [_ledger_day(TODAY), _ledger_day(TODAY)]
    grains = {"call-1": {**_ledger_day(PAST), "id": "call-1"}}
    outcomes = admin.aggregate_outcomes(
        [_past_outcome(["call-1"])], [_price("2026-01-01T00:00:00+00:00", 2)], grains,
    )
    merged = admin.roll_forward(existing, ledger, outcomes, {("reason.brief", "haiku", 1)})
    assert merged[call_key]["calls"] == 3
    assert merged[call_key]["cost"] == 3
    assert merged[call_key]["proven_calls"] == 0
    assert merged[call_key]["booked"] == 2
    assert merged[today_key]["proven_calls"] == 2


def test_outcome_today_on_an_old_call_still_counts():
    """An outcome recorded today whose first ledger call is from 1 Sep counts on 1 Sep."""
    call_key = (PAST, T, "tiger", "reason.brief", 1, "haiku")
    existing = {call_key: _stored(1, 0), (date(2026, 10, 12), T, "tiger", "reason.brief", 1, "haiku"): _stored(1, 0)}
    grains = {"call-1": {**_ledger_day(PAST), "id": "call-1"}}
    today_ts = datetime(2026, 10, 13, 9, tzinfo=timezone.utc)
    outcomes = admin.aggregate_outcomes(
        [_past_outcome(["call-1"], ts=today_ts)], [_price("2026-01-01T00:00:00+00:00", 3)], grains,
    )
    merged = admin.roll_forward(existing, [], outcomes, set())
    assert merged[call_key]["outcomes"] == 1
    assert merged[call_key]["booked"] == 3
    assert "bucket.day >=" not in admin.OUTCOME_UPSERT_ALL_SQL
    assert "$1" not in admin.OUTCOME_UPSERT_ALL_SQL
    assert not hasattr(admin, "OUTCOME_UPSERT_SINCE_SQL")


class _FakeConn:
    def __init__(self, max_day: date | None) -> None:
        self.max_day = max_day
        self.executed: list[str] = []

    @asynccontextmanager
    async def transaction(self):
        yield

    async def execute(self, sql: str, *args) -> str:
        self.executed.append(sql)
        return ""

    async def executemany(self, sql: str, rows) -> None:
        self.executed.append(sql)

    async def fetchval(self, sql: str, *args):
        return self.max_day

    async def fetch(self, sql: str, *args) -> list:
        return []


def _rollup_sql(max_day: date | None) -> list[str]:
    conn = _FakeConn(max_day)
    asyncio.run(admin.refresh_econ(conn, TODAY))
    return conn.executed


def test_rollup_rebuilds_outcomes_for_every_day_in_the_locked_transaction():
    for max_day in (date(2026, 10, 12), None):
        executed = _rollup_sql(max_day)
        assert executed[0] == "SELECT pg_advisory_xact_lock($1)"
        tail = executed[-3:]
        assert tail == [admin.OUTCOME_ZERO_SQL, admin.OUTCOME_UPSERT_ALL_SQL, admin.DROP_EMPTY_SQL]
        calls = admin.LEDGER_CALLS_SINCE_SQL if max_day else admin.LEDGER_CALLS_ALL_SQL
        assert executed.index(calls) < executed.index(admin.OUTCOME_ZERO_SQL)
    windowed = _rollup_sql(date(2026, 10, 12))
    assert admin.REPLACE_WINDOW_SQL in windowed
    assert "WHERE day" not in admin.OUTCOME_ZERO_SQL
    assert "calls = 0" in admin.DROP_EMPTY_SQL and "outcomes = 0" in admin.DROP_EMPTY_SQL


def test_same_day_prices_the_last_saved_wins():
    early = _price("2026-10-01T00:00:00+00:00", 1, "2026-10-01T08:00:00+00:00")
    late = _price("2026-10-01T00:00:00+00:00", 4, "2026-10-01T09:00:00+00:00")
    for rows in ([early, late], [late, early]):
        assert admin.unit_price(rows, "base.record_enriched", T, "2026-10-02T00:00:00+00:00") == 4
    assert "p.created_at DESC" in admin.OUTCOME_UPSERT_ALL_SQL


def test_price_start_validates_the_effective_date():
    assert admin.price_start(None, TODAY) is None
    assert admin.price_start("", TODAY) is None
    assert admin.price_start("2026-08-01", TODAY) == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert admin.price_start("2026-08-01T06:30:00Z", TODAY) == datetime(2026, 8, 1, 6, 30, tzinfo=timezone.utc)
    assert admin.price_start("2026-08-01T06:30:00", TODAY) == datetime(2026, 8, 1, 6, 30, tzinfo=timezone.utc)
    assert admin.price_start("2027-10-13", TODAY) == datetime(2027, 10, 13, tzinfo=timezone.utc)
    for bad in ("yesterday", "2026-13-01", "2026-02-30", "01/08/2026", "1999-12-31", "2027-10-15", "0026-10-01"):
        try:
            admin.price_start(bad, TODAY)
        except ValueError as exc:
            assert str(exc).startswith("Effective from")
        else:
            raise AssertionError(bad)


class _FakePool:
    def __init__(self) -> None:
        self.args: tuple | None = None

    @asynccontextmanager
    async def acquire(self):
        pool = self

        class Conn:
            async def fetchrow(self, sql: str, *args):
                pool.args = args
                return {
                    "id": "11111111-1111-1111-1111-111111111111", "tenant_id": None, "outcome_type": args[1],
                    "unit_price": args[2], "currency": args[3],
                    "effective_from": args[4] or datetime(2026, 10, 13, tzinfo=timezone.utc),
                    "effective_to": None, "note": args[5],
                }

        yield Conn()


def test_put_price_book_checks_effective_from(monkeypatch):
    fake = _FakePool()
    monkeypatch.setattr(admin, "_pool", lambda: fake)
    monkeypatch.setattr(admin, "utc_today", lambda: TODAY)

    def put(**extra):
        body = admin.PriceBody(outcome_type="base.record_enriched", unit_price=0.05, **extra)
        return asyncio.run(admin.put_price_book(body))

    saved = put(effective_from="2026-08-01")
    assert fake.args[4] == datetime(2026, 8, 1, tzinfo=timezone.utc)
    assert saved["effective_from"] == "2026-08-01T00:00:00+00:00"
    put()
    assert fake.args[4] is None
    for bad in ("not a date", "1990-01-01", "2030-01-01"):
        fake.args = None
        try:
            put(effective_from=bad)
        except admin.HTTPException as exc:
            assert exc.status_code == 400
            assert "Effective from" in str(exc.detail)
        else:
            raise AssertionError(bad)
        assert fake.args is None


def test_rollup_retries_in_five_minutes_and_logs_a_safe_message(monkeypatch, caplog):
    import logging

    monkeypatch.setenv("TANK_API_KEY", "test-secret-key")
    waits: list[float] = []

    def boom():
        raise RuntimeError("could not connect to postgresql://tank:hunter22@db:5432/tank with test-secret-key")

    async def fake_sleep(seconds: float) -> None:
        waits.append(seconds)
        raise asyncio.CancelledError

    monkeypatch.setattr(admin, "_pool", boom)
    monkeypatch.setattr(admin.asyncio, "sleep", fake_sleep)
    with caplog.at_level(logging.WARNING, logger="tank.admin"):
        try:
            asyncio.run(admin._rollup_loop())
        except asyncio.CancelledError:
            pass
    assert waits == [admin.ROLLUP_RETRY_SECONDS] == [300]
    text = caplog.text
    assert "RuntimeError" in text and "could not connect" in text
    assert "hunter22" not in text and "test-secret-key" not in text


def test_safe_error_never_shows_query_detail():
    class FakePgError(Exception):
        sqlstate = "23505"
        message = "duplicate key value violates unique constraint \"econ_daily_pkey\""
        detail = "Key (day)=(2026-09-01) already exists."
        query = "INSERT INTO tank.econ_daily VALUES ($1)"

    shown = admin.safe_error(FakePgError("ignored"))
    assert shown.startswith("FakePgError [23505]: duplicate key value")
    assert "Key (day)" not in shown and "INSERT" not in shown
    assert len(admin.safe_error(RuntimeError("x" * 1000))) < 340
