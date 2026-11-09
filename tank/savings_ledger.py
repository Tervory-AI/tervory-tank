"""Per-client savings ledger, dated baselines and billing statements.

Everything here is off unless ENGINE_LEDGER_ENABLED is the literal ``true``.
Off means no route is registered, no row is read or written and the receipt
path returns the answer object it was given, unchanged.

The ledger is append-only in the database (triggers refuse UPDATE, DELETE and
TRUNCATE for every role) and each tenant's rows form a hash chain that
``verify`` recomputes independently, so an edit made around the triggers is
detectable. Fees and prices are founder settings read by name; none is chosen
here. Stripe metering has its own literal-true setting and is off by default.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

import asyncpg
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from command import Actor, current_actor, identity, require_founder
from tenant_db import tenant_transaction

log = logging.getLogger("tank.savings_ledger")

SETTING = "ENGINE_LEDGER_ENABLED"
METERING_SETTING = "ENGINE_STRIPE_METERING_ENABLED"
# Founder settings, by name only. Unset fee plan means no fee line amount.
FEE_PLAN_SETTING = "ENGINE_LEDGER_FEE_PLAN"
FEE_FLAT_SETTING = "ENGINE_LEDGER_FEE_FLAT_USD"
FEE_SHARE_SETTING = "ENGINE_LEDGER_FEE_SHARE"
METER_EVENT_SETTING = "ENGINE_STRIPE_METER_EVENT"
STRIPE_KEY_SETTING = "STRIPE_SECRET_KEY"
FEE_PLANS = ("none", "flat", "share", "base_plus_share")
STRIPE_API = "https://api.stripe.com/v1"
GENESIS = "0" * 64
MONTH = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])$")
RUNGS = {1: "frontier", 2: "owned model", 3: "code", 4: "cache"}
USD = Decimal("0.00000001")
CENT = Decimal("0.01")
ROW_COLUMNS = ("tenant_id,seq,ledger_id,region,created_at,receipt_at,task_type,rung,cache_layer,model,"
               "tokens_in,tokens_out,cost_usd,would_have_cost_usd,top_cost_usd,baseline_id,baseline_model,"
               "input_usd,output_usd,price_date,top_model,prev_hash,row_hash")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def enabled() -> bool:
    return os.environ.get(SETTING) == "true"


def metering_enabled() -> bool:
    return enabled() and os.environ.get(METERING_SETTING) == "true"


def _number(value: Decimal | None) -> str:
    # Matches PostgreSQL numeric::text for a fixed-scale column.
    return "" if value is None else format(value, "f")


def _instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def digest(row: Any) -> str:
    """Independent Python recomputation of tank.savings_ledger_digest."""
    parts = [row["prev_hash"], str(row["tenant_id"]), str(row["seq"]), str(row["ledger_id"]), row["region"],
             _instant(row["created_at"]), _instant(row["receipt_at"]), row["task_type"], str(row["rung"]),
             row["cache_layer"] or "", row["model"], str(row["tokens_in"]), str(row["tokens_out"]),
             _number(row["cost_usd"]), _number(row["would_have_cost_usd"]), _number(row["top_cost_usd"]),
             "" if row["baseline_id"] is None else str(row["baseline_id"]), row["baseline_model"] or "",
             _number(row["input_usd"]), _number(row["output_usd"]),
             "" if row["price_date"] is None else row["price_date"].isoformat(), row["top_model"] or ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


async def _scoped(conn, tenant_id) -> None:
    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(uuid.UUID(str(tenant_id))))


def _priced(tokens_in: int, tokens_out: int, input_usd: Decimal | None, output_usd: Decimal | None) -> Decimal | None:
    if input_usd is None or output_usd is None:
        return None
    return (tokens_in * input_usd + tokens_out * output_usd).quantize(USD, rounding=ROUND_HALF_UP)


async def _price(conn, model: str | None):
    if not model:
        return None
    return await conn.fetchrow("SELECT model,family,input_usd,output_usd FROM tank.proof_prices WHERE model=$1 AND active", model)


async def _top(conn, family: str):
    return await conn.fetchrow("""SELECT model,input_usd,output_usd FROM tank.proof_prices
        WHERE family=$1 AND active ORDER BY input_usd+output_usd DESC,model LIMIT 1""", family)


async def pin_baseline(conn, task_type: str, model: str, recorded_by: str, effective_from: datetime | None = None):
    """Fix a comparison model and today's list price from effective_from forward."""
    price = await _price(conn, model)
    if price is None:
        raise HTTPException(422, "The baseline model has no active list price")
    top = await _top(conn, price["family"])
    return await conn.fetchrow("""INSERT INTO tank.savings_baselines(task_type,baseline_model,input_usd,output_usd,
            top_model,top_input_usd,top_output_usd,effective_from,recorded_by)
        VALUES($1,$2,$3,$4,$5,$6,$7,coalesce($8,now()),$9) RETURNING *""",
        task_type, model, price["input_usd"], price["output_usd"], top and top["model"],
        top and top["input_usd"], top and top["output_usd"], effective_from, recorded_by)


