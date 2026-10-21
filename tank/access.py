"""Tenant connections, official feeds and human browser handoffs.

The room/Workspace APIs never return a credential. Browser RPCs are encrypted
end to end with a separate key held only by Tank and that room's browser.
"""
from __future__ import annotations

import asyncio
import csv
import io
import ipaddress
import json
import os
import re
import socket
import uuid
from datetime import datetime, timedelta, timezone
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError

import vault
from command import Actor, identity, key_matches

async def rotation_reminders():
    # Each inserted reminder retains the credential row's tenant. No credential
    # or client data is read into application memory by this maintenance job.
    async with db().acquire() as conn:
        await conn.execute("""INSERT INTO tank.access_queue(tenant_id,room,site,reason)
            SELECT c.tenant_id,c.room,c.site,'rotation_due' FROM tank.access_connections c
            LEFT JOIN tank.access_sites p ON p.tenant_id=$1 AND p.site=c.site
            WHERE NOT c.revoked AND c.updated_at + make_interval(days => COALESCE(p.rotation_days,90)) <= now()
            ON CONFLICT (tenant_id,room,site) WHERE status IN ('waiting','handling') DO NOTHING""", PLATFORM)


async def reminder_loop():
    import logging
    while True:
        await asyncio.sleep(3600)
        try:
            await rotation_reminders()
        except Exception:
            logging.getLogger(__name__).warning("Connection renewal reminders are unavailable.")


@asynccontextmanager
async def access_lifespan(app):
    from contextlib import suppress
    task = asyncio.create_task(reminder_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError): await task


router = APIRouter(prefix="/v1/access", lifespan=access_lifespan)
PLATFORM = uuid.UUID("00000000-0000-0000-0000-000000000001")
ROOMS = {"base": "http://base-browser-gateway:3000", "tiger": "http://tiger-browser-gateway:3000"}
SOCIAL = ("facebook.com", "instagram.com", "fb.com", "fb.me")
DISTRIBUTORS = ("zanders", "sports_south", "rsr", "jerrys")


def db():
    from main import pool
    return pool()


def origin(value: str, *, https: bool = True) -> str:
    try:
        p = urlsplit(value)
        host = (p.hostname or "").lower().rstrip(".")
        if (p.scheme not in ({"https"} if https else {"https", "http"}) or not host
                or p.username or p.password or p.port not in (None, 443 if p.scheme == "https" else 80)
                or host in {"localhost", "metadata.google.internal"}
                or host.endswith((".localhost", ".local", ".internal"))):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address and (not address.is_global or address.is_multicast):
            raise ValueError()
        return p.scheme + "://" + ("[" + host + "]" if ":" in host else host)
    except ValueError:
        raise HTTPException(422, "Use a public site address without credentials.") from None


def site_name(value: str) -> str:
    result = origin(value)
    if value.rstrip("/") != result:
        raise HTTPException(422, "Use the site's HTTPS address without a path or query.")
    return result


def is_social(site: str) -> bool:
    host = urlsplit(site).hostname or ""
    return any(host == s or host.endswith("." + s) for s in SOCIAL)


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


async def parse(request: Request, model, limit: int = 16000):
    # FastAPI's default validation response includes rejected input. Credentials
    # must never enter that path, exception strings, tracing or response bodies.
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > limit:
            raise HTTPException(413, "Connection request is too large.")
    try:
        return model.model_validate_json(bytes(data))
    except (ValidationError, ValueError):
        raise HTTPException(422, "Check the connection fields and try again.") from None


class SitePolicy(Body):
    site: str = Field(max_length=240)
    terms: Literal["yes", "no", "unknown"]
    rotation_days: int = Field(default=90, ge=1, le=365)
    login_path: str = Field(default="/login", max_length=500)
    username_selector: str = Field(default='input[autocomplete="username"]', max_length=200)
    password_selector: str = Field(default='input[type="password"]', max_length=200)
    submit_selector: str = Field(default='button[type="submit"]', max_length=200)
    success_selector: str = Field(default='a[href*="logout"]', max_length=200)
    price_selector: str = Field(default="", max_length=200)
    quantity_selector: str = Field(default="", max_length=200)
    totp_selector: str = Field(default='input[autocomplete="one-time-code"]', max_length=200)


class Credential(Body):
    room: Literal["base", "tiger"]
    site: str = Field(max_length=240)
    username: SecretStr = Field(min_length=1, max_length=200)
    password: SecretStr = Field(min_length=1, max_length=2048)
    totp: SecretStr = Field(default=SecretStr(""), max_length=128)
    dedicated_read_only: Literal[True]
    device_enrolled: bool = False


class Connection(Body):
    room: Literal["base", "tiger"]
    site: str = Field(max_length=240)


