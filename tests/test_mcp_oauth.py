"""OAuth G1 against disposable Postgres; synthetic credentials, no outside I/O."""
import asyncio
import base64
import hashlib
import json
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

import command
import mcp_oauth as oauth
import mcp_server
import personal_tokens as pat
from test_command import command_pool, runtime, TENANT, OTHER  # noqa: F401

WORKSPACE = {'x-tank-key': 'dummy-workspace-key', 'x-tervory-tenant': str(TENANT), 'x-tervory-user': 'client'}
VERIFIER = 'v' * 43
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip('=')


@pytest_asyncio.fixture
async def mcp_api(runtime, monkeypatch, command_pool):  # noqa: F811
    monkeypatch.setattr(command, 'db', lambda: command_pool)
    oauth._metadata.clear()
    public_get = AsyncMock(side_effect=AssertionError('No external client fetch in this test'))
    monkeypatch.setattr(oauth.access, 'public_get', public_get)
    app = FastAPI()
    app.include_router(command.router)
    pat.register(app)
    mcp_server.register(app)
    runtime.app = app
    runtime.pool = lambda: command_pool
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='https://app.tervory.com') as client:
        yield client, command_pool, runtime, public_get
    if mcp_server._background:
        await asyncio.gather(*mcp_server._background)


async def registration(client, **override):
    response = await client.post('/oauth/register', json={'client_name': 'Offline client',
        'redirect_uris': ['https://client.example/callback'], **override})
    assert response.status_code == 201, response.text
    return response.json()


def authorization(client_id, **override):
    return {'response_type': 'code', 'client_id': client_id, 'redirect_uri': 'https://client.example/callback',
            'state': 'synthetic-state', 'code_challenge': CHALLENGE, 'code_challenge_method': 'S256',
            'resource': oauth.RESOURCE, **override}


async def approved(client, registered=None, headers=WORKSPACE):
    registered = registered or await registration(client)
    args = authorization(registered['client_id'])
    shown = await client.get('/oauth/authorize', params=args, headers=headers)
    assert shown.status_code == 200, shown.text
    decided = await client.post('/oauth/authorize', json={**args, 'action': 'approve'}, headers=headers)
    assert decided.status_code == 200, decided.text
    query = parse_qs(urlsplit(decided.json()['redirect_to']).query)
    assert query['iss'] == [oauth.ISSUER] and query['state'] == ['synthetic-state']
    return args, query['code'][0]


async def exchange(client, args, code, **override):
    return await client.post('/oauth/token', data={'grant_type': 'authorization_code',
        'client_id': args['client_id'], 'redirect_uri': args['redirect_uri'], 'resource': oauth.RESOURCE,
        'code': code, 'code_verifier': VERIFIER, **override})


async def issued(client, headers=WORKSPACE):
    args, code = await approved(client, headers=headers)
    response = await exchange(client, args, code)
    assert response.status_code == 200, response.text
    return args, response.json()


@pytest.mark.asyncio
async def test_discovery_exact_resource_metadata_and_unauthorized_challenge(mcp_api):
    client, _, _, _ = mcp_api
    for path in ['/.well-known/oauth-protected-resource', '/.well-known/oauth-protected-resource/mcp']:
        response = await client.get(path)
        assert response.json() == {'resource': oauth.RESOURCE, 'authorization_servers': [oauth.ISSUER], 'bearer_methods_supported': ['header']}
    metadata = (await client.get('/.well-known/oauth-authorization-server')).json()
    assert metadata['issuer'] == oauth.ISSUER
    assert metadata['code_challenge_methods_supported'] == ['S256']
    assert metadata['grant_types_supported'] == ['authorization_code', 'refresh_token']
    assert metadata['token_endpoint_auth_methods_supported'] == ['none']
    assert metadata['client_id_metadata_document_supported'] is True
    response = await client.post('/mcp', json={})
    assert response.status_code == 401
    assert response.headers['www-authenticate'] == f'Bearer resource_metadata="{oauth.PROTECTED_METADATA}"'


