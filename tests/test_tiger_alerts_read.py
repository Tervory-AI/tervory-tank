"""Offline Tiger alert reads: placeholder-only data, memory and disposable SQL."""
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import command
import httpx
import pytest
import pytest_asyncio
import tiger_alerts
from fastapi import FastAPI
from test_tiger_competitors import database as database, postgres as postgres, offline_dns as offline_dns
from watch import MemoryStore, PgStore, _alert_out

ROOT = Path(__file__).resolve().parents[1]
TENANT = UUID('11111111-1111-4111-8111-111111111111')
OTHER = UUID('22222222-2222-4222-8222-222222222222')
EMPTY = UUID('33333333-3333-4333-8333-333333333333')
URL = 'https://placeholder.example/product'
ALT = 'https://placeholder.example/other-product'
KINDS = ('price', 'stock', 'new_product', 'below_cost', 'market_gap')
STAMP = datetime(2026, 11, 3, 12, tzinfo=timezone.utc)


@pytest_asyncio.fixture(params=['memory', 'postgres'])
async def runtime(request, database, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://placeholder@127.0.0.1/placeholder')
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'placeholder-litellm-key')
    monkeypatch.setenv('TANK_API_KEY', 'placeholder-tank-key')
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'placeholder-founder')
    import main
    spec = importlib.util.spec_from_file_location('placeholder_tiger_alerts_room', ROOT/'agents/tiger/app.py')
    room = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, room)
    spec.loader.exec_module(room)
    store = MemoryStore() if request.param == 'memory' else PgStore(database)
    monkeypatch.setattr(room, '_store', lambda: store)
    for tenant in (TENANT, OTHER, EMPTY):
        await database.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,'tiger','placeholder-founder')", tenant)
    for tenant in (TENANT, OTHER):
        for index, kind in enumerate(KINDS):
            row = {'id':uuid4(), 'tenant_id':tenant, 'url':URL if index < 2 else ALT,
                   'ts':STAMP+timedelta(seconds=index), 'kind':kind,
                   'before':'placeholder-before', 'after':'placeholder-'+str(tenant)+'-'+kind}
            if isinstance(store, MemoryStore):
                store.alerts.append(_alert_out(row))
            else:
                await database.execute("""INSERT INTO agent_tiger.alerts(id,tenant_id,url,ts,kind,before,after)
                    VALUES($1,$2,$3,$4,$5,$6,$7)""", *row.values())
    rt = SimpleNamespace(pool=database, store=store, room=room, calls=[], inject_foreign=False,
                         main=main, actor=command.Actor(TENANT, 'placeholder-user', False, frozenset({'tiger'})))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://placeholder-room') as room_client:
        rt.room_client = room_client
        class Relay:
            async def request(self, method, url, **kwargs):
                rt.calls.append((method, url, kwargs['params']))
                response = await room_client.request(method, urlsplit(url).path, params=kwargs['params'])
                if rt.inject_foreign and response.status_code == 200:
                    payload = response.json()
                    payload['alerts'].append({'id':str(uuid4()), 'tenant_id':str(OTHER), 'url':URL,
                        'ts':STAMP.isoformat(), 'kind':'price', 'before':None, 'after':'placeholder-foreign'})
                    return httpx.Response(200, json=payload)
                return response
        monkeypatch.setattr(main, '_http', Relay())
        monkeypatch.setattr(main, 'pool', lambda: database)
        monkeypatch.setattr(main, 'box_region', lambda: 'us-east')
        monkeypatch.setattr(main, 'TANK_API_KEY', 'placeholder-tank-key')
        app = FastAPI()
        app.include_router(tiger_alerts.build_router())
        app.include_router(command.router)
        async def identity(): return rt.actor
        app.dependency_overrides[command.identity] = identity
        monkeypatch.setattr(main, 'app', app)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder-tank') as client:
            rt.client = client
            yield rt


async def receipts(rt):
    return await rt.pool.fetch("SELECT tenant_id,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out FROM tank.ledger ORDER BY ts")


async def read(rt, **params):
    before = len(await receipts(rt))
    response = await rt.client.get('/v1/command/tiger/alerts', params=params)
    assert response.status_code == 200, response.text
    rows = await receipts(rt)
    assert len(rows) == before+1
    row = rows[-1]
    assert row['tenant_id'] == rt.actor.tenant_id
    assert row['agent'] == 'tiger' and row['task_type'] == 'tiger.alerts'
    assert row['rung'] == 3 and row['model'] == 'code'
    assert row['cost_usd'] == row['tokens_in'] == row['tokens_out'] == 0
    data = response.json()
    assert data['cost_usd'] == 0 and UUID(data['ledger_id'])
    assert set(data) == {'alerts','counts','ledger_id','cost_usd'}
    return data


