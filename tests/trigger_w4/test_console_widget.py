"""Wave 4 real schema/API proof, with no model, mail or outside network."""
from trigger_signin_fakes import set_founders
import hashlib
import json
import sys
from datetime import datetime, UTC
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import command
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI, HTTPException
import trigger_bot_api as bot_api
import trigger_console as console
import trigger_widget as widget
from trigger_bot import Bot
from trigger_bot_shared import hash_key
from trigger_console_contract import Settings

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests/trigger_bot_b1'))
from test_database import database as disposable_database
database = disposable_database

A, B = UUID(int=411), UUID(int=412)
SETTINGS = {'enabled': True, 'name': 'placeholder store', 'time_zone': 'Africa/Johannesburg',
            'opening_hours': json.dumps({str(day): [['00:00', '23:59']] for day in range(7)}),
            'greeting': 'placeholder greeting', 'no_source_message': 'placeholder no source',
            'handover_message': 'placeholder hand-over', 'privacy_notice': 'placeholder notice',
            'notice_version': 'placeholder-v1'}


@pytest_asyncio.fixture
async def w4(database, monkeypatch):
    app = FastAPI()
    for router in (command.router, bot_api.router, console.router, widget.router):
        app.include_router(router)
    runtime = SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east', app=app,
                              TANK_API_KEY='placeholder-workspace-key', run_route=AsyncMock(side_effect=AssertionError('placeholder: model forbidden')))
    monkeypatch.setitem(sys.modules, 'main', runtime)
    set_founders(monkeypatch, 'placeholder-founder')
    monkeypatch.setenv('TRIGGER_BOT_TRUSTED_PROXY_CIDRS', '127.0.0.0/8')
    bot = Bot(runtime)
    bot.notify = AsyncMock()
    bot.voice = AsyncMock(return_value={'brand': 'placeholder store'})
    monkeypatch.setattr(bot_api, 'make_bot', lambda: bot)
    monkeypatch.setattr(widget, 'make_bot', lambda: bot)
    monkeypatch.setattr(console, 'bot', lambda: bot)
    token = 'rk_pub_' + hashlib.sha256(b'placeholder-public-embed-key').hexdigest()[:48]
    key = 'tb1.us-east.'+A.hex+'.'+token
    await database.execute('''INSERT INTO tank.trigger_bot_embed_keys(tenant_id,key_hash,region,origins)
        VALUES($1,$2,'us-east',$3::jsonb)''', A, hash_key(token), json.dumps(['https://store.placeholder.invalid']))
    await database.execute('''INSERT INTO tank.trigger_bot_config(tenant_id,enabled,settings,handover_email)
        VALUES($1,true,$2::jsonb,'handover@placeholder.invalid')''', A, json.dumps(SETTINGS))
    public = {'origin': 'https://store.placeholder.invalid', 'x-bot-key': key}
    private = {'x-tank-key': 'placeholder-workspace-key', 'x-tervory-tenant': str(A), 'x-tervory-user': 'placeholder-founder'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        yield SimpleNamespace(pool=database, client=client, bot=bot, runtime=runtime, public=public, private=private)


def test_calendar_rejects_ambiguous_and_nonexistent_wall_time_without_guessing():
    base = {'post_id': str(uuid4()), 'local_date': '2026-11-03', 'local_time': '10:00', 'time_zone': 'Africa/Johannesburg'}
    assert console.local_schedule(base)['planned_at'] == '2026-11-03T10:00:00+02:00'
    for date, time in [('2026-11-01', '01:30'), ('2026-03-08', '02:30')]:
        with pytest.raises(HTTPException):
            console.local_schedule({**base, 'local_date': date, 'local_time': time, 'time_zone': 'America/Los_Angeles'})
    with pytest.raises(HTTPException):
        console.local_schedule({**base, 'time_zone': 'placeholder/invalid'})


def test_explicit_hours_use_account_zone_and_fail_closed():
    settings = {**SETTINGS, 'opening_hours': '{"1":[["08:00","17:00"]]}'}
    assert widget.within_hours(settings, datetime(2026,11,3,6,0,tzinfo=UTC))
    assert not widget.within_hours(settings, datetime(2026,11,3,15,0,tzinfo=UTC))
    assert not widget.within_hours({**settings, 'time_zone': 'placeholder/invalid'})
    assert not widget.within_hours({**settings, 'opening_hours': 'placeholder prose'})


@pytest.mark.asyncio
async def test_public_config_does_not_leak_private_settings_or_other_tenant(w4):
    await w4.pool.execute('''INSERT INTO tank.trigger_bot_config(tenant_id,enabled,settings)
        VALUES($1,true,$2::jsonb)''', B, json.dumps({'name': 'placeholder private other tenant'}))
    result = await w4.client.post('/v1/bot/widget/config', json={}, headers=w4.public)
    assert result.status_code == 200, result.text
    assert result.json()['name'] == 'placeholder store'
    assert result.json()['capture'] is True
    assert not {'handover_email','opening_hours','time_zone','handover_rules','origins'} & result.json().keys()
    denied = await w4.client.post('/v1/bot/widget/config', json={}, headers={**w4.public,'origin':'https://other.placeholder.invalid'})
    assert denied.status_code == 403
    assert (await w4.client.post('/v1/bot/widget/config',json={})).status_code == 403
    w4.runtime.run_route.assert_not_awaited()


@pytest.mark.asyncio
async def test_outside_hours_hands_over_and_never_routes_a_model(w4):
    await w4.pool.execute("UPDATE tank.trigger_bot_config SET settings=jsonb_set(settings,'{opening_hours}','\"placeholder unknown\"') WHERE tenant_id=$1", A)
    result = await w4.client.post('/v1/bot/widget/message',json={'text':'placeholder enquiry'},headers=w4.public)
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'handed_over' and result.json()['answer'] is None
    assert result.json()['sources'] == []
    w4.bot.notify.assert_awaited_once()
    w4.runtime.run_route.assert_not_awaited()
    assert await w4.pool.fetchval('SELECT count(*) FROM tank.trigger_bot_messages WHERE tenant_id=$1', A) == 1


@pytest.mark.asyncio
async def test_notice_checked_before_contact_write_and_names_preserved(w4):
    body={'text':'placeholder enquiry','contact':{'name':'placeholder first last','first_name':'placeholder first',
        'last_name':'placeholder last','email':'contact@placeholder.invalid'},'notice_version':'placeholder-wrong'}
    denied=await w4.client.post('/v1/bot/widget/message',json=body,headers=w4.public)
    assert denied.status_code == 409
    assert await w4.pool.fetchval('SELECT count(*) FROM tank.trigger_bot_drafts WHERE tenant_id=$1',A)==0
    await w4.pool.execute("UPDATE tank.trigger_bot_config SET enabled=false WHERE tenant_id=$1",A)
    result=await w4.client.post('/v1/bot/widget/message',json={**body,'notice_version':'placeholder-v1'},headers=w4.public)
    assert result.status_code==200,result.text
    row=await w4.pool.fetchval("SELECT data FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND kind='lead'",A)
    assert json.loads(row)['last_name']=='placeholder last'


@pytest.mark.asyncio
async def test_settings_propose_is_not_write_and_confirm_snapshot_is_tenant_bound(w4):
    proposal=await w4.client.post('/v1/command/trigger/console/propose',json={'tool':'trigger.bot.settings',
        'arguments':{**SETTINGS,'greeting':'placeholder changed'}},headers=w4.private)
    assert proposal.status_code==200,proposal.text
    card=proposal.json()['card']
    assert 'payload' not in card
    stored=json.loads(await w4.pool.fetchval('SELECT settings FROM tank.trigger_bot_config WHERE tenant_id=$1',A))
    assert stored['greeting']=='placeholder greeting'
    actor=command.Actor(A,'placeholder-founder',True)
    args=Settings.model_validate(card['arguments'])
    await w4.pool.execute("UPDATE tank.trigger_bot_config SET settings=jsonb_set(settings,'{greeting}','\"placeholder concurrent\"') WHERE tenant_id=$1",A)
    with pytest.raises(HTTPException) as conflict:
        await console.execute('settings',args,actor,uuid4())
    assert conflict.value.status_code==409
    foreign=command.Actor(B,'placeholder-founder',True)
    with pytest.raises(HTTPException):
        await console.execute('settings',args,foreign,uuid4())
    denied=await w4.client.post('/v1/trigger/bot/settings',json=args.model_dump(mode='json'),headers=w4.private)
    assert denied.status_code==409


@pytest.mark.asyncio
async def test_human_reply_poll_requires_exact_conversation_and_visitor(w4):
    conversation,visitor=uuid4(),uuid4()
    await w4.pool.execute("INSERT INTO tank.trigger_bot_conversations(tenant_id,id,visitor_id,status) VALUES($1,$2,$3,'handed_over')",A,conversation,visitor)
    await w4.pool.execute("INSERT INTO tank.trigger_bot_messages(tenant_id,id,conversation_id,question,answer,outcome,person) VALUES($1,$2,$3,'','placeholder human reply','handed_over','placeholder person')",A,uuid4(),conversation)
    body={'conversation_id':str(conversation),'visitor_id':str(visitor)}
    result=await w4.client.post('/v1/bot/widget/poll',json=body,headers=w4.public)
    assert result.status_code==200,result.text
    assert result.json()['messages'][0]['answer']=='placeholder human reply'
    denied=await w4.client.post('/v1/bot/widget/poll',json={**body,'visitor_id':str(uuid4())},headers=w4.public)
    assert denied.status_code==404


@pytest.mark.asyncio
async def test_settings_confirm_replay_writes_once_and_other_user_cannot_confirm(w4):
    response=await w4.client.post('/v1/command/trigger/console/propose',json={'tool':'trigger.bot.settings',
        'arguments':{**SETTINGS,'greeting':'placeholder confirmed'}},headers=w4.private)
    assert response.status_code==200,response.text
    card=response.json()['card']['card_id']
    other={**w4.private,'x-tervory-user':'placeholder-other-user'}
    denied=await w4.client.post('/v1/command/cards/'+card,json={'action':'confirm'},headers=other)
    assert denied.status_code in {403,404}
    confirmed=await w4.client.post('/v1/command/cards/'+card,json={'action':'confirm'},headers=w4.private)
    assert confirmed.status_code==200,confirmed.text
    assert confirmed.json()['status']=='confirmed',confirmed.text
    before=await w4.pool.fetchrow('SELECT operation_id,updated_at,settings FROM tank.trigger_bot_config WHERE tenant_id=$1',A)
    again=await w4.client.post('/v1/command/cards/'+card,json={'action':'confirm'},headers=w4.private)
    assert again.status_code==200,again.text
    after=await w4.pool.fetchrow('SELECT operation_id,updated_at,settings FROM tank.trigger_bot_config WHERE tenant_id=$1',A)
    assert before==after
    assert json.loads(after['settings'])['greeting']=='placeholder confirmed'
    w4.runtime.run_route.assert_not_awaited()


@pytest.mark.asyncio
async def test_quote_title_quantity_request_are_captured_without_model_or_live_send(w4):
    await w4.pool.execute("INSERT INTO tank.trigger_bot_sources(tenant_id,id,kind,title,status,operation_id) VALUES($1,$2,'rig','placeholder catalogue','ready',$3)",A,uuid4(),uuid4())
    w4.bot.rig_read=AsyncMock(return_value={'id':'placeholder-sku'})
    result=await w4.client.post('/v1/bot/widget/message',headers=w4.public,json={'text':'placeholder request',
        'quote_product_id':'placeholder-sku','quote_title':'placeholder title','quote_quantity':3,
        'contact':{'name':'placeholder person','email':'quote@placeholder.invalid'},'notice_version':'placeholder-v1'})
    assert result.status_code==200,result.text
    assert result.json()['quote_draft_id']
    data=json.loads(await w4.pool.fetchval("SELECT data FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND kind='quote'",A))
    assert (data['title'],data['quantity'],data['request'])==('placeholder title',3,'placeholder request')
    assert not {'amount','price','invoice'}&data.keys()
    assert await w4.pool.fetchval("SELECT count(*) FROM tank.trigger_bot_drafts WHERE tenant_id=$1 AND state='confirmed'",A)==0
    w4.runtime.run_route.assert_not_awaited()


def test_crm_projection_keeps_approved_fields_but_no_nested_credentials():
    from trigger_crm import project
    row=project({'id':str(A),'next_follow_up':'placeholder date','line_items':[{'title':'placeholder item','quantity':3,
        'unit_price':'123.45','access_token':'placeholder private'}],'assigned_to':[{'id':str(B),'name':'placeholder person','password':'placeholder private'}],
        'public_token':'placeholder private'})
    assert row['line_items']==[{'title':'placeholder item','quantity':3,'unit_price':'123.45'}]
    assert row['assigned_to']==[{'id':str(B),'name':'placeholder person'}]
    assert 'placeholder private' not in repr(row)


@pytest.mark.asyncio
async def test_rig_keeps_request_metadata_without_inventing_a_price(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT/'agents/rig'))
    from rigbox.api import QuoteIn
    from rigbox.service import Service
    from pydantic import ValidationError
    body={'product_id':'placeholder-product','title':'placeholder title','request':'placeholder enquiry','quantity':3,
          'contact':{'name':'placeholder person','email':'contact@placeholder.invalid'}}
    parsed=QuoteIn.model_validate(body).model_dump(exclude_none=True)
    with pytest.raises(ValidationError):
        QuoteIn.model_validate({**body,'quantity':0})
    service=SimpleNamespace(store=SimpleNamespace(retailer=AsyncMock(return_value={}),products=AsyncMock(return_value=[])),
        product=AsyncMock(return_value={'id':'placeholder-product','price':{'amount':'123.45','currency':'ZAR'}}),
        _shop=AsyncMock(return_value={}))
    payload,contact=await Service.quote_payload(service,'placeholder-tenant',parsed)
    assert payload['request']=={'title':'placeholder title','request':'placeholder enquiry','quantity':3}
    assert payload['product']['price']=={'amount':'123.45','currency':'ZAR'}
    assert contact['email']=='contact@placeholder.invalid'
    assert not {'total','invoice','amount'}&payload.keys()


