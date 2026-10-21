"""CORE-1: offline decisions plus disposable-Postgres receipts, isolation and caps."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import secrets
import uuid

import httpx
from fastapi import FastAPI
import pytest
from pypdf import PdfReader

import bench
import graduate
import proof
from gold import PLATFORM_TENANT
from test_train1 import database as _database

database = _database
ROOT = Path(__file__).resolve().parents[1]


def roster():
    return [dict(model_name=name, litellm_params={'model': f'openai/gpt-{name}'},
                 model_info={'input_cost_per_token': price, 'output_cost_per_token': price})
            for name, price in [('expensive', .001), ('cheap', .0001)]]


def test_proposes_only_cheaper_no_score_regression_against_candidate():
    rows = [dict(model=name, score=score, cost_per_call=cost, status='complete')
            for name, score, cost in [('live',.7,3),('candidate',.9,2),('bad',.8,.1),('good',.9,.5)]]
    assert bench.choose_candidate(rows,'candidate','live') == 'good'
    rows[-1]['status']='capped'
    assert bench.choose_candidate(rows,'candidate','live') is None
    rows[1]['status']='failed'
    assert bench.choose_candidate(rows,'candidate','live') is None


def test_nightly_and_both_price_dimensions_trigger():
    book=bench.price_book(roster())
    rf,pf=bench.fingerprints(book)
    now=datetime.now(timezone.utc)
    state=dict(bench_at=now,bench_roster_fingerprint=rf,bench_price_fingerprint=pf)
    assert not bench.due(state,now,rf,pf)
    assert bench.due(state,now+timedelta(days=1),rf,pf)
    assert bench.due(state,now,'changed',pf)
    book['cheap']['input'] += Decimal('.00001')
    book['cheap']['output'] -= Decimal('.00001')
    assert bench.due(state,now,*bench.fingerprints(book))
    unpriced=roster(); unpriced[0]['model_info']['output_cost_per_token']=None
    assert 'expensive' not in bench.price_book(unpriced)


def test_automatic_promotion_missing_or_null_stays_off():
    for value in ({}, {'auto_promote':None}, {'auto_promote':False}):
        assert not graduate._wants_auto(value)


def test_proof_arithmetic_includes_negative_savings_and_excludes_bench_cache_from_code():
    base=dict(task_type='fixture',agent='base',cost_usd='.10',baseline_cost_usd='.25',baseline_status='measured',rung=1,cache_hit=False,outcome='delivered')
    rows=[base,dict(base,cost_usd='.4',baseline_status='backfilled'),dict(base,agent='bench'),
          dict(base,cost_usd=0,baseline_cost_usd=0,rung=3),dict(base,cost_usd=0,baseline_cost_usd=0,rung=4,cache_hit=True),
          dict(base,baseline_cost_usd=None)]
    row=proof.summarize(rows,[],[],[])[0]
    assert row['saved_usd']==0
    assert row['actual_usd']==Decimal('.5')
    assert row['code_share']==.2 and row['code_calls']==1
    assert row['unpriced_calls']==1 and row['backfilled_calls']==1


@pytest.mark.asyncio
async def test_founder_gate_including_exports(monkeypatch):
    key=secrets.token_urlsafe(32)
    monkeypatch.setenv('TANK_API_KEY',key); monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','founder-fixture')
    app=FastAPI(); app.include_router(proof.router)
    async def snap(*args):
        return dict(tenant_id=str(PLATFORM_TENANT),region='us-east',**{k:[] for k in ['tasks','ledger','shadows','runs','cases','promotions','policies','state']})
    monkeypatch.setattr(proof,'snapshot',snap)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        for path in ('/v1/proof','/v1/proof/export/csv','/v1/proof/export/pdf'):
            assert (await client.get(path)).status_code==404
            assert (await client.get(path,headers={'x-tank-key':key,'x-tervory-admin':'reviewer-fixture'})).status_code==404
            assert (await client.get(path,headers={'x-tank-key':key,'x-tervory-admin':'founder-fixture'})).status_code==200


def test_exports_complete_safe_and_pdf_is_readable():
    data=dict(tenant_id=str(PLATFORM_TENANT),region='us-east',**{k:[] for k in ['tasks','ledger','shadows','runs','cases','promotions','policies','state']})
    data['ledger']=[dict(id=str(i),task_type='=malicious',saved_usd=i) for i in range(140)]
    csv=proof.csv_export(data)
    assert "'=malicious" in csv and ',139,' in csv
    reader=PdfReader(BytesIO(proof.pdf_export(data)))
    assert len(reader.pages)>1
    assert '139' in ''.join(p.extract_text() for p in reader.pages)


@pytest.mark.asyncio
async def test_receipts_backfill_schema_repeat_and_median(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.policy(task_type,model) VALUES ('fixture','cheap')")
        # Historical receipt before the price book exists.
        old=await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd)
            VALUES($1,'base','fixture','cheap',100,20,.01) RETURNING id""",PLATFORM_TENANT)
        await bench.sync_prices(conn,bench.price_book(roster()))
        await bench.backfill(conn,PLATFORM_TENANT,'us-east')
        row=await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1',old)
        assert row['baseline_model']=='expensive' and row['baseline_status']=='backfilled'
        assert row['baseline_cost_usd']==Decimal('.12')
        for cost in (.02,.90):
            await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd)
                VALUES($1,'base','fixture','cheap',100,20,$2)""",PLATFORM_TENANT,cost)
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,cost_usd)
            VALUES($1,'bench','fixture','cheap',99)""",PLATFORM_TENANT)
        table=await graduate.training_table(conn,PLATFORM_TENANT,'us-east')
        assert next(r for r in table if r['task_type']=='fixture')['current_cost']==.02
        before=await conn.fetch('SELECT * FROM tank.ledger ORDER BY id')
        await conn.execute((ROOT/'tank/schema.sql').read_text())
        await bench.backfill(conn,PLATFORM_TENANT,'us-east')
        assert await conn.fetch('SELECT * FROM tank.ledger ORDER BY id')==before
        assert not await conn.fetchval("SELECT auto_promote FROM tank.policy WHERE task_type='fixture'")
        assert 'false' in await conn.fetchval("SELECT column_default FROM information_schema.columns WHERE table_schema='tank' AND table_name='policy' AND column_name='auto_promote'")
    data=await proof.snapshot(PLATFORM_TENANT,'fixture')
    summary=data['tasks'][0]
    assert summary['calls']==3 and summary['actual_usd']==.93
    assert summary['saved_usd']==-.57
    assert len((await proof.snapshot(uuid.uuid4(),'fixture'))['ledger'])==0


