import asyncio
import base64
import hashlib
import hmac
import json
from uuid import uuid4
import httpx
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
    mux=Mux(None,journal,webhook_secret='test-webhook-secret')
    journal.bind(scope,'stream-local','live_stream')
    event={'id':'event-local','type':'video.live_stream.active',
      'created_at':'2026-11-08T10:00:00Z','data':{'id':'stream-local'}}
    raw,signature=signed(event)
    assert mux.webhook(raw,signature,now=1000)
    assert mux.webhook(raw,signature,now=1000) is False
    for data,signature2,now in [(raw+b' ',signature,1000),(raw,signature,2000),(raw,'t=1000,v1=bad',1000)]:
        with pytest.raises(MediaError):mux.webhook(data,signature2,now=now)
    with pytest.raises(MediaError,match='resource_binding_conflict'):
        journal.bind(Scope(str(uuid4()),scope.region,scope.hearing),'stream-local','live_stream')
    event['id']='event-other';event['data']['id']='foreign'
    with pytest.raises(MediaError,match='unbound_resource'):
        mux.webhook(*signed(event),now=1000)


def test_mux_no_build_billing_and_no_stream_key_errors(scope,journal):
    async def run():
        def handler(request):
            return httpx.Response(500,json={'error':'secret-stream-key-must-not-escape'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            mux=Mux(client,journal,'test-id','test-secret')
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
    mux=Mux(None,journal,webhook_secret='test-webhook-secret')
    journal.bind(scope,'local-stream','live_stream')
    events=[('a','video.live_stream.active','2026-11-08T10:00:00Z'),
            ('b','video.live_stream.idle','2026-11-08T10:01:00Z'),
            ('c','video.live_stream.active','2026-11-08T09:59:00Z'),
            ('d','video.live_stream.disabled','2026-11-08T10:02:00Z')]
    for eid,kind,created in events:
        mux.webhook(*signed({'id':eid,'type':kind,'created_at':created,
            'data':{'id':'local-stream','playback_ids':[{'id':'private-playback','policy':'signed'}]}}),now=1000)
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
