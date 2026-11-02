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


def fake_transport(monkeypatch, callback, *, attest=True):
    real = httpx.AsyncClient
    def call(req):
        response = callback(req)
        if attest and 200 <= response.status_code < 300:
            response.headers.setdefault("X-Tervory-CRM-Organization", ORG)
        return response
    def client(**kw):
        assert kw['follow_redirects'] is False and kw['trust_env'] is False
        return real(**kw, transport=httpx.MockTransport(call))
    monkeypatch.setattr(crm, 'httpx', SimpleNamespace(AsyncClient=client, Timeout=httpx.Timeout, HTTPError=httpx.HTTPError))


@pytest.mark.asyncio
async def test_read_projection_and_explicit_auth(setup, monkeypatch):
    def upstream(req):
        assert str(req.url) == 'http://trigger-crm-backend:8000/api/contacts/?offset=0&limit=10'
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
        assert req.url.params['offset'] == '10' and req.url.params['limit'] == '10'
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


@pytest.mark.parametrize('squads', [frozenset({squad}) for squad in command.TOOLS] + [frozenset(command.TOOLS)])
@pytest.mark.parametrize('tenant_admin', [False, True])
def test_no_client_squad_grant_exposes_crm_write(squads, tenant_admin):
    actor = command.Actor(T, 'offline-client', False, squads, tenant_admin)
    assert 'trigger.crm.write' not in command.allowed_tools(actor)
    with pytest.raises(HTTPException) as exc:
        command.require_tool(actor, 'trigger.crm.write')
    assert exc.value.status_code == 403


def test_tool_requires_founder_and_estimate_sideeffects_denied():
    assert 'trigger.crm.write' not in command.allowed_tools(command.Actor(T,'client',False))
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


@pytest.mark.asyncio
async def test_real_identity_requires_service_key_user_and_home_box(setup,monkeypatch):
    setup.dependency_overrides.clear()
    monkeypatch.setitem(sys.modules,'main',SimpleNamespace(TANK_API_KEY='dummy-workspace-key',box_region=lambda:'us-east'))
    fake_transport(monkeypatch,lambda req:httpx.Response(200,json={'results':[],'count':0}))
    assert (await request(setup)).status_code == 401
    headers={'X-Tank-Key':'dummy-workspace-key','X-Tervory-User':'offline-founder','X-Tervory-Tenant':str(T),'X-Tervory-Home-Region':'us-east'}
    assert (await request(setup,headers=headers)).status_code == 200
    assert (await request(setup,headers={**headers,'X-Tervory-Home-Region':'za'})).status_code == 403
    assert (await request(setup,headers={**headers,'X-Tervory-Tenant':str(OTHER)})).status_code == 503


@pytest.mark.asyncio
async def test_existing_durable_card_gate_checks_executing_payload_and_owner(setup,monkeypatch):
    args={'resource':'contacts','data':{'first_name':'Synthetic','last_name':'Offline'}}
    action=command.validate_action(command.PlannedAction(tool='trigger.crm.write',arguments=args),FOUNDER)
    state={'cards':{str(RECORD):{'status':'proposed','payload':action.model_dump(mode='json')}}}
    class Connection:
        async def fetchval(self,sql,*values):
            assert values == (RECORD,T,'offline-founder')
            assert 'tenant_id=$2 AND user_id=$3' in sql
            return state
    class Acquire:
        async def __aenter__(self):return Connection()
        async def __aexit__(self,*args):pass
    monkeypatch.setattr(command,'db',lambda:SimpleNamespace(acquire=lambda:Acquire()))
    dispatched=AsyncMock(return_value=(200,{'item':{'id':str(RECORD)}}))
    monkeypatch.setattr(command,'dispatch_action',dispatched)
    with pytest.raises(HTTPException) as exc:
        await trigger_commands.dispatch_confirmed(action,FOUNDER,RECORD,str(RECORD))
    assert exc.value.status_code == 409
    dispatched.assert_not_awaited()
    state['cards'][str(RECORD)]['status']='executing'
    async def bound_dispatch(sent,actor):
        assert trigger_commands.confirmation(actor,'trigger.crm.write',args) == RECORD
        return 200,{'item':{'id':str(RECORD)}}
    monkeypatch.setattr(command,'dispatch_action',bound_dispatch)
    assert (await trigger_commands.dispatch_confirmed(action,FOUNDER,RECORD,str(RECORD)))[0] == 200
    assert trigger_commands.CONFIRMED.get() is None