def permit_room(actor: Actor, room: str):
    if room not in ROOMS or (not actor.founder and room not in actor.squads):
        raise HTTPException(403, "This room is not enabled for this account.")


async def receipt(conn, tenant, room: str, site: str, actor: str, action: str, *, duration_ms=0, row_count=None):
    # An explicit projection, never a request body, exception or URL path.
    await conn.execute("""INSERT INTO tank.access_receipts
        (tenant_id,room,site,actor,action,duration_ms,row_count) VALUES($1,$2,$3,$4,$5,$6,$7)""",
        tenant, room, site, actor, action, duration_ms, row_count)


async def enqueue(conn, tenant, room: str, site: str, reason: str, handle=None, task=None):
    row = await conn.fetchrow("""INSERT INTO tank.access_queue(tenant_id,room,site,reason,browser_handle,task_id)
        VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT (tenant_id,room,site) WHERE status IN ('waiting','handling')
        DO UPDATE SET reason=EXCLUDED.reason,browser_handle=EXCLUDED.browser_handle,
        task_id=COALESCE(EXCLUDED.task_id,tank.access_queue.task_id),status='waiting',handler=NULL,started_at=NULL RETURNING id""",
        tenant, room, site, reason, handle, task)
    return str(row["id"])


@router.get("/connections")
async def connections(actor: Actor = Depends(identity)):
    async with db().acquire() as conn:
        rows = await conn.fetch("""SELECT c.room,c.site,c.updated_at,c.clear_pending,c.revoked,
            COALESCE(p.terms,'unknown') AS terms,COALESCE(p.rotation_days,90) AS rotation_days,
            c.updated_at + make_interval(days => COALESCE(p.rotation_days,90)) AS rotate_by
            FROM tank.access_connections c LEFT JOIN tank.access_sites p ON p.tenant_id=$2 AND p.site=c.site
            WHERE c.tenant_id=$1 ORDER BY c.site,c.room""", actor.tenant_id, PLATFORM)
        policies = await conn.fetch("SELECT site,terms,rotation_days FROM tank.access_sites WHERE tenant_id=$1 ORDER BY site", PLATFORM)
        feeds = await conn.fetch("""SELECT distributor,site,source,fetched_at,row_count FROM tank.access_feed_batches
            WHERE tenant_id=$1 ORDER BY fetched_at DESC LIMIT 30""", actor.tenant_id)
    now = datetime.now(timezone.utc)
    return {"connections": [{**dict(r), "overdue": r["rotate_by"] <= now} for r in rows],
            "policies": [dict(r) for r in policies], "feeds": [dict(r) for r in feeds],
            "meta_enabled": bool(os.environ.get("META_APP_ID")) and os.environ.get("META_APP_REVIEW_APPROVED") == "true"}


@router.post("/sites")
async def policy(request: Request, actor: Actor = Depends(identity)):
    if not actor.founder:
        raise HTTPException(403, "Only the founder may set site terms.")
    body = await parse(request, SitePolicy)
    site = site_name(body.site)
    if is_social(site) or not body.login_path.startswith("/") or body.login_path.startswith("//") or any(c in body.login_path for c in "?#\\"):
        raise HTTPException(422, "Use a same-site login path; social logins are not supported.")
    async with db().acquire() as conn:
        await conn.execute("""INSERT INTO tank.access_sites(tenant_id,site,terms,rotation_days,login_config)
            VALUES($1,$2,$3,$4,$5::jsonb) ON CONFLICT(tenant_id,site) DO UPDATE SET
            terms=$3,rotation_days=$4,login_config=$5::jsonb,updated_at=now()""", PLATFORM, site,
            body.terms, body.rotation_days, json.dumps(body.model_dump(exclude={"site", "terms", "rotation_days"})))
        await receipt(conn, PLATFORM, "platform", site, actor.user_id, "terms_updated")
    return {"ok": True}


async def control(room: str, data: dict) -> dict:
    key = os.environ.get("TANK_KEY_" + room.upper(), "")
    if not key:
        raise HTTPException(503, "The room's browser is not connected.")
    payload = vault.envelope(room, "control", data)
    try:
        async with httpx.AsyncClient(timeout=35, trust_env=False) as client:
            response = await client.post(ROOMS[room] + "/access/control", json=payload, headers={"X-Tank-Key": key})
        if response.status_code != 200:
            raise ValueError()
        result = vault.open_envelope(room, "result", response.json())
        if result.get("request_nonce") != vault.open_envelope(room, "control", payload)["nonce"]:
            raise ValueError()
        if result.get("error"):
            raise HTTPException(409, "The live page is no longer available; retry the page to open a new check.")
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "The room's browser is unavailable. Session removal has not been confirmed.") from None