async def baseline_for(conn, task_type: str, at: datetime, standard_model: str | None):
    """The baseline in effect at a receipt's time; the first one is pinned on first use.

    The first use pins what the receipt already compares with today: the
    provider's default model (or the founder's task override), with the top
    model second. A receipt older than the first pin uses that first pin.
    """
    row = await conn.fetchrow("""SELECT * FROM tank.savings_baselines WHERE task_type=$1 AND effective_from<=$2
        ORDER BY effective_from DESC LIMIT 1""", task_type, at)
    if row is None:
        row = await conn.fetchrow("SELECT * FROM tank.savings_baselines WHERE task_type=$1 ORDER BY effective_from LIMIT 1", task_type)
    if row is not None or await _price(conn, standard_model) is None:
        return row
    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('tank.savings_baselines:'||$1,0))", task_type)
    row = await conn.fetchrow("SELECT * FROM tank.savings_baselines WHERE task_type=$1 ORDER BY effective_from LIMIT 1", task_type)
    return row or await pin_baseline(conn, task_type, standard_model, "first use")


async def append(pool, tenant_id, ledger_id, *, cache_layer: str | None = None):
    """Append one receipt; a receipt already in the ledger is left exactly as it is."""
    async with tenant_transaction(pool) as conn:
        await _scoped(conn, tenant_id)
        receipt = await conn.fetchrow("""SELECT l.id,l.ts,l.region,l.task_type,l.rung,l.model,l.tokens_in,l.tokens_out,
                l.cost_usd,l.cache_hit,l.standard_model,r.detail->>'cache_layer' AS receipt_layer
            FROM tank.ledger l LEFT JOIN tank.engine_receipts r ON r.tenant_id=l.tenant_id AND r.ledger_id=l.id
            WHERE l.tenant_id=$1 AND l.id=$2""", tenant_id, ledger_id)
        if receipt is None:
            return None
        layer = cache_layer or receipt["receipt_layer"] or ("cache" if receipt["rung"] == 4 or receipt["cache_hit"] else None)
        base = await baseline_for(conn, receipt["task_type"], receipt["ts"], receipt["standard_model"])
        tokens_in, tokens_out = receipt["tokens_in"], receipt["tokens_out"]
        cost = Decimal(receipt["cost_usd"] or 0).quantize(USD, rounding=ROUND_HALF_UP)
        would = top = None
        if base is not None:
            would = _priced(tokens_in, tokens_out, base["input_usd"], base["output_usd"])
            top = _priced(tokens_in, tokens_out, base["top_input_usd"], base["top_output_usd"])
        return await conn.fetchrow(f"""INSERT INTO tank.savings_ledger(tenant_id,seq,ledger_id,region,receipt_at,task_type,
                rung,cache_layer,model,tokens_in,tokens_out,cost_usd,would_have_cost_usd,top_cost_usd,baseline_id,
                baseline_model,input_usd,output_usd,price_date,top_model,prev_hash,row_hash)
            VALUES($1,0,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,'','')
            ON CONFLICT (tenant_id,ledger_id) DO NOTHING RETURNING {ROW_COLUMNS}""",
            tenant_id, ledger_id, receipt["region"], receipt["ts"], receipt["task_type"], receipt["rung"], layer,
            receipt["model"], tokens_in, tokens_out, cost, would, top, base and base["id"],
            base and base["baseline_model"], base and base["input_usd"], base and base["output_usd"],
            base and base["effective_from"].astimezone(timezone.utc).date(), base and base["top_model"])


