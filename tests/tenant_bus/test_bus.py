"""Real Redis delivery semantics and authenticated Tank boundaries, offline."""
from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import ValidationError

from chassis import events
from chassis.job_contract import Job
from event_bus import Scope, TigerFact

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'
EVENT = 'tiger.price.changed'


def scope(tenant=A, agent='rig', region='us-east'):
    return Scope(UUID(tenant), agent, region)


def facts():
    return dict(watch_id=str(uuid4()), observation_id=str(uuid4()), sku='item',
                page_id=hashlib.sha256(b'https://shop.example/item').hexdigest(), previous_price='10',
                price='12', currency='USD', observed_at=datetime.now(timezone.utc).isoformat())


def headers(agent='rig', tenant=A):
    return {'X-Tank-Key': 'offline-' + agent, 'X-Tervory-Tenant': tenant, 'X-Tervory-Region': 'us-east'}


def test_job_roundtrip_and_room_authority():
    for column in ('kind', 'task_type'):
        wire = Job(tenant_id=A, agent='base', region='us-east', skill='base.enrich',
                   input={'tenant_id': B, 'note': 'kept in job, never copied to events'},
                   priority='batch', engine='ffl')
        row = wire.to_room(skill_column=column)
        assert set(row) == {'tenant_id', column, 'input'}
        row['input'] = json.dumps(row['input'])
        assert Job.from_room(row, agent='base', region='us-east', skill_column=column) == wire
        with pytest.raises(ValueError):
            Job.from_room(row, agent='base', region='za', skill_column=column)
    with pytest.raises(ValueError):
        Job.from_room({'tenant_id': A, 'kind': 'ping', 'input': {'_job_contract': []}}, agent='rig', region='us-east')
    with pytest.raises(ValidationError):
        Job(tenant_id=A, region='us-east', agent='base', skill='base.enrich', tenant_override=B)


@pytest.mark.asyncio
async def test_stream_isolation_dedup_ack_and_trimming(bus):
    reference = uuid4()
    payload = facts()
    event_a = await bus.publish(scope(agent='tiger'), EVENT, reference, payload)
    assert await bus.publish(scope(agent='tiger'), EVENT, reference, payload) == event_a
    event_b = await bus.publish(scope(B, 'tiger'), EVENT, reference, payload)
    assert event_b != event_a
    assert await bus.redis.xlen(scope().stream(EVENT)) == 1
    consumer = str(uuid4())
    rows_a = await bus.receive(scope(), EVENT, consumer)
    rows_b = await bus.receive(scope(B), EVENT, consumer)
    assert [r['event_id'] for r in rows_a] == [event_a]
    assert [r['event_id'] for r in rows_b] == [event_b]
    row = rows_a[0]
    assert await bus.settle(scope(), EVENT, 'wrong-owner', row['id'], 'ack') == 0
    assert await bus.settle(scope(), EVENT, consumer, row['id'], 'ack') == 1
    assert await bus.settle(scope(), EVENT, consumer, row['id'], 'ack') == 0
    assert await bus.receive(scope(), EVENT, consumer) == []
    for _ in range(7):
        await bus.publish(scope(agent='tiger'), EVENT, uuid4(), facts())
    assert await bus.redis.xlen(scope().stream(EVENT)) == 3
    with pytest.raises(PermissionError):
        await bus.receive(scope(agent='base'), EVENT, consumer)
    with pytest.raises(PermissionError):
        await bus.publish(scope(agent='rig'), EVENT, uuid4(), payload)


@pytest.mark.asyncio
async def test_retry_five_then_bounded_dead_letter_and_crash_recovery(bus):
    for _ in range(4):
        await bus.publish(scope(agent='tiger'), EVENT, uuid4(), facts())
        first_owner = None
        for attempt in range(1, 6):
            consumer = str(uuid4())  # Simulates a restarted Rig process claiming pending work.
            message, = await bus.receive(scope(), EVENT, consumer)
            assert message['attempt'] == attempt
            if first_owner:
                assert await bus.settle(scope(), EVENT, first_owner, message['id'], 'ack') == 0
            first_owner = consumer
            assert await bus.settle(scope(), EVENT, consumer, message['id'], 'fail') == (2 if attempt == 5 else 1)
        assert await bus.receive(scope(), EVENT, str(uuid4())) == []
        assert (await bus.redis.xpending(scope().stream(EVENT), 'rig'))['pending'] == 0
    dead = await bus.redis.xrange(scope().stream(EVENT) + ':dead')
    assert len(dead) == 3
    assert all(row['attempts'] == '5' and row['group'] == 'rig' for _, row in dead)
    await bus.publish(scope(agent='tiger'), EVENT, uuid4(), facts())
    for _ in range(5):
        assert len(await bus.receive(scope(), EVENT, str(uuid4()))) == 1
    assert await bus.receive(scope(), EVENT, str(uuid4())) == []  # Abandoned work cannot loop forever.
    assert (await bus.redis.xpending(scope().stream(EVENT), 'rig'))['pending'] == 0


