"""Radix's actual bus retry/dead-letter semantics, using a fake room queue."""
import json
from pathlib import Path
import sys
from uuid import UUID, uuid4

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'agents/radix'))
import regulation_events as events
from event_bus import MAX_TRIES, Scope

A = '11111111-1111-4111-8111-111111111111'
B = '22222222-2222-4222-8222-222222222222'


@pytest.mark.asyncio
async def test_malformed_regulation_delivery_retries_then_dead_letters(bus, monkeypatch):
    actor = Scope(UUID(A), 'radix', 'us-east')
    await bus.redis.xadd(actor.stream(events.EVENT), {
        'event_id': str(uuid4()), 'region': 'us-east',
        'facts': json.dumps({'document_id': 'placeholder-malformed'}),
    })
    attempts = []
    class Queue:
        async def tenant_ids(self): return [A]
        async def enqueue(self, tenant, message):
            attempts.append(message['attempt'])
            events.facts(message['facts'])
    async def request(http, tenant, operation, body):
        assert tenant == A and body['event'] == events.EVENT
        if operation == 'receive':
            return {'messages': await bus.receive(actor, body['event'], body['consumer'])}
        assert body['action'] == 'fail'
        return {'settled': await bus.settle(actor, body['event'], body['consumer'], body['id'], body['action'])}
    monkeypatch.setattr(events, 'request', request)
    consumer = str(uuid4())
    for _ in range(MAX_TRIES + 1):
        assert await events.consume_tenant(Queue(), None, A, consumer) == 0
    assert attempts == list(range(1, MAX_TRIES + 1))
    dead = await bus.redis.xrange(actor.stream(events.EVENT) + ':dead')
    assert len(dead) == 1 and dead[0][1]['group'] == 'radix'
    assert dead[0][1]['attempts'] == str(MAX_TRIES)
    assert await bus.receive(actor, events.EVENT, consumer) == []
    assert await bus.receive(Scope(UUID(B), 'radix', 'us-east'), events.EVENT, consumer) == []
