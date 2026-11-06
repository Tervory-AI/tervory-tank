"""The serving ladder, real SQL and optional cloud-local CPU inference."""
import json
import os
from urllib.parse import urlsplit
from types import SimpleNamespace

import httpx
import pytest

import engine_ladder as engine
from test_tank_tenant_boundaries import boundary  # noqa: F401


def enable_local(monkeypatch):
    monkeypatch.setenv('ENGINE_LOCAL_URL', os.environ.get('ENGINE_LOCAL_URL') or 'http://127.0.0.1:18089')
    monkeypatch.setenv('ENGINE_LARGE_URL', os.environ.get('ENGINE_LARGE_URL') or 'http://127.0.0.1:18090')


def test_rung_order_and_exact_eval(monkeypatch):
    enable_local(monkeypatch)
    assert engine.order({'model': 'skill:base.extract@2.0.0', 'escalation_model': 'sol'}) == [
        'skill:base.extract@2.0.0', 'local', 'local-large', 'gpt-oss-small', 'qwen-small', 'gpt-oss', 'sol']
    assert engine.score('billing', 'not billing', 'exact') == 0
    assert engine.score({'label': 'billing'}, '{"label":"billing"}', 'exact') == 1


@pytest.mark.asyncio
async def test_only_failed_evals_climb(monkeypatch):
    enable_local(monkeypatch)
    async def cases(*args):
        return [{'input': 'fixture'}]
    async def roster():
        return [{'name': name} for name in (*engine.LOCAL, *engine.OPEN, 'sol')]
    checked = []
    async def evaluate(rt, req, policy, model, *args):
        checked.append(model)
        return {'local': .98, 'local-large': 1}[model]
    monkeypatch.setattr(engine, 'cases', cases)
    monkeypatch.setattr(engine, 'evaluate', evaluate)
    result = await engine.select(SimpleNamespace(list_models=roster), None, {'model': 'sol'})
    assert checked == ['local', 'local-large'] and result['model'] == 'local-large'
    checked.clear()
    async def unknown(*args):
        checked.append(args[3])
        return None
    monkeypatch.setattr(engine, 'evaluate', unknown)
    assert (await engine.select(SimpleNamespace(list_models=roster), None, {'model': 'sol'}))['model'] == 'local'
    assert checked == ['local']


@pytest.mark.asyncio
async def test_eval_cases_do_not_cross_tenants(boundary):  # noqa: F811
    b = boundary
    for i, tenant in enumerate(b.tenants):
        req = SimpleNamespace(tenant_id=tenant, task_type='fixture.boundary')
        rows = await engine.cases(b.tank, req)
        assert len(rows) == i + 1
        assert all(row['input']['text'] == f'client secret {i}' for row in rows)


async def setup_engine(b, monkeypatch):
    enable_local(monkeypatch)
    monkeypatch.setattr(b.tank, '_roster_cache', None)
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy(task_type,model,system_prompt,max_tokens_out,cache_scope)
            VALUES('engine.classify','luna','Return exactly billing or technical, with no explanation.',32,'tenant')""")
    return b.tank.RouteRequest(tenant_id=b.tenants[0], task_type='engine.classify',
        messages=[b.tank.Message(role='user', content='Classify: I was charged twice.')])


def local_gateway(b, monkeypatch):
    """Only local models can leave this test process; paid models are fake."""
    original = httpx.AsyncClient
    calls = []
    b.model_requests = []
    async def dispatch(request):
        data = json.loads(request.content)
        b.model_requests.append(data)
        calls.append(data['model'])
        if data['model'] in engine.LOCAL:
            base = os.environ['ENGINE_LOCAL_URL'] if data['model'] == 'local' else os.environ['ENGINE_LARGE_URL']
            assert urlsplit(base).hostname in {'127.0.0.1', '::1'}
            data.pop('disable_fallbacks', None)
            data['temperature'] = 0
            async with original(trust_env=False, timeout=120) as client:
                response = await client.post(base + request.url.path, json=data)
            response.headers['x-litellm-response-cost'] = '0'
            response.headers['x-litellm-model-group'] = data['model']
            return response
        return httpx.Response(200, headers={'x-litellm-response-cost': '0.001',
            'x-litellm-model-group': data['model']}, json={'choices': [{'message': {'content': 'billing'}}],
            'usage': {'prompt_tokens': 40, 'completion_tokens': 2}})
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(dispatch), **kw))
    return calls


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('ENGINE_LOCAL_URL'), reason='real cloud-local llama.cpp server required')
async def test_classify_real_local_zero_with_receipt(boundary, monkeypatch):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    calls = local_gateway(b, monkeypatch)
    answer = await b.tank.run_route(req)
    assert answer.content.strip().lower() == 'billing'
    assert answer.model == 'local' and answer.cost_usd == 0
    assert answer.engine['would_have_cost_usd'] > 0
    assert calls == ['local']
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.engine_receipts WHERE tenant_id=$1', b.tenants[0]) == 1
        assert await conn.fetchval('SELECT count(*) FROM tank.engine_receipts WHERE tenant_id=$1', b.tenants[1]) == 0


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('ENGINE_LOCAL_URL'), reason='real cloud-local llama.cpp server required')
async def test_local_does_not_enter_a_paid_provider_batch(boundary, monkeypatch):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    calls = local_gateway(b, monkeypatch)
    req = req.model_copy(update={'priority': 'offpeak'})
    answer = await b.tank.run_route(req)
    assert isinstance(answer, b.tank.RouteResponse) and answer.cost_usd == 0
    req = req.model_copy(update={'priority': 'batch', 'interactive': False})
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET batch_eligible=true WHERE task_type='engine.classify'")
    monkeypatch.setenv('TANK_BATCH_MIN', '1')
    result = await b.tank.route_batch(b.tank.BatchRequest(requests=[req]), caller=None)
    assert result['status'] == 'completed' and result['batch'] is False
    assert set(calls) == {'local'}
