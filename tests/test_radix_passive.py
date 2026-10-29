"""Defensive scans: fake DNS/CLIs, loopback proxy, opt-in disposable Postgres only."""
from __future__ import annotations

import json
import os
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'agents/radix'), str(ROOT / 'agents/_chassis'), str(ROOT / 'tank')]
import egress
import passive_gateway as gateway
import passive_routes as routes
import passive_store as store
import passive_tools as tools
import radix_passive_routes as corridor

A, B = UUID('11111111-1111-4111-8111-111111111111'), UUID('22222222-2222-4222-8222-222222222222')
TARGET = 'https://owned.example/'
ARTIFACT = 'commit:' + 'a' * 40


@pytest.fixture(autouse=True)
def no_external_network(monkeypatch):
    real = socket.getaddrinfo
    def resolve(host, *args, **kwargs):
        if host not in {'127.0.0.1', '::1', 'localhost'}:
            raise AssertionError('test attempted external DNS')
        return real(host, *args, **kwargs)
    monkeypatch.setattr(socket, 'getaddrinfo', resolve)
    async def no_dns(*args, **kwargs):
        raise AssertionError('test attempted external DNS')
    monkeypatch.setattr(gateway.dns.asyncresolver, 'resolve', no_dns)
    # Lease unit tests use FakeServer/loopback; runtime binds a real private interface.
    monkeypatch.setattr(gateway, 'private_bind_address', lambda: '127.0.0.1')
    monkeypatch.delenv('RADIX_EGRESS_REVOKED', raising=False)


@pytest_asyncio.fixture
async def database():
    url = os.environ.get('RADIX_PASSIVE_TEST_DATABASE_URL', '')
    if not url:
        pytest.skip('set explicit disposable loopback database')
    parsed = urlsplit(url)
    assert parsed.hostname == '127.0.0.1' and parsed.path == '/radix_passive_test' and not parsed.password
    pool = await asyncpg.create_pool(url, min_size=1, max_size=3)
    async with pool.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_radix')
        await conn.execute(store.DDL)
        await conn.execute(store.DDL)
        from scanlib.store import ensure_findings
        await ensure_findings(conn, 'agent_radix')
        await conn.execute('TRUNCATE agent_radix.passive_scans,agent_radix.passive_domains,agent_radix.findings')
    yield store.Store(pool)
    await pool.close()


@pytest.mark.parametrize('target', ['http://owned.example/', 'https://owned.example:443/',
    'https://owned.example/path', 'https://owned.example/?token=x', 'https://owned.example/#x',
    'https://user:pass@owned.example/', 'https://127.0.0.1/', 'https://[::1]/',
    'https://localhost/', 'https://a.internal/', 'https://owned.example./'])
def test_only_exact_https_origin_root(target):
    with pytest.raises(ValueError):
        store.target_url(target)


@pytest.mark.parametrize('artifact', ['latest', 'main', 'commit:' + 'a'*39, 'sha256:' + 'x'*64])
def test_artifact_must_be_immutable(artifact):
    with pytest.raises(ValueError):
        store.artifact_id(artifact)


@pytest.mark.asyncio
async def test_tenant_owns_challenge_and_run(database):
    proof_a = await database.issue(A, 'owned.example')
    proof_b = await database.issue(B, 'owned.example')
    assert proof_a['name'] == '_tervory-verify.owned.example'
    assert proof_a['value'] != proof_b['value']
    ident = await database.create(A, TARGET, ARTIFACT)
    assert (await database.pending(A, ident))['challenge'] == proof_a['value']
    assert await database.pending(B, ident) is None
    assert (await database.gate(B, TARGET, ARTIFACT))['allowed'] is False
    with pytest.raises(PermissionError):
        await database.create(A, 'https://different.example/', ARTIFACT)


