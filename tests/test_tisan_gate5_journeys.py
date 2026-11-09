"""Actual identity, command, publish and receipt routes with offline providers."""
import json
import os
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import command
import tisan_requests
from agents.tisan import publish, runtime as room_runtime
from test_tisan_requests import client as client, runtime as runtime, command_pool as command_pool, brief
from test_tisan_publish import build, exercise, FakeServices, configured as configured, TENANT, BRANCH, NEW
from trigger_signin_fakes import native_provider, ORG
import test_tisan_quotes_designed
from test_tisan_quotes_designed import database as database, HEADERS, designed

quote_api = test_tisan_quotes_designed.api
from test_tisan_quotes import A, B, quote_fields


@pytest.mark.asyncio
async def test_actual_room_authenticated_queue_roundtrip_preserves_body_and_tenant(command_pool, tmp_path, monkeypatch, caplog):
    from agents.tisan import app as room
    async with command_pool.acquire() as conn:
        name = await conn.fetchval('SELECT current_database()')
    base = urlsplit(os.environ['POOL_SCHEMA_DATABASE_URL'])
    assert base.hostname in {'127.0.0.1','localhost'}
    for key,value in {'DATABASE_URL':base._replace(path='/' + name).geturl(),
                      'DATA_DIR':str(tmp_path),'TANK_KEY':'placeholder-room-key','TANK_REGION':'us-east'}.items():
        monkeypatch.setenv(key, value)
    for key in ('HERMES_URL','CHASSIS_ADMIN_DATABASE_URL','CHASSIS_RLS_ADMIN_ROLE'):
        monkeypatch.delenv(key, raising=False)
    owner, other = str(uuid4()), str(uuid4())
    headers = {'X-Tank-Key':'placeholder-room-key','X-Tervory-Tenant':owner}
    with TestClient(room.app) as http:
        response = http.post('/jobs', headers=headers, json={'tenant_id':owner,'kind':'ping','input':{}})
        assert response.status_code == 201, response.text
        record = response.json()
        assert record['tenant_id'] == owner
        assert http.post('/jobs', json={'tenant_id':owner,'kind':'ping','input':{}}).status_code == 401
        own = http.get('/jobs/' + record['id'], headers=headers, params={'tenant_id':owner})
        assert own.status_code == 200 and own.json()['tenant_id'] == owner
        foreign = http.get('/jobs/' + record['id'], params={'tenant_id':other},
                           headers={**headers,'X-Tervory-Tenant':other})
        assert foreign.status_code == 404
        invalid = http.post('/jobs', headers=headers, json={'tenant_id':owner,'kind':'../escape','input':{}})
        assert invalid.status_code == 422
    async with command_pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM agent_tisan.jobs WHERE tenant_id=$1', UUID(owner)) == 1
    assert 'placeholder-room-key' not in caplog.text


