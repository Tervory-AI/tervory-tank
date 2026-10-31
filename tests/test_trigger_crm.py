"""Synthetic CRM transport only: no production requests, tokens, fixtures or database writes."""
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID

import command
import httpx
import pytest
import trigger_commands
import trigger_crm as crm
from fastapi import FastAPI, HTTPException

T = UUID('00000000-0000-0000-0000-000000000011')
OTHER = UUID('00000000-0000-0000-0000-000000000012')
RECORD = UUID('00000000-0000-0000-0000-000000000013')
ORG = '00000000-0000-0000-0000-000000000014'
FOUNDER = command.Actor(T, 'offline-founder', True)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'offline-founder')
    monkeypatch.setenv('TRIGGER_CRM_URL', 'http://trigger-crm-backend:8000')
    monkeypatch.setenv('TRIGGER_CRM_PAT_CONNECTOR', 'dummy-crm-token')
    monkeypatch.setenv('TRIGGER_CRM_TENANT_BINDINGS', json.dumps({str(T): {'organization_id': ORG, 'token_env': 'TRIGGER_CRM_PAT_CONNECTOR'}}))
    app = FastAPI()
    app.include_router(crm.router)
    app.dependency_overrides[command.identity] = lambda: FOUNDER
    return app


async def request(app, method='GET', path='/v1/trigger/crm/contacts', **kw):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as c:
        return await c.request(method, path, **kw)


def fake_transport(monkeypatch, callback):
    real = httpx.AsyncClient
    def client(**kw):
        assert kw['follow_redirects'] is False and kw['trust_env'] is False
        return real(**kw, transport=httpx.MockTransport(callback))
    monkeypatch.setattr(crm, 'httpx', SimpleNamespace(AsyncClient=client, Timeout=httpx.Timeout, HTTPError=httpx.HTTPError))


@pytest.mark.asyncio
async def test_read_projection_and_explicit_auth(setup, monkeypatch):
    def upstream(req):
        assert str(req.url) == 'http://trigger-crm-backend:8000/api/contacts/?page=1'
        assert req.headers['authorization'] == 'Bearer dummy-crm-token'
        assert 'x-tervory-tenant' not in req.headers
        return httpx.Response(200, json={'count': 1, 'contact_obj_list': [{'id': str(RECORD), 'first_name': 'Synthetic', 'password': 'hidden', 'users': [{'email': 'hidden'}]}], 'users': [{'email': 'hidden'}]})
    fake_transport(monkeypatch, upstream)
    r = await request(setup)
    assert r.status_code == 200
    assert r.json() == {'resource': 'contacts', 'items': [{'id': str(RECORD), 'first_name': 'Synthetic'}], 'page': 1, 'count': 1}


@pytest.mark.asyncio
async def test_nonfounder_and_other_tenant_denied_before_transport(setup, monkeypatch):
    original = crm.upstream
    transport = AsyncMock()
    monkeypatch.setattr(crm, 'upstream', transport)
    setup.dependency_overrides[command.identity] = lambda: command.Actor(T, 'client', False)
    monkeypatch.setattr(crm, 'authorized_actor', AsyncMock(side_effect=lambda actor: actor))
    assert (await request(setup)).status_code == 403
    transport.assert_not_awaited()
    setup.dependency_overrides[command.identity] = lambda: command.Actor(OTHER, 'offline-founder', True)
    monkeypatch.setattr(crm, "upstream", original)
    # Reapply configuration explicitly after restoring the mock to ensure no fallback mapping.
    monkeypatch.setenv('TRIGGER_CRM_TENANT_BINDINGS', '{}')
    assert (await request(setup)).status_code == 503


@pytest.mark.parametrize('suffix', ['?tenant_id='+str(OTHER), '?page=0', '?page=10001', '?page=1&page=2', '?status=closed', '?name='+('x'*256)])
@pytest.mark.asyncio
async def test_invalid_query_has_no_upstream(setup, monkeypatch, suffix):
    transport = AsyncMock()
    monkeypatch.setattr(crm, 'upstream', transport)
    assert (await request(setup, path='/v1/trigger/crm/contacts'+suffix)).status_code == 422
    transport.assert_not_awaited()


@pytest.mark.parametrize('code,expected', [(301,502),(401,503),(403,503),(404,404),(500,502)])
@pytest.mark.asyncio
async def test_upstream_errors_do_not_leak(setup, monkeypatch, code, expected):
    fake_transport(monkeypatch, lambda req: httpx.Response(code, json={'token':'hidden','message':'internal trace'}, headers={'Location':'https://untrusted.invalid'}))
    r = await request(setup)
    assert r.status_code == expected
    assert 'hidden' not in r.text and 'internal' not in r.text


