"""C4 reuse across real consumers; local Qdrant, fake CPU encoder, no providers."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

import pytest
from qdrant_client import QdrantClient, models

import cache_metrics
import codebase_index
import embedding_cache as cache
import semantic_encoder
from test_tank_tenant_boundaries import boundary as boundary_fixture

boundary = boundary_fixture

@pytest.fixture(autouse=True)
def enable_requested_layers(monkeypatch):
    monkeypatch.setenv('ENGINE_C4_ENABLED', '1')



@pytest.fixture
def shared(monkeypatch):
    from tank import embedding_cache as hermes_cache
    from tank import semantic_encoder as hermes_encoder
    client = QdrantClient(location=':memory:')
    monkeypatch.setattr(cache, '_cache', cache.VectorCache(client))
    monkeypatch.setattr(hermes_cache, '_cache', hermes_cache.VectorCache(client))
    calls = []
    def compute(self, text):
        calls.append(text)
        return [.25] * semantic_encoder.DIMENSIONS
    for encoder in (semantic_encoder.LocalEncoder, hermes_encoder.LocalEncoder):
        monkeypatch.setattr(encoder, '_validate', lambda self, text: None)
        monkeypatch.setattr(encoder, '_embed', compute)
    yield calls, client, hermes_cache
    client.close()


def test_text_embedded_once_across_semantic_memory_and_codebase(shared):
    import semantic_cache
    from hermes.record_runtime import LocalEncoder as MemoryEncoder
    calls, client, hermes_cache = shared
    text = 'placeholder exact source text'
    with cache.measure() as semantic:
        assert semantic_cache._encoder.embed(text) == [.25] * semantic_encoder.DIMENSIONS
    with hermes_cache.measure() as memory:
        assert MemoryEncoder().embed(text) == [.25] * semantic_encoder.DIMENSIONS
    with cache.measure() as code:
        rows = codebase_index.search(codebase_index.Search(files={'placeholder.py': text}, query=text))
    assert calls == [text]
    assert semantic.values['attempts'] == 1 and semantic.values['hits'] == 0
    assert memory.values['attempts'] == memory.values['hits'] == 1
    assert code.values['attempts'] == code.values['hits'] == 2
    assert rows[0]['file'] == 'placeholder.py' and rows[0]['score'] == pytest.approx(1)
    collection = client.get_collections().collections[0].name
    points, _ = client.scroll(collection, with_vectors=True)
    assert len(points) == 1 and text not in json.dumps(points[0].payload)
    assert set(points[0].payload) == {'key', 'expires', 'compute_ms'}
    assert memory.values['saved_compute_ms'] > 0 and memory.values['saved_usd'] == 0


def test_revision_expiry_corruption_and_concurrent_misses(shared):
    _, client, _ = shared
    instance = cache._cache
    calls = []
    def compute():
        calls.append(True)
        return [.5, .25]
    with ThreadPoolExecutor(max_workers=8) as executor:
        result = list(executor.map(lambda _: instance.embed('placeholder-model-v1', 'placeholder text', 2, compute), range(20)))
    assert len(calls) == 1 and result == [[.5, .25]] * 20
    instance.embed('placeholder-model-v2', 'placeholder text', 2, compute)
    assert len(calls) == 2
    name = instance.collection('placeholder-model-v1', 2)
    points, _ = client.scroll(name)
    client.set_payload(name, {'expires': 0}, [points[0].id])
    instance.local.clear()
    instance.embed('placeholder-model-v1', 'placeholder text', 2, compute)
    assert len(calls) == 3
    client.upsert(name, [models.PointStruct(id=points[0].id, vector=[.1, .2], payload={'key': 'placeholder-wrong-key'})])
    instance.local.clear()
    instance.embed('placeholder-model-v1', 'placeholder text', 2, compute)
    assert len(calls) == 4


def test_cache_outage_falls_through_without_text_or_error_leak():
    class Offline:
        def collection_exists(self, name):
            raise RuntimeError('placeholder private connection detail')
    instance = cache.VectorCache(Offline())
    assert instance.embed('placeholder-model', 'placeholder-input', 2, lambda: [.5, .25]) == [.5, .25]
    assert instance.embed('placeholder-model', 'placeholder-input', 2, lambda: [0., 0.]) == [.5, .25]
    with pytest.raises(ValueError, match='Invalid embedding vector'):
        instance.embed('placeholder-model', 'placeholder-other', 2, lambda: [float('nan'), 0.])


@pytest.mark.asyncio
async def test_codebase_endpoint_and_status_are_tenant_scoped(boundary, shared):
    b = boundary
    body = {'files': {'placeholder.py': 'placeholder text'}, 'query': 'placeholder text'}
    denied = await b.client.post('/v1/engine/codebase/search', json=body,
                                  headers=b.native_headers('placeholder-member'))
    assert denied.status_code == 403
    headers = b.native_headers('founder-fixture', 'org_admin')
    first = await b.client.post('/v1/engine/codebase/search', json=body, headers=headers)
    second = await b.client.post('/v1/engine/codebase/search', json=body, headers=headers)
    assert first.status_code == second.status_code == 200, second.text
    receipt = second.json()['receipt']
    assert receipt['cost_usd'] == 0 and receipt['engine']['cache_layers']['C4']['hits'] == 2
    status = await b.client.get('/v1/engine/status', params={'tenant_id': str(b.tenants[0])}, headers=headers)
    row = next(r for r in status.json()['tasks'] if r['task_type'] == 'command.code.index')
    c4 = row['cache_layers']['C4']
    assert c4['attempts'] == 4 and c4['hits'] == 3 and c4['hit_rate'] == .75
    assert c4['saved_usd'] == 0 and c4['saved_compute_ms'] > 0
    assert not await cache_metrics.status(b.tank, b.tenants[1])
    other = await b.client.post('/v1/engine/codebase/search', json={
        'files': {'placeholder-other.py': 'placeholder unrelated text'}, 'query': 'placeholder text'}, headers=headers)
    assert all(r['file'] != 'placeholder.py' for r in other.json()['matches'])


def test_legacy_hermes_encoder_also_uses_c4(shared, monkeypatch):
    from hermes.embeddings import FastEmbedder
    calls = []
    def compute(self, texts):
        calls.extend(texts)
        return [[.25] * self.dim for _ in texts]
    monkeypatch.setattr(FastEmbedder, '_embed_many', compute)
    one, two = FastEmbedder(), FastEmbedder()
    assert one.embed('placeholder text') == two.embed('placeholder text')
    assert calls == ['placeholder text']
    assert 'COPY tank/embedding_cache.py /srv/hermes/embedding_cache.py' in Path('hermes/Dockerfile').read_text()
