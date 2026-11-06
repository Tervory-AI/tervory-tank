from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI

import skala
import skala_runtime
import training
from gold import PLATFORM_TENANT, Reviewer


@pytest.mark.asyncio
@pytest.mark.parametrize('name', skala_runtime.CORE_SETTINGS)
@pytest.mark.parametrize('absent', ['', '  ', None])
async def test_missing_core_setting_starts_without_workers_or_requests(name, absent, caplog):
    events = []
    @asynccontextmanager
    async def workers(app):
        events.append('startup')
        yield
        events.append('shutdown')
    app = FastAPI(lifespan=workers)
    @app.post('/work')
    async def work():
        events.append('request')
        return {'ok': True}
    values = dict.fromkeys(skala_runtime.CORE_SETTINGS, 'offline-placeholder')
    values[name] = absent
    skala_runtime.install(app, lambda: values)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local') as client:
            response = await client.post('/work')
    assert events == []
    assert response.status_code == 503
    assert response.json()['missing_settings'] == [name]
    assert response.json()['message'] == 'Missing settings: ' + name
    assert 'offline-placeholder' not in response.text + caplog.text


@pytest.mark.asyncio
async def test_configured_startup_keeps_the_existing_lifespan():
    events = []
    @asynccontextmanager
    async def workers(app):
        events.append('startup')
        yield
        events.append('shutdown')
    app = FastAPI(lifespan=workers)
    @app.get('/health')
    async def health():
        events.append('request')
        return {'ok': True}
    skala_runtime.install(app, lambda: dict.fromkeys(skala_runtime.CORE_SETTINGS, 'offline-placeholder'))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local') as client:
            assert (await client.get('/health')).json() == {'ok': True}
    assert events == ['startup', 'request', 'shutdown']


def test_tank_import_and_startup_with_no_core_settings_make_no_connections():
    code = '''
import asyncio, json, socket, sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tank'))
def forbidden(*args, **kwargs):
    raise AssertionError('Unconfigured startup attempted a connection')
socket.create_connection = forbidden
socket.socket.connect = forbidden
socket.getaddrinfo = forbidden
import finish_proposals
import main
import httpx
async def check():
    async with main.app.router.lifespan_context(main.app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url='http://local') as client:
            result = await client.get('/health')
            assert result.status_code == 503
            print(json.dumps(result.json()))
asyncio.run(check())
'''
    env = {name: value for name, value in os.environ.items() if name not in skala_runtime.CORE_SETTINGS}
    result = subprocess.run([sys.executable, '-c', code], cwd=Path.cwd(), env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout.splitlines()[-1])
    assert report['missing_settings'] == list(skala_runtime.CORE_SETTINGS)


@pytest.mark.asyncio
@pytest.mark.parametrize('missing', [('HF_TOKEN',), ('HF_ORG',), ('HF_TOKEN', 'HF_ORG')])
async def test_missing_export_or_training_settings_stop_before_io(monkeypatch, missing):
    for name in skala_runtime.EXPORT_SETTINGS:
        monkeypatch.setenv(name, 'offline-placeholder')
    for name in missing:
        monkeypatch.delenv(name, raising=False)
    def forbidden():
        raise AssertionError('Missing configuration must stop before IO')
    monkeypatch.setattr(training, 'runtime', forbidden)
    conn = SimpleNamespace(fetchval=AsyncMock(side_effect=AssertionError('No database query needed')))
    body = training.TrainingRunRequest(agent='zenas', minutes=30)
    results = [await training.export_once(), await training._training_readiness(conn, body),
        await training.training_receipt(training.TrainingReceiptRequest(job_id='offline-job', billed_usd=0),
            Reviewer('founder', PLATFORM_TENANT, True))]
    for result in results:
        assert result['missing_settings'] == list(missing)
        assert all(name in result['message'] for name in missing)
        assert 'offline-placeholder' not in json.dumps(result)
    conn.fetchval.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('skill,name', [('trigger.languagetool', 'TANK_KEY_TRIGGER'),
    ('tisan.figma', 'TANK_KEY_TISAN'), ('tisan.scaffold', 'TANK_KEY_TISAN'),
    ('tisan.build', 'TANK_KEY_TISAN'), ('scan.iac', 'TANK_KEY_RADIX')])
async def test_missing_room_key_names_setting_and_does_not_call_room(monkeypatch, skill, name):
    import main
    monkeypatch.delenv(name, raising=False)
    http = SimpleNamespace(post=AsyncMock(side_effect=AssertionError('No room request is safe without its key')))
    monkeypatch.setattr(main, '_http', http)
    pkg = SimpleNamespace(id=skill)
    error = ValueError if skill == 'trigger.languagetool' else RuntimeError
    with pytest.raises(error, match='Missing setting: ' + name):
        if skill == 'trigger.languagetool':
            await skala.run_skill(pkg, {}, SimpleNamespace())
        else:
            await main.run_room_eval(pkg, {}, SimpleNamespace())
    http.post.assert_not_awaited()
