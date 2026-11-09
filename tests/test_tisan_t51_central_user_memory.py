"""t51 acceptance: central user-scoped memory, against CURRENT pinned Tank source.

Real vendor hermes.service.create_app + real hermes.records.Records SQL on the
suite's loopback Postgres, the real chassis MemoryClient and Tisan's real
GateMemory adapter. Own dummy agent fixture key (TANK_KEY_TISAN) only; the
dummy workspace key is used solely where Hermes requires it (founder publish).
The vector index/encoder are inert stand-ins whose search returns EVERY
indexed row, so only Hermes' own user scoping can keep users apart.

All cases run as ordinary tests against the immutable fixed shared core
selected by scripts/check.sh; the original vendor remains byte-for-byte intact.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx
import pytest

from agents.tisan import gates_memory

TENANT, OTHER_TENANT = str(uuid.uuid4()), str(uuid.uuid4())
A, B, ADMIN = 'founder-a', 'founder-b', 'founder-admin'
AGENT_KEY = 'dummy-fixture-tisan'
WORKSPACE_KEY = 'dummy-fixture-workspace'



class InertVectors:
    """Index + encoder stand-in: search returns every indexed row of the tenant."""

    def __init__(self):
        self.rows = {}

    def validate(self, claim):
        return None

    def embed(self, text):
        return [0.0] * 384

    def upsert(self, row, vector, model):
        self.rows[str(row['id'])] = str(row['tenant_id'])

    def delete(self, agent, row_id, *rest):
        self.rows.pop(str(row_id), None)

    def search(self, agent, owner, tier, vector, model, kind, limit):
        return [(rid, 1.0) for rid, tenant in self.rows.items() if tenant == str(owner)][:limit]


@pytest.fixture
def hermes(monkeypatch):
    from hermes.records import Records
    from hermes.service import create_app
    shared = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    assert shared, 'scripts/run_tests.py provides the loopback Postgres'
    monkeypatch.setenv('TANK_KEY_TISAN', AGENT_KEY)
    monkeypatch.setenv('TANK_API_KEY', WORKSPACE_KEY)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', ADMIN + ',' + A)
    name = 't51_' + uuid.uuid4().hex[:10]
    url = urlunsplit(urlsplit(shared)._replace(path='/' + name))
    loop = asyncio.new_event_loop()
    vectors = InertVectors()

    async def up():
        admin = await asyncpg.connect(shared)
        await admin.execute(f'CREATE DATABASE "{name}"')
        await admin.close()
        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
        rec = Records(pool, vectors, vectors, 'inert', ['tisan'])
        await rec.setup()
        return pool, rec

    pool, rec = loop.run_until_complete(up())
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(records=rec)), base_url='http://hermes:8000')
    yield loop, http, pool

    async def down():
        await http.aclose()
        await pool.close()
        admin = await asyncpg.connect(shared)
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()
    loop.run_until_complete(down())
    loop.close()


AGENT = {'X-Tank-Key': AGENT_KEY}


async def write(http, tenant, kind, text, *, user=None, tenant_wide=False, index=False):
    import json
    from chassis.user_assertion import bind_personal_headers
    body = {'tenant_id': tenant, 'text': text, 'kind': kind, 'source': 's',
            **({} if index else {'index': False}), **({'user_id': user} if user else {})}
    raw = json.dumps(body).encode()
    headers = {**AGENT, 'Content-Type': 'application/json'}
    if user:
        headers.update(bind_personal_headers(AGENT_KEY, 'POST', '/memories', tenant=tenant, user=user, body=raw))
    return await http.post('/memories', content=raw, headers=headers)


async def listed(http, tenant, user):
    from urllib.parse import urlencode
    from chassis.user_assertion import bind_personal_headers
    target = '/records?' + urlencode({'tenant_id': tenant, 'user_id': user, 'limit': 200})
    response = await http.get(target, headers={**AGENT,
        **bind_personal_headers(AGENT_KEY, 'GET', target, tenant=tenant, user=user)})
    assert response.status_code == 200, response.text
    return {row['id'] for row in response.json()['memories']}


def product(http):
    from chassis.memory import MemoryClient
    return MemoryClient(base_url='http://hermes:8000', api_key=AGENT_KEY, agent='tisan', http=http)


def run(hermes, flow):
    loop, http, pool = hermes
    return loop.run_until_complete(flow(http, pool))


def test_t51_own_user_positive_write_list_recall_through_product_adapter(hermes):
    async def flow(http, _pool):
        gate = gates_memory.GateMemory(product(http), TENANT, A)  # current client: SharedMemoryContractMissing
        saved = await gate.remember_choice(gates_memory.SECTION, 'hero', {'state': 'approved'})
        assert [r['id'] for r in await gate.view()] == [saved['id']]
        calls = []

        async def brain():
            calls.append(1)
            return {'plan': 'p'}, gates_memory.tank_receipt([{'cost_usd': 0.0025, 'tokens_in': 1200, 'tokens_out': 300}])
        await gates_memory.run(product(http), TENANT, A, 'tisan.plan', {'b': 1}, brain)
        repeat = await gates_memory.run(product(http), TENANT, A, 'tisan.plan', {'b': 1}, brain)
        assert calls == [1] and repeat['receipt']['paid_calls'] == 0
        owned_brand = await product(http).remember(TENANT, 'personal brand', gates_memory.BRAND, 's',
                                                   index=False, user_id=A, meta={'value': 'old'})
        edited = await gate.edit(owned_brand['id'], 'new')
        assert edited['meta']['user_id'] == A and edited['meta']['value'] == 'new'
        assert edited['id'] not in await listed(http, TENANT, B)
        assert await gate.forget(edited['id']) == 1
        assert edited['id'] not in await listed(http, TENANT, A)
    run(hermes, flow)


def test_t51_user_a_never_lists_user_b_personal_record(hermes):
    async def flow(http, _pool):
        a = await write(http, TENANT, 'tisan.section', 'a', user=A)
        b = await write(http, TENANT, 'tisan.section', 'b', user=B)
        assert a.status_code == b.status_code == 201, (a.status_code, b.status_code, b.text)
        assert await listed(http, TENANT, A) == {a.json()['id']}
        assert await listed(http, TENANT, B) == {b.json()['id']}
    run(hermes, flow)


def test_t51_user_a_never_recalls_user_b_personal_record(hermes):
    async def flow(http, _pool):
        b = await write(http, TENANT, 'tisan.section', 'b secret', user=B, index=True)
        assert b.status_code == 201, b.text
        hits = await product(http).recall(TENANT, 'secret', user_id=A)
        assert b.json()['id'] not in {m['id'] for m in hits}
        return
    run(hermes, flow)


def test_t51_user_a_never_publishes_user_b_personal_record(hermes):
    async def flow(http, _pool):
        b = await write(http, TENANT, 'tisan.section', 'b secret', user=B)
        assert b.status_code == 201, b.text
        founder = {'X-Tank-Key': WORKSPACE_KEY, 'X-Tervory-Admin': ADMIN}
        policy_body = {
            'tenant_id': TENANT, 'agent': 'tisan', 'enabled': True, 'identifiers': {'reviewed': True, 'names': ['Acme Fixture Ltd'], 'emails': [], 'phones': [], 'addresses': [], 'client_domains': ['fixture.example']}}
        import json
        from chassis.user_assertion import bind_personal_headers
        policy_raw = json.dumps(policy_body).encode()
        policy = await http.post('/founder/publish-policy', content=policy_raw, headers={**founder,
            'Content-Type': 'application/json', **bind_personal_headers(WORKSPACE_KEY, 'POST',
                '/founder/publish-policy', tenant=TENANT, user=ADMIN, body=policy_raw)})
        assert policy.status_code == 200, policy.text
        from chassis.user_assertion import bind_personal_headers
        import json
        raw = json.dumps({'tenant_id': TENANT, 'agent': 'tisan', 'source_row': b.json()['id']}).encode()
        response = await http.post('/founder/publish', headers={**founder, 'X-Tervory-Admin': A, 'Content-Type': 'application/json',
            **bind_personal_headers(WORKSPACE_KEY, 'POST', '/founder/publish', tenant=TENANT, user=A, body=raw)}, content=raw)
        assert response.status_code == 409 and 'missing' in response.text, (response.status_code, response.text)
    run(hermes, flow)


def test_t51_declared_tenant_wide_record_reaches_both_users(hermes):
    async def flow(http, _pool):
        wide = await write(http, TENANT, 'tisan.brand', 'brand', tenant_wide=True)
        assert wide.status_code == 201, (wide.status_code, wide.text)
        assert wide.json()['id'] in await listed(http, TENANT, A)
        assert wide.json()['id'] in await listed(http, TENANT, B)
    run(hermes, flow)


def test_t51_personal_record_without_user_id_is_refused_and_not_stored(hermes):
    async def flow(http, pool):
        response = await write(http, TENANT, 'tisan.section', 'no user')
        from hermes.records import schema_for
        async with pool.acquire() as conn:
            stored = await conn.fetchval(f'SELECT count(*) FROM "{schema_for("tisan")}".memory_records')
        assert response.status_code == 422 and stored == 0, (response.status_code, stored)
    run(hermes, flow)


def test_t51_tenant_wall_holds_for_personal_and_tenant_wide(hermes):
    async def flow(http, _pool):
        await write(http, TENANT, 'tisan.section', 'a', user=A)
        await write(http, TENANT, 'tisan.brand', 'brand', tenant_wide=True)
        assert await listed(http, OTHER_TENANT, A) == set()
    run(hermes, flow)


def test_t51_product_fails_closed_without_shared_contract_and_writes_nothing(hermes):
    """CURRENT-source behaviour the product must have: explicit dependency error, no write, no paid call."""
    import importlib.util
    from pathlib import Path
    legacy_path = Path(__file__).resolve().parents[1] / 'vendor/tervory-tank/agents/_chassis/chassis/memory.py'
    if not legacy_path.exists():
        legacy_path = Path(__file__).resolve().parents[1] / 'tests/fixtures/tisan_unintegrated_core/legacy_memory.py'
    spec = importlib.util.spec_from_file_location('tisan_legacy_memory', legacy_path)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)

    async def flow(http, pool):
        calls = []

        async def brain():
            calls.append(1)
            return {}, {}
        with pytest.raises(gates_memory.SharedMemoryContractMissing, match='current shared Tank personal-memory contract'):
            await gates_memory.run(legacy.MemoryClient('http://hermes', AGENT_KEY, 'tisan', http),
                                   TENANT, A, 'tisan.plan', {'b': 1}, brain)
        from hermes.records import schema_for
        async with pool.acquire() as conn:
            assert await conn.fetchval(f'SELECT count(*) FROM "{schema_for("tisan")}".memory_records') == 0
        assert calls == []
    run(hermes, flow)
