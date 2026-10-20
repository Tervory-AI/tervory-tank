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
                VALUES ($1,'us-east','base.find_site','base',$2::jsonb,'{}','room_auto',$3,$3,true,'trusted source',true,'checked',true,'fixture reviewer')""",
                gold.PLATFORM_TENANT, gold.encoded({'n': n}), str(n))
    monkeypatch.setattr(training, 'ROOMS', ('base',))
    monkeypatch.setenv('TANK_KEY_BASE', secrets.token_urlsafe(20))
    row = dict(skill_id='base.find_site', input={'n': 11}, expected={'ok': True}, label_source='trusted source', public=True, region='us-east')
    monkeypatch.setattr(training, 'is_holdout', lambda *args: False)
    new_source = row | {'input': {'n': 12}, 'label_source': 'new source'}
    client = httpx.AsyncClient
    monkeypatch.setattr(training.httpx, 'AsyncClient', lambda **kw: client(transport=httpx.MockTransport(lambda req: httpx.Response(200,json=[row, new_source])), **kw))
    stats = await training.collect_room_gold(date(2026,10,20))
    assert stats['inserted'] == 2 and stats['rejected'] == 0
    async with pool.acquire() as conn:
        saved = await conn.fetchrow("SELECT * FROM tank.gold_examples WHERE label_source='trusted source' AND input->>'n'='11'")
        assert saved['auto_approved'] and saved['status'] == 'checked'
        assert await conn.fetchval('SELECT count(*) FROM tank.training_pairs WHERE gold_id=$1', saved['id']) == 1

        fresh = await conn.fetchrow("SELECT * FROM tank.gold_examples WHERE label_source='new source'")
        assert fresh['status'] == 'candidate' and not fresh['auto_approved']
        assert not await conn.fetchval('SELECT 1 FROM tank.training_pairs WHERE gold_id=$1', fresh['id'])
        queued = await gold.sample_queue(conn, gold.Reviewer('reviewer', gold.PLATFORM_TENANT, True), 'base', 'base.find_site')
        assert [r['id'] for r in queued] == [fresh['id']]


@pytest.mark.asyncio
async def test_two_sources_on_one_skill_need_their_own_ten_checks(database):
    pool, _ = database
    actor = gold.Reviewer('source reviewer', gold.PLATFORM_TENANT, True)

    async def add_source(source):
        async with pool.acquire() as conn:
            for n in range(20):
                value = {'source': source, 'n': n}
                await conn.execute("""INSERT INTO tank.gold_examples
                    (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,auto_label,label_source,public)
                    VALUES ($1,'us-east','base.fixture','base',$2::jsonb,'{}','room_auto',$3,$3,true,$4,true)""",
                    actor.tenant, gold.encoded(value), gold.input_hash(value), source)

    async def approve_sample(source):
        async with pool.acquire() as conn:
            queue = await gold.sample_queue(conn, actor, 'base', 'base.fixture')
            assert len(queue) == 10
            assert {r['label_source'] for r in queue} == {source}
        for row in queue[:9]:
            await gold.check(row['id'], gold.Verdict(action='right'), actor)
        async with pool.acquire() as conn:
            assert not await conn.fetchval("SELECT 1 FROM tank.gold_examples WHERE label_source=$1 AND auto_approved", source)
            assert not await conn.fetchval("""SELECT 1 FROM tank.training_pairs p
                JOIN tank.gold_examples g ON g.id=p.gold_id WHERE g.label_source=$1""", source)
        await gold.check(queue[9]['id'], gold.Verdict(action='wrong', correction={'fixed': True}), actor)
        async with pool.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tank.gold_examples WHERE label_source=$1 AND auto_approved", source) == 19

    await add_source('source A')
    await approve_sample('source A')
    await add_source('source B')
    # Re-settling a trusted source cannot release another source's rows.
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM tank.gold_examples WHERE label_source='source A' LIMIT 1")
        assert await gold.settle_auto_source(conn, dict(row)) == 'passed'
        fresh = await conn.fetch("SELECT * FROM tank.gold_examples WHERE label_source='source B'")
        assert len(fresh) == 20
        assert all(r['status'] == 'candidate' and not r['auto_approved'] for r in fresh)
        # A row outside B's own first ten cannot be reviewed directly.
        outside = await conn.fetchval("SELECT id FROM tank.gold_examples WHERE label_source='source B' ORDER BY created_at,id OFFSET 10 LIMIT 1")
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:
        await gold.check(outside, gold.Verdict(action='right'), actor)
    assert error.value.status_code == 409
    # A's human correction is also queued, but does not consume B's ten slots.
    async with pool.acquire() as conn:
        corrections = await conn.fetch("SELECT id FROM tank.gold_examples WHERE source='correction' AND status='candidate'")
    for correction in corrections:
        await gold.check(correction['id'], gold.Verdict(action='right'), actor)
    await approve_sample('source B')


@pytest.mark.asyncio
async def test_failed_source_cannot_borrow_trust_and_holdouts_never_train(database):
    import training
    pool, _ = database
    actor = gold.Reviewer('source reviewer', gold.PLATFORM_TENANT, True)
    async with pool.acquire() as conn:
        for source in ('trusted', 'failed', 'unchecked'):
            for number in range(20):
                value = {'source': source, 'number': number}
                await conn.execute(
                    """INSERT INTO tank.gold_examples
                    (tenant_id,region,skill_id,agent,input,expected,source,source_ref,input_hash,
                     auto_label,label_source,public,holdout)
                    VALUES ($1,'us-east','base.fixture','base',$2::jsonb,'{}','room_auto',
                            $3,$3,true,$4,true,$5)""",
                    actor.tenant, gold.encoded(value), gold.input_hash(value), source, number in (0, 19),
                )
    for source in ('trusted', 'failed'):
        async with pool.acquire() as conn:
            sample = await conn.fetch(
                """SELECT * FROM tank.gold_examples WHERE label_source=$1
                ORDER BY created_at,id LIMIT 10""", source,
            )
        for index, row in enumerate(sample):
            wrong = source == 'failed' and index >= 8
            await gold.check(row['id'], gold.Verdict(
                action='wrong' if wrong else 'right',
                correction={'corrected': True} if wrong else None,
            ), actor)
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tank.gold_examples WHERE auto_label")
        for row in rows:
            await training.pair_from_gold(conn, dict(row))
        assert await conn.fetchval(
            """SELECT count(*) FROM tank.training_pairs p JOIN tank.gold_examples g ON g.id=p.gold_id
            WHERE g.label_source='trusted'"""
        ) == 18
        assert not await conn.fetchval(
            """SELECT 1 FROM tank.training_pairs p JOIN tank.gold_examples g ON g.id=p.gold_id
            WHERE g.label_source IN ('failed','unchecked') OR g.holdout OR p.holdout"""
        )
        assert not await conn.fetchval(
            "SELECT 1 FROM tank.gold_examples WHERE label_source='failed' AND auto_approved"
        )
        assert await conn.fetchval(
            "SELECT count(*) FROM tank.gold_examples WHERE label_source='failed' AND note='Source needs code review'"
        ) == 10
        assert await conn.fetchval(
            "SELECT count(*) FROM tank.gold_examples WHERE label_source='unchecked' AND status='candidate'"
        ) == 20


@pytest.mark.asyncio
@pytest.mark.parametrize('holdout,approved', [(True, True), (True, False), (False, False)])
async def test_training_gate_requires_source_approval_and_excludes_holdouts(holdout, approved):
    import training

    class NoWrites:
        async def execute(self, *args):
            pytest.fail('Untrusted or held-out gold must not enter training')

    await training.pair_from_gold(NoWrites(), {
        'holdout': holdout, 'auto_label': True, 'auto_approved': approved,
    })
