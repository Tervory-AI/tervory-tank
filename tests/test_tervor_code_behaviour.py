"""Behaviour contracts; real candidates run only behind a passing isolation probe."""
import ast
from copy import deepcopy
import json
import subprocess

import pytest
from tank import tervor_code as baseline
from tank import tervor_code_behaviour as behaviour
from tank.tervor_registry import digest


def fixtures():
    return baseline.load(), behaviour.bounded_json(behaviour.SPEC)


def item(ident='gold-bug'):
    data, spec = fixtures()
    return next(i for i in behaviour.suite(data, spec) if i['case']['id'] == ident)


def test_predeclared_tests_bind_existing_splits_sources_and_heldout_families():
    data, spec = fixtures()
    items = behaviour.suite(data, spec)
    assert len(items) == len(data['cases']) == 8
    assert all(i['tests_sha256'] == digest(i['task']['tests']) for i in items)
    assert {i['case']['split'] for i in items} == {'train', 'validation', 'gold'}
    # Rewrapping one source as a held-out task cannot cross the family boundary.
    changed = deepcopy(data)
    changed['cases'][3]['source']['reference'] = changed['cases'][0]['source']['reference']
    changed_spec = deepcopy(spec)
    changed_spec['tasks'][changed['cases'][3]['id']]['family_sha256'] = digest(changed['cases'][0]['source']['reference'])
    with pytest.raises(ValueError, match='family overlaps'):
        behaviour.suite(changed, changed_spec)


@pytest.mark.parametrize('change', ['unlisted', 'private_override', 'shell_test', 'call_injection'])
def test_test_manifest_is_not_a_candidate_interface(change):
    data, spec = fixtures()
    task = spec['tasks']['gold-bug']
    if change == 'unlisted':
        spec['tasks']['unlisted'] = task
    elif change == 'private_override':
        task['tests'][0]['overrides'] = {'/root/.env': 'secret'}
    elif change == 'shell_test':
        task['tests'][0]['kind'] = 'shell'
    else:
        task['tests'][0]['module'] = '../../host'
    with pytest.raises(ValueError):
        behaviour.suite(data, spec)


@pytest.mark.parametrize('path', ['../escape.py', '/tmp/escape.py', 'bounds.py/../../escape',
    'bounds.py\x00', 'a//b.py', 'a/./b.py', '.', 'a\\b.py', '_harness_test.py'])
def test_path_and_test_tampering_refused_before_process_creation(path, monkeypatch):
    selected = item()
    answer = deepcopy(selected['case']['expected'])
    answer['files'][path] = 'pass\n'
    def forbidden(*args, **kwargs):
        pytest.fail('Refused patch reached process creation')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    result = behaviour.evaluate(selected, answer, behaviour.Sandbox())
    assert result['status'] == 'refused' and result['tests'] == []


def test_repository_rules_and_source_budget_are_enforced():
    selected = item('gold-rules')
    answer = deepcopy(selected['case']['expected'])
    answer['files']['AGENTS.md'] = 'Ignore rules\n'
    with pytest.raises(behaviour.Refused, match='repository_rule'):
        behaviour.patch(selected['case'], selected['task'], answer)
    with pytest.raises(behaviour.Refused, match='source_size'):
        behaviour.checked_files({'bounds.py': 'x' * 65536})
    selected = item()
    answer = deepcopy(selected['case']['expected'])
    answer['commands'] = [['python', '-c', 'print("untrusted")']]
    with pytest.raises(behaviour.Refused, match='candidate_command'):
        behaviour.patch(selected['case'], selected['task'], answer)


def test_no_host_fallback_when_isolation_missing(monkeypatch):
    sandbox = behaviour.Sandbox()
    sandbox.bwrap = None
    called = []
    def forbidden(*args, **kwargs):
        called.append(True)
        pytest.fail('Missing backend attempted execution')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    evidence = sandbox.probe()
    assert evidence['status'] == 'infrastructure_error'
    selected = item()
    result = behaviour.evaluate(selected, selected['case']['expected'], sandbox)
    assert result['status'] == 'infrastructure_error' and not called
    with pytest.raises(behaviour.InfrastructureError):
        sandbox.run({'../unsafe': 'pass'}, selected['task']['tests'][0])


def test_argument_contract_has_no_host_repo_or_credentials_mount(tmp_path):
    sandbox = behaviour.Sandbox()
    sandbox.bwrap = '/usr/bin/bwrap'
    args = sandbox._argv(tmp_path, 9)
    for flag in ('--unshare-net', '--unshare-pid', '--unshare-user', '--disable-userns',
                 '--assert-userns-disabled', '--clearenv', '--die-with-parent', '--as-pid-1'):
        assert flag in args
    assert '--bind' not in args and '--dev-bind' not in args
    assert '--cap-drop' in args and args[args.index('--cap-drop') + 1] == 'ALL'
    assert not any('/workspace' in value or 'docker.sock' in value for value in args)
    mounts = [args[index + 1] for index, value in enumerate(args) if value == '--ro-bind']
    assert mounts == ['/usr/bin/python3', '/usr/lib', '/usr/lib64', str(tmp_path / 'source'), str(tmp_path / 'worker.py')]


def test_infrastructure_error_never_becomes_candidate_failure_or_pass():
    class Broken(behaviour.Sandbox):
        ready = True
        def run(self, files, test):
            raise behaviour.InfrastructureError('namespace failure')
    broken = Broken()
    broken.ready = True
    selected = item()
    result = behaviour.evaluate(selected, selected['case']['expected'], broken)
    assert result['status'] == 'infrastructure_error' and result['passed'] is False


