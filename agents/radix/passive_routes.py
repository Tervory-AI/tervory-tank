"""Private passive-scan API. Every execution requires a fresh gateway DNS proof."""
from __future__ import annotations

import asyncio
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, field_validator

from passive_store import DDL, Store, artifact_id, domain_name, target_url
from passive_tools import collect
from verify.routes import require_tank

GATEWAY = 'http://passive-egress:8081'


class Domain(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    domain: str

    @field_validator('domain')
    @classmethod
    def domain_valid(cls, value):
        return domain_name(value)


class Scan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    target: str
    artifact: str

    @field_validator('target')
    @classmethod
    def target_valid(cls, value):
        return target_url(value)[0]

    @field_validator('artifact')
    @classmethod
    def artifact_valid(cls, value):
        return artifact_id(value)


async def execute(store, body: Scan, *, scanner=collect, http=None) -> dict:
    ident = await store.create(body.tenant_id, body.target, body.artifact)
    lease = {'tenant_id': str(body.tenant_id), 'scan_id': str(ident)}
    async with httpx.AsyncClient(trust_env=False, timeout=15) if http is None else http as client:
        try:
            async with asyncio.timeout(360):
                response = await client.post(GATEWAY + '/lease', json=lease)
                if response.status_code != 200 or response.json().get('ready') is not True:
                    raise HTTPException(403 if response.status_code == 403 else 503, 'scan not authorized')
                with tempfile.TemporaryDirectory(prefix='radix-passive-') as directory:
                    findings = await scanner(body.target, Path(directory))
                await store.complete(body.tenant_id, ident, findings)
                result = await store.gate(body.tenant_id, body.target, body.artifact)
                if result.get('scan_id') != str(ident):
                    raise RuntimeError('assessment superseded')
                return {**result, 'findings': findings}
        except BaseException:
            await asyncio.shield(store.fail(body.tenant_id, ident))
            raise
        finally:
            try:
                await asyncio.shield(client.post(GATEWAY + '/release', json=lease))
            except Exception:
                # Gateway deadline closes old tunnels independently; never declare success here.
                pass


def attach(app):
    router = APIRouter(prefix='/passive', dependencies=[Depends(require_tank)])

    def identity(request, tenant):
        if request.headers.get('x-tervory-tenant') != str(tenant):
            raise HTTPException(403, 'tenant mismatch')

    @router.post('/domains', status_code=201)
    async def issue(body: Domain, request: Request):
        identity(request, body.tenant_id)
        return await Store(app.state.pool).issue(body.tenant_id, body.domain)

    @router.post('/scans')
    async def scan(body: Scan, request: Request):
        identity(request, body.tenant_id)
        try:
            return await execute(Store(app.state.pool), body)
        except PermissionError:
            raise HTTPException(403, 'domain proof required') from None
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, 'passive scan incomplete') from None

    @router.post('/gate')
    async def gate(body: Scan, request: Request):
        identity(request, body.tenant_id)
        return await Store(app.state.pool).gate(body.tenant_id, body.target, body.artifact)

    @router.get('/scans/{scan_id}/findings')
    async def findings(scan_id: UUID, tenant_id: UUID, request: Request):
        identity(request, tenant_id)
        return {'findings': await Store(app.state.pool).findings(tenant_id, scan_id)}

    app.include_router(router)
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(app):
        async with inner(app):
            async with app.state.pool.acquire() as conn:
                await conn.execute(DDL)
            yield

    app.router.lifespan_context = lifespan
