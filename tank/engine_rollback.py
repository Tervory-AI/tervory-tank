"""Roll a graduated engine rung back when its own live answers are rejected.

Off unless ENGINE_ROLLBACK_ENABLED is the literal ``true``. The decision reuses
graduate.rollback_if_dropped (same 5% rejection ceiling and 7-day watch); this
module only supplies the tenant's live evidence and records the move. A
recorded rollback is honoured on every later selection, so a rung that slipped
never silently returns; only a new proof revision can graduate again.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import graduate

SETTING = 'ENGINE_ROLLBACK_ENABLED'


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


async def blocked(rt, req, policy: dict, candidate: dict) -> bool:
    """True when this graduation was rolled back, now or earlier."""
    async with rt.pool().acquire() as conn:
        row = await conn.fetchrow('''SELECT previous_model,created_at,rolled_back_at FROM tank.engine_graduations
            WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND model=$4 AND revision=$5''',
            req.tenant_id, rt.box_region(), req.task_type, candidate['model'], candidate['revision'])
    if row is None:
        return False
    if row['rolled_back_at'] is not None:
        return True
    if not enabled():
        return False
    async with rt.pool().acquire() as conn:
        live = await conn.fetchrow('''SELECT count(*) FILTER(WHERE feedback='rejected') AS rejected,
                count(*) FILTER(WHERE feedback IS NOT NULL) AS judged
            FROM tank.ledger WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND model=$4
              AND outcome='delivered' AND ts>=$5''',
            req.tenant_id, rt.box_region(), req.task_type, candidate['model'], row['created_at'])
    watched = {'model': candidate['model'], 'previous_model': row['previous_model'], 'candidate_model': None,
               'promoted_at': row['created_at'],
               # No tenant can loosen the platform rejection ceiling.
               'max_reject_rate': min(graduate.DEFAULT_MAX_REJECT, float(policy.get('max_reject_rate') or graduate.DEFAULT_MAX_REJECT))}
    move = graduate.rollback_if_dropped(watched, graduate.Evidence(rejected=live['rejected'], judged=live['judged']),
                                        datetime.now(timezone.utc))
    if move.action != 'rollback':
        return False
    async with rt.pool().acquire() as conn:
        await conn.execute('''UPDATE tank.engine_graduations SET rolled_back_at=now(),rollback_reason=$6
            WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND model=$4 AND revision=$5 AND rolled_back_at IS NULL''',
            req.tenant_id, rt.box_region(), req.task_type, candidate['model'], candidate['revision'], move.reason)
    return True


async def step_back(rt, req, policy: dict, selected: dict) -> dict:
    """Serve the rung a graduation replaced when that graduation slipped."""
    async with rt.pool().acquire() as conn:
        row = await conn.fetchrow('''SELECT model,revision,previous_model FROM tank.engine_graduations
            WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND model=$4
            ORDER BY created_at DESC LIMIT 1''', req.tenant_id, rt.box_region(), req.task_type, selected['model'])
    if row is None or not await blocked(rt, req, policy, dict(row)):
        return selected
    import engine_ladder
    import engine_runtime
    info = selected['_engine']
    previous = row['previous_model']
    if previous not in info['ladder'] or not engine_runtime.available(previous):
        previous = info['baseline_model']
    return {**selected, 'model': previous,
            'rung': 3 if graduate.is_skill(previous) else 2 if previous in engine_ladder.LOCAL else 1,
            '_engine': {**info, 'free': previous in engine_ladder.LOCAL or graduate.is_skill(previous),
                        'rolled_back': row['model']}}
