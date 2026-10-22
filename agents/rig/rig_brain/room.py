"""Room-key task forwarding; the existing shopper API remains unchanged."""
import hmac
import os
import uuid

import httpx
from fastapi import Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_id: uuid.UUID
    task_id: uuid.UUID
    home_region: str
    question: str = Field(min_length=1, max_length=8000)


def authorize(key: str, region: str) -> None:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not key or not hmac.compare_digest(expected.encode(), key.encode()):
        raise HTTPException(401, "Rig room key required.")
    if region != "us-east" or region != os.environ.get("TANK_REGION", "us-east"):
        raise HTTPException(403, "This pilot stays in its home region.")


def mount(app):
    async def forward(method, path, key, **kwargs):
        base = os.environ.get("RIG_BRAIN_URL", "http://rig-brain:8001").rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=20, trust_env=False) as client:
                response = await client.request(method, base + path, headers={"X-Tank-Key": key}, **kwargs)
            if response.status_code not in {200, 202, 404, 409, 429}:
                raise HTTPException(503, "Rig's brain is unavailable.")
            return JSONResponse(response.json(), status_code=response.status_code)
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "Rig's brain is unavailable.") from None

    @app.post("/brain/tasks")
    async def start(body: Question, x_tank_key: str = Header(default="")):
        authorize(x_tank_key, body.home_region)
        return await forward("POST", "/tasks", x_tank_key, json=body.model_dump(mode="json"))

    @app.get("/brain/tasks/{task_id}")
    async def poll(task_id: uuid.UUID, tenant_id: uuid.UUID, home_region: str,
                   x_tank_key: str = Header(default="")):
        authorize(x_tank_key, home_region)
        return await forward("GET", "/tasks/" + str(task_id), x_tank_key,
                             params={"tenant_id": str(tenant_id), "home_region": home_region})

    @app.delete("/brain/tasks/{task_id}")
    async def cancel(task_id: uuid.UUID, tenant_id: uuid.UUID, home_region: str,
                     x_tank_key: str = Header(default="")):
        authorize(x_tank_key, home_region)
        return await forward("DELETE", "/tasks/" + str(task_id), x_tank_key,
                             params={"tenant_id": str(tenant_id), "home_region": home_region})
