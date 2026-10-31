"""CORE-2: exact populations, tenant/region boundaries, pagination and safe client projections."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
import re
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
UUID_TEXT = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.I)


def amounts(text):
    """Every number written in text, as a Decimal (777.00000000 reads as 777).

    Ids are removed first. Founder exports list tenant and ledger UUIDs, and a random
    UUID such as 1b2c3d4e-777a-... holds digit runs that a substring check like
    '777' not in csv would mistake for another tenant's amount."""
    return {Decimal(n) for n in re.findall(r'\d+(?:\.\d+)?', UUID_TEXT.sub(' ', text))}


def test_amounts_ignore_digits_inside_ids():
    assert amounts('1b2c3d4e-777a-4bcd-8777-123456789777') == set()
    assert amounts('row,1B2C3D4E-777A-4BCD-8777-123456789777,777.00000000,0.5') == {Decimal('777'), Decimal('0.5')}


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
    # Historical fixture snapshots are explicit, independent of today's provider defaults.
    await pool.execute("""UPDATE tank.ledger SET standard_model=$2,standard_cost_usd=$3,
        top_model=$2,top_cost_usd=$3,baseline_model=$2,baseline_cost_usd=$3,
        baseline_status=$4,baseline_priced_at=$5 WHERE id=ANY($1::uuid[])""",
        ids,baseline_model,Decimal(baseline) if baseline is not None and research!='unknown' and not model.startswith('vendor:') else None,status,day)
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
    async def snap(tenant,end=None,founder=False,**kwargs):
        called.append((tenant,founder)); return {'ok':True}
    monkeypatch.setattr(proof,'savings_snapshot',snap)
    from types import SimpleNamespace
    monkeypatch.setattr(proof,'runtime',lambda:SimpleNamespace(box_region=lambda:'us-east'))
    async def revision(tenant): return {'revision':'fixture'}
    monkeypatch.setattr(proof,'client_savings_revision',revision)
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
    foreign=uuid.uuid4()
    await seed(pool,foreign,cost='777',baseline='888')
    await seed(pool,a,cost='2',baseline='1')
    csv=(await proof.savings_export('csv',END,a,1)).body.decode()
    assert '0.00022725' in csv and '0.00000325' in csv
    # The other tenant leaks neither its id nor its amounts; compared as numbers, not substrings.
    assert str(foreign) not in csv and not {Decimal('777'),Decimal('888')} & amounts(csv)
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


