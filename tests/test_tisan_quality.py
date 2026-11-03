"""Q1 checks run locally; Tank transport and scan approval are isolated test doubles."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
from chassis.tank import TankClient

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'agents/tisan/templates/next-site'
TENANT = '11111111-1111-4111-8111-111111111111'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def scaffold():
    return load('q1_scaffold', ROOT / 'agents/tisan/scaffold.py')


def transport(calls, approved=True):
    engine = load('q1_scanner', ROOT / 'tank/skills/scan.secrets/1.1.0/engine.py')
    def respond(request):
        calls.append((request.method, request.url.path))
        assert request.url.path == '/v1/skala/scan.secrets/run'
        if request.method == 'GET':
            return httpx.Response(200, json={'version': '1.1.0'}) if approved else httpx.Response(409, json={'detail': 'scan.secrets has no approved version'})
        body = json.loads(request.content)
        assert body['tenant_id'] == TENANT and 'version' not in body
        assert set(body['input']) == {'files'}
        assert all(set(row) == {'path', 'text'} for row in body['input']['files'])
        return httpx.Response(200, json=engine.run_skill(body['input']))
    return httpx.MockTransport(respond)


@pytest.mark.asyncio
@pytest.mark.parametrize('planted', [False, True])
async def test_real_secret_scanner_via_approved_tank_contract(scaffold, tmp_path, planted):
    text = (TEMPLATE / 'tests/fixtures/quality-secrets.fixture').read_text() if planted else 'export const safe = true;\n'
    (tmp_path / 'generated.ts').write_text(text)
    calls = []
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        tank = TankClient('http://tank.test', 'test-auth', 'tisan', http)
        result = await scaffold._secret_check(tmp_path, TENANT, tank)
    assert result['ok'] is not planted
    assert calls == [('GET', '/v1/skala/scan.secrets/run'), ('POST', '/v1/skala/scan.secrets/run')]
    if planted:
        assert result['findings'][0]['file'] == 'generated.ts'
        assert result['findings'][0]['line'] == 1
        assert result['findings'][0]['rule']
        assert set(result['findings'][0]) == {'file', 'line', 'rule'}
        # Inspect the known fake marker only; the fixture never contains a real credential.
        assert text.strip() not in json.dumps(result)
        assert 'test_key_51H8X' not in json.dumps(result)


@pytest.mark.asyncio
async def test_unapproved_scan_fails_closed_without_running_it(scaffold, tmp_path):
    (tmp_path / 'generated.ts').write_text('export const safe = true;')
    calls = []
    async with httpx.AsyncClient(transport=transport(calls, approved=False)) as http:
        result = await scaffold._secret_check(tmp_path, TENANT, TankClient('http://tank.test', 'test-auth', 'tisan', http))
    assert result['ok'] is False and result['pending_approval'] is True
    assert '/skala' in result['summary']
    assert calls == [('GET', '/v1/skala/scan.secrets/run')]


@pytest.mark.asyncio
async def test_scan_errors_never_return_upstream_values(scaffold, tmp_path):
    (tmp_path / 'generated.ts').write_text('export const safe = true;')
    tank = type('Unavailable', (), {'approved_skill': AsyncMock(side_effect=RuntimeError('private upstream detail'))})()
    result = await scaffold._secret_check(tmp_path, TENANT, tank)
    assert result['ok'] is False and 'private upstream detail' not in json.dumps(result)


@pytest.mark.asyncio
async def test_quality_failures_reach_manifest_and_existing_card_rows(scaffold, monkeypatch, tmp_path):
    monkeypatch.setattr(scaffold, '_run', AsyncMock(return_value=(0, '')))
    quality = [{'name': name, 'ok': name != 'links', 'summary': '/missing answered 404' if name == 'links' else 'checked'}
               for name in ('accessibility', 'lighthouse', 'links', 'secrets')]
    monkeypatch.setattr(scaffold, '_quality_checks', AsyncMock(return_value=quality))
    checks, detail = await scaffold.run_checks(tmp_path, tenant_id=TENANT)
    assert [c['name'] for c in checks] == ['npm ci', 'npm run lint', 'npm run build', 'npm test', 'accessibility', 'lighthouse', 'links', 'secrets']
    brief = {'name': 'Test', 'slug': 'test', 'locale': 'en', 'colours': {}, 'fonts': {'body': 'Inter', 'heading': 'Jost'}, 'logo_url': None}
    manifest = scaffold._manifest(brief, files=[], checks=checks, detail=detail, archive='', build=1)
    assert manifest['ok'] is False and 'links' in detail
    assert manifest['results'][2] == {'name': 'links', 'ok': False, 'summary': '/missing answered 404'}
    assert manifest['checks'][-2]['summary'] == '/missing answered 404'


@pytest.mark.asyncio
async def test_baseline_failure_never_starts_browser_checks(scaffold, monkeypatch, tmp_path):
    monkeypatch.setattr(scaffold, '_run', AsyncMock(return_value=(1, 'install failed')))
    gate = AsyncMock()
    monkeypatch.setattr(scaffold, '_quality_checks', gate)
    checks, detail = await scaffold.run_checks(tmp_path, tenant_id=TENANT)
    assert checks == [{'name': 'npm ci', 'ok': False}] and detail == 'install failed'
    gate.assert_not_awaited()


def test_new_version_changes_sharing_without_rewriting_scanner():
    old = ROOT / 'tank/skills/scan.secrets/1.0.1'
    new = old.with_name('1.1.0')
    for name in ('engine.py', 'run.py'):
        assert (old / name).read_bytes() == (new / name).read_bytes()
    assert 'shared_with: [tisan]' in (new / 'skill.yaml').read_text()


def test_browser_cache_environment_is_forwarded_without_tank_credentials(scaffold, monkeypatch):
    monkeypatch.setenv('PLAYWRIGHT_BROWSERS_PATH', '/opt/tisan-browser')
    env = scaffold._check_env()
    assert env['PLAYWRIGHT_BROWSERS_PATH'] == '/opt/tisan-browser'
    assert 'TANK_KEY' not in env


@pytest.mark.asyncio
@pytest.mark.skipif(__import__('os').environ.get('TISAN_RUN_QUALITY_BUILD') != '1', reason='explicit real offline quality build')
async def test_real_clean_template_passes_all_four_quality_gates(scaffold, tmp_path):
    # The unchanged clean template has its existing contact and privacy routes.
    # Pending empty section designs are not fabricated just to pass Lighthouse.
    brief = scaffold.validate({'name': 'Quality fixture', 'slug': 'quality-fixture', 'pages': ['home', 'contact', 'privacy'],
        'brand': {'colours': {'ink': '#1a1a1a', 'paper': '#ffffff', 'accent': '#1d4ed8', 'line': '#d4d4d8'},
                  'fonts': {'heading': 'Literata', 'body': 'Atkinson Hyperlegible'}}})
    project = tmp_path / 'project'
    scaffold.write_project(brief, project)
    async with httpx.AsyncClient(transport=transport([])) as scan_http:
        checks, detail = await scaffold.run_checks(project, tenant_id=TENANT, tank=TankClient('http://tank.test', 'test-auth', 'tisan', scan_http))
    result = scaffold._manifest(brief, files=scaffold.project_files(project), checks=checks, detail=detail, archive='', build=1)
    proof_path = __import__('os').environ.get('TISAN_QUALITY_PROOF')
    if proof_path:
        Path(proof_path).write_text(json.dumps(result, indent=2))
    assert result['ok'] is True, result.get('detail')
    assert [row['name'] for row in result['checks']][-4:] == ['accessibility', 'lighthouse', 'links', 'secrets']
    assert all(row['ok'] for row in result['checks'])
    assert len(result['results']) == 4
    assert not any('quality-secrets.fixture' in file for file in result['files'])


@pytest.mark.asyncio
async def test_secret_scanner_line_limit_cannot_hide_unchecked_text(scaffold, tmp_path):
    (tmp_path / 'long.ts').write_text('x' * 5001)
    tank = type('Unused', (), {'approved_skill': AsyncMock()})()
    result = await scaffold._secret_check(tmp_path, TENANT, tank)
    assert result['ok'] is False
    assert result['findings'] == [{'file': 'long.ts', 'line': 1, 'rule': 'scan-input-limit'}]
    tank.approved_skill.assert_not_awaited()
