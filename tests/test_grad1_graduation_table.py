import pytest
import graduate
from test_train1 import database as _database

database = _database


def candidate(name, kind, score=.99, cost=0):
    return dict(candidate=name, kind=kind, heldout_score=score, heldout_n=20, cost_per_call=cost, cheaper=True)


def test_order_and_heldout_gate():
    policy = {'eval_threshold': .97}
    rows = [candidate('owned', 'owned'), candidate('cheap', 'model'), candidate('skill:base.fixture@1', 'code')]
    assert graduate.training_candidate(policy, rows, 99) is None
    assert graduate.training_candidate(policy, rows, 100)['kind'] == 'code'
    rows[-1]['heldout_score'] = .96
    assert graduate.training_candidate(policy, rows, 100)['kind'] == 'model'
    rows[1]['cheaper'] = False
    assert graduate.training_candidate(policy, rows, 100)['kind'] == 'owned'
    rows[0]['heldout_n'] = 0
    assert graduate.training_candidate(policy, rows, 100) is None

@pytest.mark.asyncio
async def test_empty_evidence_does_not_fabricate_costs_or_scores(database):
    pool, _ = database
    from gold import PLATFORM_TENANT
    async with pool.acquire() as conn:
        rows = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
    assert rows
    assert all(r['gold_count'] == 0 and r['heldout_score'] is None and r['candidate'] is None
               and r['current_cost'] is None and not r['can_promote'] for r in rows)

@pytest.mark.asyncio
async def test_evidence_and_costs_are_tenant_region_and_model_scoped(database):
    import uuid
    from gold import PLATFORM_TENANT
    pool, _ = database
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.policy(task_type,model,auto_promote) VALUES ('fixture.task','current',false)")
        await conn.execute("INSERT INTO tank.skills(id,version,agent,task_type,state) VALUES ('base.fixture','1','base',NULL,'approved')")
        await conn.execute("INSERT INTO tank.graduation_rank(task_type,candidate,kind) VALUES ('fixture.task','skill:base.fixture@1','code')")
        for tenant, region, model, cost in [(PLATFORM_TENANT,'us-east','current',.01),(PLATFORM_TENANT,'us-east','old',99),(uuid.uuid4(),'us-east','current',99),(PLATFORM_TENANT,'za','current',99)]:
            await conn.execute("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd) VALUES ($1,$2,'base','fixture.task',$3,$4)",tenant,region,model,cost)
        for n in range(100):
            await conn.execute("""INSERT INTO tank.gold_examples(tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status)
                VALUES ($1,'us-east','base.fixture','base','{}','{}','package',$2,$2,'checked')""", PLATFORM_TENANT,str(n))
        await conn.execute("INSERT INTO tank.gold_scores(tenant_id,region,skill_id,version,score,n,final_check) VALUES ($1,'us-east','base.fixture','1',.99,20,true)", PLATFORM_TENANT)
        rows = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
        row = next(r for r in rows if r['task_type'] == 'fixture.task')
        assert row['candidate'] == 'skill:base.fixture@1'
        assert row['heldout_score'] == .99 and row['current_cost'] == .01 and row['candidate_cost'] == 0
        assert not row['can_promote']  # Existing router blocks code names.
        await conn.execute("INSERT INTO tank.gold_scores(tenant_id,region,skill_id,version,score,n,final_check) VALUES ($1,'us-east','base.fixture','1',0,100,false)", PLATFORM_TENANT)
        again = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
        assert next(row for row in again if row['task_type'] == 'fixture.task')['heldout_score'] == .99
        other = await graduate.training_table(conn, uuid.uuid4(), 'us-east')
        assert all(r['candidate'] is None and r['current_cost'] is None for r in other)


@pytest.mark.asyncio
async def test_final_scores_only_run_holdout_rows(database, monkeypatch):
    from types import SimpleNamespace
    import gold
    import skala

    pool, runtime = database
    package = SimpleNamespace(id='base.fixture', version='1')
    runtime.get_package = lambda *args: package
    runtime.make_ctx = lambda *args, **kwargs: None
    seen = []

    async def run_skill(package, value, context):
        seen.append(value)
        return {'ok': True}

    monkeypatch.setattr(skala, 'run_skill', run_skill)
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.skills(id,version,agent,state) VALUES ('base.fixture','1','base','staging')")
        for held in (False, True):
            await conn.execute(
                """INSERT INTO tank.gold_examples
                (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status,holdout)
                VALUES ($1,'us-east','base.fixture','base',$2::jsonb,'{"ok":true}','package',$3,$3,'checked',$4)""",
                gold.PLATFORM_TENANT, gold.encoded({'held': held}), str(held), held)
    results = await gold.run_retests(final=True, skill='base.fixture', version='1')
    assert seen == [{'held': True}]
    assert results[0]['n'] == 1 and results[0]['score'] == 1
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT final_check FROM tank.gold_scores") is True


