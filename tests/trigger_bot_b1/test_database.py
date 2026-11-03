"""Disposable-Postgres proof. Tenant boundaries are enforced by SQL and native RLS."""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import command
import pytest
import pytest_asyncio
import trigger_bot_api as api
from starlette.requests import Request
from trigger_bot import Bot
from trigger_bot_contract import SourceAdd
from trigger_bot_shared import PgRateLimits, hash_key
from trigger_bot_sources import Sources

A, B = UUID(int=11), UUID(int=12)
ROOT = Path(__file__).resolve().parents[2]
DDL = (ROOT / 'tank/schema.sql').read_text()
B1 = DDL[DDL.index('-- Trigger B1:'):]


@pytest_asyncio.fixture
async def database():
    url = os.environ.get('POOL_SCHEMA_DATABASE_URL')
    if not url:
        pytest.skip('Requires isolated test Postgres; never production')
    admin = await asyncpg.connect(url)
    name = 'bot_b1_' + uuid4().hex[:16]
    await admin.execute(f'CREATE DATABASE {name}')
    parsed = urlsplit(url)
    dsn = urlunsplit((parsed.scheme, parsed.netloc, '/' + name, parsed.query, ''))
    pool = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    try:
        await pool.execute(DDL)
        yield pool
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE {name} WITH (FORCE)')
        await admin.close()


class Index:
    def __init__(self):
        self.points = []
        self.put = AsyncMock()

    async def query(self, *args):
        return self.points


async def source(pool, tenant, text, index):
    service = Sources(pool, 'us-east', index)
    identity = await service.add(tenant, uuid4(), 'document', 'Owned attachment', content=text)
    await service.refresh(tenant, identity)
    return await pool.fetchrow('SELECT * FROM tank.trigger_bot_passages WHERE tenant_id=$1 AND source_id=$2 LIMIT 1', tenant, identity)


@pytest.mark.asyncio
async def test_hybrid_index_rechecks_tenant_staleness_and_source_removal(database):
    index = Index()
    own = await source(database, A, 'Delivery takes 3 days', index)
    foreign = await source(database, B, 'Delivery takes 90 days', index)
    index.points = [(foreign['id'], 1.0)]  # A broken/unfiltered vector store cannot leak B.
    sources = Sources(database, 'us-east', index)
    rows = await sources.search(A, 'Delivery days')
    assert rows and all(p.tenant_id == A and '90' not in p.text for p in rows)
    await database.execute("UPDATE tank.trigger_bot_sources SET status='removed' WHERE tenant_id=$1 AND id=$2", A, own['source_id'])
    assert await sources.search(A, 'Delivery days') == []
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_passages WHERE tenant_id=$1', B) == 1


@pytest.mark.asyncio
async def test_native_rls_rollout_is_conditional_idempotent_and_forced(database):
    assert not await database.fetchval("SELECT relrowsecurity FROM pg_class WHERE oid='tank.trigger_bot_sources'::regclass")
    await database.execute('ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY')
    await database.execute(B1)
    await database.execute(B1)
    counts = await database.fetchrow("""SELECT count(*) AS total,bool_and(relrowsecurity AND relforcerowsecurity) AS forced
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='tank' AND relkind='r' AND relname LIKE 'trigger_bot_%'""")
    assert counts['total'] == 9 and counts['forced']
    index = Index()
    await source(database, A, 'Delivery takes 3 days', index)
    await source(database, B, 'Delivery takes 90 days', index)
    role = 'bot_b1_role_' + uuid4().hex[:12]
    async with database.acquire() as conn:
        await conn.execute(f'CREATE ROLE {role} NOSUPERUSER NOBYPASSRLS')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA tank TO {role}')
            await conn.execute(f'GRANT SELECT ON ALL TABLES IN SCHEMA tank TO {role}')
            await conn.execute(f'SET ROLE {role}')
            await conn.execute("SELECT set_config('app.tenant_id',$1,false)", str(A))
            rows = await conn.fetch('SELECT tenant_id,text FROM tank.trigger_bot_passages')
            assert rows and all(r['tenant_id'] == A and '90' not in r['text'] for r in rows)
        finally:
            await conn.execute('RESET ROLE')
            await conn.execute(f'DROP OWNED BY {role}')
            await conn.execute(f'DROP ROLE {role}')


@pytest.mark.asyncio
async def test_real_pg_limits_rollback_rejected_counts_and_do_not_store_raw_address(database):
    limits = PgRateLimits(database)
    for _ in range(10):
        assert not (await limits.consume(str(A), '192.0.2.7', '/v1/rig/ask')).retry_after
    assert (await limits.consume(str(A), '192.0.2.7', '/v1/rig/ask')).retry_after
    assert not (await limits.consume(str(B), '192.0.2.7', '/v1/rig/ask')).retry_after
    count = await database.fetchval("SELECT hits FROM tank.trigger_bot_limits WHERE tenant_id=$1 AND route='browse'", A)
    assert count == 10
    rows = await database.fetch('SELECT * FROM tank.trigger_bot_limits')
    assert '192.0.2.7' not in repr(rows)


