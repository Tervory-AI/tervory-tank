"""Private optional Market Lab task handler; every model call returns to Tank."""
from contextlib import asynccontextmanager
import json
import os
from uuid import UUID

import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Request
from market_lab_brain import brain_enabled


@asynccontextmanager
async def lifespan(app):
    app.state.pool = await asyncpg.create_pool(os.environ["DATABASE_URL"], min_size=1, max_size=2)
    app.state.http = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"ok": True, "room": "market_lab", "enabled": brain_enabled()}


@app.post("/tasks")
async def task(request: Request, tenant_id: UUID, user_id: str):
    from chassis.user_assertion import signed_user
    from chassis.tank import TankClient
    if not brain_enabled():
        raise HTTPException(409, "Market Lab brain is off")
    actor = await signed_user(request, tenant_id=str(tenant_id), product="market_lab", required=True)
    if actor.user_id != user_id:
        raise HTTPException(403, "Actor mismatch")
    try:
        body = await request.json()
        if (not isinstance(body, dict) or set(body) != {"task_key", "input", "recall", "run_id"}
                or not isinstance(body["task_key"], str) or not 0 < len(body["task_key"]) <= 120
                or not isinstance(body["input"], dict) or not isinstance(body["recall"], list)):
            raise ValueError
        run_id = str(UUID(body["run_id"]))
    except (ValueError, TypeError, KeyError):
        raise HTTPException(422, "Invalid brain task") from None
    client = TankClient(os.environ.get("TANK_URL", "http://tank:8000"),
        os.environ.get("TANK_KEY_MARKET_LAB") or os.environ.get("TANK_KEY", ""), "market_lab", app.state.http)
    try:
        data = await client.room_task(actor, run_id, [
            {"role": "system", "content": "Market Lab: return JSON. Tenant memory: " + json.dumps(body["recall"])},
            {"role": "user", "content": json.dumps({"task": body["task_key"], "input": body["input"]})}])
        content = data["choices"][0]["message"]["content"]
        try:
            result = json.loads(content)
        except ValueError:
            result = {"text": content}
        return {"result": result, "receipt": data["receipt"]}
    except httpx.HTTPStatusError as exc:
        raise HTTPException(exc.response.status_code, "Market Lab task unavailable") from None
    except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError):
        raise HTTPException(503, "Market Lab task unavailable") from None
