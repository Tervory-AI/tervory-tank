"""ML5 offline read/Confirm contracts; placeholder data, no outside/model calls."""
import json
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
import command
import market_lab_ml3 as tank
from chassis.tank import TankClient
from core import ml3 as room, patterns
from core.predictions import gate, metadata
from core.pure import make_prediction
from test_market_lab_ml3 import database as database, proposal

OWNER = '00000000-0000-0000-0000-000000000031'
OTHER = '00000000-0000-0000-0000-000000000032'
PLATFORM = '00000000-0000-0000-0000-000000000001'
NOW = datetime(2026, 11, 3, tzinfo=UTC)
CONFIG = {'id': 'placeholder_pair', 'source': 'placeholder_source',
          'ref': 'placeholder_ref', 'downstream_source': 'placeholder_downstream'}
STATS = {'lag_min': 7, 'lag_max': 14, 'lag_median': 10, 'episode_count': 3,
         'hits': 2, 'hit_rate': 2 / 3}


def original(age=90):
    made = NOW - timedelta(days=age)
    row = make_prediction(tenant_id=OWNER, statement='placeholder prediction',
                          metric_series_id='placeholder_series', comparator='gte', target=2,
                          made_at=made, resolve_by=made + timedelta(days=7), rationale='placeholder')
    row = metadata({**row, 'confidence': .5, 'kind': 'placeholder_kind', 'feed': 'placeholder_feed'})
    resolved = {**row, 'id': str(uuid4()), 'outcome': 'hit', 'resolved_at': row['resolve_by'],
                'sources': [{'resolves': row['id']}]}
    return row, resolved


def memory_row(owner, tier, **extra):
    return {'id': str(uuid4()), 'tenant_id': owner, 'tier': tier,
            'claim': json.dumps(patterns.claim(CONFIG, STATS)), 'evidence': [], **extra}


@pytest.fixture
def room_app(monkeypatch):
    own = memory_row(OWNER, 'client')
    published = memory_row(PLATFORM, 'platform')
    foreign = memory_row(OTHER, 'client')
    wrong_pair = memory_row(PLATFORM, 'platform', claim=json.dumps(
        {**patterns.claim(CONFIG, STATS), 'pair_id': 'placeholder_other_pair'}))

    class Memory:
        async def records(self, tenant, *, tier):
            # Deliberately return foreign/wrong-pair records to exercise ML4's filter.
            return [own, foreign] if tier == 'client' else [published, wrong_pair, own]

    async def predictions(tenant):
        # Deliberately include foreign predictions too; gate must still scope them.
        rows = list(original())
        return rows + [{**r, 'tenant_id': OTHER, 'id': str(uuid4())} for r in rows]

    @asynccontextmanager
    async def context():
        yield SimpleNamespace(memory=Memory(), predictions_for=predictions)

    import core.jobs
    monkeypatch.setattr(core.jobs, 'load_engine', lambda _: SimpleNamespace(warning_plan=lambda: {'pairs': [CONFIG]}))
    app = FastAPI()
    app.include_router(room.build_router(key_ok=lambda key: key == 'placeholder-room',
                                        ledger_context=context, engine='placeholder_engine'))
    return app, own, published, foreign


@pytest.fixture(autouse=True)
def no_model(monkeypatch):
    failure = AsyncMock(side_effect=AssertionError('placeholder: no model call permitted'))
    monkeypatch.setattr(TankClient, 'route', failure)
    yield
    failure.assert_not_called()


@pytest.mark.asyncio
async def test_room_patterns_private_and_published_only_for_configured_pairs(room_app):
    app, own, published, foreign = room_app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
        assert (await client.post('/market/ml3/patterns', json={'tenant_id': OWNER})).status_code == 401
        for tenant, private in ((OWNER, own), (OTHER, foreign)):
            response = await client.post('/market/ml3/patterns', json={'tenant_id': tenant},
                                         headers={'x-tank-key': 'placeholder-room'})
            assert response.status_code == 200
            body = response.json()
            assert [r['id'] for r in body['patterns']] == [private['id']]
            assert [r['id'] for r in body['published']] == [published['id']]
            assert (foreign if tenant == OWNER else own)['id'] not in response.text


@pytest.mark.parametrize('delta,opened', [(timedelta(microseconds=-1), False), (timedelta(), True), (timedelta(days=1), True)])
def test_gate_opening_date_matches_exact_ninety_day_boundary(delta, opened):
    row, resolved = original()
    rows = [row, resolved, resolved]
    cohort = gate(rows, OWNER, now=NOW + delta)['cohorts'][0]
    assert cohort['open'] is opened
    assert cohort['opens_at'] == NOW.isoformat()
    assert cohort['resolved_count'] == 1
    assert gate(rows, OTHER, now=NOW)['cohorts'] == []
    unresolved = gate([row], OWNER, now=NOW)['cohorts'][0]
    assert unresolved['opens_at'] is None and unresolved['resolved_count'] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['patterns', 'gate'])
async def test_confirmed_read_receipt_pagination_and_exact_command_without_planner(database, room_app, monkeypatch, operation):
    db = database
    app, own, published, _ = room_app
    requests = []

    async def corridor(name, tenant):
        requests.append((name, str(tenant)))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
            response = await client.post('/market/ml3/' + name, json={'tenant_id': str(tenant)},
                                         headers={'x-tank-key': 'placeholder-room'})
            assert response.status_code == 200
            return response.json()

    monkeypatch.setattr(tank, 'room', corridor)
    # The fixture's main runtime has no Message, RouteRequest or run_route.
    # Any fallback to model planning raises before it can make a request.
    answer = await command.route_turn(db.actor, [{'role': 'user', 'content': 'market_lab.' + operation}])
    action = json.loads(answer.content)['actions'][0]
    assert action == {'tool': 'market_lab.' + operation, 'arguments': {'limit': 20, 'page': 0}}
    _, card = await proposal(db, action['tool'], action['arguments'])
    assert requests == []  # Read actions still require the existing Confirm card.
    result = await db.client.post('/v1/command/cards/' + card, json={'action': 'confirm'})
    assert result.status_code == 200
    body = result.json()['result']
    assert requests == [(operation, OWNER)]
    assert body['cost_usd'] == 0
    receipt = await db.pool.fetchrow('SELECT tenant_id,model,rung,cost_usd FROM tank.ledger WHERE id=$1', UUID(body['ledger_id']))
    assert receipt['tenant_id'] == UUID(OWNER) and receipt['model'] == 'code'
    assert receipt['rung'] == 3 and receipt['cost_usd'] == 0
    adapter = command.ADAPTERS[action['tool']]
    assert not adapter.paid and adapter.kind == 'other'
    if operation == 'patterns':
        assert body['total'] == 2
        assert [r['status'] for r in body['records']] == ['client', 'platform']
        assert all(r['name'] == CONFIG['id'] and r['count'] == 3 and r['total'] == 2 for r in body['records'])
    else:
        assert body['total'] == 1
        assert body['records'][0]['summary'] == NOW.isoformat()
        assert body['records'][0]['count'] == 1
    paged = await db.client.get('/v1/market-lab/reads/' + operation + '?limit=1&page=1')
    assert paged.status_code == 200 and paged.json()['total'] == body['total']
    assert len(paged.json()['records']) == (1 if operation == 'patterns' else 0)