async def clear_session(tenant, room, site):
    result = await control(room, {"action": "revoke", "tenant_id": str(tenant), "site": site})
    if result.get("cleared") is not True:
        raise HTTPException(503, "Session removal has not been confirmed.")
    async with db().acquire() as conn:
        await conn.execute("UPDATE tank.access_connections SET clear_pending=false WHERE tenant_id=$1 AND room=$2 AND site=$3", tenant, room, site)
        await receipt(conn, tenant, room, site, "browser", "logout")


@asynccontextmanager
async def connection_change(tenant, room, site):
    # Serialize rotate/revoke across Tank workers without holding a row lock
    # while the browser calls back for its current policy.
    name = f"{tenant}:{room}:{site}"
    async with db().acquire() as conn:
        await conn.execute("SELECT pg_advisory_lock(hashtextextended($1,0))", name)
        try:
            yield
        finally:
            await conn.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))", name)


@router.post("/credentials")
async def credentials(request: Request, actor: Actor = Depends(identity)):
    body = await parse(request, Credential)
    permit_room(actor, body.room)
    site = site_name(body.site)
    if is_social(site) or (body.totp.get_secret_value() and not body.device_enrolled):
        raise HTTPException(422, "Use a dedicated distributor account and enroll authenticator devices deliberately.")
    secret = {name: getattr(body, name).get_secret_value() for name in ("username", "password", "totp")}
    if secret["totp"]:
        import base64
        try:
            base64.b32decode(secret["totp"].upper(), casefold=True)
        except Exception:
            raise HTTPException(422, "Check the authenticator enrollment.") from None
    encrypted = vault.seal(secret, vault.context(actor.tenant_id, body.room, site, "login"))
    async with connection_change(actor.tenant_id, body.room, site):
        # Disable the old generation before clearing its cookies. A failed clear is
        # visible and leaves login denied; no old session is silently reused.
        async with db().acquire() as conn:
            await conn.execute("""INSERT INTO tank.access_connections(tenant_id,room,site,sealed,revoked,clear_pending)
                VALUES($1,$2,$3,NULL,true,true) ON CONFLICT(tenant_id,room,site)
                DO UPDATE SET sealed=NULL,revoked=true,clear_pending=true,version=gen_random_uuid()""", actor.tenant_id, body.room, site)
        await clear_session(actor.tenant_id, body.room, site)
        async with db().acquire() as conn:
            await conn.execute("""UPDATE tank.access_connections SET sealed=$4,revoked=false,updated_at=now(),version=gen_random_uuid()
                WHERE tenant_id=$1 AND room=$2 AND site=$3""", actor.tenant_id, body.room, site, encrypted)
            await receipt(conn, actor.tenant_id, body.room, site, actor.user_id, "credential_updated")
        return {"ok": True}


@router.post("/revoke")
async def revoke(request: Request, actor: Actor = Depends(identity)):
    body = await parse(request, Connection)
    site = site_name(body.site)
    async with connection_change(actor.tenant_id, body.room, site):
        async with db().acquire() as conn:
            await conn.execute("""UPDATE tank.access_connections SET sealed=NULL,revoked=true,clear_pending=true,
                version=gen_random_uuid() WHERE tenant_id=$1 AND room=$2 AND site=$3""", actor.tenant_id, body.room, site)
            await conn.execute("""UPDATE tank.access_queue SET status='revoked' WHERE tenant_id=$1 AND room=$2
                AND site=$3 AND status IN ('waiting','handling')""", actor.tenant_id, body.room, site)
            await receipt(conn, actor.tenant_id, body.room, site, actor.user_id, "revoked")
        await clear_session(actor.tenant_id, body.room, site)
        return {"ok": True, "credential_deleted": True, "session_deleted": True}


class Sealed(Body):
    sealed: str = Field(max_length=24000)


async def browser_policy(conn, tenant, room, site):
    row = await conn.fetchrow("""SELECT c.*,COALESCE(p.terms,'unknown') AS terms,
        COALESCE(p.rotation_days,90) AS rotation_days,p.login_config FROM tank.access_connections c
        LEFT JOIN tank.access_sites p ON p.tenant_id=$4 AND p.site=c.site
        WHERE c.tenant_id=$1 AND c.room=$2 AND c.site=$3""", tenant, room, site, PLATFORM)
    if row is None:
        return None, "public"
    if row["revoked"] or row["clear_pending"] or not row["sealed"]:
        return row, "revoked"
    if is_social(site):
        return row, "terms_no"
    if row["terms"] != "yes":
        return row, "terms_" + row["terms"]
    if row["updated_at"] + timedelta(days=row["rotation_days"]) <= datetime.now(timezone.utc):
        return row, "rotation_due"
    return row, "allowed"


