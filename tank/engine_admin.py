"""Founder registration for a served trained checkpoint; registration never promotes."""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from command import Actor, identity, require_founder


class Candidate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: uuid.UUID
    task_type: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    checkpoint: str = Field(pattern=r'^[a-f0-9]{64}$')


def build_router(rt):
    router = APIRouter(prefix='/v1/engine', tags=['engine'])

    @router.post('/candidates')
    async def register(body: Candidate, actor: Actor = Depends(identity)):
        require_founder(actor)
        roster = {row['name']: row for row in await rt.list_models()}
        if body.model not in roster or rt.is_build_only_model(body.model):
            raise HTTPException(422, 'Candidate must be on the serving roster')
        await rt.load_policy(body.task_type, body.tenant_id)
        async with rt.pool().acquire() as conn:
            await conn.execute('''INSERT INTO tank.engine_candidates(tenant_id,region,task_type,model,checkpoint)
                VALUES($1,$2,$3,$4,$5) ON CONFLICT(tenant_id,region,task_type,model)
                DO UPDATE SET checkpoint=excluded.checkpoint,created_at=now()''',
                body.tenant_id, rt.box_region(), body.task_type, body.model, body.checkpoint)
        return {'state': 'candidate', 'model': body.model, 'checkpoint': body.checkpoint}

    return router
