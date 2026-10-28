"""Fixed, tenant-scoped case studies extending CORE-1 proof. No page or model calls."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.encoders import jsonable_encoder

from command import Actor, db, identity, require_founder
from case_study_templates import PRODUCTS, empty_figures
from case_study_sources import exists, histogram, populate, put
from proof import product_summary

router = APIRouter(prefix="/v1/case-studies", tags=["case-studies"])


async def register(conn, tenant: uuid.UUID) -> None:
    """Reconcile only this authenticated tenant, including pre-existing grants."""
    await conn.execute("INSERT INTO tank.case_study_clients(tenant_id) VALUES($1) ON CONFLICT DO NOTHING", tenant)
    await conn.execute("""INSERT INTO tank.case_study_reports(tenant_id,product)
        SELECT tenant_id,agent FROM tank.tenant_squad WHERE tenant_id=$1 AND agent=ANY($2::text[])
        ON CONFLICT DO NOTHING""", tenant, list(PRODUCTS))
    # Trigger has a voice provision rather than a squad grant on today's main.
    if await exists(conn, "agent_trigger.voices"):
        await conn.execute("""INSERT INTO tank.case_study_reports(tenant_id,product)
            SELECT tenant_id,'trigger' FROM agent_trigger.voices WHERE tenant_id=$1 ON CONFLICT DO NOTHING""", tenant)
    # Existing product work is evidence of product use, not an access grant. This
    # also discovers clients provisioned before case-study registration existed.
    await conn.execute("""INSERT INTO tank.case_study_reports(tenant_id,product)
        SELECT DISTINCT tenant_id,CASE WHEN agent='ghost' THEN 'autumbra' WHEN agent='market-lab' THEN 'market_lab' ELSE agent END
        FROM tank.ledger WHERE tenant_id=$1 AND agent=ANY($2::text[])
        ON CONFLICT DO NOTHING""", tenant, [*PRODUCTS, "ghost", "market-lab"])


def scoped(actor: Actor, tenant: uuid.UUID | None) -> uuid.UUID:
    if tenant is not None and tenant != actor.tenant_id:
        require_founder(actor)
    return tenant or actor.tenant_id


def period(start: date | None, end: date | None):
    end = end or datetime.now(timezone.utc).date()
    start = start or end - timedelta(days=29)
    if start > end or (end - start).days > 365 or end > datetime.now(timezone.utc).date():
        raise HTTPException(422, "Invalid report period")
    return start, end, datetime.combine(start, time.min, timezone.utc), datetime.combine(end + timedelta(days=1), time.min, timezone.utc)


@router.post("/ensure")
async def ensure(actor: Actor = Depends(identity)) -> dict:
    async with db().acquire() as conn, conn.transaction():
        await register(conn, actor.tenant_id)
        rows = await conn.fetch("SELECT product FROM tank.case_study_reports WHERE tenant_id=$1 ORDER BY product", actor.tenant_id)
    return {"tenant_id": str(actor.tenant_id), "products": [r["product"] for r in rows]}


@router.get("/clients")
async def clients(actor: Actor = Depends(identity), offset: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500)) -> dict:
    require_founder(actor)
    async with db().acquire() as conn:
        rows = await conn.fetch("""SELECT c.tenant_id,c.created_at,
            coalesce(array_agg(r.product ORDER BY r.product) FILTER(WHERE r.product IS NOT NULL),'{}') AS products
            FROM tank.case_study_clients c LEFT JOIN tank.case_study_reports r ON r.tenant_id=c.tenant_id
            GROUP BY c.tenant_id ORDER BY c.tenant_id OFFSET $1 LIMIT $2""", offset, limit + 1)
    return {"clients": [dict(r) for r in rows[:limit]], "has_more": len(rows) > limit}


@router.get("")
async def reports(response: Response, tenant_id: uuid.UUID | None = None, actor: Actor = Depends(identity)) -> dict:
    tenant = scoped(actor, tenant_id)
    response.headers["Cache-Control"] = "private, no-store"
    async with db().acquire() as conn:
        rows = await conn.fetch("SELECT product,template_version,created_at FROM tank.case_study_reports WHERE tenant_id=$1 ORDER BY product", tenant)
    return {"tenant_id": str(tenant), "reports": [dict(r) for r in rows]}


async def autumbra(tenant, start, end, figures):
    # The existing tenant receipt corridor exposes applied shields. Global
    # platform monitoring totals must never become a client's incident/check count.
    if not os.environ.get("TANK_KEY_GHOST"):
        return
    from ghost_routes import call_room
    response = await call_room("GET", "ghost", "/ghost/autumbra/receipts", params={"tenant_id": str(tenant)})
    if response.status_code == 404:
        return
    if response.status_code != 200:
        raise HTTPException(503, "Report source could not be read")
    data = response.json()
    if data.get("tenant_id") != str(tenant):
        raise HTTPException(502, "Report source tenant mismatch")
    applied = set()
    for row in data.get("receipts", []):
        if row.get("tenant_id") != str(tenant):
            raise HTTPException(502, "Report source tenant mismatch")
        try:
            at = datetime.fromisoformat(row.get("timestamp", "").replace("Z", "+00:00"))
            if at.tzinfo is None or not start <= at < end:
                continue
        except (ValueError, TypeError):
            continue
        if row.get("applied") is True and row.get("id") and not row.get("undone") and row.get("kind") != "undo":
            applied.add(row["id"])
    put(figures, "autumbra.shields_applied", len(applied), "ghost.autumbra.tenant_receipts")


@router.get("/{product}")
async def report(product: str, response: Response, tenant_id: uuid.UUID | None = None,
                 start: date | None = None, end: date | None = None, actor: Actor = Depends(identity)) -> dict:
    if product not in PRODUCTS:
        raise HTTPException(404, "Report not found")
    tenant = scoped(actor, tenant_id)
    first, last, since, until = period(start, end)
    from main import box_region
    region = box_region()
    async with db().acquire() as conn, conn.transaction(isolation="repeatable_read", readonly=True):
        saved = await conn.fetchrow("SELECT template_version,created_at FROM tank.case_study_reports WHERE tenant_id=$1 AND product=$2", tenant, product)
        if not saved:
            raise HTTPException(404, "Report not found")
        figures = empty_figures(product, first, last)
        shared = await product_summary(conn, tenant, product, region, since, until)
        for name, key in (("spend", "spent"), ("savings_vs_baseline", "saved"), ("cost_per_task", "cost_per_task"), ("cache_hits", "cache_hits")):
            put(figures, "tank." + name, shared[key], "proof.product_summary")
        figures["tank.spend"]["unknown_cost_calls"] = shared["unknown_cost_calls"]
        figures["tank.cost_per_task"]["tasks"] = shared["tasks"]
        histogram(figures, "tank.work_by_execution", {"code": shared["code"], "cache": shared["cache_hits"], "model": shared["model"]}, "proof.product_summary")
        put(figures, "tank.graduation_progress", shared["graduation"], "proof.product_summary")
        await populate(conn, tenant, product, region, since, until, figures)
    if product == "autumbra":
        await autumbra(tenant, since, until, figures)
    response.headers["Cache-Control"] = "private, no-store"
    return jsonable_encoder({"tenant_id": tenant, "product": product, "template_version": saved["template_version"],
        "created_at": saved["created_at"], "period": {"start": first, "end": last, "timezone": "UTC"},
        "tank": [v for key, v in figures.items() if key.startswith("tank.")],
        "figures": [v for key, v in figures.items() if not key.startswith("tank.")]}, custom_encoder={Decimal: float})
