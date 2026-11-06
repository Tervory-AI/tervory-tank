"""IaC runner contracts, all offline; real pinned-tool eval proof runs in Radix."""
import importlib.util
import json
import subprocess
import sys

import httpx
import pytest

from test_rx1_scans import Ctx, ROOT, _b64, _tar
from scanlib import iac, orchestrate

PACKAGE = ROOT / 'tank/skills/scan.iac/1.0.0'


@pytest.fixture
def fake_checkov(tmp_path, monkeypatch):
    binary = tmp_path / 'placeholder-checkov'
    binary.write_text('#!' + sys.executable + '\n' + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
assert '--skip-download' in args
assert args[args.index('--download-external-modules') + 1] == 'false'
assert args[args.index('--output') + 1] == 'json'
assert Path(args[args.index('--config-file') + 1]).read_text() == '{}\\n'
assert os.environ['HTTPS_PROXY'] == 'http://127.0.0.1:9'
assert os.environ['NO_PROXY'] == ''
assert 'BC_API_KEY' not in os.environ
for part in ('.git', 'node_modules', '.venv', 'venv', '__pycache__'):
    assert any(part.replace('.', r'\\.') in arg for arg in args)
root = Path(args[args.index('--directory') + 1])
assert Path.cwd() != root
print(json.dumps([{'results': {'failed_checks': [
 {'check_id': 'CKV_AWS_24', 'check_name': 'placeholder Checkov rule text',
  'severity': 'CRITICAL', 'file_abs_path': str(root / 'open.tf'), 'file_line_range': [7, 10]},
 {'check_id': 'CKV_AWS_24', 'check_name': 'placeholder skipped text',
  'file_abs_path': str(root / 'node_modules/open.tf'), 'file_line_range': [1, 2]}
], 'parsing_errors': []}}]))
sys.exit(1)
''')
    binary.chmod(0o755)
    # This fixture tests Checkov alone; the other engines use their offline mode.
    monkeypatch.setenv('RADIX_USE_SYSTEM_TOOLS', '0')
    monkeypatch.setattr(iac, 'checkov_bin', lambda: str(binary))
    monkeypatch.setenv('CHECKOV_BIN', str(binary))
    monkeypatch.setenv('BC_API_KEY', 'placeholder-not-a-secret')
    return binary


def test_real_subprocess_contract_and_unknown_severity(tmp_path, fake_checkov):
    found = iac.scan_tree(tmp_path)
    assert found.status == 'run'
    assert found == [{'tool': 'scan.iac', 'severity': 'unknown', 'file': 'open.tf',
                      'line': 7, 'rule': 'CKV_AWS_24', 'fix': 'placeholder Checkov rule text'}]


@pytest.mark.parametrize('mode', ['missing', 'bad-json', 'exit', 'timeout'])
def test_unavailable_or_failed_checkov_is_not_run(tmp_path, monkeypatch, mode):
    monkeypatch.setenv('RADIX_USE_SYSTEM_TOOLS', '1')
    monkeypatch.setenv('CHECKOV_BIN', str(tmp_path / 'placeholder-missing'))
    if mode != 'missing':
        def run(*args, **kwargs):
            if mode == 'timeout':
                raise subprocess.TimeoutExpired('placeholder-checkov', 120)
            return subprocess.CompletedProcess(args[0], 2 if mode == 'exit' else 0, b'not json', b'')
        monkeypatch.setattr(iac.subprocess, 'run', run)
    found = iac.scan_tree(tmp_path)
    assert found == [] and found.status == 'not run'


def test_iac_alone_never_blocks_build(fake_checkov):
    result = orchestrate.build_result(Ctx(_b64(_tar({'open.tf': 'locals { placeholder = true }'}))))
    assert result['tool_status']['scan.iac'] == 'run'
    assert result['scan_complete'] is True
    assert result['critical'] == 0 and result['deploy_blocked'] is False
    assert {r['severity'] for r in result['findings']} == {'unknown'}


def test_missing_checkov_qualifies_summary_and_never_claims_complete(monkeypatch):
    monkeypatch.delenv('RADIX_USE_SYSTEM_TOOLS', raising=False)
    result = orchestrate.build_result(Ctx(_b64(_tar({'open.tf': 'locals { placeholder = true }'}))))
    assert result['tool_status'] == {'scan.iac': 'not run'}
    assert result['scan_complete'] is False
    assert result['summary'].endswith('scan.iac: not run.')
    assert 'No findings' not in result['summary']
    assert 'scan.iac' in result['tools']


def test_evals_match_fixture_files_and_have_real_pin_rule_sets():
    cases = [json.loads(line) for line in (PACKAGE / 'evals/cases.jsonl').read_text().splitlines()]
    assert len(cases) >= 5
    for case in cases:
        for item in case['input']['files']:
            stored = {'docker': {'Dockerfile': 'root-container.fixture'},
                      'kubernetes': {'privileged.yaml': 'privileged-pod.fixture'}}
            name = stored.get(case['name'], {}).get(item['path'], item['path'])
            assert (PACKAGE / 'evals/fixtures' / case['name'] / name).read_text() == item['text']
    by_name = {case['name']: case for case in cases}
    assert 'CKV_AWS_24' in by_name['terraform']['expected']['rules']
    assert 'CKV_K8S_16' in by_name['kubernetes']['expected']['rules']
    assert 'CKV_DOCKER_8' in by_name['docker']['expected']['rules']
    assert by_name['clean']['expected']['rules'] == []
    assert by_name['refuse']['must_refuse'] is True


@pytest.mark.parametrize('files', [[], [{'path': '../placeholder.tf', 'text': 'placeholder'}],
                                  [{'path': '/placeholder.tf', 'text': 'placeholder'}], [None]])
def test_eval_refuses_unhanded_or_unsafe_files(files):
    result = iac.run_skill({'files': files})
    assert result['refused'] is True and result['status'] == 'not run'


@pytest.mark.asyncio
async def test_room_eval_auth_and_exact_skill_version(monkeypatch):
    # Reproduce a worker that already cached another room's sibling module.
    monkeypatch.setitem(sys.modules, 'gold_sources', type(sys)('placeholder_other_room_gold_sources'))
    monkeypatch.syspath_prepend(str(ROOT / 'agents/radix'))
    # Other room tests import a sibling gold_sources under the same bare name.
    monkeypatch.delitem(sys.modules, 'gold_sources', raising=False)
    spec = importlib.util.spec_from_file_location('placeholder_radix_r5_app', ROOT / 'agents/radix/app.py')
    room = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, room)
    spec.loader.exec_module(room)
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-auth')
    monkeypatch.setattr(iac, 'run_skill', lambda payload: {'status': 'run', 'critical': 0})
    body = {'skill_id': 'scan.iac', 'version': '1.0.0', 'tenant_id': str(Ctx('').tenant_id), 'input': {'files': []}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(room.app), base_url='http://placeholder') as client:
        assert (await client.post('/evals/run', json=body)).status_code == 401
        headers = {'X-Tank-Key': 'placeholder-room-auth'}
        assert (await client.post('/evals/run', json={**body, 'skill_id': 'scan.static'}, headers=headers)).status_code == 404
        assert (await client.post('/evals/run', json={**body, 'version': '9.0.0'}, headers=headers)).status_code == 404
        result = await client.post('/evals/run', json=body, headers=headers)
        assert result.status_code == 200 and result.json() == {'status': 'run', 'critical': 0}
