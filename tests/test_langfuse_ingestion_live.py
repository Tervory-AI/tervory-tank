"""Optional native Langfuse contract: real ingestion/readback, fake model response."""
import asyncio
from datetime import datetime, timezone
import json
import os
from urllib.parse import urlsplit
import uuid

import httpx
import pytest

from test_engine_observability import sink_module


@pytest.mark.asyncio
@pytest.mark.skipif(not os.environ.get('LANGFUSE_TEST_URL'), reason='native loopback Langfuse integration runtime')
async def test_real_langfuse_reads_back_faked_call_costs(tmp_path, monkeypatch):
    base = os.environ['LANGFUSE_TEST_URL'].rstrip('/')
    assert urlsplit(base).hostname in {'127.0.0.1', 'localhost', '::1'}
    public, secret = 'pk-lf-placeholder-engine', 'sk-lf-placeholder-engine'
    tenant, trace_id = str(uuid.uuid4()), str(uuid.uuid4())
    monkeypatch.setenv('LANGFUSE_HOST', base)
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECTS', json.dumps({tenant: {
        'project_id': 'placeholder-engine-project', 'public_key': public, 'secret_key': secret}}))
    sink = sink_module.TraceSink(str(tmp_path / 'outbox.sqlite'))
    monkeypatch.setattr(sink, 'start', lambda: None)
    meta = {'tank_trace': {'tenant_id': tenant, 'trace_id': trace_id, 'task_type': 'engine.classify',
        'model': 'gpt-oss-small', 'rung': 'open-weight', 'region': 'us-east',
        'baseline_input_usd_per_m': 2, 'baseline_output_usd_per_m': 10,
        'input_usd_per_m': .05, 'output_usd_per_m': .18}}
    now = datetime.now(timezone.utc)
    await sink.before({'metadata': meta, 'messages': [{'content': 'placeholder-private-prompt'}]})
    await sink.after({'litellm_params': {'metadata': meta}, 'response_cost': .001},
        {'usage': {'prompt_tokens': 1000, 'completion_tokens': 200},
         'choices': [{'message': {'content': 'placeholder-private-answer'}}]}, now, now)
    async with httpx.AsyncClient(base_url=base, auth=(public, secret), trust_env=False) as client:
        for _ in range(60):
            response = await client.get('/api/public/v2/observations', params={
                'traceId': uuid.UUID(trace_id).hex, 'type': 'GENERATION', 'fields': 'basic,metadata,usage,model,io'})
            if response.status_code == 200 and response.json().get('data'):
                break
            await asyncio.sleep(1)
        assert response.status_code == 200, response.text
        assert response.json().get('data'), response.text
        trace = response.json()['data'][0]
    assert trace['userId'] == tenant and trace['name'] == 'engine.classify'
    assert trace['metadata']['cost_usd'] == .001
    assert trace['metadata']['would_have_cost_usd'] == .004
    assert trace['metadata']['rung'] == 'open-weight'
    assert trace['metadata']['tenant_id'] == tenant
    assert trace['usageDetails'] == {'input': 1000, 'output': 200, 'total': 1200}
    assert trace['totalCost'] == .001
    assert 'placeholder-private' not in json.dumps(trace)
    assert public not in json.dumps(trace) and secret not in json.dumps(trace)
    print('LANGFUSE_PROOF ' + json.dumps({'trace_id': trace_id, 'cost_usd': trace['totalCost'],
        'would_have_cost_usd': trace['metadata']['would_have_cost_usd'], 'tenant_scoped': True}))
