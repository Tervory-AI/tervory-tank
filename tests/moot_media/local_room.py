"""Explicit local integration harness: real SFU/Chromium, fixture actor boundary.

Run manually with MOOT_LOCAL_CONFIG pointing at private disposable config. This
never contacts Mux, Tank or a speech/model provider and never records a fixture live.
"""
import asyncio
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import ssl
from pathlib import Path
import threading
import tempfile
import time
import socket
import uvicorn
from tank.moot.journal import Journal
from tank.moot.service import create_app
from uuid import uuid4
from playwright.sync_api import sync_playwright
from tank.moot.contracts import Scope
from tank.moot.livekit import Rooms


def main():
    config=json.loads(Path(os.environ['MOOT_LOCAL_CONFIG']).read_text())
    key,secret=next(iter(config['keys'].items()))
    scope=Scope(str(uuid4()),'us-east',str(uuid4()))
    endpoint=os.environ.get('MOOT_LOCAL_LIVEKIT_URL','http://127.0.0.1:7880')
    tls=ssl.create_default_context()
    if os.environ.get('MOOT_LOCAL_TLS_CA_FILE'):
        tls.load_verify_locations(cafile=os.environ['MOOT_LOCAL_TLS_CA_FILE'])
    rooms=Rooms(endpoint,endpoint.replace('http','ws',1),key,secret,tls_context=tls)
    asyncio.run(rooms.create(scope))
    journal=Journal(Path(tempfile.mkdtemp(prefix='moot-browser-journal-'))/'media.sqlite')
    states={seat:{'id':scope.hearing,'region':scope.region,'revision':3,'phase':'hearing',
      'floor':'respondent','current_issue':1,'pending_question':{'turn':2,'target':'respondent'},
      'transcript':[{'number':2,'seat':'judge','text':'Saved pending question'}],
      'seats':{s:{'kind':'human','epoch':0} for s in ('applicant','respondent','judge')},'my_seats':[seat]}
      for seat in ('applicant','respondent')}
    class Bridge:
        async def projection(self,scope,user,seat):return deepcopy(states[seat])
    with socket.socket() as candidate:
        candidate.bind(('127.0.0.1',0));gateway_port=candidate.getsockname()[1]
    gateway=create_app(bridge=Bridge(),rooms=rooms,journal=journal,internal_key='local-fixture-key',region=scope.region)
    gateway_server=uvicorn.Server(uvicorn.Config(gateway,host='127.0.0.1',port=gateway_port,
        log_level='critical',access_log=False))
    gateway_thread=threading.Thread(target=gateway_server.run,daemon=True);gateway_thread.start()
    deadline=time.monotonic()+5
    while not gateway_server.started:
        if time.monotonic()>deadline:raise RuntimeError('local gateway did not start')
        time.sleep(.02)
    rooms.public_url=f'ws://127.0.0.1:{gateway_port}'
    tokens={}
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path=self.path.split('?')[0]
            if path=='/client.js':
                body=Path('/tmp/moot-client.js').read_bytes();mime='text/javascript'
            elif path in ('/state','/grant'):
                seat=self.headers.get('Authorization','').removeprefix('Bearer fixture-')
                if seat not in states:
                    self.send_error(403);return
                state=deepcopy(states[seat])
                try:
                    result=state if path=='/state' else rooms.grant(scope,'fixture-'+seat,seat,state)
                    if path=='/grant':
                        journal.save_lease(scope,'fixture-'+seat,seat,result['epoch'],result['identity'])
                        tokens[seat]=result['token']
                except ValueError:
                    self.send_error(403);return
                body=json.dumps(result).encode();mime='application/json'
            else:
                body=b'<!doctype html><html><body><script src="/client.js"></script></body></html>';mime='text/html'
            self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    initialize="""async seat=>{
      window.received=[];
      const request=async path=>{const response=await fetch(path,{headers:{Authorization:'Bearer fixture-'+seat}});if(!response.ok)throw Error('fixture_denied');return response.json();};
      window.peer=new window.MootParticipant(seat,()=>request('/state'),()=>request('/grant'),(track,p)=>{received.push({kind:track.kind,participant:p.identity});document.body.append(track.attach());});
      await peer.connect();await peer.microphone(true);await peer.camera(true);
    }"""
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('MOOT_LOCAL_CHROMIUM','/usr/bin/chromium') or None,headless=True,args=[
                '--no-sandbox','--proxy-bypass-list=livekit;localhost;127.0.0.1','--allow-loopback-in-peer-connection','--disable-features=WebRtcHideLocalIpsWithMdns','--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream','--autoplay-policy=no-user-gesture-required'])
            contexts=[browser.new_context(permissions=['camera','microphone']) for _ in range(2)]
            pages=[context.new_page() for context in contexts]
            for page,seat in zip(pages,('applicant','respondent')):
                page.goto(url);page.evaluate(initialize,seat)
            for page in pages:
                page.wait_for_function("received.some(t=>t.kind==='video')&&received.some(t=>t.kind==='audio')",timeout=30000)
            for page in pages:
                page.evaluate("async()=>{for(const kind of ['videoinput','audioinput']){const devices=await peer.devices(kind);if(!devices.length)throw Error('local_device_missing');await peer.device(kind,devices[0].deviceId);}}")
            pages[0].evaluate('async()=>{await peer.camera(false);await peer.microphone(false);}')
            assert pages[0].evaluate('peer.tracks().every(t=>t.isMuted)')
            pages[0].evaluate('async()=>{await peer.camera(true);await peer.microphone(true);}')
            # A genuine signaling/media connection is torn down and re-established.
            pages[1].reload();pages[1].evaluate(initialize,'respondent')
            pages[1].wait_for_function("received.some(t=>t.kind==='video')&&received.some(t=>t.kind==='audio')",timeout=30000)
            resumed=pages[1].evaluate('peer.hearing')
            assert resumed['pending_question']==states['respondent']['pending_question']
            assert resumed['transcript']==states['respondent']['transcript']
            # Epoch revocation stops the participant; no transcript reset occurs.
            states['applicant']['seats']['applicant']={'kind':'ai','epoch':1}
            pages[0].evaluate('async()=>{try{await peer.refresh()}catch{}}')
            assert pages[0].evaluate('peer.state')=='disconnected'
            import httpx
            denied=httpx.get(f'http://127.0.0.1:{gateway_port}/rtc/v1/validate',params={'access_token':tokens['applicant']},trust_env=False)
            assert denied.status_code==403
            attacker_connected=pages[0].evaluate('''async input=>{const room=new window.LiveKitRoom();try{await room.connect(input.url,input.token,{maxRetries:0});return true;}catch{return false;}finally{await room.disconnect();}}''',{'url':rooms.public_url,'token':tokens['applicant']})
            assert attacker_connected is False
            assert pages[1].evaluate('peer.hearing.current_issue')==1
            browser.close()
        print(json.dumps({'local_real_sfu':True,'real_browser_participants':2,
          'camera_and_microphone_received':True,'mute_controls':True,'device_selection':True,'reconnect':True,
          'handover_disconnect':True,'exact_pending_question_resume':True,'epoch_signaling_gateway':True,'old_token_rejoin_denied':True,
          'actor_boundary':'fixture','internal_signaling_tls':endpoint.startswith('https:'),
          'browser_signaling':'loopback_test_only','mux':'not_contacted','speech':'unavailable'}))
    finally:
        server.shutdown()
        gateway_server.should_exit=True
        gateway_thread.join(timeout=3)
        async def cleanup():
            from livekit import api
            async with rooms.client() as client:
                await client.room.delete_room(api.DeleteRoomRequest(room=scope.room))
        asyncio.run(cleanup())


if __name__=='__main__':main()
