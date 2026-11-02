"""Synthetic local OIDC provider, real JWT verification and disposable Tank DB."""
import base64
import json
import time
from urllib.parse import parse_qs

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest
from starlette.requests import Request

import command
import identity_oidc as oidc
import personal_tokens as pat
from test_device_login import device  # noqa: F401
from test_command import runtime, command_pool, TENANT  # noqa: F401

CLIENT = '123@tervory'
ORG = '10001'
SUB = '20001'


class Provider:
    def __init__(self):
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = 'first-key'
        self.keys = [self.jwk()]
        self.calls = []
        self.claims = {'iss': oidc.ISSUER, 'aud': CLIENT, 'sub': SUB, 'exp': int(time.time()) + 600,
                       'iat': int(time.time()), oidc.ORG_CLAIM: ORG,
                       oidc.ROLES_CLAIM: {'org_admin': {ORG: 'tervory'}}}

    def jwk(self):
        return {**jwt.algorithms.RSAAlgorithm.to_jwk(self.private.public_key(), as_dict=True),
                'kid': self.kid, 'alg': 'RS256', 'use': 'sig'}

    def token(self, **claims):
        return jwt.encode({**self.claims, **claims}, self.private, algorithm='RS256', headers={'kid': self.kid})

    def __call__(self, request):
        assert request.url.host == 'auth.za.tervory.com'
        self.calls.append((request.method, request.url.path))
        if request.url.path == '/.well-known/openid-configuration':
            return httpx.Response(200, json={'issuer': oidc.ISSUER, 'jwks_uri': oidc.ISSUER + '/keys',
                'token_endpoint': oidc.ISSUER + '/oauth/v2/token',
                'device_authorization_endpoint': oidc.ISSUER + '/oauth/v2/device_authorization'})
        if request.url.path == '/keys':
            return httpx.Response(200, json={'keys': self.keys})
        form = parse_qs(request.content.decode())
        assert request.method == 'POST' and form['client_id'] == [CLIENT]
        if request.url.path == '/oauth/v2/device_authorization':
            assert form['scope'] == [oidc.SCOPE]
            return httpx.Response(200, json={'device_code': 'synthetic-provider-code', 'user_code': '1234-5678',
                'verification_uri': oidc.ISSUER + '/ui/v2/login/device',
                'verification_uri_complete': oidc.ISSUER + '/ui/v2/login/device?user_code=1234-5678',
                'expires_in': 600, 'interval': 5})
        assert request.url.path == '/oauth/v2/token'
        assert form['device_code'] == ['synthetic-provider-code']
        assert form['grant_type'] == ['urn:ietf:params:oauth:grant-type:device_code']
        return httpx.Response(200, json={'id_token': self.token(), 'access_token': 'unused-synthetic-upstream-token'})


@pytest.fixture
def provider(monkeypatch):
    provider = Provider()
    oidc._cache.clear()
    monkeypatch.setenv('IDENTITY_ISSUER', oidc.ISSUER)
    monkeypatch.setenv('IDENTITY_CLIENT_ID', CLIENT)
    monkeypatch.setenv('IDENTITY_ORG_TENANTS', json.dumps({ORG: str(TENANT)}))
    monkeypatch.setattr(oidc, 'http_client', lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider)))
    yield provider
    oidc._cache.clear()


@pytest.mark.asyncio
async def test_verified_claims_and_key_cache_rotation(provider):
    assert (await oidc.verify(provider.token()))['sub'] == SUB
    await oidc.verify(provider.token())
    assert provider.calls.count(('GET', '/keys')) == 1
    provider.kid = 'rotated-key'
    provider.keys = [provider.jwk()]
    await oidc.verify(provider.token())
    assert provider.calls.count(('GET', '/keys')) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [{'aud': 'another-client'}, {'iss': 'https://other.example'}, {'exp': 1}, {'azp': 'other-client'}])
async def test_token_checks_refuse_invalid_claims(provider, change):
    with pytest.raises(oidc.IdentityError, match='token refused'):
        await oidc.verify(provider.token(**change))


@pytest.mark.asyncio
async def test_bad_signature_and_unknown_kid_are_refused(provider):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(provider.claims, other, algorithm='RS256', headers={'kid': provider.kid})
    with pytest.raises(oidc.IdentityError):
        await oidc.verify(forged)
    provider.kid = 'unknown'
    with pytest.raises(oidc.IdentityError):
        await oidc.verify(provider.token())