@router.post("/browser/{room}")
async def browser_rpc(room: str, request: Request):
    body = await parse(request, Sealed)
    data = vault.open_envelope(room, "request", body.model_dump())
    try:
        tenant = uuid.UUID(data["tenant_id"])
        nonce = uuid.UUID(data["nonce"])
        site = origin(data["site"], https=False)
        action = data["action"]
    except (ValueError, KeyError):
        raise HTTPException(422, "Invalid browser request.") from None
    async with db().acquire() as conn:
        inserted = await conn.fetchval("""INSERT INTO tank.access_nonces(tenant_id,nonce) VALUES($1,$2)
            ON CONFLICT DO NOTHING RETURNING nonce""", tenant, nonce)
        if inserted is None:
            raise HTTPException(409, "Browser request already used.")
        await conn.execute("DELETE FROM tank.access_nonces WHERE tenant_id=$1 AND created_at < now()-interval '5 minutes'", tenant)
        row, state = await browser_policy(conn, tenant, room, site)
        result = {"state": state, "version": str(row["version"]) if row else None}
        if state == "allowed":
            vault.key()  # A missing/invalid encryption setting must fail closed even for existing cookies.
            result["config"] = json.loads(row["login_config"]) if isinstance(row["login_config"], str) else row["login_config"]
        if action == "release":
            if state != "allowed":
                await receipt(conn, tenant, room, site, "browser", "login_refused")
            else:
                result["credential"] = vault.open_seal(row["sealed"], vault.context(tenant, room, site, "login"))
                result["config"] = json.loads(row["login_config"]) if isinstance(row["login_config"], str) else row["login_config"]
                await receipt(conn, tenant, room, site, "browser", "login_started")
        elif action == "queue":
            reason = data.get("reason")
            if reason not in {"captcha", "human_login", "terms_no", "terms_unknown", "rotation_due"}:
                raise HTTPException(422, "Invalid check reason.")
            handle = uuid.UUID(data["handle"]) if data.get("handle") else None
            task = uuid.UUID(data["task_id"]) if data.get("task_id") else None
            result["queue_id"] = await enqueue(conn, tenant, room, site, reason, handle, task)
        elif action == "event":
            event = data.get("event")
            if event not in {"logged_in", "login_failed", "logout", "live_expired"}:
                raise HTTPException(422, "Invalid browser event.")
            await receipt(conn, tenant, room, site, "browser", event)
            if event == "live_expired":
                await conn.execute("UPDATE tank.access_queue SET browser_handle=NULL,handler=NULL,status='waiting' WHERE tenant_id=$1 AND room=$2 AND site=$3 AND status IN ('waiting','handling')", tenant, room, site)
        elif action != "policy":
            raise HTTPException(422, "Unknown browser operation.")
    return vault.envelope(room, "response", {**result, "request_nonce": str(nonce)})


@router.get("/queue")
async def queue(actor: Actor = Depends(identity)):
    async with db().acquire() as conn:
        rows = await conn.fetch("""SELECT id,tenant_id,room,site,reason,status,created_at,
            (browser_handle IS NOT NULL) AS live_available FROM tank.access_queue
            WHERE (tenant_id=$1 OR $2::bool) AND status IN ('waiting','handling') ORDER BY created_at LIMIT 100""",
            actor.tenant_id, actor.founder)
    return [dict(r) for r in rows]


class HumanAction(Body):
    tenant_id: uuid.UUID
    action: Literal["open", "frame", "click", "key", "text", "scroll", "hand_back"]
    x: int = Field(default=0, ge=0, le=1280)
    y: int = Field(default=0, ge=0, le=900)
    text: SecretStr = Field(default=SecretStr(""), max_length=2000)
    key: Literal["", "Enter", "Tab", "Backspace", "Escape", "ArrowDown", "ArrowUp"] = ""
    delta: int = Field(default=0, ge=-900, le=900)


