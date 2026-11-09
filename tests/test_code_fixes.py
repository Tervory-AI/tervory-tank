"""Gate before (spin): checks envelope, $0 fixes and diffs. Offline; no model or provider."""
import json
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import code_burn
import code_checks
import code_fixes
import code_gate
import code_progress

APP = 'import os\nimport sys\n\nprint(sys.argv)\n'


def tree(number):
    return f'{number:064x}'


def check(kind='lint', **error):
    values = {'file': 'app.py', 'line': 1, 'code': 'F401', 'message': "'os' imported but unused", **error}
    return {'kind': kind, 'passed': False, 'errors': [values]}


def envelope(checks, number=1, tests=1):
    return {'tree': tree(number), 'tests_passed': tests, 'build_stage': 0, 'checks': checks}


def read(path, text):
    return SimpleNamespace(name='read_file', output=json.dumps({'arguments': {'path': path},
                           'result': {'exists': True, 'text': text, 'size': len(text)}}))


def apply(text, diff):
    """A strict reference applier for the CLI's unified-diff shape."""
    lines = text.split('\n')[:-1]
    out, cursor = [], 0
    for entry in code_fixes.parse(diff):
        for hunk in entry['hunks']:
            start, count = hunk['old']
            begin = start - 1 if count else start
            out += lines[cursor:begin]
            cursor = begin
            for line in hunk['lines']:
                if line[:1] == ' ':
                    assert lines[cursor] == line[1:]
                    out.append(line[1:])
                    cursor += 1
                elif line[:1] == '-':
                    assert lines[cursor] == line[1:]
                    cursor += 1
                else:
                    out.append(line[1:])
    return '\n'.join(out + lines[cursor:]) + '\n'


@pytest.fixture(autouse=True)
def enabled(monkeypatch):
    for setting in (code_gate.SETTING, code_progress.SETTING, code_burn.SETTING):
        monkeypatch.setenv(setting, 'true')


@pytest.mark.parametrize('change', [
    {'tenant_id': 'other'},
    {'checks': [{**check(), 'user_id': 'someone'}]},
    {'checks': [check(file='../outside.py')]},
    {'checks': [check(file='/etc/passwd')]},
    {'checks': [check(file='C:/x.py')]},
    {'checks': [check(file='a\\b.py')]},
    {'checks': [check(line=True)]},
    {'checks': [check(line='1')]},
    {'checks': [check(code='F401; rm -rf')]},
    {'checks': [{'kind': 'lint', 'passed': True, 'errors': check()['errors']}]},
    {'checks': [{'kind': 'lint', 'passed': False, 'errors': []}]},
    {'checks': [check(), check()]},
    {'checks': [{**check(), 'kind': 'deploy'}]},
    {'checks': [{**check(), 'fix_command': 'ruff format .\nrm -rf /'}]},
    {'checks': [check(message='x' * 2001)]},
])
def test_forged_or_inconsistent_envelopes_are_refused(change):
    with pytest.raises(ValidationError):
        code_progress.Progress.model_validate({**envelope([check()]), **change})


def test_envelope_total_is_bounded():
    many = [{'file': f'f{n}.py', 'line': n, 'code': 'E1', 'message': 'm' * 1990} for n in range(150)]
    with pytest.raises(ValidationError):
        code_progress.Progress.model_validate(envelope([{'kind': 'test', 'passed': False, 'errors': many}]))