def test_pinned_schema_property_names_are_not_stripped_as_annotations():
    from pathlib import Path

    import yaml
    from trigger_crm_schema import ROOTS, SCHEMAS
    upstream=yaml.safe_load((Path(__file__).parents[1]/'ops/trigger-crm/openapi-cd7c12a.yml').read_text())['components']['schemas']
    excluded={'custom_fields','start_project','project_billing_type','public_link_enabled','deposit_percent'}
    for resource,name in ROOTS.items():
        excluded_for_resource = excluded if resource == 'estimates' else {'custom_fields', 'public_link_enabled'} if resource == 'invoices' else {'custom_fields'}
        expected=set(upstream[name]['properties'])-excluded_for_resource
        assert set(SCHEMAS[name]['properties']) == expected
    crm.validate_data('leads',{'title':'Synthetic','description':'Offline','assigned_to':[],'contacts':[],'teams':[]})
    crm.validate_data('contacts',{'first_name':'Synthetic','last_name':'Offline','title':'Offline role','description':'Offline'})
    crm.validate_data('estimates',{'title':'Synthetic','account_id':str(RECORD),'contact_id':str(RECORD)})


@pytest.mark.parametrize('actor', [
    command.Actor(T, 'offline-client', False, frozenset({'trigger'})),
    command.Actor(T, 'offline-admin', False, frozenset({'trigger'}), True),
    command.Actor(T, 'offline-member', False),
], ids=['granted-client', 'tenant-admin', 'member'])
@pytest.mark.asyncio
async def test_nonfounder_reads_and_writes_refused_even_with_grants(setup, monkeypatch, actor):
    setup.dependency_overrides[command.identity] = lambda: actor
    monkeypatch.setattr(crm, 'authorized_actor', AsyncMock(return_value=actor))
    upstream = AsyncMock()
    monkeypatch.setattr(crm, 'upstream', upstream)
    assert 'trigger.crm.write' not in command.allowed_tools(actor)
    for method, path, body in [
        ('GET', '/v1/trigger/crm/contacts', None),
        ('GET', '/v1/trigger/crm/contacts/' + str(RECORD), None),
        ('POST', '/v1/trigger/crm/write', {'resource': 'contacts', 'data': {'first_name': 'Synthetic', 'last_name': 'Offline'}}),
    ]:
        response = await request(setup, method, path, **({'json': body} if body else {}))
        assert response.status_code == 403
    upstream.assert_not_awaited()


@pytest.mark.parametrize('attested',[None,str(OTHER),'not-a-uuid'])
@pytest.mark.asyncio
async def test_wrong_or_missing_authenticated_org_never_leaks_or_writes(setup,monkeypatch,attested):
    calls=[]
    def upstream(req):
        calls.append(req.method)
        headers={} if attested is None else {'X-Tervory-CRM-Organization':attested}
        return httpx.Response(200,json={'results':[{'id':str(RECORD),'first_name':'FOREIGN'}],'count':1},headers=headers)
    fake_transport(monkeypatch,upstream,attest=False)
    response=await request(setup)
    assert response.status_code == 502 and 'FOREIGN' not in response.text
    args={'resource':'contacts','data':{'first_name':'Synthetic','last_name':'Offline'}}
    token=trigger_commands.CONFIRMED.set((T,'offline-founder',RECORD,'trigger.crm.write',args))
    try:
        response=await request(setup,'POST','/v1/trigger/crm/write',json=args)
        assert response.status_code == 502
        assert calls == ['GET','GET']  # Write blocked by attested read preflight.
    finally:trigger_commands.CONFIRMED.reset(token)


