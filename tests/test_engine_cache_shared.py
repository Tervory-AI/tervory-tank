"""Stage 3 reuse: C5 on every provider and shared public work, on real Tank SQL over HTTP.

The model gateway is a fake (no provider call, no key). Postgres is a disposable
database per test (test_tank_tenant_boundaries.boundary).
"""
import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
import yaml
from fastapi import FastAPI, HTTPException

import prompt_cache_providers as c5
import shared_work
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, policy, selected_policy_protocol
from tenant_db import bind_tenant_endpoints

boundary = boundary_fixture
ladder = ladder_fixture
ROOT = Path(__file__).resolve().parents[1]
# The ladder fixture replaces httpx.AsyncClient with its model fake; keep the real one.
REAL_CLIENT = httpx.AsyncClient
OFF_VALUES = [None, '', '1', 'TRUE', 'True', 'yes', ' true', 'true ']
INPUT, OUTPUT = .000001, .000002
STABLE = 'placeholder stable instruction for every call'
MEMORY = c5.MEMORY_HEAD + ' placeholder tenant fact'
FOUNDER = 'founder-fixture'

# (roster native id, usage shape) for every provider format in the LiteLLM rosters.
PROVIDERS = {
    'openai': ('openai/gpt-6-luna', 'openai'),
    'anthropic': ('anthropic/claude-haiku-5-5', 'anthropic'),
    'gemini': ('gemini/gemini-3.8-flash', 'gemini'),
    'deepseek': ('deepseek/deepseek-flash', 'deepseek'),
    'moonshot': ('moonshot/kimi-k3', 'openai'),
    'xai': ('xai/grok-4.3', 'openai'),
    'zai': ('openai/glm-5.3', 'openai'),
    'minimax': ('openai/MiniMax-M3', 'openai'),
    'stepfun': ('openai/step-3.5-flash', 'stepfun'),
    'hf-router': ('openai/meta-llama/Llama-3.1-8B-Instruct:novita', 'openai'),
    'dashscope': ('openai/qwen3.5-27b', 'openai'),
    'perplexity': ('perplexity/preset/low', 'perplexity'),
}
# Documented read rates the roster does not carry (USD per token), from prompt_cache_providers.
DOCUMENTED = {'xai': .2e-6, 'zai': .26e-6, 'minimax': .06e-6, 'stepfun': .02e-6}


def set_env(monkeypatch, name, value):
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)


def usage(shape, cached):
    if shape == 'gemini':
        return {'promptTokenCount': 2000, 'candidatesTokenCount': 10, 'cachedContentTokenCount': cached}
    if shape == 'anthropic':
        return {'prompt_tokens': 2000, 'completion_tokens': 10, 'cache_read_input_tokens': cached}
    if shape == 'deepseek':
        return {'prompt_tokens': 2000, 'completion_tokens': 10, 'prompt_cache_hit_tokens': cached}
    if shape == 'stepfun':
        return {'prompt_tokens': 2000, 'completion_tokens': 10, 'cached_tokens': cached}
    if shape == 'perplexity':
        return {'prompt_tokens': 2000, 'completion_tokens': 10, 'cache_read_input_tokens': cached}
    return {'prompt_tokens': 2000, 'completion_tokens': 10, 'prompt_tokens_details': {'cached_tokens': cached}}


def roster(monkeypatch, b, native, *, cache_read=None):
    info = {'input_cost_per_token': INPUT, 'output_cost_per_token': OUTPUT}
    if cache_read is not None:
        info['cache_read_input_token_cost'] = cache_read
    monkeypatch.setattr(b.tank, '_roster_models', AsyncMock(return_value=[
        {'model_name': 'haiku', 'litellm_params': {'model': native}, 'model_info': info}]))


def gateway(monkeypatch, b, shape='openai', cached=lambda n: 0, delay=0.):
    b.sent = []

    class Gateway:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            b.sent.append(kwargs['json'])
            n = len(b.sent)
            if delay:
                await asyncio.sleep(delay)
            text = kwargs['json']['messages'][-1]['content']
            content = 'placeholder public answer' if '"source_version"' in text else 'placeholder client answer'
            return httpx.Response(200, headers={'content-type': 'application/json', 'x-litellm-response-cost': '.0021'},
                                  json={'choices': [{'message': {'content': content}}], 'usage': usage(shape, cached(n))},
                                  request=httpx.Request('POST', url))

    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', Gateway)


