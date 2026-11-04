"""Deployment-owned Trigger sign-in resource registry; no user provisioning by Tank."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
import os
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from tenant_db import tenant_scope

ISSUERS = {'us-east': 'https://auth.tervory.com', 'za': 'https://auth-za.tervory.com'}
PLATFORM = uuid.UUID('00000000-0000-0000-0000-000000000001')
_records: dict[str, dict] = {}
_expires = 0.0
_lock = asyncio.Lock()
_issuer: ContextVar[str] = ContextVar('trigger_signin_issuer', default='')
proof: ContextVar[dict[str, str]] = ContextVar('trigger_signin_proof', default={})


def setup_authorized(request: Request) -> bool:
    from command import key_matches
    return key_matches(request.headers.get('x-trigger-signin-setup', ''), os.environ.get('TRIGGER_SIGNIN_SETUP_TOKEN', ''))


async def require_setup(request: Request):
    if not setup_authorized(request):
        raise HTTPException(404, 'not found')


def config(region: str) -> dict:
    record = _records.get(region)
    if record is None:
        raise HTTPException(503, 'Trigger sign-in setup is incomplete')
    return record


def founders() -> set[str]:
    issuer = _issuer.get()
    return {subject for record in _records.values() if record['issuer'] == issuer for subject in record['founders']}


async def refresh(*, force: bool = False):
    global _records, _expires
    if not force and _expires > time.monotonic():
        return
    async with _lock:
        if not force and _expires > time.monotonic():
            return
        from command import db
        with tenant_scope(PLATFORM, administrative=True):
            async with db().acquire() as conn:
                rows = await conn.fetch('SELECT region,issuer,client_id,workspace_client_id,project_id FROM tank.trigger_signin_config')
                bindings = await conn.fetch('SELECT region,org_id,tenant_id FROM tank.trigger_signin_organisations')
                owners = await conn.fetch('SELECT region,subject FROM tank.trigger_signin_founders')
        records = {}
        for row in rows:
            record = dict(row)
            record['organisations'] = {binding['org_id']: str(binding['tenant_id']) for binding in bindings if binding['region'] == row['region']}
            record['founders'] = [owner['subject'] for owner in owners if owner['region'] == row['region']]
            records[row['region']] = record
        _records, _expires = records, time.monotonic() + 30


class Binding(BaseModel):
    model_config = ConfigDict(extra='forbid')
    org_id: str = Field(pattern=r'^\d{1,30}$')
    tenant_id: uuid.UUID


class Deployment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    region: str
    issuer: str
    client_id: str = Field(pattern=r'^[A-Za-z0-9@._-]{1,200}$')
    workspace_client_id: str = Field(pattern=r'^[A-Za-z0-9@._-]{1,200}$')
    project_id: str = Field(pattern=r'^\d{1,30}$')
    founder_subject: str = Field(pattern=r'^[A-Za-z0-9_-]{1,200}$')
    organisations: list[Binding] = Field(max_length=10000)


router = APIRouter(prefix='/v1/trigger-signin', include_in_schema=False)


@router.get('/config')
async def read_config(request: Request, response: Response):
    from command import key_matches
    from main import TANK_API_KEY
    if not setup_authorized(request) and not key_matches(request.headers.get('x-tank-key', ''), TANK_API_KEY):
        raise HTTPException(404, 'not found')
    await refresh()
    response.headers['Cache-Control'] = 'private, no-store'
    return {'regions': _records}


@router.put('/config', dependencies=[Depends(require_setup)])
async def write_config(body: Deployment):
    if ISSUERS.get(body.region) != body.issuer:
        raise HTTPException(422, 'Trigger sign-in region refused')
    organisations = {binding.org_id: binding.tenant_id for binding in body.organisations}
    if len(organisations) != len(body.organisations) or len(set(organisations.values())) != len(organisations):
        raise HTTPException(422, 'Trigger sign-in organisations refused')
    from command import db
    with tenant_scope(PLATFORM, administrative=True):
        async with db().acquire() as conn, conn.transaction():
            await conn.execute('SELECT pg_advisory_xact_lock(72451301)')
            current = await conn.fetchrow('SELECT * FROM tank.trigger_signin_config WHERE region=$1 FOR UPDATE', body.region)
            if current and any(current[name] != getattr(body, name) for name in ('issuer', 'client_id', 'workspace_client_id', 'project_id')):
                raise HTTPException(409, 'Trigger sign-in resources are already bound')
            await conn.execute('''INSERT INTO tank.trigger_signin_config(region,issuer,client_id,workspace_client_id,project_id)
                VALUES($1,$2,$3,$4,$5) ON CONFLICT DO NOTHING''', body.region, body.issuer, body.client_id, body.workspace_client_id, body.project_id)
            for org_id, tenant in organisations.items():
                if not await conn.fetchval('SELECT EXISTS(SELECT 1 FROM tank.case_study_clients WHERE tenant_id=$1)', tenant):
                    raise HTTPException(422, 'Trigger sign-in tenant does not exist')
                existing = await conn.fetchrow('SELECT org_id,tenant_id FROM tank.trigger_signin_organisations WHERE region=$1 AND (org_id=$2 OR tenant_id=$3)', body.region, org_id, tenant)
                if existing and (existing['org_id'] != org_id or existing['tenant_id'] != tenant):
                    raise HTTPException(409, 'Trigger sign-in tenant is already bound')
                await conn.execute('''INSERT INTO tank.trigger_signin_organisations(region,org_id,tenant_id)
                    VALUES($1,$2,$3) ON CONFLICT DO NOTHING''', body.region, org_id, tenant)
            existing_founder = await conn.fetchval('SELECT subject FROM tank.trigger_signin_founders WHERE region=$1', body.region)
            if existing_founder and existing_founder != body.founder_subject:
                raise HTTPException(409, 'Trigger sign-in founder is already bound')
            await conn.execute('INSERT INTO tank.trigger_signin_founders(region,subject) VALUES($1,$2) ON CONFLICT DO NOTHING', body.region, body.founder_subject)
    await refresh(force=True)
    return {'configured': True}
