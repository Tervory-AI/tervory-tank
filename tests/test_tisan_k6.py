"""J5: real pinned k6, loopback fixtures, and the existing build/memory contract."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'agents/tisan/templates/next-site/scripts/quality-check.cjs'
TENANT = '11111111-1111-4111-8111-111111111111'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def servers():
    received = []
    outside = []

    class Outside(BaseHTTPRequestHandler):
        def do_GET(self):
            outside.append(self.path)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    external = ThreadingHTTPServer(('127.0.0.1', 0), Outside)

    class Local(Outside):
        def do_GET(self):
            received.append(self.path)
            self.send_response(500 if self.path == '/placeholder-500' else
                               302 if self.path == '/placeholder-redirect' else 200)
            if self.path == '/placeholder-redirect':
                self.send_header('Location', f'http://127.0.0.1:{external.server_port}/placeholder-outside')
            self.end_headers()
            self.wfile.write(b'placeholder')

    local = ThreadingHTTPServer(('127.0.0.1', 0), Local)
    for server in (external, local):
        threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f'http://127.0.0.1:{local.server_port}', received, outside
    finally:
        for server in (external, local):
            server.shutdown()
            server.server_close()


def smoke(project, origin, paths):
    if not shutil.which('k6'):
        pytest.skip('real k6 binary required; installed in the Tisan room image')
    (project / 'scripts').mkdir(exist_ok=True)
    shutil.copyfile(SCRIPT.with_name('smoke.k6.js'), project / 'scripts/smoke.k6.js')
    # An inherited proxy must not influence the subprocess.
    env = {**os.environ, 'HTTPS_PROXY': 'http://127.0.0.1:1', 'HTTP_PROXY': 'http://127.0.0.1:1',
           'K6_OUT': 'loki=http://127.0.0.1:1', 'K6_WEB_DASHBOARD': 'true'}
    result = subprocess.run(['node', '-e',
        'require(process.argv[1]).smoke(process.argv[2], JSON.parse(process.argv[3]))'
        '.then(r=>console.log(JSON.stringify(r))).catch(()=>process.exit(1))',
        str(SCRIPT), origin, json.dumps(paths)], cwd=project, env=env,
        capture_output=True, text=True, timeout=25, check=True)
    assert not (project / '.k6-check.json').exists()
    return json.loads(result.stdout)


@pytest.mark.parametrize('page,passed', [('/placeholder-clean', True), ('/placeholder-500', False),
                                        ('/placeholder-redirect', False)])
def test_real_k6_every_page_200_and_p95_with_no_redirects(tmp_path, servers, page, passed):
    origin, received, outside = servers
    result = smoke(tmp_path, origin, ['/placeholder-other', page])
    assert result['name'] == 'k6' and result['ok'] is passed
    assert {row['page'] for row in result['pages']} == {'/placeholder-other', page}
    assert all(row['requests'] > 1 and row['p95_ms'] >= 0 for row in result['pages'])
    assert set(received) == {'/placeholder-other', page}
    assert outside == []
    if passed:
        assert all(row['status'] == 200 for row in result['pages'])


@pytest.mark.parametrize('origin,paths', [
    ('https://placeholder.invalid', ['/']),
    ('http://127.0.0.1:80', ['//placeholder.invalid/']),
    ('http://127.0.0.1:80', ['/\\placeholder.invalid/']),
    ('http://127.0.0.1:80', ['http://placeholder.invalid/']),
])
def test_real_k6_refuses_nonlocal_targets_before_any_request(tmp_path, origin, paths):
    result = smoke(tmp_path, origin, paths)
    assert result['ok'] is False and result['pages'] == []


@pytest.mark.asyncio
async def test_500_smoke_fails_build_and_saved_manifest(tmp_path, servers, monkeypatch):
    origin, _, outside = servers
    check = smoke(tmp_path, origin, ['/placeholder-500'])
    scaffold = load('j5_scaffold', ROOT / 'agents/tisan/scaffold.py')
    monkeypatch.setattr(scaffold, '_run', AsyncMock(return_value=(0, '')))
    quality = [{'name': name, 'ok': True} for name in ('accessibility', 'lighthouse', 'links', 'secrets')]
    monkeypatch.setattr(scaffold, '_quality_checks', AsyncMock(return_value=quality + [check]))
    checks, detail = await scaffold.run_checks(tmp_path, tenant_id=TENANT)
    assert 'k6' in detail and checks[-1]['ok'] is False
    brief = {'name': 'placeholder', 'slug': 'placeholder', 'locale': 'en', 'colours': {},
             'fonts': {'body': 'placeholder', 'heading': 'placeholder'}, 'logo_url': None}
    result = scaffold._manifest(brief, files=[], checks=checks, detail=detail, archive='', build=1)
    assert result['ok'] is False and result['checks'][-1] == check
    assert result['results'][-1]['name'] == 'k6' and result['results'][-1]['ok'] is False
    assert outside == []
    # Feed the real failing smoke into the real builder failure/archive path.
    from test_tisan_builder import client_for, copy_for, payload
    builder = load('j5_failed_builder', ROOT / 'agents/tisan/builder.py')
    monkeypatch.setattr(builder, '_scaffold', lambda: scaffold)
    data = payload()
    data['copy'] = copy_for(builder, data['plan'])
    async with client_for() as client:
        failed = await builder.execute(data, TENANT, http=client, data_root=tmp_path / 'builds')
    assert failed['ok'] is False and failed['checks'][-1] == check
    assert not list((tmp_path / 'builds').rglob('*.tar.gz'))
    saved = list((tmp_path / 'builds').rglob('*.json'))
    assert len(saved) == 1 and json.loads(saved[0].read_text())['checks'][-1] == check


@pytest.mark.asyncio
@pytest.mark.parametrize('passed', [False, True])
async def test_build_memory_keeps_complete_k6_result(monkeypatch, passed):
    builder = load('j5_builder', ROOT / 'agents/tisan/builder.py')
    check = {'name': 'k6', 'ok': passed, 'pages': [{'page': '/placeholder', 'status': 200 if passed else None,
                                               'p95_ms': 12.5, 'requests': 45, 'failures': 0 if passed else 45}]}
    monkeypatch.setattr(builder, 'execute', AsyncMock(return_value={'ok': False, 'build': 1, 'checks': [check]}))
    memory = SimpleNamespace(remember=AsyncMock(return_value={'id': 'placeholder-memory'}))
    result = await builder.handle(SimpleNamespace(input={}, tenant_id=TENANT, tank=None,
                                                  job_id='placeholder-job', memory=memory))
    claim = json.loads(memory.remember.call_args.args[1])
    assert claim['checks'] == [check] and result['memory_id'] == 'placeholder-memory'


@pytest.mark.asyncio
async def test_scan_finishes_before_final_local_smoke(tmp_path, monkeypatch):
    scaffold = load('j5_order_scaffold', ROOT / 'agents/tisan/scaffold.py')
    order = []

    async def scan(*_args):
        order.append('secrets')
        return {'name': 'secrets', 'ok': True}

    async def runner(*_args):
        assert order == ['secrets']
        order.extend(['accessibility', 'lighthouse', 'links', 'k6'])
        rows = [{'name': name, 'ok': True, 'summary': 'placeholder'}
                for name in ('accessibility', 'lighthouse', 'links', 'k6')]
        (tmp_path / '.quality-checks.json').write_text(json.dumps(rows))
        return 0, ''

    monkeypatch.setattr(scaffold, '_secret_check', scan)
    monkeypatch.setattr(scaffold, '_run', runner)
    results = await scaffold._quality_checks(tmp_path, {}, TENANT, None)
    assert [row['name'] for row in results] == ['accessibility', 'lighthouse', 'links', 'secrets', 'k6']
    assert order[-1] == 'k6'
