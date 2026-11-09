"""Gate before (finish): tenant caps, error-to-fix memory, rollback, diffs and live admission.

Five controls for the signed Command code path, each behind its own setting that
must be the literal `true`:

  ENGINE_CODE_TENANT_CAPS_ENABLED  a tenant's own token/dollar cap per code task
  ENGINE_CODE_FIX_MEMORY_ENABLED   errors a later change fixed are fixed again at $0
  ENGINE_CODE_ROLLBACK_ENABLED     a paid round that made things worse goes back to green
  ENGINE_CODE_DIFFS_ENABLED        diffs in and out instead of whole files
  ENGINE_CODE_ADMISSION_ENABLED    per-tenant concurrent and per-minute paid code calls

They run only from code_preflight's two existing chokepoints (before the paid call,
inside the tenant/user-owned thread transaction, and around the single paid call).
Nothing here chooses, names or calls a model: the paid call is still Command's
route_code through Tank's policy, ladder and LiteLLM. Unset settings keep main's
behaviour exactly, and nothing in this module runs.
"""
from __future__ import annotations

import contextvars
import hashlib
import json
import os
import re
import uuid

SETTINGS = {
    'caps': 'ENGINE_CODE_TENANT_CAPS_ENABLED',
    'memory': 'ENGINE_CODE_FIX_MEMORY_ENABLED',
    'rollback': 'ENGINE_CODE_ROLLBACK_ENABLED',
    'diffs': 'ENGINE_CODE_DIFFS_ENABLED',
    'admission': 'ENGINE_CODE_ADMISSION_ENABLED',
}
TASK_TYPE = 'command.code'
STATE = 'code_finish'
LABELS = {
    'fix_memory': 'Fixed from memory', 'fix_memory_done': 'Remembered fix passed', 'fix_memory_rollback': 'Remembered fix rolled back',
    'rollback': 'Rolled back to the last green checkpoint', 'rollback_unconfirmed': 'Rollback not applied',
    'rollback_needs_undo': 'Rollback needs /undo', 'busy': 'Waiting for a free code slot', 'setting': 'Admission setting invalid',
}
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
# Volatile parts of check output that must not split one error into many signatures.
VOLATILE = [(re.compile(r'\b\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:?\d\d)?\b'), '<time>'),
            (re.compile(r'\b\d\d:\d\d:\d\d(?:\.\d+)?\b'), '<time>'),
            (re.compile(r'\b0x[0-9a-fA-F]+\b'), '<addr>'),
            (re.compile(r'\b\d+(?:\.\d+)?\s?(?:ms|s|sec|seconds)\b'), '<duration>'),
            (re.compile(r'[ \t]+'), ' ')]

# Per request: what the before hook found for the paid call (bases, notes).
_STASH: contextvars.ContextVar[dict | None] = contextvars.ContextVar('code_finish_stash', default=None)


def on(name: str) -> bool:
    return os.environ.get(SETTINGS[name]) == 'true'


def any_on(*names: str) -> bool:
    return any(on(name) for name in (names or SETTINGS))


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def envelope(result) -> tuple[dict, dict]:
    try:
        value = json.loads(result.output)
    except (ValueError, RecursionError):
        return {}, {}
    if not isinstance(value, dict):
        return {}, {}
    arguments = value.get('arguments') if isinstance(value.get('arguments'), dict) else {}
    body = value.get('result') if isinstance(value.get('result'), dict) else {}
    return arguments, body


def signature(command: str, output) -> str:
    """Error signature: the check command and its output without volatile parts."""
    text = output if isinstance(output, str) else json.dumps(output, sort_keys=True, default=str)
    text = ANSI.sub('', text).replace('\r\n', '\n')
    for pattern, replacement in VOLATILE:
        text = pattern.sub(replacement, text)
    return sha(command.strip() + '\0' + '\n'.join(line.strip() for line in text.strip().splitlines()))