async def prepare(b, monkeypatch, native='openai/gpt-6-luna', **roster_kwargs):
    selected_policy_protocol(monkeypatch)
    monkeypatch.setattr(b.tank.semantic_cache, 'lookup', AsyncMock(return_value=None))
    monkeypatch.setattr(b.tank.semantic_cache, 'schedule', Mock())
    roster(monkeypatch, b, native, **roster_kwargs)
    for tenant in b.tenants:
        await policy(b, tenant, model='haiku', rung=1, system_prompt='placeholder stable policy',
                     cache_scope='none', semantic_cache=False, candidate_model=None, shadow_rate=0)


def body(tenant, text='placeholder request', memory=MEMORY):
    messages = ([{'role': 'system', 'content': memory}] if memory else []) + [
        {'role': 'system', 'content': STABLE}, {'role': 'user', 'content': text}]
    return {'tenant_id': str(tenant), 'agent': 'base', 'task_type': 'base.normalize', 'messages': messages}


async def route(b, payload):
    response = await b.client.post('/v1/route', json=payload)
    assert response.status_code == 200, response.text
    return response.json()


async def receipts(b, tenant):
    async with b.pool.acquire() as conn:
        rows = await conn.fetch('SELECT ledger_id,detail FROM tank.engine_receipts WHERE tenant_id=$1', tenant)
    return {r['ledger_id']: json.loads(r['detail']) if isinstance(r['detail'], str) else r['detail'] for r in rows}


def stable(response):
    text = json.dumps({k: v for k, v in response.items() if k != 'latency_ms'}, sort_keys=True)
    text = text.replace(response['ledger_id'], 'placeholder-ledger-id')
    if (response.get('execution') or {}).get('ledger_id'):
        text = text.replace(response['execution']['ledger_id'], 'placeholder-ledger-id')
    return json.loads(text)


# ---------------------------------------------------------------- unset = main

@pytest.mark.asyncio
@pytest.mark.parametrize('value', OFF_VALUES)
async def test_unset_settings_keep_main_behaviour_at_the_http_boundary(ladder, monkeypatch, value):
    b = ladder
    set_env(monkeypatch, c5.SETTING, value)
    set_env(monkeypatch, shared_work.SETTING, value)
    await prepare(b, monkeypatch, 'xai/grok-4.3')
    gateway(monkeypatch, b, cached=lambda n: 600)
    tenant = b.tenants[0]
    first = await route(b, body(tenant))
    sent_first = list(b.sent)
    # The same call with every new hook replaced by the identity.
    async def same(rt, req, answer):
        return answer
    async def nothing(*args, **kwargs):
        return {}
    monkeypatch.setattr(c5, 'receipt', same)
    monkeypatch.setattr(c5, 'request_options', nothing)
    monkeypatch.setattr(c5, 'fill', lambda prices: prices)
    second = await route(b, body(tenant))
    assert stable(first) == stable(second)
    assert b.sent[1] == sent_first[0] and 'prompt_cache_key' not in sent_first[0]
    for detail in (await receipts(b, tenant)).values():
        assert 'prompt_cache' not in detail and 'reuse' not in detail and 'shared_work' not in detail
    # xAI hits stay unpriced exactly as on main: the roster has no xAI cache rate.
    assert first['engine']['cache_layers']['C5']['saved_usd'] is None
    assert first['engine']['cache_layers']['C5']['unpriced_calls'] == 1
    # No shared route, no shared table, and the public entry point refuses.
    assert shared_work.build_router(b.tank).routes == []
    unknown = await b.client.post('/v1/engine/shared/nowhere', json={})
    for path in ('/v1/engine/shared/route', '/v1/engine/shared/founder/source'):
        for headers in ({}, b.native_headers(FOUNDER, 'org_admin')):
            response = await b.client.post(path, json={}, headers=headers)
            assert (response.status_code, response.json()) == (unknown.status_code, unknown.json())
    with pytest.raises(HTTPException) as refused:
        await shared_work.public_part(b.tank, tenant, 'base', None, 'anything', {}, 'v1')
    assert refused.value.status_code == 404
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT to_regclass('tank.engine_shared_work')") is None
        assert await conn.fetchval("SELECT to_regclass('tank.engine_shared_sources')") is None
    # The documented-rate fill and the cache key are inert too.
    prices = {'provider': 'xai', 'native': 'grok-4.3', 'input': INPUT, 'output': OUTPUT}
    assert c5.fill(prices) is prices


