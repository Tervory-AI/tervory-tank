"""Live memory for every Tisan endpoint, plus the user's view/edit/forget/off controls.

Identity is never taken from a request body. The signed-in caller is the
Tank-verified X-Tervory-User, forwarded with the room key and bound to one
X-Tervory-Tenant; an admin/service header alone is not an end-user identity.
The existing founder guard still applies, and any X-Tervory-Admin must be the
same user. Every row is scoped to that tenant and that user; a mismatch is
refused before anything is read or changed.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict

try:
    from agents.tisan import gates_memory
except ModuleNotFoundError:
    import gates_memory

log = logging.getLogger("agent")
SKIP = ("/health", "/readiness", "/memory")
TIMEOUT_S = 10


class Setting(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    user_id: str
    enabled: bool


class Edit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    user_id: str
    value: Any


class Rejection(BaseModel):
    tenant_id: UUID
    page_id: str
    frame_hash: str
    page_hash: str
    reason: str


async def signed_in(request: Request, tenant: Any, founder: Any) -> str:
    """The caller Tank signed for this exact request and tenant, or refuse (404) before any memory access."""
    from fastapi import HTTPException
    try:
        from chassis.user_assertion import signed_user
    except ImportError:
        raise gates_memory.SharedMemoryContractMissing("shared request verifier missing; needs current Tank chassis") from None
    try:
        actor = await signed_user(request, tenant_id=str(tenant), product="tisan", required=True)
    except HTTPException:
        raise HTTPException(404, "not found") from None
    admins = request.headers.getlist("x-tervory-admin")
    if len(admins) > 1 or (admins and admins[0].strip() != actor.user_id):
        raise HTTPException(404, "not found")
    founder(request.headers.get("x-tank-key", ""), actor.user_id)
    return gates_memory.trusted_user(actor.user_id)


def gate(app: Any, tenant: Any, user: str) -> Any:
    return gates_memory.GateMemory(app.state.memory, str(tenant), user)


async def caller(request: Request, tenant: Any) -> str | None:
    """The signed caller for a handler whose own guard already ran, or None (then nothing is remembered)."""
    try:
        return await signed_in(request, tenant, lambda key, user: None)
    except HTTPException:
        return None


async def remember_value(app: Any, tenant: Any, request: Request, kind: str, subject: str, value: Any) -> str | None:
    """Remember a live outcome for the signed caller; a memory outage never fails the user's action."""
    if not gates_memory.brain_enabled():
        return None
    user = await caller(request, tenant)
    if user is None:
        return None
    try:
        value = json.loads(json.dumps(value, default=str))
        saved = await asyncio.wait_for(gate(app, tenant, user).remember_choice(kind, subject, value), TIMEOUT_S)
        return saved.get("id") if saved else None
    except Exception as exc:
        if not gates_memory.is_outage(exc):
            raise
        log.warning("tisan memory write failed (%s)", type(exc).__name__)
        return None


async def _tenant(request: Request) -> str | None:
    value = request.query_params.get("tenant_id")
    if value is None and request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        try:
            data = json.loads(await request.body() or b"{}")
            value = data.get("tenant_id") if isinstance(data, dict) else None
        except ValueError:
            value = None
    try:
        return str(UUID(str(value))) if value is not None else None
    except ValueError:
        return None


def mount(app: Any, founder: Any) -> None:
    from fastapi.responses import JSONResponse

    @app.exception_handler(gates_memory.SharedMemoryContractMissing)
    async def contract_missing(request: Request, exc: Exception):
        # Fail closed: no product-side filtering fallback and no paid route.
        return JSONResponse({"detail": "memory unavailable: shared user-scoped memory contract missing"}, status_code=503)

    @app.middleware("http")
    async def recall_and_remember(request: Request, call_next):
        if not gates_memory.brain_enabled():
            return await call_next(request)
        tenant = None if request.url.path.startswith(SKIP) else await _tenant(request)
        verified, user = False, ""
        if tenant:
            try:
                user = await signed_in(request, tenant, founder)
                verified = True
            except HTTPException:
                verified = False
        recalled = None
        if verified:
            try:
                memory = gate(request.app, tenant, user)
                recalled = len(await asyncio.wait_for(memory.view(), TIMEOUT_S)) if await memory.enabled() else "off"
            except gates_memory.SharedMemoryContractMissing:
                recalled = "contract-missing"
            except Exception as exc:
                if not gates_memory.is_outage(exc):
                    return JSONResponse({"detail": "memory scope refused"}, status_code=403)
                log.warning("tisan memory recall failed (%s)", type(exc).__name__)
                recalled = "unavailable"
        response = await call_next(request)
        if verified:
            route = getattr(request.scope.get("route"), "path", request.url.path)
            try:
                subject = request.path_params.get("request_id") if request.path_params else None
                await asyncio.wait_for(gate(request.app, tenant, user).remember_outcome(
                    route, request.method, response.status_code, str(subject) if subject else None), TIMEOUT_S)
            except Exception as exc:
                if not gates_memory.is_outage(exc):
                    return JSONResponse({"detail": "memory scope refused"}, status_code=403)
                log.warning("tisan memory outcome failed (%s)", type(exc).__name__)
            response.headers["X-Tisan-Memory-Recalled"] = str(recalled)
        return response

    async def controls(request: Request, tenant: Any, target_user: str) -> Any:
        """The named target scope (tenant AND user) must be the signed-in caller's own, else refuse."""
        user = await signed_in(request, tenant, founder)
        if not gates_memory.brain_enabled():
            raise HTTPException(503, "memory unavailable")
        if target_user != user:
            raise HTTPException(404, "not found")
        return gate(app, tenant, user)

    @app.get("/memory")
    async def view(tenant_id: UUID, user_id: str, request: Request):
        memory = await controls(request, tenant_id, user_id)
        return {"enabled": await memory.enabled(), "remembers": gates_memory.REMEMBERS,
                "memories": [{"id": r["id"], "kind": r["kind"], "meta": r.get("meta") or {}} for r in await memory.view()]}

    @app.post("/memory/setting")
    async def setting(body: Setting, request: Request):
        memory = await controls(request, body.tenant_id, body.user_id)
        await memory.set_enabled(body.enabled)
        return {"enabled": body.enabled}

    @app.post("/memory/{memory_id}")
    async def edit(memory_id: UUID, body: Edit, request: Request):
        memory = await controls(request, body.tenant_id, body.user_id)
        try:
            saved = await memory.edit(str(memory_id), body.value)
        except KeyError:
            raise HTTPException(404, "not found") from None
        return {"id": saved["id"], "kind": saved["kind"]}

    @app.delete("/memory/{memory_id}")
    async def forget_one(memory_id: UUID, tenant_id: UUID, user_id: str, request: Request):
        memory = await controls(request, tenant_id, user_id)
        try:
            return {"forgotten": await memory.forget(str(memory_id))}
        except KeyError:
            raise HTTPException(404, "not found") from None

    @app.delete("/memory")
    async def forget_all(tenant_id: UUID, user_id: str, request: Request):
        memory = await controls(request, tenant_id, user_id)
        return {"forgotten": await memory.forget()}
