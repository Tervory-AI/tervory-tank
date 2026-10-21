"""CORE-2: exact populations, tenant/region boundaries, pagination and safe client projections."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import secrets
import subprocess
import uuid

from fastapi import FastAPI
import httpx
from pypdf import PdfReader
import pytest

import proof
from test_train1 import database as _database

database = _database
ROOT = Path(__file__).resolve().parents[1]
END = datetime(2026, 10, 21, tzinfo=timezone.utc)


async def seed(pool, tenant, *, count=1, day=None, model='cheap', cost='.1', baseline='.3',
               baseline_model='expensive', status='measured', agent='base', region='us-east',
               rung=1, cache=False, linked=True, research=None, outcome='delivered'):
    day = day or END-timedelta(days=1)
    job = uuid.uuid4()
    if linked:
        await pool.execute("""INSERT INTO tank.tasks(id,tenant_id,agent,task_type,title,input,status,finished_at)
            VALUES($1,$2,$3,'fixture','Business list','{}','done',$4)""", job, tenant, agent, day)
    ids = []
    for _ in range(count):
        ids.append(await pool.fetchval("""INSERT INTO tank.ledger(tenant_id,ts,agent,task_type,model,cost_usd,
            baseline_cost_usd,baseline_model,baseline_status,region,rung,cache_hit,task_id,research_cost_status,outcome)
            VALUES($1,$2,$3,'fixture',$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14) RETURNING id""",
            tenant,day,agent,model,Decimal(cost),Decimal(baseline) if baseline is not None else None,
            baseline_model,status,region,rung,cache,job if linked else None,research,outcome))
    return ids, job


async def prices(pool):
    await pool.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd)
        VALUES('cheap','same',.001,.001),('expensive','same',.01,.01),('other','different',.01,.01)""")


@pytest.mark.asyncio
async def test_graph_totals_reconcile_to_every_page_and_scope(database, monkeypatch):
    pool, rt = database
    monkeypatch.setattr(proof, 'runtime', lambda: rt)
    await prices(pool)
    a, b = uuid.uuid4(), uuid.uuid4()
    await seed(pool,a,count=205)
    await seed(pool,a,day=datetime(2025,1,1,tzinfo=timezone.utc),agent='tiger')
    await seed(pool,b,cost='2',baseline='3')
    await seed(pool,a,region='za',cost='8',baseline='9')
    await seed(pool,a,agent='bench',cost='4',baseline='5')
    await seed(pool,a,agent='shadow',cost='4',baseline='5')
    await seed(pool,a,day=END,cost='6',baseline='7')  # exclusive snapshot boundary
    data = await proof.savings_snapshot(a,END)
    assert data['total']['work_count'] == 206
    assert Decimal(data['total']['saved']) == Decimal('41.2')
    assert data['month']['work_count'] == 205
    assert Decimal(data['month']['saved']) == Decimal('41')
    assert data['total']['jobs_count'] == 2
    assert Decimal(data['daily'][-1]['cumulative']) == Decimal(data['total']['saved'])
    assert sum(Decimal(r['saved']) for r in data['members']) == Decimal(data['total']['saved'])
    pages = [await proof.savings_rows(a,END,n) for n in range(3)]
    assert [len(p['rows']) for p in pages] == [100,100,6]
    assert [p['has_more'] for p in pages] == [True,True,False]
    assert all(p['total']==data['total'] for p in pages)
    for field in ['spent','would_have_cost','saved']:
        assert sum(Decimal(r[field]) for p in pages for r in p['rows']) == Decimal(data['total'][field])
    assert not {'tenant_id','tenants','margin','excluded','region'} & data.keys()
    assert all(not {'id','model','baseline_model','tenant_id','excluded_reason'} & row.keys() for page in pages for row in page['rows'])
    all_data = await proof.savings_snapshot(None,END,founder=True)
    assert all_data['total']['work_count']==207
    assert Decimal(all_data['total']['saved'])==Decimal('42.2')
    assert {str(a),str(b),'00000000-0000-0000-0000-000000000001'} <= set(all_data['tenants'])
    tiger = await proof.savings_rows(a,END,member='Tiger')
    assert tiger['total']['work_count']==1 and tiger['rows'][0]['member']=='Tiger'
    month = await proof.savings_rows(a,END,start=END.replace(day=1))
    assert month['total']==data['month']
    day = await proof.savings_rows(a,END,start=END-timedelta(days=1),until=END)
    assert day['total']==data['month']
    assert (await proof.savings_snapshot(uuid.uuid4(),END))['total']['work_count']==0


