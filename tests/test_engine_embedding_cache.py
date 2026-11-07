"""C4: fake inference and local Qdrant only, including real consumer paths."""
from concurrent.futures import ThreadPoolExecutor
import asyncio
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from qdrant_client import AsyncQdrantClient, QdrantClient

import embedding_cache as cache
import semantic_encoder
from test_agent_memory_records import memory as memory_fixture

memory = memory_fixture


@pytest.fixture
def shared(monkeypatch):
    from tank import embedding_cache as memory_cache
    from tank import semantic_encoder as memory_encoder
    client = QdrantClient(location=':memory:')
    monkeypatch.setenv('ENGINE_C4_ENABLED', '1')
    for module in (cache, memory_cache):
        monkeypatch.setattr(module, '_cache', module.VectorCache(client))
    calls = []
    def compute(self, text):
        calls.append(text)
        return [.25] * semantic_encoder.DIMENSIONS
    for encoder in (semantic_encoder.LocalEncoder, memory_encoder.LocalEncoder):
        monkeypatch.setattr(encoder, '_validate', lambda self, text: None)
        monkeypatch.setattr(encoder, '_embed', compute)
    yield calls, client, memory_cache
    client.close()




def test_enabled_without_tenant_never_creates_shared_cache(shared):
    calls, _, _ = shared
    encoder = semantic_encoder.LocalEncoder()
    encoder.embed('placeholder text')
    encoder.embed('placeholder text')
    assert len(calls) == 2 and not cache._cache.local
    assert not cache.active()


@pytest.mark.asyncio
async def test_reuse_across_index_semantic_and_memory_same_tenant(shared, monkeypatch):
    import semantic_cache
    import trigger_bot_sources
    from hermes.record_runtime import LocalEncoder as MemoryEncoder
    calls, client, memory_cache = shared
    created = []
    original_create = client.create_collection
    def capture_create(name, **kwargs):
        created.append(kwargs)
        return original_create(name, **kwargs)
    monkeypatch.setattr(client, 'create_collection', capture_create)
    tenant, other = uuid4(), uuid4()
    text = 'placeholder exact source text'
    index = trigger_bot_sources.BotIndex(AsyncQdrantClient(location=':memory:'))
    try:
        await index.put(tenant, 'us-east', uuid4(), text)
        assert await index.query(tenant, 'us-east', text)
        # A miss in the semantic result cache can still reuse an exact vector.
        semantic_index = semantic_cache.VectorIndex(AsyncQdrantClient(location=':memory:'))
        monkeypatch.setattr(semantic_cache, '_index', semantic_index)
        rt = SimpleNamespace(box_region=lambda: 'us-east')
        req = SimpleNamespace(tenant_id=tenant, task_type='placeholder.task')
        with cache.measure() as measured:
            result = await semantic_cache.lookup(rt, req, {'cache_scope': 'tenant'},
                ('placeholder-context',), [{'role': 'user', 'content': text}])
        assert result.status == 'miss' and measured.values['hits'] == 1
        await semantic_index.client.close()
        # Separate module/process-local caches reuse the same regional store.
        with memory_cache.measure() as memory_measure:
            vector = await asyncio.to_thread(memory_cache.scoped_embed, MemoryEncoder().embed, text, tenant)
        assert vector == [.25] * semantic_encoder.DIMENSIONS
        assert memory_measure.values['hits'] == 1 and memory_measure.values['saved_usd'] == 0
        assert calls == [text]
        await index.put(other, 'us-east', uuid4(), text)
        assert calls == [text, text]
        names = client.get_collections().collections
        assert len(names) == 1
        config = client.get_collection(names[0].name).config
        assert config.params.vectors.on_disk
        # Local Qdrant does not implement disk/ANN tuning: verify the real API arguments.
        assert created[0]['hnsw_config'].m == 0
        assert created[0]['on_disk_payload'] is True
        points, _ = client.scroll(names[0].name, with_vectors=True)
        assert len(points) == 2
        assert text not in json.dumps([p.payload for p in points])
        assert {p.payload['tenant'] for p in points} == {
            hashlib.sha256(str(t).encode()).hexdigest() for t in (tenant, other)}
        assert all(set(p.payload) == {'key', 'tenant', 'expires', 'compute_ms'} for p in points)
    finally:
        await index.client.close()
    assert not cache.active() and not memory_cache.active()