@pytest.mark.asyncio
async def test_bench_runs_every_model_records_scores_proposes_and_does_not_switch(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async def models(): return roster()
    rt._roster_models=models
    called=[]
    async def call(model,messages,max_tokens):
        called.append(model)
        return dict(model=model,content='{"answer":"yes"}',tokens_in=100,tokens_out=20,
                    cost=Decimal('.012') if model=='cheap' else Decimal('.12'),ok=True)
    monkeypatch.setattr(bench,'call_model',call)
    monkeypatch.setenv('TANK_BENCH_MAX_USD','5')
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.policy(task_type,model,max_tokens_out) VALUES ('fixture','expensive',10)")
        await conn.execute("""INSERT INTO tank.evals(task_type,input,expected) VALUES('fixture','{"text":"test"}','{"answer":"yes"}')""")
        await conn.execute("""INSERT INTO tank.evals(task_type,tenant_id,input,expected) VALUES('fixture',$1,'{}','{}')""",uuid.uuid4())
    await bench.tick()
    assert called==['cheap','expensive']
    async with pool.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM tank.policy WHERE task_type='fixture'")
        assert row['model']=='expensive' and row['candidate_model']=='cheap' and not row['auto_promote']
        assert await conn.fetchval("SELECT count(*) FROM tank.route_evidence WHERE task_type='fixture' AND bench_n=1")==2
        assert await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND agent='bench'",PLATFORM_TENANT)==2
        assert await conn.fetchval("SELECT count(*) FROM tank.bench_calls WHERE tenant_id=$1 AND status='complete'",PLATFORM_TENANT)==2
    await bench.tick()
    assert called==['cheap','expensive'] # no replay before next night or roster change


@pytest.mark.asyncio
async def test_reservation_cap_survives_unknown_spend_and_concurrent_requests(database):
    import asyncio
    pool,_=database
    async with pool.acquire() as conn:
        run=await conn.fetchval("""INSERT INTO tank.bench_runs(tenant_id,region,task_type,model,comparison_model,suite_hash,expected_n)
            VALUES($1,'us-east','fixture','cheap','expensive','hash',2) RETURNING id""",PLATFORM_TENANT)
    async def reserve():
        async with pool.acquire() as conn:
            return await bench.reserve(conn,run,'us-east',{'ref':'one','kind':'eval'},Decimal('.6'),Decimal('1'))
    ids=await asyncio.gather(reserve(),reserve())
    assert sum(x is not None for x in ids)==1
    # Unsettled reservations survive another attempt/restart.
    assert await reserve() is None


@pytest.mark.asyncio
async def test_bench_cap_prevents_network_and_partial_proposals(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async def forbidden(*args): raise AssertionError('No funds reserved')
    monkeypatch.setattr(bench,'call_model',forbidden)
    policy={'task_type':'fixture','model':'expensive','max_tokens_out':100}
    cases=[{'ref':'one','kind':'eval','input':'x','expected':'x'}]
    async with pool.acquire() as conn:
        result=await bench.bench_model(conn,policy,'cheap',cases,bench.price_book(roster()),'us-east',Decimal('0'),'expensive')
        assert result['status']=='capped' and result['score'] is None
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1',PLATFORM_TENANT)==0