def middleware_class():
    import importlib.util
    from pathlib import Path
    path=Path(__file__).parents[1]/'ops/trigger-crm/tervory_crm_middleware.py'
    spec=importlib.util.spec_from_file_location('offline_crm_middleware',path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.OrganizationBinding


@pytest.mark.parametrize('expected,has_pat',[(str(OTHER),True),(ORG,False),('invalid',True)])
def test_crm_middleware_refuses_wrong_org_before_view(monkeypatch,expected,has_pat):
    monkeypatch.setitem(sys.modules,'django.http',SimpleNamespace(JsonResponse=lambda data,status:SimpleNamespace(status_code=status,data=data)))
    calls=[]
    handler=middleware_class()(lambda request:calls.append(request))
    req=SimpleNamespace(headers={'X-Tervory-CRM-Organization':expected},org=SimpleNamespace(id=UUID(ORG)),_pat=object() if has_pat else None)
    assert handler(req).status_code == 403
    assert calls == []


def test_crm_middleware_attests_only_resolved_pat_org():
    class Response(dict):status_code=200
    response=Response({'X-Tervory-CRM-Organization':'forged'})
    handler=middleware_class()(lambda req:response)
    req=SimpleNamespace(headers={'X-Tervory-CRM-Organization':ORG},org=SimpleNamespace(id=UUID(ORG)),_pat=object())
    assert handler(req)['X-Tervory-CRM-Organization'] == ORG
    req.headers={}
    req._pat=None
    assert 'X-Tervory-CRM-Organization' not in handler(req)


@pytest.mark.asyncio
async def test_invoice_read_uses_native_records_and_excludes_public_tokens(setup,monkeypatch):
    def upstream(req):
        invoice={'id':str(RECORD),'invoice_number':'OFFLINE-1','invoice_title':'Synthetic invoice','currency':'USD','total_amount':'123.45','amount_due':'123.45','amount_paid':'0.00','reminder_enabled':True,'reminder_frequency':'daily','public_token':'hidden','created_by':{'email':'hidden'}}
        if req.url.path.endswith(str(RECORD)+'/'):
            return httpx.Response(200,json={'invoice':invoice,'history':[{'private':'hidden'}]})
        assert req.url.path == '/api/invoices/'
        assert req.url.params['offset']=='10' and req.url.params['limit']=='10'
        return httpx.Response(200,json={'results':[invoice],'count':1,'totals':{'private':'hidden'}})
    fake_transport(monkeypatch,upstream)
    listing=await request(setup,path='/v1/trigger/crm/invoices?page=2')
    assert listing.status_code == 200 and listing.json()['resource']=='invoices'
    assert listing.json()['items'][0]['total_amount']=='123.45'
    assert 'hidden' not in listing.text
    detail=await request(setup,path=f'/v1/trigger/crm/invoices/{RECORD}')
    assert detail.status_code == 200 and detail.json()['item']['reminder_enabled'] is True
    assert 'hidden' not in detail.text


@pytest.mark.asyncio
async def test_invoice_confirmed_put_preserves_reminder_settings_without_send_or_payment(setup,monkeypatch):
    from trigger_crm_schema import SCHEMAS
    frequency=SCHEMAS['ReminderFrequencyEnum']['enum'][0]
    data={'account_id':str(RECORD),'contact_id':str(RECORD),'invoice_title':'Synthetic invoice','reminder_enabled':True,'reminder_frequency':frequency,'reminder_days_before':2,'reminder_days_after':1}
    args={'resource':'invoices','record_id':str(RECORD),'data':data}
    calls=[]
    def upstream(req):
        calls.append((req.method,req.url.path))
        assert '/send/' not in req.url.path and '/payments/' not in req.url.path
        if req.method=='GET':return httpx.Response(200,json={'results':[],'count':0})
        assert req.method=='PUT' and json.loads(req.content)==data
        return httpx.Response(200,json={'error':False,'invoice':{'id':str(RECORD),'invoice_title':data['invoice_title'],'reminder_enabled':True,'reminder_frequency':frequency}})
    fake_transport(monkeypatch,upstream)
    assert (await request(setup,'POST','/v1/trigger/crm/write',json=args)).status_code == 409
    assert calls == []
    monkeypatch.setitem(sys.modules,'trigger_routes',SimpleNamespace(code_receipt=AsyncMock(return_value=RECORD)))
    token=trigger_commands.CONFIRMED.set((T,'offline-founder',RECORD,'trigger.crm.write',args))
    try:
        response=await request(setup,'POST','/v1/trigger/crm/write',json=args)
        assert response.status_code == 200 and response.json()['item']['reminder_frequency']==frequency
        assert calls == [('GET','/api/invoices/'),('PUT',f'/api/invoices/{RECORD}/')]
    finally:trigger_commands.CONFIRMED.reset(token)


@pytest.mark.parametrize('extra',[{'amount_paid':'1.00'},{'status':'paid'},{'public_link_enabled':True},{'payment_method':'stripe'},{'reminder_frequency':'invented'}])
def test_invoice_record_write_never_accepts_payment_or_unapproved_sideeffects(extra):
    data={'account_id':str(RECORD),'contact_id':str(RECORD),'invoice_title':'Synthetic',**extra}
    with pytest.raises(ValueError):crm.validate_data('invoices',data)


@pytest.mark.parametrize('suffix',['send','mark-paid','payments'])
@pytest.mark.asyncio
async def test_invoice_action_paths_are_not_proxied(setup,monkeypatch,suffix):
    transport=AsyncMock()
    monkeypatch.setattr(crm,'upstream',transport)
    response=await request(setup,'POST',f'/v1/trigger/crm/invoices/{RECORD}/{suffix}')
    assert response.status_code == 404
    transport.assert_not_awaited()
