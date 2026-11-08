"""Default-off planning runtime. Only Tank discovers and signs this service.

Pure parsing/validation precedes the existing tisan.plan route. Tank retains
policy, paid admission/checkpoints and the actual cost/token/ledger evidence.
"""
from __future__ import annotations

import hmac
import os
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

import asyncpg
import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict

try:
    from agents.tisan import builder, gates_memory
except ModuleNotFoundError:
    import builder
    import gates_memory


@asynccontextmanager
async def lifespan(app):
    database = os.environ.get('DATABASE_URL', '')
    app.state.pool = (await asyncpg.create_pool(database, min_size=1, max_size=2)
                      if database and gates_memory.brain_enabled() else None)
    try:
        yield
    finally:
        if app.state.pool is not None:
            await app.state.pool.close()
        client = _tank.pop('client', None)
        if client is not None:
            await client._http.aclose()


app = FastAPI(lifespan=lifespan)
_tank: dict[str, Any] = {}


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_key: str
    input: dict
    recall: list[dict]
    run_id: UUID


def authenticate(key: str) -> None:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "room key required")


def tank_client() -> Any:
    if "client" not in _tank:
        from chassis.tank import TankClient
        _tank["client"] = TankClient(os.environ.get("TANK_URL", "http://tank:8000"), os.environ.get("TANK_KEY", ""),
                                     "tisan", httpx.AsyncClient(timeout=70))
    return _tank["client"]


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "room": "tisan", "tasks": ["plan"], "enabled": gates_memory.brain_enabled()}


@app.post("/tasks/plan")
async def plan(body: Plan, request: Request, tenant_id: UUID, user_id: str,
               x_tank_key: str = Header(default=""), x_home_region: str = Header(default="")) -> dict:
    authenticate(x_tank_key)
    if not gates_memory.brain_enabled():
        raise HTTPException(503, "tisan brain could not plan")
    if x_home_region != os.environ.get("TANK_REGION", "us-east"):
        raise HTTPException(403, "This task belongs to another region.")
    if getattr(app.state, 'pool', None) is None:
        raise HTTPException(503, 'DATABASE_URL is required for signed planning')
    from chassis.user_assertion import PostgresNonces, signed_user
    actor = await signed_user(request, tenant_id=str(tenant_id), product='tisan', required=True,
                              nonces=PostgresNonces(app.state.pool, 'tisan'))
    if actor.user_id != user_id:
        raise HTTPException(403, 'Actor mismatch')
    if body.task_key != 'tisan.plan' or set(body.input) != {'request', 'contract'} or body.recall:
        raise HTTPException(422, 'Invalid planning task')
    prompt = body.input['request']
    if not isinstance(prompt, str) or not 1 <= len(prompt) <= 16000 or not isinstance(body.input['contract'], dict):
        raise HTTPException(422, 'Invalid planning task')
    replies: list = []
    try:
        result = await builder.make_plan({'request': prompt}, actor.tenant_id, body.input['contract'],
            builder.run_tank(tank_client(), str(body.run_id)), replies, cache_allowed=False)
    except ValueError:
        raise HTTPException(422, 'plan could not be validated') from None
    receipt = {**gates_memory.tank_receipt(replies), 'source': 'tisan-brain',
               'tenant_id': actor.tenant_id, 'user_id': actor.user_id, 'run_id': str(body.run_id),
               'room': 'tisan', 'task_type': 'tisan.plan', 'region': x_home_region}
    return {'result': result, 'receipt': receipt}
