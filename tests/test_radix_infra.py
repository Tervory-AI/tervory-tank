"""Fake targets and real bounded TCP proxy; no target outside loopback is dialled."""
import errno
import json
import socket
import threading
from uuid import UUID

import dns.message
import dns.rrset
import httpx
import pytest
from fastapi import HTTPException

from test_radix_passive import database as database,FakeServer,A,B
from passive_store import watch_artifact
import passive_gateway
import active_routes
import passive_infra_proxy as policy
import passive_infra_tools as tools
from egress import BOUNDS

DOMAIN='placeholder.example'
TARGET='https://placeholder.example/'


def request(proxy,payload):
    client,server=socket.socketpair()
    task=threading.Thread(target=proxy.handle,args=(server,),daemon=True);task.start()
    client.settimeout(2);client.sendall(payload)
    output=b''
    while True:
        part=client.recv(65536)
        if not part:break
        output+=part
    client.close();task.join(2)
    return output


def test_proxy_scope_ports_public_address_dns_and_shared_bounds():
    calls=[]
    def connect(address,port):
        calls.append((address,port));raise ConnectionRefusedError(errno.ECONNREFUSED,'placeholder closed')
    def exchange(payload,domain):
        calls.append(('dns',domain));return dns.message.make_response(dns.message.from_wire(payload)).to_wire()
    proxy=policy.InfraProxy(verified_host=DOMAIN,allow_storage=False,resolve=lambda _: '93.184.216.34',connect=connect,
        dns_exchange=exchange,max_concurrent=2,max_requests_per_minute=120,max_response_bytes=2_000_000,max_duration_seconds=30)
    assert len(policy.top_ports())==100 and 80 in policy.top_ports() and 22 in policy.top_ports()
    for target in ['placeholder.other:80','sub.placeholder.example:80','placeholder.example:65000','93.184.216.34:80']:
        assert b'403' in request(proxy,f'CONNECT {target} HTTP/1.1\r\n\r\n'.encode())
    assert calls==[]
    assert b'502' in request(proxy,b'CONNECT placeholder.example:22 HTTP/1.1\r\n\r\n')
    assert calls==[('93.184.216.34',22)]
    def packet(name):
        body=dns.message.make_query(name,'A').to_wire()
        return f'POST /infra/dns HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n'.encode()+body
    for name in [DOMAIN,'placeholder.other','www.placeholder.other']:
        assert b'503' in request(proxy,packet(name))
    assert len(calls)==1
    assert b'200' in request(proxy,packet('www.'+DOMAIN)) and calls[-1]==('dns',DOMAIN)
    private=policy.InfraProxy(verified_host=DOMAIN,allow_storage=False,resolve=lambda _:'127.0.0.1',connect=connect)
    assert b'503' in request(private,b'CONNECT placeholder.example:22 HTTP/1.1\r\n\r\n') and len(calls)==2
    assert BOUNDS=={'max_concurrent':2,'max_requests_per_minute':6,'max_response_bytes':1_000_000,'max_duration_seconds':20}
    assert proxy._admit(False) and proxy._admit(False) and not proxy._admit(False)
    proxy._release(False);proxy._release(False)


@pytest.mark.asyncio
async def test_infra_admission_refuses_no_consent_or_txt_and_uses_one_lock(database,monkeypatch):
    monkeypatch.setattr(passive_gateway,'private_bind_address',lambda:'127.0.0.1')
    await database.issue(A,DOMAIN)
    async def forbidden(*args):raise AssertionError('placeholder request without consent')
    with pytest.raises(PermissionError):
        await active_routes.execute(database,A,TARGET,client=True,infra=True,scanner=forbidden,
            http=httpx.AsyncClient(transport=httpx.MockTransport(forbidden)))
    consent=await database.consent(A,DOMAIN,'placeholder-admin','placeholder consent')
    ident=await database.create(A,TARGET,watch_artifact(DOMAIN),active=True,infra=True,consent_id=UUID(consent['id']))
    async def proof(*args):return True
    lease=passive_gateway.Lease(database,check=proof,server=FakeServer)
    with pytest.raises(HTTPException):await lease.start(A,ident,active=True) # Mode cannot be escalated.
    await lease.start(A,ident,active=True,infra=True)
    assert isinstance(lease.proxy_server.proxy,policy.InfraProxy)
    passive=await database.create(A,TARGET,watch_artifact(DOMAIN))
    second=passive_gateway.Lease(database,check=proof,server=FakeServer)
    with pytest.raises(HTTPException) as error:await second.start(A,passive)
    assert error.value.status_code==409
    await lease.release(A,ident)
    await second.start(A,passive);await second.release(A,passive)
    await database.withdraw_consent(A,DOMAIN,'placeholder-admin')
    with pytest.raises(PermissionError):
        await database.create(A,TARGET,watch_artifact(DOMAIN),active=True,infra=True,consent_id=UUID(consent['id']))
    with pytest.raises(PermissionError):
        await database.create(B,TARGET,watch_artifact(DOMAIN),active=True,infra=True,consent_id=UUID(consent['id']))


@pytest.mark.asyncio
@pytest.mark.parametrize('covered',[True,False])
async def test_collector_flags_proxy_coverage_and_keeps_tool_findings(tmp_path,covered):
    async def run(argv,directory,seconds):
        if '/usr/bin/nmap' in argv:
            assert '-sT' in argv and '-Pn' in argv and '-n' in argv and '--max-parallelism' in argv
            assert not any(x in argv for x in ['-sS','-sV','-sC','--script','-A'])
            assert len(argv[argv.index('-p')+1].split(','))==100
            (directory/'nmap.xml').write_text('<nmaprun><host><ports><port protocol="tcp" portid="80"><state state="open"/><service name="http"/></port></ports></host><runstats><finished exit="success"/></runstats></nmaprun>')
            return 0,b'',b''
        assert argv[0]=='/usr/local/bin/dnsx' and '-duc' in argv
        assert (directory/'domains.txt').read_text().splitlines()==['www.'+DOMAIN,'api.'+DOMAIN,'mail.'+DOMAIN]
        return 0,json.dumps({'host':'www.'+DOMAIN,'a':['93.184.216.34'],'rcode':'NOERROR'}).encode(),b''
    async def peer(request):
        return httpx.Response(200,json={'ports':sorted(policy.top_ports()) if covered else [80],
            'dns_names':['www.'+DOMAIN,'api.'+DOMAIN,'mail.'+DOMAIN] if covered else [],'errors':0,'refused':0})
    data=await tools.collect(TARGET,tmp_path,run=run,proxy_ip='127.0.0.1',transport=httpx.MockTransport(peer))
    assert data['checks']['active']['status']==('complete' if covered else 'partial')
    assert {f['tool'] for f in data['findings']}=={'nmap','dnsx'}
    assert all(json.loads(f['fix'])['_measured']['mode']=='infra' for f in data['findings'])
