import asyncio
import base64
import hashlib
import hmac
import json
from uuid import uuid4
import jwt
import pytest
from fastapi.testclient import TestClient
from tank.moot.contracts import Scope, MediaError
from tank.moot.journal import Journal
from tank.moot.livekit import Rooms
from tank.moot.mux import Mux
from tank.moot.recording import Recording
from tank.moot.service import create_app
from tank.moot.speech import Speech, EndOfTurn


@pytest.fixture
def scope():
    return Scope(str(uuid4()), 'us-east', str(uuid4()))


@pytest.fixture
def journal(tmp_path):
    return Journal(tmp_path / 'media.sqlite')


def projection(scope, seat='applicant', epoch=2):
    return {'id': scope.hearing, 'region': scope.region, 'phase': 'hearing', 'revision': 9,
        'floor': seat, 'current_issue': 1, 'pending_question': {'turn': 3, 'target': seat},
        'transcript': [{'number': 3, 'seat': 'judge', 'text': 'A pending question'}],
        'my_seats': [seat], 'seats': {s: {'kind': 'human' if s == seat else 'ai', 'epoch': epoch} for s in ('applicant','respondent','judge')}}


@pytest.mark.parametrize('seat', ['applicant','respondent','judge'])
def test_exact_scope_and_camera_microphone_grants(scope, seat):
    rooms = Rooms('http://localhost:7880','ws://localhost:7880','test-key','s'*32)
    grant = rooms.grant(scope, 'member', seat, projection(scope, seat))
    claims = jwt.decode(grant['token'], 's'*32, algorithms=['HS256'])
    assert claims['video']['room'] == scope.room
    assert claims['video']['canPublishSources'] == ['camera','microphone']
    assert claims['video']['canPublishData'] is False
    assert claims['exp'] - claims['nbf'] == 60
    assert 'bench' not in json.dumps(claims)
    state=projection(scope, seat);state['my_seats']=[]
    with pytest.raises(MediaError, match='seat_not_owned'):
        rooms.grant(scope,'member',seat,state)


def test_journal_cas_resume_and_cross_tenant(scope, journal):
    event={'kind':'caption','seat':'judge','text':'Actual adapter output','final':True}
    assert journal.append(scope,'request',0,event)==1
    assert journal.append(scope,'request',0,event)==1
    with pytest.raises(MediaError,match='idempotency_conflict'):
        journal.append(scope,'request',0,{**event,'text':'changed'})
    with pytest.raises(MediaError,match='stale_sequence'):
        journal.append(scope,'other',0,event)
    assert journal.events(Scope(str(uuid4()),scope.region,scope.hearing))==[]
    assert journal.events(Scope(scope.tenant,'za',scope.hearing))==[]
    assert journal.events(scope,1)==[]
    assert journal.events(scope)[0]['seq']==1


def test_effect_restart_never_replays(scope,journal):
    assert journal.claim(scope,'stt',{'audio_hash':'actual'}) is None
    restarted=Journal(journal.path)
    assert restarted.claim(scope,'stt',{'audio_hash':'actual'})=={'status':'started','result':None}
    with pytest.raises(MediaError,match='idempotency_conflict'):
        restarted.claim(scope,'stt',{'audio_hash':'other'})


def test_speech_unavailable_and_revocation(scope,journal):
    async def run():
        async def current():return 2
        with pytest.raises(MediaError,match='audio_unavailable'):
            await Speech(journal).dispatch(scope,'a','moot.stt',{},current=current,epoch=2)
        class Adapter:
            calls=0
            async def route(self,*args):
                self.calls+=1
                await asyncio.sleep(0.2)
                return {'ledger_id':'actual-tank-receipt'}
        adapter=Adapter();epoch=[2]
        async def current():return epoch[0]
        task=asyncio.create_task(Speech(journal,adapter).dispatch(scope,'b','moot.stt',{},current=current,epoch=2))
        await asyncio.sleep(0.01);epoch[0]=3
        with pytest.raises(MediaError,match='seat_revoked'):await task
        assert adapter.calls==1
        epoch[0]=2
        result=await Speech(journal,adapter).dispatch(scope,'b','moot.stt',{},current=current,epoch=2)
        assert result['status']=='started' and adapter.calls==1
    asyncio.run(run())