@pytest.mark.asyncio
async def test_cimd_exact_identity_redirect_size_cache_and_public_get(mcp_api, monkeypatch):
    client, _, _, fetch = mcp_api
    client_id = 'https://client.example/oauth/metadata.json'
    metadata = {'client_id': client_id, 'client_name': 'CIMD client', 'redirect_uris': ['https://client.example/callback']}
    fetch.side_effect = None; fetch.return_value = (json.dumps(metadata).encode(), {'cache-control': 'max-age=172800'})
    args = authorization(client_id)
    assert (await client.get('/oauth/authorize', params=args, headers=WORKSPACE)).status_code == 200
    assert (await client.get('/oauth/authorize', params=args, headers=WORKSPACE)).status_code == 200
    fetch.assert_awaited_once_with(client_id, limit=65536)
    assert next(iter(oauth._metadata.values()))[0] <= oauth.time.monotonic() + 86400
    response = await client.get('/oauth/authorize', params={**args, 'redirect_uri': 'https://attacker.example/'}, headers=WORKSPACE)
    assert response.status_code == 400 and 'location' not in response.headers
    oauth._metadata.clear(); fetch.return_value = (json.dumps({**metadata, 'client_id': 'https://other.example/metadata'}).encode(), {})
    assert (await client.get('/oauth/authorize', params=args, headers=WORKSPACE)).status_code == 400
    oauth._metadata.clear(); fetch.return_value = (b' ' * 65537, {})
    assert (await client.get('/oauth/authorize', params=args, headers=WORKSPACE)).status_code == 400
    oauth._metadata.clear(); fetch.return_value = (json.dumps(metadata).encode(), {'cache-control': 'no-store'})
    assert (await client.get('/oauth/authorize', params=args, headers=WORKSPACE)).status_code == 200
    assert not oauth._metadata
    fetch.reset_mock()
    response = await client.get('/oauth/authorize', params={**args, 'client_id': 'http://127.0.0.1/metadata'}, headers=WORKSPACE)
    assert response.status_code == 400
    fetch.assert_not_awaited()


@pytest.mark.parametrize('redirect', ['http://evil.example/cb', 'https://user:pass@client.example/cb', 'javascript:alert(1)', 'https://client.example/cb#fragment', 'https://client.example/\ncb'])
@pytest.mark.asyncio
async def test_dcr_rejects_unsafe_redirects(mcp_api, redirect):
    client, _, _, _ = mcp_api
    response = await client.post('/oauth/register', json={'client_name': 'Offline', 'redirect_uris': [redirect]})
    assert response.status_code == 400


@pytest.mark.parametrize('redirect', ['https://client.example/callback', 'http://127.0.0.1:6543/callback', 'http://localhost:6543/callback'])
@pytest.mark.asyncio
async def test_dcr_allows_https_and_only_http_loopback(mcp_api, redirect):
    client, _, _, _ = mcp_api
    registered = await registration(client, redirect_uris=[redirect])
    assert registered['redirect_uris'] == [redirect] and registered['token_endpoint_auth_method'] == 'none'
    assert 'client_secret' not in registered


@pytest.mark.asyncio
async def test_dcr_name_auth_method_and_source_rate_limit(mcp_api):
    client, pool, _, _ = mcp_api
    for patch in [{'client_name': 'x' * 101}, {'token_endpoint_auth_method': 'client_secret_basic'}]:
        response = await client.post('/oauth/register', json={'client_name': 'Offline', 'redirect_uris': ['https://client.example/cb'], **patch})
        assert response.status_code == 400
    await registration(client)
    async with pool.acquire() as conn:
        source = await conn.fetchval('SELECT source_address_hash FROM tank.oauth_clients LIMIT 1')
        await conn.execute("INSERT INTO tank.oauth_clients(client_id,client_name,redirect_uris,source_address_hash) SELECT 'tvc_'||md5(i::text),'Offline','[\"https://client.example/callback\"]'::jsonb,$1 FROM generate_series(1,49) i", source)
    assert (await client.post('/oauth/register', json={'client_name': 'Offline', 'redirect_uris': ['https://client.example/cb']})).status_code == 429


@pytest.mark.asyncio
async def test_pkce_wrong_verifier_replay_expiry_and_hash_only(mcp_api):
    client, pool, _, _ = mcp_api
    args, code = await approved(client)
    wrong = await exchange(client, args, code, code_verifier='w' * 43)
    assert wrong.json() == {'error': 'invalid_grant'}
    responses = await asyncio.gather(exchange(client, args, code), exchange(client, args, code))
    assert sorted(r.status_code for r in responses) == [200, 400]
    grant = next(r.json() for r in responses if r.status_code == 200)
    assert grant['expires_in'] == 3600 and grant['refresh_expires_in'] == 30 * 86400
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.personal_tokens')
        stored_code = await conn.fetchrow('SELECT * FROM tank.oauth_codes')
    assert row['audience'] == 'mcp' and row['client_id'] == args['client_id'] and row['name'] == 'Offline client'
    assert row['token_hash'] == pat.digest(grant['access_token'])
    assert row['refresh_hash'] == pat.digest(grant['refresh_token'])
    stored = repr(dict(row)) + repr(dict(stored_code))
    assert all(token not in stored for token in (code, grant['access_token'], grant['refresh_token']))
    args, expired = await approved(client)
    async with pool.acquire() as conn:
        await conn.execute("UPDATE tank.oauth_codes SET expires_at=now()-interval '1 second' WHERE code_hash=$1", pat.digest(expired))
    assert (await exchange(client, args, expired)).json() == {'error': 'invalid_grant'}


