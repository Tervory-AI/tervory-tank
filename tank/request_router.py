"""Per-request router: RouteLLM difficulty plus the scoreboard, across the whole ladder.

Off unless ENGINE_ROUTER_ENABLED is the literal ``true``. With it on, every
request the ladder routes gets a decision; the decision is shadow-only (the
ladder's own pick still serves) until BOTH of these hold for the task type:

  * the founder lists it in ENGINE_ROUTER_SERVE_TASK_TYPES (comma separated), and
  * tank.router_promotions says the router is proven there (see ``prove``).

The router never picks a model whose measured quality at this request's
difficulty (or, without difficulty evidence, on the whole task type) is below
the task type's bar: max(99%, policy.eval_threshold), the ladder's own bar.
It only ever moves to a strictly cheaper model than the ladder's pick, and keeps
the ladder's pick as the fallback when the cheaper model fails upstream.

An empty or stale board, an unpriced ladder pick, a free code/local rung or any
error keeps today's routing. ENGINE_ROUTER_LATENCY_ENABLED (literal ``true``)
adds LiteLLM health to the choice: cooled-down models (the mirror of LiteLLM's
five-minute cooldown), unhealthy error rates and models much slower than the
ladder's pick are skipped. Every model call still goes through Tank and LiteLLM.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import math
import os
import time
from typing import Any, Callable
import uuid

import graduate
import router_scoreboard as board_module
from router_scoreboard import ALL, Entry, bucket

log = logging.getLogger(__name__)
SETTING = board_module.SETTING
LATENCY_SETTING = 'ENGINE_ROUTER_LATENCY_ENABLED'
SERVE_SETTING = 'ENGINE_ROUTER_SERVE_TASK_TYPES'
LATENCY_SLACK = 1.5      # a cheaper model may be at most 50% slower at p95
MAX_ERROR_RATE = 0.05    # above this a model is unhealthy for latency-aware routing
SCORE_TIMEOUT_S = 0.5    # the same foreground bound as RouteLLM serving
MAX_SCORING = 4
PROMOTE_MIN_DECISIONS = 200
PROMOTE_MIN_COMPARED = 30
_scoring = 0
_tasks: set[asyncio.Task] = set()
_refreshing: set[tuple[str, str, str]] = set()


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


def latency_enabled() -> bool:
    return os.environ.get(LATENCY_SETTING) == 'true'


def serve_listed(task_type: str) -> bool:
    names = {name.strip() for name in os.environ.get(SERVE_SETTING, '').split(',') if name.strip()}
    return task_type in names


def quality_bar(policy: dict) -> float:
    return max(.99, float(policy.get('eval_threshold') or .99))


def _passes(entry: Entry | None, bar: float) -> bool:
    return entry is not None and entry.quality is not None and entry.quality >= bar


def choose(board: list[Entry], *, ladder_model: str, bar: float, difficulty: float | None,
           now: datetime, latency: bool = False,
           refused: Callable[[str], bool] = lambda model: False) -> tuple[str | None, str]:
    """A pure lookup. Returns (model, reason); model None means keep today's routing."""
    if not board:
        return None, 'empty_board'
    whole = {e.model: e for e in board if e.difficulty == ALL and e.fresh(now)}
    if not whole:
        return None, 'stale_board'
    current = whole.get(ladder_model)
    if current is None or current.price_usd is None:
        return None, 'ladder_pick_unpriced'
    level = bucket(difficulty)
    at_level = {e.model: e for e in board if level is not None and e.difficulty == level and e.fresh(now)}

    def passing(model: str) -> bool:
        measured = at_level.get(model)
        if measured is not None and measured.quality is not None:
            return measured.quality >= bar  # difficulty evidence decides when it exists
        return _passes(whole.get(model), bar)

    eligible = []
    for model, entry in whole.items():
        if model == ladder_model or not entry.available or entry.price_usd is None:
            continue
        if entry.price_usd >= current.price_usd:
            continue
        if graduate.is_skill(model) or graduate.router_cannot_serve(model) or model.lower().startswith('build-'):
            continue
        if not passing(model):
            continue
        if latency:
            if entry.cooling(now):
                continue
            if entry.error_rate is None or entry.error_rate > MAX_ERROR_RATE:
                continue
            if entry.p95_ms is None or (current.p95_ms is not None and entry.p95_ms > current.p95_ms * LATENCY_SLACK):
                continue
        if refused(model):
            continue
        eligible.append(entry)
    if not eligible:
        return ladder_model, 'ladder_pick_cheapest_passing'
    best = min(eligible, key=lambda e: (e.price_usd, e.p95_ms if latency and e.p95_ms is not None else 0, e.model))
    return best.model, 'cheaper_model_passes' + ('_at_difficulty' if best.model in at_level else '')


def _prompt(req) -> str:
    return next((m.content for m in reversed(req.messages) if m.role == 'user'), '')


