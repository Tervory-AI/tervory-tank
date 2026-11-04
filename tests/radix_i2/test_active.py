"""Founder-only active scans, fake scanners and disposable tenant DB; no live site."""
import json
from pathlib import Path
import sys

import httpx
import pytest
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'agents/radix'), str(ROOT/'tests/radix_i8')]
from test_events import pool as pool, A, B
import active_policy as policy
import active_routes as routes
import active_tools as tools
import passive_gateway as gateway
import passive_store as store
from egress import BOUNDS as PASSIVE_BOUNDS
from test_radix_passive import FakeServer

DOMAIN = 'tervory.com'
TARGET = 'https://tervory.com/'


def report():
    return {'site': [{'@name': TARGET[:-1], 'alerts': [{'pluginid': '40012', 'riskcode': '2',
        'desc': '<p>placeholder upstream description</p>', 'solution': 'placeholder upstream fix'}]}]}


def test_allowlist_and_plan(tmp_path):
    assert json.loads((ROOT/'agents/radix/active-domains.json').read_text()) == [DOMAIN]
    assert policy.active_target(TARGET) == (TARGET, DOMAIN)
    for url in ['https://placeholder.example/', 'https://sub.tervory.com/', 'https://tervory.com:443/',
                'http://tervory.com/', 'https://tervory.com/path', 'https://tervory.com/?placeholder=1']:
        with pytest.raises((PermissionError, ValueError)):
            policy.active_target(url)
    plan = tools.zap_plan(TARGET, tmp_path)
    jobs = {row['type']: row for row in plan['jobs']}
    assert jobs['spider']['parameters']['maxDuration'] == 5
    assert jobs['spider']['parameters']['postForm'] is False
    active = jobs['activeScan']
    assert active['parameters']['context']=='verified-active' and 'url' not in active['parameters']
    assert active['parameters']['threadPerHost'] == 2
    assert active['parameters']['maxRuleDurationInMins'] == 2
    assert active['parameters']['maxScanDurationInMins'] == 14
    assert active['policyDefinition']['defaultStrength'] == 'LOW'
    assert all(r['threshold'] == 'MEDIUM' for r in active['policyDefinition']['rules'])
    assert 'addOns' not in jobs and tools.RULES == (40003,40012,40018)
    args = tools.zap_command(tmp_path/'placeholder.yaml', tmp_path/'placeholder-home')
    assert 'network.connection.httpProxy.enabled=true' in args
    assert 'network.connection.httpProxy.host=radix-passive-proxy' in args
    assert 'network.connection.httpProxy.port=8082' in args
    assert all('addonupdate' not in value and 'addoninstall' not in value for value in args)
    assert PASSIVE_BOUNDS == {'max_concurrent':2,'max_requests_per_minute':6,
        'max_response_bytes':1_000_000,'max_duration_seconds':20}
    assert policy.BOUNDS == {'max_concurrent':2,'max_requests_per_minute':120,
        'max_response_bytes':2_000_000,'max_duration_seconds':30}


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['complete','blocked','timeout','empty','bad-report','cap','lost-response','rule-timeout'])
async def test_collect_never_calls_blocked_or_timeout_clean(tmp_path, mode):
    async def run(argv, directory, seconds):
        assert seconds == 1200 and argv[0] == '/opt/zap/zap.sh'
        assert '__HOST__' not in (directory/'guard.js').read_text()
        if mode == 'timeout':
            raise TimeoutError('placeholder')
        coverage = {'requests': 2, 'responses': 2, 'active_requests': 1, 'active_responses': 1, 'blocked':mode=='blocked',
            'capped':mode=='cap', 'refused':0}
        if mode=='lost-response': coverage['responses']=1
        if mode=='rule-timeout':
            (directory/'zap-home').mkdir()
            (directory/'zap-home/zap.log').write_text('placeholder skipped plugin [maximum rule duration]')
        (directory/'coverage.json').write_text(json.dumps(coverage))
        (directory/'zap.json').write_text(json.dumps({} if mode=='bad-report' else report()))
        return (1 if mode=='empty' else 0), b'placeholder', b''
    result = await tools.collect(TARGET,tmp_path,run=run)
    assert result['checks']['active']['status'] == ('complete' if mode=='complete' else 'partial')
    if result['findings']:
        item = store.report_finding(result['findings'][0])
        assert item['tool'] == 'zap' and item['active'] and item['mode']=='active'
        assert item['explanation']=='placeholder upstream description'


