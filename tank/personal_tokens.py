"""CLI-1 personal tokens: server-derived identity, local box, hash-only storage.

The tenant in the opaque token envelope selects a database scope only. No
identity is accepted until the complete token hash matches an unrevoked row.
Management endpoints deliberately require the original Workspace dependency.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

import command
from tenant_db import tenant_scope

router = APIRouter(prefix="/v1/personal-tokens", tags=["personal tokens"])
TOKEN = re.compile(r"tv1\.(us-east|za)\.([0-9a-f]{32})\.([A-Za-z0-9_-]{43})\Z")


class NewToken(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


async def workspace_actor(request: Request) -> command.Actor:
    # Do not permit a PAT to mint new PATs or manage Workspace credentials.
    return await command.identity(request)


async def identity(request: Request) -> command.Actor:
    authorization = request.headers.get("authorization")
    if authorization is None:
        return await command.identity(request)
    scheme, _, token = authorization.partition(" ")
    match = TOKEN.fullmatch(token) if scheme.lower() == "bearer" else None
    if match is None:
        raise HTTPException(401, "Personal token refused")
    from main import box_region
    region, tenant_hex, _ = match.groups()
    if region != box_region():
        raise HTTPException(403, "Personal token belongs to another box")
    tenant = uuid.UUID(hex=tenant_hex)
    with tenant_scope(tenant):
        async with command.db().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT token_id,user_id,last_used_at < now() - interval '1 minute' AS stale FROM tank.personal_tokens "
                "WHERE tenant_id=$1 AND region=$2 AND token_hash=$3 AND revoked_at IS NULL "
                "AND (expires_at IS NULL OR expires_at > now())",
                tenant, region, digest(token),
            )
            if row is not None and row.get("stale") is not False:
                # At most one write a minute per credential; NULL means never used.
                await conn.execute("UPDATE tank.personal_tokens SET last_used_at=now() WHERE tenant_id=$1 AND token_id=$2",
                                   tenant, row["token_id"])
        if row is None:
            raise HTTPException(401, "Personal token refused")
        # Headers for user, tenant, role and squad are never used on this path.
        # Existing Tank authorization re-reads founder membership and squad grants.
        return await command.authorized_actor(command.Actor(tenant, row["user_id"], False))


@router.post("", status_code=201)
async def create_token(body: NewToken, response: Response,
                       actor: command.Actor = Depends(workspace_actor)) -> dict[str, Any]:
    from main import box_region
    region = box_region()
    if region not in {"us-east", "za"}:
        raise HTTPException(503, "Personal tokens unavailable on this box")
    token = f"tv1.{region}.{actor.tenant_id.hex}.{secrets.token_urlsafe(32)}"
    with tenant_scope(actor.tenant_id):
        async with command.db().acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO tank.personal_tokens(tenant_id,user_id,region,name,token_hash) "
                "VALUES($1,$2,$3,$4,$5) RETURNING token_id,name,region,created_at",
                actor.tenant_id, actor.user_id, region, body.name, digest(token),
            )
    response.headers["Cache-Control"] = "no-store"
    return {**dict(row), "token": token}


@router.get("")
async def list_tokens(response: Response,
                      actor: command.Actor = Depends(workspace_actor)) -> list[dict[str, Any]]:
    with tenant_scope(actor.tenant_id):
        async with command.db().acquire() as conn:
            rows = await conn.fetch(
                "SELECT token_id,name,region,device_name,created_at,expires_at,last_used_at,revoked_at FROM tank.personal_tokens "
                "WHERE tenant_id=$1 AND user_id=$2 ORDER BY created_at DESC,token_id",
                actor.tenant_id, actor.user_id,
            )
    response.headers["Cache-Control"] = "no-store"
    return [dict(row) for row in rows]


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: uuid.UUID, actor: command.Actor = Depends(workspace_actor)) -> Response:
    with tenant_scope(actor.tenant_id):
        async with command.db().acquire() as conn:
            row = await conn.fetchrow(
                "UPDATE tank.personal_tokens SET revoked_at=COALESCE(revoked_at,now()) "
                "WHERE tenant_id=$1 AND user_id=$2 AND token_id=$3 RETURNING token_id",
                actor.tenant_id, actor.user_id, token_id,
            )
    if row is None:
        raise HTTPException(404, "Personal token not found")
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


def register(app: Any) -> None:
    app.include_router(router)
    # CLI sign-in by device approval issues rows in this same table.
    app.include_router(__import__("device_login").router)
    # The same command endpoints, validation, confirms and receipts serve both
    # clients. Do not broaden Tank's global service-key dependency.
    app.dependency_overrides[command.identity] = identity
