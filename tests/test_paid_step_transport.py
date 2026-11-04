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

