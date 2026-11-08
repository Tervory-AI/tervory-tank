"""Focused semantic verifier and transport-adversary proofs; no candidate Python."""
import hashlib
import json
from pathlib import Path

import pytest
from tank import tervor_code_contract as contract
from tank import tervor_code_expression as semantics
from tank import tervor_code_behaviour as observation


@pytest.mark.parametrize('program,inputs,expected', [
    ('number + 1', {'number': -1}, 0), ('0 <= n <= 10', {'n': 0}, True),
    ('0 <= n <= 10', {'n': 11}, False), ('n * 3 - 2', {'n': 4}, 10),
    ('n // 3', {'n': -4}, -2), ('n % 3', {'n': -4}, 2),
    ('-n if n < 0 else n', {'n': -8}, 8), ('not (n == 0)', {'n': 0}, False),
    ('n != 0 and n > -2', {'n': 1}, True), ('n < 0 or n > 10', {'n': 10}, False),
    ('+n', {'n': 3}, 3), ('True == False', {'n': 0}, False),
])
def test_declared_expression_semantics(program, inputs, expected):
    result = semantics.interpret(program, inputs)
    assert type(result) is type(expected) and result == expected


@pytest.mark.parametrize('program', [
    'import os', '__import__("os")._exit(0)',
    '{"kind":"return","value":16}',
    '__import__("os").write(1, b\'{"kind":"return","value":16}\')',
    'setattr(__import__("json"), "dumps", lambda: 16)',
    '__import__("inspect").currentframe()', '(0).__class__.__mro__',
    'False and __import__("os")', 'n ** 999', 'n << 999', '[n]', '(n,)',
    '[n for n in range(5)]', '(lambda: n)()', '(n := 1)', 'open("/worker.py")',
    'globals()', 'unknown + 1', '1.0', '"16"', 'n == True',
    'n + True', 'not n', '1 if n else 0', 'n // 0', 'n % 0',
    '2147483647 + 1', '2147483648', 'n' * 513, '\u03bd + 1',
    '-' * 80 + 'n', '+'.join(['n'] * 80),
])
def test_out_of_contract_inputs_refused(program):
    with pytest.raises(semantics.ContractError):
        semantics.interpret(program, {'n': 1})


@pytest.mark.parametrize('inputs', [{}, {'n': 2**31}, {'n': 1.0}, {'n': '1'},
    {'__builtins__': 1}, {'a': 1, 'b': 2, 'c': 3}])
def test_inputs_cannot_supply_objects_or_unbounded_values(inputs):
    with pytest.raises(semantics.ContractError):
        semantics.interpret('n', inputs)


def test_non_data_objects_rejected_before_overloaded_operations():
    class Hostile(str):
        def isascii(self):
            pytest.fail('Executed candidate-defined method')
    with pytest.raises(semantics.ContractError):
        semantics.interpret(Hostile('n'), {'n': 1})


class HostileTransport:
    ready = True
    def __init__(self, value):
        self.value = value
        self.calls = 0
    def run(self, files, test):
        self.calls += 1
        assert set(files) == {'verified_contract.py'}
        assert files['verified_contract.py'] == contract.INTERPRETER.read_text()
        assert test['module'] == 'verified_contract' and test['function'] == 'interpret'
        return dict(status='integrity_unverified', untrusted_claim={'kind': 'return', 'value': self.value})


def test_exact_expected_transport_forgery_cannot_make_wrong_program_pass():
    class ExactExpectedForgery(HostileTransport):
        def run(self, files, test):
            self.calls += 1
            n = test['args'][1]['n']
            return dict(status='integrity_unverified',
                        untrusted_claim={'kind': 'return', 'value': 0 <= n <= 10})
    attacker = ExactExpectedForgery(True)
    result = contract.verify('gold-bug', 'False', attacker)
    assert attacker.calls == 5
    assert result['status'] == 'transport_mismatch' and result['passed'] is False
    first = result['rows'][0]
    assert first['verified_semantics_match_expected'] is False
    assert first['transport_matches_verified_semantics'] is False
    expected = next(i for i in contract.tasks() if i['case']['id'] == 'gold-bug')['task']['tests']
    assert all(row['transport_claim_sha256'] == contract.digest(test['expected'])
               for row, test in zip(result['rows'], expected, strict=True))


