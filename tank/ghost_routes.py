"""Ghost's narrow corridor. No policy, key, merge, database or arbitrary URL API.

The recovery backend is deliberately unconfigured until the operator supplies an
existing control-plane integration. It must verify current state and implement
only the two operations below. Missing integration fails closed with a receipt.
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import time
import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

import admin

router = APIRouter(prefix="/v1/ghost")
ROOMS = {name: f"http://agent-{name.replace('_', '-')}:8000" for name in
         ("base", "tiger", "market_lab", "rig", "tisan", "radix", "zenas", "ghost")}
TARGETS = frozenset((*ROOMS, "workspace", "site", "tank"))
ROOM_METHODS = {("POST", "/v1/ghost/check"), ("POST", "/v1/ghost/actions"),
                ("POST", "/v1/ghost/radix"), ("GET", "/v1/ghost/radix")}


def runtime():
    import main
    return main


async def require_ghost(request: Request, x_tank_key: str = Header(default="")):
    if await runtime().require_key(request, x_tank_key) != "ghost":
        raise HTTPException(403, "Only Ghost may use this corridor.")


async def call_room(method: str, room: str, path: str, *, body=None, params=None):
    key = os.environ.get(f"TANK_KEY_{room.upper()}", "")
    http = runtime()._http
    if not key or http is None:
        raise HTTPException(503, "The room is unavailable.")
    try:
        response = await http.request(method, ROOMS[room] + path, json=body, params=params,
                                      headers={"X-Tank-Key": key}, follow_redirects=False, timeout=60)
    except httpx.HTTPError:
        raise HTTPException(503, "The room is unavailable.") from None
    if len(response.content) > 2_000_000 or response.status_code >= 500:
        raise HTTPException(503, "The room is unavailable.")
    return response


@router.api_route("/{action}", methods=["GET", "POST"], dependencies=[Depends(admin.require_admin)])
async def panel(action: str, request: Request):
    paths = {("GET", "incidents"): "/incidents", ("POST", "look"): "/look",
             ("POST", "message"): "/message", ("POST", "alert"): "/alert"}
    path = paths.get((request.method, action))
    if path is None:
        raise HTTPException(404, "Not found.")
    raw = await request.body()
    if len(raw) > 4096:
        raise HTTPException(413, "Request too large.")
    try:
        body = json.loads(raw) if raw else None
    except ValueError:
        raise HTTPException(422, "Invalid Ghost request.") from None
    response = await call_room(request.method, "ghost", path, body=body)
    return Response(response.content, status_code=response.status_code, media_type="application/json")


@router.post("/incidents/{incident}/resolve", dependencies=[Depends(admin.require_admin)])
async def resolve(incident: uuid.UUID, request: Request):
    raw = await request.body()
    if len(raw) > 1024:
        raise HTTPException(413, "Request too large.")
    try:
        body = json.loads(raw)
    except ValueError:
        raise HTTPException(422, "Invalid resolution.") from None
    response = await call_room("POST", "ghost", f"/incidents/{incident}/resolve", body=body)
    return Response(response.content, status_code=response.status_code, media_type="application/json")


# ---------- GHOST-2 Shields Up: founder-only reads and the Shield / Undo taps ----------

@router.get("/shields/list", dependencies=[Depends(admin.require_admin)])
async def shields_list():
    response = await call_room("GET", "ghost", "/ghost/shields")
    return Response(response.content, status_code=response.status_code, media_type="application/json")


@router.get("/shields/tile", dependencies=[Depends(admin.require_admin)])
async def shields_tile():
    """The founder tile: Ghost's own numbers plus Ghost's cost this month from Tank's receipts."""
    response = await call_room("GET", "ghost", "/ghost/summary")
    if response.status_code != 200:
        raise HTTPException(503, "The room is unavailable.")
    core = runtime()
    async with core.pool().acquire() as conn:
        row = await conn.fetchrow(
            "SELECT coalesce(sum(cost_usd), 0) AS cost, count(*) AS receipts FROM tank.ledger"
            " WHERE tenant_id=$1 AND agent='ghost' AND ts >= date_trunc('month', now())",
            core.PLATFORM_TENANT)
    return {**response.json(), "cost_this_month_usd": float(row["cost"] if row else 0),
            "receipts_this_month": int(row["receipts"] if row else 0)}


@router.post("/shields/{shield}/{tap}", dependencies=[Depends(admin.require_admin)])
async def shields_tap(shield: uuid.UUID, tap: Literal["raise", "undo"]):
    response = await call_room("POST", "ghost", f"/ghost/shields/{shield}/{tap}")
    return Response(response.content, status_code=response.status_code, media_type="application/json")


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target: str
    signal: Literal["health", "slow", "errors", "deploy", "ci", "radix"]


@router.post("/check", dependencies=[Depends(require_ghost)])
async def check(request: Request):
    body = await parse(request, Check)
    if body.target not in TARGETS:
        raise HTTPException(422, "Unknown check target.")
    if body.signal not in {"health", "slow"}:
        # No raw-log API, GitHub administration credential, or cross-region proxy.
        raise HTTPException(503, "The read-only evidence feed is not connected.")
    if body.target not in ROOMS and body.target != "tank":
        raise HTTPException(422, "Public sites use Ghost's own browser.")
    start = time.monotonic()
    if body.target == "tank":
        async with runtime().pool().acquire() as conn:
            await conn.fetchval("SELECT 1")
        status = 200
    else:
        try:
            response = await call_room("GET", body.target, "/health")
            status = response.status_code
        except HTTPException:
            status = 503
    latency = min(120000, int((time.monotonic() - start) * 1000))
    return {"target": body.target, "signal": body.signal, "failing": status >= 400 or (body.signal == "slow" and latency > 3000),
            "count": 1, "latency_ms": latency, "status_code": status}


