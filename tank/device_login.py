"""CLI sign-in by device approval (RFC 8628 shape) on the existing Workspace login.

`tervory login` asks this box for a device code, the signed-in Workspace user
approves it on one page, and the CLI polls for an org-scoped credential. No
token is ever pasted, printed or stored in plaintext here:

* device codes, access and refresh tokens are stored only as SHA-256 hashes;
* the credential is a row in tank.personal_tokens (the CLI-1 table), scoped to
  the approving user's org (tenant) on this box, with expiry, rotating refresh,
  last_used_at and revoke;
* approval and denial use the Workspace service key plus the Clerk-derived user
  and tenant headers (command.identity), never a CLI bearer. On a ZA box the
  dedicated TANK_DEVICE_APPROVAL_KEY (held by the Boston Workspace as
  TANK_DEVICE_APPROVAL_KEY_ZA) is also accepted for these two routes only
  (personal_tokens.device_approval_actor), with the same user/tenant checks.
  The ZA homes key is not.

Unauthenticated callers can only create a pending code, poll with the secret
device code, refresh with the secret refresh token, or revoke a credential they
hold. Approval requires a signed-in Workspace session.
"""
from __future__ import annotations

import os
import re
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

import command
import personal_tokens as pat
from tenant_db import tenant_scope

router = APIRouter(prefix="/v1/command/device", tags=["cli device login"])

CODE_TTL = timedelta(minutes=10)
POLL_INTERVAL_S = 5
ACCESS_TTL = timedelta(hours=1)
REFRESH_TTL = timedelta(days=30)
MAX_PENDING = 500  # per box; bounds unauthenticated row creation
# Unambiguous consonants only: no vowels (no words), no 0/O or 1/I confusion.
ALPHABET = "BCDFGHJKLMNPQRSTVWXZ"
USER_CODE = re.compile(r"[BCDFGHJKLMNPQRSTVWXZ]{4}-[BCDFGHJKLMNPQRSTVWXZ]{4}\Z")
DEVICE_CODE = re.compile(r"tvd1\.(us-east|za)\.([A-Za-z0-9_-]{43})\Z")
REFRESH = re.compile(r"tvr1\.(us-east|za)\.([0-9a-f]{32})\.([A-Za-z0-9_-]{43})\Z")
NO_STORE = {"Cache-Control": "no-store", "Pragma": "no-cache"}


