"""Remote MCP server for mcp.tervory.com. Streamable HTTP, OAuth, Tank only."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from connector.oauth import Settings, load_settings, register_oauth, www_authenticate
from connector.store import MemoryStore, RedisStore, Store
from connector.tank import HttpTank, Tank
from connector.tokens import TokenError, read_access
from connector.tenant import tenant_id_for
from connector.tools import Caller, call_tool, list_tools, render

log = logging.getLogger("tervory.mcp")

PROTOCOLS = ("2025-11-25", "2025-06-18", "2025-03-26")


def create_app(
    *,
    settings: Settings | None = None,
    store: Store | None = None,
    tank: Tank | None = None,
    http: httpx.AsyncClient | None = None,
) -> FastAPI:
    chosen = settings or load_settings()
    if not log.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        log.propagate = False

    @asynccontextmanager
    async def lifespan(server: FastAPI):
        if getattr(server.state, "http", None) is None:
            server.state.http = httpx.AsyncClient(timeout=httpx.Timeout(30.0, read=120.0))
            server.state.http_owned = True
        if getattr(server.state, "tank", None) is None:
            server.state.tank = HttpTank(chosen.tank_url, chosen.tank_api_key, server.state.http)
        yield
        if getattr(server.state, "http_owned", False):
            await server.state.http.aclose()

    app = FastAPI(title="Tervory", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.settings = chosen
    app.state.store = store or (_redis_or_memory(chosen))
    app.state.http = http
    app.state.http_owned = False
    app.state.tank = tank
    register_oauth(app, chosen, app.state.store)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.api_route("/mcp", methods=["GET", "DELETE"])
    async def mcp_other(request: Request) -> Response:
        if _bearer(request) is None:
            return _unauthorized(chosen)
        return Response(status_code=405, headers={"allow": "POST"})

    @app.post("/mcp")
    async def mcp(request: Request) -> Response:
        blocked = _origin_block(request, chosen)
        if blocked is not None:
            return blocked
        raw_token = _bearer(request)
        if raw_token is None:
            return _unauthorized(chosen)
        try:
            caller = _caller(raw_token, chosen)
        except TokenError:
            return _unauthorized(chosen)
        accept = request.headers.get("accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            return JSONResponse(status_code=406, content={"error": "Accept must list application/json and text/event-stream"})
        try:
            body = await request.json()
        except ValueError:
            return _rpc(None, error={"code": -32700, "message": "Parse error"})
        if not isinstance(body, dict):
            return _rpc(None, error={"code": -32600, "message": "Invalid request"})
        method = body.get("method")
        if not isinstance(method, str) or not method:
            return _rpc(body.get("id"), error={"code": -32600, "message": "Invalid request"})
        request_id = body.get("id")
        if request_id is None or method.startswith("notifications/"):
            log.info("notification %s", method)
            return Response(status_code=202)
        version = request.headers.get("mcp-protocol-version")
        if version and version not in PROTOCOLS and method != "initialize":
            return _rpc(request_id, error={"code": -32600, "message": "Unsupported protocol version."})
        try:
            result = await _method(method, body.get("params"), caller, app.state.tank, version)
        except _Rpc as exc:
            return _rpc(request_id, error={"code": -32602, "message": exc.message})
        except Exception:
            log.info("mcp call failed")
            return _rpc(request_id, error={"code": -32603, "message": "That could not be completed."})
        if result is None:
            return _rpc(request_id, error={"code": -32601, "message": "Method not found"})
        return _rpc(request_id, result=result, version=version if version in PROTOCOLS else None)

    return app


def _redis_or_memory(settings: Settings) -> Store:
    if not settings.redis_url:
        return MemoryStore()
    try:
        return RedisStore(settings.redis_url)
    except Exception:
        log.info("sign-in state is in memory")
        return MemoryStore()


def _unauthorized(settings: Settings) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"error": "unauthorized"},
        headers={"www-authenticate": www_authenticate(settings), "cache-control": "no-store"},
    )


def _bearer(request: Request) -> str | None:
    if request.query_params.get("token") or request.query_params.get("access_token"):
        return None
    header = request.headers.get("authorization", "")
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def _caller(token: str, settings: Settings) -> Caller:
    if len(settings.signing_key) < 16:
        raise TokenError("rejected")
    payload = read_access(
        token,
        secret=settings.signing_key,
        issuer=settings.issuer,
        audience=settings.resource_url,
    )
    org_id = str(payload["org_id"])
    tenant_id = tenant_id_for(org_id, settings.tenant_aliases)
    if payload.get("tenant_id") != tenant_id:
        raise TokenError("rejected")
    return Caller(user_id=str(payload["sub"]), org_id=org_id, tenant_id=tenant_id)


def _origin_block(request: Request, settings: Settings) -> Response | None:
    origin = request.headers.get("origin")
    if not origin:
        return None
    parsed = urlparse(origin)
    host = (parsed.hostname or "").lower()
    public_host = (urlparse(settings.public_url).hostname or "").lower()
    allowed = host in {"claude.ai", "www.claude.ai", "claude.com", "localhost", "127.0.0.1", public_host}
    scheme_ok = parsed.scheme == "https" or (parsed.scheme == "http" and host in {"localhost", "127.0.0.1"})
    if allowed and scheme_ok:
        return None
    log.info("origin refused")
    return JSONResponse(status_code=403, content={"error": "origin"})


async def _method(method: str, params: Any, caller: Caller, tank: Tank, version: str | None) -> dict[str, Any] | None:
    if method == "initialize":
        asked = ""
        if isinstance(params, dict):
            asked = str(params.get("protocolVersion") or "")
        chosen = asked if asked in PROTOCOLS else PROTOCOLS[-1]
        if asked and asked not in PROTOCOLS:
            raise _Rpc("Unsupported protocol version.")
        return {
            "protocolVersion": chosen,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "Tervory", "version": "1.0.0"},
        }
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": list_tools()}
    if method == "tools/call":
        if not isinstance(params, dict) or not isinstance(params.get("name"), str):
            raise _Rpc("Name the tool to call.")
        payload = await call_tool(str(params["name"]), caller, tank, params.get("arguments"))
        failed = payload.get("ok") is False
        log.info("tool %s error=%s", params["name"], failed)
        return {"content": [{"type": "text", "text": render(payload)}], "isError": failed}
    del version
    return None


class _Rpc(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _rpc(
    request_id: Any,
    *,
    result: dict[str, Any] | None = None,
    error: dict[str, Any] | None = None,
    version: str | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {"jsonrpc": "2.0", "id": request_id}
    if error is not None:
        body["error"] = error
    else:
        body["result"] = result
    headers = {"cache-control": "no-store"}
    if version:
        headers["mcp-protocol-version"] = version
    return JSONResponse(body, headers=headers)


app = create_app()