@router.post("/queue/{item_id}")
async def human_action(item_id: uuid.UUID, request: Request, actor: Actor = Depends(identity)):
    if not actor.founder:
        raise HTTPException(403, "A person on our team must handle this check.")
    body = await parse(request, HumanAction)
    async with db().acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow("SELECT * FROM tank.access_queue WHERE id=$1 AND tenant_id=$2 AND status IN ('waiting','handling') FOR UPDATE", item_id, body.tenant_id)
            if not row or not row["browser_handle"]:
                raise HTTPException(409, "Retry the page after the connection or site terms are updated.")
            if row["handler"] and row["handler"] != actor.user_id:
                raise HTTPException(409, "Another person is handling this check.")
            if row["status"] == "waiting" and body.action != "open":
                raise HTTPException(409, "Open the live view first.")
            await conn.execute("UPDATE tank.access_queue SET handler=$2,status='handling',started_at=COALESCE(started_at,now()) WHERE id=$1 AND tenant_id=$3", item_id, actor.user_id, row["tenant_id"])
    result = await control(row["room"], {"action": "live", "tenant_id": str(row["tenant_id"]), "site": row["site"],
        "handle": str(row["browser_handle"]), "input": {**body.model_dump(exclude={"text", "tenant_id"}), "text": body.text.get_secret_value()}})
    if body.action == "hand_back":
        if not result.get("ready"):
            raise HTTPException(409, "The page still needs a person.")
        async with db().acquire() as conn:
            duration = await conn.fetchval("""UPDATE tank.access_queue SET status='done',finished_at=now()
                WHERE id=$1 AND tenant_id=$2 RETURNING (extract(epoch FROM now()-started_at)*1000)::bigint""", item_id, row["tenant_id"])
            await receipt(conn, row["tenant_id"], row["room"], row["site"], actor.user_id, "handled", duration_ms=duration)
    # Screenshot only: no DOM, remote URL, cookies or browser debug endpoint.
    return Response(json.dumps({k: result[k] for k in ("png", "ready") if k in result}), media_type="application/json",
                    headers={"Cache-Control": "no-store", "Pragma": "no-cache"})


async def room_identity(request: Request) -> str:
    for room in ROOMS:
        if key_matches(request.headers.get("x-tank-key", ""), os.environ.get("TANK_KEY_" + room.upper(), "")):
            return room
    raise HTTPException(401, "Room authentication required.")


# Official distributor adapters accept the dealer's official export, including
# configurable column mappings; no guessed remote endpoints or dealer accounts.
FEED_COLUMNS = {
    "zanders": {"sku": ("itemnumber", "itemno", "sku"), "price": ("price", "dealerprice"), "quantity": ("quantity", "qty"), "upc": ("upc",)},
    "sports_south": {"sku": ("itemno", "itemnumber", "sku"), "price": ("prc", "price"), "quantity": ("qty", "quantity"), "upc": ("upc",)},
    "rsr": {"sku": ("rsrstocknumber", "rsrstocknbr", "sku"), "price": ("rsrregularprice", "price"), "quantity": ("inventoryquantity", "quantity"), "upc": ("upccode", "upc")},
    "jerrys": {"sku": ("itemnumber", "itemno", "sku"), "price": ("dealerprice", "price"), "quantity": ("qtyavailable", "quantity", "qty"), "upc": ("upc",)},
}


class FeedImport(Body):
    distributor: Literal["zanders", "sports_south", "rsr", "jerrys"]
    site: str = Field(max_length=240)
    source: Literal["dealer_api", "ftp_export", "edi_export"]
    format: Literal["csv", "tsv", "json", "edi846"]
    contents: SecretStr = Field(max_length=8_000_000)
    columns: dict[str, str] = Field(default_factory=dict, max_length=5)


def parse_feed(body: FeedImport) -> list[dict]:
    raw = body.contents.get_secret_value()
    if body.format == "json":
        rows = json.loads(raw)
        if not isinstance(rows, list):
            raise ValueError()
    elif body.format == "edi846":
        rows = []
        current = None
        for segment in raw.replace("\r", "").replace("\n", "").split("~"):
            parts = segment.split("*")
            if parts[0] == "LIN":
                current = {}
                for i in range(2, len(parts)-1, 2):
                    if parts[i] in {"VP", "SK"}: current["sku"] = parts[i+1]
                    if parts[i] in {"UP", "UK"}: current["upc"] = parts[i+1]
                rows.append(current)
            elif current is not None and parts[0] == "QTY" and len(parts) > 2 and parts[1] == "33":
                current["quantity"] = parts[2]
            elif current is not None and parts[0] == "CTP" and len(parts) > 3:
                current["price"] = parts[3]
    else:
        rows = list(csv.DictReader(io.StringIO(raw), delimiter="\t" if body.format == "tsv" else ","))
    if len(rows) > 50000 or not rows:
        raise ValueError()
    result = []
    normalize = lambda value: re.sub(r"[^a-z0-9]", "", str(value).lower())
    for row in rows:
        if not isinstance(row, dict): raise ValueError()
        values = {normalize(k): v for k, v in row.items()}
        def field(name):
            keys = (normalize(body.columns[name]),) if name in body.columns else FEED_COLUMNS[body.distributor][name] + (name,)
            return next((str(values[k]).strip() for k in keys if k in values and values[k] is not None), "")
        sku, upc = field("sku"), field("upc")
        price = Decimal(field("price")) if field("price") else None
        quantity = Decimal(field("quantity")) if field("quantity") else None
        if not sku or len(sku) > 120 or len(upc) > 32 or any(v is not None and (not v.is_finite() or v < 0) for v in (price, quantity)):
            raise ValueError()
        result.append({"sku": sku, "upc": upc, "price": str(price) if price is not None else None,
                       "quantity": str(quantity) if quantity is not None else None, "currency": "USD"})
    if len({r["sku"] for r in result}) != len(result): raise ValueError()
    return result


