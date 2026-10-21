"""Founder control state. Only implemented controls have write routes."""
from __future__ import annotations

import uuid
import logging
from datetime import datetime, timezone

import httpx
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict

from admin import require_admin

PLATFORM = uuid.UUID('00000000-0000-0000-0000-000000000001')
log = logging.getLogger('tank.controls')
PAID_TOOL_HOSTS = frozenset({'api.search.brave.com'})

router = APIRouter(prefix='/v1/controls', dependencies=[Depends(require_admin)])


def db() -> Any:
    from main import pool
    return pool()


class Pause(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paused: bool


async def paid_paused() -> bool:
    async with db().acquire() as conn:
        return bool(await conn.fetchval(
            "SELECT value FROM tank.controls WHERE tenant_id=$1 AND name='paid_paused'", PLATFORM
        ))


async def refuse_paid(*, paid: bool = True, task: str = "unknown", path: str = "route") -> None:
    """Free work never reads control state. Paid work fails closed on read failure."""
    if not paid:
        return
    reason = "paid work is paused"
    try:
        paused = await paid_paused()
    except Exception:
        paused = True
        reason = "paid work is paused: pause state unavailable"
    if not paused:
        return
    # Safe identifiers only: never log a request URL, query, prompt or credentials.
    task = task[:120]
    path = path[:120]
    at = datetime.now(timezone.utc).isoformat()
    log.warning("paid_refused task=%s path=%s at=%s", task, path, at)
    try:
        async with db().acquire() as conn:
            await conn.execute(
                """INSERT INTO tank.control_log
                (tenant_id,name,by_user,old_value,new_value,task,path)
                VALUES ($1,'paid_refused','system',true,true,$2,$3)""", PLATFORM, task, path,
            )
    except Exception:
        # Database outage must not turn a refusal into permission.
        log.error("paid_refusal_audit_unavailable task=%s path=%s at=%s", task, path, at)
    raise HTTPException(status_code=503, detail=reason)


async def paid_host_hook(request: httpx.Request) -> None:
    host = request.url.host.lower()
    if host in PAID_TOOL_HOSTS:
        await refuse_paid(path=f"HTTP host:{host}", task="unattributed skill HTTP request")


@router.get('')
async def read_controls() -> dict[str, Any]:
    async with db().acquire() as conn:
        rows = await conn.fetch(
            "SELECT task,path,at FROM tank.control_log WHERE tenant_id=$1 AND name='paid_refused' ORDER BY at DESC LIMIT 10", PLATFORM
        )
    return {'paid_paused': await paid_paused(), 'refused': [dict(row) for row in rows]}


@router.put('/paid-paused')
async def set_pause(body: Pause, x_tervory_admin: str = Header(default='')) -> dict[str, bool]:
    async with db().acquire() as conn:
        async with conn.transaction():
            # Serialize first-time creation and concurrent writes across processes.
            await conn.execute('SELECT pg_advisory_xact_lock(4810115)')
            old = bool(await conn.fetchval(
                "SELECT value FROM tank.controls WHERE tenant_id=$1 AND name='paid_paused'", PLATFORM
            ))
            await conn.execute(
                """INSERT INTO tank.controls (tenant_id,name,value,updated_by)
                VALUES ($1,'paid_paused',$2,$3) ON CONFLICT (tenant_id,name)
                DO UPDATE SET value=EXCLUDED.value,updated_by=EXCLUDED.updated_by,updated_at=now()""",
                PLATFORM, body.paused, x_tervory_admin,
            )
            await conn.execute(
                """INSERT INTO tank.control_log (tenant_id,name,by_user,old_value,new_value)
                VALUES ($1,'paid_paused',$2,$3,$4)""",
                PLATFORM, x_tervory_admin, old, body.paused,
            )
    return {'paid_paused': body.paused}
