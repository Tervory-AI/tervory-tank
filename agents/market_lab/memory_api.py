"""Live Market Lab memory controls (view / edit / forget / switch-off).

Auth: tenant + user from the shared verified, nonce-protected assertion only.
Body/query must never supply a forged tenant or user selector that overrides
the actor. Target records must match actor tenant AND user or the call is
refused before any read or mutation.
"""
from __future__ import annotations

from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from market_lab_memory_runtime import (
    MemoryControlError,
    MemoryScopeError,
    apply_memory_edit,
    apply_memory_forget,
    normalize_memory_control,
    set_memory_control,
    view_memories,
)


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


async def _actor_scope_from_request(request: Request, *, body: bytes = b"") -> tuple[str, str]:
    from core.personal import verified_actor
    actor = await verified_actor(request, required=True)
    tenant, user = actor.tenant_id, actor.user_id
    if request.query_params.get('tenant_id', tenant) != tenant or request.query_params.get('user_id', user) != user:
        raise HTTPException(403, 'Memory scope refused')
    return tenant, user


def _memory_client(app: FastAPI) -> Any:
    memory = getattr(app.state, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="Market Lab memory is unavailable.")
    return memory


def _refuse_forged_body_selectors(body: BaseModel, tenant: str, user: str) -> None:
    data = body.model_dump()
    if "tenant_id" in data and data["tenant_id"] is not None and str(data["tenant_id"]) != tenant:
        raise HTTPException(status_code=403, detail="forged tenant_id selector refused")
    if "user_id" in data and data["user_id"] is not None and str(data["user_id"]) != user:
        raise HTTPException(status_code=403, detail="forged user_id selector refused")


def attach_memory_routes(app: FastAPI) -> None:
    """Mount live Market Lab memory control routes."""

    @app.get("/v1/market-lab/memory")
    async def memory_view(
        request: Request,
        task_key: str = Query(default="memory_control", min_length=1, max_length=120),
        memory_control: Literal["off", "view", "edit", "forget"] = "view",
        memory_id: str | None = Query(default=None, min_length=1, max_length=80),
    ) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        control = normalize_memory_control(memory_control)
        memory = _memory_client(app)
        try:
            result = await view_memories(
                memory,
                tenant_id=tenant,
                user_id=user,
                task_key=task_key,
                memory_id=memory_id,
            )
        except MemoryScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        result["memory_control"] = result.get("memory_control") or control
        return result

    @app.post("/v1/market-lab/memory/control")
    async def memory_control_set(request: Request, body: MemoryControlBody) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        _refuse_forged_body_selectors(body, tenant, user)
        memory = _memory_client(app)
        try:
            saved = await set_memory_control(
                memory,
                tenant_id=tenant,
                user_id=user,
                control=body.control,
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

    @app.post("/v1/market-lab/memory/edit")
    async def memory_edit(request: Request, body: MemoryEditBody) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        _refuse_forged_body_selectors(body, tenant, user)
        memory = _memory_client(app)
        try:
            return await apply_memory_edit(
                memory,
                memory_id=body.memory_id,
                tenant_id=tenant,
                user_id=user,
                text=body.text,
                memory_control=body.memory_control,
            )
        except MemoryControlError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except MemoryScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.post("/v1/market-lab/memory/forget")
    async def memory_forget(request: Request, body: MemoryForgetBody) -> dict[str, Any]:
        tenant, user = await _actor_scope_from_request(request)
        _refuse_forged_body_selectors(body, tenant, user)
        memory = _memory_client(app)
        try:
            await apply_memory_forget(
                memory,
                memory_id=body.memory_id,
                tenant_id=tenant,
                user_id=user,
                memory_control=body.memory_control,
            )
        except MemoryControlError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except MemoryScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"forgotten": body.memory_id, "tenant_id": tenant, "user_id": user}
