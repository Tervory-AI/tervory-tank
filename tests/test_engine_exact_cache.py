"""Offline C1 protocol proof against real Tank SQL, with only the model faked."""
from contextvars import ContextVar
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import yaml

import exact_cache
import product_identity
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, policy, request, selected_policy_protocol

boundary = boundary_fixture
ladder = ladder_fixture


def set_user(monkeypatch, tenant, user='placeholder-user-a'):
    actor = product_identity.User(str(tenant), user, 'member') if user else None
    monkeypatch.setattr(product_identity, 'current', ContextVar('placeholder-cache-actor', default=actor))


async def setup(b, monkeypatch):
    selected_policy_protocol(monkeypatch)
    monkeypatch.setattr(b.tank.semantic_cache, 'lookup', AsyncMock(return_value=None))
    monkeypatch.setattr(b.tank.semantic_cache, 'schedule', Mock())
    for tenant in b.tenants:
        await policy(b, tenant, model='haiku', rung=1, cache_scope='tenant', cache_ttl_s=60,
                     semantic_cache=False, candidate_model=None, shadow_rate=0)
    set_user(monkeypatch, b.tenants[0])
    return request(b, b.tenants[0], text='placeholder input for an exact answer')


async def run(b, req):
    return await b.tank.run_route(req, _paid_policy=await b.tank.load_policy(req.task_type, req.tenant_id))


@pytest.mark.asyncio
async def test_exact_repeat_is_free_and_user_and_tenant_cannot_hit(ladder, monkeypatch):
    b = ladder
    req = await setup(b, monkeypatch)
    first = await run(b, req)
    repeat = await run(b, req)
    assert first.cost_usd == .001 and repeat.cost_usd == 0
    assert repeat.cache_layer == 'C1' and repeat.cache_backend == 'tank-sql'
    assert len(b.sent) == 1 and repeat.ledger_id != first.ledger_id
    options = b.sent[0]['cache']
    assert options['use-cache'] and options['ttl'] == options['s-maxage'] == 60
    assert 'placeholder-user' not in options['namespace']
    set_user(monkeypatch, req.tenant_id, 'placeholder-user-b')
    assert (await run(b, req)).cache_layer is None
    assert b.sent[-1]['cache']['namespace'] != options['namespace']
    other = req.model_copy(update={'tenant_id': b.tenants[1]})
    set_user(monkeypatch, other.tenant_id)
    assert (await run(b, other)).cache_layer is None
    assert b.sent[-1]['cache']['namespace'] != options['namespace']
    assert len(b.sent) == 3
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT cost_usd,cache_hit FROM tank.ledger WHERE tenant_id=$1 AND id=$2',
                                  req.tenant_id, repeat.ledger_id)
        assert row['cost_usd'] == 0 and row['cache_hit']
        expiry = await conn.fetchval('SELECT max(extract(epoch FROM expires_at-now())) FROM tank.route_cache WHERE tenant_id=$1', req.tenant_id)
        assert 0 < expiry <= 60
    from engine_admin import engine_status
    status = await engine_status(b.tank, req.tenant_id)
    c1 = next(r for r in status['tasks'] if r['task_type'] == req.task_type)['cache_layers']['C1']
    assert c1['hits'] == 1 and c1['attempts'] == 3
    assert c1['hit_rate'] == pytest.approx(1 / 3) and c1['saved_usd'] > 0
    assert (await exact_cache.status(b.tank, other.tenant_id))[req.task_type]['C1']['hits'] == 0


@pytest.mark.asyncio
async def test_gateway_hit_receipt_uses_actual_cache_signal(ladder, monkeypatch):
    b = ladder
    req = await setup(b, monkeypatch)
    stored = set()

    class Gateway:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            body = kwargs['json']
            b.sent.append(body)
            options = body['cache']
            key = options.get('namespace')
            hit = key in stored and not options.get('no-cache')
            if key:
                stored.add(key)
            return httpx.Response(200, headers={'x-litellm-response-cost': '0' if hit else '.001',
                **({'x-tervory-cache-layer': 'C1'} if hit else {})},
                json={'choices': [{'message': {'content': 'placeholder answer'}}],
                      'usage': {'prompt_tokens': 20, 'completion_tokens': 10}})

    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', Gateway)
    first = await run(b, req)
    # A Tank cache eviction must still allow the gateway's independent cache.
    async with b.pool.acquire() as conn:
        await conn.execute('DELETE FROM tank.route_cache WHERE tenant_id=$1', req.tenant_id)
    hit = await run(b, req)
    assert first.cost_usd == .001 and hit.cost_usd == 0
    assert hit.cache_layer == 'C1' and hit.cache_backend == 'litellm'
    assert hit.rung == 4 and hit.execution is None
    assert hit.cache_read_tokens == hit.cache_write_tokens == 0
    assert hit.tokens_in == 20 and hit.tokens_out == 10
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT cache_hit FROM tank.ledger WHERE id=$1 AND tenant_id=$2', hit.ledger_id, req.tenant_id)
        await conn.execute("UPDATE tank.ledger SET feedback='rejected' WHERE id=$1 AND tenant_id=$2", hit.ledger_id, req.tenant_id)
    refreshed = await run(b, req)
    assert refreshed.cost_usd == .001 and refreshed.cache_layer is None
    assert b.sent[-1]['cache']['no-cache'] is True


