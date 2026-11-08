"""Missing configuration starts a safe room, not a worker with ambient access."""
from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from agents.tisan import figma, runtime


def configure(monkeypatch, root):
    names = {*runtime.CORE, *(name for names in runtime.CAPABILITIES.values() for name in names)}
    for name in names:
        monkeypatch.setenv(name, 'placeholder')
    monkeypatch.setenv('DATA_DIR', str(root))
    monkeypatch.setenv('TANK_REGION', 'us-east')


def room_app():
    calls = []
    @asynccontextmanager
    async def prior(app):
        calls.append('startup')
        yield
        calls.append('shutdown')
    app = FastAPI(lifespan=prior)
    app.state.agent = 'tisan'
    original = {name: AsyncMock(return_value={'ok': True}) for name in
                ('ping', 'figma', 'build', 'scaffold', 'pipeline', 'archive')}
    app.state.handlers = dict(original)
    @app.api_route('/{rest:path}', methods=['GET', 'POST', 'PUT'])
    async def dispatch(rest: str, request: Request):
        calls.append(rest)
        return await request.json() if request.method == 'POST' else {'ok': True}
    # The exact readiness route must precede the catch-all used by this fake.
    fallback = app.router.routes.pop()
    runtime.install(app, lambda *_: figma, preflight=AsyncMock(return_value=[]))
    app.router.routes.append(fallback)
    return app, calls, original


@pytest.mark.parametrize('setting', runtime.CORE)
def test_actual_room_starts_without_each_core_setting_and_never_connects(tmp_path, monkeypatch, setting):
    from agents.tisan import app as room
    import chassis.app
    configure(monkeypatch, tmp_path)
    monkeypatch.delenv(setting)
    connect = AsyncMock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(chassis.app.asyncpg, 'create_pool', connect)
    with TestClient(room.app) as client:
        for path in ('/health', '/gold/pages', '/quotes', '/storage/usage'):
            response = client.get(path)
            assert response.status_code == 503
            assert response.json()['missing_settings'] == [setting]
            assert setting in response.json()['detail']
        report = client.get('/readiness').json()
        assert report['ok'] is False
        assert all(value['ready'] is False for value in report['capabilities'].values())
        connect.assert_not_awaited()
    assert room.app.state.tisan_active is False


CAP_PATHS = {'heartbeat': '/jobs', 'figma_live': '/pipeline/start', 'build': '/jobs',
             'pipeline': '/pipeline/start', 'publish': '/publish/build',
             'promotion': '/promotion/promote', 'archive': '/jobs', 'storage': '/storage/usage',
             'founder': '/quotes'}


@pytest.mark.parametrize('capability,setting', [(capability, name)
    for capability, names in runtime.CAPABILITIES.items() for name in names if name not in runtime.CORE])
def test_each_optional_setting_is_named_before_any_operation(tmp_path, monkeypatch, capability, setting):
    configure(monkeypatch, tmp_path)
    monkeypatch.delenv(setting)
    app, calls, original = room_app()
    kind = 'ping' if capability == 'heartbeat' else capability
    payload = {'kind': kind, 'input': {'heartbeat': True}}
    with TestClient(app) as client:
        response = client.post(CAP_PATHS[capability], json=payload)
        assert response.status_code == 503, response.text
        assert response.json()['missing_settings'] == [setting]
        assert calls == ['startup']
        report = client.get('/readiness').json()
        assert report['ok'] is True
        assert report['capabilities'][capability] == {'ready': False, 'missing_settings': [setting]}
        for handler in original.values():
            handler.assert_not_awaited()
    assert calls == ['startup', 'shutdown']


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['ping', 'scaffold', 'build', 'pipeline', 'archive'])
async def test_missing_job_setting_blocks_worker_dispatch_without_a_fake_receipt(tmp_path, monkeypatch, kind):
    configure(monkeypatch, tmp_path)
    missing = runtime.job_settings(kind, {'heartbeat': True})[-1]
    monkeypatch.delenv(missing)
    app, _, original = room_app()
    # Core removals intentionally exercise the startup guard instead.
    if missing in runtime.CORE:
        monkeypatch.setenv(missing, 'placeholder')
        missing = runtime.job_settings(kind, {'heartbeat': True})[0]
        monkeypatch.delenv(missing)
    async with app.router.lifespan_context(app):
        result = await app.state.handlers[kind](SimpleNamespace(input={'heartbeat': True}))
        assert result['ok'] is False and missing in result['missing_settings']
        assert not any(key in result for key in ('memory_id', 'archive_sha256', 'heartbeats_seen'))
        original[kind].assert_not_awaited()
    assert app.state.handlers == original


