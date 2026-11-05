"""Refresh, metric resolution and public-source failures use production job code."""
import importlib.util
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/market_lab'))
from core import jobs, pure
from core.document_read import extract
from core.documents import accept
from core.ledger import MemoryLedger
from feeds.live import BlockedSite


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', [0, 4])
async def test_refresh_recomputes_opportunities_only_for_new_pooled_data(monkeypatch, changed):
    spec = importlib.util.spec_from_file_location('finish_room_jobs', ROOT/'agents/market_lab/app.py')
    room = importlib.util.module_from_spec(spec);sys.modules[spec.name] = room;spec.loader.exec_module(room)
    connection = SimpleNamespace(execute=AsyncMock())
    @asynccontextmanager
    async def ledger(**kwargs): yield SimpleNamespace(conn=connection)
    monkeypatch.setattr(room, '_ledger', ledger)
    monkeypatch.setattr(room, 'perform_refresh', AsyncMock(return_value={'observations_stored':changed}))
    opportunities = AsyncMock(return_value={'ranked':[]})
    monkeypatch.setattr(room, 'perform_opportunities', opportunities)
    import core.warning_http
    monkeypatch.setattr(core.warning_http, 'refresh', AsyncMock(return_value={}))
    ctx = SimpleNamespace(tenant_id=str(uuid4()), input={'engine':'ffl'}, memory=SimpleNamespace())
    result = await room.refresh(ctx)
    assert opportunities.await_count == bool(changed)
    if changed: assert opportunities.call_args.kwargs['tenant_id'] == ctx.tenant_id
    assert ('opportunities' in result) == bool(changed)
    assert 'pg_advisory_unlock' in connection.execute.call_args.args[0]


@pytest.mark.asyncio
async def test_uploaded_response_metric_resolves_without_changing_original():
    owner, other = str(uuid4()), str(uuid4())
    ledger = MemoryLedger();made = datetime(2026,7,1,tzinfo=timezone.utc)
    prediction = pure.prediction_for_recommendation({'area':'north','segment':'retail','recommendation':'increase',
        'demand_idx':2,'supply_idx':1,'gap':2,'saturation':1,'reachability':1,'trend':{}}, tenant_id=owner, made_at=made)
    ledger.save_prediction(prediction)
    original = dict(ledger.predictions[0])
    raw = b'date,value,unit,series\n2026-10-01,6,percent,response:north:retail\n'
    for tenant in (owner,other):
        await accept(ledger, tenant, str(uuid4()), 'outcomes.csv', extract('outcomes.csv',raw), region='us-east')
    result = await jobs.perform_resolve(tenant_id=owner, ledger=ledger, now=made+timedelta(days=93))
    assert result['resolved'] == 1 and result['outcomes'][0]['outcome'] == 'hit'
    assert ledger.predictions[0] == original
    assert ledger.predictions[-1]['realised_value'] == 6
    assert ledger.predictions[-1]['realised_date'] == '2026-10-01'
    assert ledger.predictions[-1]['sources'][-1]['metric_series_id'] == ledger.series_for(owner)[0]['id']
    assert (await jobs.perform_resolve(tenant_id=owner,ledger=ledger,now=made+timedelta(days=94)))['resolved'] == 0
    assert len(ledger.predictions_for(other)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('unit,duplicate', [('cartons',False),('percent',True)])
async def test_unmeasurable_or_ambiguous_uploaded_metric_is_not_scored(unit,duplicate):
    tenant=str(uuid4());ledger=MemoryLedger();made=datetime(2026,7,1,tzinfo=timezone.utc)
    ledger.save_prediction(pure.make_prediction(tenant_id=tenant, statement='response', metric_series_id='response:north:retail',
        comparator='gt', target=5, resolve_by=made+timedelta(days=90),made_at=made,rationale='saved metric',sources=[]))
    for _ in range(2 if duplicate else 1):
        raw=f'date,value,unit,series\n2026-10-01,6,{unit},response:north:retail\n'.encode()
        await accept(ledger,tenant,str(uuid4()),'outcomes.csv',extract('outcomes.csv',raw),region='us-east')
    assert (await jobs.perform_resolve(tenant_id=tenant,ledger=ledger,now=made+timedelta(days=93)))['resolved'] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize('blocked', [False,True])
async def test_fred_failures_do_not_abort_other_sources_or_copy_restricted_points(monkeypatch, blocked):
    calls=[]
    async def read(ref, **kwargs):
        calls.append(ref)
        if blocked: raise BlockedSite('api.stlouisfed.org')
        if len(calls)==1: raise RuntimeError('upstream private diagnostic must not leave this function')
        if len(calls)==3: return {'observations':[]}
        return {'observations':[{'date':'2026-10-01','value':'4'}]}
    monkeypatch.setattr(jobs,'_live_fred',read)
    ledger=MemoryLedger()
    result=await jobs.perform_refresh(tenant_id=str(uuid4()),engine='ffl',ledger=ledger,
        fixtures=str(ROOT/'tests/fixtures/feeds'),live=True)
    assert len(result['fred']) == 4 and result['fred_stored'] == 0
    assert all(p['source']!='fred' for p in ledger.points)
    assert len(calls) == (1 if blocked else 4)
    assert [r['state'] for r in result['fred']] == (['off']*4 if blocked else ['off','on','off','on'])
    assert all('private diagnostic' not in r['note'] for r in result['fred'])


def test_listing_never_implicitly_uses_bundled_fixture_data(monkeypatch):
    monkeypatch.setattr(pure,'_repo_root',lambda:ROOT)
    with pytest.raises(RuntimeError,match='needs fixtures or a live runner'):
        jobs.series_fetch({'adapter':'listing','engine':'ffl','ref':'state:north'})
