"""Workspace's tenant-scoped Market Lab corridor. It never routes a model call."""
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class MarketRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    question: str = Field(default="", max_length=2000)
    document_id: UUID | None = None
    offset: int = Field(default=0, ge=0, le=10000000)


def build_router(tank):
    router = APIRouter()

    @router.post("/v1/market-lab/{operation}", dependencies=[Depends(tank.require_key)])
    async def call(operation: str, body: MarketRequest):
        if operation not in {"overview", "ask", "document", "refresh"}:
            raise HTTPException(404, "Not found")
        key = os.environ.get("TANK_KEY_MARKET_LAB", "")
        if not key:
            raise HTTPException(503, "Market Lab is not connected")
        try:
            response = await tank.shared_http().post(
                "http://agent-market-lab:8000/market/" + operation,
                json=body.model_dump(mode="json"), headers={"x-tank-key": key}, timeout=30,
            )
            if response.status_code >= 400:
                status = response.status_code if response.status_code in {404, 422, 503} else 502
                raise HTTPException(status, "Market Lab could not complete this request")
            return JSONResponse(response.json(), headers={"Cache-Control": "private, no-store"})
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(502, "Market Lab could not complete this request") from None

    return router