@pytest.mark.asyncio
async def test_document_preview_binds_actual_owned_attachment_not_model_text(database, monkeypatch):
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'founder')
    actor = command.Actor(A, 'founder', True)
    bot = Bot(SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east'))
    bot.sources._index = Index()
    action = command.PlannedAction(tool='trigger.bot.source.add', arguments=SourceAdd(
        kind='document', title='Policy', attachment_name='policy.txt').model_dump(mode='json', exclude_none=True))
    text = 'Actual owned attachment. ' * 3000  # Over the Command action envelope, stored as a draft reference.
    async with database.acquire() as conn:
        prepared = await api.prepare(action, actor, {'messages': [
            {'role': 'user', 'attachments': [{'name': 'policy.txt', 'text': text}]}]}, conn=conn)
    assert len(json.dumps(prepared.arguments)) < 32000
    monkeypatch.setattr(api, 'make_bot', lambda: bot)
    result = await api.execute('source.add', SourceAdd.model_validate(prepared.arguments), actor, uuid4())
    assert result['status'] == 'ready'
    row = await database.fetchrow('SELECT content,status FROM tank.trigger_bot_sources WHERE tenant_id=$1 AND id=$2', A, UUID(result['source_id']))
    assert row['content'] == text and row['status'] == 'ready'
    index = bot.sources._index
    assert index.put.await_count > 1


@pytest.mark.asyncio
async def test_public_origin_key_is_hash_checked_scoped_and_region_bound(database, monkeypatch):
    raw = 'rk_pub_' + 'a' * 48
    await database.execute('''INSERT INTO tank.trigger_bot_embed_keys(tenant_id,key_hash,region,origins)
        VALUES($1,$2,'us-east',$3::jsonb)''', A, hash_key(raw), json.dumps(['https://store.invalid']))
    monkeypatch.setattr(api, 'runtime', lambda: SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east'))
    def request(origin, key):
        return Request({'type': 'http', 'method': 'POST', 'path': '/v1/bot/messages', 'client': ('192.0.2.10', 123),
                        'headers': [(b'origin', origin.encode()), (b'x-bot-key', key.encode())]})
    key = 'tb1.us-east.' + A.hex + '.' + raw
    assert (await api.authenticate(request('https://store.invalid', key)))[0] == A
    for origin, value in [('https://other.invalid', key), ('https://store.invalid', key.replace(A.hex, B.hex)),
                          ('https://store.invalid', key.replace('us-east', 'za'))]:
        with pytest.raises(api.HTTPException) as denied:
            await api.authenticate(request(origin, value))
        assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_startup_refuses_bypass_tenant_role_before_schema_and_bot_task(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', os.environ['POOL_SCHEMA_DATABASE_URL'])
    monkeypatch.setenv('LITELLM_MASTER_KEY', 'offline-test-placeholder')
    monkeypatch.setenv('TANK_API_KEY', 'offline-test-placeholder')
    import main
    class Connection:
        async def fetchval(self, sql):
            return True
        async def fetchrow(self, sql):
            return {'rolsuper': True, 'rolbypassrls': True}
    class Acquire:
        async def __aenter__(self):
            return Connection()
        async def __aexit__(self, *args):
            return False
    pool = SimpleNamespace(acquire=lambda: Acquire())
    monkeypatch.setattr(main.asyncpg, 'create_pool', AsyncMock(return_value=pool))
    monkeypatch.setattr(main, '_pool', None)
    monkeypatch.setattr(main, '_admin_pool', None)
    monkeypatch.setattr(main, '_bot_task', None)
    monkeypatch.delenv('TANK_ADMIN_DATABASE_URL', raising=False)
    with pytest.raises(RuntimeError, match='RLS requires'):
        await main._startup()
    assert main._bot_task is None


@pytest.mark.asyncio
async def test_bot_policy_reuses_writing_route_and_faq_records_zero_cost(database, monkeypatch):
    import sys
    writing = dict(await database.fetchrow("SELECT * FROM tank.policy WHERE tenant_id IS NULL AND task_type='trigger.write'"))
    answer = dict(await database.fetchrow("SELECT * FROM tank.policy WHERE tenant_id IS NULL AND task_type='trigger.bot.answer'"))
    for column in ('rung', 'model', 'priority', 'max_tokens_out'):
        assert answer[column] == writing[column]
    assert answer['cache_scope'] == 'none'
    runtime = SimpleNamespace(pool=lambda: database, box_region=lambda: 'us-east')
    monkeypatch.setitem(sys.modules, 'main', runtime)
    bot = Bot(runtime)
    bot.sources = Sources(database, 'us-east', Index())
    bot.voice = AsyncMock(side_effect=AssertionError('FAQ must not fetch a voice'))
    bot.route = AsyncMock(side_effect=AssertionError('FAQ must not call a model'))
    await database.execute('INSERT INTO tank.trigger_bot_config(tenant_id,enabled) VALUES($1,true)', A)
    question = 'How long does delivery take?'
    for answer_text in ('Delivery takes 3 days.', 'Delivery takes 5 days.'):
        identity = await bot.sources.add(A, uuid4(), 'faq', question,
                                         content=json.dumps({'question': question, 'answer': answer_text}))
        await bot.sources.refresh(A, identity)
    result = await bot.ask(A, question)
    assert result['answer'] == 'Delivery takes 5 days.'
    assert result['outcome'] == 'faq'
    bot.route.assert_not_called()
    receipt = await database.fetchrow('SELECT cost_usd,tokens_in,tokens_out,model FROM tank.ledger WHERE tenant_id=$1 AND id=$2', A, UUID(result['ledger_id']))
    assert receipt['cost_usd'] == 0 and receipt['tokens_in'] == receipt['tokens_out'] == 0
    assert receipt['model'] == 'code'
    saved = await database.fetchrow('SELECT retrieved,cited FROM tank.trigger_bot_messages WHERE tenant_id=$1 AND id=$2', A, UUID(result['message_id']))
    assert saved['cited'] and set(saved['cited']) <= set(saved['retrieved'])