async def difficulty(req) -> float | None:
    """RouteLLM's strong-win-rate for the last user prompt, on CPU, bounded; None when unavailable."""
    global _scoring
    if _scoring >= MAX_SCORING:
        return None
    import routellm_shadow
    _scoring += 1
    task = asyncio.create_task(asyncio.to_thread(routellm_shadow.score, _prompt(req)))

    def completed(work):
        global _scoring
        _scoring -= 1
        if not work.cancelled():
            work.exception()  # consume; never log prompt text

    task.add_done_callback(completed)
    try:
        value = float(await asyncio.wait_for(asyncio.shield(task), SCORE_TIMEOUT_S))
    except Exception as exc:
        log.info('Router difficulty unavailable (%s)', type(exc).__name__)
        return None
    return value if math.isfinite(value) and 0 <= value <= 1 else None


async def promoted(pool, tenant_id: uuid.UUID, region: str, task_type: str) -> bool:
    from tenant_db import tenant_scope
    with tenant_scope(tenant_id):
        async with pool.acquire() as conn:
            return bool(await conn.fetchval('''SELECT proven FROM tank.router_promotions
                WHERE tenant_id=$1 AND region=$2 AND task_type=$3''', tenant_id, region, task_type))


async def prove(pool, tenant_id: uuid.UUID, region: str, task_type: str, bar: float) -> dict:
    """Proven = enough decisions, and the router's cheaper picks measured on the same requests at the bar.

    The measurement is the existing shadow/engine-proof comparison of that model on
    that ledger row; no extra model call is made to prove the router.
    """
    from tenant_db import tenant_scope
    window = timedelta(days=board_module.WINDOW_DAYS)
    with tenant_scope(tenant_id):
        async with pool.acquire() as conn, conn.transaction():
            row = await conn.fetchrow('''WITH d AS (
                    SELECT ledger_id,chosen_model FROM tank.router_decisions
                    WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND mode IN ('shadow','served')
                      AND created_at>now()-$4::interval),
                m AS (
                    SELECT d.ledger_id,s.agreement FROM d JOIN tank.shadow s ON s.tenant_id=$1 AND s.ledger_id=d.ledger_id
                      AND (s.candidate_model=d.chosen_model
                           OR (s.candidate_model LIKE 'routellm:%' AND split_part(s.candidate_model,':',2)=d.chosen_model))
                    WHERE s.agreement IS NOT NULL
                    UNION ALL
                    SELECT d.ledger_id,p.agreement FROM d JOIN tank.engine_proofs p ON p.tenant_id=$1 AND p.region=$2
                      AND p.task_type=$3 AND p.ledger_id=d.ledger_id AND p.model=d.chosen_model)
                SELECT (SELECT count(*) FROM d) AS decisions,count(*) AS compared,avg(agreement) AS agreement FROM m''',
                tenant_id, region, task_type, window)
            decisions, compared = int(row['decisions']), int(row['compared'])
            agreement = float(row['agreement']) if row['agreement'] is not None else None
            prior = bool(await conn.fetchval('''SELECT proven FROM tank.router_promotions
                WHERE tenant_id=$1 AND region=$2 AND task_type=$3''', tenant_id, region, task_type))
            if decisions >= PROMOTE_MIN_DECISIONS and compared >= PROMOTE_MIN_COMPARED:
                proven = agreement is not None and agreement >= bar
            else:
                # Thin new evidence keeps a standing promotion; any measured shortfall ends it.
                proven = prior and (agreement is None or agreement >= bar)
            await conn.execute('''INSERT INTO tank.router_promotions(tenant_id,region,task_type,proven,decisions,compared,agreement,checked_at)
                VALUES($1,$2,$3,$4,$5,$6,$7,now()) ON CONFLICT(tenant_id,region,task_type) DO UPDATE SET
                proven=excluded.proven,decisions=excluded.decisions,compared=excluded.compared,
                agreement=excluded.agreement,checked_at=now()''',
                tenant_id, region, task_type, proven, decisions, compared, agreement)
    return {'proven': proven, 'decisions': decisions, 'compared': compared, 'agreement': agreement}


async def _refresh(rt, tenant_id: uuid.UUID, region: str, task_type: str, bar: float) -> None:
    key = (str(tenant_id), region, task_type)
    try:
        roster = {row['model_name'] for row in await rt._roster_models()}
        await board_module.refresh(rt.pool(), tenant_id, region, task_type,
                                   roster=roster, platform_tenant=rt.PLATFORM_TENANT)
        await prove(rt.pool(), tenant_id, region, task_type, bar)
    except Exception as exc:
        log.warning('Router scoreboard refresh failed (%s)', type(exc).__name__)
    finally:
        _refreshing.discard(key)


def schedule_refresh(rt, tenant_id: uuid.UUID, region: str, task_type: str, bar: float) -> None:
    """Off the request path: a decision never waits for evidence to be recomputed."""
    key = (str(tenant_id), region, task_type)
    if key in _refreshing:
        return
    _refreshing.add(key)
    task = asyncio.create_task(_refresh(rt, tenant_id, region, task_type, bar))
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    while _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)


