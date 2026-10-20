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
        other = await graduate.training_table(conn, uuid.uuid4(), 'us-east')
        assert all(r['candidate'] is None and r['current_cost'] is None for r in other)
