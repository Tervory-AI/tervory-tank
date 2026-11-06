"""Current deployments serve hosted rungs without starting optional engine services."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace, ModuleType
import sys

import httpx
import pytest
import yaml

import engine_ladder
import engine_runtime
import engine_tracing
import engine_quality
import engine_proof
from test_engine_ladder import setup_engine
from test_tank_tenant_boundaries import boundary  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ('ENGINE_LOCAL_URL', 'ENGINE_LARGE_URL', 'LANGFUSE_HOST'):
        monkeypatch.delenv(key, raising=False)
    # A stale enable flag and invalid settings must be harmless without a host.
    monkeypatch.setenv('LANGFUSE_ENABLED', 'true')
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECTS', 'not-json')
    monkeypatch.setenv('LANGFUSE_TENANT_PROJECT_IDS', 'not-json')


@pytest.mark.parametrize('file', ['docker-compose.yml', 'docker-compose.za.yml'])
def test_default_compose_does_not_start_or_depend_on_engine(file):
    services = yaml.safe_load((ROOT / file).read_text())['services']
    optional = {name for name in services if name.startswith(('local-model', 'langfuse-'))}
    assert {'local-model', 'local-model-large'} <= optional
    if file == 'docker-compose.yml':
        assert len(optional) == 8  # Includes every private Langfuse backing store.
    for name in optional:
        assert services[name]['profiles'] == ['engine']
    default = {name for name, spec in services.items() if not spec.get('profiles')}
    assert not default & optional
    for name in default:
        assert not set(services[name].get('depends_on', ())) & optional
    for name in ('tank', 'litellm'):
        env = services[name]['environment']
        assert all(env[key] == '${' + key + ':-}' for key in ('ENGINE_LOCAL_URL', 'ENGINE_LARGE_URL', 'LANGFUSE_HOST'))
        assert not env.get('COMPOSE_PROFILES')


@pytest.mark.parametrize('file', ['config.yaml', 'config.za.yaml'])
def test_litellm_roster_skips_offline_models_but_preserves_fallthrough(file, monkeypatch):
    module = load('engine_config_test', 'litellm/engine_config.py')
    original = yaml.safe_load((ROOT / 'litellm' / file).read_text())
    config = module.configure(original)
    assert not set(engine_runtime.LOCAL) & {r['model_name'] for r in config['model_list']}
    chains = {k: v for chain in config['litellm_settings']['fallbacks'] for k, v in chain.items()}
    assert chains['local'] == chains['local-large'] == list(engine_ladder.OPEN)
    assert config['router_settings']['model_group_alias'] == {
        name: {'model': 'gpt-oss-small', 'hidden': True} for name in engine_runtime.LOCAL}
    assert engine_runtime.local_status() == 'local rung offline'
    monkeypatch.setenv('ENGINE_LOCAL_URL', 'http://127.0.0.1:18089')
    monkeypatch.setenv('ENGINE_LARGE_URL', 'http://127.0.0.1:18090/v1')
    enabled = module.configure(original)
    local = {r['model_name']: r for r in enabled['model_list'] if r['model_name'] in engine_runtime.LOCAL}
    assert local['local']['litellm_params']['api_base'] == 'http://127.0.0.1:18089/v1'
    assert local['local-large']['litellm_params']['api_base'] == 'http://127.0.0.1:18090/v1'
    assert engine_runtime.local_status() == 'local rung online'
    monkeypatch.delenv('ENGINE_LOCAL_URL')
    assert not any(engine_runtime.available(m) for m in engine_runtime.LOCAL)


@pytest.mark.asyncio
@pytest.mark.parametrize('policy_model', ['luna', 'local', 'local-large'])
async def test_tank_offline_falls_through_with_receipt_and_status(boundary, monkeypatch, policy_model):  # noqa: F811
    b = boundary
    req = await setup_engine(b, monkeypatch)
    # Simulate a formerly enabled installation with cached roster and promotion.
    await b.tank.list_models()
    monkeypatch.delenv('ENGINE_LOCAL_URL')
    monkeypatch.delenv('ENGINE_LARGE_URL')
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET model=$1 WHERE task_type=$2", policy_model, req.task_type)
        await conn.execute('''INSERT INTO tank.engine_state(tenant_id,region,task_type,model,revision)
            VALUES($1,'us-east',$2,'local-large','old')''', req.tenant_id, req.task_type)
        for model in engine_runtime.LOCAL:
            await conn.execute('''INSERT INTO tank.engine_candidates(tenant_id,region,task_type,model,checkpoint)
                VALUES($1,'us-east',$2,$3,'old')''', req.tenant_id, req.task_type, model)
    assert not set(engine_runtime.LOCAL) & {r['name'] for r in await b.tank.list_models()}
    calls = []
    original = httpx.AsyncClient
    async def dispatch(request):
        data = json.loads(request.content)
        calls.append(data['model'])
        assert data['model'] == 'gpt-oss-small'
        return httpx.Response(200, headers={'x-litellm-response-cost': '0.001', 'x-litellm-model-group': data['model']},
            json={'choices': [{'message': {'content': 'billing'}}], 'usage': {'prompt_tokens': 40, 'completion_tokens': 2}})
    monkeypatch.setattr(b.tank.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(dispatch), **kw))
    answer = await b.tank.run_route(req)
    assert calls == ['gpt-oss-small'] and answer.content == 'billing' and answer.cost_usd == .001
    assert answer.engine['local_status'] == 'local rung offline'
    assert answer.engine['rung'] == 'open-weight' and answer.ledger_id
    policy = await engine_ladder.select(b.tank, req, await b.tank.load_policy(req.task_type, req.tenant_id))
    assert not set(engine_runtime.LOCAL) & {r['model'] for r in await engine_proof.options(b.tank, req, policy)}
    status = await b.client.get('/v1/engine/status', params={'tenant_id': str(req.tenant_id)},
                              headers=b.native_headers('founder-fixture', 'org_admin'))
    assert status.status_code == 200
    assert status.json()['local_status'] == 'local rung offline'
    row = next(t for t in status.json()['tasks'] if t['task_type'] == req.task_type)
    assert row['model'] == 'gpt-oss-small' and row['traces_url'] is None
    assert row['local_status'] == 'local rung offline' and row['requests'] == 1


@pytest.mark.asyncio
async def test_offline_judge_and_code_escalation_never_select_local(monkeypatch):
    class Conn:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def fetchval(self, query, *args): return True
    rt = SimpleNamespace(pool=lambda: SimpleNamespace(acquire=Conn), box_region=lambda: 'us-east',
                         is_build_only_model=lambda name: False)
    async def roster():
        return [{'name': name, 'input_usd_per_m': 0 if name in engine_runtime.LOCAL else 1,
                 'output_usd_per_m': 0 if name in engine_runtime.LOCAL else 1}
                for name in (*engine_runtime.LOCAL, *engine_ladder.OPEN)]
    rt.list_models = roster
    req = SimpleNamespace(tenant_id='placeholder', task_type='base.extract')
    judge = await engine_quality.calibrated_judge(rt, req, {}, 'trained-placeholder')
    assert judge[0] == 'gpt-oss-small'
    async def cases(*args): return []
    async def evaluate(*args): return None
    monkeypatch.setattr(engine_ladder, 'cases', cases)
    monkeypatch.setattr(engine_ladder, 'evaluate', evaluate)
    selected = await engine_ladder.select(SimpleNamespace(list_models=roster, get_package=lambda *args: None),
        None, {'model': 'skill:base.extract@1.0.0', 'escalation_model': 'luna'})
    assert selected['model'].startswith('skill:') and selected['escalation_model'] == 'gpt-oss-small'


@pytest.mark.asyncio
async def test_unset_langfuse_host_is_noop_for_tank_and_litellm(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline tracing must not start workers, touch storage or parse project settings')
    monkeypatch.setattr(engine_tracing, 'batch_sink', forbidden)
    assert await engine_tracing.metadata(None, None, None, None) == {}
    assert engine_tracing.traces_url(None, 'base.extract') is None
    await engine_tracing.resume_batches()
    await engine_tracing.batch_trace(None, None, None)
    # The actual adapter uses only the SDK base class here; no provider SDK needed.
    stub = ModuleType('litellm.integrations.custom_logger')
    stub.CustomLogger = object
    monkeypatch.setitem(sys.modules, 'litellm.integrations.custom_logger', stub)
    adapter = load('offline_trace_adapter', 'litellm/tenant_traces.py')
    monkeypatch.setattr(adapter.callback.sink, 'before', forbidden)
    monkeypatch.setattr(adapter.callback.sink, 'after', forbidden)
    data = {'model': 'gpt-oss-small', 'messages': [{'role': 'user', 'content': 'placeholder'}]}
    assert await adapter.callback.async_pre_call_hook(None, None, data, 'completion') is data
    await adapter.callback.async_log_success_event({'metadata': {'tank_trace': {}}}, {}, None, None)
    await adapter.callback.async_log_failure_event({'metadata': {'tank_trace': {}}}, {}, None, None)
    sink = load('offline_sink', 'litellm/trace_sink.py').TraceSink(str(tmp_path / 'absent.sqlite'), forbidden)
    await sink.flush()
    assert not (tmp_path / 'absent.sqlite').exists()


def test_runtime_copies_and_gateway_startup_agree():
    assert (ROOT / 'tank/engine_runtime.py').read_bytes() == (ROOT / 'litellm/engine_runtime.py').read_bytes()
    assert 'ENTRYPOINT ["python", "/app/engine_config.py"]' in (ROOT / 'litellm/Dockerfile').read_text()


def test_gateway_entrypoint_loads_optional_config_and_preserves_callback_imports(monkeypatch, capsys, tmp_path):
    module = load('engine_startup_test', 'litellm/engine_config.py')
    monkeypatch.setattr(module.tempfile, 'tempdir', str(tmp_path))
    monkeypatch.delenv('USE_DDTRACE', raising=False)
    monkeypatch.delenv('PYTHONPATH', raising=False)
    calls = []
    monkeypatch.setattr(module.os, 'execvp', lambda *args: calls.append(args))
    module.main(['--config', str(ROOT / 'litellm/config.za.yaml'), '--port', '4000'])
    command, args = calls[0]
    assert command == args[0] == 'litellm' and args[-2:] == ['--port', '4000']
    config = yaml.safe_load(Path(args[args.index('--config') + 1]).read_text())
    assert not set(engine_runtime.LOCAL) & {r['model_name'] for r in config['model_list']}
    assert config['litellm_settings']['callbacks'] == ['tenant_traces.callback']
    assert module.os.environ['PYTHONPATH'] == str(ROOT / 'litellm')
    assert capsys.readouterr().out.strip() == 'local rung offline'
