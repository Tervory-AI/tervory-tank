"""Tiger — watches pages and keeps a price history. It knows no industry."""

from __future__ import annotations

import hmac
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Header, HTTPException, Query
from gold_sources import candidates
from pydantic import BaseModel

from chassis.app import create_app
from chassis.jobs import JobContext
from watch import (
    SCHEMA,
    BadWatch,
    DomainLimiter,
    DuplicateWatch,
    PgStore,
    check_every,
    check_text,
    check_threshold,
    check_url,
    dispatch_tenant,
    run_check,
)

AGENT = os.environ.get("AGENT_NAME", "tiger")
TIGER_URL = os.environ.get("TIGER_URL", "http://tiger:3000")
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"
INTERVAL_S = float(os.environ.get("DOMAIN_INTERVAL_S", "10"))
ROBOTS_UA = "TervoryTiger/0.1 (+https://tervory.com)"

log = logging.getLogger("agent")
_limiter = DomainLimiter(INTERVAL_S)


async def ping(ctx: JobContext) -> dict:
    result: dict = {"pong": True, "agent": ctx.agent}
    if ctx.input.get("heartbeat"):
        try:
            saved = await ctx.memory.remember(
                ctx.tenant_id,
                f"{ctx.agent} heartbeat",
                "heartbeat",
                "schedule:*/5",
            )
            result["heartbeats_seen"] = saved.get("seen")
        except Exception as exc:  # noqa: BLE001 — class name only, never the message
            log.warning("heartbeat memory failed (%s)", type(exc).__name__)
            result["memory"] = "unreachable"
    return result


async def _render(url: str, session: str, agent: str, tenant: str) -> dict[str, Any]:
    response = await app.state.http.post(
        f"{TIGER_URL.rstrip('/')}/render",
        json={
            "url": url,
            "session": session,
            "agent": agent,
            "tenant": tenant,
            "screenshot": True,
            "settle_ms": 10_000,
            "max_ms": 25_000,
        },
        timeout=50,
    )
    if response.status_code >= 400:
        return {"ok": False, "challenge": False, "error": f"browser answered {response.status_code}"}
    data = response.json()
    if not isinstance(data, dict):
        return {"ok": False, "challenge": False, "error": "browser answer was not an object"}
    return data


async def _fetch_text(url: str) -> str:
    response = await app.state.http.get(
        url,
        timeout=8,
        headers={"User-Agent": ROBOTS_UA},
        follow_redirects=True,
    )
    if response.status_code != 200:
        return ""
    return response.text[:100_000]


async def check(ctx: JobContext) -> dict:
    url = str(ctx.input.get("url") or "").strip()
    store = PgStore(app.state.pool, SCHEMA)
    watch = await store.get_watch(ctx.tenant_id, url)
    if watch is None or not watch.get("enabled"):
        return {"status": "skipped", "url": url, "alerts": []}

    async def extract(html: str, page_url: str) -> dict[str, Any]:
        return await ctx.tank.run_skill(ctx.tenant_id, "tiger.price_extract", {"html": html, "url": page_url})

    async def ocr(png_base64: str, page_url: str) -> dict[str, Any]:
        return await ctx.tank.run_skill(ctx.tenant_id, "tiger.price_ocr", {"png_base64": png_base64, "url": page_url})

    return await run_check(
        store,
        ctx.tenant_id,
        watch,
        ctx.agent,
        _render,
        extract,
        ocr,
        _fetch_text,
        _limiter,
        files=ctx.files,
    )


async def dispatch(ctx: JobContext) -> dict:
    store = PgStore(app.state.pool, SCHEMA)
    return await dispatch_tenant(store, ctx.tenant_id, datetime.now(timezone.utc))


app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "check": check, "dispatch": dispatch},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
    ],
)


class WatchIn(BaseModel):
    tenant_id: UUID
    url: str
    label: str = ""
    engine: str = ""
    every: str
    enabled: bool = True
    threshold: float = 0


class WatchPatch(BaseModel):
    tenant_id: UUID
    url: str | None = None
    label: str | None = None
    engine: str | None = None
    every: str | None = None
    enabled: bool | None = None
    threshold: float | None = None