async def parse(request: Request, model, max_bytes: int = 4096):
    raw = await request.body()
    if len(raw) > max_bytes:
        raise HTTPException(413, "Request too large.")
    try:
        return model.model_validate_json(raw)
    except ValidationError:
        raise HTTPException(422, "Invalid Ghost request.") from None


class Recovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: uuid.UUID
    action: Literal["rerun_failed_deploy", "restart_crashed_room"]
    target: str


async def action_receipt(identity: uuid.UUID, step: str, outcome: str):
    core = runtime()
    receipt = core.VendorCall(id=uuid.uuid5(identity, step), agent="ghost", task_type="ghost.recovery",
                              vendor=f"ghost.{step}", units=1, cost_usd=0,
                              outcome=outcome, region=core.box_region())
    return await core.vendor_ledger(receipt, agent="ghost")


@router.post("/actions", dependencies=[Depends(require_ghost)])
async def recover(request: Request):
    """One guarded action route. Pending/uncertain requests are never retried."""
    # Record every authenticated call, including malformed/refused requests.
    attempt = uuid.uuid4()
    receipt = await action_receipt(attempt, "requested", "unverified")
    try:
        body = await parse(request, Recovery)
    except HTTPException:
        await action_receipt(attempt, "refused", "failed")
        raise
    allowed = set(ROOMS) if body.action == "restart_crashed_room" else TARGETS
    if body.target not in allowed:
        await action_receipt(attempt, "refused", "failed")
        raise HTTPException(403, {"message": "Action target is not allowed.", **receipt})
    core = runtime()
    async with core.pool().acquire() as conn:
        row = await conn.fetchrow("""INSERT INTO tank.ghost_recovery
            (tenant_id,id,action,target,status) VALUES ($1,$2,$3,$4,'pending')
            ON CONFLICT (tenant_id,id) DO NOTHING RETURNING status""",
                                 core.PLATFORM_TENANT, body.id, body.action, body.target)
        if row is None:
            prior = await conn.fetchrow("SELECT action,target,status FROM tank.ghost_recovery WHERE tenant_id=$1 AND id=$2",
                                        core.PLATFORM_TENANT, body.id)
            if prior is None or prior["action"] != body.action or prior["target"] != body.target:
                raise HTTPException(409, {"message": "Request identifier already used.", **receipt})
            return {"status": prior["status"], "repeated": True, **receipt}
    backend = getattr(core.app.state, "ghost_recovery_backend", None)
    status = "unavailable"
    try:
        if backend is None:
            raise HTTPException(503, {"message": "Recovery integration is not connected. No action was taken.", **receipt})
        observed = await backend.observe(body.target)
        required = "crashed" if body.action == "restart_crashed_room" else "failed"
        if observed.get("state") != required or not observed.get("revision"):
            status = "refused"
            raise HTTPException(409, {"message": "Current state does not permit this action.", **receipt})
        await action_receipt(body.id, "authorized", "unverified")
        status = "uncertain"
        # The backend must compare this revision again atomically and rerun the
        # exact failed revision, never deploy current main or change settings.
        result = await backend.execute(body.action, body.target, observed["revision"], str(body.id))
        if result != "queued":
            raise HTTPException(502, {"message": "Action outcome is uncertain; do not retry.", **receipt})
        status = "queued"
        await action_receipt(body.id, "queued", "delivered")
        return {"status": status, **receipt}
    except (HTTPException, asyncio.CancelledError):
        raise
    except Exception:
        raise HTTPException(502, {"message": "Action outcome is uncertain; do not retry.", **receipt}) from None
    finally:
        async with core.pool().acquire() as conn:
            await conn.execute("UPDATE tank.ghost_recovery SET status=$3 WHERE tenant_id=$1 AND id=$2",
                               core.PLATFORM_TENANT, body.id, status)
        if status in {"refused", "unavailable"}:
            await action_receipt(body.id, status, "failed")


class Scan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    archive: str = Field(min_length=1, max_length=2_000_000)


@router.post("/radix", dependencies=[Depends(require_ghost)])
async def scan(request: Request):
    body = await parse(request, Scan, max_bytes=2_010_000)
    try:
        raw = base64.b64decode(body.archive, validate=True)
    except ValueError:
        raise HTTPException(422, "Hand over a base64 archive.") from None
    if not (raw.startswith((b"PK\x03\x04", b"\x1f\x8b")) or raw[257:262] == b"ustar"):
        raise HTTPException(422, "Hand over a tar or zip archive.")
    response = await call_room("POST", "radix", "/jobs", body={
        "tenant_id": str(runtime().PLATFORM_TENANT), "kind": "scan",
        "input": {"source": "b64:" + body.archive, "ref": "Ghost incident code"},
    })
    if response.status_code != 201:
        raise HTTPException(503, "Radix did not accept the scan.")
    data = response.json()
    return {"id": str(uuid.UUID(data["id"])), "status": "queued"}


@router.get("/radix", dependencies=[Depends(require_ghost)])
async def scan_result(id: uuid.UUID):
    response = await call_room("GET", "radix", f"/jobs/{id}", params={"tenant_id": str(runtime().PLATFORM_TENANT)})
    if response.status_code != 200:
        raise HTTPException(503, "Radix results are unavailable.")
    data = response.json()
    result = data.get("result") or {}
    # Never forward findings' snippets, paths, or exception text to Ghost.
    return {"id": str(id), "status": data.get("status") if data.get("status") in {"queued", "running", "done", "failed"} else "unknown",
            "findings": len(result.get("findings", [])), "critical": int(result.get("critical", 0))}


# Explicit routes must precede the founder panel's single-segment catch-all.
router.routes.sort(key=lambda route: "{action}" in route.path)
