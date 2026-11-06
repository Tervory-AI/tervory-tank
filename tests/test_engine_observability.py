"""Langfuse ingestion contracts, redaction, durable retry and project isolation."""
import base64
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import httpx
import pytest
import yaml

import engine_models
import engine_tracing

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tank_trace_sink', ROOT / 'litellm/trace_sink.py')
sink_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sink_module)


@pytest.mark.asyncio
async def test_faked_call_creates_langfuse_trace_with_costs_and_no_secrets(tmp_path, monkeypatch):
    tenants = [str(uuid.uuid4()), str(uuid.uuid4())]
    projects = {t: {'project_id': f'placeholder-project-{i}', 'public_key': f'placeholder-public-{i}',
                    'secret_key': f'placeholder-secret-{i}'} for i, t in enumerate(tenants)}
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECTS', json.dumps(projects))
    monkeypatch.setenv('LANGFUSE_ENABLED', 'true')
    received = []
    available = [False]
    async def server(request):
        if not available[0]:
            return httpx.Response(503)
        token = base64.b64decode(request.headers['authorization'].split()[1]).decode()
        entry = next(p for p in projects.values() if token == p['public_key'] + ':' + p['secret_key'])
        if request.method == 'GET':
            return httpx.Response(200, json={'data': [{'id': entry['project_id']}]})
        data = json.loads(request.content)
        spans = data['resourceSpans'][0]['scopeSpans'][0]['spans']
        received.extend((entry['project_id'], span) for span in spans)
        assert not any(word in request.content.decode() for word in ('private prompt', 'private answer', 'placeholder-secret', 'Authorization'))
        return httpx.Response(200, json={})
    def client(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(server), **kwargs)
    sink = sink_module.TraceSink(str(tmp_path / 'outbox.sqlite'), client)
    monkeypatch.setattr(sink, 'start', lambda: None)
    async def roster():
        return [{'name': 'local', 'input_usd_per_m': 0, 'output_usd_per_m': 0},
                {'name': 'sol', 'input_usd_per_m': 2, 'output_usd_per_m': 10}]
    rt = SimpleNamespace(list_models=roster, box_region=lambda: 'us-east')
    now = datetime.now(timezone.utc)
    for tenant in tenants:
        data = {'model': 'local', 'messages': [{'content': 'private prompt'}],
                **await engine_tracing.metadata(rt, tenant, 'base.extract', 'local', {'model': 'sol'})}
        data['metadata']['untrusted'] = 'placeholder-secret-do-not-log'
        await sink.before(data)
        await sink.after({'litellm_params': {'metadata': data['metadata']}, 'response_cost': 0},
            {'choices': [{'message': {'content': 'private answer'}}],
             'usage': {'prompt_tokens': 1000, 'completion_tokens': 200}}, now, now)
    assert received == []
    # Reopen the queue as after a LiteLLM restart; successful ingestion clears it.
    available[0] = True
    resumed = sink_module.TraceSink(sink.path, client)
    await resumed.flush()
    with resumed.database() as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 0
    for tenant, entry in projects.items():
        events = [e for project, e in received if project == entry['project_id']]
        def attrs(span):
            return {a['key']: (int(a['value']['intValue']) if 'intValue' in a['value']
                               else next(iter(a['value'].values()))) for a in span['attributes']}
        generation = next(attrs(e) for e in events if attrs(e)['langfuse.observation.type'] == 'generation')
        assert generation['langfuse.observation.metadata.tenant_id'] == tenant
        assert generation['langfuse.observation.metadata.task_type'] == 'base.extract'
        assert generation['langfuse.observation.metadata.rung'] == 'local small'
        assert json.loads(generation['langfuse.observation.usage_details']) == {'input': 1000, 'output': 200, 'total': 1200}
        assert json.loads(generation['langfuse.observation.cost_details']) == {'total': 0}
        assert generation['langfuse.observation.metadata.cost_usd'] == 0
        assert generation['langfuse.observation.metadata.would_have_cost_usd'] == .004
        assert all(attrs(e)['langfuse.trace.public'] is False for e in events)


def test_tenant_project_reuse_and_missing_context_are_rejected(monkeypatch):
    entry = {'project_id': 'placeholder-project', 'public_key': 'placeholder-public', 'secret_key': 'placeholder-secret'}
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECTS', json.dumps({str(uuid.uuid4()): entry, str(uuid.uuid4()): entry}))
    with pytest.raises(ValueError, match='distinct'):
        sink_module.projects()
    with pytest.raises(ValueError, match='context'):
        sink_module.safe_metadata({'messages': [{'content': 'private'}]})


def test_status_links_use_only_requested_tenant_project(monkeypatch):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    monkeypatch.setenv('LANGFUSE_UI_URL', 'https://langfuse.tervory.com')
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECT_IDS', json.dumps({a: 'placeholder-a', b: 'placeholder-b'}))
    assert '/project/placeholder-a/' in engine_tracing.traces_url(a, 'base.extract')
    assert 'placeholder-b' not in engine_tracing.traces_url(a, 'base.extract')
    assert engine_tracing.traces_url(uuid.uuid4(), 'base.extract') is None
    for invalid in ('https://cloud.langfuse.com', 'https://evil.invalid/langfuse.tervory.com',
                    'https://langfuse.tervory.com.evil.invalid', 'https://langfuse.tervory.com@evil.invalid',
                    'https://langfuse.tervory.com/?redirect=evil.invalid'):
        monkeypatch.setenv('LANGFUSE_UI_URL', invalid)
        assert engine_tracing.traces_url(a, 'base.extract') is None


