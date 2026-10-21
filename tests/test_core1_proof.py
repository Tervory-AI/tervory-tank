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
from test_train1 import database as _database, URL

database = _database
ROOT = Path(__file__).resolve().parents[1]


def roster():
    return [dict(model_name=name, litellm_params={'model': f'openai/gpt-{name}'},
                 model_info={'input_cost_per_token': price, 'output_cost_per_token': price})
            for name, price in [('expensive', .001), ('cheap', .0001)]]


def comparison_roster():
    return roster()+[dict(model_name="sol",litellm_params={"model":"openai/gpt-sol"},
        model_info={"input_cost_per_token":.001,"output_cost_per_token":.001})]


def test_proposes_only_cheaper_no_score_regression_against_live():
    rows = [dict(model=name, score=score, cost_per_call=cost, status='complete')
            for name, score, cost in [('live',.9,3),('candidate',.7,2),('bad',.8,.1),('good',.9,.5)]]
    assert bench.choose_candidate(rows,'live') == 'good'
    rows[-1]['status']='capped'
    assert bench.choose_candidate(rows,'live') is None
    rows[-1]['status']='complete'
    rows[0]['status']='failed'
    assert bench.choose_candidate(rows,'live') is None


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
        await bench.sync_prices(conn,bench.price_book(comparison_roster()))
        await conn.execute("UPDATE tank.ledger SET baseline_status='pending' WHERE id=$1",old)
        await bench.backfill(conn,PLATFORM_TENANT,'us-east')
        row=await conn.fetchrow('SELECT * FROM tank.ledger WHERE id=$1',old)
        assert row['baseline_model']=='sol' and row['baseline_status']=='backfilled'
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
    async with pool.acquire() as conn:
        rt.DATABASE_URL=URL.rsplit('/',1)[0]+'/'+await conn.fetchval('SELECT current_database()')
    called=[]
    async def call(model,messages,max_tokens):
        assert pool.get_idle_size() == pool.get_size(), 'No request-pool connection may be held during a model call'
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
    assert called==['expensive','cheap']
    async with pool.acquire() as conn:
        row=await conn.fetchrow("SELECT * FROM tank.policy WHERE task_type='fixture'")
        assert row['model']=='expensive' and row['candidate_model']=='cheap' and not row['auto_promote']
        assert await conn.fetchval("SELECT count(*) FROM tank.route_evidence WHERE task_type='fixture' AND bench_n=1")==2
        assert await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND agent='bench'",PLATFORM_TENANT)==2
        assert await conn.fetchval("SELECT count(*) FROM tank.bench_calls WHERE tenant_id=$1 AND status='complete'",PLATFORM_TENANT)==2
    await bench.tick()
    assert called==['expensive','cheap'] # no replay before next night or roster change


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
        result=await bench.bench_model(pool,policy,'cheap',cases,bench.price_book(roster()),'us-east',Decimal('0'),'expensive')
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
        result=await bench.bench_model(pool,policy,'cheap',[{'ref':'one','kind':'eval','input':'x','expected':'x'}],
                                      bench.price_book(roster()),'us-east',Decimal('5'),'expensive')
        assert result['status']=='failed' and result['score'] is None
        row=await conn.fetchrow('SELECT * FROM tank.bench_calls WHERE tenant_id=$1',PLATFORM_TENANT)
        assert row['charged_usd'] is None and row['reserved_usd']>0 and row['status']=='unverified'
        assert row['ledger_id'] is None
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1',PLATFORM_TENANT)==0


@pytest.mark.asyncio
@pytest.mark.parametrize('price',[0,.0001])
async def test_founder_pause_stops_bench_before_reservation_and_network(database,monkeypatch,price):
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
        book=bench.price_book(roster())
        book['cheap']['input']=book['cheap']['output']=Decimal(str(price))
        result=await bench.bench_model(pool,policy,'cheap',[{'ref':'one','kind':'eval','input':'x','expected':'x'}],
                                      book,'us-east',Decimal('5'),'expensive')
        assert result['status']=='paused' and not called
        assert await conn.fetchval('SELECT count(*) FROM tank.bench_calls WHERE tenant_id=$1',PLATFORM_TENANT)==0
        assert await conn.fetchval('SELECT count(*) FROM tank.ledger WHERE tenant_id=$1',PLATFORM_TENANT)==0
        assert await conn.fetchval("SELECT count(*) FROM tank.control_log WHERE tenant_id=$1 AND task='fixture' AND path='bench'",PLATFORM_TENANT)==1


