"""Offline real route/SQL/Qdrant tests. Only the encoder and paid gateway are stubbed."""
import asyncio
import json
from pathlib import Path
import uuid

import httpx
import pytest
import pytest_asyncio
from qdrant_client import AsyncQdrantClient

import proof
import semantic_cache as cache
from semantic_encoder import DIMENSIONS, ENCODER_ID
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder, policy, request  # noqa: F401


class EncoderStub:
    def __init__(self):
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        # Deliberately maximally similar: hard guards must defeat the vector.
        return [1.0] + [0.0] * (DIMENSIONS - 1)


async def drain(b):
    while b.tank._background:
        await asyncio.gather(*list(b.tank._background))


@pytest_asyncio.fixture
async def semantic(ladder, monkeypatch):
    b = ladder
    b.encoder = EncoderStub()
    store = cache.VectorIndex(AsyncQdrantClient(location=":memory:"))
    monkeypatch.setattr(cache, '_encoder', b.encoder)
    monkeypatch.setattr(cache, '_index', store)
    monkeypatch.setattr(proof, 'runtime', lambda: b.tank)
    monkeypatch.setenv('TANK_SHADOW_BUDGET_USD', '1')
    b.store = store
    for tenant in b.tenants:
        await policy(b, tenant, model='haiku', rung=1, cache_scope='tenant', semantic_cache=False,
                     candidate_model=None, shadow_rate=0, system_prompt='Summarize the requested topic.')
    try:
        yield b
    finally:
        await drain(b)
        await store.client.close()


async def run(b, text, *, tenant=None, **kwargs):
    result = await b.tank.run_route(request(b, tenant or b.tenants[0], text=text, **kwargs))
    await drain(b)
    return result


async def observation(b, result, tenant=None):
    async with b.pool.acquire() as conn:
        return await conn.fetchrow('SELECT * FROM tank.semantic_observations WHERE tenant_id=$1 AND ledger_id=$2',
                                   tenant or b.tenants[0], result.ledger_id)