def test_end_turn_requires_both_vad_silence_and_detector():
    end=EndOfTurn()
    assert not end.frame(0,.9,False)
    assert not end.frame(1600,.1,False)
    assert end.frame(1700,.1,True)
    assert not end.frame(1800,.1,True)


def signed(event,secret='test-webhook-secret',now=1000):
    raw=json.dumps(event).encode()
    sig=hmac.new(secret.encode(),str(now).encode()+b'.'+raw,hashlib.sha256).hexdigest()
    return raw,f't={now},v1={sig}'


def test_mux_signatures_binding_idempotency(scope,journal):
    mux=Mux(journal,webhook_secret='test-webhook-secret')
    journal.bind(scope,'stream-local','live_stream')
    event={'id':'event-local','type':'video.live_stream.active',
      'created_at':'2026-11-08T10:00:00Z','data':{'id':'stream-local','stream_key':'must-not-be-persisted'}}
    raw,signature=signed(event)
    assert mux.webhook(raw,signature,now=1000)
    assert mux.webhook(raw,signature,now=1000) is False
    with journal.connect() as db:
        assert 'must-not-be-persisted' not in db.execute('SELECT payload FROM mux_events').fetchone()[0]
    for data,signature2,now in [(raw+b' ',signature,1000),(raw,signature,2000),(raw,'t=1000,v1=bad',1000)]:
        with pytest.raises(MediaError):mux.webhook(data,signature2,now=now)
    with pytest.raises(MediaError,match='resource_binding_conflict'):
        journal.bind(Scope(str(uuid4()),scope.region,scope.hearing),'stream-local','live_stream')
    event['id']='event-other';event['data']['id']='foreign'
    with pytest.raises(MediaError,match='unbound_resource'):
        mux.webhook(*signed(event),now=1000)


def test_mux_no_build_billing_and_no_stream_key_errors(scope,journal):
    async def run():
        class Account:
            async def request(self, *args, **kwargs):
                raise RuntimeError('secret-stream-key-must-not-escape')
        mux=Mux(journal,account=Account())
        with pytest.raises(MediaError,match='billable_media_disabled'):
            await mux.create_stream(scope,'id',founder=True,consented=True)
        with pytest.raises(MediaError,match='mux_request_failed') as exc:
            await mux.create_stream(scope,'id',founder=True,consented=True,allow_billable=True)
        assert 'secret-stream-key' not in str(exc.value)
        assert (await mux.create_stream(scope,'id',founder=True,consented=True,allow_billable=True))['status']=='started'
    asyncio.run(run())


def test_consent_expires_on_handover(scope,journal):
    rec=Recording(journal);state=projection(scope)
    assert not rec.allowed(scope,state)
    rec.consent(scope,'consent',0,seat='applicant',user='member',projection=state,accepted=True)
    assert rec.allowed(scope,state)
    state['seats']['applicant']['epoch']+=1
    assert not rec.allowed(scope,state)


def test_internal_auth_and_exact_resume(scope,journal):
    class Bridge:
        async def projection(self,scope,user,seat):return projection(scope,seat)
    app=create_app(bridge=Bridge(),rooms=None,journal=journal,internal_key='internal-test-key',region=scope.region)
    with TestClient(app) as client:
        url=f'/internal/hearings/{scope.hearing}/resume?seat=applicant'
        assert client.get(url).status_code==401
        response=client.get(url,headers={'X-Moot-Key':'internal-test-key','X-Moot-Tenant':scope.tenant,'X-Moot-Actor':'member'})
        assert response.status_code==200
        result=response.json()['hearing']
        assert result['pending_question']=={'turn':3,'target':'applicant'}
        assert result['transcript'][0]['text']=='A pending question'
        assert result['current_issue']==1