def test_self_hosted_services_have_private_stores_no_telemetry_and_pinned_images():
    compose = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())
    names = ['langfuse-web', 'langfuse-worker', 'langfuse-postgres', 'langfuse-clickhouse', 'langfuse-minio', 'langfuse-redis']
    assert compose['networks']['langfuse-internal']['internal']
    for name in names:
        service = compose['services'][name]
        assert '@sha256:' in service['image'] and 'ports' not in service
        assert service['networks'] == (['langfuse-internal', 'product-proxy'] if name == 'langfuse-web' else ['langfuse-internal'])
    for name in names[:2]:
        env = compose['services'][name]['environment']
        assert env['TELEMETRY_ENABLED'] == 'false'
        assert env['LANGFUSE_S3_BATCH_EXPORT_ENABLED'] == 'false'
        assert '@langfuse-postgres:5432/langfuse' in env['DATABASE_URL']
        assert env['LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT'] == 'http://langfuse-minio:9000'
    assert compose['services']['litellm']['environment']['LANGFUSE_ENABLED'] == 'true'
    from test_routing import validate
    validate({'docker-compose.yml': {'services': {'langfuse-web': compose['services']['langfuse-web']},
                                    'networks': compose['networks']}},
             json.loads((ROOT / 'litellm/langfuse-ingress.json').read_text()))


def test_catalog_selection_is_permissive_and_cpu_fit():
    rows = engine_models.validate()
    for name in engine_models.SELECTED.values():
        assert rows[name]['licence'] in {'Apache-2.0', 'MIT'}
    assert all(rows[engine_models.SELECTED[name]]['runs_on_Boston_CPU'] == 'yes' for name in engine_models.LOCAL)
    assert not any('Cohere' in name for name in rows)


@pytest.mark.asyncio
async def test_native_batch_trace_is_tenant_scoped_and_reuses_item_identity(monkeypatch):
    tenant, item_id = uuid.uuid4(), uuid.uuid4()
    monkeypatch.setenv('LANGFUSE_ENABLED', 'true')
    calls = []
    class Sink:
        async def before(self, data):
            calls.append(data)
        async def after(self, data, response, start, end, failed=False):
            calls.append(data)
            assert response['usage']['prompt_tokens'] == 5
    monkeypatch.setattr(engine_tracing, '_batch_sink', Sink())
    async def roster():
        return [{'name': 'sol', 'input_usd_per_m': 2, 'output_usd_per_m': 10}]
    rt = SimpleNamespace(list_models=roster, box_region=lambda: 'us-east')
    batch = {'tenant_id': tenant, 'model': 'sol', 'submitted_at': datetime.now(timezone.utc)}
    item = {'item_id': item_id, 'request': {'task_type': 'base.extract'}, 'policy': {'routing': {'model': 'sol'}}}
    await engine_tracing.batch_trace(rt, batch, item)
    await engine_tracing.batch_trace(rt, batch, item, {'usage': {'prompt_tokens': 5}}, .001)
    assert calls[0]['metadata'] == calls[1]['metadata']
    assert calls[1]['response_cost'] == .001
    assert calls[0]['metadata']['tank_trace']['tenant_id'] == str(tenant)
    assert calls[0]['metadata']['tank_trace']['trace_id'] == str(item_id)


def test_exporter_copies_match_for_separate_image_build_contexts():
    # DECISION keep one tested exporter in both independent Docker build contexts.
    assert (ROOT / 'tank/trace_sink.py').read_bytes() == (ROOT / 'litellm/trace_sink.py').read_bytes()


@pytest.mark.asyncio
async def test_wrong_project_credentials_never_export_tenant_data(tmp_path, monkeypatch):
    tenant = str(uuid.uuid4())
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECTS', json.dumps({tenant: {
        'project_id': 'placeholder-a', 'public_key': 'placeholder-public', 'secret_key': 'placeholder-secret'}}))
    async def server(request):
        assert request.method == 'GET', 'Foreign project must never receive a span'
        return httpx.Response(200, json={'data': [{'id': 'placeholder-b'}]})
    def client(**kwargs):
        return httpx.AsyncClient(transport=httpx.MockTransport(server), **kwargs)
    sink = sink_module.TraceSink(str(tmp_path / 'outbox.sqlite'), client)
    sink.enqueue(tenant, [{'id': 'placeholder-event', 'span': {}}])
    await sink.flush()
    with sink.database() as db:
        assert db.execute('SELECT count(*) FROM events').fetchone()[0] == 1


@pytest.mark.asyncio
async def test_missing_provider_usage_is_unknown_instead_of_free(tmp_path, monkeypatch):
    tenant = str(uuid.uuid4())
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECTS', json.dumps({tenant: {
        'project_id': 'placeholder-project', 'public_key': 'placeholder-public', 'secret_key': 'placeholder-secret'}}))
    sink = sink_module.TraceSink(str(tmp_path / 'outbox.sqlite'))
    async def offline():
        pass
    monkeypatch.setattr(sink, 'flush', offline)
    meta = {'tank_trace': {'tenant_id': tenant, 'trace_id': str(uuid.uuid4()), 'task_type': 'base.extract',
        'model': 'gpt-oss-small', 'rung': 'open-weight', 'region': 'us-east',
        'input_usd_per_m': .05, 'output_usd_per_m': .18,
        'baseline_input_usd_per_m': 2, 'baseline_output_usd_per_m': 10}}
    now = datetime.now(timezone.utc)
    await sink.after({'metadata': meta}, {'usage': None}, now, now)
    with sink.database() as db:
        event = json.loads(db.execute('SELECT payload FROM events').fetchone()[0])
    attrs = {a['key']: a['value'] for a in event['span']['attributes']}
    assert attrs['langfuse.observation.metadata.cost_status'] == {'stringValue': 'unknown'}
    assert 'langfuse.observation.cost_details' not in attrs
    assert 'langfuse.observation.metadata.would_have_cost_usd' not in attrs
