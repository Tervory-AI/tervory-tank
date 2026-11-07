"""C5 provider formats, stable prefixes and receipt-backed savings without API calls."""
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import yaml

import prompt_cache
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, policy, request, selected_policy_protocol

boundary = boundary_fixture
ladder = ladder_fixture


def usage(provider, cached):
    if provider == 'gemini':
        return {'promptTokenCount': 100, 'candidatesTokenCount': 10, 'cachedContentTokenCount': cached}
    if provider == 'minimax':
        return {'input_tokens': 100 - cached, 'output_tokens': 10, 'cache_read_input_tokens': cached}
    field = {'deepseek': {'prompt_cache_hit_tokens': cached},
             'moonshot': {'prompt_tokens_details': {'cached_tokens': cached}},
             'stepfun': {'cached_tokens': cached}}
    return {'prompt_tokens': 100, 'completion_tokens': 10, **field[provider]}


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['deepseek', 'moonshot', 'gemini', 'minimax', 'stepfun'])
async def test_each_provider_reports_cached_tokens_and_task_hit_rate(ladder, monkeypatch, provider):
    b = ladder
    selected_policy_protocol(monkeypatch)
    monkeypatch.setattr(b.tank.semantic_cache, 'lookup', AsyncMock(return_value=None))
    monkeypatch.setattr(b.tank.semantic_cache, 'schedule', Mock())
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[{
        'model_name': 'haiku', 'litellm_params': {'model': provider + '/placeholder-model'},
        'model_info': {'input_cost_per_token': .000001, 'output_cost_per_token': .000002,
                      'cache_read_input_token_cost': .0000001, 'cache_creation_input_token_cost': .000001}}]))
    await policy(b, b.tenants[0], model='haiku', rung=1, system_prompt='placeholder stable policy',
                 cache_scope='none', semantic_cache=False, candidate_model=None, shadow_rate=0)
    memory = 'Tenant memory, most recent facts first. placeholder tenant fact'
    req = request(b, b.tenants[0], text='placeholder request')
    req = req.model_copy(update={'messages': [b.tank.Message(role='system', content=memory),
        b.tank.Message(role='system', content='placeholder stable instruction'), *req.messages]})
    class Gateway:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def post(self, url, **kwargs):
            b.sent.append(kwargs['json'])
            cached = 60 if len(b.sent) == 1 else 0
            return httpx.Response(200, headers={'x-litellm-response-cost': '.000066' if cached else '.00012'},
                json={'choices': [{'message': {'content': 'placeholder answer'}}], 'usage': usage(provider, cached)})
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', Gateway)
    selected = await b.tank.load_policy(req.task_type, req.tenant_id)
    first = await b.tank.run_route(req, _paid_policy=selected)
    second = await b.tank.run_route(req, _paid_policy=selected)
    assert [m['content'] for m in b.sent[0]['messages']] == [
        'placeholder stable policy', 'placeholder stable instruction', memory, 'placeholder request']
    assert all('cache_control' not in m for m in b.sent[0]['messages'])
    assert 'prompt_cache_options' not in b.sent[0]  # Existing automatic/default TTLs.
    assert first.tokens_in == 100 and first.tokens_out == 10
    assert first.cache_read_tokens == 60 and first.cache_hit_rate == .6
    assert second.cache_read_tokens == 0 and second.cache_hit_rate == 0
    assert first.engine['cache_layers']['C5']['saved_usd'] == pytest.approx(.000054)
    assert second.engine['cache_layers']['C5']['saved_usd'] == 0
    from engine_admin import engine_status
    status = await engine_status(b.tank, req.tenant_id)
    row = next(r for r in status['tasks'] if r['task_type'] == req.task_type)['cache_layers']['C5']
    assert row['attempts'] == 2 and row['hits'] == 1 and row['hit_rate'] == .5
    assert row['cached_tokens'] == 60 and row['token_hit_rate'] == .3
    assert row['saved_usd'] == pytest.approx(.000054) and row['unpriced_calls'] == 0
    other = await engine_status(b.tank, b.tenants[1])
    assert all(r['cache_layers']['C5']['hits'] == 0 for r in other['tasks'])


def test_cache_write_overhead_unknown_prices_and_bad_counts_are_honest():
    prices = dict(input=.000001, output=.000002, cache_read=.0000001, cache_write=.00000125)
    assert prompt_cache.statistics(prices, 100, 0, 100)['saved_usd'] == pytest.approx(-.000025)
    assert prompt_cache.statistics(prices, 100, 60, 0, multiplier=.5)['saved_usd'] == pytest.approx(.000027)
    unknown = prompt_cache.statistics({'input': .000001}, 100, 60, 0)
    assert unknown['saved_usd'] is None and unknown['unpriced_calls'] == 1 and unknown['hits'] == 1
    assert prompt_cache.cache_tokens({'prompt_tokens': 10, 'cached_tokens': 20}) == (0, 0)
    assert prompt_cache.cache_tokens({'prompt_tokens': 100, 'input_tokens_details': {'cached_tokens': 60}}) == (60, 0)
    assert prompt_cache.automatic({'provider': 'openai', 'native': 'stepfun-ai/placeholder'})
    assert prompt_cache.automatic({'provider': 'openai', 'native': 'minimax/placeholder'})


def test_both_rosters_price_automatic_cache_without_adding_storage_controls():
    for file in ('config.yaml', 'config.za.yaml'):
        rows = yaml.safe_load((Path('litellm') / file).read_text())['model_list']
        for row in rows:
            params, info = row['litellm_params'], row['model_info']
            if params['model'].split('/')[0] in {'gemini', 'deepseek', 'moonshot'}:
                assert info['prompt_cache_mode'] == 'implicit'
                assert 0 < info['cache_read_input_token_cost'] < info['input_cost_per_token']
                assert 'cache_control_injection_points' not in params
                assert 'prompt_cache_options' not in params