class FakeServer:
    def __init__(self, proxy, **kwargs):
        self.proxy, self.closed = proxy, False
    def start(self):
        return self
    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_dns_required_and_verified_run_only_own_tenant(database):
    await database.issue(A, 'owned.example')
    ident = await database.create(A, TARGET, ARTIFACT)
    calls = []
    async def check(domain, challenge):
        calls.append((domain,challenge))
        return False
    lease = gateway.Lease(database, check=check, server=FakeServer)
    for tenant in (B,A):
        with pytest.raises(HTTPException) as err:
            await lease.start(tenant, ident)
        assert err.value.status_code == 403
    assert len(calls) == 1  # Another tenant cannot even request a DNS proof lookup.
    async def yes(*args):
        return True
    lease.check = yes
    assert await lease.start(A, ident) == {'ready': True}
    proxy = lease.proxy_server.proxy
    assert proxy._verified_host == 'owned.example' and proxy._storage_host == ''
    assert proxy._active_lease()
    await lease.release(B, ident)
    assert proxy._active_lease()
    await lease.release(A, ident)
    assert not proxy._active_lease()


@pytest.mark.asyncio
async def test_expired_owner_does_not_permanently_block_other_tenant(database):
    for tenant in (A,B):
        await database.issue(tenant, 'owned.example')
    first = await database.create(A, TARGET, ARTIFACT)
    second = await database.create(B, TARGET, ARTIFACT)
    assert await database.running(A, first)
    # B's tenant operation must not clean or change A's active row.
    with pytest.raises(asyncpg.UniqueViolationError):
        await database.running(B, second)
    async with database.pool.acquire() as conn:
        assert await conn.fetchval('SELECT status FROM agent_radix.passive_scans WHERE tenant_id=$1 AND id=$2', A,first) == 'running'
        await conn.execute("UPDATE agent_radix.passive_scans SET lease_until=now()-interval '1 second' WHERE tenant_id=$1 AND id=$2",A,first)
    # Independent gateway startup/maintenance reaps only elapsed leases by their owners.
    await database.reap_expired()
    assert await database.running(B,second)
    await database.reap_expired()
    async with database.pool.acquire() as conn:
        assert await conn.fetchval('SELECT status FROM agent_radix.passive_scans WHERE tenant_id=$1 AND id=$2',A,first) == 'error'
        assert await conn.fetchval('SELECT status FROM agent_radix.passive_scans WHERE tenant_id=$1 AND id=$2',B,second) == 'running'


@pytest.mark.asyncio
async def test_postgres_receipt_gate_bus_and_restart(database,monkeypatch):
    from chassis import events
    sent=[]
    async def publish(*args,**kwargs):
        sent.append(args)
        return False  # Down bus does not fail the committed product work.
    monkeypatch.setattr(events,'publish',publish)
    await database.issue(A,'owned.example')
    ident=await database.create(A,TARGET,ARTIFACT)
    assert await database.running(A,ident)
    findings=[tools.finding('zap','high','10001',TARGET)]
    await database.complete(A,ident,findings)
    restarted=store.Store(database.pool)
    gate=await restarted.gate(A,TARGET,ARTIFACT)
    assert gate['status']=='complete' and gate['high']==1 and not gate['allowed']
    assert len(await restarted.findings(A,ident))==1
    assert await restarted.findings(B,ident)==[]
    assert not (await restarted.gate(A,'https://other.example/',ARTIFACT))['allowed']
    assert not (await restarted.gate(A,TARGET,'commit:'+'b'*40))['allowed']
    assert sent==[(str(A),'radix.finding',f'{ident}:0',{'scan_id':str(ident),'ordinal':0,'severity':'high'})]
    # A newer failed attempt invalidates the older assessment for that artifact.
    newer=await database.create(A,TARGET,ARTIFACT)
    await database.fail(A,newer)
    assert (await restarted.gate(A,TARGET,ARTIFACT))['status']=='error'


@pytest.mark.parametrize('status,age,high,critical,allowed',[
    ('complete',0,0,0,True),('complete',3601,0,0,False),('complete',-1,0,0,False),
    ('running',0,0,0,False),('pending',0,0,0,False),('error',0,0,0,False),
    ('complete',0,1,0,False),('complete',0,0,1,False)])
def test_gate_fails_closed(status,age,high,critical,allowed):
    now=datetime.now(timezone.utc)
    row={'id':uuid4(),'status':status,'completed_at':now-timedelta(seconds=age),'high':high,'critical':critical}
    assert store.gate_result(row,A,TARGET,ARTIFACT,now=now)['allowed'] is allowed
    assert not store.gate_result(None,A,TARGET,ARTIFACT)['allowed']


