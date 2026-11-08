"""Live Opli memory and code-turn endpoints (chassis MemoryClient + Tank code_turn).

Auth: signed-in tenant + user from the authenticated actor chain only (request
headers resolved into actor scope after the workspace key). Body must never
carry a tenant/user selector. Memory uses app.state.memory — production MemoryClient
(chassis MemoryClient → Hermes). Task work: product_path → command.code_turn.
"""
from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from agents.opli.gates_memory import (
    MemoryControlError,
    MemoryScopeError,
    apply_memory_edit,
    apply_memory_forget,
    normalize_memory_control,
    require_authenticated_scope,
    set_memory_control,
    view_memories,
)
from agents.opli.product_path import run_opli_code_turn_with_memory


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


class CodeTurnLiveBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    thread_id: UUID
    text: str = Field(min_length=1, max_length=20000)
    model: str = Field(default="auto", min_length=1, max_length=100)
    prompt_id: UUID | None = None
    memory_control: Literal["off", "view", "edit", "forget"] | None = None
    repo: str | None = Field(default=None, max_length=400)


def _actor_scope_from_request(request: Request) -> tuple[str, str]:
    """Authenticated actor chain only — never a body user selector."""
    tenant = request.headers.get("x-tervory-tenant")
    user = request.headers.get("x-tervory-user", "").strip()
    try:
        return require_authenticated_scope(tenant_id=tenant, user_id=user)
    except MemoryScopeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _memory_client(app: FastAPI) -> Any:
    memory = getattr(app.state, "memory", None)
    if memory is None:
        raise HTTPException(status_code=503, detail="Opli memory is unavailable.")
    return memory


def _command(app: FastAPI) -> Any:
    command = getattr(app.state, "command", None)
    if command is None:
        raise HTTPException(status_code=503, detail="Opli Tank command agent is unavailable.")
    return command


def attach_opli_live_routes(app: FastAPI) -> None:
    """Mount live Opli memory + code-turn routes on a FastAPI app with chassis state."""

    @app.get("/v1/opli/memory")
    async def memory_view(
        request: Request,
        task_key: str = Query(default="memory_control", min_length=1, max_length=120),
        memory_control: Literal["off", "view", "edit", "forget"] = "view",
        memory_id: str | None = Query(default=None, min_length=1, max_length=80),
    ) -> dict[str, Any]:
        tenant, user = _actor_scope_from_request(request)
        control = normalize_memory_control(memory_control)
        memory = _memory_client(app)
        try:
            result = await view_memories(
                memory, tenant_id=tenant, user_id=user, task_key=task_key,
                memory_id=memory_id,
            )
        except MemoryScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        result["memory_control"] = result.get("memory_control") or control
        return result

    @app.post("/v1/opli/memory/control")
    async def memory_control_set(request: Request, body: MemoryControlBody) -> dict[str, Any]:
        tenant, user = _actor_scope_from_request(request)
        memory = _memory_client(app)
        try:
            saved = await set_memory_control(
                memory, tenant_id=tenant, user_id=user, control=body.control,
                memory_id=body.memory_id,
            )
        except MemoryScopeError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {"memory_control": body.control, "id": saved.get("id"), "tenant_id": tenant, "user_id": user}

    @app.post("/v1/opli/memory/edit")
    async def memory_edit(request: Request, body: MemoryEditBody) -> dict[str, Any]:
        tenant, user = _actor_scope_from_request(request)
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

    @app.post("/v1/opli/memory/forget")
    async def memory_forget(request: Request, body: MemoryForgetBody) -> dict[str, Any]:
        tenant, user = _actor_scope_from_request(request)
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

    @app.post("/v1/opli/code-turn")
    async def opli_code_turn(request: Request, body: CodeTurnLiveBody) -> dict[str, Any]:
        """Live task endpoint: memory free steps, then Tank command.code_turn, then remember."""
        tenant, user = _actor_scope_from_request(request)
        memory = _memory_client(app)
        command = _command(app)

        class _Actor:
            tenant_id = UUID(tenant) if not isinstance(tenant, UUID) else tenant
            user_id = user
            founder = False
            squads = frozenset()
            tenant_admin = False
            mcp_tools = {}

        class _Turn:
            def __init__(self) -> None:
                import uuid as _uuid
                self.text = body.text
                self.model = body.model
                self.prompt_id = body.prompt_id or body.thread_id
                self.request_id = _uuid.uuid4()
                self.tool_results = []
                self.history = []
                self.continuation = False
                self.mode = "ask"
                self.attachments = []
                self.local_mcp = []

        try:
            return await run_opli_code_turn_with_memory(
                memory,
                command,
                tenant_id=tenant,
                user_id=user,
                thread_id=body.thread_id,
                body=_Turn(),
                actor=_Actor(),
                memory_control=body.memory_control,
                repo=body.repo,
            )
        except MemoryScopeError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except MemoryControlError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