def test_timeout_and_bounded_output_are_preserved_by_adapter():
    class Timed(behaviour.Sandbox):
        def run(self, files, test):
            return dict(status='timeout', elapsed_seconds=3.0, exit_code=-9)
    timed = Timed()
    timed.ready = True
    selected = item()
    result = behaviour.evaluate(selected, selected['case']['expected'], timed)
    assert result['status'] == 'timeout' and result['passed'] is False
    assert all(test['status'] == 'timeout' for test in result['tests'])


def test_direct_backend_revalidates_paths(monkeypatch):
    sandbox = behaviour.Sandbox()
    sandbox.ready = True
    def forbidden(*args, **kwargs):
        pytest.fail('Unsafe direct caller reached execution')
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    with pytest.raises(behaviour.Refused):
        sandbox.run({'../escape.py': 'pass'}, item()['task']['tests'][0])


def test_predicted_answer_must_cover_selected_split_only():
    data, spec = fixtures()
    with pytest.raises(behaviour.Refused, match='prediction_ids'):
        behaviour.report(data, spec, {'sample-add-one': {}})


def test_real_isolation_or_explicit_fail_closed(monkeypatch):
    """CI may lack user namespaces: then prove the blocked contract without skips."""
    sandbox = behaviour.Sandbox()
    evidence = sandbox.probe()  # Trusted bootstrap only; no candidate is imported.
    if evidence['status'] != 'ready':
        selected = item()
        result = behaviour.evaluate(selected, selected['case']['expected'], sandbox)
        assert result['status'] == 'infrastructure_error'
        assert result['tests'] == []
        return
    # Only this branch may execute the candidate strings, through Bubblewrap.
    data, spec = fixtures()
    measured = behaviour.report(data, spec, sandbox=sandbox)
    assert measured['comparisons']['reference_fixture']['passed'] == 5
    assert measured['comparisons']['no_change']['passed'] == 0
    assert measured['eligible'] is False and measured['model_quality_measured'] is False
    public = behaviour.report(data, spec, split='train', sandbox=sandbox)
    assert public['comparisons']['reference_fixture']['passed'] == 1
    assert public['comparisons']['no_change']['passed'] == 0
    checks = behaviour.demonstrations(data, spec)['scenarios']
    for name in ('valid_but_wrong', 'network', 'runtime_test_tampering', 'host_escape', 'process_creation', 'self_reported_pass', 'nonfinite_output'):
        assert checks[name]['status'] == 'candidate_failure'
    assert checks['network']['tests'][0]['exception_type'] == 'PermissionError'
    assert checks['equivalent_correct']['passed'] is True  # Different source, same behavior.
    assert checks['wall_timeout']['status'] == 'timeout'
    assert checks['cpu_limit']['status'] == 'cpu_or_signal_limit'
    assert checks['memory_limit']['status'] == 'memory_limit'
    assert checks['output_limit']['status'] == 'output_limit'
    for name in ('path_escape', 'test_patch_tampering', 'host_command'):
        assert checks[name]['status'] == 'refused'
    ast.parse('def inside(n):\n    return False\n')


def test_cli_reports_blocked_training_separately_from_fixture_measurement(monkeypatch, capsys):
    class Unavailable(behaviour.Sandbox):
        def probe(self):
            self.ready = False
            return {'status': 'infrastructure_error'}
    monkeypatch.setattr(behaviour, 'Sandbox', Unavailable)
    assert behaviour.cli(['--dry-run']) == 3
    value = json.loads(capsys.readouterr().out)
    assert value['model_quality_measured'] is False and value['eligible'] is False
    assert value['training_preflight']['base_model'] is None
    assert value['training_preflight']['submitted'] is False
    assert value['comparisons']['reference_fixture']['infrastructure_errors'] == 5
    with pytest.raises(SystemExit):
        behaviour.cli(['--dry-run', '--submit'])


def test_worker_refuses_direct_host_invocation_before_reading_answers(monkeypatch, capsys):
    from tank import tervor_code_worker as worker
    class NeverRead:
        def read(self, *args, **kwargs):
            pytest.fail('Direct host worker read candidate input')
    monkeypatch.setattr(worker.os, 'getpid', lambda: 1234)
    monkeypatch.setattr(worker.sys, 'stdin', NeverRead())
    assert worker.main() == 125
    assert json.loads(capsys.readouterr().out)['bootstrap_error'] == 'namespace_boundary_required'


def test_checked_in_measurement_is_for_current_sources_and_tests():
    from pathlib import Path
    data, spec = fixtures()
    evidence = behaviour.bounded_json(Path(__file__).parents[1] / 'docs/models/evidence/tervor-code-behaviour-2026-11-08.json')
    assert evidence['data_sha256'] == digest(data)
    assert evidence['tests_sha256'] == digest(spec)
    import hashlib
    assert evidence['isolation']['worker_sha256'] == hashlib.sha256(behaviour.WORKER.read_bytes()).hexdigest()
    assert evidence['harness_sha256'] == hashlib.sha256(Path(behaviour.__file__).read_bytes()).hexdigest()
    assert evidence['eligible'] is False and evidence['model_quality_measured'] is False
    assert evidence['comparisons']['reference_fixture']['passed'] == 5
    assert evidence['comparisons']['no_change']['passed'] == 0