def test_proxy_single_host_redirect_storage_and_dns_rebinding(monkeypatch):
    assert egress.parse_connect_target('owned.example:443',verified_host='owned.example')
    for host in ['other.example','sub.owned.example','lokd.co.za','127.0.0.1','metadata.google.internal','account.r2.cloudflarestorage.com']:
        assert egress.parse_connect_target(host+':443',verified_host='owned.example') is None
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw:[(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('127.0.0.1',443))])
    with pytest.raises(egress.ProxyError):
        egress.system_resolve('owned.example',verified_host='owned.example')
    with pytest.raises(egress.ProxyError):
        egress.system_resolve('other.example',verified_host='owned.example')


def test_loopback_proxy_rejects_outside_host_and_expired_lease():
    # Real TCP loopback handshake, injected public resolver/dial never connects externally.
    called=[]
    proxy=egress.Proxy(verified_host='owned.example',allow_storage=False,
        resolve=lambda h:called.append(h) or '93.184.216.34', active=lambda:False)
    server=egress.Server(proxy).start()
    try:
        for host in ['owned.example','outside.example']:
            with socket.create_connection(('127.0.0.1',server.port),timeout=2) as conn:
                conn.sendall(f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode())
                assert b'403' in conn.recv(1024)
        assert called==[]
    finally:
        server.close()


def test_tools_only_passive_no_discovery_and_strip_response_secrets(tmp_path):
    plan=tools.zap_plan(TARGET,tmp_path)
    assert [j['type'] for j in plan['jobs']]==['passiveScan-config','requestor','spider','passiveScan-wait','report']
    assert plan['jobs'][1]['requests']==[{'url':TARGET,'method':'GET','responseCode':200}]
    assert plan['env']['parameters']['failOnWarning'] is True
    spider=plan['jobs'][2]['parameters']
    assert spider['processForm'] is False and spider['postForm'] is False and spider['threadCount']==1
    command=tools.nuclei_command(TARGET,tmp_path/'n.jsonl')
    for flag in ['-no-interactsh','-disable-update-check','-disable-redirects','-no-httpx','-omit-raw','-omit-template']:
        assert flag in command
    assert command[command.index('-t')+1]==tools.TEMPLATE
    raw={'site':[{'@name':TARGET.rstrip('/'),'alerts':[{'riskcode':'3','pluginid':'10001','evidence':'private response','cookie':'private cookie'}]}]}
    result=tools.zap_findings(raw,TARGET)
    assert result==[{'tool':'zap','severity':'high','rule':'10001','file':TARGET,'line':0}]
    with pytest.raises(ValueError):
        tools.zap_findings({'site':[]},TARGET)
    with pytest.raises(ValueError):
        tools.nuclei_findings(json.dumps({'template-id':'active-exploit'}),TARGET)


@pytest.mark.asyncio
async def test_execute_persists_error_not_clean_when_tool_fails(database):
    await database.issue(A,'owned.example')
    async def check(*args):return True
    lease=gateway.Lease(database,check=check,server=FakeServer)
    async def handle(request):
        body=json.loads(request.content)
        if request.url.path=='/lease':
            return httpx.Response(200,json=await lease.start(UUID(body['tenant_id']),UUID(body['scan_id'])))
        await lease.release(UUID(body['tenant_id']),UUID(body['scan_id']))
        return httpx.Response(200,json={'released':True})
    async def fail(*args):raise RuntimeError('fake CLI failed')
    client=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    with pytest.raises(RuntimeError):
        await routes.execute(database,routes.Scan(tenant_id=A,target=TARGET,artifact=ARTIFACT),scanner=fail,http=client)
    assert (await database.gate(A,TARGET,ARTIFACT))['status']=='error'
    assert lease.run is None


