"""I6 offline: app isolation, fail-open reads, trusted provenance and founder override."""
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID,uuid4

import httpx
import pytest
from fastapi import FastAPI,HTTPException

import command
import radix_deploy as gate
from test_command import TENANT,OTHER,runtime as runtime,command_pool as command_pool,api as api
from test_deploy_changed import _script,_apps
from test_command_radix_repo import repo_api as repo_api

COMMIT='a'*40
JOB=UUID('33333333-3333-4333-8333-333333333333')


def test_deploy_blocks_only_one_app_and_continues_other_apps(monkeypatch,tmp_path):
    mod=_script(monkeypatch)
    monkeypatch.setenv('RADIX_DEPLOY_TENANT_ID',str(TENANT))
    monkeypatch.setenv('RADIX_DEPLOY_TANK_KEY','placeholder-service-key')
    monkeypatch.setenv('GITHUB_STEP_SUMMARY',str(tmp_path/'placeholder-summary'))
    reads=[];deploys=[]
    class Response:
        def __init__(self,app): self.app=app
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def read(self,limit):
            return json.dumps({'app':self.app,'blocked':self.app=='main','findings':[
                {'id':str(JOB),'severity':'critical','commit':COMMIT,'tool':'placeholder-tool','rule':'placeholder-rule','file':'tank/placeholder.py'}
            ] if self.app=='main' else []}).encode()
    def open(request,timeout):
        from urllib.parse import urlsplit,parse_qs
        app=parse_qs(urlsplit(request.full_url).query)['app'][0]
        reads.append(app)
        assert request.get_header('X-tervory-tenant')==str(TENANT) and timeout==10
        return Response(app)
    monkeypatch.setattr(mod.urllib.request,'build_opener',lambda *args:SimpleNamespace(open=open))
    monkeypatch.setattr(mod,'changed_paths',lambda:['tank/placeholder.py','agents/zenas/placeholder.py'])
    monkeypatch.setattr(mod,'api',lambda *args:(200,_apps()))
    monkeypatch.setattr(mod,'deploy',lambda uuid,name:deploys.append(name) or True)
    monkeypatch.setattr(mod,'wait_for',lambda *args:True)
    assert mod.main()==0
    assert 'main' not in deploys and sorted(deploys)==['agent-zenas','agent-zenas-za','tervory-tank-za']
    assert deploys.index('tervory-tank-za') < deploys.index('agent-zenas-za')
    assert set(reads)=={'main',*deploys}
    assert 'placeholder-rule' in (tmp_path/'placeholder-summary').read_text()


def test_unreachable_tank_fails_open_without_disclosing_key(monkeypatch,capsys):
    mod=_script(monkeypatch)
    monkeypatch.setenv('RADIX_DEPLOY_TENANT_ID',str(TENANT))
    monkeypatch.setenv('RADIX_DEPLOY_TANK_KEY','placeholder-never-print')
    def open(*args,**kwargs): raise OSError('placeholder-never-print')
    monkeypatch.setattr(mod.urllib.request,'build_opener',lambda *args:SimpleNamespace(open=open))
    assert mod.radix_blocks('agent-radix') is False
    text=capsys.readouterr().out
    assert 'gate could not be checked; deploy continues' in text and 'placeholder-never-print' not in text


