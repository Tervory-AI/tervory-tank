"""Signed Base personal memory controls; no request-provided usage or paid calls."""
from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from chassis.user_assertion import signed_user
from base_gates_memory import (MemoryScopeError, require_authenticated_user_id,
                          select_tenant_user_memories, _text_has_secret)

CONTROL_KIND = 'base.quirk'


class Owner(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    user_id: str = Field(min_length=1, max_length=200)


class Forget(Owner):
    memory_id: UUID
    memory_control: Literal['forget'] = 'forget'


class Edit(Owner):
    memory_id: UUID
    text: str = Field(min_length=1, max_length=20000, pattern=r'\S')


class Control(Owner):
    control: Literal['off', 'view', 'edit', 'forget']


def room_session_user(*, tenant_id, user_id):
    try:
        return require_authenticated_user_id(user_id, tenant_id=tenant_id)
    except MemoryScopeError:
        raise HTTPException(401, 'Signed user required for memory') from None


async def actor(request, tenant, user):
    verified = await signed_user(request, tenant_id=str(tenant), product='base', required=True)
    if room_session_user(tenant_id=tenant, user_id=user) != verified.user_id:
        raise HTTPException(403, 'Memory owner mismatch')
    return verified.user_id


def memory_client(app):
    memory = getattr(app.state, 'memory', None)
    if memory is None:
        raise HTTPException(503, 'Base memory is unavailable')
    return memory


async def owned_rows(memory, tenant, user):
    try:
        rows = await memory.records(str(tenant), user_id=user)
    except RuntimeError as exc:
        for status in (401, 403):
            if str(exc) == f'hermes answered {status}':
                raise HTTPException(status, 'Memory access refused') from None
        raise
    return select_tenant_user_memories(rows, tenant_id=str(tenant), user_id=user)


async def invalidate(memory, rows, tenant, user, task_key, *, except_id=None):
    for row in rows:
        if (row['id'] != except_id and row.get('kind') == 'base.receipt'
                and (row.get('meta') or {}).get('task_key') == task_key):
            await memory.forget(row['id'], str(tenant), user_id=user)


def attach_memory_routes(app):
    @app.get('/v1/base/memory')
    async def view(request: Request, tenant_id: UUID, user_id: str, task_key: str = '',
                   memory_control: Literal['off', 'view', 'edit', 'forget'] = 'view'):
        user = await actor(request, tenant_id, user_id)
        rows = [] if memory_control == 'off' else await owned_rows(memory_client(app), tenant_id, user)
        rows = [row for row in rows if not (row.get('meta') or {}).get('base_control')]
        if task_key:
            rows = [row for row in rows if (row.get('meta') or {}).get('task_key') == task_key]
        return dict(tenant_id=str(tenant_id), user_id=user, task_key=task_key,
                    memory_control=memory_control, memories=rows)

    @app.post('/v1/base/memory/edit')
    async def edit(body: Edit, request: Request):
        user = await actor(request, body.tenant_id, body.user_id)
        if _text_has_secret(body.text):
            raise HTTPException(422, 'Private credentials cannot be stored in memory')
        memory = memory_client(app)
        rows = await owned_rows(memory, body.tenant_id, user)
        row = next((r for r in rows if r['id'] == str(body.memory_id)), None)
        if row is None or (row.get('meta') or {}).get('base_control'):
            raise HTTPException(404, 'Memory not found')
        meta = dict(row.get('meta') or {})
        meta.pop('reusable_result', None)
        meta.pop('input_hash', None)
        meta['correction'] = body.text
        meta['invalidated'] = True
        await invalidate(memory, rows, body.tenant_id, user, meta.get('task_key'), except_id=row['id'])
        saved = await memory.remember(str(body.tenant_id), body.text, row['kind'],
            str(row.get('source') or 'base:correction'), user_id=user,
            meta=meta, record_id=str(body.memory_id), replace=True)
        return dict(updated=True, id=saved['id'])

    @app.post('/v1/base/memory/forget')
    async def forget(body: Forget, request: Request):
        user = await actor(request, body.tenant_id, body.user_id)
        memory = memory_client(app)
        rows = await owned_rows(memory, body.tenant_id, user)
        row = next((r for r in rows if r['id'] == str(body.memory_id)), None)
        if row is None or (row.get('meta') or {}).get('base_control'):
            raise HTTPException(404, 'Memory not found')
        await invalidate(memory, rows, body.tenant_id, user, (row.get('meta') or {}).get('task_key'), except_id=row['id'])
        await memory.forget(str(body.memory_id), str(body.tenant_id), user_id=user)
        return dict(forgotten=True, memory_id=str(body.memory_id))

    @app.post('/v1/base/memory/control')
    async def control(body: Control, request: Request):
        user = await actor(request, body.tenant_id, body.user_id)
        memory = memory_client(app)
        rows = await owned_rows(memory, body.tenant_id, user)
        record_id = str(uuid5(NAMESPACE_URL, 'base:control:' + str(body.tenant_id) + ':' + user))
        exists = any(row['id'] == record_id for row in rows)
        await memory.remember(str(body.tenant_id), 'Personal memory preference', CONTROL_KIND,
            'base:control', user_id=user, record_id=record_id, replace=exists, index=False,
            meta={'base_control': body.control})
        return dict(control=body.control, saved=True)

# Preserve the pre-integration test/provider model contract.
RoomSessionUser = Owner
_memory_client = memory_client
