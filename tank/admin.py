"""Founder console. Platform-wide, and invisible to everyone else.

Every route on this router returns 404 unless the caller sends the Workspace
key and a Clerk user id listed in TERVORY_ADMIN_USER_IDS. The numbers are
our own measurements: a route is proven only when its evals have passed,
its shadow sample is large enough and in agreement, and clients are not
rejecting it above the policy's ceiling.
"""

from __future__ import annotations

import hmac
import os
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

# Rungs 2–4 are off a paid model (our model, code, cache). Rung 1 is a paid model.
OFF_PAID_RUNGS = (2, 3, 4)
SHADOW_RUNGS = (1, 2)
DEFAULT_MIN_SHADOW = 30
DEFAULT_MAX_REJECT = 0.05
DEFAULT_AGREEMENT = 0.97

Key = tuple[date, str, str, str, int, str]


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def as_day(value: Any) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).date()
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def as_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day)
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_dt(value).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


def founder_allowed(tank_key: str, user_id: str) -> bool:
    """True only for the Workspace key plus a listed Clerk user id."""
    expected = os.environ.get("TANK_API_KEY", "")
    if not expected or not tank_key or not user_id:
        return False
    try:
        if not hmac.compare_digest(tank_key, expected):
            return False
    except Exception:
        return False
    allowed = {part.strip() for part in os.environ.get("TERVORY_ADMIN_USER_IDS", "").split(",") if part.strip()}
    return user_id in allowed


async def require_admin(
    x_tank_key: str = Header(default=""),
    x_tervory_admin: str = Header(default=""),
) -> None:
    if not founder_allowed(x_tank_key, x_tervory_admin):
        raise HTTPException(status_code=404, detail="not found")


router = APIRouter(prefix="/v1/admin", include_in_schema=False, dependencies=[Depends(require_admin)])


# ---------- proven ----------

def _meets(value: float, bar: float) -> bool:
    """Compare at the same precision the ledger stores (4 decimal places)."""
    return round(value, 4) >= round(bar, 4)


def eval_from_skill(skill: dict[str, Any] | None) -> tuple[bool, float | None]:
    if not skill or skill.get("last_eval_score") is None:
        return False, None
    score = float(skill["last_eval_score"])
    bar = float(skill["eval_threshold"]) if skill.get("eval_threshold") is not None else DEFAULT_AGREEMENT
    return _meets(score, bar), score


