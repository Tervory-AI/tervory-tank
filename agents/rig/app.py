"""Rig. Public catalogue API for one retailer at a time."""

from __future__ import annotations

import hmac
import importlib.util
import json
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from chassis.app import create_app
from chassis.db import ensure_schedules, schema_for
from chassis.jobs import JobContext
from chassis.logs import log_line
from fastapi import FastAPI, Header, HTTPException, Query

from rigbox.api import mount
from rigbox.page_route import mount_page
from rigbox.service import Service, WebhookHandoff
from rigbox.store import PgStore

AGENT = os.environ.get("AGENT_NAME", "rig")
HEARTBEAT_TENANT = "00000000-0000-0000-0000-000000000001"

log = logging.getLogger("agent")


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


async def pull_feeds(ctx: JobContext) -> dict:
    service: Service = app.state.rig
    http = app.state.http

    async def fetch(url: str) -> Any:
        response = await http.get(url)
        content_type = response.headers.get("content-type", "")
        if "json" in content_type or url.endswith(".json"):
            return response.json()
        return response.text

    reports = await service.pull_feeds(ctx.tenant_id, fetch)
    log_line(AGENT, json.dumps({"feeds": reports}), tenant_id=ctx.tenant_id, job_id=ctx.job_id)
    return {"pulled": len(reports), "reports": reports}


async def expire_searches(ctx: JobContext) -> dict:
    """Nightly. Deletes saved searches older than the recall window.

    Safe to run twice: the second run finds nothing left to delete.
    It writes only to agent_rig.searches.
    """
    service: Service = app.state.rig
    deleted = await service.expire_searches()
    log_line(AGENT, json.dumps({"deleted": deleted}), tenant_id=ctx.tenant_id, job_id=ctx.job_id)
    return {"deleted": deleted}


app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "pull_feeds": pull_feeds, "expire_searches": expire_searches},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        },
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "0 3 * * *",
            "kind": "expire_searches",
            "input": {},
        },
    ],
)
mount(app)

# Chassis job intake and the generated docs are not part of the shopper API.
# The worker and the scheduler still run inside this process.
_CLOSED = {
    "/jobs",
    "/jobs/{job_id}",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}


def _close_public_surface(application: FastAPI) -> None:
    application.router.routes = [
        route for route in application.router.routes if getattr(route, "path", None) not in _CLOSED
    ]
    application.openapi_url = None
    application.docs_url = None
    application.redoc_url = None


_close_public_surface(app)
mount_page(app)


@app.get("/gold/candidates")
async def gold_candidates(
    limit: int = Query(default=200, ge=1, le=200),
    x_tank_key: str = Header(default=""),
) -> list[dict[str, Any]]:
    """Room key only. Catalogue compatibility lists, marked public."""
    key = os.environ.get("TANK_KEY", "")
    # compare_digest on str rejects some headers with TypeError. Bytes compare
    # instead, so a bad or non-ASCII header is 401.
    try:
        matches = bool(key) and bool(x_tank_key) and hmac.compare_digest(key.encode(), x_tank_key.encode())
    except (AttributeError, TypeError, UnicodeError):
        matches = False
    if not matches:
        raise HTTPException(status_code=401, detail="room key required")
    root = Path(os.environ.get("CATALOGUE_DIR", str(Path(__file__).resolve().parent / "catalogues")))
    return _gold_candidates()(limit, region=os.environ.get("TANK_REGION", "us-east"), root=root)


def _gold_candidates():
    """Load this room's gold module by file, not by the shared import name.

    Other rooms also ship a module called gold_sources. Importing by name
    picks up whichever room a test put on the path first.
    """
    cached = getattr(_gold_candidates, "fn", None)
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent / "gold_sources.py"
    spec = importlib.util.spec_from_file_location("rig_room_gold_sources", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("rig gold sources are missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    _gold_candidates.fn = module.candidates
    return module.candidates

_inner = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with _inner(app):
        store = PgStore(app.state.pool)
        await store.apply_schema()
        service = Service(store, _TankModels(app.state.tank), WebhookHandoff(app.state.http))
        app.state.rig = service
        root = Path(os.environ.get("CATALOGUE_DIR", str(Path(__file__).resolve().parent / "catalogues")))
        if not root.is_dir():
            root = Path("/app/catalogues")
        reports = await service.load_catalogues(root)
        for report in reports:
            log_line(AGENT, json.dumps(_public_report(report)), tenant_id=report.get("tenant_id") or None)
        nightly = [
            {
                "tenant_id": report["tenant_id"],
                "cron": "0 3 * * *",
                "kind": "pull_feeds",
                "input": {},
            }
            for report in reports
            if report.get("tenant_id")
        ]
        async with app.state.pool.acquire() as conn:
            await ensure_schedules(conn, schema_for(AGENT), nightly)
        yield


app.router.lifespan_context = _lifespan


class _TankModels:
    def __init__(self, tank: Any) -> None:
        self.tank = tank

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        result = await self.tank.route(tenant_id, task_type, messages)
        return str(result.get("content") or "")


def _public_report(report: dict) -> dict:
    """Import counts only. Keys are never written to the log."""
    return {
        "slug": report.get("slug"),
        "products": report.get("products"),
        "fits": report.get("fits"),
        "keys": report.get("keys", 0),
        "keys_rejected": report.get("keys_rejected", []),
    }
