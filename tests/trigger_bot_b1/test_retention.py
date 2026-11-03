"""Founder-approved retention on isolated PostgreSQL; no external calls/content receipts."""
import asyncio
import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_database import A, B
from test_database import database as database  # noqa: PLC0414 -- pytest fixture re-export
from trigger_bot import Bot, retention_due


def bot(database, monkeypatch):
    runtime = SimpleNamespace(pool=lambda: database, _admin_pool=None, box_region=lambda: 'us-east')
    monkeypatch.setitem(sys.modules, 'main', runtime)
    return Bot(runtime)


async def conversation(pool, tenant, days=-1):
    ident = uuid4()
    stamp = await pool.fetchval("SELECT now()-interval '12 months'+$1::int*interval '1 day'", days)
    await pool.execute('''INSERT INTO tank.trigger_bot_conversations(tenant_id,id,visitor_id,created_at)
        VALUES($1,$2,$3,$4)''', tenant, ident, uuid4(), stamp)
    await pool.execute('''INSERT INTO tank.trigger_bot_messages(tenant_id,id,conversation_id,question,outcome,created_at)
        VALUES($1,$2,$3,'placeholder private content','faq',$4)''', tenant, uuid4(), ident, stamp)
    ledger = uuid4()
    await pool.execute('''UPDATE tank.trigger_bot_messages SET ledger_id=$3
        WHERE tenant_id=$1 AND conversation_id=$2''', tenant, ident, ledger)
    await pool.execute('''INSERT INTO tank.transcripts(tenant_id,ledger_id,task_type,messages,content)
        VALUES($1,$2,'trigger.bot.answer','[]','placeholder masked question')''', tenant, ledger)
    return ident


@pytest.mark.asyncio
async def test_calendar_month_boundary_last_message_and_tenant_isolation(database, monkeypatch):
    service = bot(database, monkeypatch)
    over = await conversation(database, A, -1)
    under = await conversation(database, A, 1)
    foreign = await conversation(database, B, -1)
    active = await conversation(database, A, -10)
    await database.execute('''INSERT INTO tank.trigger_bot_messages(tenant_id,id,conversation_id,question,outcome)
        VALUES($1,$2,$3,'placeholder recent message','faq')''', A, uuid4(), active)
    counts = await service.retain_conversations(A)
    assert counts == {'conversations': 1, 'messages': 1, 'transcripts': 1, 'drafts': 0, 'confirmed_drafts_kept': 0, 'complete': True}
    remaining = await database.fetch('SELECT tenant_id,id FROM tank.trigger_bot_conversations')
    assert {(r['tenant_id'], r['id']) for r in remaining} == {(A, under), (A, active), (B, foreign)}
    assert over not in {r['id'] for r in remaining}
    assert await database.fetchval('SELECT count(*) FROM tank.transcripts WHERE tenant_id=$1', A) == 2
    assert await database.fetchval('SELECT count(*) FROM tank.transcripts WHERE tenant_id=$1', B) == 1
    assert not await database.fetchval('''SELECT 1 FROM tank.transcripts t
        WHERE t.tenant_id=$1 AND NOT EXISTS (SELECT 1 FROM tank.trigger_bot_messages m
          WHERE m.tenant_id=$1 AND m.ledger_id=t.ledger_id)''', A)
    receipt = await database.fetchrow('''SELECT l.*,r.receipt FROM tank.ledger l
        JOIN tank.agent_receipts r ON r.ledger_id=l.id AND r.tenant_id=l.tenant_id
        WHERE l.tenant_id=$1 AND l.task_type='trigger.bot.retention' ''', A)
    assert receipt['cost_usd'] == receipt['tokens_in'] == receipt['tokens_out'] == 0
    assert receipt['model'] == 'code' and receipt['rung'] == 3
    assert json.loads(receipt['receipt']) == counts
    assert 'placeholder' not in receipt['receipt'] and str(over) not in receipt['receipt']
    assert not await database.fetchval("SELECT 1 FROM tank.ledger WHERE tenant_id=$1 AND task_type='trigger.bot.retention'", B)


