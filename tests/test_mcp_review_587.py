"""PR587: real-client compatibility, source trust and OAuth code replay."""
# ruff: noqa: F811 -- imported pytest fixtures are injected by name.
import ast
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest

import mcp_oauth as oauth
import personal_tokens as pat
from test_command import runtime, command_pool, TENANT  # noqa: F401
from test_mcp_oauth import mcp_api, registration, approved, authorization, exchange, issued, WORKSPACE  # noqa: F401
from test_mcp_server import initialize, rpc


@pytest.mark.asyncio
async def test_authorize_ignores_extensions_but_refuses_duplicates(mcp_api):
    client, _, _, _ = mcp_api
    registered = await registration(client)
    args = {**authorization(registered['client_id']), 'scope': 'mcp', 'prompt': 'consent', 'nonce': 'synthetic'}
    response = await client.get('/oauth/authorize', params=args, headers=WORKSPACE)
    assert response.status_code == 200
    for key in ('scope', 'prompt', 'nonce'):
        duplicate = await client.get('/oauth/authorize', params=[*args.items(), (key, 'again')], headers=WORKSPACE)
        assert duplicate.status_code == 400 and 'location' not in duplicate.headers
    decision = await client.post('/oauth/authorize', json={**args, 'action': 'deny'}, headers=WORKSPACE)
    assert decision.status_code == 200 and 'access_denied' in decision.json()['redirect_to']


@pytest.mark.parametrize('params', [{'cursor': 'opaque'}, {'_meta': {'progressToken': 'offline'}}, {'cursor': '', '_meta': {}}])
@pytest.mark.asyncio
async def test_tool_list_accepts_standard_optional_params(mcp_api, params):
    client, _, _, _ = mcp_api
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    expected = (await rpc(client, headers, 'tools/list')).json()['result']
    assert (await rpc(client, headers, 'tools/list', params)).json()['result'] == expected


@pytest.mark.parametrize('grants,responses', [
    (['refresh_token', 'authorization_code'], ['code']),
    (['authorization_code'], ['code']),
    (['authorization_code', 'authorization_code'], ['code', 'code']),
])
@pytest.mark.asyncio
async def test_registration_compares_supported_sets(mcp_api, grants, responses):
    client, _, _, _ = mcp_api
    registered = await registration(client, grant_types=grants, response_types=responses)
    assert set(registered['grant_types']) == set(grants)
    assert set(registered['response_types']) == set(responses)


@pytest.mark.parametrize('grants,responses', [(['implicit'], ['code']), (['authorization_code'], ['token']), ('authorization_code', ['code']), ([{}], ['code'])])
@pytest.mark.asyncio
async def test_registration_refuses_unsupported_or_malformed_sets(mcp_api, grants, responses):
    client, _, _, _ = mcp_api
    response = await client.post('/oauth/register', json={'client_name': 'Offline', 'redirect_uris': ['https://client.example/callback'], 'grant_types': grants, 'response_types': responses})
    assert response.status_code == 400 and response.json()['error'] == 'invalid_client_metadata'


@pytest.mark.asyncio
async def test_registration_sources_have_separate_limits_and_headers_need_service_auth(mcp_api):
    client, pool, rt, _ = mcp_api
    payload = {'client_name': 'Offline', 'redirect_uris': ['https://client.example/callback']}
    def headers(address, key=rt.TANK_API_KEY):
        return {'x-tervory-oauth-source': address, 'x-tank-key': key}
    source_a, source_b = '203.0.113.10', '203.0.113.20'
    assert (await client.post('/oauth/register', json=payload, headers=headers(source_a))).status_code == 201
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.oauth_clients(client_id,client_name,redirect_uris,source_address_hash)
            SELECT 'tvc_'||md5('source-a-'||i::text),'Offline','["https://client.example/callback"]'::jsonb,$1
            FROM generate_series(1,49) i""", pat.digest(source_a))
    assert (await client.post('/oauth/register', json=payload, headers=headers(source_a))).status_code == 429
    assert (await client.post('/oauth/register', json=payload, headers=headers(source_b))).status_code == 201
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.oauth_clients(client_id,client_name,redirect_uris,source_address_hash)
            SELECT 'tvc_'||md5('peer-'||i::text),'Offline','["https://client.example/callback"]'::jsonb,$1
            FROM generate_series(1,50) i""", pat.digest('127.0.0.1'))
    for patch in [headers(source_b, 'spoofed'), {'x-real-ip': source_b}, {'x-forwarded-for': source_b}, {'x-tervory-oauth-source': source_b}]:
        assert (await client.post('/oauth/register', json=payload, headers=patch)).status_code == 429
    assert (await client.post('/oauth/register', json=payload, headers=headers('not-an-ip'))).status_code == 400


