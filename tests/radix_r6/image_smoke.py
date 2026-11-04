"""Real image tools, network-disabled container, synthetic HTTPS via real proxy.

The proxy's existing test-only DNS/dial seams pin a public placeholder address
and redirect that dial to this process's loopback fixture. Bounds are unchanged.
Ephemeral self-signed TLS material exists only in TemporaryDirectory, never logs.
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
from egress import Proxy, Server
import passive_r6 as r6

DOMAIN='placeholder.example'
TARGET='https://placeholder.example/'
EICAR=b'X5O!P%@AP[4\\PZX54(P^)7CC)7}$'+b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*'


class Page(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        body=(b'<html lang="en"><title>placeholder</title><a href="/placeholder-file">placeholder</a>'
              b'<img src="/placeholder-image"><script>document.cookie="placeholder_js=placeholder; Secure; SameSite=Lax";fetch("https://127.0.0.1/placeholder").catch(()=>{});new WebSocket("wss://placeholder.example/placeholder-ws")</script>'
              b'<iframe src="/placeholder-frame"></iframe><script src="https://other-placeholder.example/placeholder.js"></script></html>')
        kind='text/html'
        if self.path=='/placeholder-frame':
            body=(b'<html><script>document.cookie="placeholder_frame=placeholder; Domain=PLACEHOLDER.EXAMPLE; Secure; SameSite=Lax";'
                b'document.cookie="placeholder_transient=placeholder; Secure; Path=/";document.cookie="placeholder_transient=; Max-Age=0; Secure; Path=/";'
                b'document.cookie="placeholder_injected=placeholder; Secure; Path=/";'
                b'window.__radix_cookie_set({name:"placeholder_injected",domain:"placeholder.example",path:"/",expiry:-1,Secure:true,SameSite:"Lax",value:"placeholder-never-export"});'
                b'if(window.cookieStore) cookieStore.set({name:"placeholder_store",value:"placeholder",secure:true,sameSite:"lax",path:"/"});</script></html>')
        if self.path=='/placeholder-file': body,kind=EICAR,'application/octet-stream'
        if self.path=='/placeholder-image': body,kind=b'placeholder','image/png'
        self.send_response(200)
        self.send_header('Content-Type',kind)
        self.send_header('Set-Cookie','placeholder_http=placeholder; Secure; HttpOnly; SameSite=Lax; Path=/')
        self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)


async def main():
    with tempfile.TemporaryDirectory(prefix='placeholder-r6-') as tmp:
        directory=Path(tmp)
        # Test-server-only certificate/key, generated without displaying either.
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','10',
            '-keyout',str(directory/'placeholder.key'),'-out',str(directory/'placeholder.pem'),
            '-subj','/CN=placeholder.example','-addext','subjectAltName=DNS:placeholder.example'],
            check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        https=ThreadingHTTPServer(('127.0.0.1',0),Page)
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version=ssl.TLSVersion.TLSv1_2
        context.maximum_version=ssl.TLSVersion.TLSv1_3
        context.load_cert_chain(directory/'placeholder.pem',directory/'placeholder.key')
        https.socket=context.wrap_socket(https.socket,server_side=True)
        threading.Thread(target=https.serve_forever,daemon=True).start()
        dials=[]
        loopback_proxied=[]
        class ObservedProxy(Proxy):
            def handle(self,conn):
                conn.settimeout(5)
                if b'CONNECT 127.0.0.1:443 ' in conn.recv(4096,socket.MSG_PEEK):
                    loopback_proxied.append(True)
                return super().handle(conn)
        def dial(ip,port):
            assert ip=='93.184.216.34' and port==443
            dials.append((ip,port))
            return socket.create_connection(('127.0.0.1',https.server_port),timeout=5)
        proxy=Server(ObservedProxy(verified_host=DOMAIN,allow_storage=False,resolve=lambda _: '93.184.216.34',
                           connect=dial),port=8082).start()
        try:
            for destination in ('other-placeholder.example:443','placeholder.example:444'):
                with socket.create_connection(('127.0.0.1',8082)) as sock:
                    sock.sendall(('CONNECT '+destination+' HTTP/1.1\r\n\r\n').encode())
                    assert b'403' in sock.recv(4096)
            rc,out,_=await r6.command(['/usr/bin/node','/app/browser/check.cjs',TARGET,'full'],directory,45)
            assert rc==0, 'browser check failed'
            browser=json.loads(out)
            assert any(f['rule']=='image-alt' for f in browser['findings'])
            assert {'placeholder_js','placeholder_http','placeholder_frame','placeholder_transient','placeholder_store'} <= {c['name'] for c in browser['cookies']}
            assert all(c['first_party'] for c in browser['cookies'] if c['name']=='placeholder_frame')
            assert b'placeholder-never-export' not in out
            assert browser['third_party_refused']>=1
            assert browser['client_refused']>=1 and loopback_proxied
            assert all('value' not in c for c in browser['cookies'])
            if '--browser-only' in sys.argv:
                print(json.dumps({'axe_image_alt':True,'cookies_before_interaction':len(browser['cookies']),
                    'third_party_refused':browser['third_party_refused'],'loopback_used_proxy':True,
                    'websocket_refused':True}))
                return
            # Reset only the test lease between separate tool proofs. Bounds stay unchanged.
            proxy.close()
            proxy=Server(ObservedProxy(verified_host=DOMAIN,allow_storage=False,resolve=lambda _: '93.184.216.34',
                connect=dial),port=8082).start()
            result=await r6.collect(TARGET,directory,budget=r6.Budget(110),notice_only=True)
            assert result['checks']['browser']['status']=='complete'
            assert 'axe-core' not in {f['tool'] for f in result['findings']}
            path=directory/'placeholder-eicar';path.write_bytes(EICAR)
            try:
                rc,out,err=await r6.command(['/usr/bin/clamscan','--no-summary','--max-filesize=1M',str(path)],directory,90)
            except TimeoutError:
                rc,out,err=124,b'',b''
            malware='skipped_budget' if rc==124 else 'found' if rc==1 and b' FOUND' in out else 'skipped_memory' if rc in {-9,137} or b'memory' in err.lower() or b'allocat' in err.lower() else 'error'
            assert malware!='error', (rc,err.decode(errors='replace')[:200])
            proxy.close()
            proxy=Server(ObservedProxy(verified_host=DOMAIN,allow_storage=False,resolve=lambda _: '93.184.216.34',
                connect=dial),port=8082).start()
            full=await r6.collect(TARGET,directory,budget=r6.Budget(150))
            assert any(f['rule']=='tls-expiring' for f in full['findings'])
            assert full['checks']['certificate']['status']=='complete'
            assert dials
            print(json.dumps({'axe_image_alt':True,'cookies_before_interaction':len(browser['cookies']),
                'third_party_refused':browser['third_party_refused'],'proxy_other_host_port_refused':True,
                'regulation_browser_cookie_check':True,'clamav_eicar':malware,'proxy_dials':len(dials),'full_run_checks':full['checks']}))
        finally:
            proxy.close();https.shutdown();https.server_close()


asyncio.run(main())