@pytest.mark.asyncio
async def test_paraphrase_shadow_keeps_real_answer_and_reports_savings(semantic):
    b = semantic
    first = await run(b, 'Explain how rain forms.')
    second = await run(b, 'Describe the process that produces rainfall.')
    assert first.rung == second.rung == 1 and len(b.sent) == 2
    assert (await observation(b, first))['status'] == 'miss'
    row = await observation(b, second)
    assert row['status'] == 'hit' and row['source_id'] == first.ledger_id
    assert row['candidate_content'] == first.content and row['agreement'] == 1
    async with b.pool.acquire() as conn:
        pair = await conn.fetchrow('SELECT * FROM tank.shadow WHERE tenant_id=$1 AND ledger_id=$2', b.tenants[0], second.ledger_id)
    assert pair['method'] == 'fields' and pair['candidate_model'] == cache.CANDIDATE
    report = await proof.snapshot(b.tenants[0], 'base.normalize')
    task = report['tasks'][0]
    assert task['semantic_cache'] == dict(task_type='base.normalize', misses_checked=2, would_have_hits=1,
                                         scored_hits=1, agreement=1, could_have_saved_usd=.001)
    assert task['shadow_pairs'][0]['could_have_cost_usd'] == 0
    assert 'could_have_saved_usd' in proof.csv_export(report)
    assert (await proof.snapshot(b.tenants[1], 'base.normalize'))['tasks'][0]['semantic_cache'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('other', ['Explain 3 rainfall stages.', 'Explain three rainfall stages.',
                                   'Do not explain 2 rainfall stages.', "Don't explain 2 rainfall stages.",
                                   'Explain 2 stages without rain.', 'Explain 2 stages except rain.'])
async def test_numbers_and_negation_never_match_even_identical_vectors(semantic, other):
    b = semantic
    await run(b, 'Describe 2 rainfall stages.')
    result = await run(b, other)
    row = await observation(b, result)
    assert row['status'] in {'miss', 'guarded'} and row['candidate_content'] is None
    assert result.rung == 1 and len(b.sent) == 2


@pytest.mark.asyncio
async def test_tenant_collections_are_isolated(semantic):
    b = semantic
    first = await run(b, 'Explain how rain forms.')
    second = await run(b, 'Describe how rainfall develops.', tenant=b.tenants[1])
    assert (await observation(b, second, b.tenants[1]))['status'] == 'miss'
    names = {c.name for c in (await b.store.client.get_collections()).collections}
    assert names == {cache.collection(t) for t in b.tenants}
    for tenant in b.tenants:
        points, _ = await b.store.client.scroll(cache.collection(tenant))
        assert points and all(p.payload['tenant_id'] == str(tenant) for p in points)
        assert all('content' not in p.payload and 'text' not in p.payload for p in points)
    assert first.rung == second.rung == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('change', ['expiry', 'feedback', 'policy', 'matter', 'region'])
async def test_stale_or_different_context_never_reuses_qdrant_hit(semantic, monkeypatch, change):
    b = semantic
    await run(b, 'Explain how rain forms.', case_ref='matter-a')
    kwargs = {'case_ref': 'matter-a'}
    async with b.pool.acquire() as conn:
        if change == 'expiry':
            await conn.execute("UPDATE tank.route_cache SET expires_at=now()-interval '1 second' WHERE tenant_id=$1", b.tenants[0])
        if change == 'feedback':
            await conn.execute("UPDATE tank.ledger SET feedback='rejected' WHERE tenant_id=$1", b.tenants[0])
        if change == 'policy':
            await conn.execute("UPDATE tank.policy SET system_prompt='Changed context' WHERE tenant_id=$1", b.tenants[0])
    if change == 'matter':
        kwargs['case_ref'] = 'matter-b'
    if change == 'region':
        # Use the index lookup directly: routing to a foreign region is already refused.
        pol = await b.tank.load_policy('base.normalize', b.tenants[0])
        req = request(b, b.tenants[0], text='Describe how rainfall develops.', **kwargs)
        msgs = [{'role': 'system', 'content': pol['system_prompt']}, *[m.model_dump() for m in req.messages]]
        ident = b.tank._cache_identity(req, pol, msgs, pol['max_tokens_out'], None)
        monkeypatch.setenv('TANK_REGION', 'za')
        probe = await cache.lookup(b.tank, req, pol, ident, msgs)
        assert probe.status == 'miss'
        return
    result = await run(b, 'Describe how rainfall develops.', **kwargs)
    assert (await observation(b, result))['status'] == 'miss'


@pytest.mark.asyncio
async def test_command_turn_exact_only_even_with_legacy_semantic_flag(semantic):
    b = semantic
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy(task_type,tenant_id,model,rung,cache_scope,semantic_cache)
            VALUES('command.turn',$1,'haiku',1,'tenant',true)""", b.tenants[0])
    one = await run(b, 'Please summarize the clouds.', task='command.turn')
    two = await run(b, 'Summarise the clouds.', task='command.turn')
    exact = await run(b, 'Please summarize the clouds.', task='command.turn')
    assert one.rung == two.rung == 1 and exact.rung == 4
    assert not b.encoder.calls
    async with b.pool.acquire() as conn:
        assert not await conn.fetchval('SELECT count(*) FROM tank.semantic_observations WHERE tenant_id=$1', b.tenants[0])
    result = await b.client.post('/v1/semantic-cache/command.turn/approval', headers={'X-Tervory-Admin': 'founder-fixture'},
                                json={'tenant_id': str(b.tenants[0]), 'encoder_id': ENCODER_ID, 'policy_hash': 'unused'})
    assert result.status_code == 409


async def seed_evidence(b, count, score=1.0, *, tenant=None, task='base.normalize', distinct=True):
    """Local-only synthetic judge evidence for exact graduation boundary tests."""
    tenant = tenant or b.tenants[0]
    pol = await b.tank.load_policy(task, tenant)
    async with b.pool.acquire() as conn:
        source = await conn.fetchval("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd,outcome) VALUES($1,'us-east','base',$2,'haiku',.001,'delivered') RETURNING id", tenant, task)
        for i in range(count):
            ledger = await conn.fetchval("INSERT INTO tank.ledger(tenant_id,region,agent,task_type,model,cost_usd,outcome) VALUES($1,'us-east','base',$2,'haiku',.001,'delivered') RETURNING id", tenant, task)
            await conn.execute("""INSERT INTO tank.semantic_observations
                (tenant_id,region,task_type,ledger_id,policy_hash,encoder_id,input_hash,status,source_id,agreement)
                VALUES($1,'us-east',$2,$3,$4,$5,$6,'hit',$7,$8)""", tenant, task, ledger, cache.digest(pol), ENCODER_ID,
                f'seed-{i}' if distinct else 'repeated', source, score)
    return pol


async def approval(b, pol, *, tenant=None, approved=True, headers=None):
    return await b.client.post('/v1/semantic-cache/base.normalize/approval',
        headers=headers if headers is not None else {'X-Tervory-Admin': 'founder-fixture'},
        json={'tenant_id': str(tenant or b.tenants[0]), 'encoder_id': ENCODER_ID,
              'policy_hash': cache.digest(pol), 'approved': approved})


@pytest.mark.asyncio
@pytest.mark.parametrize('count,score,distinct', [(199,1,True), (200,.989,True), (200,1,False)])
async def test_approval_refuses_insufficient_evidence(semantic, count, score, distinct):
    b = semantic
    pol = await seed_evidence(b, count, score, distinct=distinct)
    assert (await approval(b, pol)).status_code == 409


@pytest.mark.asyncio
async def test_requires_founder_approval_per_tenant_then_can_serve_and_revoke(semantic):
    b = semantic
    await run(b, 'Explain how rain forms.')
    pol = await seed_evidence(b, 200, .99)
    # Passing evidence alone never serves the embedding candidate.
    second = await run(b, 'Describe how rainfall develops.')
    assert second.rung == 1
    assert (await approval(b, pol, headers={})).status_code == 404
    assert (await approval(b, pol, headers={'X-Tervory-Admin': 'ordinary-user'})).status_code == 404
    assert (await approval(b, pol)).status_code == 200
    hit = await run(b, 'How does rain come about?')
    assert hit.rung == 4 and hit.model == cache.CANDIDATE
    assert len(b.sent) == 2
    # A second tenant has neither the corpus nor the approval/evidence.
    foreign = await run(b, 'How does rain come about?', tenant=b.tenants[1])
    assert foreign.rung == 1
    assert (await approval(b, pol, approved=False)).status_code == 200
    after = await run(b, 'What causes rainfall?')
    assert after.rung == 1


@pytest.mark.asyncio
async def test_new_policy_invalidates_approval(semantic):
    b = semantic
    await run(b, 'Explain how rain forms.')
    pol = await seed_evidence(b, 200)
    assert (await approval(b, pol)).status_code == 200
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET max_tokens_out=max_tokens_out+1 WHERE tenant_id=$1", b.tenants[0])
    assert (await approval(b, pol)).status_code == 409
    assert (await run(b, 'Describe how rainfall develops.')).rung == 1


@pytest.mark.asyncio
async def test_existing_judge_used_for_prose_and_cost_booked_separately(semantic, monkeypatch):
    b = semantic
    first = await run(b, 'Explain how rain forms.')
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.transcripts SET content='Water condenses in clouds.' WHERE tenant_id=$1 AND ledger_id=$2", b.tenants[0], first.ledger_id)
    calls = []
    async def judge(model, messages, tokens):
        calls.append((model, messages))
        return '100', .0002
    monkeypatch.setattr(b.tank, '_llm', judge)
    second = await run(b, 'Describe how rainfall develops.')
    assert len(calls) == 1 and 'SECOND ANSWER:\nWater condenses in clouds.' in calls[0][1][-1]['content']
    assert (await observation(b, second))['agreement'] == 1
    report = await proof.snapshot(b.tenants[0], 'base.normalize')
    pair = report['tasks'][0]['shadow_pairs'][0]
    assert pair['could_have_cost_usd'] == 0 and pair['evaluation_cost_usd'] == .0002
    async with b.pool.acquire() as conn:
        assert float(await conn.fetchval("SELECT cost_usd FROM tank.ledger WHERE tenant_id=$1 AND task_type='base.normalize#shadow'", b.tank.PLATFORM_TENANT)) == .0002


@pytest.mark.asyncio
async def test_judge_budget_exhaustion_keeps_unscored_would_hit(semantic, monkeypatch):
    b = semantic
    first = await run(b, 'Explain how rain forms.')
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.transcripts SET content='Water condenses in clouds.' WHERE tenant_id=$1 AND ledger_id=$2", b.tenants[0], first.ledger_id)
    monkeypatch.setenv('TANK_SHADOW_BUDGET_USD', '0')
    async def forbidden(*args):
        raise AssertionError('Judge must not run after budget exhaustion')
    monkeypatch.setattr(b.tank, '_llm', forbidden)
    second = await run(b, 'Describe how rainfall develops.')
    row = await observation(b, second)
    assert row['status'] == 'hit' and row['agreement'] is None and row['candidate_content']


@pytest.mark.asyncio
async def test_encoder_unavailable_leaves_served_route_intact_and_records_status(semantic, monkeypatch):
    b = semantic
    def unavailable(text):
        raise RuntimeError('offline stub error')
    monkeypatch.setattr(b.encoder, 'embed', unavailable)
    result = await run(b, 'Explain how rain forms.')
    assert result.rung == 1 and (await observation(b, result))['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_schema_reapplies_without_losing_observations(semantic):
    b = semantic
    result = await run(b, 'Explain how rain forms.')
    async with b.pool.acquire() as conn:
        await conn.execute((Path(__file__).resolve().parents[1] / 'tank/schema.sql').read_text())
    assert (await observation(b, result))['status'] == 'miss'


def test_model_download_is_build_only_and_module_is_in_image(monkeypatch):
    import semantic_encoder as encoder
    calls = []
    import sys
    from types import SimpleNamespace
    def forbidden(**kwargs):
        calls.append(kwargs)
        raise AssertionError('No download in runtime or tests')
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(snapshot_download=forbidden))
    monkeypatch.setattr(encoder, 'MODEL_PATH', Path('/definitely-missing-offline-fixture'))
    with pytest.raises(RuntimeError, match='missing'):
        encoder.LocalEncoder().embed('rain')
    assert not calls
    docker = (Path(__file__).resolve().parents[1] / 'tank/Dockerfile').read_text()
    heavy_copy = docker.index('COPY requirements-routellm.txt')
    heavy_run = docker.index('RUN --mount=type=secret,id=proxy_ca')
    download = docker.index('python semantic_encoder.py')
    code_copy = docker.index('COPY *.py schema.sql')
    assert heavy_copy < heavy_run < download < code_copy
    assert 'semantic_encoder.py' in docker[heavy_copy:heavy_run]
    assert 'python routellm_build.py /opt/routellm &&' in docker[heavy_run:code_copy]
    assert 'COPY main.py' not in docker


@pytest.mark.asyncio
async def test_batch_completion_records_enqueue_time_shadow_once(semantic, monkeypatch):
    from test_tank_batch_providers import LiteLLMStub, NATIVE
    b = semantic
    async with b.pool.acquire() as conn:
        await conn.execute("""UPDATE tank.policy SET model='batch-fixture',batch_eligible=true,
            max_cost_usd=1 WHERE tenant_id=$1""", b.tenants[0])
    async def roster():
        return [{'model_name': 'batch-fixture', 'litellm_params': {'model': 'openai/' + NATIVE['openai']},
                 'model_info': {'input_cost_per_token': .000002, 'output_cost_per_token': .00001}}]
    monkeypatch.setattr(b.tank, '_roster_models', roster)
    monkeypatch.setenv('TANK_BATCH_MIN', '2')
    stub = LiteLLMStub('openai')
    monkeypatch.setattr(b.tank, '_batch_gateway', stub)
    async def judge(*args):
        return '100', 0
    monkeypatch.setattr(b.tank, '_llm', judge)
    await run(b, 'Explain rainfall stage 0')
    body = b.tank.BatchRequest(requests=[request(b, b.tenants[0], interactive=False, text=f'Describe rain stage {i}') for i in range(2)])
    queued = await b.tank.route_batch(body, None)
    assert queued['status'] == 'queued'
    await b.tank.process_batches_once()
    stub.finished = True
    await b.tank.process_batches_once()
    await drain(b)
    await b.tank.process_batches_once()
    status = await b.tank.batch_status(body.id, b.tenants[0])
    assert status['status'] == 'completed'
    async with b.pool.acquire() as conn:
        rows = await conn.fetch("""SELECT o.status FROM tank.semantic_observations o JOIN tank.ledger l
            ON l.id=o.ledger_id AND l.tenant_id=o.tenant_id WHERE o.tenant_id=$1 AND l.batch_id=$2""", b.tenants[0], body.id)
    assert sorted(r['status'] for r in rows) == ['hit', 'miss']


@pytest.mark.asyncio
async def test_untrusted_qdrant_payload_cannot_cross_tenant(semantic, monkeypatch):
    from types import SimpleNamespace
    b = semantic
    await run(b, 'Explain how rain forms.', tenant=b.tenants[1])
    foreign, _ = await b.store.client.scroll(cache.collection(b.tenants[1]))
    async def wrong_results(**kwargs):
        return SimpleNamespace(points=[SimpleNamespace(score=1, payload=foreign[0].payload)])
    await b.store.ensure(cache.collection(b.tenants[0]))
    monkeypatch.setattr(b.store.client, 'query_points', wrong_results)
    result = await run(b, 'Describe how rainfall develops.')
    assert (await observation(b, result))['status'] == 'miss'


@pytest.mark.asyncio
async def test_qdrant_failure_is_recorded_without_changing_real_answer(semantic, monkeypatch):
    b = semantic
    async def unavailable(*args):
        raise ConnectionError('stub')
    monkeypatch.setattr(b.store, 'search', unavailable)
    result = await run(b, 'Explain how rain forms.')
    assert result.rung == 1 and (await observation(b, result))['status'] == 'unavailable'


@pytest.mark.asyncio
async def test_negated_source_is_not_indexed(semantic):
    b = semantic
    first = await run(b, 'Do not describe rainfall.')
    second = await run(b, 'Describe rainfall.')
    assert (await observation(b, first))['status'] == 'guarded'
    assert (await observation(b, second))['status'] == 'miss'


def test_runtime_encoder_uses_pinned_files_cpu_and_never_truncates(monkeypatch, tmp_path):
    import sys
    from types import SimpleNamespace
    import semantic_encoder as encoder
    calls = []
    for name in encoder.FILES:
        (tmp_path / name).touch()
    (tmp_path / 'revision').write_text(encoder.MODEL_REVISION)
    monkeypatch.setattr(encoder, 'MODEL_PATH', tmp_path)
    class Tokenizer:
        long = False
        def no_truncation(self):
            self.truncated = False
        def encode(self, text):
            return SimpleNamespace(ids=list(range(513 if self.long else 2)))
    tokenizer = Tokenizer()
    class Model:
        def __init__(self, **kwargs):
            calls.append(kwargs)
        def embed(self, texts):
            return iter([[1.0] * DIMENSIONS])
    monkeypatch.setitem(sys.modules, 'fastembed', SimpleNamespace(TextEmbedding=Model))
    monkeypatch.setitem(sys.modules, 'tokenizers', SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: tokenizer)))
    local = encoder.LocalEncoder()
    assert len(local.embed('rain')) == DIMENSIONS
    assert calls == [dict(model_name=encoder.MODEL_NAME, specific_model_path=str(tmp_path),
                          local_files_only=True, cuda=False, threads=2)]
    tokenizer.long = True
    with pytest.raises(ValueError, match='context'):
        local.embed('long input')
    (tmp_path / 'revision').write_text('changed')
    with pytest.raises(RuntimeError, match='missing'):
        encoder.LocalEncoder().embed('rain')
