"""Private room interface used only by the authenticated Tank proxy."""
import json
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from core.evidence import answer, document_page, overview
from core.calibration import calibration, identity
from core.jobs import _call


class RequestBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    question: str = Field(default="", max_length=2000)
    document_id: UUID | None = None
    offset: int = Field(default=0, ge=0, le=10000000)
    row: int | None = Field(default=None, ge=0, le=10000000)
    row_kind: Literal["point", "event"] | None = None
    kind: str | None = Field(default=None, min_length=1, max_length=200)


def build_router(*, key_ok, ledger_context, engine: str | None = None):
    router = APIRouter()

    @router.post("/market/{operation}")
    async def call(operation: str, body: RequestBody, x_tank_key: str = Header(default="")):
        if not key_ok(x_tank_key):
            raise HTTPException(401, "Room key required")
        if operation not in {"overview", "ask", "document", "refresh", "predictions", "calibration"}:
            raise HTTPException(404, "Not found")
        if operation in {"overview", "refresh"} and not engine:
            raise HTTPException(503, "Market Lab's feeds have not been configured.")
        try:
            async with ledger_context() as ledger:
                tenant = str(body.tenant_id)
                if operation in {"predictions", "calibration"}:
                    rows = await _call(ledger.predictions_for, tenant)
                    series = await _call(ledger.series_for, tenant)
                    if operation == "calibration":
                        return calibration(rows, tenant, series, kind=body.kind)
                    predictions = [{**row, **identity(row, series),
                                    "confidence": row.get("confidence"),
                                    "confidence_count": row.get("confidence_count") or 0}
                                   for row in rows if str(row["tenant_id"]) == tenant]
                    return {"predictions": [row for row in predictions if body.kind is None or row["kind"] == body.kind]}
                if operation == "document":
                    if body.document_id is None:
                        raise HTTPException(422, "A source is required")
                    found = await document_page(ledger, tenant, str(body.document_id), body.offset, row=body.row, row_kind=body.row_kind, engine=engine)
                    if found is None:
                        raise HTTPException(404, "Source not found")
                    return found
                if operation == "ask":
                    if not body.question.strip():
                        raise HTTPException(422, "A question is required")
                    return await answer(ledger, tenant, body.question, engine=engine)
                if operation == "refresh":
                    async with ledger.conn.transaction():
                        await ledger.conn.execute("SELECT pg_advisory_xact_lock(hashtextextended($1, 0))", tenant + ":market-refresh")
                        existing = await ledger.conn.fetchval("""
                            SELECT id FROM agent_market_lab.jobs
                            WHERE tenant_id = $1 AND kind = 'refresh' AND status IN ('queued', 'running') LIMIT 1
                        """, body.tenant_id)
                        if existing is None:
                            await ledger.conn.execute("""
                                INSERT INTO agent_market_lab.jobs (tenant_id, kind, input, status, run_at, timeout_s)
                                VALUES ($1, 'refresh', $2::jsonb, 'queued', now(), 86400)
                            """, body.tenant_id, json.dumps({"engine": engine}))
                    return {"status": "queued"}
                result = await overview(ledger, tenant, engine)
                status = await ledger.conn.fetchval("""
                    SELECT status FROM agent_market_lab.jobs WHERE tenant_id = $1 AND kind = 'refresh'
                    ORDER BY created_at DESC LIMIT 1
                """, body.tenant_id)
                return {**result, "refresh_status": status}
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "Market Lab could not read its stored sources. Try again shortly.") from None

    return router