@pytest.mark.asyncio
@pytest.mark.parametrize('enabled', [False, True])
async def test_sql_memory_jobs_and_recall_reuse_without_broadening_ownership(memory, shared, monkeypatch, enabled):
    from hermes.records import embedding_cache as memory_cache
    m = memory
    if not enabled:
        monkeypatch.delenv('ENGINE_C4_ENABLED')
    calls = []
    class Encoder:
        def validate(self, text):
            pass
        def embed(self, text):
            def compute():
                calls.append(text)
                return [1., 0., 0., 0.]
            return memory_cache.embed('offline-pin-v1', text, 4, compute)
    m.records.encoder = Encoder()
    text = 'placeholder private claim'
    row = await m.records.save(m.agent, m.tenant, text, [], meta={'user_id': 'placeholder-user-a'})
    found = await m.records.recall(m.agent, m.tenant, text, None, 8, 'client', user_id='placeholder-user-a')
    assert [r['id'] for r in found] == [row['id']] and calls == [text] * (1 if enabled else 2)
    assert await m.records.recall(m.agent, m.tenant, text, None, 8, 'client', user_id='placeholder-user-b') == []
    assert calls == [text] * (1 if enabled else 2)
    other = await m.records.save(m.agent, m.other, text, [], meta={'user_id': 'placeholder-user-a'})
    found = await m.records.recall(m.agent, m.other, text, None, 8, 'client', user_id='placeholder-user-a')
    assert [r['id'] for r in found] == [other['id']] and calls == [text] * (2 if enabled else 4)


def test_revision_dimensions_expiry_corruption_and_concurrent_misses(shared):
    _, client, _ = shared
    instance = cache._cache
    calls = []
    def compute():
        calls.append(True)
        return [.5, .25]
    def embed():
        return instance.embed('tenant-a', 'placeholder-v1', 'placeholder text', 2, compute)
    with ThreadPoolExecutor(max_workers=8) as executor:
        result = list(executor.map(lambda _: embed(), range(20)))
    assert len(calls) == 1 and result == [[.5, .25]] * 20
    result[0][0] = 999
    assert embed() == [.5, .25]
    instance.embed('tenant-a', 'placeholder-v2', 'placeholder text', 2, compute)
    assert len(calls) == 2
    assert instance.embed('tenant-a', 'placeholder-v1', 'placeholder text', 3, lambda: [.5, .25, 0.]) == [.5, .25, 0.]
    name = instance.collection('placeholder-v1', 2)
    points, _ = client.scroll(name)
    for corruption in ({'expires': 0}, {'tenant': 'placeholder-wrong-tenant'}, {'compute_ms': float('nan')}):
        client.set_payload(name, corruption, [points[0].id])
        instance.local.clear()
        assert embed() == [.5, .25]
    assert len(calls) == 5


def test_cache_bounds_outage_validation_and_scope_reset(monkeypatch):
    class Offline:
        def collection_exists(self, name):
            raise RuntimeError('placeholder private connection detail')
    instance = cache.VectorCache(Offline())
    monkeypatch.setattr(cache, 'MAX_ENTRIES', 2)
    for i in range(3):
        assert instance.embed('tenant-a', 'placeholder-model', str(i), 2, lambda: [.5, .25]) == [.5, .25]
    assert len(instance.local) == 2
    assert instance.embed('tenant-a', 'placeholder-model', '2', 2, lambda: [0., 0.]) == [.5, .25]
    for vector in ([float('nan'), 0.], [True, 0.], [.5]):
        with pytest.raises(ValueError, match='Invalid embedding vector'):
            instance.embed('tenant-a', 'placeholder-model', 'bad', 2, lambda: vector)
    monkeypatch.setenv('ENGINE_C4_ENABLED', '1')
    def broken(text):
        raise RuntimeError('placeholder encoder error')
    with pytest.raises(RuntimeError, match='placeholder encoder error'):
        cache.scoped_embed(broken, 'placeholder', 'tenant-a')
    assert not cache.active()