@router.post("/feeds/import")
async def import_feed(request: Request, actor: Actor = Depends(identity)):
    permit_room(actor, "tiger")
    body = await parse(request, FeedImport, 8_020_000)
    site_name(body.site)
    try:
        rows = parse_feed(body)
    except (ValueError, TypeError, KeyError, InvalidOperation):
        raise HTTPException(422, "The feed could not be read. Check its format and column mapping.") from None
    return await save_feed(actor, body, rows)


@router.get("/feeds/price")
async def feed_price(tenant_id: uuid.UUID, site: str, sku: str = "", upc: str = "", url: str = "", room: str = Depends(room_identity)):
    if room != "tiger" or (not sku and not upc and not url):
        raise HTTPException(422, "Tiger must name the product identifier.")
    async with db().acquire() as conn:
        if url:
            if origin(url) != site_name(site): raise HTTPException(422, "Product site differs.")
            sku = await conn.fetchval("SELECT sku FROM tank.access_feed_links WHERE tenant_id=$1 AND url=$2", tenant_id, url) or ""
        row = await conn.fetchrow("""SELECT r.data,b.source,b.fetched_at,b.row_count,b.distributor,b.id FROM tank.access_feed_rows r
            JOIN tank.access_feed_batches b ON b.tenant_id=r.tenant_id AND b.id=r.batch_id
            WHERE r.tenant_id=$1 AND r.site=$2 AND (($3<>'' AND r.sku=$3) OR ($4<>'' AND r.upc=$4))
            ORDER BY b.fetched_at DESC LIMIT 1""", tenant_id, site_name(site), sku, upc)
    if not row: return {"found": False}
    data = json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
    return {"found": True, "item": data, "receipt": {k: row[k] for k in ("source", "fetched_at", "row_count", "distributor", "id")}}


async def public_get(url: str, *, headers=None, limit=2_000_000) -> tuple[bytes, dict]:
    """Resolve, validate all answers, pin the connection, retain TLS hostname.

    No environment proxy, credentials in URLs, automatic redirects or localhost
    fallback. The caller owns any authentication headers and the destination.
    """
    origin(url)
    p = urlsplit(url)
    answers = await asyncio.get_running_loop().getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    addresses = list(dict.fromkeys(answer[4][0] for answer in answers))
    if not addresses or any(not ipaddress.ip_address(a).is_global or ipaddress.ip_address(a).is_multicast for a in addresses):
        raise ValueError("Private address refused")
    target = httpx.URL(url).copy_with(host=addresses[0])
    async with httpx.AsyncClient(timeout=25, trust_env=False, follow_redirects=False) as client:
        async with client.stream("GET", target, headers={**(headers or {}), "Host": p.hostname},
                                 extensions={"sni_hostname": p.hostname}) as response:
            if response.status_code != 200 and response.status_code != 206: raise ValueError("Source unavailable")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > limit: raise ValueError("Source too large")
            return bytes(data), dict(response.headers)


class FeedConnection(Body):
    distributor: Literal["zanders", "sports_south", "rsr", "jerrys"]
    site: str = Field(max_length=240)
    endpoint: str = Field(max_length=1000)
    token: SecretStr = Field(default=SecretStr(""), max_length=2048)
    format: Literal["csv", "tsv", "json", "edi846"]
    columns: dict[str, str] = Field(default_factory=dict, max_length=5)
    official_read_only: Literal[True]


@router.post("/feeds/connect")
async def connect_feed(request: Request, actor: Actor = Depends(identity)):
    permit_room(actor, "tiger")
    body = await parse(request, FeedConnection)
    site = site_name(body.site)
    if origin(body.endpoint) != site or urlsplit(body.endpoint).query or urlsplit(body.endpoint).fragment:
        raise HTTPException(422, "Use a same-site read-only HTTPS feed endpoint, without a query or credentials.")
    config = {**body.model_dump(exclude={"token"}), "token": body.token.get_secret_value()}
    encrypted = vault.seal(config, vault.context(actor.tenant_id, "tiger", site, "feed:" + body.distributor))
    async with db().acquire() as conn:
        await conn.execute("""INSERT INTO tank.access_feed_connections(tenant_id,distributor,site,sealed)
            VALUES($1,$2,$3,$4) ON CONFLICT(tenant_id,distributor,site) DO UPDATE SET sealed=$4""",
            actor.tenant_id, body.distributor, site, encrypted)
    return {"ok": True}


