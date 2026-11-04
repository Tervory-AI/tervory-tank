"""Synthetic local OIDC provider, real JWT verification and disposable Tank DB."""
from trigger_signin_fakes import set_founders
import asyncio
import base64
import time

from cryptography.hazmat.primitives.asymmetric import rsa
import httpx
import jwt
import pytest
from starlette.requests import Request

import identity_oidc as oidc
import personal_tokens as pat
from test_device_login import device as device_fixture
from test_command import runtime as runtime_fixture, command_pool as command_pool_fixture, TENANT

# Reuse the existing real-Postgres fixtures under their original pytest names.
device = device_fixture
runtime = runtime_fixture
command_pool = command_pool_fixture

from trigger_signin_fakes import Provider, CLIENT, ORG, SUB, install_registry


@pytest.fixture(params=['us-east', 'za'])
def provider(monkeypatch, runtime, request):
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
async def test_verified_claims_and_key_cache_rotation(provider):
    assert (await oidc.verify(provider.token()))['sub'] == SUB
    await oidc.verify(provider.token())
    assert provider.calls.count(('GET', '/keys')) == 1
    provider.kid = 'rotated-key'
    provider.keys = [provider.jwk()]
    with pytest.raises(oidc.IdentityError):
        await oidc.verify(provider.token())
    assert provider.calls.count(('GET', '/keys')) == 1
    oidc._cache[provider.issuer]['keys_refresh_after'] = time.monotonic() - 1
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


def test_native_external_founder_uses_signed_tenant_grant_not_home_org(provider):
    claims = {**provider.claims, oidc.ORG_CLAIM: '90001'}
    tenant, subject, tenant_admin = oidc.principal(claims)
    assert tenant == TENANT and subject == SUB and tenant_admin is True
    with pytest.raises(oidc.IdentityError):
        oidc.principal(claims, org_id='90001')


def test_unmapped_organisation_and_metadata_do_not_grant_identity(provider, monkeypatch):
    with pytest.raises(oidc.IdentityError):
        oidc.principal({**provider.claims, oidc.ORG_CLAIM: '99999', oidc.ROLES_CLAIM: {'member': {'99999': 'foreign'}}})
    claims = {**provider.claims, oidc.ROLES_CLAIM: {'member': {ORG: 'tervory'}}, 'email': 'founder@tervory.com',
              'name': 'founder', 'metadata': {'role': 'org_admin', 'founder': True},
              'urn:zitadel:iam:user:metadata': {'founder': 'true'},
              'urn:zitadel:iam:org:project:another-project:roles': {'org_admin': {ORG: 'tervory'}}}
    tenant, user, admin = oidc.principal(claims)
    assert tenant == TENANT and user == SUB and admin is False
    assert oidc.principal(provider.claims)[2] is True
    assert oidc.principal({**provider.claims, oidc.ROLES_CLAIM: {'member': {ORG: 'tervory'}, 'org_admin': {'99999': 'elsewhere'}}})[2] is False


@pytest.mark.asyncio
async def test_provider_endpoints_cannot_escape_fixed_origin(provider, monkeypatch):
    for endpoint in ['https://evil.example/token', 'http://auth.tervory.com/token',
                     'https://user@auth.tervory.com/token', 'https://auth.tervory.com:444/token']:
        with pytest.raises(oidc.IdentityError):
            oidc.endpoint(endpoint)


@pytest.mark.asyncio
@pytest.mark.parametrize('region', ['us-east', 'za'])
async def test_missing_or_misplaced_issuer_fails_closed(device, monkeypatch, region):
    client, _, runtime = device
    runtime.box_region = lambda: region
    install_registry(monkeypatch, [], {})
    monkeypatch.setattr(oidc, 'http_client', lambda: pytest.fail('Unconfigured issuer made an HTTP request'))
    result = await client.post('/v1/command/device/code', json={'device_name': 'synthetic'})
    assert result.status_code == 503
    record = {'issuer': 'https://retired.example.invalid', 'client_id': CLIENT, 'workspace_client_id': CLIENT, 'organisations': {}}
    monkeypatch.setitem(oidc.registry._records, 'us-east', record)
    assert (await client.post('/v1/command/device/code', json={'device_name': 'synthetic'})).status_code == 503


