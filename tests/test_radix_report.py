"""I7 real Command and private downloads, offline findings and no model."""
from uuid import UUID
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException,FastAPI

import command
import radix_report as report
from test_radix_passive import database as database
from test_command import TENANT,OTHER,runtime as runtime,command_pool as command_pool,api as api

JOB=UUID('33333333-3333-4333-8333-333333333333')


def fixture(count=12):
    return {'scan_id':str(JOB),'status':'complete','findings':[
        {'tool':'placeholder-tool','rule':f'placeholder-rule-{i}','severity':'critical' if i%2 else 'low',
         'file':f'placeholder-{i}.py','line':i+1,'explanation':f'placeholder own title {i} <script>placeholder</script>',
         'remediation':f'placeholder upstream fix {i}'} for i in range(count)]}


def test_every_finding_escaped_counts_and_private_evidence_links(monkeypatch):
    monkeypatch.delenv('TERVORY_WORKSPACE_URL',raising=False)
    data=fixture()
    text=report.render(JOB,data)
    assert text.count('<article>')==12 and '<dt>critical</dt><dd>6</dd>' in text
    assert '<dt>low</dt><dd>6</dd>' in text and '<script>' not in text and '&lt;script&gt;' in text
    for i in range(12):
        assert f'placeholder-rule-{i}' in text and f'placeholder upstream fix {i}' in text
        assert f'https://app.tervory.com/chats/api/radix/reports/{JOB}/evidence/{i}' in text
    data.update(repository='Tervory-AI/tervory-tank',commit='a'*40)
    assert '/blob/'+('a'*40)+'/placeholder-0.py#L1' in report.render(JOB,data)
    observed=fixture(1);observed['findings'][0]['file']='https://placeholder.example/'
    assert f'/reports/{JOB}/evidence/0' in report.render(JOB,observed)
    assert 'href="https://placeholder.example/' not in report.render(JOB,observed)
    bad=fixture(1);bad['findings'][0]['file']='javascript:placeholder'
    assert 'href="javascript:' not in report.render(JOB,bad)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind',['repo','passive','watch','active'])
async def test_real_scan_kinds_download_tenant_scoped_with_zero_receipt(api,runtime,monkeypatch,kind):
    client,pool=api;runtime.pool=lambda:pool;runtime.app=FastAPI();runtime.app.include_router(command.router)
    runtime.run_route=AsyncMock(side_effect=AssertionError('placeholder model called'))
    monkeypatch.setattr(report,'pdf_available',lambda:False)
    calls=[]
    async def room(method,agent,path,params=None,**kwargs):
        tenant=params['tenant_id'];calls.append((path,tenant))
        if tenant!=str(TENANT): return httpx.Response(404,json={})
        data=fixture()
        if path.startswith('/jobs/'):
            if kind!='repo': return httpx.Response(404,json={})
            # R5's actual tenant/job/type validation remains active.
            result={**data,'tenant_id':str(TENANT),'scan_complete':True,
                'findings':[{**row,'fix':row['remediation']} for row in data['findings']]}
            return httpx.Response(200,json={'id':str(JOB),'tenant_id':str(TENANT),'kind':'scan','status':'done','result':result})
        assert path==f'/passive/scans/{JOB}/report'
        return httpx.Response(200,json={**data,'tenant_id':str(TENANT),'active':kind=='active'})
    monkeypatch.setattr('ghost_routes.call_room',room)
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    card=(await client.post(f'/v1/command/threads/{thread}/actions',json={'tool':'radix.report','arguments':{'scan_id':str(JOB)}})).json()
    assert card['status']=='pending' and calls==[]
    response=await client.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm'})
    assert response.status_code==200,response.text
    result=response.json();assert result['status']=='confirmed',result
    data=result['result'];assert data['url']==f'https://app.tervory.com/chats/api/radix/reports/{JOB}/html'
    assert 'pdf_url' not in data and data['cost_usd']==0
    async with pool.acquire() as conn:
        receipt=await conn.fetchrow('SELECT cost_usd,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2',TENANT,UUID(data['ledger_id']))
        assert receipt['cost_usd']==0 and receipt['model']=='code'
    file=await client.get(f'/v1/command/radix/reports/{JOB}/html')
    assert file.status_code==200 and file.text.count('<article>')==12
    assert file.headers['content-disposition'].endswith('.html')
    assert file.headers['cache-control']=='private, no-store' and 'sandbox' in file.headers['content-security-policy']
    other=await client.get(f'/v1/command/radix/reports/{JOB}/html',headers={'x-tervory-tenant':str(OTHER)})
    assert other.status_code==404
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'radix','placeholder-founder')",TENANT)
    customer=await client.get(f'/v1/command/radix/reports/{JOB}/html',headers={'x-tervory-user':'placeholder-client'})
    assert customer.status_code==200 and customer.text.count('<article>')==12
    evidence=await client.get(f'/v1/command/radix/reports/{JOB}/evidence/11')
    assert evidence.status_code==200 and evidence.json()['rule']=='placeholder-rule-11'
    assert (await client.get(f'/v1/command/radix/reports/{JOB}/pdf')).status_code==404
    runtime.run_route.assert_not_called()