class NewCode(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_name: str = Field(min_length=1, max_length=100)


class Poll(BaseModel):
    model_config = ConfigDict(extra="forbid")
    device_code: str = Field(min_length=1, max_length=200)


class Refresh(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: str = Field(min_length=1, max_length=200)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["approve", "deny"]


def now() -> datetime:
    return datetime.now(timezone.utc)


def region() -> str:
    from main import box_region
    value = box_region()
    if value not in {"us-east", "za"}:
        raise HTTPException(503, "CLI sign-in is unavailable on this box")
    return value


def workspace_url() -> str:
    # The one Workspace with the Clerk login; ZA has a Tank-only public host.
    return (os.environ.get("TERVORY_WORKSPACE_URL") or "https://app.tervory.com").rstrip("/")


def clean_name(value: str) -> str:
    name = re.sub(r"[\x00-\x1f\x7f-\x9f]", "", value).strip()
    if not name:
        raise HTTPException(422, "A device name is required")
    return name[:100]


def user_code() -> str:
    letters = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{letters[:4]}-{letters[4:]}"


def error(code: str, status: int = 400) -> JSONResponse:
    # RFC 8628 section 3.5 error names; never echo the presented secret.
    return JSONResponse({"error": code}, status_code=status, headers=NO_STORE)


def credential_pair(box: str, tenant: uuid.UUID) -> tuple[str, str]:
    access = f"tv1.{box}.{tenant.hex}.{secrets.token_urlsafe(32)}"
    refresh = f"tvr1.{box}.{tenant.hex}.{secrets.token_urlsafe(32)}"
    return access, refresh


def grant(access: str, refresh: str, token_id: uuid.UUID, box: str, issued: datetime) -> dict[str, Any]:
    return {"token_type": "Bearer", "access_token": access, "refresh_token": refresh,
            "expires_in": int(ACCESS_TTL.total_seconds()), "refresh_expires_in": int(REFRESH_TTL.total_seconds()),
            "expires_at": (issued + ACCESS_TTL).isoformat(), "refresh_expires_at": (issued + REFRESH_TTL).isoformat(),
            "region": box, "credential_id": str(token_id)}


def platform():
    # Lookups keyed by a secret hash (device code) or by a short-lived user code
    # under a signed-in Workspace approval, before the tenant is known.
    return tenant_scope(None, administrative=True)


@router.post("/code")
async def create_code(body: NewCode) -> JSONResponse:
    box = region()
    import identity_oidc
    if identity_oidc.configured():
        from identity_device import create
        return await create(clean_name(body.device_name))
    device_code = f"tvd1.{box}.{secrets.token_urlsafe(32)}"
    name = clean_name(body.device_name)
    with platform():
        async with command.db().acquire() as conn:
            await conn.execute("DELETE FROM tank.device_authorizations WHERE expires_at < now() - interval '1 day'")
            pending = await conn.fetchval(
                "SELECT count(*) FROM tank.device_authorizations WHERE status='pending' AND expires_at > now()")
            if pending >= MAX_PENDING:
                return error("slow_down", 429)
            for _ in range(5):
                code = user_code()
                row = await conn.fetchrow(
                    "INSERT INTO tank.device_authorizations(device_hash,user_code,region,device_name,expires_at) "
                    "VALUES($1,$2,$3,$4,now()+$5::interval) ON CONFLICT DO NOTHING RETURNING expires_at",
                    pat.digest(device_code), code, box, name, CODE_TTL)
                if row is not None:
                    break
            else:
                raise HTTPException(503, "Could not allocate a sign-in code")
    query = urlencode({"code": code, "region": box})
    return JSONResponse({
        "device_code": device_code, "user_code": code,
        "verification_uri": f"{workspace_url()}/cli/device",
        "verification_uri_complete": f"{workspace_url()}/cli/device?{query}",
        "expires_in": int(CODE_TTL.total_seconds()), "interval": POLL_INTERVAL_S, "region": box,
    }, headers=NO_STORE)


@router.post("/token")
async def poll(body: Poll) -> JSONResponse:
    box = region()
    import identity_oidc
    if body.device_code.startswith('tzd1.') and identity_oidc.configured():
        from identity_device import poll as identity_poll
        return await identity_poll(body.device_code)
    match = DEVICE_CODE.fullmatch(body.device_code)
    if match is None or match.group(1) != box:
        return error("invalid_grant")
    with platform():
        async with command.db().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT device_hash,status,tenant_id,user_id,device_name,expires_at,last_polled_at "
                "FROM tank.device_authorizations WHERE device_hash=$1 AND region=$2 FOR UPDATE",
                pat.digest(body.device_code), box)
            if row is None:
                return error("invalid_grant")
            if row["expires_at"] <= now():
                return error("expired_token")
            if row["status"] == "denied":
                return error("access_denied")
            if row["status"] == "consumed":
                return error("invalid_grant")
            if row["status"] == "pending":
                fast = row["last_polled_at"] is not None and now() - row["last_polled_at"] < timedelta(seconds=POLL_INTERVAL_S - 1)
                await conn.execute("UPDATE tank.device_authorizations SET last_polled_at=now() WHERE device_hash=$1",
                                   row["device_hash"])
                return error("slow_down" if fast else "authorization_pending")
            # Approved: single use. Consume before minting so a replay cannot mint twice.
            consumed = await conn.fetchval(
                "UPDATE tank.device_authorizations SET status='consumed',decided_at=coalesce(decided_at,now()) "
                "WHERE device_hash=$1 AND status='approved' RETURNING device_hash", row["device_hash"])
            if consumed is None:
                return error("invalid_grant")
    tenant, user = row["tenant_id"], row["user_id"]
    access, refresh = credential_pair(box, tenant)
    issued = now()
    with tenant_scope(tenant):
        async with command.db().acquire() as conn:
            token_id = await conn.fetchval(
                "INSERT INTO tank.personal_tokens(tenant_id,user_id,region,name,token_hash,device_name,"
                "expires_at,refresh_hash,refresh_expires_at) VALUES($1,$2,$3,$4,$5,$4,$6,$7,$8) RETURNING token_id",
                tenant, user, box, row["device_name"], pat.digest(access), issued + ACCESS_TTL,
                pat.digest(refresh), issued + REFRESH_TTL)
    with platform():
        async with command.db().acquire() as conn:
            await conn.execute("UPDATE tank.device_authorizations SET token_id=$2 WHERE device_hash=$1",
                               row["device_hash"], token_id)
    return JSONResponse(grant(access, refresh, token_id, box, issued), headers=NO_STORE)


@router.post("/refresh")
async def refresh(body: Refresh) -> JSONResponse:
    box = region()
    match = REFRESH.fullmatch(body.refresh_token)
    if match is None or match.group(1) != box:
        return error("invalid_grant")
    tenant = uuid.UUID(hex=match.group(2))
    access, rotated = credential_pair(box, tenant)
    issued = now()
    with tenant_scope(tenant):
        async with command.db().acquire() as conn:
            # Rotation: the presented refresh token and the old access token stop working.
            token_id = await conn.fetchval(
                "UPDATE tank.personal_tokens SET token_hash=$4,expires_at=$5,refresh_hash=$6,refresh_expires_at=$7 "
                "WHERE tenant_id=$1 AND region=$2 AND refresh_hash=$3 AND revoked_at IS NULL "
                "AND refresh_expires_at > now() RETURNING token_id",
                tenant, box, pat.digest(body.refresh_token), pat.digest(access), issued + ACCESS_TTL,
                pat.digest(rotated), issued + REFRESH_TTL)
    if token_id is None:
        return error("invalid_grant")
    return JSONResponse(grant(access, rotated, token_id, box, issued), headers=NO_STORE)


@router.post("/revoke")
async def revoke(request: Request) -> JSONResponse:
    """Revoke the credential the caller holds: bearer access token or body refresh token."""
    box = region()
    token = None
    authorization = request.headers.get("authorization") or ""
    scheme, _, bearer = authorization.partition(" ")
    if scheme.lower() == "bearer" and pat.TOKEN.fullmatch(bearer):
        token, column = bearer, "token_hash"
    else:
        try:
            payload = await request.json()
        except Exception:  # noqa: BLE001 - any unreadable body is a refusal
            payload = None
        presented = payload.get("refresh_token") if isinstance(payload, dict) else None
        if isinstance(presented, str) and REFRESH.fullmatch(presented):
            token, column = presented, "refresh_hash"
    if token is None:
        return error("invalid_request")
    parts = token.split(".")
    if parts[1] != box:
        return error("invalid_grant")
    tenant = uuid.UUID(hex=parts[2])
    with tenant_scope(tenant):
        async with command.db().acquire() as conn:
            await conn.execute(
                f"UPDATE tank.personal_tokens SET revoked_at=coalesce(revoked_at,now()) "
                f"WHERE tenant_id=$1 AND region=$2 AND {column}=$3", tenant, box, pat.digest(token))
    # RFC 7009: the same answer whether or not the token existed.
    return JSONResponse({"revoked": True}, headers=NO_STORE)


async def pending(conn: Any, code: str, box: str) -> Any:
    if not USER_CODE.fullmatch(code):
        raise HTTPException(404, "Sign-in code not found")
    row = await conn.fetchrow(
        "SELECT device_hash,user_code,region,device_name,status,created_at,expires_at FROM tank.device_authorizations "
        "WHERE user_code=$1 AND region=$2 AND provider='workspace' FOR UPDATE", code, box)
    if row is None or row["status"] != "pending" or row["expires_at"] <= now():
        raise HTTPException(404, "Sign-in code not found or expired")
    return row


@router.get("/approval/{code}")
async def approval(code: str, actor: command.Actor = Depends(pat.device_approval_actor)) -> JSONResponse:
    box = region()
    with platform():
        async with command.db().acquire() as conn:
            row = await pending(conn, code, box)
    return JSONResponse({"user_code": row["user_code"], "device_name": row["device_name"], "region": row["region"],
                         "created_at": row["created_at"].isoformat(), "expires_at": row["expires_at"].isoformat(),
                         "status": row["status"]}, headers=NO_STORE)


@router.post("/approval/{code}")
async def decide(code: str, body: Decision, actor: command.Actor = Depends(pat.device_approval_actor)) -> JSONResponse:
    box = region()
    with platform():
        async with command.db().acquire() as conn:
            row = await pending(conn, code, box)
            status = "approved" if body.action == "approve" else "denied"
            await conn.execute(
                "UPDATE tank.device_authorizations SET status=$2,tenant_id=$3,user_id=$4,decided_at=now() "
                "WHERE device_hash=$1 AND status='pending'",
                row["device_hash"], status, actor.tenant_id if status == "approved" else None,
                actor.user_id if status == "approved" else None)
    return JSONResponse({"user_code": row["user_code"], "device_name": row["device_name"], "status": status},
                        headers=NO_STORE)