@pytest.mark.asyncio
async def test_scan_materialization_is_tenant_app_and_commit_scoped_then_confirm_override(api,runtime,monkeypatch):
    client,pool=api
    runtime.pool=lambda:pool;runtime.app=FastAPI();runtime.app.include_router(command.router)
    actor=command.Actor(TENANT,'founder',True)
    await gate.register(actor,JOB,COMMIT)
    seen=[]
    async def room(method,agent,path,params):
        seen.append(params['tenant_id'])
        return httpx.Response(200,json={'id':str(JOB),'tenant_id':str(TENANT),'kind':'scan','status':'done',
            'result':{'scan_id':str(JOB),'tenant_id':str(TENANT),'repository':gate.REPOSITORY,'commit':COMMIT,
                'scan_complete':True,'findings':[{'severity':'critical','tool':'placeholder-tool','rule':'placeholder-rule',
                    'file':'agents/radix/placeholder.py','line':2,'fix':'placeholder upstream fix'}]}})
    monkeypatch.setattr('ghost_routes.call_room',room)
    assert (await gate.decision(OTHER,'agent-radix'))['blocked'] is False and not seen
    assert (await gate.decision(TENANT,'main'))['blocked'] is False
    data=await gate.decision(TENANT,'agent-radix')
    finding=data['findings'][0]
    assert data['blocked'] and finding['commit']==COMMIT
    assert not (await gate.decision(TENANT,'agent-zenas'))['blocked']
    assert 'radix.deploy.override' not in command.allowed_tools(command.Actor(TENANT,'placeholder-client',False,frozenset({'radix'}),True))
    args={'app':'agent-radix','finding_id':finding['id']}
    assert (await client.post('/v1/command/radix/deploy/override',json=args)).status_code==409
    thread=(await client.post('/v1/command/threads',json={})).json()['thread_id']
    card=(await client.post(f'/v1/command/threads/{thread}/actions',json={'tool':'radix.deploy.override','arguments':args})).json()
    assert (await gate.decision(TENANT,'agent-radix'))['blocked']
    result=await client.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm'})
    assert result.status_code==200,result.text
    value=result.json();assert value['status']=='confirmed',value
    receipt=UUID(value['result']['ledger_id'])
    async with pool.acquire() as conn:
        row=await conn.fetchrow('SELECT cost_usd,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2',TENANT,receipt)
        assert row['cost_usd']==0 and row['model']=='code'
    assert not (await gate.decision(TENANT,'agent-radix'))['blocked']
    assert (await gate.decision(TENANT,'agent-radix-za'))['blocked']  # Override is one app/observation, no global switch.


@pytest.mark.asyncio
async def test_complete_descendant_scan_resolves_older_partial_scan_cannot_clear(api,runtime,monkeypatch):
    _,pool=api;runtime.pool=lambda:pool
    actor=command.Actor(TENANT,'founder',True)
    jobs={}
    async def room(method,agent,path,params): return httpx.Response(200,json=jobs[path.split('/')[-1]])
    monkeypatch.setattr('ghost_routes.call_room',room)
    async def ancestor(base,head): return base<=head
    monkeypatch.setattr(gate,'ancestor',ancestor)
    for commit,complete,rows in [(COMMIT,True,[{'severity':'critical','tool':'placeholder','rule':'placeholder','file':'agents/radix/placeholder.py'}]),
        ('b'*40,False,[]),('c'*40,True,[])]:
        ident=uuid4();await gate.register(actor,ident,commit)
        jobs[str(ident)]={'id':str(ident),'tenant_id':str(TENANT),'kind':'scan','status':'done','result':
            {'scan_id':str(ident),'tenant_id':str(TENANT),'repository':gate.REPOSITORY,'commit':commit,'scan_complete':complete,'findings':rows}}
        result=await gate.decision(TENANT,'agent-radix')
        assert result['blocked']==(commit!='c'*40)


@pytest.mark.asyncio
async def test_wrong_job_provenance_never_creates_block(api,runtime,monkeypatch):
    _,pool=api;runtime.pool=lambda:pool
    await gate.register(command.Actor(TENANT,'founder',True),JOB,COMMIT)
    async def room(*args,**kwargs): return httpx.Response(200,json={'id':str(JOB),'tenant_id':str(OTHER),'kind':'scan','status':'done','result':{}})
    monkeypatch.setattr('ghost_routes.call_room',room)
    with pytest.raises(HTTPException): await gate.decision(TENANT,'main')
    async with pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.radix_deploy_findings WHERE tenant_id=$1',TENANT)==0