@pytest.mark.asyncio
async def test_new_signed_in_client_first_request_error_safe_retry_first_result_and_receipt(
        client, runtime, configured, tmp_path, monkeypatch, caplog):
    browser, pool, journal, room = client
    owner = UUID(TENANT)
    # Trigger sign-in owns sign-up. Its fake issuer supplies a newly registered
    # organisation; the real identity verifier checks its signed session.
    provider = native_provider(monkeypatch, {ORG: TENANT})
    signed = provider.workspace_headers('placeholder-admin', TENANT)
    import identity_oidc
    claims = await identity_oidc.verify(signed['x-trigger-signin-token'], workspace=True)
    tenant, subject, administrator = identity_oidc.principal(claims, workspace=True)
    assert tenant == owner and subject == 'placeholder-admin' and administrator is True
    browser.headers.update({**signed, 'X-Tervory-Role':'org:admin'})
    room_runtime.secure_routes(room)
    app = FastAPI()
    app.include_router(command.router)
    app.include_router(tisan_requests.build_router())
    runtime.app = app

    async def confirmed(tool, arguments, thread):
        proposed = await browser.post(f'/v1/command/threads/{thread}/actions',
                                      json={'tool': tool, 'arguments': arguments})
        assert proposed.status_code == 200, proposed.text
        card = proposed.json()['card_id']
        response = await browser.post('/v1/command/cards/' + card, json={'action': 'confirm'})
        assert response.status_code == 200, response.text
        return response.json(), card

    empty = await browser.get('/v1/command/tisan/preview', params={'slug': 'site'})
    assert empty.status_code == 404 and 'url' not in empty.json()
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_requests WHERE tenant_id=$1', owner) == 0
    thread = (await browser.post('/v1/command/threads', json={'title':'placeholder first site'})).json()['thread_id']
    requested, card = await confirmed('tisan.request', {**brief(), 'slug':'site'}, thread)
    assert requested['result']['status'] == 'requested'
    replay = await browser.post('/v1/command/cards/' + card, json={'action':'confirm'})
    assert replay.status_code == 200 and replay.json()['result'] == requested['result']
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_requests WHERE tenant_id=$1', owner) == 1

    build(tmp_path)
    fake = FakeServices()
    fake.git_branch = 'placeholder-wrong-branch'
    service, http, _ = await exercise(tmp_path, monkeypatch, fake)
    operation = publish.PublishRequest(tenant_id=owner, slug='site', build=1, operation_id=uuid4())
    async with http:
        failed = await service.run(operation, 'founder')
        assert failed['result'] == 'refused'
        assert not any(method in {'POST','PATCH'} for method, _, _ in fake.calls)
        count = len(fake.calls)
        assert await service.run(operation, 'founder') == failed
        assert len(fake.calls) == count
        unavailable = await browser.get('/v1/command/tisan/preview', params={'slug':'site'})
        assert unavailable.status_code == 200 and 'url' not in unavailable.json()

        # A new explicit operation may retry a refusal made before side effects.
        fake.git_branch = BRANCH
        retry = operation.model_copy(update={'operation_id':uuid4()})
        assert (await service.run(retry, 'founder'))['result'] == 'pending'
        published = await service.status(retry, 'founder')
        assert published['result'] == 'succeeded'
        mutations = [(method,url) for method,url,_ in fake.calls if method in {'POST','PATCH'}]
        assert await service.run(retry, 'founder') == published
        assert [(method,url) for method,url,_ in fake.calls if method in {'POST','PATCH'}] == mutations
    result = await browser.get('/v1/command/tisan/preview', params={'slug':'site'})
    assert result.status_code == 200
    assert result.json()['build_id'] == 1 and result.json()['commit'] == NEW
    accepted, _ = await confirmed('tisan.handover', {'slug':'site'}, thread)
    receipt = accepted['result']
    assert receipt['status'] == 'accepted' and receipt['cost_usd'] == 0
    assert receipt['commit'] == NEW and receipt['url'] == 'https://stage.test/'
    async with pool.acquire() as conn:
        measured = await conn.fetchrow('SELECT cost_usd,model,agent FROM tank.ledger WHERE tenant_id=$1 AND id=$2',
                                      owner, UUID(receipt['ledger_id']))
        assert measured['cost_usd'] == 0 and measured['model'] == 'code' and measured['agent'] == 'tisan'
        assert await conn.fetchval('SELECT count(*) FROM tank.tisan_request_events WHERE tenant_id=$1', owner) == 2
    foreign = await browser.get('/v1/command/tisan/preview', params={'slug':'site'},
                                headers={'X-Tervory-Tenant':str(uuid4())})
    assert foreign.status_code in {401,403,404}
    assert provider.calls  # The real OIDC verifier consumed the fake discovery/key responses.
    assert not any('prod' in url for _,url,_ in fake.calls)
    assert 'credential-marker-test-only' not in json.dumps(receipt) + caplog.text
    assert 'coolify-marker-test-only' not in json.dumps(receipt) + caplog.text


@pytest.mark.asyncio
async def test_quote_journey_has_real_history_and_an_invalid_retry_never_duplicates_it(quote_api):
    browser, store, admin, _ = quote_api
    assert (await browser.get('/quotes', params={'tenant_id':str(A)}, headers=HEADERS)).json() == []
    response = await browser.post('/quotes', headers=HEADERS, json={'tenant_id':str(A),'data':designed()})
    assert response.status_code == 201 and response.json()['state'] == 'submitted'
    ident = response.json()['id']
    early = await browser.post('/quotes/' + ident + '/state', headers=HEADERS,
                               json={'tenant_id':str(A),'state':'accepted'})
    assert early.status_code == 409
    for state in ('acknowledged','quoted','accepted'):
        response = await browser.post('/quotes/' + ident + '/state', headers=HEADERS,
            json={'tenant_id':str(A),'state':state, **(quote_fields() if state == 'quoted' else {})})
        assert response.status_code == 200
    replay = await browser.post('/quotes/' + ident + '/state', headers=HEADERS,
                                 json={'tenant_id':str(A),'state':'accepted'})
    assert replay.status_code == 409
    history = await browser.get('/quotes/' + ident, params={'tenant_id':str(A)}, headers=HEADERS)
    assert [event['to_state'] for event in history.json()['events']] == ['draft','submitted','acknowledged','quoted','accepted']
    assert (await browser.get('/quotes/' + ident, params={'tenant_id':str(B)}, headers=HEADERS)).status_code == 404
    assert (await browser.get('/quotes', params={'tenant_id':str(B)}, headers=HEADERS)).json() == []
    assert await admin.fetchval('SELECT count(*) FROM agent_tisan.quote_events') == 5
