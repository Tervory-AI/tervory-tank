"""Research evidence and receipts persist before optional memory, with no model I/O."""
import copy
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'agents/market_lab'))
from core import research_records, http, research_adapter
from core.ledger import MemoryLedger


def research(cost=None):
    return {'facts':[{'text':'Recorded inventory rose.', 'href':'https://www.census.gov/data.html',
        'name':'Recorded source','fetched_at':'2026-11-05T00:00:00+00:00','quote':'inventory rose'}],
        'sources':[], 'receipts':[{'ledger_id':str(uuid4()),'tokens_in':11,'tokens_out':7,'cost_usd':cost}]}


@pytest.mark.asyncio
async def test_report_keeps_original_receipts_and_unknown_cost_and_survives_memory_failure():
    owner, other=str(uuid4()),str(uuid4());ledger=MemoryLedger();data=research()
    original=copy.deepcopy(data)
    report=await research_records.save(ledger,owner,'Inventory?',data)
    assert data==original and ledger.reports[0]['receipts']==data['receipts']
    assert report['citations'][0]['quote']=='inventory rose'
    assert report['receipts'][0]['cost_usd'] is None
    memory=SimpleNamespace(remember=AsyncMock(side_effect=RuntimeError('unavailable')))
    await research_records.remember(memory,report)
    assert len(ledger.reports)==1
    memory.remember.assert_awaited_once_with(owner,report['answer'],'report',data['facts'][0]['href'])
    assert not [r for r in ledger.reports if r['tenant_id']==other]


@pytest.mark.asyncio
@pytest.mark.parametrize('mutation',['no_facts','bad_url','invalid_ledger','negative_cost'])
async def test_invalid_evidence_or_receipts_are_never_saved(mutation):
    data=research(.01);ledger=MemoryLedger()
    if mutation=='no_facts':data['facts']=[]
    if mutation=='bad_url':data['facts'][0]['href']='https://user:private@example.com/'
    if mutation=='invalid_ledger':data['receipts'][0]['ledger_id']='not-a-receipt'
    if mutation=='negative_cost':data['receipts'][0]['cost_usd']=-1
    with pytest.raises(ValueError):await research_records.save(ledger,str(uuid4()),'question',data)
    assert ledger.reports==[]


@pytest.mark.asyncio
async def test_http_research_releases_database_for_network_and_remembers_after_save(monkeypatch):
    owner=str(uuid4());ledger=MemoryLedger();active=[];events=[]
    class Memory:
        async def remember(self,*args):
            assert not active and ledger.reports
            events.append('remember')
    ledger.memory=Memory()
    @asynccontextmanager
    async def connection():
        active.append(True)
        try:yield ledger
        finally:active.pop()
    async def local(*args,**kwargs):return {'content':'No stored data matches this question','facts':[],'sources':[]}
    async def network(tenant,question):
        assert tenant==owner and not active
        events.append('research')
        return research(.004)
    monkeypatch.setattr(http,'answer',local);monkeypatch.setattr(research_adapter,'research_web',network)
    app=FastAPI();app.include_router(http.build_router(key_ok=lambda key:key=='placeholder-room',ledger_context=connection))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://room') as client:
        response=await client.post('/market/ask',headers={'X-Tank-Key':'placeholder-room'},json={'tenant_id':owner,'question':'inventory'})
    assert response.status_code==200
    assert response.json()['report_id']==ledger.reports[0]['id']
    assert ledger.reports[0]['receipts']==response.json()['receipts']
    assert events==['research','remember']


