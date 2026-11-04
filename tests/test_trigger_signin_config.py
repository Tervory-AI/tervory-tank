import sys

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import command
import trigger_signin_config as registry
from test_command import command_pool as command_pool_fixture, runtime as runtime_fixture, TENANT

command_pool = command_pool_fixture
runtime = runtime_fixture
registry_refresh = registry.refresh


@pytest_asyncio.fixture
async def registry_client(monkeypatch, command_pool, runtime):
    monkeypatch.setattr(command, 'db', lambda: command_pool)
    monkeypatch.setenv('TRIGGER_SIGNIN_SETUP_TOKEN', 'offline-setup-only')
    monkeypatch.setattr(registry, '_records', {})
    monkeypatch.setattr(registry, '_expires', 0.0)
    monkeypatch.setattr(registry, 'refresh', registry_refresh)
    async with command_pool.acquire() as conn:
        await conn.execute('INSERT INTO tank.case_study_clients(tenant_id) VALUES($1) ON CONFLICT DO NOTHING', TENANT)
    app = FastAPI()
    app.include_router(registry.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        yield client


def deployment(region='us-east'):
    return {'region': region, 'issuer': registry.ISSUERS[region], 'client_id': '30001@tervory',
            'workspace_client_id': '30002@tervory', 'project_id': '40001', 'founder_subject': '50001',
            'organisations': [{'org_id': '60001', 'tenant_id': str(TENANT)}]}


@pytest.mark.asyncio
async def test_only_setup_can_bind_existing_tenants_and_native_founder(registry_client):
    client = registry_client
    payload = deployment()
    setup = {'x-trigger-signin-setup': 'offline-setup-only'}
    key = sys.modules['main'].TANK_API_KEY
    for headers in [{}, {'x-tank-key': key}, {'x-trigger-signin-setup': 'wrong'}]:
        assert (await client.put('/v1/trigger-signin/config', json=payload, headers=headers)).status_code == 404
    assert (await client.put('/v1/trigger-signin/config', json=payload, headers=setup)).status_code == 200
    assert (await client.put('/v1/trigger-signin/config', json=payload, headers=setup)).status_code == 200
    assert (await client.get('/v1/trigger-signin/config')).status_code == 404
    response = await client.get('/v1/trigger-signin/config', headers={'x-tank-key': key})
    record = response.json()['regions']['us-east']
    assert record['organisations'] == {'60001': str(TENANT)}
    assert record['founders'] == ['50001']
    assert record['workspace_client_id'] == '30002@tervory'
    assert response.headers['cache-control'] == 'private, no-store'
    assert 'offline-setup-only' not in response.text
    for change in [{'client_id': 'different-client'}, {'founder_subject': 'changed-subject'},
                   {'organisations': [{'org_id': '70001', 'tenant_id': str(TENANT)}]}]:
        assert (await client.put('/v1/trigger-signin/config', json={**payload, **change}, headers=setup)).status_code == 409


@pytest.mark.asyncio
async def test_registry_never_creates_or_invents_tenants(registry_client):
    response = await registry_client.put('/v1/trigger-signin/config', json={**deployment(), 'organisations': [
        {'org_id': '60001', 'tenant_id': '00000000-0000-4000-8000-000000000099'}]},
        headers={'x-trigger-signin-setup': 'offline-setup-only'})
    assert response.status_code == 422
    assert registry._records == {}


def test_founder_subjects_are_bound_to_verified_issuer(monkeypatch):
    monkeypatch.setattr(registry, '_records', {'us-east': {'issuer': registry.ISSUERS['us-east'], 'founders': ['50001']},
                                             'za': {'issuer': registry.ISSUERS['za'], 'founders': ['80001']}})
    context = registry._issuer.set('')
    try:
        assert registry.founders() == set()
        registry._issuer.set(registry.ISSUERS['us-east'])
        assert registry.founders() == {'50001'}
        registry._issuer.set(registry.ISSUERS['za'])
        assert registry.founders() == {'80001'}
    finally:
        registry._issuer.reset(context)


@pytest.mark.asyncio
async def test_setup_read_requires_capability_not_a_native_subject_name(monkeypatch):
    from unittest.mock import AsyncMock
    from starlette.requests import Request
    import case_studies
    from command import Actor
    monkeypatch.setenv('TRIGGER_SIGNIN_SETUP_TOKEN', 'offline-setup-only')
    claimed = Actor(TENANT, 'trigger-signin-setup', False)
    monkeypatch.setattr(case_studies, 'identity', AsyncMock(return_value=claimed))
    def request(value=''):
        return Request({'type': 'http', 'headers': [(b'x-trigger-signin-setup', value.encode())]})
    assert await case_studies.tenant_listing_identity(request()) is claimed
    assert claimed is not case_studies._SETUP_TENANT_READER
    assert await case_studies.tenant_listing_identity(request('wrong')) is claimed
    assert await case_studies.tenant_listing_identity(request('offline-setup-only')) is case_studies._SETUP_TENANT_READER