@pytest.mark.asyncio
async def test_authorization_requires_workspace_and_exact_request_and_deny(mcp_api):
    client, pool, _, _ = mcp_api
    registered = await registration(client)
    args = authorization(registered['client_id'])
    assert (await client.get('/oauth/authorize', params=args)).status_code == 401
    for patch in [{'redirect_uri': 'https://evil.example/cb'}, {'code_challenge_method': 'plain'}, {'response_type': 'token'}, {'resource': 'https://evil.example/'}]:
        response = await client.get('/oauth/authorize', params={**args, **patch}, headers=WORKSPACE)
        assert response.status_code == 400 and 'location' not in response.headers
    duplicate = await client.get('/oauth/authorize', params=list(args.items()) + [('client_id', args['client_id'])], headers=WORKSPACE)
    assert duplicate.status_code == 400
    denied = await client.post('/oauth/authorize', json={**args, 'action': 'deny'}, headers=WORKSPACE)
    assert parse_qs(urlsplit(denied.json()['redirect_to']).query)['error'] == ['access_denied']
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.oauth_codes') == 0


@pytest.mark.asyncio
async def test_code_client_redirect_resource_and_tenant_binding(mcp_api):
    client, _, _, _ = mcp_api
    args, code = await approved(client)
    other = await registration(client, client_name='Other client')
    for patch in [{'client_id': other['client_id']}, {'redirect_uri': 'https://evil.example/cb'}]:
        assert (await exchange(client, args, code, **patch)).json() == {'error': 'invalid_grant'}
    assert (await exchange(client, args, code, resource='https://evil.example/')).json() == {'error': 'invalid_target'}
    foreign = code.replace(TENANT.hex, OTHER.hex)
    assert (await exchange(client, args, foreign)).json() == {'error': 'invalid_grant'}
    assert (await exchange(client, args, code)).status_code == 200


@pytest.mark.asyncio
async def test_refresh_rotation_reuse_client_binding_and_cli_separation(mcp_api):
    client, _, _, _ = mcp_api
    args, grant = await issued(client)
    refresh = {'grant_type': 'refresh_token', 'client_id': args['client_id'], 'resource': oauth.RESOURCE, 'refresh_token': grant['refresh_token']}
    assert (await client.post('/v1/command/device/refresh', json={'refresh_token': grant['refresh_token']})).json() == {'error': 'invalid_grant'}
    other = await registration(client)
    assert (await client.post('/oauth/token', data={**refresh, 'client_id': other['client_id']})).json() == {'error': 'invalid_grant'}
    rotated = await client.post('/oauth/token', data=refresh)
    assert rotated.status_code == 200
    assert (await client.post('/oauth/token', data=refresh)).json() == {'error': 'invalid_grant'}
    assert (await client.post('/mcp', headers={'authorization': 'Bearer ' + grant['access_token']}, json={})).status_code == 401
    assert (await client.get('/v1/command/tools', headers={'authorization': 'Bearer ' + rotated.json()['access_token']})).status_code == 401
    listed = (await client.get('/v1/personal-tokens', headers=WORKSPACE)).json()
    assert listed[0]['name'] == 'Offline client'
    cli = await client.post('/v1/personal-tokens', json={'name': 'Existing CLI'}, headers=WORKSPACE)
    assert cli.status_code == 201
    assert (await client.post('/mcp', headers={'authorization': 'Bearer ' + cli.json()['token']}, json={})).status_code == 401


@pytest.mark.asyncio
async def test_revoke_and_existing_sign_in_page_revocation_stop_immediately(mcp_api):
    client, _, _, _ = mcp_api
    args, grant = await issued(client)
    response = await client.post('/oauth/revoke', data={'client_id': args['client_id'], 'token': grant['refresh_token']})
    assert response.status_code == 200
    assert (await client.post('/mcp', headers={'authorization': 'Bearer ' + grant['access_token']}, json={})).status_code == 401
    assert (await client.post('/oauth/token', data={'grant_type': 'refresh_token', 'resource': oauth.RESOURCE, 'client_id': args['client_id'], 'refresh_token': grant['refresh_token']})).json() == {'error': 'invalid_grant'}
    args, grant = await issued(client)
    assert (await client.delete('/v1/personal-tokens/' + grant['credential_id'], headers=WORKSPACE)).status_code == 204
    assert (await client.post('/mcp', headers={'authorization': 'Bearer ' + grant['access_token']}, json={})).status_code == 401


@pytest.mark.asyncio
async def test_za_protocol_endpoints_are_absent(mcp_api, monkeypatch):
    client, _, rt, _ = mcp_api
    monkeypatch.setattr(rt, 'box_region', lambda: 'za')
    for method, path in [('GET', '/.well-known/oauth-authorization-server'), ('POST', '/oauth/token'), ('POST', '/oauth/register'), ('POST', '/oauth/revoke'), ('POST', '/mcp'), ('GET', '/mcp'), ('DELETE', '/mcp')]:
        assert (await client.request(method, path)).status_code == 404