@pytest.mark.asyncio
async def test_only_current_own_main_is_accepted_before_scan(monkeypatch):
    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def github(): yield object()
    async def get(client,path): return ({'object':{'sha':COMMIT}} if path=='git/ref/heads/main' else {'sha':COMMIT}),False
    monkeypatch.setattr('command_repo.github',github);monkeypatch.setattr('command_repo._get',get)
    await gate.verify_main(COMMIT)
    with pytest.raises(HTTPException): await gate.verify_main('b'*40)


def test_immutable_bundle_commit_is_verified_before_scanning(tmp_path,monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'agents/radix'))
    from scanlib import archive
    repo=tmp_path/'placeholder-repo';repo.mkdir()
    def git(*args): return subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
    git('init','-b','main');git('config','user.name','placeholder');git('config','user.email','placeholder@example.com')
    (repo/'placeholder.txt').write_text('placeholder')
    git('add','.');git('commit','-m','placeholder')
    commit=git('rev-parse','HEAD');bundle=tmp_path/'placeholder.bundle';git('bundle','create',str(bundle),'--all')
    root=archive.unpack(bundle.read_bytes(),tmp_path/'placeholder-good',commit=commit)
    assert (root/'placeholder.txt').read_text()=='placeholder'
    with pytest.raises(ValueError,match='bundle commit mismatch'):
        archive.unpack(bundle.read_bytes(),tmp_path/'placeholder-wrong',commit='f'*40)
    with pytest.raises(ValueError,match='bundle commit required'):
        archive.unpack(b'PK\x03\x04',tmp_path/'placeholder-zip',commit=commit)


@pytest.mark.asyncio
async def test_verified_founder_bundle_flows_from_confirmed_repo_scan_to_app_gate(repo_api,tmp_path,monkeypatch):
    from test_command_radix_repo import upload,propose
    from scanlib import orchestrate,iac
    client,pool,runtime=repo_api
    repo=tmp_path/'placeholder-source';repo.mkdir()
    def git(*args): return subprocess.run(['git',*args],cwd=repo,check=True,capture_output=True,text=True).stdout.strip()
    git('init','-b','main');git('config','user.name','placeholder');git('config','user.email','placeholder@example.com')
    folder=repo/'agents/radix';folder.mkdir(parents=True);(folder/'placeholder.py').write_text('placeholder = True')
    git('add','.');git('commit','-m','placeholder');commit=git('rev-parse','HEAD')
    bundle=tmp_path/'placeholder.bundle';git('bundle','create',str(bundle),'--all')
    async def verify(value): assert value==commit
    monkeypatch.setattr(gate,'verify_main',verify)
    def collect(root,status):
        assert (root/'agents/radix/placeholder.py').exists()
        status[iac.TOOL]='run'
        return [{'tool':'scan.static','severity':'critical','rule':'placeholder-rule','file':'agents/radix/placeholder.py','line':1,'fix':'placeholder upstream fix'}],[]
    monkeypatch.setattr(orchestrate,'collect',collect)
    saved={}
    async def room(method,agent,path,body=None,params=None):
        if method=='POST':
            payload=body['input']
            assert payload['commit']==commit and payload['repository']==gate.REPOSITORY
            ctx=SimpleNamespace(input=payload,tenant_id=str(TENANT),job_id=str(JOB),files=object())
            saved.update(id=str(JOB),tenant_id=str(TENANT),kind='scan',status='done',result=orchestrate.build_result(ctx))
            return httpx.Response(201,json={'id':str(JOB),'tenant_id':str(TENANT),'kind':'scan'})
        return httpx.Response(200,json=saved)
    monkeypatch.setattr('ghost_routes.call_room',room)
    thread,attachment=await upload(client,bundle.read_bytes(),name='placeholder.bundle')
    card=await propose(client,thread,'radix.repo.scan',{'attachment_id':attachment,'commit':commit})
    result=await client.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm'})
    assert result.status_code==200 and result.json()['status']=='confirmed',result.text
    data=await gate.decision(TENANT,'agent-radix')
    assert data['blocked'] and data['findings'][0]['commit']==commit
    assert not (await gate.decision(TENANT,'agent-zenas'))['blocked']