@pytest.mark.asyncio
async def test_flagged_unknown_unlinked_and_foreign_jobs_never_reach_client(database, monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    a,b=uuid.uuid4(),uuid.uuid4()
    await seed(pool,a)  # only valid paid comparison
    for options in [dict(cost='.4'),dict(baseline_model='other'),dict(baseline_model='missing'),
                    dict(baseline=None,status='unpriced'),dict(research='unknown',cost='0'),
                    dict(model='vendor:search'),dict(linked=False),dict(outcome='failed')]:
        await seed(pool,a,**options)
    # A forged job reference must not match another tenant's title or job.
    _,foreign=await seed(pool,b)
    ids,_=await seed(pool,a,linked=False)
    await pool.execute('UPDATE tank.ledger SET task_id=$2 WHERE id=$1',ids[0],foreign)
    data=await proof.savings_snapshot(a,END)
    assert data['total']['work_count']==1
    assert (await proof.savings_rows(a,END))['total']==data['total']
    founder=await proof.savings_snapshot(a,END,founder=True)
    assert sum(r['count'] for r in founder['excluded'])==9
    flagged=await proof.savings_rows(a,END,population='excluded')
    assert len(flagged['rows'])==9
    assert all(r['id'] and r['excluded_reason'] for r in flagged['rows'])
    assert all(str(r['job_id'])!=str(foreign) for r in flagged['rows'])
    assert founder['margin']['status']=='no billing data yet'
    assert founder['margin']['paid'] is founder['margin']['margin'] is founder['margin']['margin_percent'] is None
    assert founder['margin']['total']['unknown_costs']==1
    # Valid zero-cost tools/cache without a price family claim zero savings only.
    await seed(pool,a,model='code',baseline_model='code',cost='0',baseline='0',status='no_tokens',rung=3)
    await seed(pool,a,model='cached',baseline_model='cached',cost='0',baseline='0',status='no_tokens',rung=4,cache=True)
    # Zero cost alone is not evidence of no model call.
    await seed(pool,a,cost='0',baseline='.3')
    data=await proof.savings_snapshot(a,END)
    assert data['total']['work_count']==4 and data['total']['free_count']==2
    free=await proof.savings_rows(a,END,free_only=True)
    assert free['total']['work_count']==2 and all(r['free_work'] for r in free['rows'])


@pytest.mark.asyncio
async def test_reverse_job_link_does_not_duplicate_receipts(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    a=uuid.uuid4()
    ids,job=await seed(pool,a)
    await pool.execute('UPDATE tank.ledger SET task_id=NULL WHERE id=$1',ids[0])
    await pool.execute('UPDATE tank.tasks SET ledger_id=$2 WHERE id=$1',job,ids[0])
    assert (await proof.savings_rows(a,END))['rows'][0]['job_id']==str(job)
    _,job2=await seed(pool,a)
    await pool.execute('UPDATE tank.tasks SET ledger_id=$2 WHERE id=$1',job2,ids[0])
    assert (await proof.savings_snapshot(a,END))['total']['work_count']==2


@pytest.mark.asyncio
async def test_authentication_and_no_client_all_scope(monkeypatch):
    key=secrets.token_urlsafe(32)
    monkeypatch.setenv('TANK_API_KEY',key)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','fixture-founder')
    app=FastAPI(); app.include_router(proof.router); app.include_router(proof.client_router)
    called=[]
    async def snap(tenant,end=None,founder=False):
        called.append((tenant,founder)); return {'ok':True}
    monkeypatch.setattr(proof,'savings_snapshot',snap)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        a=uuid.uuid4()
        assert (await client.get(f'/v1/client-savings?tenant_id={a}')).status_code==404
        assert (await client.get('/v1/client-savings',headers={'x-tank-key':key})).status_code==422
        assert (await client.get('/v1/client-savings?tenant_id=all',headers={'x-tank-key':key})).status_code==422
        assert (await client.get(f'/v1/client-savings?tenant_id={a}',headers={'x-tank-key':key})).status_code==200
        assert called[-1]==(a,False)
        for path in ['/v1/proof/savings','/v1/proof/savings/rows','/v1/proof/savings/export/csv','/v1/proof/savings/export/pdf']:
            for headers in [{},{'x-tank-key':key},{'x-tank-key':key,'x-tervory-admin':'other'}]:
                assert (await client.get(path,headers=headers)).status_code==404
        assert (await client.get('/v1/proof/savings',headers={'x-tank-key':key,'x-tervory-admin':'fixture-founder'})).status_code==200
        assert called[-1]==(None,True)


@pytest.mark.asyncio
async def test_exports_reconcile_and_keep_precise_decimals(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    a=uuid.uuid4()
    await seed(pool,a,count=101,cost='.000001',baseline='.00000325')
    await seed(pool,uuid.uuid4(),cost='777',baseline='888')
    await seed(pool,a,cost='2',baseline='1')
    csv=(await proof.savings_export('csv',END,a,1)).body.decode()
    assert '0.00022725' in csv and '0.00000325' in csv and '777' not in csv
    assert 'no billing data yet' in csv
    pdf=PdfReader(BytesIO((await proof.savings_export('pdf',END,a,1)).body))
    text=''.join(p.extract_text() for p in pdf.pages)
    assert '0.00022725' in text and 'Client savings' in text
    assert 'selected page' in text


def test_client_actions_resolve_tenant_server_side_and_project_arguments():
    subprocess.run(['node','tests/core2-actions.cjs'],cwd=ROOT,check=True,capture_output=True,text=True)


@pytest.mark.asyncio
async def test_completed_jobs_and_late_backfills_obey_snapshot_cutoff(database,monkeypatch):
    pool,rt=database
    monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    a=uuid.uuid4()
    ids,job=await seed(pool,a)
    before=await proof.savings_snapshot(a,END)
    await pool.execute('UPDATE tank.ledger SET baseline_priced_at=$2 WHERE id=$1',ids[0],END+timedelta(seconds=1))
    assert (await proof.savings_snapshot(a,END))['total']['work_count']==0
    assert (await proof.savings_rows(a,END))['total']['work_count']==0
    await pool.execute('UPDATE tank.ledger SET baseline_priced_at=NULL WHERE id=$1',ids[0])
    await pool.execute("UPDATE tank.tasks SET status='running',finished_at=NULL WHERE id=$1",job)
    assert (await proof.savings_snapshot(a,END))['total']['work_count']==0
    await pool.execute("UPDATE tank.tasks SET status='done',finished_at=$2 WHERE id=$1",job,END+timedelta(seconds=1))
    after=await proof.savings_snapshot(a,END)
    assert after['total']['work_count']==0 and before['revision']!=after['revision']
    assert (await proof.savings_snapshot(a,END+timedelta(seconds=2)))['total']['work_count']==1
    # The schema remains additive and repeatable with existing work.
    await pool.execute((ROOT/'tank/schema.sql').read_text())
    await pool.execute((ROOT/'tank/schema.sql').read_text())
    assert await pool.fetchval('SELECT count(*) FROM tank.tasks WHERE tenant_id=$1',a)==1
