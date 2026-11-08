"""Savings endpoints authenticate before acquiring a tenant-bound connection."""
from contextlib import asynccontextmanager
import importlib
from types import SimpleNamespace
from uuid import UUID

from fastapi import FastAPI
import httpx
import pytest

import tenant_db
import tiger_savings

TENANT = UUID('11111111-1111-4111-8111-111111111111')
OTHER = UUID('22222222-2222-4222-8222-222222222222')


@pytest.fixture
def savings_app(monkeypatch):
    tank = importlib.import_module('main')
    acquired = []

    @asynccontextmanager
    async def transaction():
        yield

    @asynccontextmanager
    async def acquire():
        # This is the scope TenantPool copies into SET LOCAL for real SQL.
        assert tenant_db._tenant.get() == str(TENANT)
        assert not tenant_db.administrative()
        acquired.append(str(TENANT))
        yield SimpleNamespace(transaction=transaction)

    async def record(conn, body):
        assert body.tenant_id == TENANT
        return {'tenant_id': str(body.tenant_id), 'action': body.action}

    async def listed(conn, tenant):
        assert tenant == TENANT
        return [{'tenant_id': str(tenant)}]

    monkeypatch.setattr(tank, 'pool', lambda: SimpleNamespace(acquire=acquire))
    monkeypatch.setattr(tank, '_agent_keys_synced', True)
    monkeypatch.setattr(tank, 'TANK_API_KEY', 'placeholder-workspace-key')
    monkeypatch.setenv('TANK_KEY_TIGER', 'placeholder-tiger-key')
    monkeypatch.setattr(tiger_savings, 'record', record)
    monkeypatch.setattr(tiger_savings, 'listed', listed)
    app = FastAPI()
    app.include_router(tiger_savings.build_router(tank))
    tenant_db.bind_tenant_endpoints(app)
    app.add_middleware(tenant_db.TenantContextMiddleware)
    return app, acquired


@pytest.mark.asyncio
@pytest.mark.parametrize('method,key', [('POST', 'placeholder-tiger-key'), ('GET', 'placeholder-workspace-key')])
async def test_validated_tenant_reaches_transaction_and_scope_is_reset(savings_app, method, key):
    app, acquired = savings_app
    body = {'tenant_id': str(TENANT), 'id': str(OTHER), 'action': 'tiger.placeholder', 'input': {}, 'output': {}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder.invalid') as client:
        response = await client.request(method, '/v1/tiger/savings', params={'tenant_id': str(TENANT)},
                                        headers={'x-tank-key': key}, json=body if method == 'POST' else None)
    assert response.status_code == 200
    assert acquired == [str(TENANT)]
    assert tenant_db._tenant.get() == ''


@pytest.mark.asyncio
@pytest.mark.parametrize('method,key,mismatch,status', [
    ('POST', '', False, 401), ('GET', '', False, 401),
    ('POST', 'placeholder-workspace-key', False, 403),
    ('GET', 'placeholder-tiger-key', False, 403),
    ('POST', 'placeholder-tiger-key', True, 403),
    ('GET', 'placeholder-workspace-key', True, 403),
])
async def test_unauthorized_or_conflicting_tenant_never_acquires(savings_app, method, key, mismatch, status):
    app, acquired = savings_app
    headers = {'x-tank-key': key}
    if mismatch:
        headers['x-tenant-id'] = str(OTHER)
    body = {'tenant_id': str(TENANT), 'id': str(OTHER), 'action': 'tiger.placeholder', 'input': {}, 'output': {}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder.invalid') as client:
        response = await client.request(method, '/v1/tiger/savings', params={'tenant_id': str(TENANT)},
                                        headers=headers, json=body if method == 'POST' else None)
    assert response.status_code == status
    assert acquired == []
