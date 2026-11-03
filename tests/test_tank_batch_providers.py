"""Real Tank/SQL, stubbed LiteLLM only; no provider key or paid network call."""
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

import batch_providers
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder, policy, request  # noqa: F401

REAL_HTTP_CLIENT = httpx.AsyncClient
PROVIDERS = ['openai', 'vertex_ai', 'anthropic']
NATIVE = {'openai': 'gpt-6-luna', 'vertex_ai': 'gemini-2.5-flash', 'anthropic': 'claude-sonnet-5-5',
          'gemini': 'gemini-2.5-flash', 'other': 'unsupported-model'}


class LiteLLMStub:
    def __init__(self, provider):
        self.provider = provider
        self.calls = []
        self.rows = []
        self.finished = False
        self.failures = {}
        self.batch_id = 'msgbatch_offline' if provider == 'anthropic' else 'offline-batch'

    async def __call__(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs))
        assert kwargs['model'] == 'batch-fixture'
        if self.provider == 'anthropic':
            assert path.startswith('/anthropic/v1/messages/batches')
            assert 'params' not in kwargs  # no provider key, URL or custom provider forwarded
            if path == '/anthropic/v1/messages/batches':
                assert method == 'POST'
                self.rows = kwargs['json']['requests']
                assert len(kwargs['json']) == 1
                for row in self.rows:
                    assert row['params']['model'] == NATIVE[self.provider]
                    assert row['params']['max_tokens'] == 1024
                    # One prompt-cache breakpoint after the fixed system text (prompt caching).
                    assert row['params']['system'] == [{'type': 'text', 'text': 'Offline system instruction',
                                                        'cache_control': {'type': 'ephemeral'}}]
                    assert all(m['role'] != 'system' for m in row['params']['messages'])
                return httpx.Response(200, json={'id': self.batch_id, 'processing_status': 'in_progress'})
            if path.endswith('/cancel'):
                return httpx.Response(200, json={'processing_status': 'canceling'})
            if not path.endswith('/results'):
                return httpx.Response(200, json={'processing_status': 'ended' if self.finished else 'in_progress',
                                                'results_url': 'https://must-not-be-followed.invalid/results'})
        else:
            if path == '/v1/files':
                assert kwargs['data'] == {'purpose': 'batch', 'custom_llm_provider': self.provider}
                self.rows = [json.loads(line) for line in kwargs['files']['file'][1].decode().splitlines()]
                assert all(row['body']['model'] == NATIVE[self.provider] for row in self.rows)
                return httpx.Response(200, json={'id': 'offline-file'})
            if path == '/v1/batches':
                assert kwargs['json']['custom_llm_provider'] == self.provider
                assert kwargs['json']['completion_window'] == '24h'
                return httpx.Response(200, json={'id': self.batch_id})
            if path.endswith('/cancel'):
                return httpx.Response(200, json={'status': 'cancelling'})
            assert kwargs['params'] == {'custom_llm_provider': self.provider}
            if path.startswith('/v1/batches/'):
                return httpx.Response(200, json={'status': 'completed' if self.finished else 'in_progress',
                                                'output_file_id': 'offline-output'})
        rows = []
        for item in self.rows:
            payload = item['params'] if self.provider == 'anthropic' else item['body']
            position = int(payload['messages'][-1]['content'].split()[-1])
            failed = self.failures.get(position)
            if failed == 'missing':
                continue
            if self.provider == 'anthropic':
                result = {'type': failed} if failed else {'type': 'succeeded', 'message': {
                    'content': [{'type': 'text', 'text': 'Offline answer'}], 'stop_reason': 'end_turn',
                    'usage': {'input_tokens': 100, 'output_tokens': 50}}}
                rows.append({'custom_id': item['custom_id'], 'result': result})
            else:
                rows.append({'custom_id': item['custom_id'], 'response': {'status_code': 500 if failed else 200,
                    'body': {'choices': [{'message': {'content': 'Offline answer'}}],
                             'usage': {'prompt_tokens': 100, 'completion_tokens': 50}}}})
        return httpx.Response(200, text='\n'.join(json.dumps(row) for row in reversed(rows)))

    def submissions(self):
        return [call for call in self.calls if call[0] == 'POST' and call[1] in
                {'/v1/batches', '/anthropic/v1/messages/batches'}]


