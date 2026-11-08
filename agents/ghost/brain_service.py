"""Private Autumbra brain. Tank owns discovery, room policy and paid receipts."""
from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from chassis.tank import TankClient

from .brain import TASK_TYPES, contains_secret, brain_enabled
from .brain_state import verified_actor
from .store import Store

SYSTEM = "You are Autumbra's security brain. Use the supplied tenant memory. Answer briefly."


class TaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=4000)
    case_ref: str = Field(pattern=r"^autumbra-user:[0-9a-f]{64}$")
    home_region: str


class BrainTask(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: uuid.UUID
    task_key: str
    input: TaskInput
    recall: list[dict] = Field(max_length=20)


def tank_client(http):
    return TankClient(os.environ.get("TANK_URL", "http://tank:8000"),
                      os.environ.get("TANK_KEY", ""), "ghost", http)


async def route(http, body, actor):
    memory = "\n".join(f"- {m.get('kind')}: {m.get('text')}" for m in body.recall)
    return await tank_client(http).room_task(actor, str(body.run_id), [
        {"role": "system", "content": SYSTEM + ("\nMemory:\n" + memory if memory else "")},
        {"role": "user", "content": body.task_key + ": " + body.input.text}])


def create_app(http: httpx.AsyncClient | None = None, store: Store | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        owned = store or Store(Path(os.environ.get("DATA_DIR", "/data")) / "brain.sqlite3")
        app.state.store = owned
        try:
            yield
        finally:
            if store is None:
                owned.close()
    app = FastAPI(title="autumbra-brain", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    if store is not None:
        app.state.store = store

    @app.get("/health")
    async def health():
        return {"ok": True, "room": "ghost", "service": "autumbra-brain"}

    @app.post("/tasks")
    async def tasks(body: BrainTask, request: Request, tenant_id: uuid.UUID, user_id: str):
        if not brain_enabled():
            raise HTTPException(503, "GHOST_BRAIN_ENABLED is off.")
        actor = await verified_actor(request, tenant_id, user_id)
        if body.input.home_region != os.environ.get("TANK_REGION", "us-east"):
            raise HTTPException(403, "Autumbra task region mismatch.")
        if body.task_key not in TASK_TYPES or contains_secret(body.input.text) or contains_secret(str(body.recall)):
            raise HTTPException(422, "Invalid Autumbra brain task.")
        try:
            if http is not None:
                data = await route(http, body, actor)
            else:
                async with httpx.AsyncClient(follow_redirects=False) as client:
                    data = await route(client, body, actor)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(exc.response.status_code, "Autumbra task unavailable.") from None
        except (httpx.HTTPError, ValueError, AttributeError):
            raise HTTPException(503, "Autumbra task unavailable.") from None
        return {"result": data["choices"][0]["message"]["content"], "receipt": data["receipt"]}
    return app


app = create_app()