@pytest.mark.asyncio
async def test_private_corridor_uses_authenticated_scope_not_message(corridor, bus):
    body = {'event': EVENT, 'source_id': str(uuid4()), 'facts': facts()}
    for modified in ({**body, 'tenant_id': B}, {**body, 'facts': {**body['facts'], 'tenant_id': B}},
                     {**body, 'facts': {**body['facts'], 'text': 'client text'}}):
        assert (await corridor.post('/v1/events/publish', headers=headers('tiger'), json=modified)).status_code == 422
    assert (await corridor.post('/v1/events/publish', headers=headers('rig'), json=body)).status_code == 403
    assert (await corridor.post('/v1/events/publish?tenant_id=' + B, headers=headers('tiger'), json=body)).json()['published']
    consumer = {'event': EVENT, 'consumer': str(uuid4())}
    for agent, status in [('workspace', 403), ('tiger', 403), ('client', 401)]:
        assert (await corridor.post('/v1/events/receive', headers=headers(agent), json=consumer)).status_code == status
    assert (await corridor.post('/v1/events/receive', headers=headers('rig', B), json=consumer)).json() == {'messages': []}
    assert len((await corridor.post('/v1/events/receive?tenant_id=' + B, headers=headers(), json=consumer)).json()['messages']) == 1
    wrong_region = {**headers(), 'X-Tervory-Region': 'za'}
    assert (await corridor.post('/v1/events/receive', headers=wrong_region, json=consumer)).status_code == 403
    assert (await corridor.post('/v1/events/receive', headers={'X-Tank-Key': 'offline-rig'}, json=consumer)).status_code == 401
    assert await bus.redis.xlen(scope(B).stream(EVENT)) == 0


@pytest.mark.asyncio
async def test_redis_failure_is_best_effort_without_private_logs(corridor, bus, monkeypatch, caplog):
    async def broken(*args, **kwargs):
        raise RuntimeError('private-marker-must-not-appear')
    monkeypatch.setattr(bus.redis, 'eval', broken)
    result = await corridor.post('/v1/events/publish', headers=headers('tiger'),
                                json={'event': EVENT, 'source_id': str(uuid4()), 'facts': facts()})
    assert result.status_code == 200 and result.json() == {'published': False}
    monkeypatch.setattr(events, '_retry_after', 0)
    monkeypatch.setenv('TANK_KEY', 'offline-tiger')
    calls = []
    async def failed(request):
        calls.append(request)
        raise httpx.ConnectError('private-marker-must-not-appear')
    async with httpx.AsyncClient(transport=httpx.MockTransport(failed)) as http:
        assert not await events.publish(A, EVENT, 'offline-source', facts(), http=http)
        assert not await events.publish(A, EVENT, 'offline-source', facts(), http=http)
    assert len(calls) == 1
    assert 'private-marker' not in caplog.text
    monkeypatch.setattr(events, '_retry_after', 0)
    monkeypatch.delenv('TANK_KEY')
    async with httpx.AsyncClient(transport=httpx.MockTransport(failed)) as http:
        assert not await events.publish(A, EVENT, 'offline-source', facts(), http=http)
    assert len(calls) == 1


@pytest.mark.parametrize('change', [{'price': 'NaN'}, {'price': '-1'}, {'observed_at': '2026-10-28'},
                                   {'currency': 'USD secret'}, {'url': 'https://private.example'}, {'client_text': 'private'}])
def test_events_refuse_nonfacts(change):
    with pytest.raises(ValidationError):
        TigerFact.model_validate({**facts(), **change})