async def setup(b, monkeypatch, provider, *, cap=1, count=2, **policy_values):
    async def roster():
        return [{'model_name': 'batch-fixture', 'litellm_params': {'model': provider + '/' + NATIVE[provider]},
                 'model_info': {'input_cost_per_token': 0.000002, 'output_cost_per_token': 0.00001}}]
    monkeypatch.setattr(b.tank, '_roster_models', roster)
    monkeypatch.setenv('TANK_BATCH_MIN', '2')
    await policy(b, b.tenants[0], model='batch-fixture', rung=1, batch_eligible=True,
                 system_prompt='Offline system instruction', max_cost_usd=cap, **policy_values)
    stub = LiteLLMStub(provider)
    monkeypatch.setattr(b.tank, '_batch_gateway', stub)
    body = b.tank.BatchRequest(requests=[request(b, b.tenants[0], interactive=False, text=f'Offline input {i}')
                                       for i in range(count)])
    return stub, body


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', PROVIDERS)
async def test_fifty_requests_one_batch_poll_and_discounted_ledger(ladder, monkeypatch, provider):  # noqa: F811
    b = ladder
    stub, body = await setup(b, monkeypatch, provider, count=50)
    monkeypatch.delenv('TANK_BATCH_MIN')  # actual production default, 50
    queued = await b.tank.route_batch(body, None)
    assert queued['status'] == 'queued'
    assert (await b.tank.route_batch(body, None))['id'] == queued['id']
    await b.tank.process_batches_once()
    assert len(stub.rows) == 50 and len(stub.submissions()) == 1
    await b.tank.process_batches_once()
    assert (await b.tank.batch_status(body.id, b.tenants[0]))['status'] == 'submitted'
    stub.finished = True
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    result = await b.tank.batch_status(body.id, b.tenants[0])
    assert result['status'] == 'completed' and len(result['results']) == 50
    assert len(stub.submissions()) == 1 and not b.sent
    assert [row['position'] for row in result['results']] == list(range(50))
    async with b.pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM tank.ledger WHERE batch_id=$1 AND tenant_id=$2', body.id, b.tenants[0])
        assert len(rows) == 50
        for row in rows:
            assert row['batch']
            assert row['batch_baseline_cost_usd'] == Decimal('0.000700')
            assert row['cost_usd'] == Decimal('0.000350')
            assert row['batch_discount_usd'] == Decimal('0.000350')
        assert await conn.fetchval('SELECT sum(reserved_usd) FROM tank.batch_items WHERE batch_id=$1', body.id) == Decimal('0.017500')
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as denied:
        await b.tank.batch_status(body.id, b.tenants[1])
    assert denied.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', PROVIDERS)
