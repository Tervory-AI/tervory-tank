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
import controls
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
    monkeypatch.setattr(controls,'db',lambda:pool)
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
    monkeypatch.setattr(controls,'db',lambda:pool)
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async def models(): return roster()
    rt._roster_models=models
    rt.LITELLM_MASTER_KEY="fixture-only"
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
    monkeypatch.setattr(controls,'db',lambda:pool)
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async def forbidden(*args): raise AssertionError('No funds reserved')
    monkeypatch.setattr(bench,'call_model',forbidden)
    policy={'task_type':'fixture','model':'expensive','max_tokens_out':100}
    cases=[{'ref':'one','kind':'eval','input':'x','expected':'x'}]
    async with pool.acquire() as conn:
        result=await bench.bench_model(conn,policy,'cheap',cases,bench.price_book(roster()),'us-east',Decimal('0'),'expensive')
        assert result['status']=='capped' and result['score'] is None
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1',PLATFORM_TENANT)==0


@pytest.mark.asyncio
async def test_hourly_rollup_rebuild_preserves_bench_evidence(database):
    pool,_=database
    async with pool.acquire() as conn:
        run=await conn.fetchval("""INSERT INTO tank.bench_runs
            (tenant_id,region,task_type,model,comparison_model,suite_hash,expected_n,status,score,cost_per_call,finished_at)
            VALUES($1,'us-east','fixture','cheap','expensive','hash',3,'complete',.99,.012,now()) RETURNING id""",PLATFORM_TENANT)
        for _ in range(2):
            await conn.execute("DELETE FROM tank.route_evidence WHERE task_type='fixture'")
            await conn.execute("INSERT INTO tank.route_evidence(task_type,model,rung,eval_score) VALUES('fixture','cheap',1,.8)")
            row=await conn.fetchrow("SELECT * FROM tank.route_evidence WHERE task_type='fixture'")
            assert row['bench_run_id']==run and row['bench_n']==3
            assert row['bench_score']==Decimal('.99') and row['bench_cost_per_call']==Decimal('.012')
            assert row['eval_score']==Decimal('.8') # rollup's independent measure remains intact


@pytest.mark.asyncio
async def test_heldout_examples_are_platform_and_box_scoped(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(controls,'db',lambda:pool)
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async with pool.acquire() as conn:
        for tenant,region,held,status in [(PLATFORM_TENANT,'us-east',True,'checked'),
                (PLATFORM_TENANT,'us-east',False,'checked'),(PLATFORM_TENANT,'za',True,'checked'),
                (uuid.uuid4(),'us-east',True,'checked'),(PLATFORM_TENANT,'us-east',True,'candidate')]:
            ref=str(uuid.uuid4())
            await conn.execute("""INSERT INTO tank.gold_examples
                (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status,holdout)
                VALUES($1,$2,'fixture','base','{}','{}','package',$3,$3,$4,$5)""",tenant,region,ref,status,held)
        cases=await bench.cases_for(conn,'fixture','us-east')
        assert len(cases)==1 and cases[0]['kind']=='holdout'


@pytest.mark.asyncio
async def test_unknown_response_cost_keeps_reservation_and_blocks_proposal(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(controls,'db',lambda:pool)
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async def unknown(*args):
        return dict(model='cheap',content='x',tokens_in=100,tokens_out=10,cost=None,ok=True)
    monkeypatch.setattr(bench,'call_model',unknown)
    policy={'task_type':'fixture','model':'expensive','max_tokens_out':100}
    async with pool.acquire() as conn:
        result=await bench.bench_model(conn,policy,'cheap',[{'ref':'one','kind':'eval','input':'x','expected':'x'}],
                                      bench.price_book(roster()),'us-east',Decimal('5'),'expensive')
        assert result['status']=='failed' and result['score'] is None
        row=await conn.fetchrow('SELECT * FROM tank.bench_calls WHERE tenant_id=$1',PLATFORM_TENANT)
        assert row['charged_usd'] is None and row['reserved_usd']>0 and row['status']=='unverified'
        assert await conn.fetchval('SELECT outcome FROM tank.ledger WHERE tenant_id=$1',PLATFORM_TENANT)=='unverified'


@pytest.mark.asyncio
async def test_founder_pause_stops_bench_before_reservation_and_network(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(controls,'db',lambda:pool)
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    called=[]
    async def forbidden(*args):
        called.append(True)
        raise AssertionError('A paused bench must not call a provider')
    monkeypatch.setattr(bench,'call_model',forbidden)
    policy={'task_type':'fixture','model':'expensive','max_tokens_out':100}
    async with pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.controls(tenant_id,name,value,updated_by)
            VALUES($1,'paid_paused',true,'fixture')""",PLATFORM_TENANT)
        result=await bench.bench_model(conn,policy,'cheap',[{'ref':'one','kind':'eval','input':'x','expected':'x'}],
                                      bench.price_book(roster()),'us-east',Decimal('5'),'expensive')
        assert result['status']=='paused' and not called
        assert await conn.fetchval('SELECT count(*) FROM tank.bench_calls WHERE tenant_id=$1',PLATFORM_TENANT)==0
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1',PLATFORM_TENANT)==0
        assert await conn.fetchval("SELECT count(*) FROM tank.control_log WHERE tenant_id=$1 AND task='fixture' AND path='bench'",PLATFORM_TENANT)==1