@pytest.mark.asyncio
async def test_disabled_expired_and_unsigned_caches_do_not_reuse_personal_answers(ladder, monkeypatch):
    b = ladder
    req = await setup(b, monkeypatch)
    await run(b, req)
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.route_cache SET expires_at=now()-interval '1 second' WHERE tenant_id=$1", req.tenant_id)
    assert (await run(b, req)).cache_layer is None
    set_user(monkeypatch, req.tenant_id, None)
    assert (await run(b, req)).cache_layer is None
    assert b.sent[-1]['cache']['no-store'] is True
    set_user(monkeypatch, req.tenant_id)
    for changes in ("cache_ttl_s=0", "cache_ttl_s=60, cache_scope='none'"):
        async with b.pool.acquire() as conn:
            await conn.execute('UPDATE tank.policy SET ' + changes + ' WHERE tenant_id=$1 AND task_type=$2', req.tenant_id, req.task_type)
        for _ in range(2):
            assert (await run(b, req)).cache_layer is None
            assert b.sent[-1]['cache']['use-cache'] is False


def test_key_changes_with_model_input_policy_and_scope(monkeypatch):
    req = SimpleNamespace(tenant_id='placeholder-tenant', task_type='placeholder-task', case_ref=None)
    set_user(monkeypatch, req.tenant_id)
    pol = {'cache_scope': 'tenant', 'cache_ttl_s': 30}
    key = exact_cache.request_options(req, pol, ('placeholder-context', 'placeholder-input', ''), 'placeholder-model')
    for identity, model in [(('placeholder-context', 'different-input', ''), 'placeholder-model'),
                            (('different-context', 'placeholder-input', ''), 'placeholder-model'),
                            (('placeholder-context', 'placeholder-input', ''), 'different-model')]:
        assert exact_cache.request_options(req, pol, identity, model) != key
    for options in ({'safe': False}, {'streaming': True}):
        assert not exact_cache.request_options(req, pol, ('a', 'b', ''), 'placeholder-model', **options)['cache']['use-cache']
    set_user(monkeypatch, 'placeholder-foreign-tenant')
    assert not exact_cache.request_options(req, pol, ('a', 'b', ''), 'placeholder-model')['cache']['use-cache']


@pytest.mark.asyncio
async def test_gateway_callback_and_both_rosters_default_off(monkeypatch):
    # Tank's test environment intentionally has no provider SDK; fake only the
    # logger base class, and execute the production callback unchanged.
    base = ModuleType('litellm.integrations.custom_logger')
    base.CustomLogger = object
    monkeypatch.setitem(sys.modules, 'litellm.integrations.custom_logger', base)
    spec = importlib.util.spec_from_file_location('placeholder_response_cache', Path('litellm/response_cache.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    hook = module.callback.async_post_call_response_headers_hook
    for hit, enabled in ((False, True), (True, False), (True, True)):
        headers = await hook({'cache': {'use-cache': enabled}}, None, SimpleNamespace(_hidden_params={'cache_hit': hit}))
        assert headers == ({'x-tervory-cache-layer': 'C1', 'x-litellm-response-cost': '0'} if hit and enabled else {})
    for name in ('config.yaml', 'config.za.yaml'):
        config = yaml.safe_load((Path('litellm') / name).read_text())['litellm_settings']
        assert config['cache'] and config['cache_params']['type'] == 'redis'
        assert config['cache_params']['mode'] == 'default_off'
        assert config['callbacks'] == ['tenant_traces.callback']
        assert config['cache_params']['supported_call_types'] == ['acompletion']
    assert 'response_cache.py' in Path('litellm/Dockerfile').read_text()
    assert 'TenantLangfuseCallback(ResponseCacheMixin, CustomLogger)' in Path('litellm/tenant_traces.py').read_text()


@pytest.mark.asyncio
async def test_policy_api_round_trips_task_ttl_and_rejects_bad_values(ladder):
    b = ladder
    headers = b.native_headers('founder-fixture', 'org_admin')
    body = {'task_type': 'placeholder.cache', 'tenant_id': str(b.tenants[0]), 'model': 'haiku',
            'cache_scope': 'tenant', 'cache_ttl_s': 123}
    result = await b.client.put('/v1/policy/placeholder.cache', json=body, headers=headers)
    assert result.status_code == 200, result.text
    row = await b.tank.load_policy('placeholder.cache', b.tenants[0])
    assert row['cache_ttl_s'] == 123
    for invalid in (-1, 2592001):
        result = await b.client.put('/v1/policy/placeholder.cache', json={**body, 'cache_ttl_s': invalid}, headers=headers)
        assert result.status_code == 422
