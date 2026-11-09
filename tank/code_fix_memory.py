"""Gate before (finish): error-to-fix memory, per tenant (ENGINE_CODE_FIX_MEMORY_ENABLED).

When a check that failed with an error signature later passes after edits the
model proposed, the pair is stored for the tenant: signature, the check command,
the fix as diffs and the files. The next time the same error is reported, Tank
answers at $0 with the remembered fix and a re-run of the check, before any paid
call. If the remembered fix applies but the error stays, Tank rolls it back at $0
and marks the entry bad, and the next round goes to the paid path.

Storage is tank.code_fix_memory, keyed by tenant (row-level security joins the
existing tenant rollout), queried only with the authenticated tenant.
"""
from __future__ import annotations

import code_finish

MAX_DIFFS = 3
MAX_FILES = 2  # reads + edits + one re-run fit Command's six requests per answer
MAX_BYTES = 20000
MAX_ENTRIES = 500
MAX_MISSES = 2


def fix_before(timeline: list[dict], check: dict) -> list[dict] | None:
    """The edits that turned the latest earlier failure of this command into this pass."""
    edits = []
    for item in reversed([entry for entry in timeline if entry['index'] < check['index']]):
        if item['kind'] == 'check' and item['command'] == check['command']:
            if item['passed']:
                return None
            return [*reversed(edits)], item
        if item['kind'] == 'edit':
            if item['applied'] is not True:
                return None
            edits.append(item)
    return None


async def learn(command, conn, row, state, actor, turn_id, body, work, timeline, fresh):
    tank_diffs = set(work['tank_diffs'])
    for check in fresh:
        if check['kind'] != 'check' or not check['passed']:
            continue
        found = fix_before(timeline, check)
        if not found:
            continue
        edits, failure = found
        if not edits or len(edits) > MAX_DIFFS or any(edit['whole'] or code_finish.sha(edit['diff']) in tank_diffs for edit in edits):
            continue
        diffs = [edit['diff'] for edit in edits]
        files = list(dict.fromkeys(path for edit in edits for path in edit['files']))
        if len(files) > MAX_FILES or sum(len(diff.encode()) for diff in diffs) > MAX_BYTES:
            continue
        await conn.execute(
            "INSERT INTO tank.code_fix_memory(tenant_id,signature,command,diffs,files,created_by) "
            "VALUES($1,$2,$3,$4,$5,$6) ON CONFLICT(tenant_id,signature) DO UPDATE SET command=EXCLUDED.command,"
            "diffs=EXCLUDED.diffs,files=EXCLUDED.files,status='good',bad_reason=NULL,misses=0,updated_at=now()",
            actor.tenant_id, failure['signature'], failure['command'], diffs, files, actor.user_id)
        await conn.execute(
            "DELETE FROM tank.code_fix_memory WHERE tenant_id=$1 AND signature IN (SELECT signature FROM tank.code_fix_memory "
            "WHERE tenant_id=$1 ORDER BY updated_at DESC OFFSET $2)", actor.tenant_id, MAX_ENTRIES)


async def serve(command, conn, row, state, actor, turn_id, body, work, timeline, fresh):
    memory = work.setdefault('memory', {'served': None, 'tried': []})
    latest = next((item for item in reversed(timeline) if item['kind'] in ('check', 'edit')), None)
    if latest is None or latest['kind'] != 'check' or latest['passed'] or latest not in fresh:
        return None
    if latest['signature'] in memory['tried']:
        return None
    entry = await conn.fetchrow(
        "SELECT signature,command,diffs,files FROM tank.code_fix_memory "
        "WHERE tenant_id=$1 AND signature=$2 AND status='good'", actor.tenant_id, latest['signature'])
    if entry is None:
        return None
    allowed = code_finish.planned_files(state, body)
    if allowed is not None and not set(entry['files']) <= allowed:
        return None  # The scope lock wins; the paid path handles this task.
    memory['tried'].append(latest['signature'])
    requests = ([code_finish.request('read_file', {'path': path}) for path in entry['files']]
                + [code_finish.request('propose_edit', {'diff': diff}) for diff in entry['diffs']]
                + [code_finish.request('run_command', {'command': latest['command']})])
    memory['served'] = {'signature': entry['signature'], 'command': latest['command'], 'diffs': list(entry['diffs'])}
    work['tank_diffs'] = [*work['tank_diffs'], *(code_finish.sha(diff) for diff in entry['diffs'])][-16:]
    return await code_finish.free(
        command, conn, row, state, actor, turn_id, 'fix_memory',
        'This error was fixed before in this workspace. Applying the remembered fix and re-running the check. '
        'No model call was made.', {'files': list(entry['files'])}, requests=requests)


async def verify(command, conn, row, state, actor, turn_id, body, work, timeline, fresh):
    memory = work.get('memory')
    served = memory.get('served') if isinstance(memory, dict) else None
    if not served:
        return None
    memory['served'] = None
    edits = [item for item in fresh if item['kind'] == 'edit' and item['diff'] in served['diffs']]
    if len(edits) != len(served['diffs']):
        return None  # Not reported back (declined or a new window); nothing is concluded.
    if any(edit['applied'] == 'error' for edit in edits):
        await conn.execute(
            "UPDATE tank.code_fix_memory SET misses=misses+1,status=CASE WHEN misses+1>=$3 THEN 'bad' ELSE status END,"
            "bad_reason=CASE WHEN misses+1>=$3 THEN 'did_not_apply' ELSE bad_reason END,updated_at=now() "
            "WHERE tenant_id=$1 AND signature=$2", actor.tenant_id, served['signature'], MAX_MISSES)
        return None
    if any(edit['applied'] is not True for edit in edits):
        return None
    last = edits[-1]['index']
    rerun = next((item for item in fresh if item['kind'] == 'check' and item['index'] > last
                  and item['command'] == served['command']), None)
    if rerun is None:
        return None
    if rerun['passed'] or rerun['signature'] != served['signature']:
        await conn.execute("UPDATE tank.code_fix_memory SET hits=hits+1,misses=0,updated_at=now() "
                           "WHERE tenant_id=$1 AND signature=$2", actor.tenant_id, served['signature'])
        if not rerun['passed']:
            return None  # This error is gone; a different one goes on to memory or the paid path.
        return await code_finish.free(
            command, conn, row, state, actor, turn_id, 'fix_memory_done',
            'The remembered fix was applied and the check passes now. No model call was made. '
            'Send a follow-up if there is more to do.', {'check': 'passed'})
    # Applied but the error stayed: the entry is wrong. Undo it at $0, then pay to fix properly.
    await conn.execute("UPDATE tank.code_fix_memory SET status='bad',bad_reason='did_not_fix',updated_at=now() "
                       "WHERE tenant_id=$1 AND signature=$2", actor.tenant_id, served['signature'])
    import code_diffs
    inverse = [code_diffs.invert(diff) for diff in reversed(served['diffs'])]
    work['tank_diffs'] = [*work['tank_diffs'], *(code_finish.sha(diff) for diff in inverse)][-16:]
    work.setdefault('notes', []).append('A remembered fix did not clear this error and was rolled back.')
    return await code_finish.free(
        command, conn, row, state, actor, turn_id, 'fix_memory_rollback',
        'The remembered fix did not clear the error. Rolling it back; the next round works on the error itself. '
        'No model call was made.', {'check': 'failed'},
        requests=[code_finish.request('propose_edit', {'diff': diff}) for diff in inverse])