@pytest.mark.asyncio
async def test_schema_migration_runs_once_preserving_founder_choice(database):
    pool,_=database
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM tank.policy_log WHERE detail->>'id'='2026-10-21-core1-auto-off'")
        await conn.execute("INSERT INTO tank.policy(task_type,model,auto_promote) VALUES('fixture','cheap',true)")
        await conn.execute((ROOT/'tank/schema.sql').read_text())
        assert not await conn.fetchval("SELECT auto_promote FROM tank.policy WHERE task_type='fixture'")
        await conn.execute("UPDATE tank.policy SET auto_promote=true WHERE task_type='fixture'")
        await conn.execute((ROOT/'tank/schema.sql').read_text())
        assert await conn.fetchval("SELECT auto_promote FROM tank.policy WHERE task_type='fixture'")
        assert await conn.fetchval("SELECT count(*) FROM tank.policy_log WHERE detail->>'id'='2026-10-21-core1-auto-off'")==1


@pytest.mark.asyncio
async def test_backfill_batches_once_daily_and_retries_unpriced_on_price_change(database):
    pool,_=database
    await pool.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,cost_usd)
        SELECT $1,'base','fixture','cheap',100,.01 FROM generate_series(1,5001)""",PLATFORM_TENANT)
    book=bench.price_book(comparison_roster())
    async with pool.acquire() as conn:
        await bench.sync_prices(conn,book)
    await bench.scheduled_backfill(pool,'us-east','first')
    assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE baseline_status='backfilled'")==5001
    unknown=await pool.fetchval("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,cost_usd)
        VALUES($1,'base','unknown','missing',100,.01) RETURNING id""",PLATFORM_TENANT)
    await bench.scheduled_backfill(pool,'us-east','first')
    assert await pool.fetchval('SELECT baseline_status FROM tank.ledger WHERE id=$1',unknown)=='unpriced'
    await pool.execute("UPDATE tank.search_state SET bench_at=now()-interval '1 day' WHERE task_type='@backfill:us-east'")
    await bench.scheduled_backfill(pool,'us-east','first')
    assert await pool.fetchval('SELECT baseline_status FROM tank.ledger WHERE id=$1',unknown)=='unpriced'
    # Daily retry must not keep locking unpriceable historical rows.
    await pool.execute("UPDATE tank.search_state SET bench_at=now()-interval '1 day' WHERE task_type='@backfill:us-east'")
    await bench.scheduled_backfill(pool,'us-east','first')
    assert await pool.fetchval('SELECT baseline_status FROM tank.ledger WHERE id=$1',unknown)=='unpriced'
    book['missing']=book['cheap']
    async with pool.acquire() as conn:
        await bench.sync_prices(conn,book)
    await bench.scheduled_backfill(pool,'us-east','changed')
    assert await pool.fetchval('SELECT baseline_status FROM tank.ledger WHERE id=$1',unknown)=='backfilled'


