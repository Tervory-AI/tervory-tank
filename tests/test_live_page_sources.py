"""Actual room read routes, with offline storage doubles. No network, SQL server, or models."""
from __future__ import annotations

import importlib.util
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = UUID('00000000-0000-0000-0000-000000000001')
MATCH_ID = UUID('c634c3df-a3e3-4d25-86ea-0286d63ba4c9')


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return self.rows

    @asynccontextmanager
    async def acquire(self):
        yield self


def match_row(**updates):
    # Offline match, never persisted or served by a live process.
    return {
        'id': MATCH_ID, 'problem_id': 'offline-civil-appeal', 'title': 'Published civil appeal',
        'body': json.dumps({'title': 'Published civil appeal', 'region': 'us-east'}),
        'region': 'us-east', 'mode': 'student_student', 'published': True,
        'fairness': json.dumps({'reading': 'split'}),
        'runs': json.dumps([{'transcript': [], 'ruling': {'order': 'appeal_dismissed'}}]),
        **updates,
    }


@pytest.mark.asyncio
async def test_moot_published_route_scopes_reads_and_excludes_offline_content(monkeypatch):
    from agents.zenas import app as room

    conn = Connection([
        match_row(), match_row(published=False), match_row(title='Fixture Landlord v Tenant [TEST]'),
        match_row(body='{}'), match_row(body=json.dumps({'fixture': True})),
    ])
    monkeypatch.setattr(room.app.state, 'pool', conn, raising=False)
    monkeypatch.setattr(room, '_box_region', lambda: 'us-east')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://test') as client:
        result = await client.get('/moot/published', params={'home_region': 'us-east', 'match_id': str(MATCH_ID)})
    assert result.status_code == 200
    assert [m['matchId'] for m in result.json()['matches']] == [str(MATCH_ID)]
    assert not any(word in result.text for word in ('Fixture', '[TEST]', '00000000-0000-0000-0000'))
    sql, args = conn.calls[0]
    assert args == (PLATFORM, 'us-east', MATCH_ID)
    assert 'm.tenant_id = $1' in sql and 'm.region = $2' in sql and 'm.published = true' in sql
    assert 'p.tenant_id = m.tenant_id' in sql and 'p.region = m.region' in sql
    assert '$3::uuid IS NULL OR m.id = $3' in sql


@pytest.mark.asyncio
async def test_moot_empty_missing_and_wrong_region_never_use_fixtures(monkeypatch):
    from agents.zenas import app as room

    conn = Connection([])
    monkeypatch.setattr(room.app.state, 'pool', conn, raising=False)
    monkeypatch.setattr(room, '_box_region', lambda: 'us-east')
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://test') as client:
        result = await client.get('/moot/published?home_region=us-east')
        assert result.json() == {'matches': []}
        assert (await client.get('/moot/published?home_region=za')).status_code == 403
        assert len(conn.calls) == 1
        monkeypatch.setattr(room, '_box_region', lambda: 'za')
        assert (await client.get('/moot/published?home_region=us-east')).status_code == 403
        assert len(conn.calls) == 1
        monkeypatch.setattr(room, '_box_region', lambda: 'us-east')
        monkeypatch.setattr(room.app.state, 'pool', None)
        assert (await client.get('/moot/published?home_region=us-east')).status_code == 503


@pytest.mark.asyncio
async def test_market_quarantine_route_uses_existing_catalogue_name_and_state(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'agents' / '_chassis'))
    monkeypatch.syspath_prepend(str(ROOT / 'agents' / 'market_lab'))
    # Other room tests share a top-level core package. Load this route in its own test command.
    spec = importlib.util.spec_from_file_location('market_live_page_sources', ROOT / 'agents/market_lab/app.py')
    room = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(room)
    conn = Connection([{
        'id': 'offline-batch', 'series_id': f'{PLATFORM}:check_counts:total:AL',
        'source': 'check_counts', 'ref': 'total:AL', 'engine': 'ffl', 'status': 'held',
    }])

    @asynccontextmanager
    async def ledger():
        yield SimpleNamespace(conn=conn)

    monkeypatch.setattr(room, '_ledger', ledger)
    monkeypatch.setattr(room, '_room_key_ok', lambda _: True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=room.app), base_url='http://test') as client:
        result = await client.get('/quarantine')
        assert result.status_code == 200
        assert '00000000-0000-0000-0000' not in result.text
        assert result.json()['batches'][0]['series_name'] == 'Monthly background-check counts by state and type · Alabama'
        sql, args = conn.calls[0]
        assert args == (PLATFORM,)
        assert 's.tenant_id = b.tenant_id' in sql and 'b.tenant_id = $1' in sql
        conn.rows[0]['source'] = 'no-such-source'
        assert (await client.get('/quarantine')).status_code == 503