def pick_latest_skills(skills: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The newest skill version for a task type. A later failure replaces an older pass."""
    best: dict[str, dict[str, Any]] = {}
    for skill in skills:
        task = skill.get("task_type")
        if not task:
            continue
        prev = best.get(task)
        if prev is None or as_dt(skill.get("updated_at") or "1970-01-01") >= as_dt(prev.get("updated_at") or "1970-01-01"):
            best[str(task)] = skill
    return best


def shadow_for_model(shadows: list[dict[str, Any]]) -> dict[tuple[str, str], tuple[int, float]]:
    acc: dict[tuple[str, str], list[float]] = {}
    for row in shadows:
        n = int(row.get("n") or 0)
        if n <= 0 or row.get("agreement") is None:
            continue
        key = (str(row["task_type"]), str(row["candidate_model"]))
        slot = acc.setdefault(key, [0.0, 0.0])
        slot[0] += n
        slot[1] += float(row["agreement"]) * n
    return {key: (int(slot[0]), slot[1] / slot[0]) for key, slot in acc.items()}


def prove_reason(
    *,
    eval_passed: bool,
    shadow_applies: bool,
    shadow_n: int,
    shadow_agreement: float | None,
    min_shadow_samples: int,
    agreement_threshold: float,
    rejected: int,
    judged: int,
    max_reject_rate: float,
) -> tuple[bool, str | None]:
    """A route is proven only on our measurements. Any miss returns why."""
    if not eval_passed:
        return False, "evals have not passed"
    if shadow_applies and shadow_n < min_shadow_samples:
        return False, "too few shadow samples"
    if shadow_applies and (shadow_agreement is None or not _meets(shadow_agreement, agreement_threshold)):
        return False, "shadow agreement is below the bar"
    if judged > 0 and round(rejected / judged, 4) > round(max_reject_rate, 4):
        return False, "client rejections are above the threshold"
    return True, None


def is_proven(**kwargs: Any) -> bool:
    return prove_reason(**kwargs)[0]


def build_route_evidence(
    *,
    policies: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    shadows: list[dict[str, Any]],
    feedback: list[dict[str, Any]],
    routes: set[tuple[str, str, int]],
    previous: dict[tuple[str, str, int], dict[str, Any]],
    now: datetime,
) -> list[dict[str, Any]]:
    by_policy = {str(p["task_type"]): p for p in policies}
    by_skill = pick_latest_skills(skills)
    by_shadow = shadow_for_model(shadows)
    by_feedback: dict[tuple[str, str], tuple[int, int]] = {}
    for row in feedback:
        by_feedback[(str(row["task_type"]), str(row["model"]))] = (int(row.get("accepted") or 0), int(row.get("rejected") or 0))
    wanted = set(routes)
    for policy in policies:
        wanted.add((str(policy["task_type"]), str(policy["model"]), int(policy["rung"])))
    rows: list[dict[str, Any]] = []
    for task, model, rung in sorted(wanted):
        policy = by_policy.get(task, {})
        passed, score = eval_from_skill(by_skill.get(task))
        shadow_n, agreement = by_shadow.get((task, model), (0, None))
        accepted, rejected = by_feedback.get((task, model), (0, 0))
        judged = accepted + rejected
        bar = float(policy["eval_threshold"]) if policy.get("eval_threshold") is not None else DEFAULT_AGREEMENT
        minimum = int(policy["min_shadow_samples"]) if policy.get("min_shadow_samples") is not None else DEFAULT_MIN_SHADOW
        ceiling = float(policy["max_reject_rate"]) if policy.get("max_reject_rate") is not None else DEFAULT_MAX_REJECT
        proven, reason = prove_reason(
            eval_passed=passed,
            shadow_applies=rung in SHADOW_RUNGS,
            shadow_n=shadow_n,
            shadow_agreement=agreement,
            min_shadow_samples=minimum,
            agreement_threshold=bar,
            rejected=rejected,
            judged=judged,
            max_reject_rate=ceiling,
        )
        prev = previous.get((task, model, rung), {})
        proven_at = prev.get("proven_at")
        lost_at = prev.get("lost_at")
        flag = None
        if proven:
            proven_at = proven_at or now
            lost_at = None
        elif proven_at is not None:
            flag = reason
            lost_at = lost_at or now
        else:
            lost_at = None
        rows.append({
            "task_type": task,
            "model": model,
            "rung": rung,
            "eval_score": score,
            "shadow_agreement": agreement,
            "shadow_n": shadow_n,
            "acceptance_rate": (accepted / judged) if judged else None,
            "judged": judged,
            "rejected": rejected,
            "proven": proven,
            "proven_at": proven_at,
            "lost_at": lost_at,
            "flag": flag,
        })
    return rows


# ---------- money ----------

def unit_price(rows: list[dict[str, Any]], outcome_type: str, tenant_id: Any, at: Any) -> float | None:
    """Tenant price wins over the default. The latest effective row wins. Never edits an old row."""
    moment = as_dt(at)
    tenant = str(tenant_id) if tenant_id is not None else None
    covering: list[dict[str, Any]] = []
    for row in rows:
        if row["outcome_type"] != outcome_type:
            continue
        row_tenant = str(row["tenant_id"]) if row.get("tenant_id") is not None else None
        if row_tenant is not None and row_tenant != tenant:
            continue
        start = as_dt(row["effective_from"])
        end = as_dt(row["effective_to"]) if row.get("effective_to") else None
        if start <= moment and (end is None or end > moment):
            covering.append(row)
    specific = [row for row in covering if row.get("tenant_id") is not None]
    pool = specific or [row for row in covering if row.get("tenant_id") is None]
    if not pool:
        return None
    best = max(pool, key=lambda row: as_dt(row["effective_from"]))
    return float(best["unit_price"])


def append_price(existing: list[dict[str, Any]], new_row: dict[str, Any]) -> list[dict[str, Any]]:
    return [*existing, new_row]


def base_outcome_rows(records: list[dict[str, Any]], existing_refs: set[tuple[str, str]]) -> list[dict[str, Any]]:
    """One base.record_enriched per done record. Running it again adds nothing."""
    seen = set(existing_refs)
    out: list[dict[str, Any]] = []
    for record in records:
        if record.get("status") != "done":
            continue
        ref = str(record["id"])
        key = ("base.record_enriched", ref)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "ts": record.get("updated_at"),
            "tenant_id": record["tenant_id"],
            "agent": "base",
            "outcome_type": "base.record_enriched",
            "quantity": 1,
            "ref": ref,
            "ledger_ids": [],
        })
    return out


def _empty_call() -> dict[str, float]:
    return {"calls": 0, "cost": 0.0, "cache_hits": 0}


def aggregate_calls(ledger_rows: list[dict[str, Any]]) -> dict[Key, dict[str, float]]:
    """Group a fixture or a ledger read. Shadow rows add cost and not a client call."""
    out: dict[Key, dict[str, float]] = {}
    for row in ledger_rows:
        task = str(row["task_type"])
        day = as_day(row.get("day") or row["ts"])
        tenant = str(row["tenant_id"])
        model = str(row["model"])
        cost = num(row.get("cost_usd", row.get("cost")))
        if task.endswith("#shadow"):
            key = (day, tenant, "tank", task, 1, model)
            slot = out.setdefault(key, _empty_call())
            slot["cost"] += cost
            continue
        key = (day, tenant, str(row["agent"]), task, int(row["rung"]), model)
        slot = out.setdefault(key, _empty_call())
        slot["calls"] += int(row.get("calls") or 1)
        slot["cost"] += cost
        if row.get("cache_hit"):
            slot["cache_hits"] += int(row.get("calls") or 1)
    return out


def outcome_bucket(outcome: dict[str, Any], grains: dict[str, dict[str, Any]]) -> Key:
    ids = outcome.get("ledger_ids") or []
    if ids:
        grain = grains.get(str(ids[0]))
        if grain and not str(grain["task_type"]).endswith("#shadow"):
            return (
                as_day(grain.get("day") or grain["ts"]),
                str(grain["tenant_id"]),
                str(grain["agent"]),
                str(grain["task_type"]),
                int(grain["rung"]),
                str(grain["model"]),
            )
    return (as_day(outcome["ts"]), str(outcome["tenant_id"]), str(outcome["agent"]), str(outcome["outcome_type"]), 0, "")


def aggregate_outcomes(
    outcomes: list[dict[str, Any]],
    prices: list[dict[str, Any]],
    grains: dict[str, dict[str, Any]],
) -> dict[Key, dict[str, float]]:
    out: dict[Key, dict[str, float]] = {}
    for outcome in outcomes:
        qty = num(outcome.get("quantity"), 1.0)
        price = unit_price(prices, str(outcome["outcome_type"]), outcome.get("tenant_id"), outcome["ts"])
        booked = qty * price if price is not None else 0.0
        key = outcome_bucket(outcome, grains)
        slot = out.setdefault(key, {"outcomes": 0.0, "booked": 0.0})
        slot["outcomes"] += qty
        slot["booked"] += booked
    return out


def merge_econ(
    existing: dict[Key, dict[str, Any]],
    call_updates: dict[Key, dict[str, float]],
    outcome_updates: dict[Key, dict[str, float]],
    proven_keys: set[tuple[str, str, int]],
    replace_from: date | None,
) -> dict[Key, dict[str, Any]]:
    """Replace call figures for the days being rolled up. Do not add them twice.

    replace_from None means call_updates is the full call picture. Otherwise
    only days on or after that date are replaced, and older days stay so
    pruning the ledger cannot erase them.
    """
    keys = set(existing) | set(call_updates) | set(outcome_updates)
    merged: dict[Key, dict[str, Any]] = {}
    for key in keys:
        prev = existing.get(key)
        replace_calls = replace_from is None or key[0] >= replace_from
        if replace_calls:
            src = call_updates.get(key)
            calls = int(src["calls"]) if src else 0
            cost = float(src["cost"]) if src else 0.0
            cache_hits = int(src["cache_hits"]) if src else 0
        else:
            calls = int(prev["calls"]) if prev else 0
            cost = float(prev["cost"]) if prev else 0.0
            cache_hits = int(prev["cache_hits"]) if prev else 0
        outcome = outcome_updates.get(key)
        outcomes = float(outcome["outcomes"]) if outcome else 0.0
        booked = float(outcome["booked"]) if outcome else 0.0
        proven_calls = calls if (key[3], key[5], key[4]) in proven_keys else 0
        if calls == 0 and cost == 0 and cache_hits == 0 and outcomes == 0 and booked == 0:
            continue
        merged[key] = {
            "calls": calls,
            "cost": round(cost, 6),
            "cache_hits": cache_hits,
            "outcomes": round(outcomes, 4),
            "booked": round(booked, 6),
            "proven_calls": proven_calls,
        }
    return merged


def pack_metrics(calls: int, proven_calls: int, off_paid_calls: int, spend: float, outcomes: float, booked: float) -> dict[str, Any]:
    off = round(100 * off_paid_calls / calls, 2) if calls else None
    return {
        "calls": calls,
        "spend_usd": round(spend, 6),
        "outcomes": round(outcomes, 4),
        "booked_usd": round(booked, 4),
        "margin_pct": round(100 * (booked - spend) / booked, 2) if booked else None,
        "cost_per_outcome": round(spend / outcomes, 6) if outcomes else None,
        "proven_pct": round(100 * proven_calls / calls, 2) if calls else None,
        "off_paid_pct": off,
        "independence_pct": off,
    }


def _accumulate(rows: list[dict[str, Any]], start: date | None, end: date | None) -> dict[str, Any]:
    calls = proven = off = 0
    spend = outcomes = booked = 0.0
    for row in rows:
        day = row["day"]
        if start is not None and day < start:
            continue
        if end is not None and day >= end:
            continue
        rung = int(row["rung"])
        if rung != 0:
            calls += int(row["calls"])
            proven += int(row["proven_calls"])
            if rung in OFF_PAID_RUNGS:
                off += int(row["calls"])
        spend += float(row["cost"])
        outcomes += float(row["outcomes"])
        booked += float(row["booked"])
    return pack_metrics(calls, proven, off, spend, outcomes, booked)


def window_bounds(today: date, days: int) -> tuple[date, date]:
    start = today - timedelta(days=days - 1)
    return start, today + timedelta(days=1)


def counter_report(rows: list[dict[str, Any]], today: date) -> dict[str, Any]:
    last_start, last_end = window_bounds(today, 30)
    prev_start = last_start - timedelta(days=30)
    lifetime = _accumulate(rows, None, None)
    last = _accumulate(rows, last_start, last_end)
    prev = _accumulate(rows, prev_start, last_start)

    def gap(key: str) -> float | None:
        a, b = last[key], prev[key]
        if a is None or b is None:
            return None
        return round(a - b, 2)

    return {
        "note": "Booked revenue is outcomes times the price book. Billing is not connected yet.",
        "lifetime": lifetime,
        "last_30_days": last,
        "previous_30_days": prev,
        "change": {
            "proven_pct": gap("proven_pct"),
            "off_paid_pct": gap("off_paid_pct"),
            "independence_pct": gap("independence_pct"),
            "margin_pct": gap("margin_pct"),
            "booked_usd": round(last["booked_usd"] - prev["booked_usd"], 2),
            "spend_usd": round(last["spend_usd"] - prev["spend_usd"], 2),
            "cost_per_outcome": gap("cost_per_outcome"),
        },
    }


def series_report(rows: list[dict[str, Any]], today: date, days: int, group: str) -> dict[str, Any]:
    start, end = window_bounds(today, days)
    points: dict[tuple[date, str], dict[str, Any]] = {}
    totals: dict[str, dict[str, Any]] = {}

    def bucket(key: str) -> dict[str, Any]:
        return totals.setdefault(key, {
            "calls": 0, "proven_calls": 0, "off_paid_calls": 0, "spend": 0.0, "outcomes": 0.0, "booked": 0.0,
        })

    for row in rows:
        day = row["day"]
        if day < start or day >= end:
            continue
        if group == "agent":
            gkey = str(row["agent"])
        elif group == "tenant":
            gkey = str(row["tenant_id"])
        else:
            gkey = str(row["task_type"])
        rung = int(row["rung"])
        point = points.setdefault((day, gkey), {
            "calls": 0, "proven_calls": 0, "off_paid_calls": 0, "spend": 0.0, "outcomes": 0.0, "booked": 0.0,
            "calls_by_rung": {"1": 0, "2": 0, "3": 0, "4": 0},
        })
        total = bucket(gkey)
        calls = int(row["calls"]) if rung != 0 else 0
        proven_calls = int(row["proven_calls"]) if rung != 0 else 0
        off_calls = calls if rung in OFF_PAID_RUNGS else 0
        for target in (point, total):
            target["calls"] += calls
            target["proven_calls"] += proven_calls
            target["off_paid_calls"] += off_calls
            target["spend"] += float(row["cost"])
            target["outcomes"] += float(row["outcomes"])
            target["booked"] += float(row["booked"])
        if rung in (1, 2, 3, 4):
            point["calls_by_rung"][str(rung)] += calls

    point_rows = []
    for (day, gkey), point in sorted(points.items()):
        packed = pack_metrics(point["calls"], point["proven_calls"], point["off_paid_calls"], point["spend"], point["outcomes"], point["booked"])
        point_rows.append({
            "day": day.isoformat(),
            "key": gkey,
            "calls_by_rung": point["calls_by_rung"],
            "proven_calls": point["proven_calls"],
            "off_paid_calls": point["off_paid_calls"],
            **packed,
        })
    total_rows = []
    for gkey, total in sorted(totals.items(), key=lambda item: (-item[1]["spend"], item[0])):
        packed = pack_metrics(total["calls"], total["proven_calls"], total["off_paid_calls"], total["spend"], total["outcomes"], total["booked"])
        total_rows.append({"key": gkey, **packed})
    return {"days": days, "group": group, "points": point_rows, "totals": total_rows}


def focus_status(
    *,
    candidate: str | None,
    sample_size: int,
    agreement: float | None,
    threshold: float,
    min_samples: int,
    proven: bool,
) -> tuple[str, str]:
    eligible = bool(candidate) and sample_size >= min_samples and agreement is not None and agreement >= threshold
    if candidate and eligible:
        return "ready to promote", "ready to promote"
    if candidate:
        return "testing", f"keep testing: {sample_size} of {min_samples} samples"
    if proven:
        return "proven", "proven"
    return "unproven", "unproven: set a shadow candidate"


def focus_list(
    policies: list[dict[str, Any]],
    econ_rows: list[dict[str, Any]],
    shadows: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    today: date,
    days: int,
) -> list[dict[str, Any]]:
    start, end = window_bounds(today, days)
    by_shadow = shadow_for_model(shadows)
    proven = {(row["task_type"], row["model"], int(row["rung"])) for row in evidence if row.get("proven")}
    stats: dict[str, dict[str, float]] = {}
    for row in econ_rows:
        if row["day"] < start or row["day"] >= end:
            continue
        task = str(row["task_type"])
        if task.endswith("#shadow"):
            continue
        slot = stats.setdefault(task, {"calls": 0, "spend": 0.0, "cache_hits": 0, "paid_spend": 0.0})
        rung = int(row["rung"])
        if rung != 0:
            slot["calls"] += int(row["calls"])
            slot["cache_hits"] += int(row["cache_hits"])
        if rung == 1:
            slot["paid_spend"] += float(row["cost"])
        slot["spend"] += float(row["cost"])
    paid = [p for p in policies if int(p.get("rung") or 1) == 1 and not str(p["task_type"]).endswith("#shadow")]
    total_paid = sum(stats.get(str(p["task_type"]), {}).get("paid_spend", 0.0) for p in paid)
    rows = []
    for policy in paid:
        task = str(policy["task_type"])
        model = str(policy["model"])
        rung = int(policy["rung"])
        slot = stats.get(task, {"calls": 0, "spend": 0.0, "cache_hits": 0, "paid_spend": 0.0})
        candidate = policy.get("candidate_model") or None
        sample_size, agreement = by_shadow.get((task, candidate), (0, None)) if candidate else (0, None)
        minimum = int(policy["min_shadow_samples"]) if policy.get("min_shadow_samples") is not None else DEFAULT_MIN_SHADOW
        threshold = float(policy["eval_threshold"]) if policy.get("eval_threshold") is not None else DEFAULT_AGREEMENT
        status, nxt = focus_status(
            candidate=candidate,
            sample_size=sample_size,
            agreement=agreement,
            threshold=threshold,
            min_samples=minimum,
            proven=(task, model, rung) in proven,
        )
        calls = int(slot["calls"])
        paid_spend = float(slot["paid_spend"])
        rows.append({
            "task_type": task,
            "model": model,
            "rung": rung,
            "calls": calls,
            "spend_usd": round(paid_spend, 6),
            "share_of_paid_spend_pct": round(100 * paid_spend / total_paid, 2) if total_paid else 0.0,
            "cache_hit_rate_pct": round(100 * slot["cache_hits"] / calls, 2) if calls else None,
            "candidate_model": candidate,
            "agreement": agreement,
            "sample_size": sample_size,
            "min_samples": minimum,
            "status": status,
            "next_step": nxt,
            "eval_score": next((e["eval_score"] for e in evidence if e["task_type"] == task and e["model"] == model and int(e["rung"]) == rung), None),
            "acceptance_rate": next((e["acceptance_rate"] for e in evidence if e["task_type"] == task and e["model"] == model and int(e["rung"]) == rung), None),
        })
    rows.sort(key=lambda row: (-row["spend_usd"], row["task_type"]))
    return rows


def saving_pct(primary: float | None, candidate: float | None) -> float | None:
    if primary is None or candidate is None or primary <= 0:
        return None
    return round((1 - candidate / primary) * 100, 1)


def graduation_rows(logs: list[dict[str, Any]], shadows: list[dict[str, Any]], today: date, days: int) -> list[dict[str, Any]]:
    start, end = window_bounds(today, days)
    avgs: dict[tuple[str, str, str], tuple[float, float]] = {}
    for row in shadows:
        if row.get("prim_cost") is None or row.get("cand_cost") is None:
            continue
        avgs[(str(row["task_type"]), str(row["primary_model"]), str(row["candidate_model"]))] = (float(row["prim_cost"]), float(row["cand_cost"]))
    out = []
    for log in logs:
        if log.get("action") not in ("promote", "rollback"):
            continue
        moment = as_dt(log["created_at"])
        if moment.date() < start or moment.date() >= end:
            continue
        task = str(log["task_type"])
        source = log.get("from_model")
        dest = log.get("to_model")
        direct = avgs.get((task, str(source), str(dest)))
        flipped = avgs.get((task, str(dest), str(source)))
        if direct:
            saved = saving_pct(direct[0], direct[1])
        elif flipped:
            saved = saving_pct(flipped[1], flipped[0])
        else:
            saved = None
        out.append({
            "id": str(log["id"]),
            "at": moment.isoformat(),
            "day": moment.date().isoformat(),
            "task_type": task,
            "action": log["action"],
            "from_model": source,
            "to_model": dest,
            "saving_pct": saved,
        })
    out.sort(key=lambda row: row["at"])
    return out


# ---------- database ----------

def _pool() -> asyncpg.Pool:
    from main import pool as get_pool
    return get_pool()


def _records(rows: list[Any]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def _econ_map(rows: list[dict[str, Any]]) -> dict[Key, dict[str, Any]]:
    mapped: dict[Key, dict[str, Any]] = {}
    for row in rows:
        key = (as_day(row["day"]), str(row["tenant_id"]), str(row["agent"]), str(row["task_type"]), int(row["rung"]), str(row["model"]))
        mapped[key] = {
            "calls": int(row["calls"]),
            "cost": num(row["cost_usd"]),
            "cache_hits": int(row["cache_hits"]),
            "outcomes": num(row["outcomes"]),
            "booked": num(row["booked_usd"]),
            "proven_calls": int(row["proven_calls"]),
        }
    return mapped


def _econ_list(mapped: dict[Key, dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"day": key[0], "tenant_id": key[1], "agent": key[2], "task_type": key[3], "rung": key[4], "model": key[5], **value}
        for key, value in mapped.items()
    ]


async def refresh_econ(conn: asyncpg.Connection, today: date | None = None) -> None:
    """Idempotent rollup: backfill once, then replace yesterday and today."""
    today = today or utc_today()
    now = datetime.now(timezone.utc)
    async with conn.transaction():
        await conn.execute("SELECT pg_advisory_xact_lock(81111)")
        done = await conn.fetch("SELECT id, tenant_id, status, updated_at FROM base.records WHERE status = 'done'")
        existing_refs = await conn.fetch("SELECT outcome_type, ref FROM tank.outcomes WHERE ref IS NOT NULL")
        fresh_outcomes = base_outcome_rows(_records(done), {(row["outcome_type"], row["ref"]) for row in existing_refs})
        if fresh_outcomes:
            await conn.executemany(
                """
                INSERT INTO tank.outcomes (ts, tenant_id, agent, outcome_type, quantity, ref, ledger_ids)
                VALUES ($1, $2, $3, $4, $5, $6, $7::uuid[])
                ON CONFLICT (outcome_type, ref) WHERE ref IS NOT NULL DO NOTHING
                """,
                [
                    (row["ts"], row["tenant_id"], row["agent"], row["outcome_type"], row["quantity"], row["ref"], [])
                    for row in fresh_outcomes
                ],
            )
        policies = _records(await conn.fetch(
            """
            SELECT task_type, rung, model, candidate_model, eval_threshold, min_shadow_samples, max_reject_rate
            FROM tank.policy WHERE tenant_id IS NULL
            """
        ))
        shadows = _records(await conn.fetch(
            """
            SELECT task_type, primary_model, candidate_model,
                   count(*) FILTER (WHERE agreement IS NOT NULL)::int AS n,
                   avg(agreement) FILTER (WHERE agreement IS NOT NULL) AS agreement,
                   avg(primary_cost_usd) AS prim_cost,
                   avg(candidate_cost_usd) AS cand_cost
            FROM tank.shadow
            GROUP BY task_type, primary_model, candidate_model
            """
        ))
        skills = _records(await conn.fetch(
            """
            SELECT task_type, last_eval_score, eval_threshold, updated_at
            FROM tank.skills WHERE task_type IS NOT NULL
            """
        ))
        feedback = _records(await conn.fetch(
            """
            SELECT task_type, model,
                   count(*) FILTER (WHERE feedback = 'accepted')::int AS accepted,
                   count(*) FILTER (WHERE feedback = 'rejected')::int AS rejected
            FROM tank.ledger
            WHERE feedback IN ('accepted', 'rejected')
            GROUP BY task_type, model
            """
        ))
        previous_rows = _records(await conn.fetch("SELECT * FROM tank.route_evidence"))
        previous = {(row["task_type"], row["model"], int(row["rung"])): row for row in previous_rows}
        existing = _econ_map(_records(await conn.fetch("SELECT * FROM tank.econ_daily")))
        since = None if not existing else today - timedelta(days=1)
        ledger = _records(await conn.fetch(
            """
            SELECT ts, tenant_id, agent, task_type, rung, model, cost_usd, cache_hit
            FROM tank.ledger
            WHERE ($1::date IS NULL OR (timezone('UTC', ts))::date >= $1)
            """,
            since,
        ))
        call_map = aggregate_calls(ledger)
        outcome_rows = _records(await conn.fetch(
            "SELECT ts, tenant_id, agent, outcome_type, quantity, ref, ledger_ids FROM tank.outcomes"
        ))
        prices = _records(await conn.fetch(
            "SELECT tenant_id, outcome_type, unit_price, effective_from, effective_to FROM tank.price_book"
        ))
        grain_ids = [row["ledger_ids"][0] for row in outcome_rows if row.get("ledger_ids")]
        grains: dict[str, dict[str, Any]] = {}
        if grain_ids:
            grain_rows = _records(await conn.fetch(
                "SELECT id, ts, tenant_id, agent, task_type, rung, model FROM tank.ledger WHERE id = ANY($1::uuid[])",
                grain_ids,
            ))
            grains = {str(row["id"]): row for row in grain_rows}
        routes = {(key[3], key[5], key[4]) for key in set(existing) | set(call_map) if key[4] != 0}
        evidence = build_route_evidence(
            policies=policies, skills=skills, shadows=shadows, feedback=feedback,
            routes=routes, previous=previous, now=now,
        )
        proven_keys = {(row["task_type"], row["model"], int(row["rung"])) for row in evidence if row["proven"]}
        outcome_map = aggregate_outcomes(outcome_rows, prices, grains)
        merged = merge_econ(existing, call_map, outcome_map, proven_keys, since)
        await conn.execute("DELETE FROM tank.route_evidence")
        if evidence:
            await conn.executemany(
                """
                INSERT INTO tank.route_evidence (
                    task_type, model, rung, eval_score, shadow_agreement, shadow_n, acceptance_rate,
                    judged, rejected, proven, proven_at, lost_at, flag, updated_at
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,now())
                """,
                [
                    (
                        row["task_type"], row["model"], row["rung"], row["eval_score"], row["shadow_agreement"],
                        row["shadow_n"], row["acceptance_rate"], row["judged"], row["rejected"], row["proven"],
                        row["proven_at"], row["lost_at"], row["flag"],
                    )
                    for row in evidence
                ],
            )
        await conn.execute("DELETE FROM tank.econ_daily")
        if merged:
            await conn.executemany(
                """
                INSERT INTO tank.econ_daily (
                    day, tenant_id, agent, task_type, rung, model, calls, cost_usd, outcomes, booked_usd, cache_hits, proven_calls
                ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
                """,
                [
                    (key[0], uuid.UUID(key[1]), key[2], key[3], key[4], key[5], value["calls"], value["cost"], value["outcomes"], value["booked"], value["cache_hits"], value["proven_calls"])
                    for key, value in merged.items()
                ],
            )


def _public_route(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_type": row["task_type"],
        "model": row["model"],
        "rung": int(row["rung"]),
        "eval_score": num(row["eval_score"]) if row["eval_score"] is not None else None,
        "shadow_agreement": num(row["shadow_agreement"]) if row["shadow_agreement"] is not None else None,
        "shadow_n": int(row["shadow_n"]),
        "acceptance_rate": num(row["acceptance_rate"]) if row["acceptance_rate"] is not None else None,
        "proven": bool(row["proven"]),
        "proven_at": iso(row["proven_at"]),
        "lost_at": iso(row["lost_at"]),
        "flag": row["flag"],
    }


def _price_out(row: dict[str, Any], current_ids: set[Any]) -> dict[str, Any]:
    return {
        "id": str(row["id"]),
        "tenant_id": str(row["tenant_id"]) if row["tenant_id"] is not None else None,
        "outcome_type": row["outcome_type"],
        "unit_price": num(row["unit_price"]),
        "currency": row["currency"],
        "effective_from": iso(row["effective_from"]),
        "effective_to": iso(row["effective_to"]),
        "note": row["note"],
        "current": row["id"] in current_ids,
    }


class PriceBody(BaseModel):
    outcome_type: str = Field(min_length=1, max_length=120)
    unit_price: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    tenant_id: uuid.UUID | None = None
    note: str | None = Field(default=None, max_length=500)
    effective_from: datetime | None = None


@router.get("/counters")
async def counters() -> dict[str, Any]:
    async with _pool().acquire() as conn:
        await refresh_econ(conn)
        econ = _econ_list(_econ_map(_records(await conn.fetch("SELECT * FROM tank.econ_daily"))))
        routes = _records(await conn.fetch("SELECT * FROM tank.route_evidence ORDER BY task_type, rung, model"))
    report = counter_report(econ, utc_today())
    report["routes"] = [_public_route(row) for row in routes]
    return report


@router.get("/series")
async def series(days: int = 90, group: str = "task_type") -> dict[str, Any]:
    if group not in ("agent", "task_type", "tenant"):
        raise HTTPException(status_code=400, detail="group must be agent, task_type, or tenant")
    days = max(1, min(days, 3650))
    async with _pool().acquire() as conn:
        await refresh_econ(conn)
        econ = _econ_list(_econ_map(_records(await conn.fetch("SELECT * FROM tank.econ_daily"))))
    return series_report(econ, utc_today(), days, group)


@router.get("/graduations")
async def graduations(days: int = 90) -> list[dict[str, Any]]:
    days = max(1, min(days, 3650))
    start, _end = window_bounds(utc_today(), days)
    async with _pool().acquire() as conn:
        logs = _records(await conn.fetch(
            """
            SELECT id, task_type, action, from_model, to_model, created_at
            FROM tank.policy_log
            WHERE action IN ('promote', 'rollback') AND created_at >= $1
            ORDER BY created_at
            """,
            datetime(start.year, start.month, start.day, tzinfo=timezone.utc),
        ))
        shadows = _records(await conn.fetch(
            """
            SELECT task_type, primary_model, candidate_model,
                   avg(primary_cost_usd) AS prim_cost, avg(candidate_cost_usd) AS cand_cost
            FROM tank.shadow
            GROUP BY task_type, primary_model, candidate_model
            """
        ))
    return graduation_rows(logs, shadows, utc_today(), days)


@router.get("/focus")
async def focus(days: int = 30) -> list[dict[str, Any]]:
    days = max(1, min(days, 3650))
    async with _pool().acquire() as conn:
        await refresh_econ(conn)
        policies = _records(await conn.fetch(
            """
            SELECT task_type, rung, model, candidate_model, eval_threshold, min_shadow_samples, max_reject_rate
            FROM tank.policy WHERE tenant_id IS NULL
            """
        ))
        shadows = _records(await conn.fetch(
            """
            SELECT task_type, candidate_model,
                   count(*) FILTER (WHERE agreement IS NOT NULL)::int AS n,
                   avg(agreement) FILTER (WHERE agreement IS NOT NULL) AS agreement
            FROM tank.shadow
            GROUP BY task_type, candidate_model
            """
        ))
        evidence = _records(await conn.fetch("SELECT * FROM tank.route_evidence"))
        econ = _econ_list(_econ_map(_records(await conn.fetch("SELECT * FROM tank.econ_daily"))))
    for row in evidence:
        row["eval_score"] = num(row["eval_score"]) if row["eval_score"] is not None else None
        row["acceptance_rate"] = num(row["acceptance_rate"]) if row["acceptance_rate"] is not None else None
        row["shadow_agreement"] = num(row["shadow_agreement"]) if row["shadow_agreement"] is not None else None
    return focus_list(policies, econ, shadows, evidence, utc_today(), days)


def _current_price_ids(rows: list[dict[str, Any]], now: datetime) -> set[Any]:
    """Rows are newest first. The latest row still in effect is the current price."""
    current: set[Any] = set()
    seen: set[tuple[str, str | None]] = set()
    for row in rows:
        key = (row["outcome_type"], str(row["tenant_id"]) if row["tenant_id"] is not None else None)
        if key in seen:
            continue
        start = as_dt(row["effective_from"])
        end = as_dt(row["effective_to"]) if row.get("effective_to") else None
        if start <= now and (end is None or end > now):
            current.add(row["id"])
            seen.add(key)
    return current


@router.get("/price_book")
async def get_price_book() -> list[dict[str, Any]]:
    async with _pool().acquire() as conn:
        rows = _records(await conn.fetch(
            """
            SELECT id, tenant_id, outcome_type, unit_price, currency, effective_from, effective_to, note
            FROM tank.price_book
            ORDER BY outcome_type, effective_from DESC
            """
        ))
    current = _current_price_ids(rows, datetime.now(timezone.utc))
    return [_price_out(row, current) for row in rows]


@router.put("/price_book")
async def put_price_book(body: PriceBody) -> dict[str, Any]:
    """A price change is a new row. The previous row is left as it was."""
    async with _pool().acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO tank.price_book (tenant_id, outcome_type, unit_price, currency, effective_from, note)
            VALUES ($1, $2, $3, $4, COALESCE($5, now()), $6)
            RETURNING id, tenant_id, outcome_type, unit_price, currency, effective_from, effective_to, note
            """,
            body.tenant_id, body.outcome_type.strip(), body.unit_price, body.currency.upper(), body.effective_from, body.note,
        )
    return _price_out(dict(row), {row["id"]})
