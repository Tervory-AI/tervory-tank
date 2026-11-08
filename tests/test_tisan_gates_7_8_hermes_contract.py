"""Gates 7+8 contract: Tisan against the fixed shared core's REAL Hermes app.

The app is vendor/tervory-tank/hermes/service.py create_app with its real
routes, auth (hermes.auth) and SQL Records (hermes.records) on a disposable
loopback Postgres. Only the embedding index/encoder are inert stand-ins,
because every Tisan write is index=False and every read is the SQL listing.
Keys are offline dummy fixture values; no real secret is read.
"""
from __future__ import annotations

import asyncio
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx
import pytest

from agents.tisan import gates_memory
from agents.tisan.gates_memory import GateMemory, REMEMBERS

ROOT = Path(__file__).resolve().parents[1]
TENANT, OTHER_TENANT = str(uuid.uuid4()), str(uuid.uuid4())
USER, OTHER_USER = 'founder-a', 'founder-b'
KEYS = {'TANK_KEY_TISAN': 'dummy-fixture-tisan', 'TANK_KEY_GHOST': 'dummy-fixture-ghost',
        'TANK_API_KEY': 'dummy-fixture-workspace'}



class InertIndex:
    def search(self, *a, **k):
        raise AssertionError('Tisan must not embed-search memory')

    upsert = delete = search


class InertEncoder:
    def validate(self, claim):
        raise AssertionError('Tisan writes must be index=False')

    embed = validate


@pytest.fixture
def hermes(monkeypatch):
    from hermes.records import Records
    from hermes.service import create_app
    shared = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    assert shared, 'scripts/run_tests.py provides the loopback Postgres'
    for name, value in KEYS.items():
        monkeypatch.setenv(name, value)
    name = 'tg78_' + uuid.uuid4().hex[:12]
    url = urlunsplit(urlsplit(shared)._replace(path='/' + name))
    loop = asyncio.new_event_loop()

    async def up():
        admin = await asyncpg.connect(shared)
        await admin.execute(f'CREATE DATABASE "{name}"')
        await admin.close()
        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
        records = Records(pool, InertIndex(), InertEncoder(), 'inert', ['tisan', 'ghost'])
        await records.setup()
        return pool, records

    pool, records = loop.run_until_complete(up())
    app = create_app(records=records)
    yield loop, app, pool

    async def down():
        await pool.close()
        admin = await asyncpg.connect(shared)
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()
    loop.run_until_complete(down())
    loop.close()


def client(app, key_field):
    """The product's own client (chassis MemoryClient) exactly as the room builds it."""
    from chassis.memory import MemoryClient
    http = httpx.AsyncClient(transport=httpx.ASGITransport(app=app))
    return MemoryClient(base_url='http://hermes:8000', api_key=os.environ[key_field], agent='tisan', http=http)


def test_adapter_write_recall_forget_on_real_hermes_with_own_agent_key(hermes):
    loop, app, pool = hermes
    mine = client(app, 'TANK_KEY_TISAN')

    async def flow():
        gate = GateMemory(mine, TENANT, USER)
        saved = await gate.remember_choice(gates_memory.SECTION, 'brand', {'fonts': ['Jost']})
        rows = await gate.view()
        assert [r['id'] for r in rows] == [saved['id']]
        row = rows[0]
        assert row['kind'] == 'tisan.section' and row['tenant_id'] == TENANT and row['agent'] == 'tisan'
        assert row['meta']['user_id'] == USER and row['meta']['value'] == {'fonts': ['Jost']}
        # Exact repeat recalled from real SQL records, no paid call.
        calls = []

        async def brain():
            calls.append(1)
            return {'plan': 'p'}, {**gates_memory.free_receipt(None, 'tank'), 'paid_calls': 1, 'cost_usd': 0.0025}
        first = await gates_memory.run(mine, TENANT, USER, 'tisan.plan', {'brief': 'x'}, brain)
        repeat = await gates_memory.run(mine, TENANT, USER, 'tisan.plan', {'brief': 'x'}, brain)
        assert calls == [1] and repeat['memory']['hit'] and repeat['receipt']['paid_calls'] == 0
        assert first['result'] == repeat['result'] == {'plan': 'p'}
        # Other user / other tenant see nothing and miss.
        assert await GateMemory(mine, TENANT, OTHER_USER).view() == []
        assert await GateMemory(mine, OTHER_TENANT, USER).view() == []
        assert await GateMemory(mine, TENANT, OTHER_USER).lookup('tisan.plan', {'brief': 'x'}) is None
        # Another agent's own key cannot see Tisan's collection.
        assert await GateMemory(client(app, 'TANK_KEY_GHOST'), TENANT, USER).view() == []
        # Forget really deletes in Hermes SQL.
        assert await gate.forget(saved['id']) == 1
        assert saved['id'] not in [r['id'] for r in await mine.records(TENANT, user_id=USER)]
        await gate.set_enabled(False)
        assert await gate.enabled() is False
        assert await gate.forget() >= 1 and [r['kind'] for r in await gate.view()] == ['tisan.memory_setting']
        async with pool.acquire() as conn:
            from hermes.records import schema_for
            stored = await conn.fetch(f'SELECT tenant_id::text, kind FROM "{schema_for("tisan")}".memory_records')
            other = await conn.fetchval(f'SELECT count(*) FROM "{schema_for("ghost")}".memory_records')
        assert other == 0
        assert {r['tenant_id'] for r in stored} == {TENANT}
        assert all(re.fullmatch(r'^[a-z][a-z0-9_.]{0,79}$', r['kind']) for r in stored)
    loop.run_until_complete(flow())