def test_mux_lifecycle_ordering_private_publication_and_asset_binding(scope,journal):
    mux=Mux(journal,webhook_secret='test-webhook-secret')
    journal.bind(scope,'local-stream','live_stream')
    events=[('a','video.live_stream.active','2026-11-08T10:00:00Z'),
            ('b','video.live_stream.idle','2026-11-08T10:01:00Z'),
            ('c','video.live_stream.active','2026-11-08T09:59:00Z'),
            ('d','video.live_stream.disabled','2026-11-08T10:02:00Z')]
    for eid,kind,created in events:
        mux.webhook(*signed({'id':eid,'type':kind,'created_at':created,
            'data':{'id':'local-stream','playback_ids':[{'id':'private-playback','policy':'signed'}]}}),now=1000)
        if eid in ('b','c'):assert journal.resource(scope,'local-stream')['state']=='paused'
    assert journal.resource(scope,'local-stream')['state']=='ended'
    with pytest.raises(MediaError,match='playback_not_published'):
        mux.playback(scope,'local-stream',permitted=True)
    with pytest.raises(MediaError,match='independent_published_ruling_required'):
        journal.publish(scope,'local-stream',founder=True,hearing={'id':scope.hearing,'region':scope.region,'phase':'hearing'})
    journal.publish(scope,'local-stream',founder=True,hearing={'id':scope.hearing,'region':scope.region,'phase':'closed','published':True})
    with pytest.raises(MediaError,match='mux_signing_unavailable'):
        mux.playback(scope,'local-stream',permitted=True)
    mux.webhook(*signed({'id':'asset-event','type':'video.asset.ready','created_at':'2026-11-08T10:03:00Z',
        'data':{'id':'local-asset','live_stream_id':'local-stream','playback_ids':[{'id':'asset-playback','policy':'signed'}]}}),now=1000)
    assert journal.resource(scope,'local-asset')['state']=='ready'
    assert journal.resource(scope,'local-asset')['published']==0
    mux.webhook(*signed({'id':'asset-failed','type':'video.asset.errored','created_at':'2026-11-08T10:04:00Z',
        'data':{'id':'local-asset','live_stream_id':'local-stream'}}),now=1000)
    assert journal.resource(scope,'local-asset')['state']=='failed'
    with pytest.raises(MediaError,match='playback_unavailable'):mux.playback(scope,'local-asset',permitted=True)


def test_retention_prevents_early_and_path_escape(tmp_path):
    from datetime import datetime,timezone,timedelta
    root=tmp_path/'recordings';root.mkdir();(root/'audio.ogg').write_bytes(b'local')
    now=datetime.now(timezone.utc)
    with pytest.raises(MediaError,match='retention_not_due'):
        Recording.local_delete(root,'audio.ogg',due_at=now+timedelta(days=1),now=now)
    with pytest.raises(MediaError,match='invalid_recording_path'):
        Recording.local_delete(root,'../foreign.ogg',due_at=now,now=now)
    Recording.local_delete(root,'audio.ogg',due_at=now,now=now)
    assert not (root/'audio.ogg').exists()


def test_recording_start_stop_no_duplicate_dispatch(scope,journal):
    class Result:
        egress_id='local-egress'
    class Rooms:
        starts=0;stops=0
        async def record(self,*args,**kwargs):self.starts+=1;return Result()
        async def stop_recording(self,*args):self.stops+=1
    rooms=Rooms();recording=Recording(journal);state=projection(scope)
    async def run():
        with pytest.raises(MediaError,match='recording_consent_required'):
            await recording.start(scope,'start',founder=True,projection=state,rooms=rooms,output=None)
        recording.consent(scope,'consent',0,seat='applicant',user='member',projection=state,accepted=True)
        assert (await recording.start(scope,'start',founder=True,projection=state,rooms=rooms,output=None))['state']=='starting'
        await recording.start(scope,'start',founder=True,projection=state,rooms=rooms,output=None)
        assert rooms.starts==1
        with pytest.raises(MediaError,match='not_found'):
            await recording.stop(Scope(str(uuid4()),scope.region,scope.hearing),'stop',rooms=rooms,egress_id='local-egress')
        await recording.stop(scope,'stop',rooms=rooms,egress_id='local-egress')
        await recording.stop(scope,'stop',rooms=rooms,egress_id='local-egress')
        assert rooms.stops==1
    asyncio.run(run())