# ---------------------------------------------------------------- C5 on every provider

@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(PROVIDERS))
async def test_prefix_is_byte_identical_across_calls_in_each_provider_format(ladder, monkeypatch, name):
    b = ladder
    monkeypatch.setenv(c5.SETTING, 'true')
    native, shape = PROVIDERS[name]
    await prepare(b, monkeypatch, native)
    gateway(monkeypatch, b, shape)
    first = await route(b, body(b.tenants[0], 'placeholder request one'))
    second = await route(b, body(b.tenants[0], 'placeholder request two, longer and different'))
    changed = await route(b, body(b.tenants[0], 'placeholder request three', memory=MEMORY + ' and a newer fact'))
    other = await route(b, body(b.tenants[1], 'placeholder request one'))
    # Fixed system text, then the tenant's memory, then the request.
    assert [m['content'] for m in b.sent[0]['messages']] == [
        'placeholder stable policy', STABLE, MEMORY, 'placeholder request one']
    fmt = c5.provider({'provider': native.partition('/')[0], 'native': native.partition('/')[2]}).wire
    for wire in ('openai', 'anthropic', 'gemini'):
        prefixes = []
        for sent in b.sent:
            fixed, memory, request = c5.split(sent['messages'])
            prefixes.append((c5.wire(wire, fixed), c5.wire(wire, [*fixed, *memory])))
        assert prefixes[0] == prefixes[1]                  # same tenant, new request: identical bytes
        assert prefixes[2][0] == prefixes[0][0]            # new memory: fixed text still identical
        assert prefixes[2][1] != prefixes[0][1]
        assert prefixes[3][0] == prefixes[0][0]            # another tenant shares the fixed text
    lines = [r['engine']['prompt_cache']['prefix'] for r in (first, second, changed, other)]
    assert all(line['format'] == fmt for line in lines)
    assert lines[0]['prefix_sha256'] == lines[1]['prefix_sha256'] == lines[3]['prefix_sha256']
    assert lines[2]['fixed_sha256'] == lines[0]['fixed_sha256'] != ''
    assert lines[2]['prefix_sha256'] != lines[0]['prefix_sha256']
    # A cache key only where the provider documents one; per tenant and task, never the tenant id.
    keys = [sent.get('prompt_cache_key') for sent in b.sent]
    if name in {'openai', 'xai'}:
        assert keys[0] == keys[1] == keys[2] != keys[3]
        assert all(str(t) not in json.dumps(b.sent) for t in b.tenants)
    else:
        assert keys == [None] * 4
    assert all('cache_control' not in m for sent in b.sent for m in sent['messages'])


@pytest.mark.asyncio
@pytest.mark.parametrize('name', sorted(PROVIDERS))
async def test_cached_tokens_and_discount_on_every_receipt(ladder, monkeypatch, name):
    b = ladder
    monkeypatch.setenv(c5.SETTING, 'true')
    native, shape = PROVIDERS[name]
    roster_rate = {'openai': .1e-6, 'anthropic': .1e-6, 'gemini': .1e-6, 'deepseek': .1e-6, 'moonshot': .1e-6}.get(name)
    await prepare(b, monkeypatch, native, cache_read=roster_rate)
    gateway(monkeypatch, b, shape, cached=lambda n: 1200 if n == 2 else 0)
    first = await route(b, body(b.tenants[0], 'placeholder request one'))
    second = await route(b, body(b.tenants[0], 'placeholder request two'))
    assert first['engine']['prompt_cache']['cached_tokens'] == 0
    line = second['engine']['prompt_cache']
    assert line['cached_tokens'] == second['cache_read_tokens'] == 1200
    assert line['provider'] == name and line['checked'] == c5.CHECKED
    rate = roster_rate or DOCUMENTED.get(name)
    if rate is None:
        # No documented price (HF router, DashScope open Qwen, Perplexity presets): never invented.
        assert line['discount_usd'] is None and line['rate_source'] is None
        assert second['engine']['reuse']['would_have_cost_usd'] is None
    else:
        assert line['rate_source'] == ('roster' if roster_rate else 'provider_docs')
        assert line['sources'] and all(s.startswith('https://') for s in line['sources'])
        assert line['discount_usd'] == pytest.approx(1200 * (INPUT - rate))
        reuse = second['engine']['reuse']
        assert reuse['cost_usd'] == pytest.approx(.0021)
        assert reuse['would_have_cost_usd'] == pytest.approx(.0021 + 1200 * (INPUT - rate))
        assert reuse['prompt_cache'] == {'cached_tokens': 1200, 'saved_usd': pytest.approx(1200 * (INPUT - rate))}
        assert reuse['shared_store'] == {'served': False, 'saved_usd': 0.}
    stored = (await receipts(b, b.tenants[0]))[uuid.UUID(second['ledger_id'])]
    assert stored['prompt_cache']['cached_tokens'] == 1200
    assert stored['reuse'] == json.loads(json.dumps(second['engine']['reuse']))
    assert stored['cache_layers']['C5']['cached_tokens'] == 1200
    # The other tenant's receipts are untouched.
    assert await receipts(b, b.tenants[1]) == {}