def _store() -> PgStore:
    return PgStore(app.state.pool, SCHEMA)


def _watch_http(exc: BadWatch) -> HTTPException:
    status = 400 if str(exc) == "url not allowed" else 422
    return HTTPException(status_code=status, detail=str(exc))


def _fields(body: WatchIn | WatchPatch, partial: bool) -> dict[str, Any]:
    try:
        fields: dict[str, Any] = {"tenant_id": str(body.tenant_id)}
        if body.url is not None:
            fields["url"] = check_url(body.url)
        elif not partial:
            raise BadWatch("url is required")
        if body.label is not None or not partial:
            fields["label"] = check_text(body.label or "", 200)
        if body.engine is not None or not partial:
            fields["engine"] = check_text(body.engine or "", 80)
        if body.every is not None:
            fields["every"] = check_every(body.every)
        elif not partial:
            raise BadWatch("every is required")
        if body.enabled is not None or not partial:
            fields["enabled"] = True if body.enabled is None else bool(body.enabled)
        if body.threshold is not None or not partial:
            fields["threshold"] = check_threshold(0 if body.threshold is None else body.threshold)
        return fields
    except BadWatch as exc:
        raise _watch_http(exc) from exc


@app.post("/watchlist", status_code=201)
async def create_watch(body: WatchIn) -> dict[str, Any]:
    fields = _fields(body, partial=False)
    try:
        return await _store().create_watch(fields)
    except DuplicateWatch as exc:
        raise HTTPException(status_code=409, detail="that url is already watched") from exc


@app.get("/watchlist")
async def list_watches(tenant_id: UUID = Query()) -> dict[str, Any]:
    rows = await _store().list_watches(str(tenant_id))
    return {"watches": rows}


@app.get("/watchlist/{watch_id}")
async def get_watch(watch_id: UUID, tenant_id: UUID = Query()) -> dict[str, Any]:
    row = await _store().get_watch_by_id(str(tenant_id), str(watch_id))
    if row is None:
        raise HTTPException(status_code=404, detail="no such watch")
    return row


@app.patch("/watchlist/{watch_id}")
async def update_watch(watch_id: UUID, body: WatchPatch) -> dict[str, Any]:
    fields = _fields(body, partial=True)
    fields.pop("tenant_id", None)
    try:
        row = await _store().update_watch(str(body.tenant_id), str(watch_id), fields)
    except DuplicateWatch as exc:
        raise HTTPException(status_code=409, detail="that url is already watched") from exc
    if row is None:
        raise HTTPException(status_code=404, detail="no such watch")
    return row


@app.delete("/watchlist/{watch_id}", status_code=204)
async def delete_watch(watch_id: UUID, tenant_id: UUID = Query()):
    if not await _store().delete_watch(str(tenant_id), str(watch_id)):
        raise HTTPException(status_code=404, detail="no such watch")


@app.get("/observations")
async def list_observations(tenant_id: UUID = Query(), url: str = Query()) -> dict[str, Any]:
    try:
        page = check_url(url)
    except BadWatch as exc:
        raise _watch_http(exc) from exc
    rows = await _store().list_observations(str(tenant_id), page)
    return {"observations": rows}


@app.get("/alerts")
async def list_alerts(tenant_id: UUID = Query(), url: str | None = Query(default=None)) -> dict[str, Any]:
    page = None
    if url is not None:
        try:
            page = check_url(url)
        except BadWatch as exc:
            raise _watch_http(exc) from exc
    rows = await _store().list_alerts(str(tenant_id), page)
    return {"alerts": rows}


@app.get("/gold/candidates")
async def gold_candidates(
    limit: int = Query(default=200, ge=1, le=200),
    x_tank_key: str = Header(default=""),
) -> list[dict]:
    key = os.environ.get("TANK_KEY", "")
    if not key or not hmac.compare_digest(key, x_tank_key):
        raise HTTPException(status_code=401, detail="room key required")
    return candidates(
        limit, region=os.environ.get("TANK_REGION", "us-east"),
        snapshots=Path(os.environ.get("DATA_DIR", "/data")) / "gold" / "public_snapshots.json",
    )
