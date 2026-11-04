"""Real /chats stream, approval card, durable resume and denial; fixture gateway only."""
import asyncio
import uuid

import pytest
import paid_steps
from test_command import command_pool as command_pool, TENANT
from test_command_streaming import streaming as streaming, thread, turn, TEXT


@pytest.mark.asyncio
@pytest.mark.parametrize('decision',['approve','deny','approve-before-save'])
async def test_real_paid_turn_pauses_and_resolves(streaming,monkeypatch,decision):
    b=streaming
    monkeypatch.setattr(paid_steps,'admit',b.paid_admission)
    if decision=='approve-before-save':
        original=paid_steps.suspend_turn
        async def racing(pause,*args,**kwargs):
            await paid_steps.decide(TENANT,pause.approval_id,user='founder',approve=True,reason='placeholder early approval')
            return await original(pause,*args,**kwargs)
        monkeypatch.setattr(paid_steps,'suspend_turn',racing)
    tid=await thread(b)
    events=await turn(b,tid)
    assert any(kind=='step' and data.get('phase_finished') for kind,data in events)
    pending=[data for kind,data in events if kind=='card' and data.get('tool')=='paid_steps.approve']
    if decision!='approve-before-save':
        assert len(pending)==1 and not b.gateway.calls
        snapshot=(await b.api.get(f'/v1/command/threads/{tid}')).json()
        assert not any(message['role']=='assistant' for message in snapshot['messages'])
        assert await b.pool.fetchval("SELECT status FROM tank.tasks WHERE tenant_id=$1",TENANT)=='queued'
        response=await b.api.post('/v1/command/cards/'+pending[0]['card_id'],json={
            'action':'cancel' if decision=='deny' else 'confirm','reason':'placeholder decision'})
        assert response.status_code==200,response.text
    if paid_steps._background:
        await asyncio.gather(*list(paid_steps._background))
    snapshot=(await b.api.get(f'/v1/command/threads/{tid}')).json()
    status=await b.pool.fetchval("SELECT status FROM tank.tasks WHERE tenant_id=$1",TENANT)
    if decision=='deny':
        assert not b.gateway.calls and status=='failed'
        assert any(step['status']=='failed' for step in snapshot['steps'])
        assert await b.pool.fetchval("SELECT reason FROM tank.paid_step_approvals WHERE tenant_id=$1",TENANT)=='placeholder decision'
    else:
        assert status=='done' and len(b.gateway.calls)==1
        assert next(message for message in snapshot['messages'] if message['role']=='assistant')['content']==TEXT
        record=await b.pool.fetchrow("SELECT paid_step_mode,cost_usd FROM tank.ledger WHERE tenant_id=$1 AND task_type='command.turn'",TENANT)
        assert record['paid_step_mode']=='approved' and float(record['cost_usd'])==0.0024
        assert uuid.UUID(snapshot['messages'][-1]['message_id'])


@pytest.mark.asyncio
async def test_member_private_turn_resumes_after_admin_approval_in_another_thread(streaming,monkeypatch):
    b=streaming
    monkeypatch.setattr(paid_steps,'admit',b.paid_admission)
    member={'X-Tervory-User':'placeholder-member','X-Tervory-Role':''}
    original=b.api.headers.copy()
    b.api.headers.update(member)
    tid=await thread(b)
    events=await turn(b,tid,text='placeholder private member request')
    assert any(kind=='step' and data.get('phase_finished') for kind,data in events)
    assert not any(kind=='done' for kind,_ in events)
    assert not b.gateway.calls
    b.api.headers=original
    admin_thread=await thread(b)
    admin=(await b.api.get(f'/v1/command/threads/{admin_thread}')).json()
    assert not admin['messages']
    card=next(card for card in admin['cards'] if card['tool']=='paid_steps.approve')
    response=await b.api.post('/v1/command/cards/'+card['card_id'],json={'action':'confirm','reason':'placeholder admin approval'})
    assert response.status_code==200,response.text
    if paid_steps._background:
        await asyncio.gather(*list(paid_steps._background))
    assert (await b.api.get(f'/v1/command/threads/{tid}')).status_code==404
    private=(await b.api.get(f'/v1/command/threads/{tid}',headers=member)).json()
    assert next(message for message in private['messages'] if message['role']=='assistant')['content']==TEXT
    assert len(b.gateway.calls)==1
    admin=(await b.api.get(f'/v1/command/threads/{admin_thread}')).json()
    assert not admin['messages']