@pytest.mark.asyncio
async def test_proof_sql_totals_match_paged_rows_scopes_windows_flags_and_exports(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    other=uuid.uuid4()
    start=datetime(2026,1,1,tzinfo=timezone.utc); end=start+timedelta(days=1)
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('cheap','family-a',.001,.001),('baseline','family-b',.001,.001)")
    # Explicit historic snapshots, including negative savings. 205 rows require 3 pages.
    await pool.execute("""INSERT INTO tank.ledger(tenant_id,region,ts,agent,task_type,model,cost_usd,baseline_model,baseline_cost_usd,baseline_status)
        SELECT $1,'us-east',$2,'base','fixture','cheap',.4,'baseline',.25,'backfilled' FROM generate_series(1,205)""",PLATFORM_TENANT,start)
    for tenant,region,agent,task,ts in [(other,'us-east','base','fixture',start),
            (PLATFORM_TENANT,'za','base','fixture',start),(PLATFORM_TENANT,'us-east','bench','fixture',start),
            (PLATFORM_TENANT,'us-east','shadow','fixture',start),(PLATFORM_TENANT,'us-east','base','fixture#shadow',start),
            (PLATFORM_TENANT,'us-east','base','different',start),(PLATFORM_TENANT,'us-east','base','fixture',end)]:
        await pool.execute("""INSERT INTO tank.ledger(tenant_id,region,agent,task_type,ts,model,cost_usd,baseline_cost_usd,baseline_status)
            VALUES($1,$2,$3,$4,$5,'cheap',.1,.25,'measured')""",tenant,region,agent,task,ts)
    # Explicit old snapshots test negative/mismatched evidence independently of today's default trigger.
    await pool.execute("UPDATE tank.ledger SET baseline_model='baseline',baseline_cost_usd=.25,standard_model='baseline',standard_cost_usd=.25,baseline_status='backfilled'")
    pages=[await proof.snapshot(PLATFORM_TENANT,'fixture',start,end,n) for n in range(3)]
    rows=[r for page in pages for r in page['ledger']]
    assert len(rows)==len({r['id'] for r in rows})==205
    assert [len(p['ledger']) for p in pages]==[100,100,5]
    assert [p['has_more']['ledger'] for p in pages]==[True,True,False]
    assert all(p['tasks'][0]['saved_usd']==-30.75 and p['tasks'][0]['calls']==205 for p in pages)
    assert sum(Decimal(str(r['saved_usd'])) for r in rows)==Decimal('-30.75')
    assert all(r['baseline_below_actual'] and r['baseline_family_mismatch'] for r in rows)
    assert all(r['agent']=='base' and r['tenant_id']==str(PLATFORM_TENANT) for r in rows)
    all_data=await proof.snapshot(None,'fixture',start,end)
    assert all_data['tasks'][0]['calls']==206 and all_data['tasks'][0]['saved_usd']==-30.6
    assert all_data['all_tenant_total']['calls']==207 and all_data['all_tenant_total']['saved_usd']==-30.45
    assert set(all_data['tenants'])=={str(PLATFORM_TENANT),str(other)}
    assert (await proof.snapshot(other,'fixture',start,end))['tasks'][0]['calls']==1
    csv=proof.csv_export(pages[0]); pdf=''.join(p.extract_text() for p in PdfReader(BytesIO(proof.pdf_export(pages[0]))).pages)
    assert rows[0]['id'] in csv and rows[0]['id'] in pdf
    assert rows[-1]['id'] not in csv and rows[-1]['id'] not in pdf
    assert 'receipt_page_total' in csv and 'selected page' in pdf


@pytest.mark.asyncio
async def test_bench_cost_is_separate_from_econ_and_dashboard_call_counts(database):
    import admin
    import dashboards
    pool,_=database
    await pool.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,cost_usd)
        VALUES($1,'base','fixture','cheap',.1),($1,'bench','fixture','cheap',.2)""",PLATFORM_TENANT)
    async with pool.acquire() as conn:
        rows=await conn.fetch(admin._CALL_SELECT+' GROUP BY 1,2,3,4,5,6')
        assert sum(r['calls'] for r in rows)==1 and sum(r['cost'] for r in rows)==Decimal('.3')
        report=await dashboards.measurements(conn,PLATFORM_TENANT)
        assert sum(r['calls'] for r in report['daily'])==1
        assert sum(r['delivered'] for r in report['daily'])==1
        assert sum(r['spent'] for r in report['daily'])==.3
        fixture=admin.aggregate_calls([dict(r) for r in await conn.fetch('SELECT * FROM tank.ledger')])
        assert sum(r['calls'] for r in fixture.values())==1
        assert sum(r['cost'] for r in fixture.values())==pytest.approx(.3)


@pytest.mark.asyncio
async def test_sql_code_share_excludes_cache_and_counts_unpriced_separately(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    for rung,cache,cost,baseline in [(3,False,0,0),(3,True,0,0),(1,False,.1,None)]:
        await pool.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,rung,cache_hit,cost_usd,baseline_cost_usd,baseline_status)
            VALUES($1,'base','fixture','cheap',$2,$3,$4,$5,'unpriced')""",PLATFORM_TENANT,rung,cache,cost,baseline)
    data=await proof.snapshot(PLATFORM_TENANT,'fixture')
    row=data['tasks'][0]
    assert row['code_calls']==1 and row['calls']==3 and row['code_share']==1/3
    assert row['priced_calls']==2 and row['unpriced_calls']==1
    assert row['actual_usd']==.1 # known spend remains visible without a baseline
    assert row['compared_actual_usd']==row['baseline_usd']==row['saved_usd']==0


