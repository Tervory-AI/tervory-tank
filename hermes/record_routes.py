"""SQL record and founder publication routes. Internal authenticated service only."""

import os
import uuid
from datetime import datetime
from typing import Literal

from fastapi import Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from hermes.auth import identify
from hermes.publishing import Publisher
from hermes.references import reference_corpora


class Scoped(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    tenant_id: uuid.UUID
    agent: str = Field(pattern=r"^[a-z][a-z0-9_]{0,40}$")


class FounderMemory(Scoped):
    id: uuid.UUID
    claim: str = Field(min_length=1, max_length=8000)
    evidence: list[str] = Field(default_factory=list, max_length=100)
    confidence: float = Field(default=0.5, ge=0, le=1)
    last_verified: datetime | None = None


class IdentityInventory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewed: bool = False
    names: list[str] = Field(max_length=500)
    emails: list[str] = Field(max_length=500)
    phones: list[str] = Field(max_length=500)
    addresses: list[str] = Field(max_length=500)
    client_domains: list[str] = Field(max_length=500)


class Policy(Scoped):
    enabled: bool = False
    identifiers: IdentityInventory | None = None


class Publication(Scoped):
    source_row: uuid.UUID


def founder(key: str, user: str) -> str:
    allowed = {
        v.strip()
        for v in os.environ.get("TERVORY_ADMIN_USER_IDS", "").split(",")
        if v.strip()
    }
    try:
        permitted = identify(key) is None and user in allowed
    except HTTPException:
        permitted = False
    if not permitted:
        raise HTTPException(404, "not found")
    return user


def register_record_routes(app, records, resolve_agent):
    def ready(agent: str):
        r = records()
        if r is None:
            raise HTTPException(503, "memory store unreachable")
        if agent not in r.agents:
            raise HTTPException(404, "Unknown agent.")
        return r

    @app.get("/records")
    async def listing(
        tenant_id: uuid.UUID,
        agent: str | None = None,
        tier: Literal["client", "platform"] = "client",
        x_tank_key: str = Header(default=""),
    ):
        selected = resolve_agent(identify(x_tank_key), agent, write=False)
        return {"memories": await ready(selected).list(selected, str(tenant_id), tier)}

    @app.get("/reference-corpora")
    async def references(
        tenant_id: uuid.UUID,
        agent: str | None = None,
        x_tank_key: str = Header(default=""),
    ):
        selected = resolve_agent(identify(x_tank_key), agent, write=False)
        return dict(
            tenant_id=str(tenant_id),
            corpora=reference_corpora(selected, os.environ.get("TANK_REGION", "")),
        )

    @app.get("/founder/records")
    async def founder_records(
        tenant_id: uuid.UUID,
        agent: str,
        tier: Literal["client", "platform"] = "client",
        x_tank_key: str = Header(default=""),
        x_tervory_admin: str = Header(default=""),
    ):
        founder(x_tank_key, x_tervory_admin)
        return {"memories": await ready(agent).list(agent, str(tenant_id), tier)}

    @app.post("/founder/memories")
    async def remember(
        body: FounderMemory,
        x_tank_key: str = Header(default=""),
        x_tervory_admin: str = Header(default=""),
    ):
        founder(x_tank_key, x_tervory_admin)
        try:
            return await ready(body.agent).save(
                body.agent,
                str(body.tenant_id),
                body.claim,
                body.evidence,
                confidence=body.confidence,
                last_verified=body.last_verified,
                row_id=str(body.id),
            )
        except ValueError:
            raise HTTPException(409, "Memory record conflict") from None

    @app.post("/founder/publish-policy")
    async def policy(
        body: Policy,
        x_tank_key: str = Header(default=""),
        x_tervory_admin: str = Header(default=""),
    ):
        actor = founder(x_tank_key, x_tervory_admin)
        try:
            return await Publisher(ready(body.agent)).set_policy(
                body.agent,
                str(body.tenant_id),
                actor,
                body.enabled,
                body.identifiers.model_dump() if body.identifiers else {},
            )
        except ValueError:
            raise HTTPException(422, "Reviewed identity inventory required") from None

    @app.post("/founder/publish")
    async def publish(
        body: Publication,
        x_tank_key: str = Header(default=""),
        x_tervory_admin: str = Header(default=""),
    ):
        actor = founder(x_tank_key, x_tervory_admin)
        result = await Publisher(ready(body.agent)).publish(
            body.agent, str(body.tenant_id), str(body.source_row), actor
        )
        if result["result"] not in ("published", "already_published"):
            raise HTTPException(403 if result["result"] == "disabled" else 409, result)
        return result