@pytest.mark.asyncio
async def test_tisan_gate_corridor_auth_tenant_region_and_unknown_state(monkeypatch):
    monkeypatch.setenv('TANK_KEY_TISAN','offline-tisan-test')
    monkeypatch.setenv('TANK_KEY_RADIX','offline-radix-test')
    calls=[]
    async def handle(request):
        calls.append(request)
        body=json.loads(request.content)
        assert request.headers['x-tervory-tenant']==str(A) and body['tenant_id']==str(A)
        return httpx.Response(200,json={'allowed':False,'status':'missing'})
    http=httpx.AsyncClient(transport=httpx.MockTransport(handle))
    tank=SimpleNamespace(TANK_API_KEY='dummy-workspace-test',_http=http,box_region=lambda:'us-east')
    app=FastAPI();app.include_router(corridor.build_router(tank))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://test') as client:
        headers={'x-tank-key':'offline-tisan-test','x-tervory-tenant':str(A),'x-tervory-squad':'tisan','x-tervory-region':'us-east'}
        payload={'tenant_id':str(A),'target':TARGET,'artifact':ARTIFACT}
        response=await client.post('/v1/radix/passive/gate',json=payload,headers=headers)
        assert response.status_code==200 and not response.json()['allowed']
        for patch in [{'x-tervory-tenant':str(B)},{'x-tervory-region':'za'},{'x-tervory-squad':'tiger'},{'x-tank-key':'not-a-room'}]:
            assert (await client.post('/v1/radix/passive/gate',json=payload,headers={**headers,**patch})).status_code in {401,403}
        assert len(calls)==1
        assert (await client.post('/v1/radix/passive/gate',json={**payload,'allowed':True},headers=headers)).status_code==422
    await http.aclose()


@pytest.mark.asyncio
async def test_txt_chunks_match_exact_challenge_and_dns_failure_refuses(monkeypatch):
    calls=[]
    async def resolve(name,kind,**kwargs):
        calls.append((name,kind))
        return [SimpleNamespace(strings=(b'tervory-',b'dummy-public-dns-proof'))]
    monkeypatch.setattr(gateway.dns.asyncresolver,'resolve',resolve)
    assert await gateway.proof('owned.example','tervory-dummy-public-dns-proof')
    assert not await gateway.proof('owned.example','different-proof')
    assert calls==[('_tervory-verify.owned.example','TXT')]*2
    async def fail(*args,**kwargs):raise gateway.dns.exception.Timeout
    monkeypatch.setattr(gateway.dns.asyncresolver,'resolve',fail)
    assert not await gateway.proof('owned.example','tervory-dummy-public-dns-proof')


def test_verified_dynamic_proxy_relays_only_pinned_public_dial():
    import threading
    calls=[]
    one,two=socket.socketpair()
    def peer():
        with two:
            assert two.recv(10)==b'ping'
            two.sendall(b'pong')
    thread=threading.Thread(target=peer,daemon=True);thread.start()
    def connect(address,port):
        calls.append((address,port));return one
    proxy=egress.Proxy(verified_host='owned.example',allow_storage=False,
        resolve=lambda host:'93.184.216.34',connect=connect)
    server=egress.Server(proxy).start()
    try:
        with socket.create_connection(('127.0.0.1',server.port),timeout=2) as client:
            client.sendall(b'CONNECT owned.example:443 HTTP/1.1\r\nHost: owned.example:443\r\n\r\n')
            assert b'200 Connection Established' in client.recv(1024)
            client.sendall(b'ping');assert client.recv(10)==b'pong'
        assert calls==[('93.184.216.34',443)]
    finally:server.close()


@pytest.mark.asyncio
async def test_complete_request_persists_clean_receipt_and_releases_lease(database,monkeypatch):
    from chassis import events
    async def publish(*args,**kwargs):return True
    monkeypatch.setattr(events,'publish',publish)
    await database.issue(A,'owned.example')
    async def yes(*args):return True
    lease=gateway.Lease(database,check=yes,server=FakeServer)
    async def handle(request):
        body=json.loads(request.content);owner=UUID(body['tenant_id']);ident=UUID(body['scan_id'])
        if request.url.path=='/lease':return httpx.Response(200,json=await lease.start(owner,ident))
        await lease.release(owner,ident);return httpx.Response(200,json={'released':True})
    async def scanner(target,directory):return [tools.finding('zap','low','10001',target)]
    result=await routes.execute(database,routes.Scan(tenant_id=A,target=TARGET,artifact=ARTIFACT),
        scanner=scanner,http=httpx.AsyncClient(transport=httpx.MockTransport(handle)))
    assert result['allowed'] is True and result['status']=='complete' and result['high']==0
    assert result['target']==TARGET and result['artifact']==ARTIFACT and lease.run is None
    assert (await database.gate(A,TARGET,ARTIFACT))['allowed'] is True