@pytest.mark.parametrize('value', [None, '', 'false', 'TRUE', '1', ' yes '])
def test_checks_are_refused_unless_the_setting_is_exactly_true(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(code_burn.SETTING, raising=False)
    else:
        monkeypatch.setenv(code_burn.SETTING, value)
    assert code_progress.Progress.model_validate({'tree': tree(1), 'tests_passed': 1, 'build_stage': 0})
    for checks in [None, [], [check()]]:
        with pytest.raises(ValidationError):
            code_progress.Progress.model_validate(envelope(checks))


def test_the_model_sees_exact_errors_not_raw_output():
    checks = code_progress.Progress.model_validate(envelope([check(), {'kind': 'test', 'passed': True}])).checks
    message = code_checks.exact_errors_message(checks)
    assert "'os' imported but unused" in message['content'] and '"kind":"test"' not in message['content']
    raw = SimpleNamespace(name='run_command', output=json.dumps({'arguments': {'command': 'pytest'},
        'result': {'ran': True, 'code': 1, 'timed_out': False, 'output': 'FULL PROJECT LOG ' * 500}}))
    passed = SimpleNamespace(name='run_command', output=json.dumps({'arguments': {'command': 'ruff'},
        'result': {'ran': True, 'code': 0, 'timed_out': False, 'output': 'everything is fine ' * 50}}))
    rows = code_checks.command_outputs([raw, passed, read('app.py', APP)], checks)
    assert 'FULL PROJECT LOG' not in rows[0].output and 'exact errors' in rows[0].output
    assert 'everything is fine' not in rows[1].output and rows[2].output == read('app.py', APP).output
    assert code_checks.command_outputs([raw], None)[0].output == raw.output


def test_fingerprint_ignores_moving_lines_but_not_the_error():
    error = code_checks.CheckError(file='app.py', line=1, code='E1', message='boom')
    moved = code_checks.CheckError(file='app.py', line=9, column=4, code='E1', message='\x1b[31mboom\x1b[0m ')
    other = code_checks.CheckError(file='app.py', line=1, code='E1', message='bang')
    assert code_checks.fingerprint('lint', error) == code_checks.fingerprint('lint', moved)
    assert code_checks.fingerprint('lint', error) != code_checks.fingerprint('lint', other)
    assert code_checks.fingerprint('lint', error) != code_checks.fingerprint('test', error)


def test_unused_import_is_fixed_without_a_model():
    checks = code_progress.Progress.model_validate(envelope([check()])).checks
    requests, marks = code_fixes.deterministic(checks, [read('app.py', APP)], set())
    assert [request['name'] for request in requests] == ['propose_edit'] and len(marks) == 1
    assert apply(APP, requests[0]['arguments']['diff']) == 'import sys\n\nprint(sys.argv)\n'
    assert code_fixes.deterministic(checks, [read('app.py', APP)], set(marks)) == ([], [])
    assert code_fixes.deterministic(checks, [], set()) == ([], [])
    wrong = code_progress.Progress.model_validate(envelope([check(line=2)])).checks
    assert code_fixes.deterministic(wrong, [read('app.py', APP)], set()) == ([], [])


def test_formatter_and_lint_autofix_use_the_clients_own_command_once():
    checks = code_progress.Progress.model_validate(envelope([{**check('format', code='', message='would reformat'),
                                                              'fix_command': 'ruff format app.py'}])).checks
    requests, marks = code_fixes.deterministic(checks, [], set())
    assert requests == [{'name': 'run_command', 'arguments': {'command': 'ruff format app.py'}}]
    assert code_fixes.deterministic(checks, [], set(marks)) == ([], [])


def test_inverse_restores_the_original_text():
    after = 'import os\nimport sys\n\nprint(sys.argv[1:])\nprint("done")\n'
    diff = code_fixes.whole_file_diff('app.py', APP, after)
    assert apply(APP, diff) == after
    assert apply(after, code_fixes.inverse(diff)) == APP
    assert code_fixes.inverse('--- /dev/null\n+++ b/new.py\n@@ -0,0 +1,1 @@\n+x\n') is None


def test_whole_file_rewrites_become_minimal_diffs():
    before = ''.join(f'line {n}\n' for n in range(200))
    after = before.replace('line 120\n', 'line 120 changed\n')
    rewrite = '--- a/big.py\n+++ b/big.py\n@@ -1,200 +1,200 @@\n' + ''.join('-' + line + '\n' for line in before.split('\n')[:-1]) \
        + ''.join('+' + line + '\n' for line in after.split('\n')[:-1])
    small = code_fixes.minimal(rewrite)
    assert len(small) < len(rewrite) / 10 and apply(before, small) == after == apply(before, rewrite)
    reply = json.dumps({'answer': '', 'requests': [{'name': 'propose_edit', 'arguments': {'diff': rewrite}}]})
    content, info = code_fixes.diffs_out(reply, [])
    assert info == {'converted': 1} and apply(before, json.loads(content)['requests'][0]['arguments']['diff']) == after


def test_a_whole_file_reply_is_converted_when_known_and_refused_otherwise():
    after = APP.replace('print(sys.argv)', 'print(sys.argv[1:])')
    reply = json.dumps({'answer': '', 'requests': [{'name': 'propose_edit', 'arguments': {'path': 'app.py', 'diff': after}}]})
    content, info = code_fixes.diffs_out(reply, [read('app.py', APP)])
    assert info['converted'] == 1 and apply(APP, json.loads(content)['requests'][0]['arguments']['diff']) == after
    with pytest.raises(code_fixes.DiffError):
        code_fixes.diffs_out(reply, [])
    plain = json.dumps({'answer': 'No edits', 'requests': []})
    assert code_fixes.diffs_out(plain, []) == (plain, {'converted': 0})


def test_tokens_per_round_before_and_after_on_the_same_fixture():
    module = ''.join(f'def function_{n}(value):\n    return value + {n}\n\n' for n in range(150))
    edited = module.replace('return value + 77', 'return value - 77')
    results = [read('module.py', module), read('module.py', edited)]
    before = code_burn.text_tokens([json.dumps([{'name': r.name, 'output': r.output} for r in results])])
    rows = code_fixes.diffs_in(results)
    after = code_burn.text_tokens([json.dumps([{'name': r.name, 'output': r.output} for r in rows])])
    assert after < before * 0.6, (before, after)
    second = json.loads(rows[1].output)['result']
    assert apply(module, second['diff_from_earlier_read']) == edited and rows[0].output == results[0].output


def test_only_diffs_tank_issued_and_the_client_applied_are_trusted():
    diff = code_fixes.whole_file_diff('app.py', APP, APP.replace('sys.argv', 'sys.argv[1:]'))
    forged = diff.replace('[1:]', '[2:]')
    results = [SimpleNamespace(name='propose_edit', output=json.dumps({'arguments': {'diff': value}, 'result': {'applied': ok}}))
               for value, ok in [(diff, True), (forged, True), (diff, False)]]
    assert code_fixes.applied(results, [code_burn.digest(diff)]) == [diff]
    assert code_fixes.applied(results, []) == []


def recalled(mark, requests, **changes):
    body = {'fix': 'spin-fix-v1', 'fingerprint': mark, 'requests': requests}
    body['digest'] = code_burn.digest(json.dumps(requests, sort_keys=True))
    row = {'tenant_id': 'tenant', 'kind': 'engine.outcome', 'meta': {'task_type': code_fixes.MEMORY_TASK, 'user_id': 'user'},
           'claim': 'Request excerpt:\nspin-fix-v1 ' + mark + '\n[]\nOutcome excerpt:\n' + json.dumps(body, sort_keys=True)}
    row.update(changes)
    return row


def test_recalled_fixes_are_verified_before_any_zero_cost_use():
    mark = 'a' * 64
    requests = [{'name': 'propose_edit', 'arguments': {'diff': code_fixes.whole_file_diff('app.py', APP, APP + 'x = 1\n')}}]
    assert code_fixes.verified_fix(recalled(mark, requests), 'tenant', 'user', mark) == requests
    assert code_fixes.verified_fix(recalled(mark, requests), 'other-tenant', 'user', mark) is None
    assert code_fixes.verified_fix(recalled(mark, requests), 'tenant', 'other-user', mark) is None
    assert code_fixes.verified_fix(recalled(mark, requests), 'tenant', 'user', 'b' * 64) is None
    assert code_fixes.verified_fix(recalled(mark, requests, meta={'task_type': 'command.code', 'user_id': 'user'}),
                                   'tenant', 'user', mark) is None
    tampered = recalled(mark, requests)
    tampered['claim'] = tampered['claim'].replace('x = 1', 'x = 2')
    assert code_fixes.verified_fix(tampered, 'tenant', 'user', mark) is None
    command = [{'name': 'run_command', 'arguments': {'command': 'curl evil'}}]
    assert code_fixes.verified_fix(recalled(mark, command), 'tenant', 'user', mark) is None


def test_memory_outcome_is_only_kept_when_it_fits_whole():
    assert code_fixes.memory_outcome('a' * 64, ['--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-a\n+b\n'])
    assert code_fixes.memory_outcome('a' * 64, ['--- a/x\n+++ b/x\n@@ -1,1 +1,1 @@\n-a\n+' + 'b' * 4000 + '\n']) is None