async def record(rt, req, answer):
    """Receipt hook. Off: returns ``answer`` untouched without any I/O."""
    if not enabled() or not isinstance(answer, rt.RouteResponse):
        return answer
    try:
        await append(rt.pool(), req.tenant_id, answer.ledger_id, cache_layer=answer.cache_layer)
    except (asyncpg.PostgresError, OSError) as exc:
        # The answer was delivered and billed by the provider already; a missed
        # row is recovered by the founder backfill, never by failing the call.
        log.warning("savings ledger append failed for %s: %s", answer.ledger_id, type(exc).__name__)
    return answer


async def backfill(pool, tenant_id, since: datetime, limit: int = 5000) -> int:
    """Append receipts that the hook missed (for example off-peak completions)."""
    async with tenant_transaction(pool) as conn:
        await _scoped(conn, tenant_id)
        missing = await conn.fetch("""SELECT l.id FROM tank.ledger l WHERE l.tenant_id=$1 AND l.ts>=$2
            AND l.outcome<>'queued' AND NOT EXISTS (SELECT 1 FROM tank.savings_ledger s
              WHERE s.tenant_id=l.tenant_id AND s.ledger_id=l.id)
            ORDER BY l.ts,l.id LIMIT $3""", tenant_id, since, limit)
    added = 0
    for row in missing:
        added += await append(pool, tenant_id, row["id"]) is not None
    return added


async def rows(pool, tenant_id, start: datetime | None = None, end: datetime | None = None) -> list[asyncpg.Record]:
    async with tenant_transaction(pool, readonly=True) as conn:
        await _scoped(conn, tenant_id)
        return await conn.fetch(f"""SELECT {ROW_COLUMNS} FROM tank.savings_ledger WHERE tenant_id=$1
            AND ($2::timestamptz IS NULL OR created_at>=$2) AND ($3::timestamptz IS NULL OR created_at<$3)
            ORDER BY seq""", tenant_id, start, end)


async def verify(pool, tenant_id) -> dict[str, Any]:
    """Recompute the whole tenant chain in Python; the first broken link is reported."""
    previous, expected_seq = GENESIS, 1
    chain = await rows(pool, tenant_id)
    for row in chain:
        if row["seq"] != expected_seq or row["prev_hash"] != previous or digest(row) != row["row_hash"]:
            return {"intact": False, "rows": len(chain), "broken_at_seq": row["seq"]}
        previous, expected_seq = row["row_hash"], expected_seq + 1
    return {"intact": True, "rows": len(chain), "broken_at_seq": None, "head": previous}


def period(month: str) -> tuple[datetime, datetime]:
    if not MONTH.fullmatch(month):
        raise HTTPException(422, "Use a month written as YYYY-MM")
    year, number = int(month[:4]), int(month[5:])
    start = datetime(year, number, 1, tzinfo=timezone.utc)
    end = datetime(year + (number == 12), number % 12 + 1, 1, tzinfo=timezone.utc)
    return start, end


def _setting_decimal(name: str) -> Decimal | None:
    raw = (os.environ.get(name) or "").strip()
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


def fee_line(saving: Decimal) -> dict[str, Any]:
    """Fee from founder settings by name. A missing or invalid price is never guessed."""
    plan = (os.environ.get(FEE_PLAN_SETTING) or "").strip() or "none"
    line: dict[str, Any] = {"plan": plan, "amount_usd": None, "flat_usd": None, "share": None, "status": "ok"}
    if plan not in FEE_PLANS:
        line["status"] = "fee plan setting is not one of " + ", ".join(FEE_PLANS)
        return line
    if plan == "none":
        line["amount_usd"] = "0.00"
        return line
    flat = _setting_decimal(FEE_FLAT_SETTING) if plan in ("flat", "base_plus_share") else Decimal(0)
    share = _setting_decimal(FEE_SHARE_SETTING) if plan in ("share", "base_plus_share") else Decimal(0)
    if share is not None and share > 1:
        share = None
    if flat is None or share is None:
        line["status"] = "price not set"
        return line
    amount = flat + share * max(saving, Decimal(0))
    line.update(amount_usd=str(amount.quantize(CENT, rounding=ROUND_HALF_UP)),
                flat_usd=str(flat) if plan != "share" else None, share=str(share) if plan != "flat" else None)
    return line


