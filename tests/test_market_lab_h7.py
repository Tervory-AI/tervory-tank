"""H7 real SQL/read route contracts with placeholder data and offline transports."""
import json
import sys
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'agents/market_lab'))
from core import ml3 as room
from core.document_read import extract
from core.documents import accept, forget
from core.ledger import PostgresLedger
from core.predictions import calibration, clock
from test_market_lab_ml3 import database as database, OWNER, OTHER
from test_market_lab_ml5 import original
import market_lab_ml3 as tank
import command

NOW = datetime(2026, 11, 4, tzinfo=UTC)


async def bridge(database, monkeypatch):
    @asynccontextmanager
    async def context():
        async with database.pool.acquire() as conn:
            yield PostgresLedger(conn)
    app = FastAPI()
    app.include_router(room.build_router(key_ok=lambda key: key == 'placeholder-room',
                                        ledger_context=context, engine='ffl'))
    async def corridor(operation, tenant, *, report_id=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://placeholder') as client:
            response = await client.post('/market/ml3/' + operation,
                headers={'x-tank-key': 'placeholder-room'},
                json={'tenant_id': str(tenant), **({'report_id': str(report_id)} if report_id else {})})
        if response.status_code != 200:
            from fastapi import HTTPException
            raise HTTPException(response.status_code)
        return response.json()
    monkeypatch.setattr(tank, 'room', corridor)


def report(ident=None):
    return {'id': str(ident or uuid4()), 'tenant_id': str(OWNER), 'made_at': NOW,
            'question': 'placeholder brief', 'answer': 'placeholder inventory claim', 'citations': []}


@pytest.mark.asyncio
async def test_detail_uses_existing_tenant_read_and_opens_exact_saved_passage(database, monkeypatch):
    file_id, foreign_file = uuid4(), uuid4()
    async with database.pool.acquire() as conn:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        for owner, ident in ((OWNER, file_id), (OTHER, foreign_file)):
            await accept(ledger, str(owner), str(ident), 'placeholder.csv', extract('placeholder.csv',
                b'date,value,unit,series\n2026-09-01,100,cartons,inventory\n'), region='us-east')
        row, resolved = original()
        row.update(tenant_id=str(OWNER), confidence=.75)
        await ledger.save_prediction(row)
        saved = report()
        saved['citations'] = [
            {'claim': 'placeholder inventory claim', 'prediction_id': row['id'],
             'url': f'https://app.tervory.com/market-lab/sources/{file_id}?row=0#passage-0'},
            {'claim': 'placeholder foreign source', 'url': f'/market-lab/sources/{foreign_file}?row=0#passage-0'},
            {'claim': 'placeholder nonexistent row', 'url': f'/market-lab/sources/{file_id}?row=999#passage-999'},
            {'claim': 'placeholder publisher', 'url': 'https://placeholder.example/source'}]
        await ledger.save_brief(saved, 'pending', None)
        # A detail can open an older brief even after it falls out of the last 12.
        for i in range(13):
            await ledger.save_brief({**report(), 'made_at': NOW + timedelta(days=i + 1)}, 'pending', None)
        assert await ledger.update_brief(str(OWNER), saved['id'], 'email', 'sending', expected='pending')
        assert not await ledger.update_brief(str(OWNER), saved['id'], 'email', 'sending', expected='pending')
        assert await ledger.update_brief(str(OWNER), saved['id'], 'email', 'sent')
    await bridge(database, monkeypatch)
    response = await database.client.get('/v1/market-lab/reads/briefs', params={'report_id': saved['id']})
    assert response.status_code == 200 and response.json()['cost_usd'] == 0
    detail = response.json()['records'][0]
    assert detail['report_id'] == saved['id'] and detail['signals'][0]['confidence'] == .75
    assert detail['sources'][0]['stored_href'] == f'/market-lab/sources/{file_id}?row=0#passage-0'
    assert [source['stored_href'] for source in detail['sources'][1:]] == [None, None, None]
    assert [event['status'] for event in detail['history'] if event.get('channel') == 'email'] == ['pending', 'sending', 'sent']
    receipt = await database.pool.fetchrow('SELECT tenant_id,model,cost_usd FROM tank.ledger WHERE id=$1', UUID(response.json()['ledger_id']))
    assert receipt['tenant_id'] == OWNER and receipt['model'] == 'code' and receipt['cost_usd'] == 0
    other = await database.client.get('/v1/market-lab/reads/briefs', params={'report_id': saved['id']},
                                      headers={'x-placeholder-tenant': str(OTHER)})
    assert other.status_code == 404
    assert (await database.client.get('/v1/market-lab/reads/briefs', params={'report_id': 'placeholder-invalid'})).status_code == 422
    async with database.pool.acquire() as conn:
        await forget(PostgresLedger(conn), str(OWNER), str(file_id))
    deleted = await database.client.get('/v1/market-lab/reads/briefs', params={'report_id': saved['id']})
    assert deleted.json()['records'][0]['sources'][0]['stored_href'] is None
    answer = await command.route_turn(database.actor, [{'role': 'user',
        'content': 'market_lab.briefs ' + json.dumps({'report_id': saved['id']})}])
    assert json.loads(answer.content)['actions'][0]['arguments']['report_id'] == saved['id']


@pytest.mark.asyncio
async def test_calibration_groups_and_curve_share_measured_code_data(database, monkeypatch):
    async with database.pool.acquire() as conn:
        ledger = PostgresLedger(conn)
        await ledger.apply_schema()
        for probability, outcome in ((.1, 'miss'), (.8, 'hit')):
            row, resolved = original()
            row.update(tenant_id=str(OWNER), confidence=probability)
            resolved.update(tenant_id=str(OWNER), outcome=outcome)
            await ledger.save_prediction(row)
            await ledger.save_prediction(resolved)
    await bridge(database, monkeypatch)
    summary = await database.client.get('/v1/market-lab/reads/calibration')
    curve = await database.client.get('/v1/market-lab/reads/calibration.curve')
    assert summary.status_code == curve.status_code == 200
    group = curve.json()['records'][0]
    assert group['mean_confidence'] == pytest.approx(.45)
    assert group['realised_rate'] == .5 and group['hits'] == group['misses'] == 1
    assert group['count'] == 2
    assert [(b['mean_confidence'], b['realised_rate'], b['count']) for b in group['bins']] == [(.1, 0, 1), (.8, 1, 1)]
    assert summary.json()['cost_usd'] == curve.json()['cost_usd'] == 0
    rows = []
    for horizon in (7, 30):
        row, resolved = original()
        row.update(confidence=.75, resolve_by=clock(row['made_at']) + timedelta(days=horizon), horizon_seconds=horizon * 86400)
        resolved.update(resolved_at=row['resolve_by'])
        rows.extend((row, resolved))
    groups = calibration(rows, rows[0]['tenant_id'])['curves']
    assert len(groups) == 2 and {g['horizon_seconds'] for g in groups} == {604800, 2592000}
    assert all(g['count'] == 1 and g['realised_rate'] == 1 for g in groups)
