"""CORE-2c: commit-time invalidation, client boundaries and Unicode exports."""
import asyncio
from contextlib import suppress
from io import BytesIO
from pathlib import Path
import secrets
import uuid

from fastapi import FastAPI, HTTPException
import httpx
from pypdf import PdfReader
import pytest
import yaml

import dashboards
import proof
from gold import PLATFORM_TENANT
from savings_defaults import STANDARDS
from test_core2_savings import END, prices, seed
from test_train1 import database as _database

database = _database
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('region',['config.yaml','config.za.yaml'])
def test_every_standard_model_is_on_the_roster(region):
    roster=yaml.safe_load((ROOT/'litellm'/region).read_text())
    names={row['model_name'] for row in roster['model_list']}
    assert set(STANDARDS.values())<=names


@pytest.mark.asyncio
async def test_deferred_counters_do_not_lock_writes_and_commit_in_tenant_order(database):
    pool,_=database
    a,b=sorted([uuid.uuid4(),uuid.uuid4()])
    jobs=[]
    for tenant in [a,b,b,a]:
        _,job=await seed(pool,tenant)
        jobs.append(job)
    before={t:await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',t) for t in [a,b]}
    constraints=await pool.fetch("""SELECT tgdeferrable,tginitdeferred FROM pg_trigger
        WHERE tgfoid='tank.bump_savings_revision()'::regprocedure AND NOT tgisinternal""")
    assert len(constraints)==4 and all(r['tgdeferrable'] and r['tginitdeferred'] for r in constraints)
    async with pool.acquire() as one,pool.acquire() as two:
        tx1,tx2=one.transaction(),two.transaction()
        await tx1.start();await tx2.start()
        try:
            async def edit(conn,job):
                await conn.execute("UPDATE tank.tasks SET title=title||' updated' WHERE id=$1",job)
            # Opposite tenant orders reproduce the old counter-row deadlock.
            await edit(one,jobs[0]);await edit(two,jobs[2])
            await asyncio.wait_for(asyncio.gather(edit(one,jobs[1]),edit(two,jobs[3])),3)
            for tenant in [a,b]:
                assert await one.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)==before[tenant]
            await asyncio.wait_for(asyncio.gather(tx1.commit(),tx2.commit()),3)
        finally:
            with suppress(Exception): await tx1.rollback()
            with suppress(Exception): await tx2.rollback()
    for tenant in [a,b]:
        assert await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)==before[tenant]+2
    await pool.execute((ROOT/'tank/schema.sql').read_text())
    assert await pool.fetchval("SELECT count(*) FROM pg_trigger WHERE tgfoid='tank.bump_savings_revision()'::regprocedure AND NOT tgisinternal")==4


@pytest.mark.asyncio
async def test_counter_coalesces_rows_and_rollback_never_invalidates(database):
    pool,_=database
    tenant=uuid.uuid4()
    _,job=await seed(pool,tenant)
    before=await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)
    async with pool.acquire() as conn:
        tx=conn.transaction();await tx.start()
        await conn.execute("UPDATE tank.tasks SET title='Discard this' WHERE tenant_id=$1",tenant)
        await tx.rollback()
    assert await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)==before
    async with pool.acquire() as conn,conn.transaction():
        for _ in range(3):
            await conn.execute("UPDATE tank.tasks SET title=title||'.' WHERE tenant_id=$1 AND id=$2",tenant,job)
        await conn.execute('UPDATE tank.ledger SET latency_ms=1 WHERE tenant_id=$1',tenant)
        assert await conn.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)==before
    assert await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)==before+1


