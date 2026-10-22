"""RIG-5F connection and receipt relay only; the forge never receives our Tank key."""
import asyncio
import os
import socket
import uuid
from typing import Literal

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .room import authorize

router = APIRouter(prefix="/forge")


async def forge_addresses():
    addresses = await asyncio.get_running_loop().getaddrinfo("rig-forge", 8010, type=socket.SOCK_STREAM)
    return {row[4][0] for row in addresses}


async def forward(method, base, path, *, key=None, **kwargs):
    try:
        async with httpx.AsyncClient(trust_env=False, timeout=40) as client:
            response = await client.request(method, base + path,
                headers={"X-Tank-Key": key} if key else {}, **kwargs)
        if response.status_code not in {200, 202, 400, 401, 403, 404, 409, 422, 429, 503}:
            raise ValueError("upstream unavailable")
        return JSONResponse(response.json(), status_code=response.status_code)
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "Forge or Tank is unavailable; no success is claimed.") from None


@router.post("/jobs")
async def create(body: dict, x_tank_key: str = Header(default="")):
    authorize(x_tank_key, body.get("home_region", ""))
    return await forward("POST", "http://rig-forge:8010", "/jobs", json=body)


@router.get("/jobs/{job_id}")
async def poll(job_id: uuid.UUID, tenant_id: uuid.UUID, home_region: str,
               x_tank_key: str = Header(default="")):
    authorize(x_tank_key, home_region)
    return await forward("GET", "http://rig-forge:8010", "/jobs/" + str(job_id),
                         params={"tenant_id": str(tenant_id)})


@router.post("/relay/{action}")
async def relay(action: Literal["reserve", "claim", "complete", "steps"], body: dict, request: Request):
    try:
        allowed = await forge_addresses()
    except OSError:
        allowed = set()
    if not request.client or request.client.host not in allowed:
        raise HTTPException(401, "Only Rig's forge may relay receipts.")
    key = os.environ.get("TANK_KEY", "")
    authorize(key, body.get("home_region", ""))
    return await forward("POST", os.environ.get("TANK_URL", "http://tank:8000").rstrip("/"),
                         "/v1/agents/rig/forge/" + action, key=key, json=body)