def test_shared_workspace_key_cannot_write_and_bad_kinds_are_refused(hermes):
    loop, app, _pool = hermes

    async def flow():
        shared = GateMemory(client(app, 'TANK_API_KEY'), TENANT, USER)
        with pytest.raises(RuntimeError, match='hermes answered (400|403)'):
            await shared.remember_choice(gates_memory.SECTION, 'brand', {'fonts': ['Jost']})
        with pytest.raises(RuntimeError, match='hermes answered 403'):
            await client(app, 'TANK_API_KEY').remember(TENANT, 't', 'tisan.brand', 's', index=False, tenant_wide=True)
        with pytest.raises(RuntimeError, match='hermes answered 422'):
            await client(app, 'TANK_KEY_TISAN').remember(TENANT, 't', 'Tisan-Brand', 's', index=False, user_id=USER)
    loop.run_until_complete(flow())
    assert all(re.fullmatch(r'^[a-z][a-z0-9_.]{0,79}$', kind) for kind in REMEMBERS)


def test_product_uses_own_agent_key_fields_and_never_tank_v1_memory():
    compose = (ROOT / 'agents/tisan/docker-compose.yml').read_text()
    assert compose.count('TANK_KEY: ${TANK_KEY_TISAN:-}') >= 2 and 'HERMES_URL: http://hermes:8000' in compose
    assert 'TANK_API_KEY' not in compose
    for path in (ROOT / 'agents/tisan').glob('*.py'):
        text = path.read_text()
        assert '/v1/memory' not in text, path
        assert 'TANK_API_KEY' not in text, path


def test_current_real_hermes_contract_write_recall_forget_keys_kinds_and_tenant(hermes):
    """Passes on the CURRENT pinned Tank: every contract point except user scope (that is group B above)."""
    loop, app, pool = hermes
    mine = client(app, 'TANK_KEY_TISAN')

    async def flow():
        saved = await mine.remember(TENANT, 'brand ink', 'tisan.brand', 'tisan:gates-7-8', index=False,
                                    meta={'subject': 'brand'}, tenant_wide=True)
        assert saved['kind'] == 'tisan.brand' and saved['tenant_id'] == TENANT and saved['agent'] == 'tisan'
        listed = await mine.records(TENANT)
        assert [r['id'] for r in listed] == [saved['id']] and listed[0]['meta']['subject'] == 'brand'
        assert await mine.records(OTHER_TENANT) == []                       # tenant scope
        assert await client(app, 'TANK_KEY_GHOST').records(TENANT) == []    # own agent collection only
        with pytest.raises(RuntimeError, match='hermes answered 403'):      # shared key cannot write
            await client(app, 'TANK_API_KEY').remember(TENANT, 't', 'tisan.brand', 's', index=False, tenant_wide=True)
        from chassis.memory import MemoryClient
        wrong = MemoryClient(base_url='http://hermes:8000', api_key='dummy-fixture-unknown', agent='tisan',
                             http=httpx.AsyncClient(transport=httpx.ASGITransport(app=app)))
        with pytest.raises(RuntimeError, match='hermes answered 401'):      # wrong key refused
            await wrong.remember(TENANT, 't', 'tisan.brand', 's', index=False, tenant_wide=True)
        with pytest.raises(RuntimeError, match='hermes answered 401'):
            await wrong.records(TENANT)
        with pytest.raises(RuntimeError, match='hermes answered 422'):      # bad kind refused
            await mine.remember(TENANT, 't', 'Tisan-Brand', 's', index=False, user_id=USER)
        await mine.forget(saved['id'], TENANT, user_id=USER)                                # forget
        assert await mine.records(TENANT) == []
    loop.run_until_complete(flow())
