"""ML3: authenticated code reads, confirmed alert opt-ins and signed delivery.

The room never receives a webhook secret. The one-time Confirm value is returned
in memory to command.execute_card, never persisted in its card/event/model history.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict

from tenant_db import tenant_path

PLATFORM = "00000000-0000-0000-0000-000000000001"
READS = {"warnings", "predictions", "calibration", "feeds"}


def obj(raw):
    return json.loads(raw) if isinstance(raw, str) else raw


async def room(operation: str, tenant) -> dict:
    from ghost_routes import call_room
    response = await call_room("POST", "market_lab", "/market/ml3/" + operation,
                               body={"tenant_id": str(tenant)})
    if response.status_code != 200:
        raise HTTPException(503, "Market Lab is not connected")
    return response.json()


def link(value: str) -> str:
    if value.startswith("/market-lab/sources/"):
        return "https://app.tervory.com" + value
    return ""


def records(operation: str, data: dict) -> list[dict]:
    if operation == "warnings":
        rows = []
        for warning in data.get("warnings", []):
            rows.extend({"name": warning["title"], "status": warning["status"], "text": f["text"],
                         "link": link(f["href"])} for f in warning["facts"])
        return rows
    if operation == "calibration":
        return [{"summary": json.dumps(data, default=str, ensure_ascii=False)}]
    fields = {
        "predictions": ("id", "made_at", "statement", "horizon_seconds", "confidence", "outcome", "realised_value", "realised_date", "sources"),
        "feeds": ("id", "name", "state", "rows", "checked_at", "key_name"),
    }[operation]
    return [{"name": r.get("name") or r.get("statement") or r["id"],
             "summary": json.dumps({k: r.get(k) for k in fields}, default=str, ensure_ascii=False)}
            for r in data.get(operation, [])]


@tenant_path("actor")
async def confirmed(action, actor, thread_id, card_id):
    import command
    import vault
    from main import pool
    from vault_routes import public_url
    actor = await command.authorized_actor(actor)
    command.require_tool(actor, action.tool)
    if not (actor.founder or actor.tenant_admin):
        raise HTTPException(403, "This tool is not available to this user")
    mode = action.tool.removeprefix("market_lab.alerts.")
    if mode not in {"email", "webhook", "off"}:
        raise HTTPException(404, "Not found")
    # Only the durable executing claim created by the actual Confirm endpoint
    # can change preferences. A model plan or direct function call is insufficient.
    async with pool().acquire() as conn:
        raw = await conn.fetchval("SELECT state FROM tank.command_threads WHERE thread_id=$1 AND tenant_id=$2 AND user_id=$3", thread_id, actor.tenant_id, actor.user_id)
    card = (obj(raw) or {}).get("cards", {}).get(str(card_id), {})
    if card.get("status") != "executing" or card.get("payload") != {"tool": action.tool, "arguments": action.arguments}:
        raise HTTPException(409, "Card has already been resolved")
    url = public_url(action.arguments["url"]) if mode == "webhook" else None
    # Register an existing chassis job before enabling any delivery. This is a
    # confirmed change, not a side effect of a read.
    if mode != "off":
        await room("alerts", actor.tenant_id)
    once = None
    async with pool().acquire() as conn, conn.transaction():
        await conn.execute("INSERT INTO tank.market_lab_alerts(tenant_id) VALUES($1) ON CONFLICT (tenant_id) DO NOTHING", actor.tenant_id)
        settings = await conn.fetchrow("SELECT * FROM tank.market_lab_alerts WHERE tenant_id=$1 FOR UPDATE", actor.tenant_id)
        if mode == "email":
            await conn.execute("UPDATE tank.market_lab_alerts SET email_enabled=true,email_since=CASE WHEN email_enabled THEN email_since ELSE now() END,updated_at=now() WHERE tenant_id=$1", actor.tenant_id)
        elif mode == "webhook" and (settings["webhook_url"] != url or not settings["webhook_sealed"]):
            once = secrets.token_urlsafe(32)
            sealed = vault.seal({"value": once}, f"market_lab:webhook:v1:{actor.tenant_id}")
            await conn.execute("UPDATE tank.market_lab_alerts SET webhook_url=$2,webhook_sealed=$3,webhook_since=now(),updated_at=now() WHERE tenant_id=$1", actor.tenant_id, url, sealed)
        elif mode == "off":
            await conn.execute("UPDATE tank.market_lab_alerts SET email_enabled=false,email_since=NULL,webhook_url=NULL,webhook_sealed=NULL,webhook_since=NULL,updated_at=now() WHERE tenant_id=$1", actor.tenant_id)
            await conn.execute("UPDATE tank.market_lab_deliveries SET status='suppressed',updated_at=now() WHERE tenant_id=$1 AND status='pending'", actor.tenant_id)
    result = {"status": mode}
    if once is not None:
        result["_once"] = once
    return result


async def prime(tenant: UUID):
    from main import pool
    async with pool().acquire() as conn:
        settings = await conn.fetchrow("SELECT * FROM tank.market_lab_alerts WHERE tenant_id=$1", tenant)
    if not settings or not (settings["email_enabled"] or settings["webhook_url"]):
        return
    data = await room("warnings", tenant)
    for warning in data.get("warnings", []):
        created = datetime.fromisoformat(warning["created_at"])
        text = "\n".join(part for f in warning["facts"] for part in (f["text"], link(f["href"])))
        letter = {"subject": warning["title"], "text": text}
        for channel in ("email", "webhook"):
            since = settings["email_since"] if channel == "email" else settings["webhook_since"]
            if since is None or created < since:
                continue
            async with pool().acquire() as conn:
                await conn.execute("INSERT INTO tank.market_lab_deliveries(tenant_id,warning_id,channel,status,letter) VALUES($1,$2,$3,'pending',$4::jsonb) ON CONFLICT (tenant_id,warning_id,channel) DO NOTHING", tenant, UUID(warning["id"]), channel, json.dumps(letter))


async def claim(tenant: UUID, ident: UUID, channel: str) -> dict | None:
    from main import pool
    async with pool().acquire() as conn, conn.transaction():
        settings = await conn.fetchrow("SELECT * FROM tank.market_lab_alerts WHERE tenant_id=$1 FOR UPDATE", tenant)
        allowed = settings and (settings["email_enabled"] if channel == "email" else settings["webhook_url"])
        if not allowed:
            return None
        row = await conn.fetchrow("UPDATE tank.market_lab_deliveries SET status='sending',updated_at=now() WHERE tenant_id=$1 AND warning_id=$2 AND channel=$3 AND status='pending' RETURNING letter", tenant, ident, channel)
        if row is None:
            return None
        return {"allowed": True, "letter": obj(row["letter"]), "settings": dict(settings)}


def signature(raw: bytes, value: str) -> str:
    return "sha256=" + hmac.new(value.encode(), raw, hashlib.sha256).hexdigest()


async def webhooks(tenant: UUID) -> dict:
    from main import pool
    from access import public_stream
    from vault import open_seal
    async with pool().acquire() as conn:
        ids = await conn.fetch("SELECT warning_id FROM tank.market_lab_deliveries WHERE tenant_id=$1 AND channel='webhook' AND status='pending' ORDER BY created_at,warning_id LIMIT 3", tenant)
    sent = 0
    for ident in ids:
        claimed = await claim(tenant, ident["warning_id"], "webhook")
        if claimed is None:
            continue
        state = "uncertain"
        try:
            settings = claimed["settings"]
            value = open_seal(settings["webhook_sealed"], f"market_lab:webhook:v1:{tenant}")["value"]
            raw = json.dumps({"tenant_id": str(tenant), "warning_id": str(ident["warning_id"]), **claimed["letter"]}, separators=(",", ":"), ensure_ascii=False).encode()
            async with public_stream(settings["webhook_url"], method="POST", content=raw,
                                     headers={"Content-Type": "application/json", "X-Market-Lab-Signature": signature(raw, value),
                                              "Idempotency-Key": str(ident["warning_id"])}) as response:
                if 200 <= response.status_code < 300:
                    state = "sent"
                    sent += 1
        except Exception:
            pass  # No URL, raw payload, signature or decrypted value in logs.
        async with pool().acquire() as conn:
            await conn.execute("UPDATE tank.market_lab_deliveries SET status=$3,updated_at=now() WHERE tenant_id=$1 AND warning_id=$2 AND channel='webhook' AND status='sending'", tenant, ident["warning_id"], state)
    return {"sent": sent}


class MailBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    warning_id: UUID | None = None
    status: Literal["pending", "sent", "uncertain", "suppressed"] | None = None


def build_router(tank):
    import command
    router = APIRouter()

    @router.get("/v1/market-lab/intel")
    async def intel(request: Request, x_tank_key: str = Header(default="")):
        if not command.key_matches(x_tank_key, os.environ.get("TANK_KEY_GHOST", "")):
            actor = await command.identity(request)
            if not actor.founder:
                raise HTTPException(403, "This tool is not available to this user")
        return JSONResponse(await room("intel", PLATFORM), headers={"Cache-Control": "private, no-store"})

    @router.get("/v1/market-lab/reads/{operation}")
    @tenant_path("actor")
    async def read(operation: str, actor=Depends(command.identity), limit: int = Query(default=20, ge=1, le=100), page: int = Query(default=0, ge=0, le=10000)):
        from main import pool, box_region
        if operation not in READS:
            raise HTTPException(404, "Not found")
        command.require_tool(actor, "market_lab." + operation)
        data = await room(operation, actor.tenant_id)
        rows = records(operation, data)
        ledger_id = await pool().fetchval("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out) VALUES($1,$2,'market_lab',$3,3,'code',0,0,0) RETURNING id", actor.tenant_id, box_region(), "market_lab." + operation)
        return JSONResponse(jsonable_encoder({"records": rows[page * limit:(page + 1) * limit], "total": len(rows), "ledger_id": str(ledger_id), "cost_usd": 0}), headers={"Cache-Control": "private, no-store"})

    async def room_only(request: Request, x_tank_key: str = Header(default="")):
        if not command.key_matches(x_tank_key, os.environ.get("TANK_KEY_MARKET_LAB", "")):
            raise HTTPException(401, "Room key required")

    @router.post("/v1/market-lab/internal/alerts/{operation}", dependencies=[Depends(room_only)])
    @tenant_path("body")
    async def alerts(operation: str, body: MailBody):
        from main import pool
        if operation in {"pending", "webhooks"}:
            await prime(body.tenant_id)
        if operation == "pending":
            async with pool().acquire() as conn:
                ids = await conn.fetch("SELECT warning_id FROM tank.market_lab_deliveries WHERE tenant_id=$1 AND channel='email' AND status='pending' ORDER BY created_at,warning_id LIMIT 3", body.tenant_id)
            return {"pending": [str(r["warning_id"]) for r in ids]}
        if operation == "claim" and body.warning_id:
            record = await claim(body.tenant_id, body.warning_id, "email")
            # SMTP's shared sender needs only the letter, never webhook credentials.
            return {"record": {"allowed": record["allowed"], "letter": record["letter"]} if record else None}
        if operation == "finish" and body.warning_id and body.status:
            async with pool().acquire() as conn:
                await conn.execute("UPDATE tank.market_lab_deliveries SET status=$3,updated_at=now() WHERE tenant_id=$1 AND warning_id=$2 AND channel='email' AND status='sending'", body.tenant_id, body.warning_id, body.status)
            return {"status": body.status}
        if operation == "webhooks":
            return await webhooks(body.tenant_id)
        raise HTTPException(404, "Not found")
    return router