def test_signed_mux_playback_crypto_and_scope(scope,journal):
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
    pem=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
    class Signer:
        def signed_playback(self, playback_id, *, ttl_seconds):
            import time
            token=jwt.encode({'sub':playback_id,'aud':'v','exp':int(time.time())+ttl_seconds},pem,algorithm='RS256',headers={'kid':'local-signing-key'})
            return f'https://stream.mux.com/{playback_id}.m3u8?token={token}'
    mux=Mux(journal,account=Signer())
    url=mux.signed_playback('local-playback',permitted=True,published=True)
    token=url.split('token=')[1]
    claims=jwt.decode(token,key.public_key(),algorithms=['RS256'],audience='v')
    assert claims['sub']=='local-playback'
    assert jwt.get_unverified_header(token)['kid']=='local-signing-key'
    with pytest.raises(MediaError,match='not_found'):
        mux.playback(Scope(str(uuid4()),scope.region,scope.hearing),'local-resource',permitted=True)


def test_caption_websocket_filters_private_fields(scope,journal):
    class Bridge:
        async def projection(self,scope,user,seat):return projection(scope,seat)
    rooms=Rooms('http://localhost:7880','ws://localhost:7880','local-key','s'*32)
    grant=rooms.grant(scope,'member','applicant',projection(scope))
    journal.save_lease(scope,'member','applicant',2,grant['identity'])
    journal.append(scope,'caption',0,{'kind':'caption','seat':'applicant','text':'Actual supplied caption',
        'final':True,'bench_notes':'must never cross caption channel','actor_id':'private-actor'})
    app=create_app(bridge=Bridge(),rooms=rooms,journal=journal,internal_key='internal-test-key',region=scope.region)
    with TestClient(app) as client:
        with client.websocket_connect('/events') as ws:
            ws.send_json({'token':grant['token'],'after':0})
            assert ws.receive_json()=={'seq':1,'seat':'applicant','text':'Actual supplied caption','final':True}


def test_livekit_signed_recording_lifecycle_is_idempotent_and_private(scope,journal):
    from livekit import api
    from tank.moot.events import LiveKitEvents
    receiver=LiveKitEvents(journal,'local-key','s'*32,'us-east')
    raw=json.dumps({'id':'local-event','event':'egress_ended','egressInfo':{
        'egressId':'local-egress','roomName':scope.room,'status':'EGRESS_COMPLETE',
        'error':'private-upstream-error-must-not-escape'}}).encode()
    token=api.AccessToken('local-key','s'*32).with_sha256(base64.b64encode(hashlib.sha256(raw).digest()).decode()).to_jwt()
    assert receiver.receive(raw,token)==1
    assert receiver.receive(raw,token)==1
    events=journal.events(scope)
    assert len(events)==1 and events[0]['kind']=='recording_ended'
    assert 'private-upstream' not in json.dumps(events)
    with pytest.raises(MediaError,match='invalid_webhook'):
        receiver.receive(raw+b' ',token)


