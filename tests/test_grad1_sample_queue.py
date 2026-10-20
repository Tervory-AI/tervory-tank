"""Spot checks release only a proven source, never provisional sample answers."""
import pytest
import gold
from test_train1 import database as _database

database = _database

@pytest.mark.parametrize('statuses,expected', [
    (['checked'] * 9, 'pending'), (['checked'] * 9 + ['candidate'], 'pending'),
    (['checked'] * 9 + ['rejected'], 'passed'), (['checked'] * 10, 'passed'),
    (['checked'] * 8 + ['rejected'] * 2, 'review')])
def test_source_threshold(statuses, expected):
    assert gold.source_verdict(statuses) == expected

@pytest.mark.asyncio
@pytest.mark.parametrize('wrong', [0, 1, 2])
async def test_queue_and_release(database, wrong):
    pool, _ = database
    tenant = gold.PLATFORM_TENANT
    actor = gold.Reviewer('fixture reviewer', tenant, True)
    async with pool.acquire() as conn:
        for n in range(20):
            await conn.execute("""INSERT INTO tank.gold_examples
                (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,auto_label,label_source,public)
                VALUES ($1,'us-east','base.fixture','base',$2::jsonb,'{}','room_auto',$3,$3,true,'fixture source',true)""",
                tenant, gold.encoded({'n': n}), str(n))
        queue = await gold.sample_queue(conn, actor, 'base', 'base.fixture')
        assert len(queue) == 10
    for n, row in enumerate(queue):
        await gold.check(row['id'], gold.Verdict(action='wrong' if n < wrong else 'right',
                        correction={'corrected': True} if n < wrong else None), actor)
        if n < 9:
            async with pool.acquire() as conn:
                assert await conn.fetchval('SELECT count(*) FROM tank.training_pairs') == 0
    async with pool.acquire() as conn:
        count = await conn.fetchval('SELECT count(*) FROM tank.training_pairs')
        assert count == (20 - wrong if wrong < 2 else 0)
        assert not await conn.fetchval("SELECT 1 FROM tank.gold_examples WHERE auto_label AND status='candidate'")
        # Corrections remain human judgement examples, not source approvals.
        assert len(await gold.sample_queue(conn, actor, 'base', 'base.fixture')) == wrong
    result = await gold.summary(actor)
    assert result['skills'][0]['checked'] == (20 - wrong if wrong < 2 else 0)