@pytest.mark.asyncio
async def test_training_table_cannot_write_policy(database):
    from gold import PLATFORM_TENANT

    pool, _ = database
    async with pool.acquire() as conn, conn.transaction(readonly=True):
        before = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
        assert await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id") == before


@pytest.mark.asyncio
async def test_model_needs_holdout_evidence_and_manual_promotion(database):
    from gold import PLATFORM_TENANT

    pool, _ = database
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO tank.policy(task_type,model,candidate_model,auto_promote)
            VALUES ('fixture.task','current','cheaper',false)""")
        await conn.execute(
            """INSERT INTO tank.graduation_rank(task_type,candidate,kind)
            VALUES ('fixture.task','cheaper','model')""")
        await conn.execute(
            """INSERT INTO tank.gold_examples
            (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,status)
            SELECT $1,'us-east','fixture.task','base','{}','{}','package',
            number::text,number::text,'checked' FROM generate_series(1,100) number""", PLATFORM_TENANT)
        await conn.execute(
            """INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd)
            VALUES ($1,'us-east','base','fixture.task','current',.02)""", PLATFORM_TENANT)
        await conn.execute(
            """INSERT INTO tank.gold_scores
            (tenant_id,region,skill_id,version,task_type,candidate_model,score,n,final_check,cost_per_call)
            VALUES ($1,'us-east','fixture.task','1','fixture.task','cheaper',1,100,false,.01)""",
            PLATFORM_TENANT)
        rows = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
        assert next(row for row in rows if row['task_type'] == 'fixture.task')['candidate'] is None
        await conn.execute(
            """INSERT INTO tank.gold_scores
            (tenant_id,region,skill_id,version,task_type,candidate_model,score,n,final_check,cost_per_call)
            VALUES ($1,'us-east','fixture.task','1','fixture.task','cheaper',.99,20,true,.01)""",
            PLATFORM_TENANT)
        await conn.execute(
            """INSERT INTO tank.gold_scores
            (tenant_id,region,skill_id,version,task_type,candidate_model,score,n,final_check,cost_per_call)
            VALUES ($1,'za','fixture.task','1','fixture.task','cheaper',.99,20,true,.01)""",
            PLATFORM_TENANT)
        rows = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
        row = next(row for row in rows if row['task_type'] == 'fixture.task')
        assert row['heldout_score'] == .99 and row['can_promote']
        assert await conn.fetchval("SELECT model FROM tank.policy WHERE task_type='fixture.task'") == 'current'
        await conn.execute("UPDATE tank.policy SET auto_promote=true WHERE task_type='fixture.task'")
        rows = await graduate.training_table(conn, PLATFORM_TENANT, 'us-east')
        assert not next(row for row in rows if row['task_type'] == 'fixture.task')['can_promote']


@pytest.mark.asyncio
async def test_promotion_endpoint_requires_verified_founder(monkeypatch):
    import secrets
    import httpx
    from types import SimpleNamespace

    key = secrets.token_urlsafe(24)
    monkeypatch.setenv('DATABASE_URL', 'postgresql://localhost/test')
    monkeypatch.setenv('LITELLM_MASTER_KEY', secrets.token_urlsafe(24))
    monkeypatch.setenv('TANK_API_KEY', key)
    import main

    monkeypatch.setattr(main, 'TANK_API_KEY', key)
    monkeypatch.setenv('TERVORY_ADMIN_USER_IDS', 'fixture-founder')
    monkeypatch.setattr(main, '_pool', None)
    called = []

    async def move(task, *, by, automatic):
        called.append((task, by, automatic))
        return SimpleNamespace(action='promote', policy={'model': 'cheap', 'previous_model': 'paid'})

    monkeypatch.setattr(main, '_move_task', move)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://test') as client:
        for user in ('', 'reviewer'):
            response = await client.post('/v1/graduation/base.fixture/promote',
                                         headers={'X-Tank-Key': key, 'X-Tervory-Admin': user},
                                         json={'by': 'fixture-founder'})
            assert response.status_code == 404
        assert called == []
        response = await client.post('/v1/graduation/base.fixture/promote',
                                     headers={'X-Tank-Key': key, 'X-Tervory-Admin': 'fixture-founder'},
                                     json={'by': 'fixture-founder'})
        assert response.status_code == 200
    assert called == [('base.fixture', 'fixture-founder', False)]