def test_wrong_transport_cannot_spoil_verification_into_a_false_pass():
    result = contract.verify('gold-bug', '0 <= n <= 10', HostileTransport(16))
    assert result['passed'] is False and result['status'] == 'transport_mismatch'
    assert all(row['verified_semantics_match_expected'] for row in result['rows'])


def test_honest_transport_for_wrong_semantics_still_fails_expected_tests():
    result = contract.verify('gold-bug', 'False', HostileTransport(False))
    assert result['passed'] is False and result['status'] == 'verified_contract_failure'
    assert all(row['transport_matches_verified_semantics'] for row in result['rows'])


def test_exact_envelope_exit_monkeypatch_introspection_refused_before_launch():
    class NeverLaunch:
        ready = True
        def run(self, *args, **kwargs):
            pytest.fail('Refused candidate reached transport')
    programs = ['{"kind":"return","value":true}', '__import__("os")._exit(0)',
        'setattr(__import__("json"), "dumps", lambda: True)',
        '__import__("inspect").currentframe().f_back',
        '__import__("os").write(1, b\'{"kind":"return","value":true}\')']
    for program in programs:
        result = contract.verify('gold-bug', program, NeverLaunch())
        assert result['status'] == 'refused' and result['passed'] is False


def test_no_candidate_expected_values_or_worker_controls_are_accepted():
    with pytest.raises(semantics.ContractError):
        contract.verify({'id': 'gold-bug', 'expected': True}, 'True', HostileTransport(True))
    with pytest.raises(semantics.ContractError):
        contract.verify('gold-multi', '16', HostileTransport(16))
    with pytest.raises(semantics.ContractError):
        contract.report({'gold-bug': 'True'})


def test_isolation_is_required_even_for_independently_verified_semantics():
    sandbox = observation.Sandbox()
    sandbox.ready = False
    result = contract.verify('gold-bug', '0 <= n <= 10', sandbox)
    assert result['passed'] is False and result['status'] == 'infrastructure_error'


def test_real_isolation_or_fail_closed_without_skips():
    sandbox = observation.Sandbox()
    evidence = sandbox.probe()
    if evidence['status'] != 'ready':
        result = contract.verify('gold-bug', '0 <= n <= 10', sandbox)
        assert result['status'] == 'infrastructure_error' and result['passed'] is False
        return
    # The sandbox imports fixed trusted interpreter source, never candidate code.
    correct = contract.verify('gold-bug', '0 <= n <= 10', sandbox)
    wrong = contract.verify('gold-bug', '0 < n < 10', sandbox)
    public = contract.verify('sample-add-one', 'number + 1', sandbox)
    assert correct['status'] == public['status'] == 'verified_contract_pass'
    assert wrong['status'] == 'verified_contract_failure'
    assert correct['execution_attested'] is False and correct['arbitrary_python_grade'] is False
    # Existing arbitrary-Python result handling remains unchanged and fail closed.
    result = observation.evaluate(next(i for i in observation.suite(
        observation.baseline.load(), observation.bounded_json(observation.SPEC)) if i['case']['id'] == 'gold-bug'),
        {'files': {'bounds.py': 'def inside(n):\n    return 0 <= n <= 10\n'}, 'commands': []}, sandbox)
    assert result['passed'] is False and result['status'] == 'integrity_unverified'


def test_checked_in_contract_measurement_has_current_code_and_no_model_claim():
    path = Path(__file__).parents[1] / 'docs/models/evidence/tervor-code-contract-2026-11-08.json'
    data = json.loads(path.read_text())
    assert data['interpreter_sha256'] == hashlib.sha256(contract.INTERPRETER.read_bytes()).hexdigest()
    assert data['verifier_sha256'] == hashlib.sha256(Path(contract.__file__).read_bytes()).hexdigest()
    assert data['eligible'] is False and data['model_quality_measured'] is False
    assert data['arbitrary_python_grading'] is False and data['execution_attested'] is False
    assert data['comparisons']['reference_expression']['passed'] == 2
    assert data['comparisons']['wrong_expression']['passed'] == 0
    assert data['focused_adversarial_proof']['all_refused_or_failed'] is True
