"""Signed planning requests use the room queue and durable worker identity."""
import json
import uuid

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict
from chassis.tenant_db import tenant_path


class PlanJob(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    run_id: uuid.UUID
    brief: dict


async def owner(pool, ctx):
    """Only server-written metadata is identity; generic job inputs are untrusted."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT user_id FROM agent_tisan.job_actors WHERE tenant_id=$1 AND job_id=$2',
                                  uuid.UUID(str(ctx.tenant_id)), uuid.UUID(str(ctx.job_id)))
    ctx.user_id = row['user_id'] if row else None
    return ctx.user_id


def mount(app, founder):
    try:
        from agents.tisan import memory_api, gates_memory, builder
    except ModuleNotFoundError:
        import memory_api
        import gates_memory
        import builder

    async def handle(ctx):
        await owner(app.state.pool, ctx)
        return await builder.execute(ctx.input, str(ctx.tenant_id), tank=ctx.tank,
                                     memory=ctx.memory, user=ctx.user_id, run_id=str(ctx.job_id))

    app.state.handlers['plan'] = handle

    @app.post('/plan/start')
    @tenant_path('body')
    async def start(body: PlanJob, request: Request):
        # Ordinary tasks retain the room/founder guard. A bad/absent assertion
        # cannot gain personal memory; the body never selects an actor.
        founder(request.headers.get('x-tank-key', ''), request.headers.get('x-tervory-admin', ''))
        user = await memory_api.caller(request, body.tenant_id) if gates_memory.brain_enabled() else None
        ident = uuid.uuid5(body.tenant_id, json.dumps([user, str(body.run_id)]))
        payload = json.dumps(body.brief, sort_keys=True, separators=(',', ':'))
        async with app.state.pool.acquire() as conn, conn.transaction():
            await conn.execute("INSERT INTO agent_tisan.jobs(id,tenant_id,kind,input,status,timeout_s,max_attempts) "
                "VALUES($1,$2,'plan',$3::jsonb,'queued',180,3) ON CONFLICT(id) DO NOTHING",
                ident, body.tenant_id, payload)
            row = await conn.fetchrow('SELECT kind,input FROM agent_tisan.jobs WHERE tenant_id=$1 AND id=$2', body.tenant_id, ident)
            stored = json.loads(row['input']) if row and isinstance(row['input'], str) else row['input'] if row else None
            if not row or row['kind'] != 'plan' or stored != body.brief:
                raise HTTPException(409, 'request identity changed')
            await conn.execute('INSERT INTO agent_tisan.job_actors(tenant_id,job_id,user_id) VALUES($1,$2,$3) '
                               'ON CONFLICT DO NOTHING', body.tenant_id, ident, user)
        return {'job_id': str(ident), 'tenant_id': str(body.tenant_id), 'run_id': str(body.run_id)}