def test_unmapped_organisation_and_metadata_do_not_grant_identity(provider, monkeypatch):
    with pytest.raises(oidc.IdentityError):
        oidc.principal({**provider.claims, oidc.ORG_CLAIM: '99999'})
    claims = {**provider.claims, oidc.ROLES_CLAIM: {}, 'email': 'founder@tervory.com',
              'name': 'founder', 'metadata': {'role': 'org_admin', 'founder': True},
              'urn:zitadel:iam:user:metadata': {'founder': 'true'},
              'urn:zitadel:iam:org:project:another-project:roles': {'org_admin': {ORG: 'tervory'}}}
    tenant, user, admin = oidc.principal(claims)
    assert tenant == TENANT and user == 'zitadel:' + SUB and admin is False
    assert oidc.principal(provider.claims)[2] is True
    assert oidc.principal({**provider.claims, oidc.ROLES_CLAIM: {'org_admin': {'99999': 'elsewhere'}}})[2] is False


@pytest.mark.asyncio
async def test_provider_endpoints_cannot_escape_fixed_origin(provider, monkeypatch):
    for endpoint in ['https://evil.example/token', 'http://auth.za.tervory.com/token',
                     'https://user@auth.za.tervory.com/token', 'https://auth.za.tervory.com:444/token']:
        with pytest.raises(oidc.IdentityError):
            oidc.endpoint(endpoint)


@pytest.mark.asyncio
async def test_issuer_unset_and_boston_keep_existing_device_flow(device, monkeypatch):
    client, _, runtime = device
    monkeypatch.delenv('IDENTITY_ISSUER', raising=False)
    monkeypatch.setattr(oidc, 'http_client', lambda: pytest.fail('OIDC was called with issuer unset'))
    result = await client.post('/v1/command/device/code', json={'device_name': 'synthetic'})
    assert result.status_code == 200 and result.json()['device_code'].startswith('tvd1.us-east.')
    monkeypatch.setenv('IDENTITY_ISSUER', oidc.ISSUER)
    assert not oidc.configured()  # Even a misplaced setting cannot change Boston.


@pytest.mark.asyncio
async def test_za_oidc_issue_refresh_revoke_and_verified_roles(device, provider, monkeypatch):
    client, pool, runtime = device
    runtime.box_region = lambda: 'za'
    result = await client.post('/v1/command/device/code', json={'device_name': 'synthetic'})
    assert result.status_code == 200
    start = result.json()
    assert start['identity_provider'] == 'zitadel' and start['user_code'] == '1234-5678'
    assert start['verification_uri'].startswith(oidc.ISSUER + '/')
    wrapped = start['device_code']
    assert base64.urlsafe_b64decode(wrapped[5:] + '=' * (-len(wrapped[5:]) % 4)) == b'synthetic-provider-code'
    issued = await client.post('/v1/command/device/token', json={'device_code': wrapped})
    assert issued.status_code == 200, issued.text
    grant = issued.json()
    assert grant['access_token'].startswith('tv1.za.') and grant['refresh_token'].startswith('tvr1.za.')
    assert grant['expires_in'] == 3600 and grant['refresh_expires_in'] == 30 * 86400
    assert (await client.post('/v1/command/device/token', json={'device_code': wrapped})).json()['error'] == 'invalid_grant'
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.personal_tokens')
        assert row['user_id'] == 'zitadel:' + SUB and row['tenant_id'] == TENANT
        assert row['identity_tenant_admin'] is True
        devices = await conn.fetch('SELECT * FROM tank.device_authorizations')
        stored = repr(dict(row)) + repr([dict(r) for r in devices])
        for secret in [wrapped, 'synthetic-provider-code', grant['access_token'], grant['refresh_token']]:
            assert secret not in stored
    def request(token, **extra):
        headers = {'authorization': 'Bearer ' + token, **extra}
        return Request({'type': 'http', 'method': 'GET', 'path': '/v1/command/tools', 'query_string': b'',
                        'headers': [(k.encode(), v.encode()) for k, v in headers.items()]})
    actor = await pat.identity(request(grant['access_token'], **{'x-tervory-user': 'founder'}))
    assert actor.user_id == 'zitadel:' + SUB and actor.tenant_admin and not actor.founder
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'zitadel:' + SUB)
    assert (await pat.identity(request(grant['access_token']))).founder
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'somebody-else')
    assert not (await pat.identity(request(grant['access_token']))).founder
    rotated = await client.post('/v1/command/device/refresh', json={'refresh_token': grant['refresh_token']})
    assert rotated.status_code == 200 and rotated.json()['access_token'] != grant['access_token']
    assert (await client.post('/v1/command/device/refresh', json={'refresh_token': grant['refresh_token']})).json()['error'] == 'invalid_grant'
    fresh = rotated.json()
    assert (await client.post('/v1/command/device/revoke', json={'refresh_token': fresh['refresh_token']})).json()['revoked']
    assert (await client.post('/v1/command/device/refresh', json={'refresh_token': fresh['refresh_token']})).json()['error'] == 'invalid_grant'
    with pytest.raises(Exception):
        await pat.identity(request(fresh['access_token']))