@pytest.mark.asyncio
async def test_four_founder_populations_and_client_json_redaction(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    platform=uuid.UUID('00000000-0000-0000-0000-000000000001');a,b=uuid.uuid4(),uuid.uuid4()
    await seed(pool,platform,cost='1',baseline='10')
    await seed(pool,a,cost='1',baseline='3')
    await seed(pool,b,cost='2',baseline='4')
    every=await proof.savings_snapshot(None,END,founder=True)
    clients=await proof.savings_snapshot(None,END,founder=True,clients_only=True)
    assert Decimal(every['total']['saved'])==13 and Decimal(clients['total']['saved'])==4
    assert clients['tenant_id']=='clients'
    rows=await proof.savings_rows(None,END,clients_only=True,founder=True)
    assert rows['total']==clients['total'] and {r['tenant_id'] for r in rows['rows']}=={str(a),str(b)}
    for tenant,saved in [(a,2),(b,2),(platform,9)]:
        assert Decimal((await proof.savings_snapshot(tenant,END))['total']['saved'])==saved
    legacy=await proof.snapshot(None,end=END,clients_only=True)
    assert Decimal(str(legacy['all_tenant_total']['saved_usd']))==4
    assert {r['tenant_id'] for r in legacy['ledger']}=={str(a),str(b)}
    csv=(await proof.savings_export('csv',END,None,0,True)).body.decode()
    assert str(platform) not in csv and str(a) in csv and str(b) in csv
    key=secrets.token_urlsafe(32);monkeypatch.setenv('TANK_API_KEY',key)
    app=FastAPI();app.include_router(proof.client_router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        for suffix,query in [('',{}),('/rows',{'end':END.isoformat()})]:
            response=await client.get('/v1/client-savings'+suffix,params={'tenant_id':str(a),**query},headers={'x-tank-key':key})
            assert response.status_code==200
            text=response.text
            for forbidden in ['standard_name','top_name','selected_name','headline','standards','tops','comparison_status','compared_at','tenant_id','region','excluded_reason','expensive','cheap',str(b),str(platform)]:
                assert '"'+forbidden+'"' not in text
            assert Decimal(response.json()['total']['saved'])==2


@pytest.mark.asyncio
async def test_client_cache_reuses_revision_isolates_tenants_and_invalidates(database,monkeypatch):
    import asyncio
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    a,b=uuid.uuid4(),uuid.uuid4()
    await seed(pool,a);await seed(pool,b,cost='1',baseline='4')
    proof._CLIENT_CACHE.clear()
    original=proof.savings_snapshot;calls=[]
    async def counted(tenant,*args,**kwargs):
        calls.append(tenant)
        return await original(tenant,*args,**kwargs)
    monkeypatch.setattr(proof,'savings_snapshot',counted)
    reports=await asyncio.gather(*(proof.client_savings(a) for _ in range(4)))
    assert len(calls)==1 and all(r==reports[0] for r in reports)
    assert await proof.client_savings(a)==reports[0] and len(calls)==1
    other=await proof.client_savings(b)
    assert Decimal(other['total']['saved'])==3 and len(calls)==2
    await seed(pool,a)
    changed=await proof.client_savings(a)
    assert changed['revision']!=reports[0]['revision'] and changed['total']['work_count']==2 and len(calls)==3
    await pool.execute("UPDATE tank.ledger SET baseline_priced_at=now() WHERE tenant_id=$1",a)
    assert (await proof.client_savings(a))['revision']!=changed['revision'] and len(calls)==4
    clock=proof.time.monotonic
    monkeypatch.setattr(proof.time,'monotonic',lambda:clock()+301)
    await proof.client_savings(a)
    assert len(calls)==5


@pytest.mark.asyncio
async def test_client_copy_exports_five_graphs_job_pages_and_no_founder_detail(database,monkeypatch):
    import csv
    import io
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    tenant,foreign=uuid.uuid4(),uuid.uuid4()
    ids,job=await seed(pool,tenant,count=101,cost='.000001',baseline='.00000325')
    await seed(pool,foreign,cost='777',baseline='888')
    await seed(pool,tenant,cost='2',baseline='1')  # excluded comparison
    await pool.execute('UPDATE tank.tasks SET title=$2 WHERE id=$1',job,' =HYPERLINK("unsafe")')
    csv_text=(await proof.savings_client_copy('csv',END,tenant,1)).body.decode()
    pdf_bytes=(await proof.savings_client_copy('pdf',END,tenant,1)).body
    reader=PdfReader(BytesIO(pdf_bytes))
    pdf_text='\n'.join(p.extract_text() for p in reader.pages)
    sections=['Spent and would have cost','Saved to date','Saved this month','Done at no AI cost','Saved by team member']
    for text in [csv_text,pdf_text]:
        for section in sections: assert section in text
        for forbidden in ['margin','no billing data','tenant_id','baseline_model','expensive',str(tenant),str(foreign),str(ids[0]),'777','888','excluded_reason']:
            assert forbidden not in text
        import re
        assert not re.search(r'\bcheap\b',text)
        assert '0.00022725' in text and '0.00000325' in text
        assert '69.2% cheaper (3.25× cheaper) vs the standard model' in text
        assert 'same work assumed; quality comparison pending' in text
        assert 'the top model' in text
    assert "' =HYPERLINK" in csv_text
    rows=list(csv.reader(io.StringIO(csv_text)))
    from savings_export import JOB_HEADERS
    assert len(rows[rows.index(JOB_HEADERS)+1:])==1
    # PDF graphs are vector paths, not just headings and JSON dumps.
    streams=b'\n'.join(p.get_contents().get_data() for p in reader.pages)
    assert b' re f' in streams and b' m ' in streams and b'[4 3]' in streams
    for tenant_arg in ['',str(foreign),'all','clients']:
        app=FastAPI();app.include_router(proof.router)
        key=secrets.token_urlsafe(32)
        monkeypatch.setenv('TANK_API_KEY',key)
        monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','founder-copy')
        headers={'x-tank-key':key,'x-tervory-admin':'founder-copy'}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            url='/v1/proof/savings/client-copy/csv'
            params={'end':END.isoformat(),'tenant_id':tenant_arg}
            assert (await client.get(url,params=params)).status_code==404
            response=await client.get(url,params=params,headers=headers)
            assert response.status_code==(200 if tenant_arg==str(foreign) else 422)
            if response.status_code==200:
                assert Decimal('777') in amounts(response.text) and '0.00022725' not in response.text
    empty=(await proof.savings_client_copy('pdf',END,uuid.uuid4(),0)).body
    assert 'No comparable work yet' in ''.join(p.extract_text() for p in PdfReader(BytesIO(empty)).pages)


@pytest.mark.asyncio
async def test_revision_counter_commits_updates_deletes_tenant_moves_and_schema_reapply(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    a,b=uuid.uuid4(),uuid.uuid4()
    before=await proof.client_savings_revision(a)
    ids,job=await seed(pool,a)
    inserted=await proof.client_savings_revision(a)
    assert inserted!=before
    other=await proof.client_savings_revision(b)
    async with pool.acquire() as conn:
        tx=conn.transaction();await tx.start()
        await conn.execute("UPDATE tank.tasks SET title='Updated work' WHERE tenant_id=$1 AND id=$2",a,job)
        assert await proof.client_savings_revision(a)==inserted  # no uncommitted invalidation
        await tx.rollback()
    assert await proof.client_savings_revision(a)==inserted
    await pool.execute("UPDATE tank.tasks SET title='Updated work' WHERE tenant_id=$1 AND id=$2",a,job)
    edited=await proof.client_savings_revision(a)
    assert edited!=inserted and await proof.client_savings_revision(b)==other
    await pool.execute('UPDATE tank.ledger SET tenant_id=$2 WHERE tenant_id=$1',a,b)
    assert await proof.client_savings_revision(a)!=edited
    assert await proof.client_savings_revision(b)!=other
    await pool.execute("""INSERT INTO tank.shadow(ledger_id,tenant_id,task_type,primary_model,candidate_model,primary_content,candidate_content,primary_cost_usd,candidate_cost_usd,agreement,method)
        VALUES($1,$2,'fixture','sol','luna','ok','ok',.3,.1,1,'exact')""",ids[0],b)
    quality=await proof.client_savings_revision(b)
    await pool.execute('DELETE FROM tank.shadow WHERE tenant_id=$1',b)
    assert await proof.client_savings_revision(b)!=quality
    revision=await proof.client_savings_revision(b)
    await pool.execute((ROOT/'tank/schema.sql').read_text())
    assert await proof.client_savings_revision(b)==revision
    await pool.execute('DELETE FROM tank.ledger WHERE tenant_id=$1',b)
    assert await proof.client_savings_revision(b)!=revision
