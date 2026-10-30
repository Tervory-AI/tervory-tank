"""One tenant-scoped Radix passive-scan corridor, including Tisan's gate call."""
from __future__ import annotations

import hmac
import os
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field


class Body(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    target: str | None = Field(default=None, max_length=300)
    artifact: str | None = Field(default=None, max_length=80)
    domain: str | None = Field(default=None, max_length=253)


def build_router(tank):
    router = APIRouter(prefix='/v1/radix/passive')

    async def authorize(request: Request, tenant: UUID, operation: str):
        supplied = request.headers.get('x-tank-key', '')
        if request.headers.get('x-tervory-tenant') != str(tenant):
            raise HTTPException(403, 'tenant mismatch')
        region = request.headers.get('x-tervory-region', request.headers.get('x-tervory-home-region'))
        if region != tank.box_region():
            raise HTTPException(403, 'region mismatch')
        room_key = os.environ.get('TANK_KEY_TISAN', '')
        if (operation in {'gate', 'scans'} and supplied and room_key
                and hmac.compare_digest(supplied.encode(), room_key.encode())
                and request.headers.get('x-tervory-squad') == 'tisan'):
            return
        # Workspace may request Radix work only for an enabled tenant/product.
        key = tank.TANK_API_KEY
        if not key or not supplied or not hmac.compare_digest(supplied.encode(), key.encode()):
            raise HTTPException(401, 'authentication required')
        if request.headers.get('x-tervory-squad') != 'radix' or not request.headers.get('x-tervory-user'):
            raise HTTPException(403, 'Radix access required')
        async with tank.pool().acquire() as conn:
            if not await conn.fetchval('SELECT 1 FROM tank.tenant_squad WHERE tenant_id=$1 AND agent=$2', tenant, 'radix'):
                raise HTTPException(403, 'Radix access required')

    async def forward(request, tenant, operation, *, body=None, params=None, method='POST'):
        await authorize(request, tenant, operation.split('/')[0])
        key = os.environ.get('TANK_KEY_RADIX', '')
        if not key or tank._http is None:
            raise HTTPException(503, 'Radix unavailable')
        try:
            response = await tank._http.request(method, 'http://agent-radix:8000/passive/' + operation,
                json=body, params=params, timeout=390 if operation == 'scans' else 15,
                headers={'X-Tank-Key': key, 'X-Tervory-Tenant': str(tenant)}, follow_redirects=False)
            if response.status_code not in {200,201}:
                raise HTTPException(response.status_code if response.status_code in {403,404,409,422} else 503,
                                    'Radix request incomplete')
            return JSONResponse(response.json(), status_code=response.status_code,
                                headers={'Cache-Control': 'private, no-store'})
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'Radix unavailable') from None

    @router.post('/{operation}')
    async def call(operation: str, body: Body, request: Request):
        if operation not in {'domains','scans','gate'}:
            raise HTTPException(404)
        payload = body.model_dump(mode='json', exclude_none=True)
        if (operation == 'domains' and set(payload) != {'tenant_id','domain'}
                or operation != 'domains' and set(payload) != {'tenant_id','target','artifact'}):
            raise HTTPException(422)
        return await forward(request, body.tenant_id, operation, body=payload)

    @router.get('/scans/{scan_id}/findings')
    async def findings(scan_id: UUID, tenant_id: UUID, request: Request):
        return await forward(request, tenant_id, f'scans/{scan_id}/findings',
                             params={'tenant_id': str(tenant_id)}, method='GET')

    return router