def test_every_roster_route_has_a_documented_provider_entry():
    for file in ('config.yaml', 'config.za.yaml'):
        rows = yaml.safe_load((ROOT / 'litellm' / file).read_text())['model_list']
        for row in rows:
            kind, _, native = row['litellm_params']['model'].partition('/')
            found = c5.provider({'provider': kind, 'native': native})
            assert found is not None, row['model_name']
            if found.mode not in {'not_applicable'}:
                assert found.sources and all(s.startswith('https://') for s in found.sources), found.name
            # Tank adds no marker; markers stay per deployment in the roster, as on main.
            if 'cache_control_injection_points' in row['litellm_params']:
                assert found.name in {'openai', 'anthropic'}
    # Longest model prefix wins: GLM-5.3 is never priced as GLM-5.
    assert c5._model_rate(c5.PROVIDERS['zai'].read_usd, 'glm-5.3') == pytest.approx(.26e-6)
    assert c5._model_rate(c5.PROVIDERS['zai'].read_usd, 'glm-5') == pytest.approx(.2e-6)
    assert c5._model_rate(c5.PROVIDERS['minimax'].read_usd, 'MiniMax-M3.1-Flash') == pytest.approx(.015e-6)


# ---------------------------------------------------------------- shared public work

PUBLIC = shared_work.PublicTask('fixture.public', 'fixture.regulations', ('rule', 'state', 'year'))