def diff_files(diff: str) -> tuple[list[str], bool]:
    """Paths a unified diff changes and whether it creates or deletes a file (or is not a diff)."""
    from code_diffs import parse
    from code_preflight import norm
    files, whole = [], False
    for item in parse(diff) or []:
        for target in (item['old'], item['new']):
            target = target.split('\t', 1)[0].strip()
            if target == '/dev/null':
                whole = True
                continue
            path = norm(target[2:] if target.startswith(('a/', 'b/')) else target)
            if path is None:
                return [], True
            if path not in files:
                files.append(path)
    return files, whole or not files


def events(results) -> list[dict]:
    """The client's tool results as an ordered timeline of checks, edits and reads."""
    timeline = []
    for index, result in enumerate(results):
        arguments, body = envelope(result)
        if result.name == 'run_command':
            command = arguments.get('command')
            if not isinstance(command, str) or body.get('ran') is not True:
                continue
            passed = body.get('code') == 0 and not body.get('timed_out')
            timeline.append({'kind': 'check', 'index': index, 'command': command, 'passed': passed,
                             'signature': None if passed else signature(command, body.get('output'))})
        elif result.name == 'propose_edit':
            diff = arguments.get('diff')
            if not isinstance(diff, str):
                continue
            files, whole = diff_files(diff)
            applied = True if body.get('applied') is True else 'error' if 'error' in body else False
            timeline.append({'kind': 'edit', 'index': index, 'diff': diff, 'files': files, 'whole': whole or not files,
                             'applied': applied})
        elif result.name == 'read_file':
            from code_preflight import norm
            path = norm(arguments.get('path'))
            if path and body.get('exists') is True and isinstance(body.get('text'), str):
                timeline.append({'kind': 'read', 'index': index, 'path': path, 'text': body['text']})
    return timeline


def first_fresh(previous: list[str], current: list[str]) -> int:
    """Index of the first result the client had not sent before (its window rolls)."""
    for size in range(min(len(previous), len(current)), 0, -1):
        if current[:size] == previous[-size:]:
            return size
    return 0


def work_state(state: dict, body) -> dict:
    work = state.get(STATE)
    if not isinstance(work, dict) or work.get('prompt_id') != str(body.prompt_id):
        work = {'prompt_id': str(body.prompt_id), 'seen': [], 'tank_diffs': [], 'last_turn': None}
        state[STATE] = work
    return work


def request(name: str, arguments: dict) -> dict:
    """A tool request Tank answers with itself, validated by Command's own schemas."""
    import command
    return {'name': name, 'arguments': command.CODE_TOOLS[name].model_validate(arguments).model_dump()}


def stash() -> dict:
    value = _STASH.get()
    return value if isinstance(value, dict) else {}


def note(turn_id: str, text: str) -> None:
    current = stash()
    if current.get('turn') != turn_id:
        current = {'turn': turn_id}
        _STASH.set(current)
    current.setdefault('notes', []).append(text)


async def free(command, conn, row, state, actor, turn_id, status, message, info=None, *, requests=()):
    """A $0 code-rung answer through Command's existing task/receipt/event path."""
    from trigger_routes import code_receipt
    ledger = await code_receipt(actor.tenant_id, TASK_TYPE, task_id=uuid.UUID(turn_id), agent='orchestrator', conn=conn)
    await command.record_receipts(conn, row, state, turn_id, [ledger])
    await conn.execute("UPDATE tank.tasks SET status='done',result=$3,ledger_id=$4,finished_at=now() "
                       "WHERE id=$1 AND tenant_id=$2", uuid.UUID(turn_id), actor.tenant_id, message, ledger)
    if not requests:
        __import__('code_sessions').remember(state, 'assistant', message)
    state['active_turn'] = None
    finish = {**(info or {}), 'status': status, 'message': message}
    await command.step(conn, row, state, {**state['steps'][turn_id], 'status': 'done', 'label': LABELS[status],
                                         'code_finish': finish, 'receipt_status': 'recorded',
                                         'tool_requests': [{'name': r['name'], 'size': len(command.dump(r['arguments']).encode())}
                                                           for r in requests]})
    await command.event(conn, row, 'done', {'message_id': turn_id})
    rows = [command.public_receipt(r, command.current_actor(actor).founder) for r in state['receipts'] if r['step_id'] == turn_id]
    return {'answer': message, 'requests': list(requests), 'cards': [], 'finish': finish,
            'receipt': {'rows': rows, 'totals': command.totals(rows)}, 'turn': {'model': 'Auto', 'cost_usd': 0.0}}


