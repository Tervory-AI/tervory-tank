from uuid import uuid4

import pytest
import tervor_dataset as dataset
from test_train1 import database as _database

database = _database


def example(tenant, **changes):
    return dataset.row(**(dict(tenant=tenant, product='base', kind='public', source='public corpus',
        provider='any provider', licence='counsel pending', source_ref='row-1', task_type='base.extract',
        input={'text': 'fixture'}, output={'answer': 'fixture'}) | changes))


def test_all_sources_and_providers_retained_with_reproducible_hashes():
    tenant = uuid4()
    rows = [example(tenant, kind=kind, provider=provider, licence=licence, source_ref=kind)
            for kind, provider, licence in zip(sorted(dataset.KINDS),
            ['OpenAI', 'Anthropic', 'Google', 'public publisher'],
            ['unknown', 'restricted', 'Apache-2.0', 'counsel pending'], strict=True)]
    result = dataset.build(tenant, 'base', rows)
    assert result['count'] == 4
    assert result['source_counts'] == dict.fromkeys(dataset.KINDS, 1)
    assert dataset.build(tenant, 'base', reversed(rows)) == result
    assert dataset.build(tenant, 'base', rows + rows) == result
    assert {r['provider'] for r in result['rows']} == {r['provider'] for r in rows}
    assert {r['licence'] for r in result['rows']} == {r['licence'] for r in rows}


@pytest.mark.parametrize('change', [{'provider': ''}, {'licence': ''}, {'source': ''},
    {'source_ref': ''}, {'kind': 'unchecked'}, {'holdout': True}, {'task_type': 'tiger.read'},
    {'input': {'large': 'x' * dataset.MAX_ROW_BYTES}}])
def test_rejects_invalid_rows(change):
    with pytest.raises(ValueError):
        example(uuid4(), **change)


def test_tenant_product_and_gold_boundaries():
    tenant = uuid4()
    row = example(tenant)
    with pytest.raises(ValueError, match='tenant or product'):
        dataset.build(uuid4(), 'base', [row])
    with pytest.raises(ValueError, match='tenant or product'):
        dataset.build(tenant, 'tiger', [row])
    with pytest.raises(ValueError, match='Gold input'):
        dataset.build(tenant, 'base', [row], gold_inputs=[row['input']])
    assert dataset.build(tenant, 'base', [])['count'] == 0


@pytest.mark.asyncio
async def test_shadow_source_joins_receipts_and_transcripts_under_same_tenant(database):
    import json
    pool, _ = database
    tenant, other = uuid4(), uuid4()
    async with pool.acquire() as conn:
        for scope in (tenant, other):
            receipt = await conn.fetchval('''INSERT INTO tank.ledger
                (tenant_id,region,agent,task_type,model,priority,cost_usd,outcome)
                VALUES ($1,'us-east','base','base.extract','teacher','batch',0,'delivered') RETURNING id''', scope)
            await conn.execute('''INSERT INTO tank.transcripts(ledger_id,tenant_id,messages,content)
                VALUES ($1,$2,$3::jsonb,'checked answer')''', receipt, scope,
                json.dumps([{'role': 'user', 'content': 'fixture input'}]))
            await conn.execute('''INSERT INTO tank.shadow
                (ledger_id,tenant_id,task_type,primary_model,candidate_model,primary_content,candidate_content,agreement,method)
                VALUES ($1,$2,'base.extract','teacher','candidate','checked answer','checked answer',1,'exact')''', receipt, scope)
        result = await dataset.collect(conn, tenant, 'base', 'us-east')
        assert result['count'] == 1
        assert result['source_counts']['shadow'] == 1
        assert result['rows'][0]['provider'] == 'teacher'
        assert result['rows'][0]['tenant_id'] == str(tenant)


@pytest.mark.asyncio
async def test_collects_real_scoped_training_and_memory_records(database):
    import json
    import training
    pool, _ = database
    tenant, other = uuid4(), uuid4()
    async with pool.acquire() as conn:
        for scope in (tenant, other):
            await training.save_pair(conn, tenant=scope, agent='base', task='base.extract',
                value={'text': 'teacher'}, output={'answer': 'checked'}, approved_by='fixture',
                source='teacher', ref='fixture', teacher_model='any-provider/model')
            await conn.execute('''INSERT INTO agent_tank.memory_records(id,tenant_id,claim,kind,meta)
                VALUES ($1,$2,'corrected answer','correction',$3::jsonb)''', uuid4(), scope,
                json.dumps({'product': 'base', 'task_type': 'base.extract', 'input': {'text': 'memory'}}))
        result = await dataset.collect(conn, tenant, 'base', 'us-east', public_rows=[example(tenant)])
        assert result['count'] == 3
        assert result['source_counts'] == {'correction': 1, 'public': 1, 'shadow': 0, 'teacher': 1}
        assert {r['tenant_id'] for r in result['rows']} == {str(tenant)}
        assert await dataset.collect(conn, tenant, 'tiger', 'us-east') == dataset.build(tenant, 'tiger', [])
