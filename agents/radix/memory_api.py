"""Radix memory controls require Tank's nonce-protected product assertion."""
from __future__ import annotations

from contextlib import asynccontextmanager

import hmac
import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from gates_memory import (
    MemoryControlError,
    MemoryScopeError,
    apply_memory_edit,
    apply_memory_forget,
    normalize_memory_control,
    require_authenticated_scope,
    set_memory_control,
    view_memories,
)

_AGENT_KEY_ENV = "TANK_KEY_RADIX"
_FALLBACK_KEY_ENV = "TANK_KEY"
_WORKSPACE_KEY_ENV = "TANK_API_KEY"


class MemoryForgetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_id: str = Field(min_length=1, max_length=80)
    memory_control: Literal["forget"] = "forget"


class MemoryControlBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    control: Literal["off", "view", "edit", "forget"]
    memory_id: str | None = Field(default=None, min_length=1, max_length=80)


class MemoryEditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    memory_id: str = Field(min_length=1, max_length=80)
    text: str = Field(min_length=1, max_length=20000, pattern=r"\S")
    memory_control: Literal["edit", "forget"] | None = None


def _key_matches(presented: str, expected: str) -> bool:
    """Tank EXISTING key_matches (hmac.compare_digest); never invent secrets."""
    return bool(presented and expected and hmac.compare_digest(presented.encode(), expected.encode()))


def _require_signed_product_key(request: Request) -> None:
    """Check the room key before verifying the separate signed user assertion."""
    presented = request.headers.get("x-tank-key", "")
    agent = os.environ.get(_AGENT_KEY_ENV, "").strip() or os.environ.get(_FALLBACK_KEY_ENV, "").strip()
    workspace = os.environ.get(_WORKSPACE_KEY_ENV, "").strip()
    if not presented:
        raise HTTPException(status_code=401, detail="verified signed request required")
    if workspace and _key_matches(presented, workspace):
        raise HTTPException(
            status_code=403,
            detail="shared workspace key refused for Radix memory identity",
        )
    if not agent or not _key_matches(presented, agent):
        raise HTTPException(status_code=401, detail="verified signed request required")


async def _actor_scope_from_request(request: Request) -> tuple[str, str]:
    """Verified Actor from Tank-signed headers only — never a body selector."""
    _require_signed_product_key(request)
    header_tenant = request.headers.get("x-tervory-tenant")
    header_user = (request.headers.get("x-tervory-user") or "").strip()
    q_tenant = request.query_params.get("tenant_id")
    q_user = request.query_params.get("user_id")
    if q_tenant is not None and header_tenant is not None and str(q_tenant) != str(header_tenant):
        raise HTTPException(status_code=403, detail="forged tenant_id selector refused")
    if q_user is not None and header_user and str(q_user) != str(header_user):
        raise HTTPException(status_code=403, detail="forged user_id selector refused")
    try:
        tenant, _ = require_authenticated_scope(tenant_id=header_tenant, user_id=header_user)
        from chassis.user_assertion import signed_user
    except (MemoryScopeError, ImportError):
        raise HTTPException(status_code=401, detail="verified signed request required") from None
    actor = await signed_user(request, tenant_id=tenant, product="radix", required=True)
    if actor.user_id != header_user:
        raise HTTPException(status_code=403, detail="forged user selector refused")
    return actor.tenant_id, actor.user_id


def _memory_client(app: FastAPI) -> Any:
    memory = getattr(app.state, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="Radix memory is unavailable.")
    return memory


def _refuse_forged_body_selectors(body: BaseModel, tenant: str, user: str) -> None:
    data = body.model_dump()
    if "tenant_id" in data and data["tenant_id"] is not None and str(data["tenant_id"]) != tenant:
        raise HTTPException(status_code=403, detail="forged tenant_id selector refused")
    if "user_id" in data and data["user_id"] is not None and str(data["user_id"]) != user:
        raise HTTPException(status_code=403, detail="forged user_id selector refused")


@asynccontextmanager
async def memory_actor_scope(app, tenant, user):
    if getattr(app.state, "radix_task_runtime", False):
        from task_runtime import actor_lock
        async with actor_lock(app.state.pool, tenant, user):
            yield
    else:
        yield


def attach_memory_routes(app: FastAPI) -> None:
    """Mount live Radix memory control routes on the product surface."""

    @app.get("/v1/radix/memory")
    async def memory_view(
        request: Request,
        task_key: str = Query(default="memory_control", min_length=1, max_length=120),
        memory_control: Literal["off", "view", "edit", "forget"] = "view",
        memory_id: str | None = Query(default=None, min_length=1, max_length=80),
    ) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        async with memory_actor_scope(app, tenant, user):
            control = normalize_memory_control(memory_control)
            memory = _memory_client(app)
            try:
                result = await view_memories(
                    memory, tenant_id=tenant, user_id=user, task_key=task_key, memory_id=memory_id,
                )
            except MemoryScopeError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            result["memory_control"] = result.get("memory_control") or control
            return result

    @app.post("/v1/radix/memory/control")
    async def memory_control_set(request: Request, body: MemoryControlBody) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        async with memory_actor_scope(app, tenant, user):
            _refuse_forged_body_selectors(body, tenant, user)
            memory = _memory_client(app)
            try:
                saved = await set_memory_control(
                    memory, tenant_id=tenant, user_id=user, control=body.control,
                    memory_id=body.memory_id,
                )
            except MemoryScopeError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            return {
                "memory_control": body.control,
                "id": saved.get("id"),
                "tenant_id": tenant,
                "user_id": user,
            }

    @app.post("/v1/radix/memory/edit")
    async def memory_edit(request: Request, body: MemoryEditBody) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        async with memory_actor_scope(app, tenant, user):
            _refuse_forged_body_selectors(body, tenant, user)
            memory = _memory_client(app)
            try:
                return await apply_memory_edit(
                    memory, memory_id=body.memory_id, tenant_id=tenant, user_id=user,
                    text=body.text, memory_control=body.memory_control,
                )
            except MemoryControlError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except MemoryScopeError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/v1/radix/memory/forget")
    async def memory_forget(request: Request, body: MemoryForgetBody) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        async with memory_actor_scope(app, tenant, user):
            _refuse_forged_body_selectors(body, tenant, user)
            memory = _memory_client(app)
            try:
                await apply_memory_forget(
                    memory, memory_id=body.memory_id, tenant_id=tenant, user_id=user,
                    memory_control=body.memory_control,
                )
            except MemoryControlError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except MemoryScopeError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            return {"forgotten": body.memory_id, "tenant_id": tenant, "user_id": user}