@pytest.mark.asyncio
async def test_price_changes_invalidate_only_affected_tenants_after_commit(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    a,b=uuid.uuid4(),uuid.uuid4()
    await seed(pool,a);await seed(pool,b,model='other',baseline_model='other')
    proof._CLIENT_CACHE.clear()
    initial=await proof.client_savings(a)
    other=await proof.client_savings_revision(b)
    async with pool.acquire() as conn,conn.transaction():
        await conn.execute("UPDATE tank.proof_prices SET family='different' WHERE model='expensive'")
        assert await proof.client_savings_revision(a)=={'revision':initial['revision']}
    updated=await proof.client_savings(a)
    assert updated['revision']!=initial['revision'] and updated['total']['work_count']==0
    assert await proof.client_savings_revision(b)==other
    before=await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',a)
    async with pool.acquire() as conn,conn.transaction():
        await conn.execute("UPDATE tank.proof_prices SET active=false WHERE model='expensive'")
        await conn.execute("UPDATE tank.proof_prices SET input_usd=.02 WHERE model='expensive'")
    assert await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',a)==before+1
    assert await proof.client_savings_revision(b)==other
    unchanged=await proof.client_savings_revision(a)
    await pool.execute("UPDATE tank.proof_prices SET active=false,updated_at=now() WHERE model='expensive'")
    assert await proof.client_savings_revision(a)==unchanged
    await pool.execute("DELETE FROM tank.proof_prices WHERE model='expensive'")
    assert await proof.client_savings_revision(a)!=unchanged
    deleted=await proof.client_savings_revision(a)
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('expensive','same',.01,.01)")
    assert await proof.client_savings_revision(a)!=deleted


@pytest.mark.asyncio
async def test_price_change_finds_every_stored_model_reference(database):
    pool,_=database
    await prices(pool)
    tenants=[]
    for field in ['model','standard_model','top_model','baseline_model']:
        tenant=uuid.uuid4();tenants.append(tenant)
        ids,_=await seed(pool,tenant)
        # The column is from this fixed list, never request input.
        await pool.execute(f"UPDATE tank.ledger SET {field}='target' WHERE tenant_id=$1 AND id=$2",tenant,ids[0])
    untouched=uuid.uuid4();await seed(pool,untouched)
    before={t:await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',t) for t in [*tenants,untouched]}
    await pool.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('target','same',.01,.01)")
    for tenant in tenants:
        assert await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',tenant)==before[tenant]+1
    assert await pool.fetchval('SELECT revision FROM tank.savings_revisions WHERE tenant_id=$1',untouched)==before[untouched]


@pytest.mark.asyncio
async def test_platform_is_refused_before_client_reads_or_exports(monkeypatch):
    key=secrets.token_urlsafe(32)
    monkeypatch.setenv('TANK_API_KEY',key);monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','fixture-founder')
    def unavailable(): raise AssertionError('A platform client request reached the database')
    monkeypatch.setattr(proof,'runtime',unavailable);monkeypatch.setattr(dashboards,'db',unavailable)
    app=FastAPI();app.include_router(proof.router);app.include_router(proof.client_router);app.include_router(dashboards.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        paths=['/v1/client-savings','/v1/client-savings/rows','/v1/client-savings/revision','/v1/dashboards/client',
               '/v1/proof/savings/client-copy/csv','/v1/proof/savings/client-copy/pdf']
        for path in paths:
            response=await client.get(path,params={'tenant_id':str(PLATFORM_TENANT),'end':END.isoformat()},
                headers={'x-tank-key':key,'x-tervory-admin':'fixture-founder'})
            assert response.status_code==404
    for read in [proof.client_savings,proof.client_savings_revision]:
        with pytest.raises(HTTPException) as exc: await read(PLATFORM_TENANT)
        assert exc.value.status_code==404
    # Founder evidence still allows the platform scope.
    async def founder(tenant,*args,**kwargs):
        assert tenant==PLATFORM_TENANT
        return {'founder':True}
    monkeypatch.setattr(proof,'savings_snapshot',founder)
    assert await proof.founder_savings(PLATFORM_TENANT)=={'founder':True}


@pytest.mark.asyncio
async def test_unicode_job_titles_survive_client_and_founder_pdfs(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    tenant=uuid.uuid4();_,job=await seed(pool,tenant)
    title='Café Αθήνα Москва 中文工作 日本語 한국어'
    await pool.execute('UPDATE tank.tasks SET title=$2 WHERE id=$1 AND tenant_id=$3',job,title,tenant)
    for export in [proof.savings_client_copy,proof.savings_export]:
        response=await export('pdf',END,tenant,0)
        reader=PdfReader(BytesIO(response.body))
        text='\n'.join(p.extract_text() for p in reader.pages)
        for word in title.split(): assert word in text
        assert '?' not in text and '\\u4e2d' not in text
        assert "Some characters can't be shown" not in text
        fonts=[font.get_object() for page in reader.pages for font in page['/Resources']['/Font'].values()]
        assert any('/FontFile2' in font.get('/FontDescriptor',{}) for font in fonts)
        assert any('/ToUnicode' in font for font in fonts)
        # Subsetting keeps documents small despite the broad bundled fonts.
        assert len(response.body)<200000


@pytest.mark.asyncio
async def test_unchanged_price_sync_does_not_invalidate_clients(database,monkeypatch):
    import bench
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    tenant=uuid.uuid4();await seed(pool,tenant)
    before=await proof.client_savings_revision(tenant)
    book={r['model']:{'family':r['family'],'input':r['input_usd'],'output':r['output_usd']}
          for r in await pool.fetch('SELECT * FROM tank.proof_prices')}
    async with pool.acquire() as conn:
        await bench.sync_prices(conn,book)
    assert await proof.client_savings_revision(tenant)==before
    del book['expensive']
    async with pool.acquire() as conn:
        await bench.sync_prices(conn,book)
    assert await proof.client_savings_revision(tenant)!=before
    assert await pool.fetchval("SELECT active FROM tank.proof_prices WHERE model='expensive'") is False


@pytest.mark.asyncio
@pytest.mark.parametrize('title,expected',[('Launch plan 🚀','Launch plan �'),('Launch خطة العمل','Launch ��� �����')])
async def test_unsupported_titles_download_with_notice_and_original_csv(database,monkeypatch,title,expected):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await prices(pool)
    tenant=uuid.uuid4();_,job=await seed(pool,tenant)
    await pool.execute('UPDATE tank.tasks SET title=$2 WHERE id=$1 AND tenant_id=$3',job,title,tenant)
    notice="Some characters can't be shown in the PDF; the CSV has the full text"
    for export in [proof.savings_client_copy,proof.savings_export]:
        response=await export('pdf',END,tenant,0,client_name='Café Client')
        reader=PdfReader(BytesIO(response.body))
        text='\n'.join(page.extract_text() for page in reader.pages)
        assert expected in " ".join(text.split())
        assert text.count(notice)==1
        assert reader.metadata.title=='Café Client'
        assert reader.metadata.author=='Tervory'
        csv=await export('csv',END,tenant,0)
        assert title in csv.body.decode()


@pytest.mark.asyncio
async def test_index_is_built_online_and_reapplies(database):
    from savings_indexes import ensure_index
    pool,_=database
    assert not await pool.fetchval("SELECT to_regclass('tank.ledger_savings_model_references')")
    # CONCURRENTLY would fail if wrapped in the schema transaction.
    await ensure_index(pool)
    await ensure_index(pool)
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT indisvalid FROM pg_index WHERE indexrelid='tank.ledger_savings_model_references'::regclass")
        await conn.execute((ROOT/'tank/schema.sql').read_text())
    await ensure_index(pool)
