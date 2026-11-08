"""Real Hermes records, in-process Qdrant and Tank; no paid provider calls."""
from contextvars import ContextVar
import json
import os
import uuid

import httpx
import pytest
import pytest_asyncio
from qdrant_client import QdrantClient

import engine_memory
import product_identity
from trigger_signin_fakes import set_founders
from hermes_lifecycle import personal_headers
from hermes.record_index import RecordIndex
from hermes.records import Records
from hermes.service import create_app
from hermes.store import InMemoryStore
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_engine_ladder import setup_engine, local_gateway


class MemoryEncoder:
    def validate(self, text):
        pass

    def embed(self, text):
        return [1., 0., 0., 0.]


@pytest_asyncio.fixture
async def remembered(boundary, monkeypatch):  # noqa: F811
    b = boundary
    index = RecordIndex(QdrantClient(':memory:'), 4)
    records = Records(b.pool, index, MemoryEncoder(), 'engine-memory-test', ['tank'])
    await records.setup()
    app = create_app(InMemoryStore(), MemoryEncoder(), records=records)
    client_type = httpx.AsyncClient
    monkeypatch.setattr(engine_memory, 'HTTP', lambda **kwargs: client_type(transport=httpx.ASGITransport(app=app), **kwargs))
    b.memories, b.memory_app = records, app
    async with client_type(transport=httpx.ASGITransport(app=app), base_url='http://hermes',
            headers={'X-Tank-Key': b.key}) as client:
        b.memory_client = client
        yield b
    index.client.close()


@pytest.mark.asyncio
async def test_memory_cannot_remember_another_tenants_receipt(remembered):
    b = remembered
    ledger = uuid.uuid4()
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,outcome)
            VALUES($1,$2,'tank','engine.classify','local','delivered')""", ledger, b.tenants[0])
        await conn.execute("""INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content)
            VALUES($1,$2,'engine.classify','[]','private answer')""", ledger, b.tenants[0])
    response = await b.memory_client.post('/engine/remember', json={'tenant_id': str(b.tenants[1]), 'ledger_id': str(ledger)})
    assert response.status_code == 404
    assert await b.memories.list('tank', str(b.tenants[1]), 'client') == []
    body = {'tenant_id': str(b.tenants[0]), 'ledger_id': str(ledger)}
    assert (await b.memory_client.post('/engine/remember', json=body)).status_code == 422
    assert (await b.memory_client.post('/engine/remember', json=body, headers={'X-Tank-Key': ''})).status_code == 401
    assert (await b.memory_client.post('/engine/remember', json={**body, 'claim': 'forged'})).status_code == 422


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('ENGINE_LOCAL_URL'), reason='real cloud-local llama.cpp server required')
async def test_correction_changes_next_local_answer_only_for_its_tenant(remembered, monkeypatch):
    b = remembered
    req = await setup_engine(b, monkeypatch)
    actor = product_identity.User(str(req.tenant_id), "placeholder-founder", "founder")
    monkeypatch.setattr(product_identity, "current", ContextVar("placeholder_engine_user", default=actor))
    set_founders(monkeypatch, "placeholder-founder")
    async with b.pool.acquire() as conn:
        await conn.execute("""UPDATE tank.policy SET task_type='engine.answer', system_prompt=
            'Answer using the newest tenant fact. Output only the office city. If no office city is known, output UNKNOWN.'
            WHERE task_type='engine.classify'""")
    req = req.model_copy(update={'task_type': 'engine.answer', 'messages': [b.tank.Message(role='user', content='What is our office city?')]})
    calls = local_gateway(b, monkeypatch)
    async def fact(claim):
        body = {'id': str(uuid.uuid4()), 'tenant_id': str(req.tenant_id), 'agent': 'tank', 'claim': claim}
        headers, raw = personal_headers(b.key, 'POST', '/founder/memories',
            tenant=str(req.tenant_id), user='placeholder-founder', body=body,
            extra={'X-Tervory-Admin': 'placeholder-founder'})
        response = await b.memory_client.post('/founder/memories', headers=headers, content=raw)
        assert response.status_code == 200, response.text
    await fact('Our office city is Paris.')
    recalled, evidence = await engine_memory.recall(b.tank, req)
    assert evidence['hits'] == 1, evidence
    assert 'Paris' in recalled.messages[0].content
    # This answer task has an independently known fact. Both real local models
    # are screened; the smaller model may fail, so the stronger one must earn
    # its place by answering the same gold case correctly.
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.evals(tenant_id,task_type,input,expected)
            VALUES($1,'engine.answer',$2::jsonb,'"Paris"')""", req.tenant_id,
            json.dumps({'messages': [m.model_dump() for m in recalled.messages]}))
    first = await b.tank.run_route(req)
    assert first.content.strip().rstrip('.').lower() == 'paris', b.model_requests
    assert first.engine['memory_hits'] == 1 and first.engine['remembered']
    await fact('Correction: our office city is Berlin, not Paris.')
    second = await b.tank.run_route(req)
    assert second.content.strip().rstrip('.').lower() == 'berlin'
    assert second.rung != 4 and second.engine['remembered']
    assert second.cost_usd == 0 and set(calls) <= {'local', 'local-large'}
    foreign = await b.tank.run_route(req.model_copy(update={'tenant_id': b.tenants[1]}))
    assert foreign.content.strip().rstrip('.').upper() == 'UNKNOWN'
    assert foreign.engine['memory_hits'] == 0
    rows = await b.memories.list('tank', str(b.tenants[1]), 'client')
    assert 'Berlin' not in json.dumps(rows) and 'Paris' not in json.dumps(rows)


@pytest.mark.asyncio
async def test_engine_corridor_uses_the_same_sql_user_wall(remembered):
    b = remembered
    tenant = str(b.tenants[0])
    # Historical automatic outcomes without an owner must remain hidden.
    await b.memories.save('tank', tenant, 'placeholder legacy personal outcome', [], kind='engine.outcome')
    await b.memories.save('tank', tenant, 'placeholder private A', [], meta={'user_id': 'placeholder-user-a'})
    await b.memories.save('tank', tenant, 'placeholder private B', [], meta={'user_id': 'placeholder-user-b'})
    for user, expected in ((None, []), ('placeholder-user-a', ['placeholder private A']),
                           ('placeholder-user-b', ['placeholder private B'])):
        body = {'tenant_id': tenant, 'task_type': 'engine.answer', 'query': 'placeholder query'}
        if user:
            body['user_id'] = user
        if user:
            headers, raw = personal_headers(b.key, 'POST', '/engine/recall', tenant=tenant, user=user, body=body)
            response = await b.memory_client.post('/engine/recall', headers=headers, content=raw)
        else:
            response = await b.memory_client.post('/engine/recall', json=body)
        assert response.status_code == 200
        assert [row['claim'] for row in response.json()['memories']] == expected


@pytest.mark.asyncio
async def test_unsigned_engine_never_recalls_or_creates_shared_outcomes(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(product_identity, "current", ContextVar("placeholder_unsigned", default=None))
    async def forbidden(*args, **kwargs):
        pytest.fail("unsigned call must not access memory")
    monkeypatch.setattr(engine_memory, "send", forbidden)
    request = SimpleNamespace(tenant_id=uuid.uuid4())
    recalled, state = await engine_memory.recall(None, request)
    assert recalled is request and state == {"hits": 0, "status": "unsigned"}
    assert not await engine_memory.remember(request, SimpleNamespace(ledger_id=uuid.uuid4()))
