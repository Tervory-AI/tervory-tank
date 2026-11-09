"""Gate before (finish): rollback to the last green checkpoint (ENGINE_CODE_ROLLBACK_ENABLED).

Uses the existing progress evidence (tree digest, tests passing, build stage), so
it also needs ENGINE_CODE_GATE_ENABLED and ENGINE_CODE_PROGRESS_ENABLED; without
evidence it does nothing. Each round's evidence is a checkpoint; a checkpoint is
green when every check the client ran in that round passed. When a paid round's
edits leave fewer tests passing or the build further back, Tank answers at $0 with
the inverse diffs back to the last green checkpoint (or the task start), and the
next envelope must report that checkpoint's tree before any further paid call.
State lives in the tenant/user-owned thread with the other code gates; it resets
with each new prompt.
"""
from __future__ import annotations

import code_finish

MAX_CHECKPOINTS = 8
MAX_UNDO = 5  # inverse edits plus one re-run fit Command's six requests
MAX_BYTES = 200000


def total(checkpoints) -> int:
    return sum(len(diff.encode()) for point in checkpoints for diff in point['edits'])


async def paid(conn, tenant_id, turn_id) -> bool:
    if not turn_id:
        return False
    return await conn.fetchval("SELECT EXISTS(SELECT 1 FROM tank.ledger WHERE tenant_id=$1 AND task_id=$2 AND model<>'code')",
                               tenant_id, __import__('uuid').UUID(turn_id))


async def check(command, conn, row, state, actor, turn_id, body, work, timeline, fresh):
    if body.progress is None:
        return None
    track = work.setdefault('rollback', {'checkpoints': [], 'pending': None})
    current = body.progress.model_dump()
    edits = [item for item in fresh if item['kind'] == 'edit' and item['applied'] is True]
    checks = [item for item in fresh if item['kind'] == 'check']
    green = bool(checks) and all(item['passed'] for item in checks)
    args = (command, conn, row, state, actor, turn_id)
    pending = track['pending']
    if pending:
        if current['tree'] != pending['tree']:
            return await code_finish.free(
                *args, 'rollback_unconfirmed', 'The rollback to the last green checkpoint was not applied. Apply it, '
                'or use /undo locally, then continue. No model call was made.', {'expected_tree': pending['tree']})
        track['checkpoints'] = track['checkpoints'][:pending['target'] + 1]
        track['pending'] = None
        return None
    points = track['checkpoints']
    previous = points[-1] if points else None
    worse = previous is not None and (current['tests_passed'] < previous['tests_passed']
                                      or current['build_stage'] < previous['build_stage'])
    if worse and edits and await paid(conn, actor.tenant_id, work.get('last_turn')):
        target = max((number for number, point in enumerate(points) if point['green']), default=0)
        undo = [diff for point in points[target + 1:] for diff in point['edits']] + [edit['diff'] for edit in edits]
        whole = any(code_finish.diff_files(diff)[1] for diff in undo)
        if whole or len(undo) > MAX_UNDO:
            track['pending'] = None
            return await code_finish.free(
                *args, 'rollback_needs_undo', 'The last paid round left fewer tests passing or the build further back. '
                'The way back to the last green checkpoint is too large to send as diffs; use /undo locally, then '
                'continue. No model call was made.', {'checkpoint': points[target]['tree']})
        import code_diffs
        inverse = [code_diffs.invert(diff) for diff in reversed(undo)]
        requests = [code_finish.request('propose_edit', {'diff': diff}) for diff in inverse]
        rerun = next((item['command'] for item in reversed(timeline) if item['kind'] == 'check'), None)
        if rerun:
            requests.append(code_finish.request('run_command', {'command': rerun}))
        track['pending'] = {'target': target, 'tree': points[target]['tree']}
        work['tank_diffs'] = [*work['tank_diffs'], *(code_finish.sha(diff) for diff in inverse)][-16:]
        work.setdefault('notes', []).append(
            'The previous change left fewer tests passing or the build further back, so it was rolled back to the last '
            'checkpoint where the checks passed. Try a different approach.')
        return await code_finish.free(
            *args, 'rollback', 'The last paid round left fewer tests passing or the build further back. Rolling back '
            'to the last checkpoint where the checks passed. No model call was made.',
            {'checkpoint': points[target]['tree'], 'from': {k: current[k] for k in ('tests_passed', 'build_stage')},
             'to': {k: points[target][k] for k in ('tests_passed', 'build_stage')}}, requests=requests)
    points.append({**current, 'green': green, 'edits': [edit['diff'] for edit in edits]})
    while len(points) > MAX_CHECKPOINTS or (len(points) > 1 and total(points) > MAX_BYTES):
        points.pop(0)
        points[0]['edits'] = []  # The oldest kept checkpoint is the new floor.
    return None
