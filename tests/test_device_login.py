"""Trigger sign-in only: native device flow, token provenance and regional refusal."""
import uuid

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import command
import identity_oidc as oidc
import personal_tokens as pat
from test_command import command_pool, runtime, TENANT  # noqa: F401
from trigger_signin_fakes import Provider, CLIENT, ORG, install_registry


@pytest_asyncio.fixture
async def device(runtime, monkeypatch, command_pool):  # noqa: F811
    monkeypatch.setattr(command, 'db', lambda: command_pool)
    app = FastAPI()
    app.include_router(command.router)
    pat.register(app)
    app.dependency_overrides[command.identity] = pat.identity
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://fixture') as client:
        yield client, command_pool, runtime


@pytest.fixture(params=['us-east', 'za'])
def signin_provider(monkeypatch, runtime, request):  # noqa: F811
    provider = Provider(request.param)
    install_registry(monkeypatch, [provider], {ORG: str(TENANT)})
    runtime.box_region = lambda: provider.region
    oidc._cache.clear()
    monkeypatch.setenv('TRIGGER_SIGNIN_ISSUER', provider.issuer)
    monkeypatch.setenv('TRIGGER_SIGNIN_CLIENT_ID', CLIENT)
    monkeypatch.setattr(oidc, 'http_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    yield provider
    oidc._cache.clear()


@pytest.mark.asyncio
async def test_legacy_credential_cannot_authenticate_or_refresh(device, signin_provider):
    client, pool, _ = device
    region = signin_provider.region
    secret = 'a' * 43
    token = f'tv1.{region}.{TENANT.hex}.{secret}'
    refresh = f'tvr1.{region}.{TENANT.hex}.{secret}'
    async with pool.acquire() as connection:
        await connection.execute(
            "INSERT INTO tank.personal_tokens(tenant_id,user_id,region,name,token_hash,refresh_hash,refresh_expires_at) "
            "VALUES($1,'old-subject',$2,'old sign-in',$3,$4,now()+interval '1 day')",
            TENANT, region, pat.digest(token), pat.digest(refresh))
    assert (await client.get('/v1/command/tools', headers={'authorization': 'Bearer ' + token})).status_code == 401
    result = await client.post('/v1/command/device/refresh', json={'refresh_token': refresh})
    assert result.status_code == 400 and result.json() == {'error': 'invalid_grant'}


@pytest.mark.asyncio
async def test_native_grant_logout_and_region_boundary(device, signin_provider):
    client, pool, box_runtime = device
    start = await client.post('/v1/command/device/code', json={'device_name': 'synthetic'})
    assert start.status_code == 200
    assert start.json()['verification_uri'].startswith(signin_provider.issuer + '/')
    result = await client.post('/v1/command/device/token', json={'device_code': start.json()['device_code']})
    assert result.status_code == 200
    grant = result.json()
    async with pool.acquire() as connection:
        assert await connection.fetchval('SELECT trigger_signin FROM tank.personal_tokens') is True
    headers = {'authorization': 'Bearer ' + grant['access_token']}
    assert (await client.get('/v1/command/tools', headers=headers)).status_code == 200
    original = box_runtime.box_region
    box_runtime.box_region = lambda: 'za' if signin_provider.region == 'us-east' else 'us-east'
    assert (await client.get('/v1/command/tools', headers=headers)).status_code == 403
    box_runtime.box_region = original
    assert (await client.post('/v1/command/device/revoke', json={'refresh_token': grant['refresh_token']})).status_code == 200
    assert (await client.get('/v1/command/tools', headers=headers)).status_code == 401


@pytest.mark.asyncio
async def test_legacy_device_codes_and_approval_requests_are_refused(device, signin_provider):
    client, _, _ = device
    legacy = 'tvd1.' + signin_provider.region + '.' + 'a' * 43
    result = await client.post('/v1/command/device/token', json={'device_code': legacy})
    assert result.status_code == 400 and result.json() == {'error': 'invalid_grant'}
    assert (await client.post('/v1/command/device/code', json={'device_name': 'synthetic', 'approval': 'workspace'})).status_code == 422
    assert (await client.post('/v1/command/device/code', json={'device_name': 'synthetic', 'tenant_id': str(uuid.uuid4())})).status_code == 422


def test_device_schema_is_additive_and_hash_only():
    from pathlib import Path
    schema = Path('tank/schema.sql').read_text()
    assert 'ADD COLUMN IF NOT EXISTS trigger_signin boolean NOT NULL DEFAULT false' in schema
    assert 'device_hash text PRIMARY KEY' in schema
    assert 'refresh_hash text' in schema