def test_prerequisite_body_read_preserves_the_actual_enqueued_input(tmp_path, monkeypatch):
    configure(monkeypatch, tmp_path)
    app, calls, _ = room_app()
    payload = {'kind': 'build', 'input': {'page_id': 'placeholder-home', 'brief': {'name': 'placeholder'}}}
    with TestClient(app) as client:
        response = client.post('/jobs', json=payload)
        assert response.status_code == 200 and response.json() == payload
        assert calls == ['startup', 'jobs']


@pytest.mark.parametrize('failure', ['storage', 'dependency', 'rls'])
def test_unavailable_startup_remains_diagnosable_and_discloses_no_exception(tmp_path, monkeypatch, failure):
    configure(monkeypatch, tmp_path)
    app, calls, original = room_app()
    if failure == 'storage':
        def refused(*_):
            raise PermissionError('placeholder private failure')
        monkeypatch.setattr(runtime, 'durable_root', refused)
    else:
        @asynccontextmanager
        async def failed(app):
            if failure == 'rls':
                raise RuntimeError('RLS requires a non-bypass room role and a separate admin pool')
            raise RuntimeError('placeholder private failure')
            yield
        app.router.lifespan_context = failed
        runtime.install(app, lambda *_: figma, preflight=AsyncMock(return_value=[]))
    with TestClient(app) as client:
        response = client.get('/health')
        assert response.status_code == 503
        assert response.json()['ok'] is False
        assert 'placeholder private failure' not in response.text
        assert client.post('/jobs', json={'kind': 'ping'}).status_code == 503
        for handler in original.values():
            handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_runtime_figma_jobs_use_only_real_tenant_saved_readings(tmp_path, monkeypatch):
    configure(monkeypatch, tmp_path)
    app, _, original = room_app()
    tenant = '11111111-1111-4111-8111-111111111111'
    file_id, node = 'placeholderFigmaFileKey01', '0:1'
    path = tmp_path / 'readings' / tenant / file_id / '0-1.json'
    path.parent.mkdir(parents=True)
    ctx = SimpleNamespace(tenant_id=tenant, input={'file_key': file_id, 'node_id': node})
    async with app.router.lifespan_context(app):
        for data in (None, {'source': 'fixture'}, {'source': 'figma', 'file_key': file_id, 'node': {'id': node}}):
            if data is not None:
                path.write_text(json.dumps(data))
            result = await app.state.handlers['figma'](ctx)
            assert (result.get('source') == 'figma') == (data is not None and data['source'] == 'figma')
            if result.get('source') != 'figma':
                assert result == {'ok': False, 'refused': True, 'detail': 'approved page required'}
        ctx.tenant_id = '22222222-2222-4222-8222-222222222222'
        assert (await app.state.handlers['figma'](ctx))['ok'] is False
        original['figma'].assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('setting', ['FIGMA_TOKEN', 'TISAN_FIGMA_FILES'])
@pytest.mark.parametrize('strict_mode', ['argument', 'server_payload'])
async def test_live_reader_never_falls_back_to_the_recording_when_a_setting_is_absent(tmp_path, monkeypatch, setting, strict_mode):
    tenant = '11111111-1111-4111-8111-111111111111'
    monkeypatch.setenv('FIGMA_TOKEN', 'placeholder')
    monkeypatch.setenv('TISAN_FIGMA_FILES', tenant + '=' + figma.TERVORY_FILE_KEY)
    monkeypatch.delenv(setting)
    outgoing = AsyncMock(side_effect=AssertionError('network forbidden'))
    monkeypatch.setattr(figma, '_read_live', outgoing)
    with pytest.raises(figma.FigmaError):
        await figma.execute({'allow_fixture': False} if strict_mode == 'server_payload' else {},
                            tenant, data_root=tmp_path, live=True,
                            **({'allow_fixture': False} if strict_mode == 'argument' else {}))
    outgoing.assert_not_awaited()
    assert list(tmp_path.iterdir()) == []