@pytest.mark.asyncio
async def test_confirmed_lead_and_quote_survive_unconfirmed_drafts_are_deleted(database, monkeypatch):
    service = bot(database, monkeypatch)
    old = await conversation(database, A)
    foreign = await conversation(database, B)
    kept = []
    for tenant, conv in ((A, old), (B, foreign)):
        for kind, state in (('lead','confirmed'), ('quote','confirmed'), ('lead','draft'), ('quote','draft'), ('faq','draft')):
            ident = uuid4()
            await database.execute('''INSERT INTO tank.trigger_bot_drafts(tenant_id,id,conversation_id,kind,state,data,result)
                VALUES($1,$2,$3,$4,$5,'{"placeholder":"private draft"}','{"placeholder":"confirmed destination"}')''', tenant, ident, conv, kind, state)
            if tenant == A and state == 'confirmed':
                kept.append(ident)
    counts = await service.retain_conversations(A)
    assert counts['drafts'] == 3 and counts['confirmed_drafts_kept'] == 2
    rows = await database.fetch('SELECT * FROM tank.trigger_bot_drafts WHERE tenant_id=$1', A)
    assert {r['id'] for r in rows} == set(kept)
    assert all(r['conversation_id'] is None and r['state'] == 'confirmed' and r['result'] for r in rows)
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_drafts WHERE tenant_id=$1', B) == 5


@pytest.mark.asyncio
async def test_batches_finish_then_wait_daily_even_after_restart(database, monkeypatch):
    service = bot(database, monkeypatch)
    for _ in range(5):
        await conversation(database, A)
    results = [await service.retain_conversations(A, batch_size=2) for _ in range(3)]
    assert [r['conversations'] for r in results] == [2, 2, 1]
    assert [r['complete'] for r in results] == [False, False, True]
    assert await Bot(service.rt).retain_conversations(A) is None
    await database.execute("UPDATE tank.ledger SET ts=now()-interval '25 hours' WHERE tenant_id=$1 AND task_type='trigger.bot.retention'", A)
    assert (await service.retain_conversations(A))['conversations'] == 0
    assert await database.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND task_type='trigger.bot.retention'", A) == 4


@pytest.mark.asyncio
async def test_multiple_maintenance_instances_do_not_delete_or_receipt_twice(database, monkeypatch):
    service = bot(database, monkeypatch)
    await conversation(database, A)
    results = await asyncio.gather(service.retain_conversations(A), Bot(service.rt).retain_conversations(A))
    assert sum(r['conversations'] for r in results if r is not None) == 1
    assert await database.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND task_type='trigger.bot.retention'", A) == 1


@pytest.mark.asyncio
async def test_counts_receipt_failure_rolls_back_deletion(database, monkeypatch):
    service = bot(database, monkeypatch)
    ident = await conversation(database, A)
    monkeypatch.setattr('trigger_routes.code_receipt', AsyncMock(side_effect=RuntimeError('placeholder receipt failure')))
    with pytest.raises(RuntimeError, match='placeholder receipt failure'):
        await service.retain_conversations(A)
    assert await database.fetchval('SELECT 1 FROM tank.trigger_bot_messages WHERE tenant_id=$1 AND conversation_id=$2', A, ident)
    assert await database.fetchval('SELECT 1 FROM tank.trigger_bot_conversations WHERE tenant_id=$1 AND id=$2', A, ident)
    assert await database.fetchval('SELECT count(*) FROM tank.transcripts WHERE tenant_id=$1', A) == 1


@pytest.mark.asyncio
async def test_concurrent_message_writer_is_skipped_and_fresh_message_retains_conversation(database, monkeypatch):
    service = bot(database, monkeypatch)
    ident = await conversation(database, A)
    async with database.acquire() as conn, conn.transaction():
        await conn.fetchval('SELECT id FROM tank.trigger_bot_conversations WHERE tenant_id=$1 AND id=$2 FOR UPDATE', A, ident)
        result = await service.retain_conversations(A)
        assert result['conversations'] == 0 and not result['complete']
        await conn.execute('''INSERT INTO tank.trigger_bot_messages(tenant_id,id,conversation_id,question,outcome)
            VALUES($1,$2,$3,'placeholder concurrent message','faq')''', A, uuid4(), ident)
    result = await service.retain_conversations(A)
    assert result['complete'] and result['conversations'] == 0
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_messages WHERE tenant_id=$1 AND conversation_id=$2', A, ident) == 2


@pytest.mark.asyncio
async def test_existing_loop_retention_scopes_each_tenant(database, monkeypatch):
    service = bot(database, monkeypatch)
    await conversation(database, A)
    await conversation(database, B)
    await retention_due(service.rt)
    assert await database.fetchval('SELECT count(*) FROM tank.trigger_bot_conversations') == 0
    assert await database.fetchval("SELECT count(*) FROM tank.ledger WHERE task_type='trigger.bot.retention'") == 2
    await retention_due(service.rt)
    assert await database.fetchval("SELECT count(*) FROM tank.ledger WHERE task_type='trigger.bot.retention'") == 2
