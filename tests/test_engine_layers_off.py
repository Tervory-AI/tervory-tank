"""HEAD default-off contract: preserve main's execution paths without new caches."""
import hashlib
import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import yaml

import embedding_cache
import exact_cache
import priority_queue
import semantic_encoder
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, policy, request, selected_policy_protocol

boundary = boundary_fixture
ladder = ladder_fixture
ROOT = Path(__file__).resolve().parents[1]
FLAGS = ('ENGINE_C1_ENABLED', 'ENGINE_C4_ENABLED', 'ENGINE_I8_ENABLED')


@pytest.fixture(autouse=True)
def off(monkeypatch):
    for name in FLAGS:
        monkeypatch.delenv(name, raising=False)


def gateway_config(monkeypatch, file='config.yaml'):
    monkeypatch.syspath_prepend(str(ROOT / 'litellm'))
    spec = importlib.util.spec_from_file_location('placeholder_engine_config', ROOT / 'litellm/engine_config.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.configure(yaml.safe_load((ROOT / 'litellm' / file).read_text()))


@pytest.mark.asyncio
async def test_unset_layers_keep_main_sql_cache_and_immediate_dispatch_without_new_writes(ladder, monkeypatch):
    b = ladder
    selected_policy_protocol(monkeypatch)
    monkeypatch.setattr(b.tank.semantic_cache, 'lookup', AsyncMock(return_value=None))
    monkeypatch.setattr(b.tank.semantic_cache, 'schedule', Mock())
    await policy(b, b.tenants[0], model='haiku', rung=1, cache_scope='tenant', batch_eligible=True,
                 semantic_cache=False, shadow_rate=0)
    req = request(b, b.tenants[0], text='placeholder default-off request', interactive=False, priority='standard')
    selected = await b.tank.load_policy(req.task_type, req.tenant_id)
    assert selected['cache_ttl_s'] == 0
    # Exact shape used by origin/main before this PR, including its absence of
    # the new TTL column. Previously stored SQL answers must remain reusable.
    messages = [m.model_dump() for m in req.messages]
    if selected['system_prompt']:
        messages.insert(0, {'role': 'system', 'content': selected['system_prompt']})
    old_policy = {k: v for k, v in selected.items() if k != 'cache_ttl_s'}
    legacy_context = [old_policy, req.skill, req.case_ref, None, selected['max_tokens_out'], b.tank.box_region(),
                      [m for m in messages if m['role'] != 'user']]
    identity = b.tank._cache_identity(req, selected, messages, selected['max_tokens_out'], None)
    assert identity[0] == hashlib.sha256(json.dumps(legacy_context, sort_keys=True, default=str).encode()).hexdigest()
    config = gateway_config(monkeypatch)['litellm_settings']
    redis_writes = []
    class Gateway:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            body = kwargs['json']
            b.sent.append(body)
            if config['cache'] and body.get('cache', {}).get('use-cache'):
                redis_writes.append(body)
            return httpx.Response(200, headers={'x-litellm-response-cost': '.001'}, json={
                'choices': [{'message': {'content': 'placeholder answer'}}],
                'usage': {'prompt_tokens': 12, 'completion_tokens': 6}})
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', Gateway)
    first = await b.tank.run_route(req, _paid_policy=selected)
    second = await b.tank.run_route(req, _paid_policy=selected)
    assert isinstance(first, b.tank.RouteResponse) and first.cost_usd == .001
    assert second.rung == 4 and second.cost_usd == 0 and second.content == first.content
    assert first.cache_layer is second.cache_layer is None
    assert len(b.sent) == 1 and 'cache' not in b.sent[0] and redis_writes == []
    assert config['cache'] is False and 'cache_params' not in config
    assert not any(k in (first.engine or {}).get('cache_layers', {}) for k in ('C1', 'C4'))
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.offpeak_jobs WHERE tenant_id=$1', req.tenant_id) == 0
        ttl = await conn.fetchval('SELECT extract(epoch FROM expires_at-now()) FROM tank.route_cache WHERE tenant_id=$1', req.tenant_id)
        assert b.tank.CACHE_TTL_S - 60 < ttl <= b.tank.CACHE_TTL_S


def test_unset_c4_never_reads_or_writes_either_cache_and_preserves_embedding_batch(monkeypatch):
    class Forbidden:
        def __getattr__(self, name):
            raise AssertionError('default-off cache touched ' + name)
    monkeypatch.setattr(embedding_cache, '_cache', Forbidden())
    calls = []
    def compute():
        calls.append(True)
        return [.25, .5]
    instance = embedding_cache.VectorCache(Forbidden())
    for _ in range(2):
        assert embedding_cache.embed('placeholder-model', 'placeholder text', 2, compute) == [.25, .5]
        assert instance.embed('placeholder-model', 'placeholder text', 2, compute) == [.25, .5]
    assert len(calls) == 4 and not instance.local and not instance.collections
    from hermes.embeddings import FastEmbedder
    encoder = FastEmbedder()
    batches = []
    def batch(texts):
        batches.append(texts)
        return [[.25] for _ in texts]
    monkeypatch.setattr(encoder, '_embed_many', batch)
    texts = ['placeholder a', 'placeholder b']
    assert encoder.embed_many(texts) == [[.25], [.25]]
    assert batches == [texts]  # main's single CPU batch, not one inference per text.
    local = semantic_encoder.LocalEncoder()
    monkeypatch.setattr(local, 'validate', Mock(side_effect=AssertionError('C4 added validation while off')))
    monkeypatch.setattr(local, '_embed', lambda text: compute())
    assert local.embed('placeholder text') == [.25, .5]
    assert local.embed('placeholder text') == [.25, .5]
    assert len(calls) == 6


@pytest.mark.parametrize('file', ['config.yaml', 'config.za.yaml'])
def test_litellm_cache_cannot_initialize_without_explicit_setting(file, monkeypatch):
    raw = yaml.safe_load((ROOT / 'litellm' / file).read_text())
    assert raw['litellm_settings']['cache'] is False
    for value in ('', '0', 'false', 'true', 'placeholder-invalid'):
        monkeypatch.setenv('ENGINE_C1_ENABLED', value)
        config = gateway_config(monkeypatch, file)['litellm_settings']
        assert config['cache'] is False and 'cache_params' not in config
        assert not exact_cache.enabled()
    monkeypatch.setenv('ENGINE_C1_ENABLED', '1')
    config = gateway_config(monkeypatch, file)['litellm_settings']
    assert config['cache'] is True and config['cache_params']['type'] == 'redis'
    assert config['cache_params']['mode'] == 'default_off'
    assert exact_cache.enabled() and not embedding_cache.enabled()


@pytest.mark.parametrize('file', ['docker-compose.yml', 'docker-compose.za.yml'])
def test_one_setting_per_layer_is_passed_to_all_consumers_with_off_default(file):
    services = yaml.safe_load((ROOT / file).read_text())['services']
    for service, flags in {'tank': FLAGS, 'litellm': FLAGS[:1], 'hermes': FLAGS[1:2]}.items():
        for flag in flags:
            assert services[service]['environment'][flag] == '${' + flag + ':-0}'


@pytest.mark.asyncio
async def test_i8_off_never_queries_prices_or_changes_the_request(ladder, monkeypatch):
    b = ladder
    req = request(b, b.tenants[0], text='placeholder job', interactive=False, priority='standard')
    prices = AsyncMock(side_effect=AssertionError('off I8 queried prices'))
    monkeypatch.setattr(b.tank, '_batch_price', prices)
    result = await priority_queue.automatic_request(b.tank, req, {'batch_eligible': True, 'priority': 'standard'}, [], {})
    assert result is req and result.deadline is None
    prices.assert_not_awaited()