def summarize(chain: list[Any]) -> dict[str, Any]:
    cost = would = priced_cost = top = Decimal(0)
    tokens_in = tokens_out = unpriced = 0
    standards, tops = [], []
    for row in chain:
        cost += row["cost_usd"]
        tokens_in += row["tokens_in"]
        tokens_out += row["tokens_out"]
        if row["would_have_cost_usd"] is None:
            unpriced += 1
            continue
        would += row["would_have_cost_usd"]
        priced_cost += row["cost_usd"]
        top += row["top_cost_usd"] or 0
        if row["baseline_model"] not in standards:
            standards.append(row["baseline_model"])
        if row["top_model"] and row["top_model"] not in tops:
            tops.append(row["top_model"])
    return {"calls": len(chain), "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": str(cost),
            "would_have_cost_usd": str(would), "priced_cost_usd": str(priced_cost),
            "saving_usd": str(would - priced_cost), "unpriced_calls": unpriced,
            # The default most people would use first; the top model second.
            "compared_with": {"standard": standards, "top": tops, "top_would_have_cost_usd": str(top)},
            "first_seq": chain[0]["seq"] if chain else None, "last_seq": chain[-1]["seq"] if chain else None,
            "rows_digest": hashlib.sha256("".join(r["row_hash"] for r in chain).encode()).hexdigest()}


def breakdown(chain: list[Any]) -> list[dict[str, Any]]:
    """Tervory's own model spend to serve this client, by rung, cache layer and model."""
    groups: dict[tuple, dict[str, Any]] = {}
    for row in chain:
        key = (row["rung"], row["cache_layer"] or "", row["model"])
        item = groups.setdefault(key, {"rung": row["rung"], "rung_name": RUNGS.get(row["rung"], str(row["rung"])),
                                       "cache_layer": row["cache_layer"], "model": row["model"], "calls": 0,
                                       "tokens_in": 0, "tokens_out": 0, "cost_usd": Decimal(0)})
        item["calls"] += 1
        item["tokens_in"] += row["tokens_in"]
        item["tokens_out"] += row["tokens_out"]
        item["cost_usd"] += row["cost_usd"]
    return [{**item, "cost_usd": str(item["cost_usd"])} for _, item in sorted(groups.items())]


async def statement(pool, tenant_id, month: str, *, founder: bool = False) -> dict[str, Any]:
    start, end = period(month)
    chain = await rows(pool, tenant_id, start, end)
    total = summarize(chain)
    result = {"tenant_id": str(tenant_id), "period": month, "from": start.isoformat(), "until": end.isoformat(),
              "closed": end <= _now(), **total, "fee": fee_line(Decimal(total["saving_usd"]))}
    if founder:
        spend = Decimal(total["cost_usd"])
        fee = result["fee"]["amount_usd"]
        result["cost_breakdown"] = {"serving_cost_usd": str(spend), "lines": breakdown(chain),
                                    "fee_less_serving_cost_usd": None if fee is None else str(Decimal(fee) - spend)}
        result["chain"] = await verify(pool, tenant_id)
    return result


def stripe_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=STRIPE_API, timeout=10)