@pytest.mark.asyncio
async def test_research_unknown_and_vendor_fees_never_claim_baseline_savings(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    async with pool.acquire() as conn:
        await bench.sync_prices(conn,bench.price_book(comparison_roster()))
        await conn.execute("UPDATE tank.policy SET model='cheap',baseline_model='expensive' WHERE task_type='market.research' AND tenant_id IS NULL")
        ids=[]
        for model,vendor,cost_status,cost in [('cheap',None,'unknown',0),
                ('vendor:search',None,None,2),('vendor:fetch','fetch',None,3),('cheap','other',None,2)]:
            row=await conn.fetchrow("""INSERT INTO tank.ledger
                (tenant_id,agent,task_type,model,vendor,research_cost_status,tokens_in,tokens_out,cost_usd)
                VALUES($1,'market_lab','market.research',$2,$3,$4,100,20,$5) RETURNING *""",PLATFORM_TENANT,model,vendor,cost_status,cost)
            ids.append(row['id'])
            assert row['baseline_cost_usd'] is None and row['baseline_model'] is None and row['baseline_status']=='unpriced'
        await conn.execute("""INSERT INTO tank.ledger
            (tenant_id,agent,task_type,model,research_cost_status,tokens_in,tokens_out,cost_usd)
            VALUES($1,'market_lab','market.research','cheap','itemized',100,20,.01)""",PLATFORM_TENANT)
        # Simulate receipts predating the pricing trigger, then apply the backfill.
        await conn.execute("UPDATE tank.ledger SET baseline_status='pending' WHERE id=ANY($1::uuid[])",ids)
        await bench.backfill(conn,PLATFORM_TENANT,'us-east')
        rows=await conn.fetch('SELECT * FROM tank.ledger WHERE id=ANY($1::uuid[])',ids)
        assert all(r['baseline_cost_usd'] is None and r['baseline_status']=='unpriced' for r in rows)
        await conn.execute((ROOT/'tank/schema.sql').read_text())
    data=await proof.snapshot(PLATFORM_TENANT,'market.research')
    row=data['tasks'][0]
    assert row['actual_usd']==7.01 and row['compared_actual_usd']==.01
    assert row['baseline_usd']==.12 and row['saved_usd']==.11
    assert row['unknown_cost_calls']==1 and row['unpriced_calls']==4
    unknown=next(r for r in data['ledger'] if r['research_cost_status']=='unknown')
    assert unknown['cost_usd'] is None and unknown['saved_usd'] is None
    assert sum(Decimal(str(r['cost_usd'] or 0)) for r in data['ledger'])==Decimal('7.01')


@pytest.mark.asyncio
async def test_paused_ticks_do_not_create_runs_audits_or_reservations_and_resume(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(controls,'db',lambda:pool)
    monkeypatch.setattr(bench,'runtime',lambda:rt)
    async def forbidden(): raise AssertionError('A paused tick must not fetch the roster')
    rt._roster_models=forbidden
    await pool.execute("INSERT INTO tank.controls(tenant_id,name,value,updated_by) VALUES($1,'paid_paused',true,'fixture')",PLATFORM_TENANT)
    for _ in range(3):
        status=await bench.tick()
        assert status=='paused'
        await bench.worker_status(None,status)
    for table in ('bench_runs','bench_calls','control_log'):
        assert await pool.fetchval('SELECT count(*) FROM tank.'+table)==0
    assert await pool.fetchval("SELECT bench_status FROM tank.search_state WHERE task_type='@bench'")=='paused'
    await pool.execute("UPDATE tank.controls SET value=false WHERE tenant_id=$1 AND name='paid_paused'",PLATFORM_TENANT)
    # No secret is needed for this test: reaching validation proves unpause resumes work.
    rt.LITELLM_MASTER_KEY=''
    with pytest.raises(RuntimeError,match='not configured'):
        await bench.tick()


def test_quote_uses_requested_model_rates_not_expensive_roster_peers():
    book=bench.price_book(roster())
    book['huge']={'input':Decimal('10'),'output':Decimal('20'),'family':'expensive'}
    messages=bench.messages_for('one short case',None)
    quote=bench.reserve_quote(messages,100,book['cheap'])
    assert Decimal(0)<quote<Decimal('.2')
    assert bench.reserve_quote(messages,100,book['huge'])>Decimal('5')


def test_csv_negative_numbers_remain_numeric_while_text_formulas_are_escaped():
    import csv
    data=dict(tenant_id=str(PLATFORM_TENANT),region='us-east',**{k:[] for k in ['tasks','ledger','shadows','runs','cases','promotions','policies','state']})
    data['ledger']=[dict(id='one',saved_usd=Decimal('-.25'),cost_usd=-2,task_type='=HYPERLINK("bad")',model='-formula')]
    values={r['field']:r['value'] for r in csv.DictReader(proof.csv_export(data).splitlines()) if r['section']=='ledger'}
    assert values['saved_usd']=='-0.25' and values['cost_usd']=='-2'
    assert values['task_type'].startswith("'=") and values['model']=="'-formula"


def test_tenant_name_resolution_uses_organisation_names():
    import subprocess
    subprocess.run(['node','tests/core1-tenant-names.cjs'],cwd=ROOT,check=True,capture_output=True,text=True)
