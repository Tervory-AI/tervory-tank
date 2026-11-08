"""Opt-in private coordinator; all inference and authorization return to Tank."""
from contextlib import asynccontextmanager
import os
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

import httpx
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict
from chassis.tank import TankClient
from chassis.sqlite_nonces import SQLiteNonces
from chassis.user_assertion import signed_user
from radix_brain import brain_enabled, error_receipt, explain
from verify.routes import require_tank


@asynccontextmanager
async def lifespan(app):
    if not brain_enabled():
        yield
        return
    app.state.assertion_nonces = SQLiteNonces(Path(os.environ.get("DATA_DIR", "/data")) / "assertion-nonces.sqlite3")
    async with httpx.AsyncClient(timeout=65, follow_redirects=False) as http:
        app.state.tank = TankClient(os.environ.get("TANK_URL", "http://tank:8000"),
            os.environ.get("TANK_KEY_RADIX") or os.environ.get("TANK_KEY", ""), "radix", http)
        yield


app = FastAPI(lifespan=lifespan)


class Task(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_key: Literal["radix.site_risk"]
    input: dict[str, Any]
    recall: list[dict[str, Any]]
    run_id: UUID


@app.get("/health")
async def health():
    return {"ok": True, "room": "radix", "enabled": brain_enabled()}


@app.post("/tasks")
async def task(request: Request, body: Task, tenant_id: UUID, user_id: str):
    if not brain_enabled():
        raise HTTPException(409, "Radix brain is off")
    if request.headers.get("x-home-region") != os.environ.get("TANK_REGION", "us-east"):
        raise HTTPException(403, "Region mismatch")
    await require_tank(request)
    actor = await signed_user(request, tenant_id=str(tenant_id), product="radix", required=True,
                              nonces=getattr(request.app.state, "assertion_nonces", None))
    if actor.user_id != user_id:
        raise HTTPException(403, "Actor mismatch")
    try:
        return await explain(app.state.tank, actor, body.run_id, body.task_key, body.input, body.recall)
    except httpx.HTTPStatusError as exc:
        receipt = error_receipt(exc, actor, body.run_id)
        detail = {"message": "Radix task unavailable", "receipt": receipt} if receipt else "Radix task unavailable"
        raise HTTPException(exc.response.status_code, detail) from None
    except (httpx.HTTPError, TimeoutError, ValueError, KeyError, TypeError, IndexError):
        raise HTTPException(503, "Radix task unavailable") from None
