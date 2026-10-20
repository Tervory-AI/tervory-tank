"""Room intake rejects private/cross-region rows and survives missing endpoints."""
from datetime import date
from types import SimpleNamespace
import secrets

import httpx
import pytest
import training

from test_train1 import database as _database

database = _database


def example(**changes):
    return dict(skill_id='base.find_site', input={'name': 'Public fixture'}, expected={'url': 'example.test'},
                label_source='registry fixture', region='us-east', public=True) | changes


@pytest.mark.parametrize('changes', [{'public': False}, {'client_matter': True}, {'tenant_id': 'client'}, {'public': 'true'}, {'region': 'za'},
                                     {'skill_id': 'zenas.retrieve'}, {'label_source': ''}])
def test_reject_unsafe_candidates(changes):
    assert not training.valid_auto_candidate(example(**changes), 'base', 'us-east')


def test_region_is_exact():
    assert training.valid_auto_candidate(example(), 'base', 'us-east')
    assert training.valid_auto_candidate(example(region='za'), 'base', 'za')
    assert not training.valid_auto_candidate(example(), 'base', 'za')


@pytest.mark.asyncio
async def test_missing_endpoint_and_room_auth(monkeypatch):
    key = secrets.token_urlsafe(20)
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    monkeypatch.setenv('TANK_KEY_BASE', key)
    monkeypatch.setattr(training, 'runtime', lambda: SimpleNamespace(box_region=lambda: 'us-east'))
    real_client = httpx.AsyncClient
    def respond(request):
        assert request.headers['X-Tank-Key'] == key
        assert request.url.host == 'agent-base'
        return httpx.Response(404)
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(respond), **kw))
    await training.collect_room_gold(date(2026, 10, 20))


@pytest.mark.asyncio
async def test_cap_dedup_and_no_automatic_approval(database, monkeypatch):
    pool, _ = database
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    monkeypatch.setenv('TANK_KEY_BASE', secrets.token_urlsafe(20))
    monkeypatch.setenv('GOLD_AUTO_MAX', '2')
    rows = [example(input={'n': n}, label_source=f'citation {n}') for n in range(5)] + [example(region='za')]
    real_client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: real_client(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=rows)), **kw))
    for _ in range(2):
        await training.collect_room_gold(date(2026, 10, 20))
    async with pool.acquire() as conn:
        saved = await conn.fetch('SELECT * FROM tank.gold_examples')
        assert len(saved) == 2
        assert all(r['auto_label'] and r['public'] and r['status'] == 'candidate' and r['region'] == 'us-east' for r in saved)
        assert await conn.fetchval('SELECT count(*) FROM tank.training_pairs') == 0


def test_existing_room_skill_namespaces():
    assert training.valid_auto_candidate(example(skill_id='market.series_fetch'), 'market_lab', 'us-east')
    assert training.valid_auto_candidate(example(skill_id='scan.secrets'), 'radix', 'us-east')
    assert not training.valid_auto_candidate(example(skill_id='scan.secrets'), 'base', 'us-east')
