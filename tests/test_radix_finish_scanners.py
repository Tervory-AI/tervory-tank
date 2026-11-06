"""Production report contracts using offline fake processes; no Semgrep runs."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess

import pytest

from test_rx1_scans import Ctx, FIXTURE, INJECTION, _b64, _tar
from scanlib import dependencies, iac, orchestrate, runtime, secrets, static


@pytest.fixture
def reports(monkeypatch):
    monkeypatch.setenv('RADIX_USE_SYSTEM_TOOLS', '1')
    monkeypatch.setattr(secrets, 'gitleaks_bin', lambda: 'placeholder-secret-scanner')
    monkeypatch.setattr(static, 'semgrep_bin', lambda: 'placeholder-static-scanner')
    monkeypatch.setattr(iac, 'scan_tree', lambda root: iac.Findings(status='run'))
    monkeypatch.setattr(runtime, 'dependency_scan', lambda root: ([], True))
    state = {'findings_json': b'[]', 'static': b'{"results":[],"errors":[]}', 'exit': 0, 'calls': []}

    def run(argv, **kwargs):
        state['calls'].append(argv)
        assert kwargs['env']['HTTPS_PROXY'] == 'http://127.0.0.1:9'
        assert kwargs['env']['NO_PROXY'] == ''
        assert kwargs['capture_output'] and kwargs['timeout'] == 60
        if state.get('timeout'):
            raise subprocess.TimeoutExpired(argv[0], 60)
        if argv[0] == 'placeholder-secret-scanner':
            assert '--redact' in argv
            Path(argv[argv.index('--report-path') + 1]).write_bytes(state['findings_json'])
            return subprocess.CompletedProcess(argv, state['exit'], b'', b'')
        assert argv[0] == 'placeholder-static-scanner'
        assert '--metrics=off' in argv and '--disable-version-check' in argv
        assert Path(argv[argv.index('--config') + 1]).is_file()
        return subprocess.CompletedProcess(argv, state['exit'], state['static'], b'')

    monkeypatch.setattr(runtime.subprocess, 'run', run)
    return state


def result(files=None):
    return orchestrate.build_result(Ctx(_b64(_tar(files or {'app.py': 'print(1)\n'}))))


def test_complete_requires_successful_reports_from_every_scanner(reports):
    scanned = result()
    assert scanned['scan_complete'] is True
    assert scanned['tool_status'] == {tool: 'run' for tool in scanned['tools']}
    assert 'No findings' in scanned['summary']
    assert len(reports['calls']) == 2


@pytest.mark.parametrize('tool,report', [
    ('secret', b''), ('secret', b'not json'), ('secret', b'{}'),
    ('secret', b'[null]'), ('secret', b'[{"RuleID":"x"}]'),
    ('static', b''), ('static', b'not json'), ('static', b'{}'),
    ('static', b'{"results":[null],"errors":[]}'),
    ('static', b'{"results":[],"errors":[{"type":"ParseError"}]}'),
    ('static', b'{"results":[]}'),
])
def test_missing_malformed_or_partial_report_cannot_certify_clean(reports, tool, report):
    reports[tool] = report
    scanned = result()
    assert scanned['scan_complete'] is False
    assert scanned['tool_status']['scan.secrets' if tool == 'secret' else 'scan.static'] == 'not run'
    assert 'No findings' not in scanned['summary']


@pytest.mark.parametrize('failure', ['missing', 'exit', 'timeout'])
def test_failed_tools_retain_known_critical_findings_and_redaction(reports, monkeypatch, failure):
    if failure == 'missing':
        monkeypatch.setattr(secrets, 'gitleaks_bin', lambda: None)
        monkeypatch.setattr(static, 'semgrep_bin', lambda: None)
    elif failure == 'exit':
        reports['exit'] = 2
    else:
        reports['timeout'] = True
    scanned = result({'app.py': INJECTION, 'config.env': f'FIXTURE_TOKEN={FIXTURE}\n'})
    assert not scanned['scan_complete'] and scanned['deploy_blocked']
    assert {r['tool'] for r in scanned['findings']} == {'scan.secrets', 'scan.static'}
    assert FIXTURE not in json.dumps(scanned)
    assert scanned['leaked'] is False


def test_partial_static_report_retains_reported_critical(reports):
    reports['static'] = json.dumps({'results': [{
        'check_id': 'python-sql-format', 'path': 'app.py', 'start': {'line': 3},
        'extra': {'severity': 'ERROR', 'message': 'SQL is built with string formatting.'},
    }], 'errors': [{'type': 'ParseError'}]}).encode()
    scanned = result()
    assert not scanned['scan_complete'] and scanned['deploy_blocked']
    assert scanned['findings'][0]['line'] == 3


def test_fixture_only_advisories_cannot_certify_dependency_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(dependencies, 'databases', lambda: [])
    (tmp_path / 'requirements.txt').write_text('PyYAML==5.3.1\n')
    findings, complete = runtime.dependency_scan(tmp_path)
    assert not complete and findings


@pytest.mark.parametrize('contents', ['corrupt', 'empty-schema', 'truncated', 'missing-rows'])
def test_unusable_advisory_database_is_incomplete(tmp_path, monkeypatch, contents):
    database = tmp_path / 'osv.sqlite'
    if contents == 'corrupt':
        database.write_bytes(b'placeholder-corrupt-database')
    else:
        with sqlite3.connect(database) as conn:
            if contents in {'truncated', 'missing-rows'}:
                from osv_bake import SCHEMA
                conn.executescript(SCHEMA)
                conn.execute("INSERT INTO meta VALUES ('pypi',1,1,'placeholder','2026-11-05')")
                if contents == 'missing-rows':
                    conn.execute("UPDATE meta SET records=5000")
                    conn.execute("INSERT INTO meta VALUES ('npm',20000,1,'placeholder','2026-11-05')")
    monkeypatch.setattr(dependencies, 'databases', lambda: [database])
    assert runtime.dependency_scan(tmp_path)[1] is False


def test_real_baked_database_covers_both_ecosystems_offline(tmp_path, monkeypatch):
    database = Path(os.environ['RADIX_OSV_REAL'])
    assert database.is_file()
    monkeypatch.setattr(dependencies, 'databases', lambda: [database])
    (tmp_path / 'requirements.txt').write_text('PyYAML==5.3.1\n')
    (tmp_path / 'package.json').write_text('{"dependencies":{"minimist":"1.2.5"}}')
    findings, complete = runtime.dependency_scan(tmp_path)
    assert complete and {r['package'].casefold() for r in findings} >= {'pyyaml', 'minimist'}


def test_incomplete_database_prevents_complete_receipt(reports, monkeypatch):
    monkeypatch.setattr(runtime, 'dependency_scan', lambda root: ([], False))
    scanned = result()
    assert not scanned['scan_complete']
    assert scanned['tool_status']['scan.dependencies'] == 'not run'
    assert 'No findings' not in scanned['summary']