@pytest.mark.asyncio
async def test_all_five_saved_kinds_and_data_only_counts(runtime):
    data = await read(runtime)
    assert len(data['alerts']) == 5 and data['counts'] == dict.fromkeys(KINDS, 1)
    assert {row['kind'] for row in data['alerts']} == set(KINDS)
    assert all(set(row) == {'id','url','ts','kind','before','after'} for row in data['alerts'])
    assert all(str(TENANT) in row['after'] for row in data['alerts'])


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', KINDS)
async def test_kind_filter_and_one_tiger_zero_receipt(runtime, kind):
    data = await read(runtime, kind=kind)
    assert len(data['alerts']) == 1 and data['alerts'][0]['kind'] == kind
    assert data['counts'] == {name:int(name == kind) for name in KINDS}
    assert runtime.calls[-1][2] == [('tenant_id',str(TENANT)), ('kind',kind)]


@pytest.mark.asyncio
async def test_url_filter_and_combined_kind(runtime):
    data = await read(runtime, url=URL)
    assert {row['kind'] for row in data['alerts']} == {'price','stock'}
    assert data['counts'] == {name:int(name in {'price','stock'}) for name in KINDS}
    data = await read(runtime, url=URL, kind='below_cost')
    assert data['alerts'] == [] and data['counts'] == dict.fromkeys(KINDS, 0)


@pytest.mark.asyncio
async def test_unknown_kind_is_422_in_room_and_tank(runtime):
    assert (await runtime.room_client.get('/alerts', params={'tenant_id':str(TENANT),'kind':'placeholder-unknown'})).status_code == 422
    assert (await runtime.client.get('/v1/command/tiger/alerts', params={'kind':'placeholder-unknown'})).status_code == 422
    assert runtime.calls == [] and await receipts(runtime) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('url',['ftp://placeholder.example/product','https://placeholder-user:placeholder-password@placeholder.example/product','placeholder'])
async def test_url_rules_match_existing_urlargs(runtime, url):
    assert (await runtime.client.get('/v1/command/tiger/alerts', params={'url':url})).status_code == 422
    assert runtime.calls == [] and await receipts(runtime) == []


@pytest.mark.asyncio
@pytest.mark.parametrize('url',[None,URL])
async def test_no_kind_room_response_is_byte_identical_to_previous_query(runtime,url):
    if isinstance(runtime.store, MemoryStore):
        rows = [dict(row) for row in runtime.store.alerts if row['tenant_id'] == str(TENANT) and (url is None or row['url'] == url)]
    else:
        await runtime.pool.executemany("""INSERT INTO agent_tiger.alerts(tenant_id,url,ts,kind,before,after)
            VALUES($1,$2,$3,'price','placeholder-before','placeholder-after')""",
            [(TENANT,URL,STAMP+timedelta(minutes=i+1)) for i in range(205)])
        rows = [_alert_out(row) for row in await runtime.pool.fetch("""SELECT id,tenant_id,url,ts,kind,before,after
            FROM agent_tiger.alerts WHERE tenant_id=$1 AND ($2::text IS NULL OR url=$2)
            ORDER BY ts DESC LIMIT 200""", TENANT, url)]
        assert len(rows) == 200
    expected = json.dumps({'alerts':rows}, separators=(',',':'), ensure_ascii=False).encode()
    params = {'tenant_id':str(TENANT), **({'url':url} if url else {})}
    response = await runtime.room_client.get('/alerts', params=params)
    assert response.status_code == 200 and response.content == expected


@pytest.mark.asyncio
async def test_tenant_scope_and_existing_page_response_filter(runtime):
    runtime.inject_foreign = True
    data = await read(runtime, tenant_id=str(TENANT))
    assert len(data['alerts']) == 5 and data['counts'] == dict.fromkeys(KINDS, 1)
    assert all(str(TENANT) in row['after'] for row in data['alerts'])
    before = len(await receipts(runtime))
    assert (await runtime.client.get('/v1/command/tiger/alerts', params={'tenant_id':str(OTHER)})).status_code == 403
    assert len(await receipts(runtime)) == before
    runtime.inject_foreign = False
    runtime.actor = command.Actor(OTHER, 'placeholder-other-user', False, frozenset({'tiger'}))
    other = await read(runtime)
    assert {row['id'] for row in data['alerts']}.isdisjoint(row['id'] for row in other['alerts'])
    assert all(str(OTHER) in row['after'] for row in other['alerts'])


