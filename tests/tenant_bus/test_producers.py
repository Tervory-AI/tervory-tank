"""Completion hooks use saved facts, never private record/site/finding text."""
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import UUID

import pytest

from chassis import events
from event_bus import EVENTS, FACTS, Scope
from test_bus import A
from test_tiger import _load

ROOT = Path(__file__).resolve().parents[2]


def recorder(bus, monkeypatch):
    seen = []
    async def publish(tenant, event, reference, facts, **kwargs):
        FACTS[event].model_validate(facts)
        assert 'private-marker' not in json.dumps(facts)
        await bus.publish(Scope(UUID(tenant), EVENTS[event], 'us-east'), event, UUID(events.source_id(reference)), facts)
        seen.append((tenant, event, reference, facts))
        return True
    monkeypatch.setattr(events, 'publish', publish)
    return seen, publish


@pytest.mark.asyncio
async def test_base_emits_once_after_real_record_commit(database, bus, monkeypatch):
    sys.path.insert(0, str(ROOT / 'agents/base'))
    from test_b3_base_room import RAW, _scripted
    room = _load('bus_base_room', ROOT / 'agents/base/room.py')
    seen, publish = recorder(bus, monkeypatch)
    async def after_commit(tenant, event, reference, facts):
        async with database.acquire() as conn:
            row = await conn.fetchrow('SELECT status,confidence,updated_at FROM agent_base.records WHERE tenant_id=$1 AND id=$2',
                                      UUID(tenant), UUID(facts['record_id']))
            assert row['status'] == 'done' and row['confidence'] == facts['confidence']
            assert row['updated_at'].isoformat() == facts['observed_at']
        return await publish(tenant, event, reference, facts)
    monkeypatch.setattr(room, 'publish', after_commit)
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_base')
        await room.ensure_tables(conn)
        row = await room.insert_batch(conn, UUID(A), None, 'private-marker', [RAW[0]], '', False, None, 1, None)
        cfg = json.loads(await conn.fetchval('SELECT input FROM agent_base.tasks WHERE id=$1', row['id']))
    async def call(skill_id, payload):
        return _scripted(skill_id, payload)
    await room._run_batch(database, row['id'], cfg, call)
    assert len(seen) == 1 and seen[0][1] == 'base.record.enriched'
    await room._run_batch(database, row['id'], cfg, call)
    assert len(seen) == 1  # Already-finished records do not emit again on resume.


@pytest.mark.asyncio
async def test_marketlab_emits_once_per_saved_scored_signal(bus, monkeypatch):
    from test_market_lab import AREAS, NOW, MemoryLedger, perform_opportunities
    ledger = MemoryLedger()
    seen, publish = recorder(bus, monkeypatch)
    async def after_commit(tenant, event, ref, facts):
        assert any(row['id'] == facts['signal_id'] and row['tenant_id'] == tenant for row in ledger.opportunities)
        return await publish(tenant, event, ref, facts)
    monkeypatch.setattr(events, 'publish', after_commit)
    await perform_opportunities(tenant_id=A, engine='ffl', ledger=ledger, areas=AREAS[:1],
                                signals={'thin': {'no_website': True, 'size': 100}}, now=NOW)
    assert len(seen) == len(ledger.opportunities) == 1
    assert seen[0][1] == 'marketlab.signal.scored'


@pytest.mark.asyncio
async def test_zenas_nightly_new_version_only_platform_scope(bus, monkeypatch):
    from test_zenas_pool_corpus import MemoryStore, ON, _snaps, run_nightly
    from agents.zenas.pool.ingest import version_saved
    store = MemoryStore()
    seen, _ = recorder(bus, monkeypatch)
    for _ in range(2):
        await run_nightly(store, region='us-east', snapshots=_snaps(), on=ON, only=['govinfo-uscode'])
        assert version_saved.get() is None
    assert len(seen) == 1
    assert seen[0][0:2] == ('00000000-0000-0000-0000-000000000001', 'zenas.regulation.changed')
    assert len(seen[0][3]['document_id']) == 64


@pytest.mark.asyncio
async def test_radix_emits_once_after_finding_commit_without_text(database, bus, monkeypatch):
    sys.path.insert(0, str(ROOT / 'agents/radix'))
    from scanlib import orchestrate
    seen, publish = recorder(bus, monkeypatch)
    scan_id = UUID('33333333-3333-4333-8333-333333333333')
    findings = [{'tool': 'static', 'severity': 'high', 'file': 'private-marker', 'line': 1, 'fix': 'private-marker'}]
    monkeypatch.setattr(orchestrate, 'build_result', lambda ctx: {'findings': findings})
    async with database.acquire() as conn:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS agent_radix')
    closed = []
    async def connect():
        conn = await database.acquire()
        async def close():
            await database.release(conn)
            closed.append(True)
        return SimpleNamespace(execute=conn.execute, close=close)
    async def after_commit(tenant, event, ref, facts):
        assert closed
        async with database.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM agent_radix.findings WHERE tenant_id=$1 AND scan_id=$2',
                                       UUID(tenant), scan_id) == 1
        return await publish(tenant, event, ref, facts)
    monkeypatch.setattr(events, 'publish', after_commit)
    result = await orchestrate.scan_job(SimpleNamespace(tenant_id=A, job_id=scan_id, agent='radix'), connect=connect)
    assert result['findings'] == findings and len(seen) == 1
    assert seen[0][3] == {'scan_id': str(scan_id), 'ordinal': 0, 'severity': 'high'}


@pytest.mark.asyncio
async def test_tisan_emits_only_after_scaffold_success(bus, monkeypatch):
    app = _load('bus_tisan', ROOT / 'agents/tisan/app.py')
    seen, _ = recorder(bus, monkeypatch)
    result = {'ok': False, 'slug': 'private-marker'}
    async def execute(brief, tenant):
        assert tenant == A
        return result
    monkeypatch.setattr(app, '_scaffold_module', lambda: SimpleNamespace(execute=execute))
    ctx = SimpleNamespace(tenant_id=A, job_id='44444444-4444-4444-8444-444444444444', input={})
    assert await app.scaffold(ctx) is result
    assert seen == []
    result['ok'] = True
    assert await app.scaffold(ctx) is result
    assert len(seen) == 1 and seen[0][1] == 'tisan.build.ready'
    assert seen[0][3]['site_id'] == hashlib.sha256(b'private-marker').hexdigest()
