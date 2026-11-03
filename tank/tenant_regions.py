"""C1/N1: founder-owned tenant home; content is accepted only on its home box."""
from __future__ import annotations

from typing import Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from gold import PLATFORM_TENANT, require_reviewer
from pydantic import BaseModel
from tenant_db import tenant_scope


class Onboarding(BaseModel):
    home_region: Literal['us-east', 'za']


async def home(tank, tenant: UUID) -> str:
    if tenant == PLATFORM_TENANT:
        return tank.box_region()
    with tenant_scope(tenant):
        async with tank.pool().acquire() as conn:
            value = await conn.fetchval('SELECT home_region FROM tank.tenants WHERE tenant_id=$1', tenant)
    if value not in ('us-east', 'za'):
        raise HTTPException(409, {'code': 'tenant_onboarding_required'})
    return value


async def local(tank, tenant: UUID, claimed=None):
    region = await home(tank, tenant)
    if claimed is not None and claimed != region:
        raise HTTPException(403, 'The request home differs from the tenant record.')
    if region != tank.box_region():
        raise HTTPException(403, {'code': 'tenant_home_region', 'home_region': region})
    return region


def install(app, tank):
    @app.get('/v1/tenants/{tenant_id}', dependencies=[Depends(tank.require_key)])
    async def get_home(tenant_id: UUID):
        return {'tenant_id': str(tenant_id), 'home_region': await home(tank, tenant_id)}

    @app.put('/v1/tenants/{tenant_id}')
    async def onboard(tenant_id: UUID, body: Onboarding, actor=Depends(require_reviewer)):  # noqa: B008
        if not actor.founder or actor.tenant != tenant_id or tenant_id == PLATFORM_TENANT:
            raise HTTPException(404, 'not found')
        with tenant_scope(tenant_id):
            async with tank.pool().acquire() as conn:
                await conn.execute('''INSERT INTO tank.tenants(tenant_id,home_region,onboarded_by)
                    VALUES($1,$2,$3) ON CONFLICT(tenant_id) DO NOTHING''', tenant_id, body.home_region, actor.user)
        region = await home(tank, tenant_id)
        if region != body.home_region:
            raise HTTPException(409, 'A tenant home cannot be changed by onboarding. A separate data migration is required.')
        return {'tenant_id': str(tenant_id), 'home_region': region}
