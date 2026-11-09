"""Learning-loop numbers for the founder's engine status, from rows that exist today.

Off unless ENGINE_STATUS_NUMBERS_ENABLED is the literal ``true``; then each task
row gains one ``learning`` object. Every query is scoped to one tenant and this
box's region. Nothing here calls a model or estimates beyond the receipts.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import engine_coverage

SETTING = 'ENGINE_STATUS_NUMBERS_ENABLED'
LAYERS = ('C1', 'C2', 'C3', 'C4', 'C5', 'C6')
TARGET_AGREEMENT = .99
TARGET_SAMPLES = 200


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


def _by_task(rows) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in rows:
        out.setdefault(row['task_type'], []).append(dict(row))
    return out


async def collect(rt, tenant_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    region = rt.box_region()
    async with rt.pool().acquire() as conn:
        policies = await conn.fetch('''SELECT DISTINCT ON (task_type) task_type,model FROM tank.policy
            WHERE tenant_id=$1 OR tenant_id IS NULL ORDER BY task_type, tenant_id NULLS LAST''', tenant_id)
        states = await conn.fetch('''SELECT task_type,model FROM tank.engine_state
            WHERE tenant_id=$1 AND region=$2''', tenant_id, region)
        # C2 is tenant memory recalled into the request; C3 is the semantic
        # answer cache (Tank's own label C2 on a semantic route-cache match,
        # or the cache:semantic candidate). Other layers are read as recorded.
        layers = await conn.fetch('''SELECT r.task_type,
            count(*) FILTER(WHERE coalesce((r.detail->'cache_layers'->'C1'->>'hits')::integer,0)>0
                               OR r.detail->>'cache_layer'='C1') AS "C1",
            count(*) FILTER(WHERE coalesce((r.detail->>'memory_hits')::integer,0)>0) AS "C2",
            count(*) FILTER(WHERE r.detail->>'cache_layer'='C2' OR l.model='cache:semantic') AS "C3",
            count(*) FILTER(WHERE coalesce((r.detail->'cache_layers'->'C4'->>'hits')::integer,0)>0) AS "C4",
            count(*) FILTER(WHERE coalesce((r.detail->'cache_layers'->'C5'->>'hits')::integer,0)>0) AS "C5",
            count(*) FILTER(WHERE coalesce((r.detail->'cache_layers'->'C6'->>'hits')::integer,0)>0) AS "C6",
            count(*) FILTER(WHERE l.cache_hit AND r.detail->>'cache_layer' IS NULL
                               AND l.model<>'cache:semantic') AS unlabelled
            FROM tank.engine_receipts r JOIN tank.ledger l ON l.id=r.ledger_id AND l.tenant_id=r.tenant_id
            WHERE r.tenant_id=$1 AND r.region=$2 GROUP BY r.task_type''', tenant_id, region)
        live = await conn.fetch('''SELECT s.task_type,s.candidate_model AS model,count(*) AS samples,
                avg(s.agreement) AS agreement
            FROM tank.shadow s JOIN tank.ledger l ON l.id=s.ledger_id AND l.tenant_id=s.tenant_id
            WHERE s.tenant_id=$1 AND l.region=$2 GROUP BY s.task_type,s.candidate_model''', tenant_id, region)
        replayed = await conn.fetch('''SELECT task_type,model,revision,count(*) AS samples,avg(agreement) AS agreement
            FROM tank.engine_proofs WHERE tenant_id=$1 AND region=$2
            GROUP BY task_type,model,revision''', tenant_id, region)
        moves = await conn.fetch('''SELECT task_type,count(*) AS graduations,
                count(*) FILTER(WHERE rolled_back_at IS NOT NULL) AS rollbacks
            FROM tank.engine_graduations WHERE tenant_id=$1 AND region=$2 GROUP BY task_type''', tenant_id, region)
    roster = {r['name']: r for r in await rt.list_models()}

    def rung(model):
        name = engine_coverage.rung_of(model)
        # A zero-price model outside the public ladder is a served trained checkpoint.
        if name == 'frontier' and engine_coverage.free(roster, model):
            return 'local trained'
        return name or ('unselected' if model is None else 'unsupported')
    policy = {r['task_type']: r['model'] for r in policies}
    state = {r['task_type']: r['model'] for r in states}
    layer = {r['task_type']: dict(r) for r in layers}
    shadows, proofs = _by_task(live), _by_task(replayed)
    move = {r['task_type']: dict(r) for r in moves}
    names = set(policy) | set(state) | set(layer) | set(shadows) | set(proofs) | set(move)
    result = {}
    for name in names:
        serving = state.get(name) or policy.get(name)
        best = max(proofs.get(name, []), key=lambda r: (r['samples'], r['agreement'] or 0), default=None)
        result[name] = {
            'serving_model': serving,
            'serving_rung': rung(serving),
            'rung_source': 'engine' if name in state else 'policy' if name in policy else 'none',
            'cache_hits_by_layer': {k: int(layer.get(name, {}).get(k) or 0) for k in LAYERS},
            'cache_hits_unlabelled': int(layer.get(name, {}).get('unlabelled') or 0),
            'shadows_run': {'live': sum(int(r['samples']) for r in shadows.get(name, [])),
                            'replayed': sum(int(r['samples']) for r in proofs.get(name, []))},
            'live_shadow_agreement': [{'candidate': r['model'], 'samples': int(r['samples']),
                                       'agreement': float(r['agreement']) if r['agreement'] is not None else None}
                                      for r in shadows.get(name, [])],
            'proof': None if best is None else {
                'candidate': best['model'], 'samples': int(best['samples']),
                'agreement': float(best['agreement']) if best['agreement'] is not None else None,
                'target_agreement': TARGET_AGREEMENT, 'target_samples': TARGET_SAMPLES,
                'samples_progress': min(1., int(best['samples']) / TARGET_SAMPLES)},
            'graduations': int(move.get(name, {}).get('graduations') or 0),
            'rollbacks': int(move.get(name, {}).get('rollbacks') or 0),
        }
    return result


def attach(row: dict[str, Any], numbers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    learning = dict(numbers.get(row['task_type']) or {})
    learning['savings'] = {'cost_usd': row['cost_usd'], 'would_have_cost_usd': row['would_have_cost_usd'],
                           'saved_usd': row['saved_usd'], 'estimated': True}
    return {**row, 'learning': learning}
