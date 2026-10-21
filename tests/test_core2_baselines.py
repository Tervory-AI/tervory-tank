import asyncio
from datetime import datetime
from pathlib import Path
from decimal import Decimal
from io import BytesIO
import uuid

from fastapi import FastAPI
import httpx
from pypdf import PdfReader
import pytest

import proof
from test_train1 import database as _database

database = _database


async def fixture(pool, count=1):
    tenant=uuid.UUID('11111111-1111-1111-1111-111111111111')
    await pool.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd)
        VALUES('luna','openai/gpt',.001,.001),('sol','openai/gpt',.003,.003),('astra','openai/gpt',.01,.01),
        ('sonnet','anthropic/claude',.003,.003)""")
    await pool.execute("INSERT INTO tank.policy(task_type,model) VALUES('baseline.fixture','luna')")
    job=await pool.fetchval("""INSERT INTO tank.tasks(tenant_id,agent,task_type,title,input,status,finished_at)
        VALUES($1,'base','baseline.fixture','A completed list','{}','done',now()-interval '1 minute') RETURNING id""",tenant)
    await pool.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,task_id,model,tokens_in,cost_usd)
        SELECT $1,'base','baseline.fixture',$2,'luna',100,.1 FROM generate_series(1,$3::int)""",tenant,job,count)
    return tenant


