import sys
from types import SimpleNamespace

import httpx
import pytest
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.requests import Request
from fastapi import HTTPException

import identity_oidc as oidc
import personal_tokens
import trigger_signin_config as registry
from trigger_signin_guard import TriggerSigninMiddleware
from trigger_signin_fakes import Provider, CLIENT, ORG, SUB, install_registry

TENANT = '00000000-0000-0000-0000-000000000011'
OTHER = '00000000-0000-0000-0000-000000000012'
WEB_CLIENT = '456@tervory'


@pytest.fixture(params=['us-east', 'za'])
def boundary(monkeypatch, request):
    runtime = SimpleNamespace(TANK_API_KEY='offline-workspace-service', box_region=lambda: request.param)
    monkeypatch.setitem(sys.modules, 'main', runtime)
    web = Provider('us-east')
    web.claims['aud'] = WEB_CLIENT
    local = Provider(request.param)
    install_registry(monkeypatch, [web, local], {ORG: TENANT, '99999': OTHER}, workspace_client=WEB_CLIENT)
    local.private = web.private
    local.keys = [local.jwk()]
    providers = {'auth.tervory.com': web}
    monkeypatch.setenv('TRIGGER_SIGNIN_ISSUER', local.issuer)
    monkeypatch.setenv('TRIGGER_SIGNIN_CLIENT_ID', CLIENT)
    monkeypatch.setenv('TRIGGER_SIGNIN_WORKSPACE_CLIENT_ID', WEB_CLIENT)
    monkeypatch.setattr(oidc, 'http_client', lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(lambda incoming: providers[incoming.url.host](incoming))))
    oidc._cache.clear()

    async def terminal(scope, receive, send):
        headers = Headers(scope=scope)
        identity = scope['state']['trigger_signin']
        await JSONResponse({'user_id': identity['user_id'], 'tenant_id': str(identity['tenant_id']),
                            'tenant_admin': identity['tenant_admin'], 'role': headers.get('x-tervory-role')})(scope, receive, send)

    headers = {'x-tank-key': runtime.TANK_API_KEY, 'x-tervory-user': SUB, 'x-tervory-tenant': TENANT,
               'x-trigger-signin-org': ORG}
    yield TriggerSigninMiddleware(terminal), web, local, headers
    oidc._cache.clear()


@pytest.mark.asyncio
async def test_workspace_token_is_required_and_verified_on_both_boxes(boundary):
    app, provider, _, headers = boundary
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        assert (await client.get('/', headers=headers)).status_code == 401
        assert provider.calls == []
        result = await client.get('/', headers={**headers, 'x-trigger-signin-token': provider.token()})
    assert result.status_code == 200
    assert result.json() == {'user_id': SUB, 'tenant_id': TENANT, 'tenant_admin': True, 'role': 'org:admin'}


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [{'aud': CLIENT}, {'iss': 'https://retired.example.invalid'}, {'exp': 1}])
async def test_other_audience_issuer_and_expired_tokens_are_refused(boundary, change):
    app, provider, _, headers = boundary
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        result = await client.get('/', headers={**headers, 'x-trigger-signin-token': provider.token(**change)})
    assert result.status_code == 401


@pytest.mark.asyncio
@pytest.mark.parametrize('change', [{'x-tervory-user': 'another-subject'}, {'x-tervory-tenant': OTHER}, {'x-tervory-admin': 'another-subject'}])
async def test_identity_headers_cannot_override_the_verified_subject_or_tenant(boundary, change):
    app, provider, _, headers = boundary
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        result = await client.get('/', headers={**headers, **change, 'x-trigger-signin-token': provider.token()})
    assert result.status_code == 403


@pytest.mark.asyncio
async def test_metadata_names_email_and_foreign_project_roles_never_grant_admin(boundary):
    app, provider, _, headers = boundary
    claims = {oidc.ROLES_CLAIM: {'member': {ORG: 'Tervory'}}, 'email': 'synthetic@example.invalid',
              'name': 'Founder', 'metadata': {'founder': True, 'role': 'org_admin'},
              'urn:zitadel:iam:org:project:unrelated:roles': {'org_admin': {ORG: 'Tervory'}}}
    token = provider.token(**claims)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        result = await client.get('/', headers={**headers, 'x-trigger-signin-token': token})
        forged = await client.get('/', headers={**headers, 'x-trigger-signin-token': token, 'x-tervory-role': 'org:admin'})
        founder = await client.get('/', headers={**headers, 'x-trigger-signin-token': token, 'x-tervory-admin': SUB})
    assert result.status_code == 200 and result.json()['tenant_admin'] is False
    assert forged.status_code == founder.status_code == 403


@pytest.mark.asyncio
async def test_organisation_switch_needs_a_signed_project_grant(boundary):
    app, provider, _, headers = boundary
    other = {**headers, 'x-trigger-signin-org': '99999', 'x-tervory-tenant': OTHER}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        refused = await client.get('/', headers={**other, 'x-trigger-signin-token': provider.token()})
        token = provider.token(**{oidc.ROLES_CLAIM: {'member': {ORG: 'Tervory', '99999': 'Another organisation'}}})
        accepted = await client.get('/', headers={**other, 'x-trigger-signin-token': token})
    assert refused.status_code == 403
    assert accepted.status_code == 200 and accepted.json()['tenant_id'] == OTHER
    assert accepted.json()['user_id'] == SUB and accepted.json()['tenant_admin'] is False


@pytest.mark.asyncio
async def test_regional_and_workspace_key_caches_and_audiences_stay_separate(boundary):
    _, web, local, _ = boundary
    assert (await oidc.verify(local.token()))['aud'] == CLIENT
    assert (await oidc.verify(web.token(), workspace=True))['aud'] == WEB_CLIENT
    with pytest.raises(oidc.IdentityError):
        await oidc.verify(local.token(), workspace=True)
    with pytest.raises(oidc.IdentityError):
        await oidc.verify(web.token())


@pytest.mark.asyncio
async def test_narrow_za_sessions_key_requires_native_proof_and_cannot_mint(boundary, monkeypatch):
    _, provider, _, headers = boundary
    region = sys.modules['main'].box_region()
    monkeypatch.setenv('TRIGGER_SIGNIN_SESSIONS_KEY', 'offline-own-sessions')
    records = {name: {**record, 'founders': [SUB]} for name, record in registry._records.items()}
    monkeypatch.setattr(registry, '_records', records)

    async def terminal(scope, receive, send):
        request = Request(scope)
        try:
            actor = await (personal_tokens.sign_in_actor(request) if request.method == 'GET'
                           else personal_tokens.workspace_actor(request))
            response = JSONResponse({'user_id': actor.user_id, 'founder': actor.founder})
        except HTTPException as error:
            response = JSONResponse({'detail': error.detail}, status_code=error.status_code)
        await response(scope, receive, send)

    presented = {**headers, 'x-tank-key': 'offline-own-sessions'}
    app = TriggerSigninMiddleware(terminal)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://offline') as client:
        assert (await client.get('/v1/personal-tokens', headers=presented)).status_code == 401
        verified = {**presented, 'x-trigger-signin-token': provider.token()}
        listed = await client.get('/v1/personal-tokens', headers=verified)
        assert listed.status_code == (200 if region == 'za' else 401)
        if region == 'za':
            assert listed.json() == {'user_id': SUB, 'founder': True}
        assert (await client.post('/v1/personal-tokens', headers=verified)).status_code == 401
        forged = {**verified, 'x-tervory-user': 'another-subject'}
        assert (await client.get('/v1/personal-tokens', headers=forged)).status_code == 403