@pytest.mark.asyncio
async def test_regional_oidc_issue_refresh_revoke_and_verified_roles(device, provider, monkeypatch):
    client, pool, runtime = device
    result = await client.post('/v1/command/device/code', json={'device_name': 'synthetic', 'approval': 'trigger-signin'})
    assert result.status_code == 200
    start = result.json()
    assert start['identity_provider'] == 'trigger-signin' and start['user_code'] == '1234-5678'
    assert start['verification_uri'].startswith(provider.issuer + '/')
    wrapped = start['device_code']
    assert base64.urlsafe_b64decode(wrapped[5:] + '=' * (-len(wrapped[5:]) % 4)) == b'synthetic-provider-code'
    issued = await client.post('/v1/command/device/token', json={'device_code': wrapped})
    assert issued.status_code == 200, issued.text
    grant = issued.json()
    assert grant['access_token'].startswith('tv1.' + provider.region + '.') and grant['refresh_token'].startswith('tvr1.' + provider.region + '.')
    assert grant['expires_in'] == 3600 and grant['refresh_expires_in'] == 30 * 86400
    assert (await client.post('/v1/command/device/token', json={'device_code': wrapped})).json()['error'] == 'invalid_grant'
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM tank.personal_tokens')
        assert row['user_id'] == SUB and row['tenant_id'] == TENANT
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
    assert actor.user_id == SUB and actor.tenant_admin and not actor.founder
    set_founders(monkeypatch, SUB)
    assert (await pat.identity(request(grant['access_token']))).founder
    set_founders(monkeypatch, 'somebody-else')
    assert not (await pat.identity(request(grant['access_token']))).founder
    rotated = await client.post('/v1/command/device/refresh', json={'refresh_token': grant['refresh_token']})
    assert rotated.status_code == 200 and rotated.json()['access_token'] != grant['access_token']
    assert (await client.post('/v1/command/device/refresh', json={'refresh_token': grant['refresh_token']})).json()['error'] == 'invalid_grant'
    fresh = rotated.json()
    assert (await client.post('/v1/command/device/revoke', json={'refresh_token': fresh['refresh_token']})).json()['revoked']
    assert (await client.post('/v1/command/device/refresh', json={'refresh_token': fresh['refresh_token']})).json()['error'] == 'invalid_grant'
    with pytest.raises(Exception):
        await pat.identity(request(fresh['access_token']))


@pytest.mark.asyncio
async def test_legacy_approval_routes_are_removed_and_default_is_native(device, provider):
    client, _, _ = device
    started = await client.post('/v1/command/device/code', json={'device_name': 'synthetic'})
    assert started.status_code == 200
    assert started.json()['identity_provider'] == 'trigger-signin'
    refused = await client.post('/v1/command/device/code', json={'device_name': 'synthetic', 'approval': 'workspace'})
    assert refused.status_code == 422
    assert (await client.get('/v1/command/device/approval/BCDF-GHJK')).status_code == 404
    assert (await client.post('/v1/command/device/approval/BCDF-GHJK', json={'action': 'approve'})).status_code == 404


@pytest.mark.asyncio
async def test_signed_but_unmapped_org_mints_no_tank_credential(device, provider):
    client, pool, runtime = device
    provider.claims[oidc.ORG_CLAIM] = '99999'
    provider.claims[oidc.ROLES_CLAIM] = {'member': {'99999': 'foreign'}}
    code = (await client.post('/v1/command/device/code', json={'device_name': 'synthetic', 'approval': 'trigger-signin'})).json()['device_code']
    response = await client.post('/v1/command/device/token', json={'device_code': code})
    assert response.status_code == 400 and response.json() == {'error': 'invalid_grant'}
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.personal_tokens') == 0