class FeedRefresh(Body):
    distributor: Literal["zanders", "sports_south", "rsr", "jerrys"]
    site: str = Field(max_length=240)


@router.post("/feeds/refresh")
async def refresh_feed(request: Request, actor: Actor = Depends(identity)):
    permit_room(actor, "tiger")
    body = await parse(request, FeedRefresh)
    site = site_name(body.site)
    async with db().acquire() as conn:
        row = await conn.fetchrow("SELECT sealed FROM tank.access_feed_connections WHERE tenant_id=$1 AND distributor=$2 AND site=$3", actor.tenant_id, body.distributor, site)
    if not row: raise HTTPException(409, "Connect the official feed first.")
    config = vault.open_seal(row["sealed"], vault.context(actor.tenant_id, "tiger", site, "feed:" + body.distributor))
    try:
        headers = {"Authorization": "Bearer " + config["token"]} if config["token"] else {}
        raw, _ = await public_get(config["endpoint"], headers=headers, limit=8_000_000)
        parsed = FeedImport(distributor=body.distributor, site=site, source="dealer_api", format=config["format"],
                            contents=SecretStr(raw.decode()), columns=config["columns"])
        rows = parse_feed(parsed)
    except Exception:
        raise HTTPException(503, "The official feed could not be refreshed. Existing data was kept.") from None
    return await save_feed(actor, parsed, rows)


async def save_feed(actor, body, rows):
    site, batch = site_name(body.site), uuid.uuid4()
    async with db().acquire() as conn:
        async with conn.transaction():
            await conn.execute("""INSERT INTO tank.access_feed_batches(tenant_id,id,distributor,site,source,row_count)
                VALUES($1,$2,$3,$4,$5,$6)""", actor.tenant_id, batch, body.distributor, site, body.source, len(rows))
            await conn.execute("DELETE FROM tank.access_feed_rows WHERE tenant_id=$1 AND distributor=$2 AND site=$3", actor.tenant_id, body.distributor, site)
            await conn.executemany("""INSERT INTO tank.access_feed_rows(tenant_id,distributor,site,sku,upc,data,batch_id)
                VALUES($1,$2,$3,$4,$5,$6::jsonb,$7)""", [(actor.tenant_id, body.distributor, site, r["sku"], r["upc"], json.dumps(r), batch) for r in rows])
            await receipt(conn, actor.tenant_id, "tiger", site, actor.user_id, "feed_fetched", row_count=len(rows))
    return {"batch_id": str(batch), "row_count": len(rows)}


class FeedLink(Body):
    url: str = Field(max_length=2048)
    sku: str = Field(min_length=1, max_length=120)


@router.post("/feeds/link")
async def link_feed(request: Request, actor: Actor = Depends(identity)):
    permit_room(actor, "tiger")
    body = await parse(request, FeedLink)
    origin(body.url)
    if urlsplit(body.url).query or urlsplit(body.url).fragment:
        raise HTTPException(422, "Use the product page address without a query or fragment.")
    async with db().acquire() as conn:
        await conn.execute("""INSERT INTO tank.access_feed_links(tenant_id,url,sku) VALUES($1,$2,$3)
            ON CONFLICT(tenant_id,url) DO UPDATE SET sku=$3""", actor.tenant_id, body.url, body.sku)
    return {"ok": True}


class PublicSource(Body):
    tenant_id: uuid.UUID
    url: str = Field(max_length=2048)


