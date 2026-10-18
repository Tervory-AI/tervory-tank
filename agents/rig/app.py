"""Rig. Public catalogue API for one retailer at a time."""

from __future__ import annotations

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
from fastapi import FastAPI

from rigbox.api import mount
from rigbox.page_route import mount_page
from rigbox.reserve import SmtpMailer
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


app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "pull_feeds": pull_feeds},
    schedules=[
        {
            "tenant_id": HEARTBEAT_TENANT,
            "cron": "*/5 * * * *",
            "kind": "ping",
            "input": {"heartbeat": True},
        }
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

_inner = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with _inner(app):
        store = PgStore(app.state.pool)
        await store.apply_schema()
        service = Service(store, _TankModels(app.state.tank), WebhookHandoff(app.state.http, SmtpMailer.from_env()))
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
