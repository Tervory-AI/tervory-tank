"""Narrow room-only corridor to the existing R5 archive scanner."""
import base64
import hashlib
import hmac
import os
from types import SimpleNamespace
from uuid import UUID
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from tenant_db import tenant_path


class Measurement(BaseModel):
    model_config = ConfigDict(extra='forbid')
    input_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    tokens_in: int = Field(ge=0, le=10000000)
    tokens_out: int = Field(ge=0, le=10000000)


class RunReceipt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    operation_id: UUID
    kind: Literal['ping', 'scaffold', 'figma', 'pipeline', 'build', 'archive']
    measurement: Measurement
    route_ids: list[UUID] = Field(default_factory=list, max_length=100)
    uncertain: bool = False


class Archive(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    source: str = Field(max_length=44_739_248)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


def build_router():
    router = APIRouter(prefix='/pipeline')

    async def authorize(request, tenant):
        import main
        expected = os.environ.get('TANK_KEY_TISAN', '')
        supplied = request.headers.get('x-tank-key', '')
        if (not expected or not supplied or not hmac.compare_digest(expected.encode(), supplied.encode())
                or request.headers.get('x-tervory-tenant') != str(tenant)
                or request.headers.get('x-tervory-region') != main.box_region()):
            raise HTTPException(403, 'not found')

    @router.post('/receipts')
    @tenant_path('body')
    async def receipt(body: RunReceipt, request: Request):
        await authorize(request, body.tenant_id)
        from main import pool
        from agents.tisan.savings import complete
        try:
            async with pool().acquire() as conn:
                measured = await complete(conn, body.tenant_id, body.operation_id, body.kind, {}, {},
                    ids=body.route_ids, uncertain=body.uncertain, measurement=body.measurement.model_dump())
        except ValueError:
            raise HTTPException(409, 'receipt evidence unavailable') from None
        return {'tenant_id': str(body.tenant_id), 'operation_id': str(body.operation_id), 'receipt': measured}

    @router.post('/repo-scan')
    async def scan(body: Archive, request: Request):
        await authorize(request, body.tenant_id)
        try:
            raw = base64.b64decode(body.source, validate=True)
        except ValueError:
            raise HTTPException(422, 'invalid archive') from None
        if (len(raw) > 32 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != body.sha256
                or not (raw.startswith((b'PK\x03\x04', b'\x1f\x8b')) or raw[257:262] == b'ustar')):
            raise HTTPException(422, 'invalid archive')
        from radix_repo import submit
        return await submit(body.tenant_id, raw, 'sha256:' + body.sha256)

    @router.get('/repo-scan/{scan_id}')
    async def read(scan_id: UUID, tenant_id: UUID, request: Request):
        await authorize(request, tenant_id)
        from radix_repo import findings
        return await findings(SimpleNamespace(tenant_id=tenant_id), scan_id)

    return router
