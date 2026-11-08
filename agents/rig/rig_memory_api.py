"""Live Rig memory controls (view / edit / forget / switch-off).

Auth: signed-in tenant + user from Tank shared nonce-protected assertions.
Body/query must never supply a forged tenant or user selector that overrides
the actor. Target records must match actor tenant AND user or the call is
refused before any read or mutation. Agent key is not user identity proof.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from chassis.user_assertion import signed_user
from fastapi import FastAPI, HTTPException, Query, Request
from rig_memory import (
    MEMORY_OFF_KIND,
    MEMORY_OFF_SOURCE,
    MEMORY_OFF_TEXT,
    build_memory_text,
    memory_enabled,
    memory_kinds,
    memory_off_from_rows,
    owned_memory_row,
    select_tenant_user_memories,
)
from pydantic import BaseModel, ConfigDict, Field


class MemoryForgetBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    memory_id: str = Field(min_length=1, max_length=80)
    user_id: str | None = Field(default=None, max_length=200)


class MemoryEditBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    text: str = Field(min_length=1, max_length=8000)
    kind: str = Field(min_length=1, max_length=64)
    source: str = Field(min_length=1, max_length=200)
    user_id: str | None = Field(default=None, max_length=200)
    task_key: str | None = Field(default=None, max_length=200)
    memory_id: str | None = Field(default=None, max_length=80)


class MemorySwitchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: UUID
    enabled: bool
    user_id: str | None = Field(default=None, max_length=200)


async def _signed_actor(request: Request, body: bytes = b"") -> tuple[str, str]:
    import json
    try:
        payload = json.loads(body) if body else {}
        if not isinstance(payload, dict):
            raise ValueError("Object required")
        tenant = request.headers.get("x-tervory-tenant") or request.query_params.get("tenant_id") or payload.get("tenant_id")
        actor = await signed_user(request, tenant_id=str(tenant), product="rig", required=True)
    except (ValueError, TypeError):
        raise HTTPException(401, "Signed user required for memory") from None
    return actor.tenant_id, actor.user_id


def _refuse_scope_widen(actor_tenant: str, actor_user: str, *, body_tenant: Any = None, body_user: Any = None) -> None:
    if body_tenant is not None and str(body_tenant) != str(actor_tenant):
        raise HTTPException(status_code=403, detail="scope widen refused")
    if body_user is not None and str(body_user) != str(actor_user):
        raise HTTPException(status_code=403, detail="scope widen refused")


def _memory_client(app: FastAPI) -> Any:
    memory = getattr(app.state, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="Rig memory is unavailable.")
    return memory


def attach_memory_routes(app: FastAPI) -> None:
    """Mount live Rig memory control routes on the product app."""

    @app.get("/memory/records")
    async def memory_view(
        request: Request,
        tenant_id: UUID | None = Query(default=None),
        user_id: str | None = Query(default=None),
        tier: str = Query(default="client"),
    ) -> dict[str, Any]:
        actor_tenant, actor_user = await _signed_actor(request)
        _refuse_scope_widen(actor_tenant, actor_user, body_tenant=tenant_id, body_user=user_id)
        if not memory_enabled():
            return {"memories": [], "memory_enabled": False, "count": 0}
        memory = _memory_client(app)
        rows = await memory.records(actor_tenant, user_id=actor_user, tier=tier)
        if memory_off_from_rows(rows, tenant_id=actor_tenant, user_id=actor_user):
            return {"memories": [], "memory_enabled": False, "count": 0}
        scoped = select_tenant_user_memories(rows, tenant_id=actor_tenant, user_id=actor_user)
        return {"memories": scoped, "memory_enabled": True, "count": len(scoped)}

    @app.post("/memory/edit")
    async def memory_edit(request: Request) -> dict[str, Any]:
        raw = await request.body()
        actor_tenant, actor_user = await _signed_actor(request, raw)
        try:
            body = MemoryEditBody.model_validate_json(raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid memory edit") from exc
        _refuse_scope_widen(
            actor_tenant, actor_user, body_tenant=body.tenant_id, body_user=body.user_id
        )
        if not memory_enabled():
            raise HTTPException(status_code=409, detail="Memory is switched off")
        memory = _memory_client(app)
        rows = await memory.records(actor_tenant, user_id=actor_user)
        if memory_off_from_rows(rows, tenant_id=actor_tenant, user_id=actor_user):
            raise HTTPException(status_code=409, detail="Memory is switched off")
        if body.kind not in memory_kinds():
            raise HTTPException(status_code=422, detail="unsupported Rig memory kind")
        if body.memory_id:
            owned = owned_memory_row(
                rows,
                memory_id=body.memory_id,
                tenant_id=actor_tenant,
                user_id=actor_user,
            )
            if owned is None:
                raise HTTPException(status_code=403, detail="Memory ownership required")
            if body.kind != owned.get("kind"):
                raise HTTPException(status_code=422, detail="unsupported Rig memory kind")
        try:
            build_memory_text(summary=body.text)
        except ValueError:
            raise HTTPException(422, "Invalid memory text") from None
        await invalidate_outcomes(memory, rows, actor_tenant, actor_user, exclude=body.memory_id)
        saved = await memory.remember(
            actor_tenant,
            body.text,
            body.kind,
            body.source,
            user_id=actor_user,
            record_id=body.memory_id, replace=bool(body.memory_id),
            meta={
                "user_id": actor_user,
                "task_key": body.task_key,
                "edited": True,
                **({"replaces": body.memory_id} if body.memory_id else {}),
            },
        )
        return {"ok": True, "memory": saved, "memory_enabled": True}

    @app.post("/memory/forget")
    async def memory_forget(request: Request) -> dict[str, Any]:
        raw = await request.body()
        actor_tenant, actor_user = await _signed_actor(request, raw)
        try:
            body = MemoryForgetBody.model_validate_json(raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid memory forget") from exc
        _refuse_scope_widen(
            actor_tenant, actor_user, body_tenant=body.tenant_id, body_user=body.user_id
        )
        if not memory_enabled():
            raise HTTPException(status_code=409, detail="Memory is switched off")
        memory = _memory_client(app)
        rows = await memory.records(actor_tenant, user_id=actor_user)
        owned = owned_memory_row(
            rows,
            memory_id=body.memory_id,
            tenant_id=actor_tenant,
            user_id=actor_user,
        )
        if owned is None:
            raise HTTPException(status_code=403, detail="Memory ownership required")
        await invalidate_outcomes(memory, rows, actor_tenant, actor_user, exclude=body.memory_id)
        await memory.forget(body.memory_id, actor_tenant, user_id=actor_user)
        return {"ok": True, "forgotten": body.memory_id, "user_id": actor_user}

    @app.post("/memory/switch")
    async def memory_switch(request: Request) -> dict[str, Any]:
        raw = await request.body()
        actor_tenant, actor_user = await _signed_actor(request, raw)
        try:
            body = MemorySwitchBody.model_validate_json(raw)
        except Exception as exc:
            raise HTTPException(status_code=422, detail="invalid memory switch") from exc
        _refuse_scope_widen(
            actor_tenant, actor_user, body_tenant=body.tenant_id, body_user=body.user_id
        )
        if not memory_enabled():
            raise HTTPException(status_code=409, detail="Memory is switched off globally")
        memory = _memory_client(app)
        rows = await memory.records(actor_tenant, user_id=actor_user)
        off_rows = [
            row
            for row in select_tenant_user_memories(
                rows, tenant_id=actor_tenant, user_id=actor_user
            )
            if row.get("kind") == MEMORY_OFF_KIND and MEMORY_OFF_TEXT in str(row.get("text", ""))
        ]
        currently_off = bool(off_rows)
        if body.enabled is False and not currently_off:
            await memory.remember(
                actor_tenant,
                build_memory_text(summary=MEMORY_OFF_TEXT, receipt="control=off"),
                MEMORY_OFF_KIND,
                MEMORY_OFF_SOURCE,
                user_id=actor_user,
                meta={"user_id": actor_user, "task_key": "memory_control", "control": "off"},
            )
            return {"ok": True, "memory_enabled": False, "user_id": actor_user}
        if body.enabled is True and currently_off:
            for row in off_rows:
                await memory.forget(str(row["id"]), actor_tenant, user_id=actor_user)
            return {"ok": True, "memory_enabled": True, "user_id": actor_user}
        return {"ok": True, "memory_enabled": not currently_off, "user_id": actor_user}


async def invalidate_outcomes(memory, rows, tenant, user, *, exclude=None):
    # Any changed personal evidence invalidates derived outcomes. Never delete
    # another user's receipt or an explicitly shared store row.
    for row in rows:
        if (str(row.get("id")) != exclude and
                (row.get("meta") or {}).get("user_id") == user and
                (row.get("meta") or {}).get("outcome")):
            await memory.forget(str(row["id"]), tenant, user_id=user)