@pytest.mark.asyncio
async def test_real_postgres_migrates_legacy_report_and_retains_receipts(tmp_path):
    import asyncpg
    import json
    import pgserver
    from core.ledger import PostgresLedger
    server=pgserver.get_server(tmp_path/'reports-pg')
    conn=await asyncpg.connect(server.get_uri())
    try:
        await conn.execute('''CREATE SCHEMA agent_market_lab;
            CREATE TABLE agent_market_lab.reports (
                id uuid PRIMARY KEY,tenant_id uuid NOT NULL,made_at timestamptz NOT NULL,
                question text NOT NULL,answer text NOT NULL,citations jsonb NOT NULL)''')
        ledger=PostgresLedger(conn)
        await ledger.apply_schema();await ledger.apply_schema()
        owner,other=str(uuid4()),str(uuid4());data=research(.004)
        report=await research_records.save(ledger,owner,'Recorded inventory?',data)
        saved=await conn.fetchrow('SELECT receipts,citations FROM agent_market_lab.reports WHERE tenant_id=$1 AND id=$2',
            __import__('uuid').UUID(owner),__import__('uuid').UUID(report['id']))
        assert json.loads(saved['receipts'])==data['receipts']
        assert json.loads(saved['citations'])[0]['fetched_at']=='2026-11-05T00:00:00+00:00'
        assert await conn.fetchval('SELECT count(*) FROM agent_market_lab.reports WHERE tenant_id=$1',__import__('uuid').UUID(other))==0
    finally:
        await conn.close();server.cleanup()


@pytest.mark.asyncio
async def test_scheduled_live_refresh_uses_recorded_publishers_and_private_postgres(monkeypatch,tmp_path):
    import asyncpg
    import importlib.util
    import io
    import json
    import pgserver
    from core.jobs import perform_refresh
    from core.ledger import PostgresLedger
    from core.evidence import answer, overview
    from feeds.collect import EvidenceClient
    from feeds.live import PoliteClient
    server=pgserver.get_server(tmp_path/'sources-pg');conn=await asyncpg.connect(server.get_uri())
    try:
        ledger=PostgresLedger(conn);await ledger.apply_schema()
        spec=importlib.util.spec_from_file_location('finish_live_room',ROOT/'agents/market_lab/app.py')
        room=importlib.util.module_from_spec(spec);sys.modules[spec.name]=room;spec.loader.exec_module(room)
        owner,other=str(uuid4()),str(uuid4());calls=[]
        class Response(io.BytesIO): status=200
        def opener(request,**kwargs):
            name={'https://data.sec.gov/submissions/CIK0000095029.json':'ruger.json',
                  'https://data.sec.gov/submissions/CIK0001092796.json':'swbi.json'}[request.full_url]
            calls.append(request.full_url)
            return Response((ROOT/'tests/fixtures/feeds/sec_edgar'/name).read_bytes())
        client=EvidenceClient(PoliteClient(opener=opener,delay=0))
        async def refresh(**kwargs):
            assert kwargs['fixtures'] is None and kwargs['live'] is True
            return await perform_refresh(**kwargs,source='sec_edgar',client=client)
        @asynccontextmanager
        async def connection(**kwargs): yield ledger
        monkeypatch.setattr(room,'_ledger',connection)
        monkeypatch.setattr(room,'perform_refresh',refresh)
        import core.warning_http
        monkeypatch.setattr(core.warning_http,'refresh',AsyncMock(return_value={'warnings':0}))
        monkeypatch.delenv('FEEDS_FIXTURES',raising=False)
        ctx=SimpleNamespace(tenant_id=owner,input={'engine':'ffl'},memory=None)
        result=await room.refresh(ctx)
        assert len(calls)==2 and result['feeds'][0]['rows']==2000
        assert not result['feeds'][0]['fixture']
        assert 'opportunities' not in result  # Event-only reads add no demand/supply measurements.
        doc=await conn.fetchval('SELECT content FROM agent_market_lab.feed_documents WHERE tenant_id=$1',__import__('uuid').UUID(owner))
        stored=json.loads(doc)
        assert len(stored['downloads'])==2 and all(len(d['sha256'])==64 for d in stored['downloads'])
        assert (await overview(ledger,owner,'ffl'))['on_count']==1
        assert (await answer(ledger,owner,'Recent SEC filings from Ruger',engine='ffl'))['facts']
        assert not (await answer(ledger,other,'Recent SEC filings from Ruger',engine='ffl'))['facts']
        await room.refresh(ctx)
        assert (await overview(ledger,owner,'ffl'))['on_count']==1
    finally:
        await conn.close();server.cleanup()