@pytest.mark.asyncio
async def test_empty_tenant_has_zero_counts_and_one_receipt(runtime):
    runtime.actor = command.Actor(EMPTY, 'placeholder-empty-user', False, frozenset({'tiger'}))
    data = await read(runtime)
    assert data['alerts'] == [] and data['counts'] == dict.fromkeys(KINDS, 0)


@pytest.mark.asyncio
async def test_without_tiger_squad_is_403_without_relay_or_receipt(runtime):
    runtime.actor = command.Actor(TENANT, 'placeholder-user', False, frozenset())
    assert (await runtime.client.get('/v1/command/tiger/alerts')).status_code == 403
    assert runtime.calls == [] and await receipts(runtime) == []


@pytest.mark.asyncio
async def test_pending_card_confirms_through_ordinary_dispatch_with_zero_receipt(runtime,monkeypatch):
    import trigger_commands
    side_effect_dispatch = AsyncMock(side_effect=AssertionError('placeholder: not a confirmed-dispatch tool'))
    ordinary_dispatch = AsyncMock(wraps=command.dispatch_action)
    monkeypatch.setattr(trigger_commands,'dispatch_confirmed',side_effect_dispatch)
    monkeypatch.setattr(command,'dispatch_action',ordinary_dispatch)
    assert command.ADAPTERS['tiger.alerts'].method == 'GET'
    assert not command.ADAPTERS['tiger.alerts'].paid
    saved_alerts = await runtime.store.list_alerts(str(TENANT),None)
    thread_reply = await runtime.client.post('/v1/command/threads',json={'title':'placeholder alerts read'})
    assert thread_reply.status_code == 200
    thread = thread_reply.json()['thread_id']
    proposal = await runtime.client.post(f'/v1/command/threads/{thread}/actions',
        json={'tool':'tiger.alerts','arguments':{'kind':'below_cost'}})
    assert proposal.status_code == 200,proposal.text
    card = proposal.json()
    assert card['tool'] == 'tiger.alerts' and card['status'] == 'pending'
    assert runtime.calls == [] and await receipts(runtime) == []
    ordinary_dispatch.assert_not_awaited()
    route = '/v1/command/cards/'+card['card_id']
    response = await runtime.client.post(route,json={'action':'confirm'})
    assert response.status_code == 200,response.text
    confirmed = response.json()
    assert confirmed['status'] == 'confirmed' and confirmed['receipt_status'] == 'recorded'
    assert confirmed['result']['counts']['below_cost'] == 1 and confirmed['result']['cost_usd'] == 0
    ordinary_dispatch.assert_awaited_once()
    side_effect_dispatch.assert_not_awaited()
    rows = await receipts(runtime)
    assert len(rows) == 1 and rows[0]['agent'] == 'tiger' and rows[0]['task_type'] == 'tiger.alerts'
    assert rows[0]['rung'] == 3 and rows[0]['model'] == 'code' and rows[0]['cost_usd'] == 0
    snapshot = (await runtime.client.get('/v1/command/threads/'+thread)).json()
    assert snapshot['cards'][0]['status'] == 'confirmed'
    assert len(snapshot['receipts']) == 1 and snapshot['receipts'][0]['cost_usd'] == 0
    assert snapshot['receipts'][0]['ledger_id'] == confirmed['result']['ledger_id']
    # Ordinary Confirm retries return the saved result, never another read/receipt.
    assert (await runtime.client.post(route,json={'action':'confirm'})).json()['status'] == 'confirmed'
    assert len(runtime.calls) == 1 and len(await receipts(runtime)) == 1
    ordinary_dispatch.assert_awaited_once()
    assert await runtime.store.list_alerts(str(TENANT),None) == saved_alerts


@pytest.mark.asyncio
async def test_typed_tiger_alerts_never_calls_model_planner(runtime,monkeypatch):
    paid = AsyncMock(side_effect=AssertionError('placeholder: no model planner for tiger.alerts'))
    monkeypatch.setattr(runtime.main,'run_route',paid)
    result = await command.route_turn(runtime.actor,[{'role':'user','content':'tiger.alerts'}])
    assert json.loads(result.content)['actions'] == [{'tool':'tiger.alerts','arguments':{}}]
    paid.assert_not_awaited()
    rows = await receipts(runtime)
    assert len(rows) == 1 and rows[0]['agent'] == 'tiger' and rows[0]['cost_usd'] == 0