@pytest.mark.asyncio
async def test_slow_provider_releases_pool_and_overlapping_polls_issue_once(device, provider, monkeypatch):
    client, pool, runtime = device
    wrapped = (await client.post('/v1/command/device/code', json={
        'device_name': 'concurrent-synthetic', 'approval': 'trigger-signin'})).json()['device_code']
    entered = [asyncio.Event(), asyncio.Event()]
    release_poll, release_verify = asyncio.Event(), asyncio.Event()
    verifying = asyncio.Event()
    calls = 0
    original_verify = oidc.verify

    async def slow_poll(code):
        nonlocal calls
        assert pool.get_idle_size() == pool.get_size()
        slot = calls
        calls += 1
        entered[slot].set()
        await release_poll.wait()
        return {'id_token': provider.token()}

    async def slow_verify(token):
        assert pool.get_idle_size() == pool.get_size()
        verifying.set()
        await release_verify.wait()
        return await original_verify(token)

    monkeypatch.setattr(oidc, 'poll', slow_poll)
    monkeypatch.setattr(oidc, 'verify', slow_verify)
    async def request():
        return await client.post('/v1/command/device/token', json={'device_code': wrapped})
    first = asyncio.create_task(request())
    second = None
    try:
        await asyncio.wait_for(entered[0].wait(), 20)
        # Simulate the next allowed interval while the first provider call is stalled.
        async with pool.acquire() as conn:
            await conn.execute("UPDATE tank.device_authorizations SET last_polled_at=now()-interval '5 seconds'")
        second = asyncio.create_task(request())
        await asyncio.wait_for(entered[1].wait(), 20)
        assert pool.get_idle_size() == pool.get_size()
        async with pool.acquire(timeout=10) as conn:
            assert await conn.fetchval('SELECT 1') == 1
        release_poll.set()
        await asyncio.wait_for(verifying.wait(), 20)
        assert pool.get_idle_size() == pool.get_size()
        release_verify.set()
        responses = await asyncio.wait_for(asyncio.gather(first, second), 30)
        assert sorted(r.status_code for r in responses) == [200, 400]
        assert [r.json()['error'] for r in responses if r.status_code == 400] == ['invalid_grant']
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM tank.personal_tokens') == 1
            assert await conn.fetchval("SELECT status FROM tank.device_authorizations") == 'consumed'
    finally:
        release_poll.set()
        release_verify.set()
        await asyncio.gather(*(t for t in [first, second] if t), return_exceptions=True)


@pytest.mark.asyncio
async def test_unknown_kid_refresh_is_bounded_and_does_not_lock_known_keys(provider, monkeypatch):
    from types import SimpleNamespace
    clock = [100.0]
    monkeypatch.setattr(oidc, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    known = provider.token()
    await oidc.verify(known)
    for i in range(20):
        provider.kid = f'unknown-{i}'
        with pytest.raises(oidc.IdentityError):
            await oidc.verify(provider.token())
    assert provider.calls.count(('GET', '/keys')) == 1
    clock[0] = 160.0
    original_fetch = oidc.fetch
    fetching, release = asyncio.Event(), asyncio.Event()
    async def slow_fetch(method, url, **kwargs):
        if url.endswith('/keys'):
            assert not oidc._lock.locked()
            fetching.set()
            await release.wait()
        return await original_fetch(method, url, **kwargs)
    monkeypatch.setattr(oidc, 'fetch', slow_fetch)
    async def unknown():
        with pytest.raises(oidc.IdentityError):
            await oidc.verify(provider.token())
    pending = asyncio.create_task(unknown())
    try:
        await asyncio.wait_for(fetching.wait(), 2)
        assert (await asyncio.wait_for(oidc.verify(known), 1))['sub'] == SUB
        release.set()
        await pending
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
    assert provider.calls.count(('GET', '/keys')) == 2
    with pytest.raises(oidc.IdentityError):
        await oidc.verify(provider.token())
    assert provider.calls.count(('GET', '/keys')) == 2
