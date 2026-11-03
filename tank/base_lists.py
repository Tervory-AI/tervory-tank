"""Tenant-only Base find and immutable list snapshots. Code, never enrichment/model work."""

import json
from datetime import date, datetime, timezone
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from base_evidence import field, public_url, row_fields
from base_metrics import export_records, obj


class FindArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str | None = Field(default=None, min_length=1, max_length=100)
    city: str | None = Field(default=None, min_length=1, max_length=100)
    licence_type: str | None = Field(default=None, min_length=1, max_length=100)
    engine_category: str | None = Field(default=None, min_length=1, max_length=100)
    has_website: bool | None = None
    has_phone: bool | None = None
    has_email: bool | None = None
    email_syntax_ok: bool | None = None
    email_disposable: bool | None = None
    phone_valid: bool | None = None
    technologies_contain: str | None = Field(default=None, min_length=1, max_length=100)
    sells_online: bool | None = None
    site_newest_year_at_least: int | None = Field(default=None, ge=1900, le=9999)
    confidence_tier: Literal["ready", "use_with_awareness", "review", "requeue"] | None = None
    checked_on_or_after: date | None = None


class SaveArgs(FindArgs):
    name: str = Field(min_length=1, max_length=120)


class ListArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    list_id: UUID


class SendArgs(ListArgs):
    record_ids: list[UUID] = Field(min_length=1, max_length=100)


def verified(item: Any) -> bool:
    return (isinstance(item, dict) and item.get("verified") is True
            and bool(public_url(item.get("source_url")) and item.get("checked_at")))


def project(row: dict) -> dict:
    profile, passes = obj(row.get("profile") or {}), obj(row.get("passes") or {})
    raw = obj(row.get("raw") or {})
    fields = row_fields({**row, "profile": profile, "passes": passes})
    # A platform reference is already source-backed; never promote uploaded identity.
    reference = raw.get("_base_reference") or {}
    source, checked = public_url(reference.get("source_url")), reference.get("checked_at")
    address = reference.get("address") or {}
    for key in ("name", "state", "city", "licence_type", "engine_category"):
        candidate = profile.get(key)
        if verified(candidate):
            fields[key] = candidate
        elif source and checked:
            value = address.get("city") if key == "city" else reference.get(key)
            if value:
                fields[key] = field(value, source, checked)
    # Categories not explicitly verified stay unavailable to filters/exports.
    if "engine_category" not in fields and verified(profile.get("categories")):
        fields["engine_category"] = profile["categories"]
    tier = profile.get("tier") or {}
    inputs = [item for item in fields.values() if verified(item)]
    if tier.get("source") == "verify" and passes.get("7") and inputs:
        fields["confidence_tier"] = {**field(tier.get("value"), inputs[0]["source_url"], str(row["updated_at"])),
                                     "source": "base.verify", "inputs": inputs}
    return {"record_id": str(row["id"]), "name": (fields.get("name") or {}).get("value"),
            "licence_key": reference.get("licence_key"),
            "state": (fields.get("state") or {}).get("value"),
            "licence_type": (fields.get("licence_type") or {}).get("value"),
            "checked_at": str(row["updated_at"]), "fields": fields}


def matches(row: dict, filters: FindArgs) -> bool:
    fields = row["fields"]

    def value(key):
        item = fields.get(key)
        return item.get("value") if verified(item) else None

    for key in ("state", "city", "licence_type", "engine_category"):
        wanted = getattr(filters, key)
        if wanted is not None:
            actual = value(key)
            options = actual if isinstance(actual, list) else [actual]
            if not any(str(item).strip().casefold() == wanted.strip().casefold() for item in options if item is not None):
                return False
    for key in ("website", "phone", "email"):
        wanted = getattr(filters, "has_" + key)
        if wanted is not None and verified(fields.get(key)) is not wanted:
            return False
    for key in ("email_syntax_ok", "email_disposable", "phone_valid", "sells_online"):
        wanted = getattr(filters, key)
        if wanted is not None and value(key) is not wanted:
            return False  # unknown never satisfies a negative filter
    if filters.technologies_contain is not None:
        technologies = value("technologies")
        if not isinstance(technologies, list) or filters.technologies_contain.casefold() not in [str(t).casefold() for t in technologies]:
            return False
    if filters.site_newest_year_at_least is not None:
        year = value("site_newest_year")
        if type(year) is not int or year < filters.site_newest_year_at_least:
            return False
    if filters.confidence_tier is not None and value("confidence_tier") != filters.confidence_tier:
        return False
    if filters.checked_on_or_after is not None:
        # Every returned verified observation must meet the cutoff; do not use
        # the record update timestamp to make an old observation appear fresh.
        observations = [item for item in fields.values() if verified(item)]
        try:
            if not observations or any(date.fromisoformat(str(item["checked_at"])[:10]) < filters.checked_on_or_after for item in observations):
                return False
        except ValueError:
            return False
    return True


