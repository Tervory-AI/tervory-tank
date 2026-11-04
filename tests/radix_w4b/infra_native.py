"""Real nmap/proxychains/dnsx with fake upstreams inside --network none."""
import asyncio
import errno
import json
from pathlib import Path
import socket
import sys
import tempfile

sys.path.insert(0,'/source')
import dns.message
import dns.rrset
from egress import Server
from passive_infra_proxy import InfraProxy,top_ports
import passive_infra_tools as tools


async def main():
    dials=[];queries=[]
    def connect(address,port):
        assert address=='93.184.216.34' and port in top_ports()
        dials.append(port)
        if port!=80:raise ConnectionRefusedError(errno.ECONNREFUSED,'placeholder closed')
        client,peer=socket.socketpair();peer.close();return client
    def exchange(payload,domain):
        query=dns.message.from_wire(payload)
        name=query.question[0].name.to_text().rstrip('.')
        assert name.endswith('.placeholder.example')
        queries.append(name)
        response=dns.message.make_response(query)
        kind=query.question[0].rdtype
        if kind==1:response.answer.append(dns.rrset.from_text(name+'.',60,'IN','A','93.184.216.34'))
        output=response.to_wire()
        return output
    proxy=InfraProxy(verified_host='placeholder.example',allow_storage=False,
        resolve=lambda _: '93.184.216.34',connect=connect,dns_exchange=exchange,
        max_concurrent=2,max_requests_per_minute=120,max_response_bytes=2_000_000,max_duration_seconds=30)
    server=Server(proxy,host='127.0.0.1',port=8082).start()
    tools.PROXY='http://127.0.0.1:8082'  # Test-only fixed peer seam, no production override.
    async def run(argv,directory,seconds):
        result=await tools.command(argv,directory,seconds)
        if result[0]:print('placeholder CLI failure',result,flush=True)
        return result
    try:
        with tempfile.TemporaryDirectory(prefix='placeholder-infra-') as directory:
            result=await tools.collect('https://placeholder.example/',Path(directory),proxy_ip='127.0.0.1',run=run)
        assert set(dials)==set(top_ports()),(len(dials),result)
        assert set(queries)=={'www.placeholder.example','api.placeholder.example','mail.placeholder.example'},queries
        assert result['checks']['active']['status']=='complete',result
        assert any(f['tool']=='nmap' and f['rule']=='tcp/80' for f in result['findings']),result
        assert any(f['tool']=='dnsx' for f in result['findings']),result
        print(json.dumps({'checks':result['checks'],'tcp_dials':len(dials),'dns_queries':len(queries),
            'findings':len(result['findings']),'all_targets_fake':True,'network':'none'}))
    finally:server.close()

asyncio.run(main())
