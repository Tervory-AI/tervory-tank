"""Shadow coverage: every task type shadows the next cheaper available rung.

Off unless ENGINE_SHADOW_COVERAGE_ENABLED is the literal ``true``. The candidate
is computed per request from the live roster and never written to tank.policy,
so switching the setting off restores the stored policy exactly. There is no
default model: when no cheaper rung is on the roster the task has no candidate.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import engine_ladder
import engine_models
import engine_runtime
import graduate

SETTING = 'ENGINE_SHADOW_COVERAGE_ENABLED'
# Highest cost first. A candidate is always on a strictly cheaper rung.
RUNGS = ('frontier', 'open-weight', 'local large', 'local small', 'local trained', 'code')
# A paid shadow samples this share of calls when the policy names no rate;
# the existing daily shadow budget still caps its spend.
PAID_RATE = 0.1
PRICES = ('input_usd_per_m', 'output_usd_per_m')


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


def rung_of(model: str | None) -> str | None:
    if not model:
        return None
    if str(model).startswith('tervor-'):
        return 'local trained'
    if str(model).startswith(('routellm:', 'cache:', 'tool:')):
        return None
    return engine_ladder.rung(model)


def free(roster: dict[str, dict], model: str) -> bool:
    if graduate.is_skill(model) or model in engine_models.LOCAL:
        return True
    row = roster.get(model, {})
    return all(row.get(key) == 0 for key in PRICES)


async def _skills(rt, tenant_id: uuid.UUID, task_type: str) -> list[str]:
    async with rt.pool().acquire() as conn:
        rows = await conn.fetch('''SELECT s.id,s.version FROM tank.skills s
            LEFT JOIN tank.agent_skill_submissions a ON a.skill_id=s.id AND a.version=s.version
            WHERE s.task_type=$1 AND s.state='approved'
              AND (a.tenant_id IS NULL OR (a.tenant_id=$2 AND a.region=$3))
            ORDER BY s.id,s.version DESC''', task_type, tenant_id, rt.box_region())
    return [f"skill:{row['id']}@{row['version']}" for row in rows]


async def _trained(rt, tenant_id: uuid.UUID, task_type: str) -> list[str]:
    async with rt.pool().acquire() as conn:
        rows = await conn.fetch('''SELECT model,checkpoint FROM tank.engine_candidates
            WHERE tenant_id=$1 AND region=$2 AND task_type=$3 ORDER BY created_at DESC''',
            tenant_id, rt.box_region(), task_type)
    import tervor_serving
    rows = await tervor_serving.pinned_candidates(rt, [dict(r) for r in rows])
    return [row['model'] for row in rows if str(row['model']).startswith('tervor-')]


async def choose(rt, tenant_id: uuid.UUID, task_type: str, model: str | None,
                 roster: dict[str, dict] | None = None) -> dict[str, Any]:
    """The next cheaper available rung for one task type, from the roster only."""
    roster = roster if roster is not None else {r['name']: r for r in await rt.list_models()}
    current = rung_of(model)
    row: dict[str, Any] = {'task_type': task_type, 'model': model, 'rung': current or 'unsupported',
                           'candidate': None, 'candidate_rung': None, 'metered': None, 'reason': None}
    if current is None:
        row['reason'] = 'this policy kind has no cheaper model rung'
        return row
    if current == 'code':
        row['reason'] = 'already on the cheapest rung'
        return row

    def served(name: str) -> bool:
        return (name in roster and name != model and engine_runtime.available(name)
                and not rt.is_build_only_model(name))

    def cheaper(name: str) -> bool:
        a, b = roster.get(name, {}), roster.get(model, {})
        return all(isinstance(a.get(k), (int, float)) and isinstance(b.get(k), (int, float)) and a[k] <= b[k]
                   for k in PRICES)

    pools = {
        'open-weight': [n for n in engine_models.OPEN if served(n) and cheaper(n)],
        'local large': [n for n in ('local-large',) if served(n)],
        'local small': [n for n in ('local',) if served(n)],
        'local trained': [n for n in await _trained(rt, tenant_id, task_type) if served(n) and cheaper(n)],
        'code': [n for n in await _skills(rt, tenant_id, task_type) if n != model],
    }
    for rung in RUNGS[RUNGS.index(current) + 1:]:
        if pools[rung]:
            name = pools[rung][0]
            row.update(candidate=name, candidate_rung=rung, metered=not free(roster, name))
            return row
    row['reason'] = 'no cheaper rung is available on the roster'
    return row


async def overlay(rt, req, policy: dict[str, Any]) -> dict[str, Any]:
    """Add this request's coverage candidate; a configured candidate always wins."""
    if not enabled() or policy.get('candidate_model') or graduate.router_cannot_serve(policy.get('model')):
        return policy
    choice = await choose(rt, req.tenant_id, req.task_type, policy.get('model'))
    name = choice['candidate']
    if not name:
        return policy
    if choice['metered']:
        rate = float(policy.get('shadow_rate') or 0) or PAID_RATE
    else:
        rate = 1.0  # Local and code shadows cost no provider spend and are not budgeted.
    stored = {'candidate_model': policy.get('candidate_model'), 'shadow_rate': policy.get('shadow_rate')}
    return {**policy, 'candidate_model': name, 'shadow_rate': rate, '_coverage': {**choice, 'stored': stored}}


async def unmetered(rt, candidate: str | None) -> bool:
    """Exempt only zero-price local/trained candidates from the paid budget, when on."""
    if not enabled() or not candidate or graduate.is_skill(candidate):
        return False
    if candidate in engine_models.LOCAL:
        return True
    roster = {r['name']: r for r in await rt.list_models()}
    return str(candidate).startswith('tervor-') and free(roster, candidate)


async def listing(rt, tenant_id: uuid.UUID) -> dict[str, Any]:
    """Every task type this tenant can route, with its serving rung and candidate."""
    async with rt.pool().acquire() as conn:
        rows = await conn.fetch('''SELECT DISTINCT ON (p.task_type) p.task_type,p.model,p.candidate_model,
                s.model AS engine_model
            FROM tank.policy p LEFT JOIN tank.engine_state s
              ON s.tenant_id=$1 AND s.region=$2 AND s.task_type=p.task_type
            WHERE p.tenant_id=$1 OR p.tenant_id IS NULL
            ORDER BY p.task_type, p.tenant_id NULLS LAST''', tenant_id, rt.box_region())
    roster = {r['name']: r for r in await rt.list_models()}
    tasks = []
    for row in rows:
        model = row['engine_model'] or row['model']
        if row['candidate_model']:
            item = {'task_type': row['task_type'], 'model': model, 'rung': rung_of(model) or 'unsupported',
                    'candidate': row['candidate_model'], 'candidate_rung': rung_of(row['candidate_model']),
                    'metered': not free(roster, row['candidate_model']), 'reason': 'configured in policy'}
        else:
            item = await choose(rt, tenant_id, row['task_type'], model, roster)
        item['source'] = 'engine' if row['engine_model'] else 'policy'
        tasks.append(item)
    return {'tenant_id': str(tenant_id), 'region': rt.box_region(), 'tasks': tasks}