@router.post("/archives")
async def archived_page(request: Request, room: str = Depends(room_identity)):
    body = await parse(request, PublicSource)
    site = origin(body.url, https=False)
    # Never send logged-in URLs or private portal data to an archive service.
    async with db().acquire() as conn:
        connected = await conn.fetchval("SELECT 1 FROM tank.access_connections WHERE tenant_id=$1 AND room=$2 AND site=$3", body.tenant_id, room, site)
    if connected or urlsplit(body.url).query or urlsplit(body.url).fragment or is_social(site):
        return {"found": False, "next": "existing_paid_rung"}
    from urllib.parse import urlencode
    failures = []
    try:
        raw, _ = await public_get("https://archive.org/wayback/available?" + urlencode({"url": body.url}))
        snapshot = json.loads(raw).get("archived_snapshots", {}).get("closest", {})
        stamp = snapshot.get("timestamp", "")
        if snapshot.get("available") and re.fullmatch(r"\d{14}", stamp):
            # Construct the URL ourselves; never trust a server-provided host.
            url = "https://web.archive.org/web/" + stamp + "id_/" + body.url
            html, _ = await public_get(url)
            async with db().acquire() as conn:
                await receipt(conn, body.tenant_id, room, site, "room", "wayback_archived")
            return {"found": True, "archived": True, "label": "archived, dated", "date": stamp,
                    "source": "Wayback Machine", "html": html.decode(errors="replace")[:600000]}
    except Exception:
        failures.append("Wayback Machine")
    try:
        # Discover the current index, instead of freezing a crawl release.
        raw, _ = await public_get("https://index.commoncrawl.org/collinfo.json")
        indexes = json.loads(raw)
        index = indexes[0]["id"]
        if not re.fullmatch(r"CC-MAIN-\d{4}-\d{2}", index): raise ValueError()
        raw, _ = await public_get("https://index.commoncrawl.org/" + index + "-index?" + urlencode({"url": body.url, "output": "json", "filter": "status:200", "collapse": "urlkey"}))
        rows = [json.loads(line) for line in raw.decode().splitlines() if line.strip()]
        entry = max(rows, key=lambda r: r.get("timestamp", ""))
        filename = entry["filename"]
        if not re.fullmatch(r"crawl-data/CC-MAIN-[A-Za-z0-9/._-]+\.warc\.gz", filename) or ".." in filename: raise ValueError()
        start, size = int(entry["offset"]), int(entry["length"])
        if start < 0 or not 0 < size <= 2_000_000: raise ValueError()
        compressed, _ = await public_get("https://data.commoncrawl.org/" + filename, headers={"Range": f"bytes={start}-{start+size-1}"})
        import gzip
        with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as stream:
            data = stream.read(2_000_001)
        if len(data) > 2_000_000: raise ValueError()
        warc, http = data.split(b"\r\n\r\n", 1)
        if (b"WARC-Target-URI: " + body.url.encode()) not in warc: raise ValueError()
        _, html = http.split(b"\r\n\r\n", 1)
        async with db().acquire() as conn:
            await receipt(conn, body.tenant_id, room, site, "room", "common_crawl_archived")
        return {"found": True, "archived": True, "label": "archived, dated", "date": entry["timestamp"],
                "source": "Common Crawl", "html": html.decode(errors="replace")[:600000]}
    except Exception:
        failures.append("Common Crawl")
    return {"found": False, "unavailable": failures, "next": "existing_paid_rung"}


class SocialPage(Body):
    tenant_id: uuid.UUID
    platform: Literal["facebook", "instagram"]
    business_id: str = Field(pattern=r"^[A-Za-z0-9._-]{1,100}$")
    business_username: str = Field(default="", pattern=r"^[A-Za-z0-9._]{0,60}$")


@router.post("/social")
async def social_page(request: Request, room: str = Depends(room_identity)):
    body = await parse(request, SocialPage)
    if room != "base": raise HTTPException(403, "Only Base reads business pages.")
    if not os.environ.get("META_APP_ID") or os.environ.get("META_APP_REVIEW_APPROVED") != "true":
        return {"enabled": False, "source": "search_results"}
    version = os.environ.get("META_GRAPH_VERSION", "")
    token = os.environ.get("META_ACCESS_TOKEN", "")
    if not token or not re.fullmatch(r"v\d+\.\d+", version):
        raise HTTPException(503, "The approved business-page API is not configured.")
    from urllib.parse import urlencode
    business_id = body.business_id
    fields = "id,name,category,website,link"
    if body.platform == "instagram":
        business_id = os.environ.get("META_IG_BUSINESS_ID", "")
        if not business_id.isdigit(): raise HTTPException(503, "The approved Instagram business account is not configured.")
        if not body.business_username: raise HTTPException(422, "A business username is required.")
        fields = "business_discovery.username(" + body.business_username + "){username,name,website,biography}"
    try:
        raw, _ = await public_get("https://graph.facebook.com/" + version + "/" + business_id + "?" + urlencode({"fields": fields}),
                                  headers={"Authorization": "Bearer " + token}, limit=100000)
        data = json.loads(raw)
        if body.platform == "facebook":
            if not data.get("category"): raise ValueError()
            result = {k: data.get(k) for k in ("id", "name", "category", "website", "link")}
        else:
            data = data["business_discovery"]
            result = {k: data.get(k) for k in ("username", "name", "website", "biography")}
    except Exception:
        raise HTTPException(503, "The public business page could not be read; use search evidence.") from None
    async with db().acquire() as conn:
        await receipt(conn, body.tenant_id, room, "https://graph.facebook.com", "room", "public_business_api")
    return {"enabled": True, "source": "Meta official API", "page": result}