@pytest.mark.parametrize('failure', [httpx.ConnectError('offline'), httpx.ReadTimeout('offline'), ValueError('offline'), OSError('offline'), RecursionError('offline')])
@pytest.mark.asyncio
async def test_cimd_fetch_failures_are_invalid_client(mcp_api, failure):
    client, _, _, fetch = mcp_api
    fetch.side_effect = failure
    args = authorization('https://client.example/metadata.json')
    response = await client.get('/oauth/authorize', params=args, headers=WORKSPACE)
    assert response.status_code == 400 and response.json() == {'detail': 'invalid_client'}
    assert 'location' not in response.headers


@pytest.mark.asyncio
async def test_code_and_refresh_exchange_never_fetch_client_metadata(mcp_api, monkeypatch):
    client, _, _, fetch = mcp_api
    client_id = 'https://client.example/metadata.json'
    fetch.side_effect = None
    fetch.return_value = (json.dumps({'client_id': client_id, 'client_name': 'Offline CIMD', 'redirect_uris': ['https://client.example/callback']}).encode(), {})
    args, code = await approved(client, {'client_id': client_id})
    oauth._metadata.clear()
    fetch.reset_mock(); fetch.side_effect = AssertionError('token exchange must not fetch')
    resolve = AsyncMock(side_effect=AssertionError('token exchange must not resolve metadata'))
    monkeypatch.setattr(oauth, 'client_metadata', resolve)
    grant_response = await exchange(client, args, code)
    assert grant_response.status_code == 200
    grant = grant_response.json()
    refresh = {'grant_type': 'refresh_token', 'client_id': client_id, 'resource': oauth.RESOURCE, 'refresh_token': grant['refresh_token']}
    for kind in ('authorization_code', 'refresh_token'):
        rejected = await client.post('/oauth/token', data={**refresh, 'grant_type': kind, 'client_id': 'https://other.example/unfetched', 'code': code, 'code_verifier': 'v' * 43, 'redirect_uri': args['redirect_uri']})
        assert rejected.json() == {'error': 'invalid_grant'}
    assert (await client.post('/oauth/token', data=refresh)).status_code == 200
    fetch.assert_not_awaited(); resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_code_replay_revokes_the_issued_grant_even_after_refresh(mcp_api):
    client, pool, _, _ = mcp_api
    args, code = await approved(client)
    grant = (await exchange(client, args, code)).json()
    async with pool.acquire() as conn:
        ident = await conn.fetchval('SELECT token_id FROM tank.oauth_codes WHERE tenant_id=$1 AND code_hash=$2', TENANT, pat.digest(code))
    assert str(ident) == grant['credential_id']
    refresh = {'grant_type': 'refresh_token', 'client_id': args['client_id'], 'resource': oauth.RESOURCE, 'refresh_token': grant['refresh_token']}
    rotated = (await client.post('/oauth/token', data=refresh)).json()
    headers = await initialize(client, rotated)
    # A mismatching verifier/client must not revoke somebody else's issued grant.
    assert (await exchange(client, args, code, code_verifier='w' * 43)).json() == {'error': 'invalid_grant'}
    assert (await exchange(client, args, code, client_id='https://other.example/unfetched')).json() == {'error': 'invalid_grant'}
    assert (await rpc(client, headers, 'ping')).status_code == 200
    assert (await exchange(client, args, code)).json() == {'error': 'invalid_grant'}
    assert (await rpc(client, headers, 'ping')).status_code == 401
    assert (await client.post('/oauth/token', data={**refresh, 'refresh_token': rotated['refresh_token']})).json() == {'error': 'invalid_grant'}
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT revoked_at IS NOT NULL FROM tank.personal_tokens WHERE tenant_id=$1 AND token_id=$2', TENANT, ident)


@pytest.mark.parametrize('origin', ['https://claude.ai', 'https://chatgpt.com', 'https://cursor.com'])
@pytest.mark.asyncio
async def test_required_client_origins_are_kept(mcp_api, origin):
    client, _, _, _ = mcp_api
    _, grant = await issued(client)
    headers = await initialize(client, grant)
    assert (await rpc(client, {**headers, 'origin': origin}, 'ping')).status_code == 200


def test_all_authentication_sql_queries_are_literals():
    root = Path(__file__).resolve().parents[1]
    for name in ['tank/mcp_oauth.py', 'tank/device_login.py', 'tank/personal_tokens.py']:
        tree = ast.parse((root / name).read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {'execute', 'fetchval', 'fetchrow', 'fetch'}:
                assert node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str), (name, node.lineno)


def test_current_official_cursor_callbacks_are_supported_without_unsafe_schemes():
    assert oauth.redirect_allowed('https://www.cursor.com/agents/mcp/oauth/callback')
    assert oauth.redirect_allowed('http://localhost:8787/callback')
    for value in ['http://evil.example/callback', 'javascript:alert(1)', 'data:text/html,hello', 'file:///tmp/callback']:
        assert not oauth.redirect_allowed(value)
