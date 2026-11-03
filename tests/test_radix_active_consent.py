"""Written tenant-admin consent through real Confirm and fresh runtime proof, offline."""
import json
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI,HTTPException

import command
from test_radix_passive import database as database,FakeServer
import active_routes
import passive_gateway
from passive_store import watch_artifact
from test_command import TENANT,OTHER,runtime as runtime,command_pool as command_pool,api as api
import radix_passive_routes

DOMAIN='placeholder.example'
URL='https://placeholder.example/'


@pytest.mark.asyncio
async def test_absent_withdrawn_and_foreign_consent_before_requests(database,monkeypatch):
    await database.issue(TENANT,DOMAIN)
    async with database.pool.acquire() as conn:
        await conn.execute('DELETE FROM agent_radix.active_consents')
    calls=[]
    async def forbidden(*args): calls.append('placeholder');raise AssertionError('placeholder request')
    for tenant in [TENANT,OTHER]:
        with pytest.raises(PermissionError):
            await active_routes.execute(database,tenant,URL,client=True,scanner=forbidden,
                http=httpx.AsyncClient(transport=httpx.MockTransport(forbidden)))
    consent=await database.consent(TENANT,DOMAIN,'placeholder-admin','placeholder written consent')
    assert consent['granted_by']=='placeholder-admin' and consent['granted_at']
    ident=await database.create(TENANT,URL,watch_artifact(DOMAIN),active=True,consent_id=UUID(consent['id']))
    await database.withdraw_consent(TENANT,DOMAIN,'placeholder-admin')
    lease=passive_gateway.Lease(database,check=forbidden,server=FakeServer)
    with pytest.raises(HTTPException): await lease.start(TENANT,ident,active=True)
    with pytest.raises(PermissionError):
        await active_routes.execute(database,TENANT,URL,client=True,scanner=forbidden,
            http=httpx.AsyncClient(transport=httpx.MockTransport(forbidden)))
    assert calls==[]
    async with database.pool.acquire() as conn:
        row=await conn.fetchrow('SELECT consent_text,withdrawn_by,withdrawn_at FROM agent_radix.active_consents WHERE tenant_id=$1 AND id=$2',TENANT,UUID(consent['id']))
    assert row['consent_text']=='placeholder written consent' and row['withdrawn_by']=='placeholder-admin' and row['withdrawn_at']


@pytest.mark.asyncio
async def test_client_runtime_proof_same_lock_and_withdraw_revoke(database,monkeypatch):
    monkeypatch.setattr(passive_gateway,'private_bind_address',lambda:'127.0.0.1')
    await database.issue(TENANT,DOMAIN)
    consent=await database.consent(TENANT,DOMAIN,'placeholder-admin','placeholder consent')
    ident=await database.create(TENANT,URL,watch_artifact(DOMAIN),active=True,consent_id=UUID(consent['id']))
    dns=[]
    async def proof(domain,challenge): dns.append(domain);return True
    lease=passive_gateway.Lease(database,check=proof,server=FakeServer)
    await lease.start(TENANT,ident,active=True)
    assert dns==[DOMAIN] and lease.proxy_server.proxy._verified_host==DOMAIN
    proxy=lease.proxy_server.proxy
    passive=await database.create(TENANT,URL,watch_artifact(DOMAIN))
    other=passive_gateway.Lease(database,check=proof,server=FakeServer)
    with pytest.raises(HTTPException) as error: await other.start(TENANT,passive)
    assert error.value.status_code==409
    await database.withdraw_consent(TENANT,DOMAIN,'placeholder-admin')
    await lease.revoke_withdrawn(TENANT)
    assert not proxy._active_lease() and lease.run is None
    await other.start(TENANT,passive)
    await other.release(TENANT,passive)


@pytest.mark.asyncio
async def test_admin_exact_confirm_and_zero_receipt(api,runtime,monkeypatch):
    client,pool=api;runtime.app=FastAPI();runtime.pool=lambda:pool
    runtime.app.include_router(radix_passive_routes.build_router(runtime))
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix','placeholder-founder')",TENANT)
    calls=[]
    async def room(request):
        calls.append(request)
        assert request.headers['x-tervory-user']=='placeholder-admin'
        assert request.headers['x-tervory-active-client']=='true'
        assert request.headers['x-tervory-active-authorized']=='true'
        return httpx.Response(200,json={'domain':DOMAIN,'id':'33333333-3333-4333-8333-333333333333'})
    monkeypatch.setenv('TANK_KEY_RADIX','placeholder-room-key')
    headers={'x-tervory-user':'placeholder-admin','x-tervory-role':'org:admin'}
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as http:
        runtime._http=http
        thread=(await client.post('/v1/command/threads',json={},headers=headers)).json()['thread_id']
        for tool,args in [('radix.active.consent',{'domain':DOMAIN,'consent_text':'placeholder written consent'}),
                          ('radix.active.consent.withdraw',{'domain':DOMAIN})]:
            response=await client.post(f'/v1/command/threads/{thread}/actions',json={'tool':tool,'arguments':args},headers=headers)
            assert response.status_code==200,response.text
            card=response.json();before=len(calls)
            assert card['status']=='pending'
            response=await client.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm'},headers=headers)
            result=response.json();assert result['status']=='confirmed',result
            assert len(calls)==before+1 and json.loads(calls[-1].content)=={'tenant_id':str(TENANT),**args}
            async with pool.acquire() as conn:
                row=await conn.fetchrow('SELECT cost_usd,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2',TENANT,UUID(result['result']['ledger_id']))
                assert row['cost_usd']==0 and row['model']=='code'
    for tool in ['radix.active.scan','radix.active.consent','radix.active.consent.withdraw']:
        assert tool not in command.allowed_tools(command.Actor(TENANT,'placeholder-member',False,frozenset({'radix'})))


@pytest.mark.asyncio
@pytest.mark.parametrize('proven',[True,False])
async def test_consented_scan_uses_fresh_proof_before_fake_scanner(database,monkeypatch,proven):
    monkeypatch.setattr(passive_gateway,'private_bind_address',lambda:'127.0.0.1')
    await database.issue(TENANT,DOMAIN)
    await database.consent(TENANT,DOMAIN,'placeholder-admin','placeholder consent')
    steps=[]
    async def proof(*args): steps.append('proof');return proven
    lease=passive_gateway.Lease(database,check=proof,server=FakeServer)
    async def control(request):
        body=json.loads(request.content)
        if request.url.path=='/active/lease':
            await lease.start(TENANT,UUID(body['scan_id']),active=True)
        else: await lease.release(TENANT,UUID(body['scan_id']))
        return httpx.Response(200,json={'ready':True})
    async def scanner(target,directory):
        assert target==URL;steps.append('scanner')
        return {'findings':[],'checks':{'active':{'status':'complete'}}}
    http=httpx.AsyncClient(transport=httpx.MockTransport(control))
    if proven:
        result=await active_routes.execute(database,TENANT,URL,client=True,scanner=scanner,http=http)
        assert result['active'] and result['status']=='complete' and steps==['proof','scanner']
    else:
        with pytest.raises(HTTPException):
            await active_routes.execute(database,TENANT,URL,client=True,scanner=scanner,http=http)
        assert steps==['proof']