class Store:
    def __init__(self, pool):
        self.pool = pool

    async def find(self, tenant: UUID, filters: FindArgs) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id,raw,profile,passes,status,updated_at FROM agent_base.records "
                                    "WHERE tenant_id=$1 AND status='done' ORDER BY updated_at DESC,id", tenant)
        projected = [project(dict(row)) for row in rows]
        return [row for row in projected if matches(row, filters)]

    async def save(self, tenant: UUID, name: str, filters: FindArgs) -> dict:
        rows = await self.find(tenant, filters)
        async with self.pool.acquire() as conn:
            saved = await conn.fetchrow("INSERT INTO tank.base_saved_lists(tenant_id,name,filters,record_ids,records) "
                                       "VALUES($1,$2,$3::jsonb,$4,$5::jsonb) RETURNING list_id,name,created_at",
                                       tenant, name, filters.model_dump_json(), [UUID(row["record_id"]) for row in rows], json.dumps(rows))
        return {**dict(saved), "total": len(rows)}

    async def show(self, tenant: UUID, list_id: UUID) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT list_id,name,filters,record_ids,records,created_at FROM tank.base_saved_lists "
                                      "WHERE tenant_id=$1 AND list_id=$2", tenant, list_id)
        if row is None:
            raise HTTPException(404, "Not found")
        return {**dict(row), "records": obj(row["records"]), "filters": obj(row["filters"])}

    async def lists(self, tenant: UUID) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT list_id,name,created_at,cardinality(record_ids) AS total "
                                    "FROM tank.base_saved_lists WHERE tenant_id=$1 ORDER BY created_at DESC,list_id", tenant)
        return [dict(row) for row in rows]


async def receipt(tenant: UUID, tool: str) -> str:
    from main import box_region, pool
    value = await pool().fetchval("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out) "
                                  "VALUES($1,$2,'base',$3,3,'code',0,0,0) RETURNING id", tenant, box_region(), tool)
    return str(value)


def preview(rows: list[dict]) -> dict:
    return {"total": len(rows), "records": [{**row, "summary": json.dumps(row["fields"], ensure_ascii=False)} for row in rows[:20]]}


def build_router() -> APIRouter:
    from command import Actor, db, identity, require_tool
    from trigger_commands import confirmation
    from fastapi.responses import Response
    router = APIRouter(prefix="/v1/command/base/lists", tags=["base"])

    def store():
        return Store(db())

    async def result(actor, tool, data):
        return {**data, "ledger_id": await receipt(actor.tenant_id, tool), "cost_usd": 0}

    @router.get("/find")
    async def find(args: FindArgs = Depends(), actor: Actor = Depends(identity)):
        require_tool(actor, "base.find")
        return await result(actor, "base.find", preview(await store().find(actor.tenant_id, args)))

    @router.post("/save")
    async def save(args: SaveArgs, actor: Actor = Depends(identity)):
        require_tool(actor, "base.list.save")
        confirmation(actor, "base.list.save", args.model_dump(mode="json", exclude_none=True))
        filters = FindArgs.model_validate(args.model_dump(exclude={"name"}))
        saved = await store().save(actor.tenant_id, args.name, filters)
        return await result(actor, "base.list.save", {**saved, "url": "https://app.tervory.com/base/download?list_id=" + str(saved["list_id"])})

    @router.get("")
    async def lists(actor: Actor = Depends(identity)):
        require_tool(actor, "base.lists")
        return await result(actor, "base.lists", {"items": await store().lists(actor.tenant_id)})

    @router.get("/show")
    async def show(list_id: UUID, actor: Actor = Depends(identity)):
        require_tool(actor, "base.list.show")
        saved = await store().show(actor.tenant_id, list_id)
        return await result(actor, "base.list.show", {"name": saved["name"], **preview(saved["records"])})

    @router.get("/export")
    async def export(list_id: UUID, actor: Actor = Depends(identity)):
        require_tool(actor, "base.list.export")
        saved = await store().show(actor.tenant_id, list_id)
        return await result(actor, "base.list.export", {"total": len(saved["records"]),
                            "url": "https://app.tervory.com/base/download?list_id=" + str(list_id)})

    @router.get("/csv")
    async def csv(list_id: UUID, actor: Actor = Depends(identity)):
        require_tool(actor, "base.list.export")
        saved = await store().show(actor.tenant_id, list_id)
        return Response(export_records(saved["records"]), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": 'attachment; filename="base-list.csv"', "Cache-Control": "private, no-store"})

    @router.post("/to-crm")
    async def to_crm(args: SendArgs, actor: Actor = Depends(identity)):
        require_tool(actor, "base.list.to_crm")
        confirmation(actor, "base.list.to_crm", args.model_dump(mode="json", exclude_none=True))
        saved = await store().show(actor.tenant_id, args.list_id)
        from base_list_crm import send
        rows = {row["record_id"]: row for row in saved["records"]}
        ids = list(dict.fromkeys(str(value) for value in args.record_ids))
        if any(identity not in rows for identity in ids):
            raise HTTPException(404, "Not found")
        # Serialize our sends for a tenant so simultaneous confirmed cards see
        # each other's completed leads when they check for duplicates.
        async with db().acquire() as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1,0))", str(actor.tenant_id))
            sent = await send(actor, [rows[value] for value in ids])
        return await result(actor, "base.list.to_crm", {"records": sent})

    return router
