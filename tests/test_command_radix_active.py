"""The existing Confirm corridor authorizes only the founder, without a model."""
import json
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import command
import radix_passive_routes as corridor
from test_command import TENANT, OTHER, runtime as runtime, command_pool as command_pool, api as api
from trigger_commands import CONFIRMED

TOOL='radix.active.scan'
ARGS={'url':'https://tervory.com/'}


def test_admin_or_founder_single_url_and_existing_presentation(runtime):
    assert TOOL in command.TOOLS['radix'] and TOOL in command.ADAPTERS
    for founder,admin in [(False,False),(False,True),(True,False)]:
        actor=command.Actor(TENANT,'founder' if founder else 'placeholder-client',founder,frozenset({'radix'}),admin)
        assert (TOOL in command.allowed_tools(actor))==(founder or admin)
        action=command.PlannedAction(tool=TOOL,arguments=ARGS)
        if not (founder or admin):
            with pytest.raises(HTTPException): command.adapter_request(action,actor)
        else:
            _,_,_,body=command.adapter_request(action,actor)
            assert body=={'tenant_id':str(TENANT),**ARGS}
            for extra in ['domain','tenant_id','artifact','active','bounds']:
                with pytest.raises(HTTPException):
                    command.validate_action(command.PlannedAction(tool=TOOL,arguments={**ARGS,extra:'placeholder'}),actor)
    projected=command.public_card({'tool':TOOL,'result':{'status':'failed','findings':[{'rule':'40012','active':True}]}})
    assert projected['tool']=='radix.findings' and projected['result']['status']=='failed'
    assert projected['result']['findings'][0]['rule']=='active · 40012'
    assert command.action_timeout(TOOL)==1260


@pytest.mark.asyncio
async def test_confirm_dispatch_receipt_and_no_second_scan(api,runtime,monkeypatch):
    client,pool=api
    runtime.app=FastAPI();runtime.pool=lambda:pool
    calls=[]
    async def room(request):
        assert request.url.path=='/passive/active'
        assert request.headers['x-tervory-active-authorized']=='true'
        payload=json.loads(request.content)
        assert payload=={'tenant_id':str(TENANT),**ARGS}
        calls.append(payload)
        return httpx.Response(200,json={'scan_id':str(uuid4()),'active':True,'status':'failed',
            'findings':[],'checks':{'active':{'status':'partial','reason':'placeholder-blocked'}}})
    monkeypatch.setenv('TANK_KEY_RADIX','placeholder-room-key')
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as room_http:
        runtime._http=room_http;runtime.app.include_router(corridor.build_router(runtime))
        thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
        response=await client.post(f'/v1/command/threads/{thread}/actions',json={'tool':TOOL,'arguments':ARGS})
        assert response.status_code==200,response.text
        card=response.json();assert card['status']=='pending' and not calls
        path=f"/v1/command/cards/{card['card_id']}"
        assert (await client.post(path,json={'action':'confirm'},headers={'x-tervory-user':'placeholder-client'})).status_code==404
        assert (await client.post(path,json={'action':'confirm'},headers={'x-tervory-tenant':str(OTHER)})).status_code==404
        result=(await client.post(path,json={'action':'confirm'})).json()
        assert result['status']=='confirmed' and result['result']['status']=='failed',result
        assert result['result']['ledger_id'] and len(calls)==1
        await client.post(path,json={'action':'confirm'})
        assert len(calls)==1
        async with pool.acquire() as conn:
            row=await conn.fetchrow("SELECT cost_usd,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2",TENANT,__import__('uuid').UUID(result['result']['ledger_id']))
            assert row['cost_usd']==0 and row['model']=='code'


@pytest.mark.asyncio
async def test_direct_unconfirmed_corridor_and_wrong_user_refused(runtime,monkeypatch):
    monkeypatch.setenv('TANK_KEY_RADIX','placeholder-room-key')
    async def room(request): raise AssertionError('placeholder room called without Confirm')
    runtime.app=FastAPI();runtime.app.include_router(corridor.build_router(runtime))
    headers={'x-tank-key':runtime.TANK_API_KEY,'x-tervory-tenant':str(TENANT),
        'x-tervory-user':'founder','x-tervory-squad':'radix','x-tervory-region':'us-east'}
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as room_http:
        runtime._http=room_http
        async with httpx.AsyncClient(transport=httpx.ASGITransport(runtime.app),base_url='http://placeholder') as client:
            payload={'tenant_id':str(TENANT),**ARGS}
            assert (await client.post('/v1/radix/passive/active',json=payload,headers=headers)).status_code==409
            headers['x-tervory-user']='placeholder-client'
            assert (await client.post('/v1/radix/passive/active',json=payload,headers=headers)).status_code==403
            token=CONFIRMED.set((TENANT,'founder',uuid4(),TOOL,{'url':'https://placeholder.example/'}))
            try:
                headers['x-tervory-user']='founder'
                assert (await client.post('/v1/radix/passive/active',json=payload,headers=headers)).status_code==409
            finally: CONFIRMED.reset(token)


@pytest.mark.asyncio
async def test_explicit_active_command_is_planned_by_code_without_model(runtime):
    from types import SimpleNamespace
    from radix_watch import code_plan
    runtime.RouteRequest=lambda **kwargs:SimpleNamespace(**kwargs)
    recorded=[]
    async def record(request,*args,**kwargs):
        recorded.append(kwargs)
        return json.loads(kwargs['content'])
    runtime._record_local=record
    messages=[{'role':'user','content':'radix.active.scan https://tervory.com/'}]
    result=await code_plan(command.Actor(TENANT,'founder',True),messages)
    assert result=={'text':'','actions':[{'tool':TOOL,'arguments':ARGS}]}
    assert recorded[0]['model']=='code'
    with pytest.raises(HTTPException):
        await code_plan(command.Actor(TENANT,'placeholder-client',False,frozenset({'radix'})),messages)
    assert len(recorded)==1