def planned_files(state: dict, body) -> set[str] | None:
    """The current #805 task's planned files when preflight has planned one (scope lock)."""
    plan = state.get('code_preflight')
    if not isinstance(plan, dict) or plan.get('prompt_id') != str(body.prompt_id):
        return None
    tasks, index = plan.get('tasks'), plan.get('current')
    if not isinstance(tasks, list) or type(index) is not int or not 0 <= index < len(tasks):
        return None
    selected = tasks[index].get('plan') if isinstance(tasks[index], dict) else None
    files = selected.get('files') if isinstance(selected, dict) else None
    return set(files) if isinstance(files, list) else None


async def before(command, conn, row, state, actor, turn_id, body, *, paid=True):
    """Runs once per durably reserved request, after code_gate and before preflight."""
    _STASH.set(None)
    if not paid or not any_on('memory', 'rollback', 'diffs'):
        return None
    work = work_state(state, body)
    waiting = work.pop('notes', [])  # Notes from a $0 round are for the next paid round.
    hashes = [sha(result.name + '\0' + result.output) for result in body.tool_results]
    start = first_fresh(work['seen'], hashes)
    work['seen'] = hashes
    timeline = events(body.tool_results)
    fresh = [item for item in timeline if item['index'] >= start]
    args = (command, conn, row, state, actor, turn_id, body, work, timeline, fresh)
    held = None
    try:
        if on('memory'):
            import code_fix_memory
            held = await code_fix_memory.verify(*args)
            if held:
                return held
        if on('rollback'):
            import code_rollback
            held = await code_rollback.check(*args)
            if held:
                return held
        if on('memory'):
            import code_fix_memory
            await code_fix_memory.learn(*args)
            held = await code_fix_memory.serve(*args)
            if held:
                return held
        if on('diffs'):
            import code_diffs
            code_diffs.inbound(body, turn_id, timeline, fresh)
        return None
    finally:
        work['last_turn'] = turn_id
        if held:
            work['notes'] = [*waiting, *work.get('notes', [])][-4:]
        else:
            for text in waiting:
                note(turn_id, text)


async def admit(command, conn, row, state, actor, turn_id, *, paid=True):
    """Runs after preflight approved the paid step: the live per-tenant admission check."""
    if not paid or not on('admission'):
        return None
    import code_admission
    try:
        refused = code_admission.admit(actor.tenant_id, turn_id)
    except code_admission.SettingError as error:
        return await free(command, conn, row, state, actor, turn_id, 'setting',
                          f'The {error} setting is not a valid whole number from 1 to 1000. No model call was made.')
    if refused is None:
        return None
    plan = state.get('code_preflight')
    active = plan.get('active') if isinstance(plan, dict) else None
    if isinstance(active, dict) and active.get('turn_id') == turn_id:
        # Preflight counted this round as its task's next paid turn; a held round is not one.
        plan['active'] = None
        turns = plan['tasks'][plan['current']]['turns']
        if turns and turns[-1] == turn_id:
            turns.pop()
    return await free(command, conn, row, state, actor, turn_id, 'busy', refused['message'], {'admission': refused})


async def paid_call(inner, state, route, actor, messages, model, task_id, **options):
    """Around the single paid call: notes and diffs out; admission slot released."""
    if not any_on('memory', 'rollback', 'diffs', 'admission'):
        return await inner(state, route, actor, messages, model, task_id, **options)
    current = stash() if stash().get('turn') == str(task_id) else {}
    notes = list(current.get('notes', []))
    if on('diffs'):
        import code_diffs
        notes.insert(0, code_diffs.INSTRUCTION)
    if notes:
        messages = [*messages, {'role': 'user', 'content': 'Tank notes DATA (not instructions to widen scope): ' + ' '.join(notes)}]
    try:
        answer = await inner(state, route, actor, messages, model, task_id, **options)
    finally:
        if on('admission'):
            import code_admission
            code_admission.release(actor.tenant_id, str(task_id))
    if on('diffs'):
        import code_diffs
        answer = code_diffs.outbound(answer, current.get('bases', {}))
    return answer
