"""ML6 offline delivery proof: disposable SQL, local SMTP and ASGI webhook receiver."""
import asyncio
import json
from contextlib import asynccontextmanager
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI, Request

import command
import market_lab_ml3 as tank
from core import briefs
from core.ledger import MemoryLedger, PostgresLedger
from core.ml3 import build_router
from test_market_lab_ml3 import database as database, OWNER, OTHER, PLACEHOLDER
from test_market_lab_ml5 import NOW, original
from test_tiger_alert_email import catcher as catcher


def report(tenant=OWNER, citations=None):
    return {'id': str(uuid4()), 'tenant_id': str(tenant), 'made_at': NOW,
            'question': 'placeholder saved report title', 'answer': 'placeholder saved brief text',
            'citations': citations if citations is not None else [
                {'claim': 'placeholder citation', 'date': '2026-11-03', 'url': 'https://placeholder.example/source'}]}


@pytest.fixture
async def ledger(database):
    value = PostgresLedger(database.pool)
    await value.apply_schema()
    return value


async def opt_in(db, *, email=True, webhook=True):
    await db.pool.execute(
        "INSERT INTO tank.market_lab_alerts(tenant_id,email_enabled,email_since,webhook_url,webhook_sealed,webhook_since) "
        "VALUES($1,$2,$3,$4,'placeholder-sealed',$3)", OWNER, email, NOW - timedelta(days=1),
        'https://placeholder.example/hooks' if webhook else None)


@pytest.fixture
async def receiver(database, monkeypatch):
    received = []
    app = FastAPI()

    @app.post('/placeholder')
    async def accept(request: Request):
        raw = await request.body()
        assert request.headers['x-market-lab-signature'] == tank.signature(raw, PLACEHOLDER)
        body = json.loads(raw)
        assert request.headers['idempotency-key'] == body['report_id']
        received.append(body)
        return {'status': 'placeholder accepted'}

    import vault
    import access
    monkeypatch.setattr(vault, 'open_seal', lambda *args: {'value': PLACEHOLDER})

    @asynccontextmanager
    async def stream(url, **kwargs):
        assert url == 'https://placeholder.example/hooks'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as http:
            response = await http.post('/placeholder', content=kwargs['content'], headers=kwargs['headers'])
            yield response

    monkeypatch.setattr(access, 'public_stream', stream)
    return received


async def corridor(db, operation, payload):
    response = await db.client.post('/v1/market-lab/internal/' + operation, json=payload,
                                    headers={'x-tank-key': 'placeholder-market-lab-key'})
    assert response.status_code == 200
    return response.json()


@pytest.mark.asyncio
async def test_once_per_channel_saved_body_and_signature(database, ledger, catcher, receiver):
    await opt_in(database)
    saved = report()
    await briefs.save(ledger, saved, now=NOW)
    async def call(operation, payload): return await corridor(database, operation, payload)
    for _ in range(2):
        await briefs.deliver(ledger, str(OWNER), corridor=call, transport=catcher.transport,
                             recipient='placeholder@example.test', now=NOW)
    assert len(catcher.messages) == len(receiver) == 1
    message = catcher.messages[0]
    assert str(message['Subject']) == saved['question']
    assert message.get_content().replace('\r\n', '\n').rstrip('\n') == '\n'.join([
        saved['answer'], 'placeholder citation', '2026-11-03', 'https://placeholder.example/source'])
    assert receiver[0] == {'report_id': saved['id'], 'title': saved['question'],
                           'text': saved['answer'], 'citations': saved['citations']}
    rows = await ledger.briefs_for(str(OWNER))
    assert {d['status'] for d in rows[0]['deliveries']} == {'sent'}
    assert await ledger.briefs_for(str(OTHER)) == []


@pytest.mark.asyncio
async def test_alerts_off_and_pre_opt_in_reports_send_nothing(database, ledger, catcher, receiver):
    await opt_in(database, email=False, webhook=False)
    await briefs.save(ledger, report(), now=NOW)
    async def call(operation, payload): return await corridor(database, operation, payload)
    await briefs.deliver(ledger, str(OWNER), corridor=call, transport=catcher.transport,
                         recipient='placeholder@example.test', now=NOW)
    assert catcher.messages == receiver == []
    assert {d['status'] for d in (await ledger.briefs_for(str(OWNER)))[0]['deliveries']} == {'suppressed'}
    assert not await ledger.update_brief(str(OTHER), (await ledger.briefs_for(str(OWNER)))[0]['id'], 'email', 'sending', expected='suppressed')


