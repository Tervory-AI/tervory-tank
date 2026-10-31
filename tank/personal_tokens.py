"""CLI-1 personal tokens: server-derived identity, local box, hash-only storage.

The tenant in the opaque token envelope selects a database scope only. No
identity is accepted until the complete token hash matches an unrevoked row.
Management endpoints deliberately require the original Workspace dependency.
"""
from __future__ import annotations

import hashlib
import os
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


# Approving a ZA CLI sign-in happens on the Boston Workspace's Clerk page, but the
# Boston Workspace never holds the ZA TANK_API_KEY, and its ZA homes key
# (TANK_HOMES_KEY, Boston's TANK_API_KEY_ZA) stays limited to the Zenas homes and
# feeds routes. So the ZA Tank accepts one dedicated key, TANK_DEVICE_APPROVAL_KEY
# (Boston holds it as TANK_DEVICE_APPROVAL_KEY_ZA), for exactly the two
# device-approval routes below (GET shows a pending code, POST approves or denies
# it), on a ZA box only. The signed-in user and tenant headers are still required
# and checked exactly as for the Workspace key. The key is refused everywhere else,
# and refused outright if it is unset or equal to the Workspace or homes key (a
# misconfiguration that would blur the scopes).
DEVICE_APPROVAL_PATH = re.compile(r"/v1/command/device/approval/[BCDFGHJKLMNPQRSTVWXZ]{4}-[BCDFGHJKLMNPQRSTVWXZ]{4}\Z")


def device_approval_key() -> str:
    """The ZA Tank's dedicated device-approval key, or '' when unset or not distinct."""
    from main import TANK_API_KEY
    key = os.environ.get("TANK_DEVICE_APPROVAL_KEY", "").strip()
    others = {TANK_API_KEY.strip(), os.environ.get("TANK_HOMES_KEY", "").strip()} - {""}
    return "" if not key or key in others else key


def device_approval_key_may_approve(request: Request) -> bool:
    from main import box_region
    key = device_approval_key()
    return (bool(key) and box_region() == "za" and request.method in {"GET", "POST"}
            and DEVICE_APPROVAL_PATH.fullmatch(request.url.path) is not None
            and command.key_matches(request.headers.get("x-tank-key", ""), key))


async def device_approval_actor(request: Request) -> command.Actor:
    """Workspace key, or (ZA box, approval routes only) the dedicated device-approval key; user and tenant always required."""
    if device_approval_key_may_approve(request):
        actor = await command.signed_in_actor(request)
        # Review of #506, should-fix 1: this key lives on the Boston Workspace and the
        # user header is its assertion. It must never approve (and so mint) a CLI
        # credential for a founder: a founder signs in to the ZA CLI with the ZA
        # Workspace key path, never this one. Checked on the raw admin list, before
        # any squad or role lookup could matter.
        admins = {s.strip() for s in os.environ.get("TERVORY_ADMIN_USER_IDS", "").split(",") if s.strip()}
        if actor.founder or actor.user_id in admins:
            raise HTTPException(403, "This sign-in cannot be approved here")
        return actor
    return await command.identity(request)


# A CLI credential authenticates the CLI corridor and nothing else. register() puts
# this dependency in place of command.identity app-wide, and on ZA the CLI talks to
# the public Tank directly, so without this list a CLI token would also reach every
# other route built on command.identity (access, event bus, triggers, case studies,
# squads, repo, attachments, worker follow-ups...). It mirrors the Workspace corridor
# (workspace/lib/tank.ts personalCommandRequest) plus the founder-only model roster,
# which the route itself answers 404 for everyone else. Review of #506, self-review (b)/(c).
_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
CLI_ROUTES = {
    "GET": re.compile(rf"/v1/command/(models|tools|threads|threads/{_UUID}(/events)?|tasks/{_UUID}/receipts)\Z"),
    "POST": re.compile(rf"/v1/command/(threads|threads/{_UUID}/(turn|actions)|cards/{_UUID}|build)\Z"),
    "PATCH": re.compile(rf"/v1/command/threads/{_UUID}\Z"),
}


def cli_route(request: Request) -> bool:
    pattern = CLI_ROUTES.get(request.method)
    return pattern is not None and pattern.fullmatch(request.url.path) is not None


async def identity(request: Request) -> command.Actor:
    authorization = request.headers.get("authorization")
    if authorization is None:
        return await command.identity(request)
    if not cli_route(request):
        # Same answer as an unknown route; no database lookup, nothing about the token.
        raise HTTPException(404, "Not Found")
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
