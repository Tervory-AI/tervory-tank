"""Both shadow experiments on one real route; all inference is stubbed."""
import asyncio
import uuid

import pytest
from qdrant_client import AsyncQdrantClient

import semantic_cache as cache
from test_tank_routellm import real_tank  # noqa: F401
from test_tank_semantic_cache import EncoderStub


@pytest.mark.asyncio
async def test_routellm_and_cache_share_shadow_runner_and_report(real_tank, monkeypatch):  # noqa: F811 (pytest fixture parameter)
    b = real_tank
    tenant, other = b.tenants
    store = cache.VectorIndex(AsyncQdrantClient(location=':memory:'))
    monkeypatch.setattr(cache, '_encoder', EncoderStub())
    monkeypatch.setattr(cache, '_index', store)
    async with b.pool.acquire() as conn:
        await conn.execute("""UPDATE tank.policy SET cache_scope='tenant',
            routellm_weak_model='flash-lite',routellm_threshold=.7 WHERE tenant_id=$1""", tenant)
    try:
        for text in ('Explain how rain forms.', 'Describe how rainfall develops.'):
            result = await b.client.post('/v1/route', json={
                'tenant_id': str(tenant), 'task_type': 'routellm.proof',
                'messages': [{'role': 'user', 'content': text}],
            })
            assert result.status_code == 200, result.text
            assert result.json()['content'] == 'Live policy answer'
            assert result.json()['model'] == 'sol' and result.json()['rung'] == 1
            while b.tank._background:
                await asyncio.gather(*list(b.tank._background))
        async with b.pool.acquire() as conn:
            rows = await conn.fetch('SELECT * FROM tank.shadow WHERE tenant_id=$1 AND ledger_id=$2',
                                    tenant, uuid.UUID(result.json()['ledger_id']))
        assert len(rows) == 2
        cached = next(row for row in rows if row['candidate_model'] == cache.CANDIDATE)
        routed = next(row for row in rows if row['routellm_config'] is not None)
        assert cached['agreement'] == routed['agreement'] == 1
        assert cached['routellm_config'] is None and cached['candidate_ledger_id'] is None
        assert routed['candidate_ledger_id'] is not None
        headers = {'X-Tervory-Admin': 'local-founder'}
        report = (await b.client.get('/v1/proof', params={'tenant_id': str(tenant)}, headers=headers)).json()
        task = next(t for t in report['tasks'] if t['task_type'] == 'routellm.proof')
        assert len(task['shadow_pairs']) == 2
        cached = next(p for p in task['shadow_pairs'] if p['candidate_model'] == cache.CANDIDATE)
        routed = next(p for p in task['shadow_pairs'] if p['candidate_model'] != cache.CANDIDATE)
        assert (cached['samples'], cached['primary_cost_usd'], cached['could_have_cost_usd'],
                cached['saved_usd'], cached['evaluation_cost_usd']) == (1, .02, 0, .02, .001)
        assert (routed['samples'], routed['primary_cost_usd'], routed['could_have_cost_usd'],
                routed['saved_usd']) == (2, .04, .004, .036)
        assert task['semantic_cache']['would_have_hits'] == 1
        assert task['semantic_cache']['could_have_saved_usd'] == .02
        foreign = (await b.client.get('/v1/proof', params={'tenant_id': str(other)}, headers=headers)).json()
        assert not foreign['shadows'] and all(not t['shadow_pairs'] for t in foreign['tasks'])
    finally:
        while b.tank._background:
            await asyncio.gather(*list(b.tank._background))
        await store.client.close()
