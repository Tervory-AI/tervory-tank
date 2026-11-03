"""Real ZAP through the real active proxy, synthetic TLS, Docker --network none.

Only test-only DNS/dial injection maps a pinned public address to loopback.
No allowlist or production proxy policy is changed. No live scan is performed.
"""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import ssl
import subprocess
import tempfile
import threading
import sys

sys.path.insert(0,'/app')
import active_tools
from active_policy import BOUNDS
from egress import Proxy, Server

TARGET='https://tervory.com/'
MODE=sys.argv[1] if len(sys.argv)>1 else 'complete'
requests=[]


class Page(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        requests.append(self.path)
        self.send_response(403 if MODE=='blocked' else 200)
        self.send_header('Content-Type','text/html')
        self.end_headers()
        links=(b''.join(f'<a href="/placeholder-{i}">placeholder</a>'.encode() for i in range(65))
            if MODE=='cap' and self.path=='/' else b'<a href="/placeholder?input=placeholder">placeholder</a>' if self.path=='/' else b'')
        self.wfile.write(b'<html><title>placeholder</title>'+links+b'<p>placeholder</p></html>')
    def do_POST(self): self.do_GET()


async def main():
    with tempfile.TemporaryDirectory(prefix='placeholder-i2-') as tmp:
        directory=Path(tmp)
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','10',
            '-keyout',str(directory/'placeholder.key'),'-out',str(directory/'placeholder.pem'),
            '-subj','/CN=tervory.com','-addext','subjectAltName=DNS:tervory.com'],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        site=ThreadingHTTPServer(('127.0.0.1',0),Page)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.maximum_version=ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(directory/'placeholder.pem',directory/'placeholder.key')
        site.socket=context.wrap_socket(site.socket,server_side=True)
        threading.Thread(target=site.serve_forever,daemon=True).start()
        dials=[]
        def resolve(host):
            assert host=='tervory.com'
            return '93.184.216.34'
        def connect(ip,port):
            assert ip=='93.184.216.34' and port==443
            dials.append((ip,port))
            return socket.create_connection(('127.0.0.1',site.server_port),timeout=5)
        proxy=Proxy(**BOUNDS,verified_host='tervory.com',allow_storage=False,require_sni=True,
            resolve=resolve,connect=connect)
        server=Server(proxy,host='127.0.0.1',port=8082).start()
        for authority in ('other-placeholder.example:443','tervory.com:80'):
            with socket.create_connection(('127.0.0.1',8082),timeout=3) as refused:
                refused.sendall(('CONNECT '+authority+' HTTP/1.1\r\nHost: '+authority+'\r\n\r\n').encode())
                assert b'403' in refused.recv(256)
        assert not dials
        outputs=[]
        async def run(argv,directory,seconds):
            result=await active_tools.command(argv,directory,seconds)
            outputs.append(result[1].decode(errors='replace'))
            log=directory/'zap-home/zap.log'
            if log.exists():
                outputs.append('\n'.join(line for line in log.read_text(errors='replace').splitlines() if any(key in line for key in ('HostProcess','ActiveScan','Scanner','Policy','ERROR','WARN'))))
            return result
        try:
            result=await active_tools.collect(TARGET,directory,run=run)
            coverage=json.loads((directory/'coverage.json').read_text()) if (directory/'coverage.json').exists() else {}
            print(json.dumps({'mode':MODE,'checks':result['checks'],'coverage':coverage,
                'findings':len(result['findings']),'proxy_dials':len(dials),'site_requests':len(requests)}),flush=True)
            if not coverage or result['checks']['active'].get('reason') in {'scanner_unavailable','coverage_unconfirmed','report_incomplete'}:
                print('\n'.join(outputs),flush=True)
            assert coverage.get('requests') and dials
            if MODE=='complete':
                assert coverage.get('active_requests') and result['checks']['active']['status']=='complete'
            elif MODE=='cap':
                assert coverage['capped'] and coverage['spider_urls']==50
                assert result['checks']['active']['status']=='partial'
            else:
                assert result['checks']['active']['status']=='partial'
            print('PASS: actual ZAP with exact-host active proxy and unchanged passive bounds',flush=True)
        finally:
            server.close();site.shutdown()


asyncio.run(main())