@pytest.mark.asyncio
async def test_clients_need_radix_and_cannot_select_tenant_or_pdf_imports(runtime,monkeypatch):
    actor=command.Actor(TENANT,'placeholder-client',False,frozenset({'radix'}))
    assert 'radix.report' in command.allowed_tools(actor)
    assert 'radix.report' not in command.allowed_tools(command.Actor(TENANT,'placeholder-client',False))
    with pytest.raises(HTTPException):
        command.validate_action(command.PlannedAction(tool='radix.report',arguments={'scan_id':str(JOB),'tenant_id':str(OTHER)}),actor)
    async def findings(*args): return {**fixture(0),'scan_complete':False}
    monkeypatch.setattr('radix_repo.findings',findings)
    data=await report.load(actor,JOB)
    assert data['status']=='failed' and '<dd>failed</dd>' in report.render(JOB,data)


@pytest.mark.asyncio
async def test_real_scan_required_pending_and_unknown_are_not_reports(runtime,monkeypatch):
    async def findings(*args): return {'scan_id':str(JOB),'status':'pending'}
    monkeypatch.setattr('radix_repo.findings',findings)
    with pytest.raises(HTTPException) as error:
        await report.load(command.Actor(TENANT,'founder',True),JOB)
    assert error.value.status_code==409


def test_actual_workspace_download_corridor_and_existing_result_label():
    import subprocess
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node',str(root/'tests/radix_i7/workspace.cjs')],cwd=root,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr


@pytest.mark.asyncio
async def test_actual_private_room_corridor_carries_actor_tenant_header(api,runtime,database,monkeypatch):
    import passive_routes
    from passive_store import watch_artifact
    await database.issue(TENANT,'placeholder.example')
    ident=await database.create(TENANT,'https://placeholder.example/',watch_artifact('placeholder.example'))
    await database.running(TENANT,ident)
    await database.complete(TENANT,ident,[{'tool':'zap','rule':'placeholder-rule','severity':'low',
        'file':'https://placeholder.example/','line':0}])
    room=FastAPI();room.state.pool=database.pool
    passive_routes.attach(room)
    monkeypatch.setenv('TANK_KEY','placeholder-room-key');monkeypatch.setenv('TANK_KEY_RADIX','placeholder-room-key')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room)) as http:
        runtime._http=http
        actor=command.Actor(TENANT,'founder',True)
        data=await report.load(actor,ident)
        assert data['findings'][0]['rule']=='placeholder-rule'
        with pytest.raises(HTTPException) as error:
            await report.load(command.Actor(OTHER,'founder',True),ident)
        assert error.value.status_code==404