async def meter(pool, tenant_id, month: str) -> dict[str, Any]:
    """Send one closed period's fee to a Stripe meter, once. Off unless both settings are true."""
    if not metering_enabled():
        raise HTTPException(404, "Not Found")
    current = await statement(pool, tenant_id, month)
    if not current["closed"]:
        raise HTTPException(409, "Only a closed period is metered")
    fee = current["fee"]["amount_usd"]
    if fee is None:
        raise HTTPException(409, "The fee for this period is not set")
    key = (os.environ.get(STRIPE_KEY_SETTING) or "").strip()
    event = (os.environ.get(METER_EVENT_SETTING) or "").strip()
    if not key or not event:
        raise HTTPException(503, "Stripe metering is not configured")
    identifier = f"tervory-savings-{tenant_id}-{month}"
    async with tenant_transaction(pool) as conn:
        await _scoped(conn, tenant_id)
        await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", identifier)
        sent = await conn.fetchrow("SELECT * FROM tank.savings_meter_events WHERE tenant_id=$1 AND period=$2", tenant_id, month)
        if sent is not None:
            return {"sent": False, "already_sent": True, "identifier": sent["identifier"],
                    "value_cents": sent["value_cents"], "rows_digest": sent["rows_digest"]}
        cents = int((Decimal(fee) * 100).to_integral_value(rounding=ROUND_HALF_UP))
        headers = {"Authorization": f"Bearer {key}"}
        async with stripe_client() as client:
            found = await client.get("/customers/search", headers=headers,
                                     params={"query": f"metadata['tenant_id']:'{tenant_id}'", "limit": 1})
            customers = found.json().get("data") if found.status_code == 200 else None
            if not customers:
                raise HTTPException(409, "No Stripe customer is linked to this workspace")
            response = await client.post("/billing/meter_events", headers=headers, data={
                "event_name": event, "identifier": identifier,
                "timestamp": str(int(datetime.now(timezone.utc).timestamp())),
                "payload[stripe_customer_id]": customers[0]["id"], "payload[value]": str(cents)})
        if response.status_code != 200:
            raise HTTPException(502, "Stripe did not accept the meter event")
        await conn.execute("""INSERT INTO tank.savings_meter_events(tenant_id,period,identifier,value_cents,rows_digest)
            VALUES($1,$2,$3,$4,$5)""", tenant_id, month, identifier, cents, current["rows_digest"])
    return {"sent": True, "already_sent": False, "identifier": identifier, "value_cents": cents,
            "rows_digest": current["rows_digest"]}


class BaselineChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    effective_from: AwareDatetime | None = None


class Backfill(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    since: AwareDatetime
    limit: int = Field(default=5000, ge=1, le=5000)


class MeterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    period: str = Field(pattern=MONTH.pattern)


def _gate() -> None:
    if not enabled():
        raise HTTPException(404, "Not Found")


def build_router(rt) -> APIRouter:
    """No routes at all unless the setting is the literal true at start-up."""
    if not enabled():
        return APIRouter()
    router = APIRouter(prefix="/v1/engine/ledger", tags=["engine"], dependencies=[Depends(_gate)])

    @router.get("/statement")
    async def client_statement(month: str = Query(pattern=MONTH.pattern),
                               actor: Actor = Depends(identity)):
        viewer = current_actor(actor)
        if not (viewer.tenant_admin or viewer.founder):
            raise HTTPException(403, "Workspace admin access required")
        return await statement(rt.pool(), actor.tenant_id, month)

    @router.get("/founder/statement")
    async def founder_statement(tenant_id: uuid.UUID, month: str = Query(pattern=MONTH.pattern), actor: Actor = Depends(identity)):
        require_founder(actor)
        return await statement(rt.pool(), tenant_id, month, founder=True)

    @router.get("/founder/baselines")
    async def list_baselines(task_type: str, actor: Actor = Depends(identity)):
        require_founder(actor)
        async with rt.pool().acquire() as conn:
            found = await conn.fetch("SELECT * FROM tank.savings_baselines WHERE task_type=$1 ORDER BY effective_from", task_type)
        return [{**dict(row), "effective_from": row["effective_from"].isoformat(),
                 "recorded_at": row["recorded_at"].isoformat()} for row in found]

    @router.post("/founder/baselines")
    async def add_baseline(body: BaselineChoice, actor: Actor = Depends(identity)):
        require_founder(actor)
        try:
            async with rt.pool().acquire() as conn:
                row = await pin_baseline(conn, body.task_type, body.model, actor.user_id, body.effective_from)
        except asyncpg.CheckViolationError:
            raise HTTPException(422, "A baseline applies from its date forward, never to past receipts") from None
        except asyncpg.UniqueViolationError:
            raise HTTPException(409, "A baseline already starts at that time") from None
        return {"id": row["id"], "task_type": row["task_type"], "baseline_model": row["baseline_model"],
                "top_model": row["top_model"], "effective_from": row["effective_from"].isoformat()}

    @router.post("/founder/backfill")
    async def founder_backfill(body: Backfill, actor: Actor = Depends(identity)):
        require_founder(actor)
        return {"added": await backfill(rt.pool(), body.tenant_id, body.since, body.limit)}

    @router.post("/founder/meter")
    async def founder_meter(body: MeterRequest, actor: Actor = Depends(identity)):
        require_founder(actor)
        return await meter(rt.pool(), body.tenant_id, body.period)

    return router