@pytest.mark.parametrize('failure', ['errored', 'canceled', 'expired', 'missing'])
async def test_partial_failure_one_fallback_preserves_reservation(ladder, monkeypatch, provider, failure):  # noqa: F811
    b = ladder
    stub, body = await setup(b, monkeypatch, provider)
    stub.failures[1] = failure
    await b.tank.route_batch(body, None)
    async with b.pool.acquire() as conn:
        reserved = await conn.fetchval('SELECT reserved_usd FROM tank.batch_items WHERE batch_id=$1 AND position=1', body.id)
    await b.tank.process_batches_once()
    stub.finished = True
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    result = await b.tank.batch_status(body.id, b.tenants[0])
    assert result['status'] == 'completed'
    assert len(b.sent) == 1 and b.sent[0]['disable_fallbacks'] is True
    assert len(stub.submissions()) == 1
    assert result['results'][0]['discount_usd'] > 0
    assert result['results'][1]['discount_usd'] == 0
    async with b.pool.acquire() as conn:
        row = await conn.fetchrow('SELECT attempts,reserved_usd FROM tank.batch_items WHERE batch_id=$1 AND position=1', body.id)
        assert row['attempts'] == 1 and row['reserved_usd'] == reserved
        assert all(item['batch'] for item in result['results'])


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', PROVIDERS)
async def test_cost_cap_refuses_before_submit_and_caps_partial_retry(ladder, monkeypatch, provider):  # noqa: F811
    b = ladder
    stub, body = await setup(b, monkeypatch, provider)
    prices = await b.tank._batch_price('batch-fixture')
    messages = [{'role': 'system', 'content': 'Offline system instruction'},
                *[m.model_dump() for m in body.requests[0].messages]]
    reserved = b.tank._call_upper(messages, 1024, prices) * prices['discount']
    async with b.pool.acquire() as conn:
        await conn.execute('UPDATE tank.policy SET max_cost_usd=$1 WHERE tenant_id=$2', reserved * 0.9, b.tenants[0])
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as refused:
        await b.tank.route_batch(body, None)
    assert refused.value.status_code == 409 and not stub.calls and not b.sent
    async with b.pool.acquire() as conn:
        assert await conn.fetchval('SELECT count(*) FROM tank.batches') == 0
        await conn.execute('UPDATE tank.policy SET max_cost_usd=$1 WHERE tenant_id=$2', reserved * 1.1, b.tenants[0])
    await b.tank.route_batch(body, None)
    await b.tank.process_batches_once()
    stub.finished, stub.failures = True, {1: 'errored'}
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    result = await b.tank.batch_status(body.id, b.tenants[0])
    assert result['status'] == 'failed' and result['results'][1]['error'] == 'cost_cap'
    assert not b.sent and len(stub.submissions()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', PROVIDERS)
@pytest.mark.parametrize('exclusion', ['interactive', 'small', 'moa'])
async def test_exclusions_do_not_queue(ladder, monkeypatch, provider, exclusion):  # noqa: F811
    stub, body = await setup(ladder, monkeypatch, provider, moa_enabled=exclusion == 'moa')
    if exclusion == 'small':
        body = body.model_copy(update={'requests': body.requests[:1]})
    if exclusion == 'interactive':
        body = body.model_copy(update={'requests': [row.model_copy(update={'interactive': True}) for row in body.requests]})
    result = await ladder.tank.route_batch(body, None)
    assert not result['batch'] and not stub.calls
    assert len(ladder.sent) == len(body.requests)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', ['gemini', 'other'])
async def test_unsupported_providers_still_use_single_calls(ladder, monkeypatch, provider):  # noqa: F811
    stub, body = await setup(ladder, monkeypatch, provider)
    result = await ladder.tank.route_batch(body, None)
    assert not result['batch'] and not stub.calls and len(ladder.sent) == 2
    assert all(call['disable_fallbacks'] for call in ladder.sent)


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', PROVIDERS)
async def test_deadline_cancel_waits_for_terminal_provider_state(ladder, monkeypatch, provider):  # noqa: F811
    b = ladder
    stub, body = await setup(b, monkeypatch, provider)
    await b.tank.route_batch(body, None)
    await b.tank.process_batches_once()
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.batches SET submitted_at=now()-interval '25 hours' WHERE id=$1", body.id)
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    assert len([call for call in stub.calls if call[1].endswith('/cancel')]) == 1
    assert not b.sent
    stub.finished, stub.failures = True, {0: 'canceled', 1: 'expired'}
    await b.tank.process_batches_once()
    assert len(b.sent) == 2 and len(stub.submissions()) == 1


def test_explicit_rates_and_native_shape_safety():
    assert batch_providers.charge_multiplier('vertex_ai', 'claude-model') is None
    assert batch_providers.charge_multiplier('gemini', 'gemini-2.5-flash') is None
    assert batch_providers.charge_multiplier('other', 'model') is None
    prices = {'provider': 'anthropic', 'native': 'claude-sonnet-5-5'}
    assert not batch_providers.compatible(prices, [{'role': 'user', 'content': 'test'}], {'response_format': {'type': 'json_object'}})
    assert '%2F' in batch_providers.anthropic_path('../results')
    source = (Path(__file__).parents[1] / 'tank/batch_providers.py').read_text()
    assert 'ANTHROPIC_API_KEY' not in source and 'api.anthropic.com' not in source


@pytest.mark.asyncio
async def test_gateway_keeps_auth_in_existing_litellm_boundary(ladder, monkeypatch):  # noqa: F811
    b = ladder
    captured = []

    def handle(req):
        captured.append(req)
        assert str(req.url).startswith(b.tank.LITELLM_URL + '/anthropic/')
        assert req.headers['authorization'] == 'Bearer ' + b.tank.LITELLM_MASTER_KEY
        assert req.headers['anthropic-version'] == '2023-06-01'
        assert 'x-api-key' not in req.headers
        return httpx.Response(200, json={'id': 'msgbatch_offline'})

    def client(**kwargs):
        return REAL_HTTP_CLIENT(transport=httpx.MockTransport(handle), **kwargs)

    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', client)
    await b.tank._batch_gateway('POST', batch_providers.anthropic_path(), model='haiku', json={'requests': []})
    assert len(captured) == 1 and captured[0].headers['x-litellm-model'] == 'haiku'


@pytest.mark.asyncio
@pytest.mark.parametrize('provider', PROVIDERS)
async def test_uncertain_submission_is_never_bought_twice(ladder, monkeypatch, provider):  # noqa: F811
    b = ladder
    stub, body = await setup(b, monkeypatch, provider)

    async def uncertain(method, path, **kwargs):
        result = await stub(method, path, **kwargs)
        if path in {'/v1/batches', '/anthropic/v1/messages/batches'}:
            raise httpx.ReadTimeout('offline lost response')
        return result

    monkeypatch.setattr(b.tank, '_batch_gateway', uncertain)
    await b.tank.route_batch(body, None)
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    result = await b.tank.batch_status(body.id, b.tenants[0])
    assert result['status'] == 'failed'
    assert all(row['error'] == 'interrupted_attempt' for row in result['results'])
    assert not b.sent and len(stub.submissions()) == 1