@pytest.mark.asyncio
@pytest.mark.parametrize('confirmed',[True,False])
async def test_collect_requires_both_complete_reports_and_actual_nuclei_request(tmp_path,monkeypatch,confirmed):
    seen=[]
    async def run(argv,directory):
        seen.append(argv)
        if len(seen)==1:
            (directory/'zap.json').write_text(json.dumps({'site':[{'@name':TARGET.rstrip('/'),'alerts':[]}]}))
            return 0,b'',b''
        (directory/'nuclei.jsonl').write_text('')
        return 0,(b'{"requests":"1","errors":"0"}' if confirmed else b''),b''
    if confirmed:assert await tools.collect(TARGET,tmp_path,run=run)==[]
    else:
        with pytest.raises(RuntimeError,match='requests unconfirmed'):
            await tools.collect(TARGET,tmp_path,run=run)
    assert len(seen)==2


@pytest.mark.asyncio
@pytest.mark.parametrize('failure',[OSError,asyncpg.PostgresConnectionError])
async def test_gateway_maintenance_recovers_after_transport_failure(monkeypatch,caplog,failure):
    import asyncio
    recovered=asyncio.Event()
    class Pool:
        closed=False
        async def close(self):self.closed=True
    class Maintenance:
        calls=0
        async def reap_expired(self):
            self.calls+=1
            if self.calls==2:raise failure('dummy transport detail not for logs')
            if self.calls>=3:recovered.set()
    pool=Pool();maintenance=Maintenance()
    async def create_pool(*args,**kwargs):return pool
    original_sleep=asyncio.sleep
    async def sleep(seconds):
        assert seconds==15
        if maintenance.calls>=3:await asyncio.Event().wait()
        await original_sleep(0)
    monkeypatch.setenv('DATABASE_URL','postgresql://unused/radix_passive_test')
    monkeypatch.setattr(gateway.asyncpg,'create_pool',create_pool)
    monkeypatch.setattr(gateway,'Store',lambda pool:maintenance)
    monkeypatch.setattr(gateway.asyncio,'sleep',sleep)
    app=SimpleNamespace(state=SimpleNamespace())
    async with gateway.lifespan(app):
        await asyncio.wait_for(recovered.wait(),timeout=2)
        assert maintenance.calls>=3 and not pool.closed
    assert pool.closed
    assert 'will retry' in caplog.text and 'dummy transport detail' not in caplog.text


@pytest.mark.parametrize('address',[None,'0.0.0.0','127.0.0.1','8.8.8.8','169.254.1.1'])
def test_private_listener_refuses_missing_wildcard_and_public_interface(monkeypatch,address):
    def ioctl(*args):
        if address is None:raise OSError('interface missing')
        return bytes(20)+socket.inet_aton(address)+bytes(232)
    monkeypatch.setattr(egress.fcntl,'ioctl',ioctl)
    with pytest.raises(egress.ProxyError):egress.private_bind_address()


def test_private_listener_uses_exact_container_interface(monkeypatch):
    seen=[]
    def ioctl(fd,operation,interface):
        seen.append((operation,interface.rstrip(b'\x00')))
        return bytes(20)+socket.inet_aton('172.22.0.2')+bytes(232)
    monkeypatch.setattr(egress.fcntl,'ioctl',ioctl)
    # Other NICs/ambiguous hostname DNS cannot influence designated radix-link.
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**kw: (_ for _ in ()).throw(AssertionError('must not resolve hostname')))
    assert egress.private_bind_address()=='172.22.0.2' and seen==[(0x8915,b'radix-link')]


@pytest.mark.asyncio
async def test_zap_root_load_warning_refuses_assessment_before_nuclei(tmp_path):
    seen=[]
    async def warning(argv,directory):
        seen.append(argv)
        return 2,b'',b''
    with pytest.raises(RuntimeError,match='baseline incomplete'):
        await tools.collect(TARGET,tmp_path,run=warning)
    assert len(seen)==1