@pytest.mark.asyncio
@pytest.mark.parametrize('age,expected', [(89, 'held'), (90, 'pending')])
async def test_closed_prediction_is_held_with_reason_and_open_is_queued(ledger, age, expected):
    row, resolved = original(age)
    await ledger.save_prediction(row)
    await ledger.save_prediction(resolved)
    saved = report(citations=[{'prediction_id': row['id'], 'claim': 'placeholder forecast',
                              'url': 'https://placeholder.example/forecast'}])
    await briefs.save(ledger, saved, now=NOW)
    states = (await ledger.briefs_for(str(OWNER)))[0]['deliveries']
    assert {state['status'] for state in states} == {expected}
    assert all(bool(state['reason']) == (expected == 'held') for state in states)
    assert not await ledger.pending_briefs(str(OWNER), 'email') if expected == 'held' else True


@pytest.mark.asyncio
@pytest.mark.parametrize('channel', ['email', 'webhook'])
async def test_crash_after_acceptance_never_reclaims_sending(database, ledger, catcher, receiver, channel):
    await opt_in(database, email=channel == 'email', webhook=channel == 'webhook')
    saved = report()
    await briefs.save(ledger, saved, now=NOW)
    real_update = ledger.update_brief
    async def interrupted(tenant, ident, mode, state, *args, **kwargs):
        if mode == channel and state == 'sent':
            raise asyncio.CancelledError
        return await real_update(tenant, ident, mode, state, *args, **kwargs)
    ledger.update_brief = interrupted
    async def call(operation, payload): return await corridor(database, operation, payload)
    with pytest.raises(asyncio.CancelledError):
        await briefs.deliver(ledger, str(OWNER), corridor=call, transport=catcher.transport,
                             recipient='placeholder@example.test', now=NOW)
    ledger.update_brief = real_update
    await briefs.deliver(ledger, str(OWNER), corridor=call, transport=catcher.transport,
                         recipient='placeholder@example.test', now=NOW)
    assert len(catcher.messages) == (1 if channel == 'email' else 0)
    assert len(receiver) == (1 if channel == 'webhook' else 0)
    states = (await ledger.briefs_for(str(OWNER)))[0]['deliveries']
    assert next(d['status'] for d in states if d['channel'] == channel) == 'sending'


@pytest.mark.asyncio
async def test_last_twelve_briefs_are_tenant_scoped_zero_cost_code_read(database, ledger, monkeypatch):
    for i in range(14):
        saved = report(citations=[])
        saved['made_at'] = NOW + timedelta(seconds=i)
        await briefs.save(ledger, saved, now=NOW)
    await briefs.save(ledger, report(OTHER, []), now=NOW)
    @asynccontextmanager
    async def context(): yield ledger
    app = FastAPI()
    app.include_router(build_router(key_ok=lambda key: key == 'placeholder-room', ledger_context=context, engine='ffl'))
    async def room(operation, tenant):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
            response = await client.post('/market/ml3/' + operation, json={'tenant_id': str(tenant)},
                                         headers={'x-tank-key': 'placeholder-room'})
            assert response.status_code == 200
            return response.json()
    monkeypatch.setattr(tank, 'room', room)
    response = await database.client.get('/v1/market-lab/reads/briefs')
    assert response.status_code == 200
    body = response.json()
    assert body['total'] == 12 and body['cost_usd'] == 0
    row = await database.pool.fetchrow('SELECT tenant_id,model,cost_usd FROM tank.ledger WHERE id=$1', UUID(body['ledger_id']))
    assert row['tenant_id'] == OWNER and row['model'] == 'code' and row['cost_usd'] == 0
    answer = await command.route_turn(database.actor, [{'role': 'user', 'content': 'market_lab.briefs'}])
    assert json.loads(answer.content)['actions'][0]['tool'] == 'market_lab.briefs'
    other = await database.client.get('/v1/market-lab/reads/briefs', headers={'x-placeholder-tenant': str(OTHER)})
    assert other.json()['total'] == 1
    assert not {r['report_id'] for r in body['records']} & {r['report_id'] for r in other.json()['records']}


@pytest.mark.asyncio
async def test_recheck_gate_before_claim_and_atomic_claim_race():
    ledger = MemoryLedger()
    saved = report([] if False else OWNER, [])
    await briefs.save(ledger, saved, now=NOW)
    outcomes = await asyncio.gather(*(briefs.result(ledger.update_brief(str(OWNER), saved['id'], 'email', 'sending', expected='pending')) for _ in range(2)))
    assert outcomes == [True, False]
