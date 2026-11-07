"""C4 unset preserves main's original inference and batch path, without cache I/O."""
from pathlib import Path

import pytest

import embedding_cache as cache
import semantic_encoder


@pytest.mark.parametrize('setting', [None, '', '0', 'true', 'invalid'])
def test_default_off_matches_original_single_and_batch_inference(monkeypatch, setting):
    from hermes.embeddings import FastEmbedder
    from tank import embedding_cache as memory_cache
    if setting is None:
        monkeypatch.delenv('ENGINE_C4_ENABLED', raising=False)
    else:
        monkeypatch.setenv('ENGINE_C4_ENABLED', setting)
    def forbidden(*args, **kwargs):
        pytest.fail('Disabled cache must perform no cache I/O or allocation')
    for module in (cache, memory_cache):
        monkeypatch.setattr(module, '_cache', None)
        monkeypatch.setattr(module, 'VectorCache', forbidden)
    calls = []
    class Model:
        def embed(self, texts, **kwargs):
            calls.append((list(texts), kwargs))
            return [[.25] * semantic_encoder.DIMENSIONS for _ in texts]
    encoder = semantic_encoder.LocalEncoder()
    encoder._model = Model()
    validated = []
    monkeypatch.setattr(encoder, '_validate', validated.append)
    # _embed is main's original inference body, preserved without modification.
    baseline = encoder._embed('placeholder text')
    assert cache.scoped_embed(encoder.embed, 'placeholder text', 'tenant-a') == baseline
    assert validated == ['placeholder text'] * 2
    assert calls == [(['placeholder text'], {})] * 2
    batch = FastEmbedder()
    batch._model = Model()
    texts = ['placeholder a', 'placeholder b', 'placeholder a']
    expected = batch._embed_many(texts)
    assert memory_cache.scoped_embed(lambda _: batch.embed_many(texts), '', 'tenant-a') == expected
    assert calls[-2:] == [(texts, {'batch_size': 16})] * 2
    assert cache._cache is memory_cache._cache is None


def test_regional_wiring_is_opt_in_for_only_existing_consumers(monkeypatch):
    import yaml
    monkeypatch.delenv('ENGINE_C4_ENABLED', raising=False)
    assert not cache.enabled()
    assert 'ENGINE_C4_ENABLED=' in Path('.env.example').read_text().splitlines()
    for name in ('docker-compose.yml', 'docker-compose.za.yml'):
        services = yaml.safe_load(Path(name).read_text())['services']
        consumers = {name for name, service in services.items()
                     if 'ENGINE_C4_ENABLED' in service.get('environment', {})}
        assert consumers == {'tank', 'hermes'}
        for consumer in consumers:
            assert services[consumer]['environment']['ENGINE_C4_ENABLED'] == '${ENGINE_C4_ENABLED:-}'

