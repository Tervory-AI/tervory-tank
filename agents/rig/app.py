"""Rig. Public catalogue API for one retailer at a time."""

from __future__ import annotations

import hmac
import importlib.util
import json
import logging
import os
import re
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from chassis.app import create_app
from chassis.db import ensure_schedules, schema_for
from chassis.jobs import JobContext
from chassis.logs import log_line
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from rig_brain.room import mount as mount_brain
from rigbox.api import mount
from rigbox.page_route import mount_page
from rigbox.service import RigError, Service
from rigbox.store import PgStore
from rigbox.quotes.api import mount as mount_quotes
from rigbox.quotes.service import QuoteService
from rigbox.quotes.senders import RetailerHandoff
from rigbox.quotes.store import PgQuotes
from rigbox.quotes.hosting import mount as mount_widget

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


async def retry_quotes(ctx: JobContext) -> dict:
    return {"attempted": await app.state.rig.retry_pending(ctx.tenant_id)}


app = create_app(
    agent=AGENT,
    handlers={"ping": ping, "pull_feeds": pull_feeds, "expire_searches": expire_searches,
              "retry_quotes": retry_quotes},
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
mount_brain(app)
mount_quotes(app)
mount_widget(app)

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


# Room-key reads for Tank. Shopper routes stay on X-Rig-Key and are unchanged.
# A request without the room key falls through to those routes. These handlers
# do not write quotes, fits, or keys, and they never put a key in the response.
_ROOM_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_ROOM_DROP = frozenset({
    "key", "keys", "key_hash", "secret", "password", "token", "webhook", "email", "origins",
})


def _room_key_ok(request: Request) -> bool:
    key = os.environ.get("TANK_KEY", "")
    presented = request.headers.get("x-tank-key") or ""
    try:
        return bool(key) and bool(presented) and hmac.compare_digest(key.encode(), presented.encode())
    except (AttributeError, TypeError, UnicodeError):
        return False


def _room_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _room_tenant(values: list[str]) -> tuple[str | None, JSONResponse | None]:
    named = [value.strip() for value in values if value.strip()]
    if not named:
        return None, _room_error(400, "tenant", "tenant_id is required")
    parsed: list[str] = []
    for value in named:
        try:
            parsed.append(str(uuid.UUID(value)))
        except ValueError:
            return None, _room_error(400, "tenant", "tenant_id is required")
    if any(item != parsed[0] for item in parsed):
        return None, _room_error(403, "tenant", "tenant mismatch")
    return parsed[0], None


def _query_tenants(request: Request) -> list[str]:
    return [value for key, value in request.query_params.multi_items() if key == "tenant_id"]


def _public_body(value: Any) -> Any:
    """Drop key material. Counts and shopper fields stay."""
    if isinstance(value, list):
        return [_public_body(item) for item in value]
    if not isinstance(value, dict):
        return value
    kept: dict[str, Any] = {}
    for key, item in value.items():
        name = str(key).lower()
        if name in _ROOM_DROP or "secret" in name or name.endswith("_key"):
            continue
        kept[str(key)] = _public_body(item)
    return kept


def _rig_service(request: Request) -> Any:
    service = getattr(request.app.state, "rig", None)
    if service is None:
        raise RigError("unavailable", "Rig is not ready.", 503)
    return service


async def _json_object(request: Request) -> tuple[dict[str, Any] | None, JSONResponse | None]:
    raw = await request.body()
    if len(raw) > 8192:
        return None, _room_error(413, "invalid", "The request is not valid.")
    if not raw:
        return {}, None
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return None, _room_error(422, "invalid", "The request is not valid.")
    if not isinstance(body, dict):
        return None, _room_error(422, "invalid", "The request is not valid.")
    return body, None


async def _catalogue_counts(request: Request) -> JSONResponse:
    """Product and fit counts for the caller's catalogue. No keys."""
    try:
        service = _rig_service(request)
    except RigError as exc:
        return _room_error(exc.status, exc.code, exc.message)
    tenant_id, error = _room_tenant(_query_tenants(request))
    if error is not None or tenant_id is None:
        return error or _room_error(400, "tenant", "tenant_id is required")
    products = await service.store.products(tenant_id)
    fits = await service.store.fits(tenant_id)
    return JSONResponse({"products": len(products), "fits": len(fits)})


async def _room_read(request: Request, kind: str) -> JSONResponse:
    try:
        service = _rig_service(request)
    except RigError as exc:
        return _room_error(exc.status, exc.code, exc.message)
    body: dict[str, Any] = {}
    if request.method == "POST":
        body, error = await _json_object(request)
        if error is not None or body is None:
            return error or _room_error(422, "invalid", "The request is not valid.")
    named = _query_tenants(request)
    if body.get("tenant_id") not in (None, ""):
        named.append(str(body.get("tenant_id")))
    tenant_id, error = _room_tenant(named)
    if error is not None or tenant_id is None:
        return error or _room_error(400, "tenant", "tenant_id is required")
    try:
        if kind == "search":
            raw_limit = request.query_params.get("limit")
            limit = int(raw_limit) if raw_limit and raw_limit.isdigit() else None
            result = await service.search(tenant_id, request.query_params.get("q") or "", limit)
        elif kind == "product":
            result = await service.product(tenant_id, request.url.path.rsplit("/", 1)[-1])
        elif kind == "graph":
            result = await service.graph(tenant_id, request.url.path.rsplit("/", 1)[-1])
        elif kind == "compare":
            ids = body.get("product_ids")
            if not isinstance(ids, list):
                return _room_error(422, "invalid", "The request is not valid.")
            result = await service.compare(tenant_id, [str(item) for item in ids])
        elif kind == "ask":
            product_id = str(body.get("product_id") or "")
            question = body.get("question") if isinstance(body.get("question"), str) else ""
            setup = body.get("setup") if isinstance(body.get("setup"), dict) else None
            # service.ask calls Tank /v1/route with task type rig.ask when a model is needed.
            result = await service.ask(tenant_id, product_id, question, setup)
        else:
            return _room_error(404, "not_found", "No such route.")
    except RigError as exc:
        return _room_error(exc.status, exc.code, exc.message)
    if not isinstance(result, dict):
        return _room_error(502, "unavailable", "Rig did not answer.")
    return JSONResponse(_public_body(result))


def _room_read_kind(method: str, path: str) -> str | None:
    if method == "GET" and path == "/catalogues":
        return "catalogues"
    if method == "GET" and path == "/v1/rig/search":
        return "search"
    if method == "GET":
        prefix, _, item = path.rpartition("/")
        if prefix in {"/v1/rig/products", "/v1/rig/graph"} and _ROOM_ID.fullmatch(item):
            return "product" if prefix.endswith("products") else "graph"
    if method == "POST" and path == "/v1/rig/compare":
        return "compare"
    if method == "POST" and path == "/v1/rig/ask":
        return "ask"
    return None


@app.middleware("http")
async def rig_room_reads(request: Request, call_next):
    """Serve Tank's read with the room key. Shopper calls fall through."""
    kind = _room_read_kind(request.method.upper(), request.url.path)
    if kind is None or not _room_key_ok(request):
        if kind == "catalogues":
            return JSONResponse(status_code=401, content={"detail": "room key required"})
        return await call_next(request)
    if kind == "catalogues":
        return await _catalogue_counts(request)
    return await _room_read(request, kind)


_inner = app.router.lifespan_context


@asynccontextmanager
async def _lifespan(app: FastAPI):
    async with _inner(app):
        store = PgStore(app.state.pool)
        await store.apply_schema()
        service = QuoteService(store, _TankModels(app.state.tank), RetailerHandoff(app.state.http),
                               PgQuotes(app.state.pool))
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
        nightly.extend({"tenant_id": tenant, "cron": "*/5 * * * *", "kind": "retry_quotes", "input": {}}
                       for tenant in await store.tenant_ids())
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