@pytest.mark.asyncio
async def test_pinned_lead_pagination_and_detail(setup, monkeypatch):
    def upstream(req):
        if req.url.path.endswith(str(RECORD)+'/'):
            return httpx.Response(200,json={'lead_obj':{'id':str(RECORD),'title':'Synthetic'},'users':[{'email':'private'}]})
        return httpx.Response(200,json={'open_leads':{'open_leads':[{'id':str(RECORD),'title':'Synthetic'}],'leads_count':1},'close_leads':{'close_leads':[],'leads_count':0}})
    fake_transport(monkeypatch, upstream)
    r = await request(setup,path='/v1/trigger/crm/leads?page=2&status=in%20process')
    assert r.json()['count'] == 1 and r.json()['page'] == 2
    r = await request(setup,path=f'/v1/trigger/crm/leads/{RECORD}')
    assert r.json() == {'resource':'leads','item':{'id':str(RECORD),'title':'Synthetic'}}


@pytest.mark.asyncio
async def test_write_requires_actual_confirm_context(setup, monkeypatch):
    transport = AsyncMock()
    monkeypatch.setattr(crm,'upstream',transport)
    r = await request(setup,'POST','/v1/trigger/crm/write',json={'resource':'contacts','data':{'first_name':'Synthetic','last_name':'Offline'}})
    assert r.status_code == 409
    transport.assert_not_awaited()


@pytest.mark.asyncio
async def test_confirmed_context_bound_to_exact_actor_and_payload(setup, monkeypatch):
    args={'resource':'contacts','data':{'first_name':'Synthetic','last_name':'Offline'}}
    async def receipt(*args):return RECORD
    monkeypatch.setitem(sys.modules,'trigger_routes',SimpleNamespace(code_receipt=receipt))
    fake_transport(monkeypatch, lambda req: httpx.Response(200,json={'error':False,'id':str(RECORD)}))
    token=trigger_commands.CONFIRMED.set((T,'offline-founder',RECORD,'trigger.crm.write',args))
    try:
        r=await request(setup,'POST','/v1/trigger/crm/write',json={**args,'tenant_id':str(T)})
        assert r.status_code == 200 and r.json()['item'] == {'id':str(RECORD)}
        assert r.json()['ledger_id'] == str(RECORD) and r.json()['model_calls'] == 0
        wrong={**args,'data':{**args['data'],'first_name':'Changed'}}
        assert (await request(setup,'POST','/v1/trigger/crm/write',json=wrong)).status_code == 409
        assert (await request(setup,'POST','/v1/trigger/crm/write',json={**args,'tenant_id':str(OTHER)})).status_code == 403
    finally:trigger_commands.CONFIRMED.reset(token)


@pytest.mark.parametrize('extra',[{'tenant_id':str(OTHER)},{'org':ORG},{'approved':True},{'custom_fields':{'org':ORG}}])
def test_strict_write_schema_rejects_hidden_authority(extra):
    with pytest.raises(HTTPException) as exc:
        command.validate_action(command.PlannedAction(tool='trigger.crm.write',arguments={'resource':'contacts','data':{'first_name':'Synthetic','last_name':'Offline',**extra}}),FOUNDER)
    assert exc.value.status_code == 422


def test_tool_is_founder_only_and_pinned_estimate_sideeffects_denied():
    assert 'trigger.crm.write' not in command.allowed_tools(command.Actor(T,'client',False,frozenset({'trigger'})))
    with pytest.raises(HTTPException):command.validate_action(command.PlannedAction(tool='trigger.crm.write',arguments={}),command.Actor(T,'client',False))
    with pytest.raises(ValueError):crm.validate_data('estimates',{'title':'Synthetic','account_id':str(RECORD),'contact_id':str(RECORD),'start_project':True})


@pytest.mark.parametrize('change',[{'token_env':'TANK_API_KEY','organization_id':ORG},{'token_env':'TRIGGER_CRM_PAT_ABSENT','organization_id':ORG}])
def test_bad_binding_fails_closed(setup,monkeypatch,change):
    monkeypatch.setenv('TRIGGER_CRM_TENANT_BINDINGS',json.dumps({str(T):change}))
    with pytest.raises(HTTPException) as exc:crm.binding(FOUNDER)
    assert exc.value.status_code == 503


def test_shared_token_or_org_cannot_cross_tenants(setup,monkeypatch):
    bindings={str(T):{'organization_id':ORG,'token_env':'TRIGGER_CRM_PAT_CONNECTOR'},str(OTHER):{'organization_id':str(RECORD),'token_env':'TRIGGER_CRM_PAT_OTHER'}}
    monkeypatch.setenv('TRIGGER_CRM_PAT_OTHER','dummy-crm-token')
    monkeypatch.setenv('TRIGGER_CRM_TENANT_BINDINGS',json.dumps(bindings))
    with pytest.raises(HTTPException):crm.binding(FOUNDER)


@pytest.mark.parametrize('url',['https://untrusted.invalid','http://trigger-crm-backend:8000/path','https://crm.tervory.com?token=x'])
def test_ssrf_and_query_secret_destinations_refused(setup,monkeypatch,url):
    monkeypatch.setenv('TRIGGER_CRM_URL',url)
    with pytest.raises(HTTPException):crm.binding(FOUNDER)