def test_existing_legacy_memory_encoder_reuses_only_within_tenant(shared, monkeypatch):
    from hermes.embeddings import FastEmbedder
    from hermes.service import _remember, _recall
    from hermes.store import InMemoryStore
    calls = []
    def compute(self, texts):
        calls.extend(texts)
        return [[.25] * self.dim for _ in texts]
    monkeypatch.setattr(FastEmbedder, '_embed_many', compute)
    store = InMemoryStore()
    text = 'placeholder text'
    own = _remember(store, FastEmbedder(), 'mem_template', 'tenant-a', text, 'heartbeat', 'placeholder-source', {})
    assert [h.memory.id for h in _recall(store, FastEmbedder(), 'mem_template', 'tenant-a', text, None, 8)] == [own['id']]
    assert _recall(store, FastEmbedder(), 'mem_template', 'tenant-b', text, None, 8) == []
    assert calls == [text] * 2
    assert 'COPY tank/embedding_cache.py /srv/hermes/embedding_cache.py' in Path('hermes/Dockerfile').read_text()


def test_tenant_context_cannot_escape_between_concurrent_or_nested_requests(shared):
    calls, _, _ = shared
    encoder = semantic_encoder.LocalEncoder()
    def embed(tenant):
        return cache.scoped_embed(encoder.embed, 'placeholder text', tenant)
    with ThreadPoolExecutor(max_workers=8) as executor:
        assert list(executor.map(embed, ['tenant-a', 'tenant-b'] * 10)) == [[.25] * 384] * 20
    assert calls == ['placeholder text'] * 2
    cache.scoped_embed(lambda _: embed(None), 'placeholder', 'tenant-a')
    assert calls == ['placeholder text'] * 3
    assert not cache.active()


def test_pinned_tokenizer_validation_still_runs_on_cache_hits(shared, monkeypatch):
    encoder = semantic_encoder.LocalEncoder()
    cache.scoped_embed(encoder.embed, 'placeholder text', 'tenant-a')
    def reject(text):
        raise ValueError('Semantic input exceeds encoder context')
    monkeypatch.setattr(encoder, '_validate', reject)
    with pytest.raises(ValueError, match='exceeds encoder context'):
        cache.scoped_embed(encoder.embed, 'placeholder text', 'tenant-a')




def test_expiry_sweep_deletes_only_the_active_tenants_expired_vectors(shared):
    _, client, _ = shared
    instance = cache._cache
    for tenant in ('tenant-a', 'tenant-b'):
        instance.embed(tenant, 'placeholder-pin', 'placeholder old text', 2, lambda: [.5, .25])
    name = instance.collection('placeholder-pin', 2)
    points, _ = client.scroll(name)
    client.set_payload(name, {'expires': 0}, [point.id for point in points])
    instance.swept.clear()
    instance.embed('tenant-a', 'placeholder-pin', 'placeholder new text', 2, lambda: [.25, .5])
    points, _ = client.scroll(name)
    tenant_a = hashlib.sha256(b'tenant-a').hexdigest()
    tenant_b = hashlib.sha256(b'tenant-b').hexdigest()
    assert len(points) == 2
    assert all(point.payload['expires'] > 0 for point in points if point.payload['tenant'] == tenant_a)
    assert [point.payload['expires'] for point in points if point.payload['tenant'] == tenant_b] == [0]
