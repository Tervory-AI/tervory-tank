"""Founder-only Command adapters over the existing saved Base audit store."""
import json
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from base_audit import AuditStore, audit_csv
from base_lists import receipt


class StartArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign_id: UUID
    seed: int = Field(ge=0, le=2**63 - 1)


class CsvArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    campaign_id: UUID
    audit_id: UUID


class ReviewArgs(CsvArgs):
    attachment_id: UUID
    field_verdicts: dict[str, dict[str, str]] | None = None


def build_router() -> APIRouter:
    from command import Actor, db, identity, require_tool
    from admin import require_admin
    from trigger_commands import confirmation
    from types import SimpleNamespace

    router = APIRouter(prefix="/v1/command/base/audits", tags=["base"])

    async def founder(request: Request, actor: Annotated[Actor, Depends(identity)]):
        # Keep both Command's founder-only catalogue and the existing admin guard.
        require_tool(actor, "base.audit.csv")
        await require_admin(request.headers.get("x-tank-key", ""), request.headers.get("x-tervory-admin", ""))
        return actor

    def store():
        return AuditStore(SimpleNamespace(pool=db))

    async def result(actor, tool, data):
        return {**data, "summary": json.dumps(data, default=str, ensure_ascii=False),
                "ledger_id": await receipt(actor.tenant_id, tool), "cost_usd": 0}

    @router.post("/start")
    async def start(args: StartArgs, actor: Annotated[Actor, Depends(founder)]):
        require_tool(actor, "base.audit.start")
        confirmation(actor, "base.audit.start", args.model_dump(mode="json", exclude_none=True))
        saved = await store().create(actor.tenant_id, args.campaign_id, args.seed, actor.user_id)
        histogram = await store().histogram(actor.tenant_id, args.campaign_id)
        return await result(actor, "base.audit.start", {
            "audit_id": str(saved["id"]), "campaign_id": str(saved["campaign_id"]), "seed": saved["seed"],
            "population_size": saved["population_size"], "population_sha256": saved["population_sha256"],
            "measurement": saved["measurement"], "histogram": histogram})

    @router.get("/export")
    async def export(args: Annotated[CsvArgs, Depends()], actor: Annotated[Actor, Depends(founder)]):
        require_tool(actor, "base.audit.csv")
        await store().get(actor.tenant_id, args.campaign_id, args.audit_id)
        return await result(actor, "base.audit.csv", {"audit_id": str(args.audit_id),
            "url": "https://app.tervory.com/base/download?audit_id=" + str(args.audit_id) + "&campaign_id=" + str(args.campaign_id)})

    @router.get("/csv")
    async def csv(args: Annotated[CsvArgs, Depends()], actor: Annotated[Actor, Depends(founder)]):
        require_tool(actor, "base.audit.csv")
        saved = await store().get(actor.tenant_id, args.campaign_id, args.audit_id)
        return Response(audit_csv(saved), media_type="text/csv; charset=utf-8", headers={
            "Content-Disposition": 'attachment; filename="base-audit.csv"', "Cache-Control": "private, no-store"})

    @router.post("/review")
    async def review(args: ReviewArgs, actor: Annotated[Actor, Depends(founder)]):
        require_tool(actor, "base.audit.review")
        confirmation(actor, "base.audit.review", args.model_dump(mode="json", exclude_none=True))
        async with db().acquire() as conn:
            row = await conn.fetchrow("SELECT name,content FROM tank.command_attachments WHERE attachment_id=$1 AND tenant_id=$2 AND user_id=$3",
                                      args.attachment_id, actor.tenant_id, actor.user_id)
        if row is None:
            raise HTTPException(404, "Attachment not found")
        try:
            text = bytes(row["content"]).decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(422, "The action arguments are invalid") from None
        saved = await store().review(actor.tenant_id, args.campaign_id, args.audit_id, text, actor.user_id, args.field_verdicts)
        return await result(actor, "base.audit.review", {"audit_id": str(args.audit_id), "measurement": saved["measurement"]})

    return router
