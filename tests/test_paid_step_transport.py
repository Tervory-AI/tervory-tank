import uuid

import httpx
import pytest

from chassis.tank import TankClient


@pytest.mark.asyncio
@pytest.mark.parametrize('state', ['completed','interrupted','foreign'])
async def test_room_client_polls_saved_run_without_repeating_post(state):
    tenant, run = str(uuid.uuid4()), str(uuid.uuid4())
    calls = []
    def respond(request):
        calls.append((request.method, request.url.path))
        if request.method == 'POST':
            return httpx.Response(202, json={'status':'waiting_for_approval','paid_run_id':run,
                'tenant_id':str(uuid.uuid4()) if state == 'foreign' else tenant})
        assert request.url.host == 'tank.invalid' and request.url.params['tenant_id'] == tenant
        return httpx.Response(200, json={'status':state,'response_status':200,'result':{'answer':'done'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        client = TankClient('http://tank.invalid', 'offline-room', 'base', http)
        if state == 'completed':
            assert await client._post('/v1/skala/base.test/run', {'tenant_id':tenant,'input':{}}) == {'answer':'done'}
        else:
            with pytest.raises(RuntimeError):
                await client._post('/v1/skala/base.test/run', {'tenant_id':tenant,'input':{}})
    assert len([row for row in calls if row[0] == 'POST']) == 1
    assert len(calls) == (1 if state == 'foreign' else 2)



@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['base','ghost','researcher'])
async def test_direct_room_transports_consume_approved_result_once(kind, monkeypatch):
    from pathlib import Path
    tenant, run = str(uuid.uuid4()), str(uuid.uuid4())
    calls = []
    def respond(request):
        calls.append(request.method)
        assert request.headers['x-tank-key'] == 'offline-room'
        if request.method == 'POST':
            return httpx.Response(202, json={'paid_run_id':run,'tenant_id':tenant})
        assert request.url.host == 'tank' and request.url.params['tenant_id'] == tenant
        return httpx.Response(200, json={'status':'completed','response_status':200,'result':{'answer':'done'}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        if kind == 'base':
            monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'agents/base'))
            from agents.base.room import SkillClient
            call = SkillClient(http,'http://tank:8000','offline-room').bind({'base.extract':'1.0.0'},False,tenant)
            result = await call('base.extract', {'input':'bound'})
        elif kind == 'ghost':
            from agents.ghost.app import Tank
            monkeypatch.setenv('TANK_KEY','offline-room')
            result = await Tank(http).call('POST','/v1/route',{'tenant_id':tenant})
        else:
            from researcher.paid_transport import result as poll
            started = await http.post('http://tank:8000/v1/route',headers={'X-Tank-Key':'offline-room'})
            result = await poll(http,'offline-room',tenant,started.json())
    assert result == {'answer':'done'} and calls == ['POST','GET']


def test_worker_transport_keeps_original_tank_and_does_not_post_again():
    from workers.paid_transport import result
    tenant, run = str(uuid.uuid4()), str(uuid.uuid4())
    calls = []
    def respond(request):
        calls.append(request.method)
        assert request.method == 'GET' and request.url.host == 'original-tank.invalid'
        assert request.url.path == '/v1/paid-runs/'+run
        assert request.url.params['tenant_id'] == tenant and request.headers['x-tank-key'] == 'offline-worker'
        return httpx.Response(200,json={'status':'completed','response_status':200,'result':{'answer':'done'}})
    with httpx.Client(transport=httpx.MockTransport(respond)) as http:
        assert result(http,'https://original-tank.invalid/v1/route','offline-worker',tenant,
            {'paid_run_id':run,'tenant_id':tenant,'status_path':'https://foreign.invalid'}) == {'answer':'done'}
    assert calls == ['GET']