@pytest.mark.asyncio
async def test_unlisted_and_unproved_before_any_http(pool):
    database = store.Store(pool)
    for tenant,url in [(A,'https://placeholder.example/'),(A,TARGET),(B,TARGET)]:
        async def scanner(*args): raise AssertionError('placeholder scanner called')
        async def request(*args): raise AssertionError('placeholder HTTP called')
        with pytest.raises(PermissionError):
            await routes.execute(database,tenant,url,scanner=scanner,
                http=httpx.AsyncClient(transport=httpx.MockTransport(request)))
    # Another tenant's proof cannot authorize this workspace.
    await database.issue(A,DOMAIN)
    with pytest.raises(PermissionError):
        await database.create(B,TARGET,store.watch_artifact(DOMAIN),active=True)


@pytest.mark.asyncio
async def test_runtime_txt_and_mode_cannot_be_bypassed(pool,monkeypatch):
    monkeypatch.setattr(gateway, 'private_bind_address', lambda: '127.0.0.1')
    database=store.Store(pool)
    await database.issue(A,DOMAIN)
    ident=await database.create(A,TARGET,store.watch_artifact(DOMAIN),active=True)
    calls=[]
    async def check(*args): calls.append('placeholder-dns'); return False
    lease=gateway.Lease(database,check=check,server=FakeServer)
    with pytest.raises(HTTPException) as error: await lease.start(B,ident,active=True)
    assert error.value.status_code==403 and calls==[]
    with pytest.raises(HTTPException): await lease.start(A,ident)
    assert calls==[]
    with pytest.raises(HTTPException): await lease.start(A,ident,active=True)
    assert calls==['placeholder-dns'] and lease.proxy_server is None


@pytest.mark.asyncio
async def test_shared_running_lock_lease_and_active_results(pool,monkeypatch):
    monkeypatch.setattr(gateway, 'private_bind_address', lambda: '127.0.0.1')
    database=store.Store(pool)
    await database.issue(A,DOMAIN)
    async def yes(*args): return True
    clock=[100.0]
    lease=gateway.Lease(database,check=yes,server=FakeServer,now=lambda:clock[0])
    passive=await database.create(A,TARGET,store.watch_artifact(DOMAIN))
    active=await database.create(A,TARGET,store.watch_artifact(DOMAIN),active=True)
    await lease.start(A,active,active=True)
    assert lease.until==1900
    proxy=lease.proxy_server.proxy
    assert (proxy._max_concurrent,proxy._max_per_minute,proxy._max_bytes,proxy._max_duration)==(2,120,2_000_000,30)
    with pytest.raises(HTTPException) as error: await lease.start(A,passive)
    assert error.value.status_code==409
    second=gateway.Lease(database,check=yes,server=FakeServer)
    with pytest.raises(HTTPException) as error: await second.start(A,passive)
    assert error.value.status_code==409  # Same database index across gateway instances.
    item=tools.zap_findings(report(),TARGET)[0]
    data=json.loads(item['fix']);data['_measured']={'active':True,'mode':'active'};item['fix']=json.dumps(data)
    await database.complete(A,active,[item],measurements={'checks':{'active':{'status':'complete'}}})
    assert (await database.changes(A,DOMAIN))['active']
    assert (await database.changes(B,DOMAIN))=={'status':'pending'}
    assert (await database.findings(A,active))[0]['active']
    assert await database.findings(B,active)==[]
    assert (await database.gate(A,TARGET,store.watch_artifact(DOMAIN)))['allowed'] is False
    await lease.release(A,active)
    assert not proxy._active_lease()
    await second.start(A,passive)
    assert (second.proxy_server.proxy._max_per_minute,second.until>0)==(6,True)
    await second.release(A,passive)