async def shared_setup(b, monkeypatch, *, delay=0.):
    monkeypatch.setenv(shared_work.SETTING, 'true')
    monkeypatch.setitem(shared_work.PUBLIC, 'regulation.summary', PUBLIC)
    shared_work._ready.clear()
    await prepare(b, monkeypatch)
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy SELECT (jsonb_populate_record(NULL::tank.policy,
            to_jsonb(p)||$1::jsonb)).* FROM tank.policy p WHERE task_type='base.normalize' AND tenant_id IS NULL""",
            json.dumps({'task_type': 'fixture.public', 'model': 'haiku', 'rung': 1, 'cache_scope': 'none',
                        'semantic_cache': False, 'candidate_model': None, 'shadow_rate': 0,
                        'system_prompt': 'placeholder public policy'}))
    gateway(monkeypatch, b, delay=delay)
    return api_for(b)


def api_for(b):
    app = FastAPI()
    app.include_router(shared_work.build_router(b.tank))
    bind_tenant_endpoints(app)
    return REAL_CLIENT(transport=httpx.ASGITransport(app=app), base_url='http://tank', headers={'X-Tank-Key': b.key})


def ask(tenant, *, version='2026-11', rule='  Part 478   record keeping ', client=None, **extra):
    payload = {'tenant_id': str(tenant), 'agent': 'base', 'public_task': 'regulation.summary',
               'public_input': {'rule': rule, 'state': 'MA', 'year': 2026, **extra}, 'source_version': version}
    if client:
        payload.update(task_type='base.normalize', messages=[{'role': 'user', 'content': client}])
    return payload


def public_calls(b):
    return [s for s in b.sent if '"source_version"' in s['messages'][-1]['content']]


async def shared_rows(b):
    async with b.pool.acquire() as conn:
        if await conn.fetchval("SELECT to_regclass('tank.engine_shared_work')") is None:
            return []  # Refused before first use: nothing was even created.
        return [dict(r) for r in await conn.fetch('SELECT * FROM tank.engine_shared_work')]


@pytest.mark.asyncio
async def test_two_tenants_asking_the_same_public_question_compute_it_once(ladder, monkeypatch):
    b = ladder
    async with await shared_setup(b, monkeypatch, delay=.2) as api:
        # Concurrent first asks, with different spacing: one computation, one waiter.
        first, second = await asyncio.gather(
            api.post('/v1/engine/shared/route', json=ask(b.tenants[0], client='placeholder client zero')),
            api.post('/v1/engine/shared/route', json=ask(b.tenants[1], rule='Part 478 record   keeping',
                                                             client='placeholder client one')))
        third = await api.post('/v1/engine/shared/route', json=ask(b.tenants[1]))
    for response in (first, second, third):
        assert response.status_code == 200, response.text
    assert len(public_calls(b)) == 1
    assert len(b.sent) == 3                      # one public computation + two client parts
    results = [r.json() for r in (first, second, third)]
    computed = [r for r in results if not r['public']['served_from_store']]
    served = [r for r in results if r['public']['served_from_store']]
    assert len(computed) == 1 and len(served) == 2
    assert computed[0]['public']['cost_usd'] == pytest.approx(.0021)
    for result in served:
        assert result['public']['cost_usd'] == 0
        assert result['public']['content'] == 'placeholder public answer'
        assert result['reuse']['shared_store'] == {'served': True, 'saved_usd': pytest.approx(.0021)}
    # The client part ran for each tenant with the public result as fixed reference text first.
    clients = [s for s in b.sent if s not in public_calls(b)]
    for sent in clients:
        assert sent['messages'][0]['content'] == 'placeholder stable policy'
        assert sent['messages'][1]['content'].startswith(shared_work.REFERENCE_HEAD)
        assert sent['messages'][1]['content'].endswith('placeholder public answer')
    assert {s['messages'][-1]['content'] for s in clients} == {'placeholder client zero', 'placeholder client one'}
    # Per-call receipt: shared store and prompt cache against would-have-cost.
    only_public = results[2]
    assert only_public['client'] is None
    assert only_public['reuse']['cost_usd'] == 0
    assert only_public['reuse']['would_have_cost_usd'] == pytest.approx(.0021)
    stored = await receipts(b, b.tenants[1])
    assert stored[uuid.UUID(only_public['public']['ledger_id'])]['reuse']['shared_store']['served'] is True
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT cost_usd,rung,cache_hit FROM tank.ledger WHERE id=$1',
                                  uuid.UUID(only_public['public']['ledger_id']))
    assert (float(row['cost_usd']), row['rung'], row['cache_hit']) == (0, 4, True)
    rows = await shared_rows(b)
    assert len(rows) == 1 and rows[0]['hits'] == 2 and rows[0]['state'] == 'ready'
    assert json.loads(rows[0]['input']) == {'rule': 'Part 478 record keeping', 'state': 'MA', 'year': 2026}


PROBES = [
    ('tenant id', lambda b: {'rule': 'rules for ' + str(b.tenants[0])}),
    ('tenant id upper case', lambda b: {'rule': str(b.tenants[0]).upper()}),
    ('any uuid', lambda b: {'rule': str(uuid.uuid4())}),
    ('e-mail', lambda b: {'rule': 'ask jane.doe@example.com'}),
    ('national id', lambda b: {'rule': '8001015009087'}),
    ('matter reference', lambda b: {'rule': 'placeholder-matter-77'}),
    ('list value', lambda b: {'state': ['MA', str(b.tenants[0])]}),
    ('undeclared field', lambda b: {'note': 'x'}),
    ('tenant field', lambda b: {'tenant_id': str(b.tenants[0])}),
    ('client field', lambda b: {'client_name': 'x'}),
    ('user field', lambda b: {'user': 'x'}),
]


@pytest.mark.asyncio
async def test_tenant_data_never_enters_the_shared_store(ladder, monkeypatch):
    b = ladder
    async with await shared_setup(b, monkeypatch) as api:
        for label, probe in PROBES:
            payload = ask(b.tenants[0], case_ref='placeholder-matter-77')
            payload['public_input'] = {**payload['public_input'], **probe(b)}
            response = await api.post('/v1/engine/shared/route', json=payload)
            assert response.status_code == 422, (label, response.text)
        assert b.sent == [] and await shared_rows(b) == []
        # A full run with tenant secrets in the client part: none of it reaches the store or the
        # public computation.
        secret = 'placeholder tenant secret ' + uuid.uuid4().hex
        response = await api.post('/v1/engine/shared/route', json=ask(b.tenants[0], client=secret))
        assert response.status_code == 200, response.text
    public = public_calls(b)
    assert len(public) == 1
    for marker in (secret, str(b.tenants[0]), STABLE, MEMORY):
        assert marker not in json.dumps(public)
        assert marker not in json.dumps(await shared_rows(b), default=str)
    # The public computation used the platform policy, not the tenant's override.
    assert public[0]['messages'][0]['content'] == 'placeholder public policy'
    # The store has no column a tenant could be written into.
    async with b.pool.acquire() as conn:
        columns = {r['column_name'] for r in await conn.fetch(
            "SELECT column_name FROM information_schema.columns WHERE table_schema='tank' "
            "AND table_name IN ('engine_shared_work','engine_shared_sources')")}
    assert not any(shared_work.tenant_field(c) for c in columns)
    assert not {'tenant_id', 'tenant', 'user_id', 'region'} & columns


def test_no_public_task_can_declare_a_tenant_identifying_field():
    # The shipped list is empty, and any entry added later is held to the same rule.
    assert shared_work.PUBLIC == {}
    for spec in shared_work.PUBLIC.values():
        assert not any(shared_work.tenant_field(f) for f in spec.fields)
    for field in ('tenant_id', 'user_id', 'case_ref', 'email', 'client_name', 'customer_phone',
                  'account_number', 'org', 'matter', 'session_id', 'memory', 'owner', 'agent', 'api_key'):
        with pytest.raises(ValueError):
            shared_work.PublicTask('fixture.public', 'fixture.source', ('rule', field))
    for field in ('rule', 'state', 'year', 'ffl_number', 'sku', 'package', 'route', 'zip'):
        assert not shared_work.tenant_field(field)


@pytest.mark.asyncio
async def test_entries_expire_when_the_source_changes(ladder, monkeypatch):
    b = ladder
    async with await shared_setup(b, monkeypatch) as api:
        assert (await api.post('/v1/engine/shared/route', json=ask(b.tenants[0]))).status_code == 200
        assert (await api.post('/v1/engine/shared/route', json=ask(b.tenants[1]))).json()['public']['served_from_store']
        assert len(public_calls(b)) == 1
        change = {'source': PUBLIC.source, 'version': '2026-12'}
        for headers in ({}, b.native_headers('ordinary-user'), b.native_headers('ordinary-admin', 'org_admin')):
            assert (await api.post('/v1/engine/shared/founder/source', json=change, headers=headers)).status_code in {401, 403}
        changed = await api.post('/v1/engine/shared/founder/source', json=change, headers=b.native_headers(FOUNDER, 'org_admin'))
        assert changed.status_code == 200 and changed.json()['expired'] == 1
        stale = await api.post('/v1/engine/shared/route', json=ask(b.tenants[1]))
        assert stale.status_code == 409 and stale.json()['detail']['current'] == '2026-12'
        fresh = await api.post('/v1/engine/shared/route', json=ask(b.tenants[1], version='2026-12'))
        again = await api.post('/v1/engine/shared/route', json=ask(b.tenants[0], version='2026-12'))
    assert fresh.json()['public']['served_from_store'] is False
    assert again.json()['public']['served_from_store'] is True
    assert len(public_calls(b)) == 2
    rows = {r['source_version']: r for r in await shared_rows(b)}
    assert rows['2026-11']['expires_at'] <= rows['2026-12']['computed_at']
    # Past the task's maximum age an entry is worked out again too.
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.engine_shared_work SET expires_at=now()-interval '1 second'")
    async with api_for(b) as api:
        assert (await api.post('/v1/engine/shared/route', json=ask(b.tenants[0], version='2026-12'))).json()['public']['served_from_store'] is False
    assert len(public_calls(b)) == 3


@pytest.mark.asyncio
async def test_failed_public_computation_releases_its_lease(ladder, monkeypatch):
    b = ladder
    async with await shared_setup(b, monkeypatch) as api:
        async def broken(*args, **kwargs):
            raise HTTPException(502, 'placeholder gateway failure')
        monkeypatch.setattr(shared_work, '_compute', broken)
        assert (await api.post('/v1/engine/shared/route', json=ask(b.tenants[0]))).status_code == 502
        assert await shared_rows(b) == []