def test_shared_tank_mux_account_adapter_owns_credentials(scope,journal):
    class Account:
        calls=[]
        async def request(self,method,path,**kwargs):
            self.calls.append((method,path,kwargs))
            return {'id':'shared-tank-stream','status':'idle'}
        def signed_playback(self,playback_id,*,ttl_seconds):
            return f'https://stream.mux.com/{playback_id}.m3u8?token=local-test-token'
    account=Account();mux=Mux(journal,account=account)
    result=asyncio.run(mux.create_stream(scope,'shared-request',founder=True,consented=True,allow_billable=True))
    assert result['id']=='shared-tank-stream' and len(account.calls)==1
    assert account.calls[0][0:2]==('POST','live-streams')
    assert mux.signed_playback('shared-playback',permitted=True,published=True).startswith('https://stream.mux.com/')
    assert not hasattr(mux,'auth') and not hasattr(mux,'client')


def test_optional_detection_missing_runtime_is_unavailable(monkeypatch):
    import sys
    from tank.moot.detection import load_detection
    monkeypatch.setitem(sys.modules,'livekit.plugins',None)
    with pytest.raises(MediaError,match='audio_detection_unavailable'):
        load_detection()


def test_caption_revocation_prevents_stale_event(scope,journal):
    from tank.moot.captions import CaptionPublisher
    async def run():
        async def current():return 3
        with pytest.raises(MediaError,match='seat_revoked'):
            await CaptionPublisher(journal).emit(scope,'caption',0,seat='judge',epoch=2,
                text='Actual supplied STT output',final=True,current=current)
    asyncio.run(run())
    assert journal.events(scope)==[]


@pytest.mark.parametrize('seat',['applicant','respondent','judge'])
def test_independent_ai_worker_seat_grants(scope,seat):
    rooms=Rooms('http://localhost:7880','ws://localhost:7880','test-key','s'*32)
    state=projection(scope,seat);state['seats'][seat]['kind']='ai'
    token=rooms.worker_grant(scope,seat,state)
    claims=jwt.decode(token,'s'*32,algorithms=['HS256'])
    assert claims['sub']==f'ai:{seat}:2' and claims['video']['room']==scope.room
    assert claims['video']['canPublishSources']==['microphone']
    state['seats'][seat]['kind']='human'
    with pytest.raises(MediaError,match='ai_seat_required'):rooms.worker_grant(scope,seat,state)


def test_object_retention_exact_region_and_hearing(scope,journal):
    from tank.moot.retention import Retention
    from datetime import datetime,timezone,timedelta
    class Store:
        deleted=[]
        async def delete(self,**kwargs):self.deleted.append(kwargs)
    store=Store();retention=Retention(journal,store,{'us-east':'local-us-bucket','za':'local-za-bucket'})
    now=datetime.now(timezone.utc)
    retention.bind(scope,scope.room+'/audio.ogg',now+timedelta(days=1))
    assert asyncio.run(retention.run_once(scope,now=now))==0
    assert asyncio.run(retention.run_once(Scope(str(uuid4()),scope.region,scope.hearing),now=now+timedelta(days=2)))==0
    assert asyncio.run(retention.run_once(scope,now=now+timedelta(days=2)))==1
    assert asyncio.run(retention.run_once(scope,now=now+timedelta(days=2)))==0
    assert store.deleted==[{'bucket':'local-us-bucket','key':scope.room+'/audio.ogg'}]


def test_self_hosted_old_jwt_cannot_rejoin_after_epoch_handover(scope,journal):
    from tank.moot.gateway import SignalingGate
    state=projection(scope)
    class Bridge:
        async def projection(self,scope,user,seat):return state
    rooms=Rooms('http://localhost:7880','ws://localhost:8091','local-key','s'*32)
    token=rooms.grant(scope,'member','applicant',state)
    journal.save_lease(scope,'member','applicant',2,token['identity'])
    gate=SignalingGate(Bridge(),rooms,journal,scope.region)
    assert asyncio.run(gate.authorize(token['token']))[3]==2
    state['seats']['applicant']={'kind':'ai','epoch':3}
    with pytest.raises(MediaError,match='seat_revoked'):
        asyncio.run(gate.authorize(token['token']))
    # Old token remains cryptographically valid, so token expiry alone would fail.
    jwt.decode(token['token'],'s'*32,algorithms=['HS256'])