@pytest.mark.asyncio
async def test_timeout_persisted_incomplete_and_lease_released(pool,monkeypatch):
    monkeypatch.setattr(gateway, 'private_bind_address', lambda: '127.0.0.1')
    database=store.Store(pool)
    await database.issue(A,DOMAIN)
    async def yes(*args): return True
    lease=gateway.Lease(database,check=yes,server=FakeServer)
    async def control(request):
        body=json.loads(request.content)
        if request.url.path=='/active/lease': await lease.start(A,__import__('uuid').UUID(body['scan_id']),active=True)
        else: await lease.release(A,__import__('uuid').UUID(body['scan_id']))
        return httpx.Response(200,json={'ready':True})
    async def scan(*args): raise TimeoutError('placeholder timeout')
    result=await routes.execute(database,A,TARGET,scanner=scan,http=httpx.AsyncClient(transport=httpx.MockTransport(control)))
    assert result['status']=='failed' and result['checks']['active']['reason']=='scan_timeout'
    changes=await database.changes(A,DOMAIN)
    assert changes['status']=='failed' and changes['checks']['active']['status']=='partial'
    assert changes['findings']==[] and lease.run is None
    state=await database.active_state(A,__import__('uuid').UUID(result['scan_id']))
    assert state['status']=='failed' and state['checks']['active']['reason']=='scan_timeout'
    assert await database.active_state(B,__import__('uuid').UUID(result['scan_id']))=={}
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM agent_radix.passive_scans WHERE status='running'")==0


@pytest.mark.asyncio
async def test_incomplete_active_does_not_fix_prior_or_mix_passive_baselines(pool):
    database=store.Store(pool)
    await database.issue(A,DOMAIN)
    artifact=store.watch_artifact(DOMAIN)
    for active,items,status in [(False,[{'tool':'zap','rule':'10001','severity':'low','file':TARGET,'line':0}],'complete'),
            (True,tools.zap_findings(report(),TARGET),'complete'),(True,[],'partial')]:
        ident=await database.create(A,TARGET,artifact,active=active)
        await database.running(A,ident)
        await database.complete(A,ident,items,measurements={'checks':{'active':{'status':status}}} if active else None)
        changes=await database.changes(A,DOMAIN)
        if active:
            assert changes['fixed']==[]
    assert changes['status']=='failed' and changes['checks']['active']['status']=='partial'
    assert (await database.gate(A,TARGET,artifact))['status']=='complete'


@pytest.mark.asyncio
async def test_incomplete_active_findings_endpoint_keeps_existing_failed_card_state(pool):
    from fastapi import FastAPI
    import passive_routes
    database=store.Store(pool)
    await database.issue(A,DOMAIN)
    ident=await database.create(A,TARGET,store.watch_artifact(DOMAIN),active=True)
    await database.running(A,ident)
    await database.complete(A,ident,[],measurements={'checks':{'active':{'status':'partial','reason':'placeholder-blocked'}}})
    app=FastAPI();app.state.pool=pool
    app.dependency_overrides[passive_routes.require_tank]=lambda:None
    passive_routes.attach(app)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://placeholder') as client:
        result=await client.get(f'/passive/scans/{ident}/findings',params={'tenant_id':str(A)},headers={'x-tervory-tenant':str(A)})
        assert result.status_code==200 and result.json()['status']=='failed'
        assert result.json()['checks']['active']['reason']=='placeholder-blocked'
        other=await client.get(f'/passive/scans/{ident}/findings',params={'tenant_id':str(B)},headers={'x-tervory-tenant':str(B)})
        assert other.json()=={'findings':[]}