async def route(rt, req, policy: dict, caller: str | None = None) -> dict:
    """Return the policy to serve, carrying the decision as ``_router`` for the receipt."""
    started = time.perf_counter()
    ladder_model = str(policy.get('model') or '')
    info = policy.get('_engine') or {}
    bar = quality_bar(policy)
    region = rt.box_region()
    decision: dict[str, Any] = {'version': 1, 'mode': 'shadow', 'ladder_model': ladder_model,
                                'chosen_model': None, 'reason': 'not_routed', 'difficulty': None,
                                'bucket': None, 'quality_bar': bar, 'latency_aware': latency_enabled()}
    chosen: str | None = None
    try:
        if info.get('free') or graduate.is_skill(ladder_model):
            decision['reason'] = 'ladder_pick_free_or_code'
        else:
            entries = await board_module.read(rt.pool(), req.tenant_id, region, req.task_type)
            now = datetime.now(timezone.utc)
            newest = max((e.refreshed_at for e in entries), default=None)
            if newest is None or now - newest > timedelta(seconds=board_module.REFRESH_AFTER_S):
                schedule_refresh(rt, req.tenant_id, region, req.task_type, bar)
            score = await difficulty(req) if entries else None
            decision['difficulty'] = score
            decision['bucket'] = bucket(score)
            text = '\n'.join(m.content for m in req.messages)
            # Tank's own privacy and region refusal for each cheaper candidate, as _run_route applies it.
            pool_read = await rt.zenas_pool_prompt(text, caller=caller, task_type=req.task_type,
                                                   skill=req.skill) if entries else False

            def refused(model: str) -> bool:
                return bool(rt.model_call_refusal(text, model, box=region, tenant_id=str(req.tenant_id),
                                                  task_type=req.task_type, caller=caller, skill=req.skill,
                                                  pool_read=pool_read))

            chosen, decision['reason'] = choose(entries, ladder_model=ladder_model, bar=bar, difficulty=score,
                                                now=now, latency=latency_enabled(), refused=refused)
            decision['chosen_model'] = chosen
            if chosen and chosen != ladder_model and serve_listed(req.task_type) and await promoted(
                    rt.pool(), req.tenant_id, region, req.task_type):
                decision['mode'] = 'served'
    except Exception as exc:
        chosen = None
        decision.update({'mode': 'fallback', 'chosen_model': None, 'reason': 'router_unavailable:' + type(exc).__name__})
    if chosen is None and decision['mode'] != 'fallback':
        decision['mode'] = 'fallback'
    decision['decision_ms'] = round((time.perf_counter() - started) * 1000, 3)
    if decision['mode'] != 'served':
        return {**policy, '_router': decision}
    import engine_runtime
    served = {**policy, 'model': chosen, 'rung': 2 if chosen in engine_runtime.LOCAL else 1,
              # The ladder's pick stays behind the cheaper model: an upstream failure falls back to it.
              'fallbacks': [ladder_model], '_router': decision}
    if info:
        served['_engine'] = {**info, 'free': chosen in engine_runtime.LOCAL, 'router_from': ladder_model}
    return served


async def receipt(rt, req, policy: dict, answer):
    """Record the decision and show it, with its decision time, on the receipt."""
    decision = policy.get('_router')
    if not decision or not isinstance(answer, rt.RouteResponse):
        return answer
    shown = {**decision, 'served_model': answer.model}
    from tenant_db import tenant_scope
    try:
        with tenant_scope(req.tenant_id):
            async with rt.pool().acquire() as conn:
                await conn.execute('''INSERT INTO tank.router_decisions
                    (tenant_id,region,task_type,ledger_id,mode,ladder_model,chosen_model,served_model,
                     difficulty,bucket,decision_ms,reason)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12) ON CONFLICT(tenant_id,ledger_id) DO NOTHING''',
                    req.tenant_id, rt.box_region(), req.task_type, answer.ledger_id, decision['mode'],
                    decision['ladder_model'], decision['chosen_model'], answer.model, decision['difficulty'],
                    decision['bucket'], decision['decision_ms'], decision['reason'])
    except Exception as exc:
        # The answer is already delivered and charged; a missing log row never fails it.
        log.warning('Router decision not recorded (%s)', type(exc).__name__)
        shown['recorded'] = False
    return answer.model_copy(update={'engine': {**(answer.engine or {}), 'router': shown}})


async def decision_times(pool, tenant_id: uuid.UUID, region: str, task_type: str) -> dict:
    from tenant_db import tenant_scope
    with tenant_scope(tenant_id):
        async with pool.acquire() as conn:
            row = await conn.fetchrow('''SELECT count(*) AS n,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY decision_ms) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY decision_ms) AS p95
                FROM tank.router_decisions WHERE tenant_id=$1 AND region=$2 AND task_type=$3''',
                tenant_id, region, task_type)
    return {'n': int(row['n']), 'p50_ms': row['p50'], 'p95_ms': row['p95']}
