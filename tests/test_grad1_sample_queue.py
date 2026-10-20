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
                VALUES ($1,'us-east','base.fixture','base',$2::jsonb,'{}','room_auto',$3,$3,true,$3,true)""",
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

@pytest.mark.asyncio
async def test_later_intake_from_passed_source_is_approved_inside_savepoint(database, monkeypatch):
    import secrets
    from datetime import date
    import httpx
    import training
    pool, _ = database
    async with pool.acquire() as conn:
        for n in range(10):
            await conn.execute("""INSERT INTO tank.gold_examples
                (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,auto_label,label_source,public,status,auto_approved,checked_by)
                VALUES ($1,'us-east','base.find_site','base',$2::jsonb,'{}','room_auto',$3,$3,true,$3,true,'checked',true,'fixture reviewer')""",
                gold.PLATFORM_TENANT, gold.encoded({'n': n}), str(n))
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    monkeypatch.setenv('TANK_KEY_BASE', secrets.token_urlsafe(20))
    row = dict(skill_id='base.find_site', input={'n': 11}, expected={'ok': True}, label_source='new citation', public=True, region='us-east')
    client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(lambda req: httpx.Response(200,json=[row])), **kw))
    stats = await training.collect_room_gold(date(2026,10,20))
    assert stats['inserted'] == 1 and stats['rejected'] == 0
    async with pool.acquire() as conn:
        saved = await conn.fetchrow("SELECT * FROM tank.gold_examples WHERE label_source='new citation'")
        assert saved['auto_approved'] and saved['status'] == 'checked'
        assert await conn.fetchval('SELECT count(*) FROM tank.training_pairs WHERE gold_id=$1', saved['id']) == 1