@pytest.mark.asyncio
async def test_provider_defaults_and_no_expensive_fallback(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    for family,expected in [('openai/gpt','sol'),('anthropic/claude','sonnet'),('gemini/gemini','argon'),
                            ('xai/grok','grok-top'),('moonshot/kimi','kimi'),('deepseek/deepseek','deepseek-pro')]:
        assert await pool.fetchval('SELECT tank.standard_model_for($1)',family)==expected
    assert await pool.fetchval("SELECT tank.standard_model_for('unknown/thing')") is None
    tenant=await fixture(pool)
    row=await pool.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1',tenant)
    assert row['standard_model']==row['baseline_model']=='sol'
    assert row['standard_cost_usd']==Decimal('.3') and row['top_cost_usd']==Decimal('1') and row['top_model']=='astra'
    report=await proof.savings_snapshot(tenant)
    assert Decimal(report['total']['times_cheaper'])==3 and Decimal(report['total']['percent_cheaper'])>66
    assert report['total']['quality_note']=='same work assumed; quality comparison pending'
    assert 'standard model (sol)' in report['total']['headline'] and 'top model (astra)' in report['total']['headline']
    await pool.execute("DELETE FROM tank.proof_prices WHERE model='sol'")
    await pool.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,cost_usd)
        VALUES($1,'base','baseline.fixture','luna',100,.1)""",tenant)
    unknown=await pool.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1 ORDER BY ts DESC LIMIT 1',tenant)
    assert unknown['standard_model']=='sol' and unknown['standard_cost_usd'] is None
    assert unknown['top_model']=='astra' and unknown['baseline_cost_usd'] is None


@pytest.mark.asyncio
async def test_reprice_batches_audit_restart_history_and_override_not_headline(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    tenant=await fixture(pool,5001)
    before=await proof.savings_snapshot(tenant)
    cutoff=datetime.fromisoformat(before['as_of'])
    old_proof=await proof.snapshot(tenant,end=cutoff)
    await pool.execute("UPDATE tank.proof_prices SET input_usd=.004,output_usd=.004 WHERE model='sol'")
    result=await proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model='astra'),'founder-fixture')
    assert result['changed']
    assert await proof.baseline_batch()==5000
    assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE baseline_status='re-priced'")==5000
    assert await proof.baseline_batch()==1  # resume remaining batch, using durable queue
    await proof.baseline_batch()
    audit=await pool.fetchrow("SELECT * FROM tank.baseline_changes WHERE task_type='baseline.fixture'")
    assert audit['by_user']=='founder-fixture' and audit['old_model']=='sol' and audit['new_model']=='astra'
    assert audit['rows_updated']==5001 and audit['status']=='complete'
    assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE baseline_status='re-priced' AND baseline_priced_at>$1",cutoff)==5001
    assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE baseline_model='astra' AND standard_model='sol'")==5001
    after=await proof.savings_snapshot(tenant)
    assert Decimal(after['total']['would_have_cost'])==Decimal('.4')*5001
    assert after['total']['standards']==['sol'] and after['total']['tops']==['astra']
    # Existing report totals/rows remain exact after repricing, not a changing mixture.
    frozen=await proof.savings_snapshot(tenant,cutoff)
    assert frozen['total']==before['total']
    frozen_proof=await proof.snapshot(tenant,end=cutoff)
    assert frozen_proof['tasks']==old_proof['tasks'] and frozen_proof['ledger']==old_proof['ledger']
    rows=await proof.savings_rows(tenant,cutoff)
    assert rows['total']==before['total'] and all(Decimal(r['would_have_cost'])==Decimal('.3') for r in rows['rows'])
    assert (await proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model='astra'),'founder-fixture'))['changed'] is False
    await proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model=None),'founder-fixture')
    while await proof.baseline_batch():
        pass
    assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE baseline_model='sol'")==5001


@pytest.mark.asyncio
async def test_founder_gate_quality_note_exports_and_cross_family_refusal(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    tenant=await fixture(pool)
    import secrets
    key=secrets.token_urlsafe(32)
    monkeypatch.setenv('TANK_API_KEY',key);monkeypatch.setenv('TERVORY_ADMIN_USER_IDS','founder-fixture')
    app=FastAPI();app.include_router(proof.router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        for method in ['GET','POST']:
            for headers in [{},{'x-tank-key':key},{'x-tank-key':key,'x-tervory-admin':'reviewer'}]:
                assert (await client.request(method,'/v1/proof/baselines',headers=headers,json={'task':'baseline.fixture','model':'astra'})).status_code==404
        headers={'x-tank-key':key,'x-tervory-admin':'founder-fixture'}
        assert (await client.get('/v1/proof/baselines',headers=headers)).status_code==200
        assert (await client.post('/v1/proof/baselines',headers=headers,json={'task':'baseline.fixture','model':'sonnet'})).status_code==422
    before=await proof.savings_snapshot(tenant)
    assert before['total']['quality_pending']
    end=datetime.fromisoformat(before['as_of'])
    csv=(await proof.savings_export('csv',end,tenant,0)).body.decode()
    pdf=''.join(p.extract_text() for p in PdfReader(BytesIO((await proof.savings_export('pdf',end,tenant,0)).body)).pages)
    for text in [csv,pdf]:
        assert 'standard model (sol)' in text and 'top model (astra)' in text
        assert '3.00× cheaper' in text and 'same work assumed; quality comparison pending' in text
    row=await pool.fetchrow('SELECT * FROM tank.ledger WHERE tenant_id=$1',tenant)
    await pool.execute("""INSERT INTO tank.shadow(ledger_id,tenant_id,task_type,primary_model,candidate_model,primary_content,candidate_content,primary_cost_usd,candidate_cost_usd,agreement,method)
        VALUES($1,$2,'baseline.fixture','sol','luna','ok','ok',.3,.1,1,'exact')""",row['id'],tenant)
    assert (await proof.savings_snapshot(tenant))['total']['quality_pending'] is False
    # A different tenant's task does not inherit private evidence.
    other=uuid.uuid4()
    await pool.execute("UPDATE tank.shadow SET tenant_id=$1",other)
    assert (await proof.savings_snapshot(tenant))['total']['quality_pending'] is True


@pytest.mark.asyncio
async def test_superseded_requests_and_zero_cost_ratios(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    await fixture(pool)
    await proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model='astra'),'founder-fixture')
    await proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model='luna'),'founder-fixture')
    await proof.baseline_batch()
    assert await pool.fetchval("SELECT status FROM tank.baseline_changes ORDER BY revision LIMIT 1")=='superseded'
    while await proof.baseline_batch(): pass
    assert await pool.fetchval("SELECT baseline_model FROM tank.ledger LIMIT 1")=='luna'
    assert proof.comparison_numbers(0,0)=={'percent_cheaper':None,'times_cheaper':None}
    assert proof.comparison_numbers(0,1)=={'percent_cheaper':Decimal(100),'times_cheaper':None}


@pytest.mark.asyncio
async def test_schema_repeat_region_boundary_and_worker_lifespan(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    tenant=await fixture(pool)
    foreign=await pool.fetchval("""INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,tokens_in,cost_usd)
        VALUES($1,'za','base','baseline.fixture','luna',100,.1) RETURNING id""",tenant)
    await proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model='astra'),'founder-fixture')
    for _ in range(2):
        await pool.execute((Path(__file__).resolve().parents[1]/'tank/schema.sql').read_text())
    assert await pool.fetchval("SELECT override_model FROM tank.baseline_settings WHERE task_type='baseline.fixture'")=='astra'
    assert await pool.fetchval("SELECT count(*) FROM tank.baseline_changes WHERE task_type='baseline.fixture'")==1
    app=FastAPI();app.include_router(proof.router)
    async with app.router.lifespan_context(app):
        for _ in range(30):
            if await pool.fetchval("SELECT status FROM tank.baseline_changes WHERE task_type='baseline.fixture'")=='complete':
                break
            await asyncio.sleep(.2)
        else:
            pytest.fail('The mounted router did not run its repricing worker')
    assert await pool.fetchval("SELECT rows_updated FROM tank.baseline_changes WHERE task_type='baseline.fixture'")==1
    assert await pool.fetchval('SELECT baseline_model FROM tank.ledger WHERE id=$1',foreign)=='sol'


@pytest.mark.asyncio
async def test_override_waits_for_inflight_receipt_before_queue_can_complete(database,monkeypatch):
    pool,rt=database;monkeypatch.setattr(proof,'runtime',lambda:rt)
    tenant=await fixture(pool)
    async with pool.acquire() as conn:
        tx=conn.transaction();await tx.start()
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,cost_usd)
            VALUES($1,'base','baseline.fixture','luna',100,.1)""",tenant)
        changing=asyncio.create_task(proof.change_baseline(proof.BaselineChoice(task='baseline.fixture',model='astra'),'founder-fixture'))
        try:
            await asyncio.sleep(.05)
            assert not changing.done()
        finally:
            await tx.commit()
        await changing
    while await proof.baseline_batch(): pass
    assert await pool.fetchval("SELECT rows_updated FROM tank.baseline_changes WHERE task_type='baseline.fixture'")==2
    assert await pool.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND baseline_model='astra'",tenant)==2


def test_json_amounts_never_use_scientific_notation():
    # Graph integer sums and dollar labels consume fixed decimal strings, including
    # a day containing only free work and the smallest stored token comparison.
    assert proof.savings_encoded({'zero':Decimal('0E-8'),'small':Decimal('1E-8')}) == {
        'zero':'0.00000000','small':'0.00000001'}
