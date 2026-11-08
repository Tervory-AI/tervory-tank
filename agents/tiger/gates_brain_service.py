"""Opt-in Tiger brain process. A verified server actor is required before Tank.

No provider keys, no direct inference gateway: Tank still owns policy, paid-step
admission and model receipts. The ordinary room completes free passes first.
"""
from contextlib import asynccontextmanager
import os
from uuid import UUID, uuid4
import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, Request
from gates_brain import enabled, tank_paid


@asynccontextmanager
async def lifespan(app):
    app.state.pool = await asyncpg.create_pool(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    app.state.http = httpx.AsyncClient()
    try:
        yield
    finally:
        await app.state.http.aclose()
        await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.get('/health')
async def health():
    return {'ok': True, 'room': 'tiger', 'enabled': enabled()}


@app.post('/tasks')
async def task(request: Request, tenant_id: UUID, user_id: str):
    if not enabled():
        raise HTTPException(409, 'Tiger brain is off')
    try:
        from chassis.user_assertion import signed_user
    except ImportError:
        raise HTTPException(503, 'Signed-user chassis integration pending') from None
    actor = await signed_user(request, tenant_id=str(tenant_id), product='tiger', required=True)
    if actor.user_id != user_id:
        raise HTTPException(403, 'Actor mismatch')
    body = await request.json()
    if not isinstance(body.get('task_key'), str) or not isinstance(body.get('input'), dict) or not isinstance(body.get('recall'), list):
        raise HTTPException(422, 'Invalid brain task')
    try:
        run_id = str(UUID(str(body.get('run_id') or uuid4())))
    except ValueError:
        raise HTTPException(422, 'Valid run_id required') from None
    # Tank derives the tenant/person/run checkpoint from this signed request.
    try:
        answer, receipt = await tank_paid(app.state.http, actor, run_id, body['task_key'], body['input'], body['recall'])
    except httpx.HTTPStatusError as exc:
        raise HTTPException(exc.response.status_code, 'Tiger task unavailable') from None
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'Tiger task unavailable') from None
    return {'result': answer, 'receipt': receipt}