@pytest.mark.asyncio
async def test_widget_projects_grounded_answer_without_internal_metadata(w4,monkeypatch):
    monkeypatch.setattr(widget,'within_hours',lambda settings:True)
    answered=AsyncMock(return_value={'state':'bot','answer':'placeholder sourced answer',
        'sources':[{'title':'placeholder source','url':'https://source.placeholder.invalid'}],
        'conversation_id':str(A),'visitor_id':str(B),'model':'placeholder private model',
        'retrieved':['placeholder private text'],'ledger_id':str(uuid4()),'access_token':'placeholder private token'})
    monkeypatch.setattr(widget,'ask',answered)
    result=await w4.client.post('/v1/bot/widget/message',json={'text':'placeholder question'},headers=w4.public)
    assert result.status_code==200,result.text
    assert result.json()['answer']=='placeholder sourced answer'
    assert result.json()['sources'][0]['title']=='placeholder source'
    assert 'placeholder private' not in result.text
    assert answered.await_args.args[1]==A
    w4.runtime.run_route.assert_not_awaited()


@pytest.mark.asyncio
async def test_reviews_page_refreshes_existing_m1_read_and_keeps_tenant_receipt(w4,monkeypatch):
    import trigger_marketing
    location='accounts/123/locations/456'
    await w4.pool.execute("INSERT INTO tank.trigger_gbp_connections(tenant_id,generation,status,location,user_id) VALUES($1,$2,'connected',$3,'placeholder-founder')",A,uuid4(),location)
    async def refresh(tenant):
        assert tenant==A
        await w4.pool.execute("INSERT INTO tank.trigger_gbp_reviews(tenant_id,location,review_id,rating,text,updated_at) VALUES($1,$2,'placeholder-review','FIVE','placeholder review',now())",tenant,location)
    store=SimpleNamespace(reviews=AsyncMock(side_effect=refresh))
    monkeypatch.setattr(trigger_marketing,'Marketing',lambda pool:store)
    await w4.pool.execute("INSERT INTO tank.trigger_gbp_reviews(tenant_id,location,review_id,rating,text,updated_at) VALUES($1,$2,'placeholder-other','ONE','placeholder foreign review',now())",B,location)
    result=await w4.client.get('/v1/command/trigger/console/marketing/reviews',headers=w4.private)
    assert result.status_code==200,result.text
    assert len(result.json()['reviews'])==1
    assert 'placeholder foreign' not in result.text
    store.reviews.assert_awaited_once_with(A)
    receipt=await w4.pool.fetchrow('SELECT tenant_id,cost_usd,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2',A,UUID(result.json()['ledger_id']))
    assert receipt['tenant_id']==A and receipt['cost_usd']==0 and receipt['model']=='code'
