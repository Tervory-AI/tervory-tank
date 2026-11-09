"""Per-request router scoreboard: evidence kept current so a routing decision is a lookup.

One row per tenant, region, task type, model and difficulty bucket. Bucket -1 is
the whole task type; buckets 0..4 split RouteLLM's strong-win-rate (difficulty)
into fifths. Every figure comes from evidence Tank already records:

  quality       gold (tank.engine_evals), nightly bench (tank.bench_runs via bench.py),
                shadow agreement (tank.shadow, tank.engine_proofs) and DeepEval scores
                (the quality JSON those shadow rows carry);
  latency/errors p50/p95 latency and error rate from the tenant's own receipts (tank.ledger);
  price         average charged cost per request from receipts, else the platform bench;
  availability  on LiteLLM's live roster, plus a mirror of LiteLLM's cooldown
                (router_settings: allowed_fails 1, cooldown_time 300): a model whose
                last receipt for this tenant failed within five minutes is cooling down.

Nothing here calls a model or a provider. Off unless ENGINE_ROUTER_ENABLED is the
literal ``true``: with the setting unset the bench never writes here and the router
never reads here. Reads and writes are always scoped by tenant_id.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import math
import os
from typing import Any, Iterable
import uuid

SETTING = 'ENGINE_ROUTER_ENABLED'
ALL = -1
BUCKETS = 5
# Ladder parity: whole-task gold needs one accepted case, as engine_ladder does.
# Per-difficulty and shadow evidence needs a real sample before it can pass.
MIN_SAMPLES = 20
WINDOW_DAYS = 14
REFRESH_AFTER_S = 600
STALE_AFTER_S = 26 * 3600  # one nightly bench plus slack
COOLDOWN_S = 300  # litellm/config.yaml router_settings.cooldown_time
MAX_EVIDENCE_ROWS = 20000


def enabled() -> bool:
    return os.environ.get(SETTING) == 'true'


def bucket(difficulty: float | None) -> int | None:
    if difficulty is None:
        return None
    try:
        value = float(difficulty)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or not 0 <= value <= 1:
        return None
    return min(BUCKETS - 1, int(value * BUCKETS))


@dataclass(frozen=True)
class Entry:
    model: str
    difficulty: int
    quality: float | None
    quality_n: int
    p50_ms: int | None
    p95_ms: int | None
    error_rate: float | None
    price_usd: float | None
    available: bool
    cooldown_until: datetime | None
    refreshed_at: datetime

    def cooling(self, now: datetime) -> bool:
        return self.cooldown_until is not None and self.cooldown_until > now

    def fresh(self, now: datetime) -> bool:
        return now - self.refreshed_at <= timedelta(seconds=STALE_AFTER_S)


def _finite(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _money(value: Any) -> Decimal | None:
    # Prices keep their receipt precision; a float round trip would add binary noise.
    if _finite(value) is None:
        return None
    return value if isinstance(value, Decimal) else Decimal(str(value))


def compose(gold: tuple[float | None, int], bench: tuple[float | None, int],
            shadow: tuple[float | None, int], deepeval: tuple[float | None, int],
            *, whole_task: bool) -> tuple[float | None, int]:
    """The weakest qualifying signal is the row's quality; no averaging can hide a failure."""
    floor = 1 if whole_task else MIN_SAMPLES
    signals = [(gold, floor), (bench, floor), (shadow, MIN_SAMPLES), (deepeval, MIN_SAMPLES)]
    used = [(_finite(value), n) for (value, n), minimum in signals
            if _finite(value) is not None and int(n or 0) >= minimum]
    if not used:
        return None, 0
    return min(value for value, _ in used), sum(int(n) for _, n in used)


def _deepeval(quality: Any) -> float | None:
    if isinstance(quality, str):
        try:
            quality = json.loads(quality)
        except ValueError:
            return None
    scores = quality.get('scores') if isinstance(quality, dict) else None
    if not isinstance(scores, dict):
        return None
    values = [_finite(scores.get(key)) for key in ('correctness', 'faithfulness', 'task')]
    values = [v for v in values if v is not None and 0 <= v <= 1]
    return min(values) if values else None


def _model_name(candidate: str) -> str:
    # RouteLLM shadow candidates are routellm:<weak>:<fingerprint>; score the weak model.
    if candidate.startswith('routellm:'):
        parts = candidate.split(':')
        return parts[1] if len(parts) >= 3 else candidate
    return candidate


def aggregate(samples: Iterable[tuple[str, float | None, float | None, float | None]]) -> dict:
    """(model, difficulty, agreement, deepeval) → {(model, bucket): sums} for -1 and its bucket."""
    out: dict[tuple[str, int], dict] = {}
    for model, difficulty, agreement, deepeval in samples:
        keys = [ALL]
        b = bucket(difficulty)
        if b is not None:
            keys.append(b)
        for key in keys:
            slot = out.setdefault((model, key), {'agree': 0.0, 'agree_n': 0, 'deep': 0.0, 'deep_n': 0})
            a, d = _finite(agreement), _finite(deepeval)
            if a is not None:
                slot['agree'] += a
                slot['agree_n'] += 1
            if d is not None:
                slot['deep'] += d
                slot['deep_n'] += 1
    return out


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def read(pool, tenant_id: uuid.UUID, region: str, task_type: str) -> list[Entry]:
    """The router's only read: this tenant's rows for this region and task type."""
    from tenant_db import tenant_scope
    with tenant_scope(tenant_id):
        async with pool.acquire() as conn:
            rows = await conn.fetch('''SELECT model,difficulty,quality,quality_n,p50_ms,p95_ms,error_rate,
                price_usd,available,cooldown_until,refreshed_at FROM tank.router_scoreboard
                WHERE tenant_id=$1 AND region=$2 AND task_type=$3''', tenant_id, region, task_type)
    return [Entry(model=r['model'], difficulty=int(r['difficulty']), quality=_finite(r['quality']),
                  quality_n=int(r['quality_n']), p50_ms=r['p50_ms'], p95_ms=r['p95_ms'],
                  error_rate=_finite(r['error_rate']), price_usd=_finite(r['price_usd']),
                  available=bool(r['available']), cooldown_until=r['cooldown_until'],
                  refreshed_at=r['refreshed_at']) for r in rows]


async def _upsert(conn, tenant_id, region, task_type, model, difficulty, values: dict) -> None:
    await conn.execute('''INSERT INTO tank.router_scoreboard
        (tenant_id,region,task_type,model,difficulty,gold_agreement,gold_n,shadow_agreement,shadow_n,
         deepeval_score,deepeval_n,quality,quality_n,p50_ms,p95_ms,error_rate,calls,price_usd,available,
         cooldown_until,refreshed_at)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,now())
        ON CONFLICT(tenant_id,region,task_type,model,difficulty) DO UPDATE SET
        gold_agreement=excluded.gold_agreement,gold_n=excluded.gold_n,shadow_agreement=excluded.shadow_agreement,
        shadow_n=excluded.shadow_n,deepeval_score=excluded.deepeval_score,deepeval_n=excluded.deepeval_n,
        quality=excluded.quality,quality_n=excluded.quality_n,p50_ms=excluded.p50_ms,p95_ms=excluded.p95_ms,
        error_rate=excluded.error_rate,calls=excluded.calls,price_usd=excluded.price_usd,
        available=excluded.available,cooldown_until=excluded.cooldown_until,refreshed_at=now()''',
        tenant_id, region, task_type, model, difficulty, values['gold'], values['gold_n'],
        values['shadow'], values['shadow_n'], values['deepeval'], values['deepeval_n'], values['quality'],
        values['quality_n'], values['p50_ms'], values['p95_ms'], values['error_rate'], values['calls'],
        values['price'], values['available'], values['cooldown_until'])


async def refresh(pool, tenant_id: uuid.UUID, region: str, task_type: str, *,
                  roster: set[str], platform_tenant: uuid.UUID) -> int:
    """Recompute this tenant's board for one task type from receipts, evals and shadows.

    Costs no model call. Every query names this tenant; the only other rows read
    are the platform bench's price per request, which hold no client data.
    """
    from tenant_db import tenant_scope
    import engine_runtime
    window = timedelta(days=WINDOW_DAYS)
    with tenant_scope(tenant_id):
        async with pool.acquire() as conn:
            receipts = await conn.fetch('''SELECT model,count(*) AS calls,
                percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms)
                    FILTER (WHERE outcome='delivered' AND NOT cache_hit AND latency_ms IS NOT NULL) AS p50,
                percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)
                    FILTER (WHERE outcome='delivered' AND NOT cache_hit AND latency_ms IS NOT NULL) AS p95,
                avg(CASE WHEN outcome='failed' THEN 1.0 ELSE 0.0 END) AS error_rate,
                avg(cost_usd) FILTER (WHERE outcome='delivered' AND NOT cache_hit AND cost_status='set') AS price,
                count(*) FILTER (WHERE outcome='delivered' AND NOT cache_hit AND cost_status='set') AS priced,
                max(ts) FILTER (WHERE outcome='failed') AS last_failure
                FROM tank.ledger WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND ts>now()-$4::interval
                AND rung IN (1,2) GROUP BY model''', tenant_id, region, task_type, window)
            gold = await conn.fetch('''SELECT DISTINCT ON (model) model,agreement,samples FROM tank.engine_evals
                WHERE tenant_id=$1 AND region=$2 AND task_type=$3 ORDER BY model,created_at DESC''',
                tenant_id, region, task_type)
            shadows = await conn.fetch('''SELECT s.candidate_model AS model,coalesce(l.routellm_score,d.difficulty) AS difficulty,
                s.agreement,s.quality FROM tank.shadow s
                JOIN tank.ledger l ON l.id=s.ledger_id AND l.tenant_id=s.tenant_id
                LEFT JOIN tank.router_decisions d ON d.tenant_id=s.tenant_id AND d.ledger_id=s.ledger_id
                WHERE s.tenant_id=$1 AND l.region=$2 AND s.task_type=$3 AND s.created_at>now()-$4::interval
                ORDER BY s.created_at DESC LIMIT $5''', tenant_id, region, task_type, window, MAX_EVIDENCE_ROWS)
            proofs = await conn.fetch('''SELECT p.model,coalesce(l.routellm_score,d.difficulty) AS difficulty,
                p.agreement,p.quality FROM tank.engine_proofs p
                JOIN tank.ledger l ON l.id=p.ledger_id AND l.tenant_id=p.tenant_id
                LEFT JOIN tank.router_decisions d ON d.tenant_id=p.tenant_id AND d.ledger_id=p.ledger_id
                WHERE p.tenant_id=$1 AND p.region=$2 AND p.task_type=$3 AND p.created_at>now()-$4::interval
                ORDER BY p.created_at DESC LIMIT $5''', tenant_id, region, task_type, window, MAX_EVIDENCE_ROWS)
            benched = {(r['model'], int(r['difficulty'])): (_finite(r['bench_score']), int(r['bench_n']))
                       for r in await conn.fetch('''SELECT model,difficulty,bench_score,bench_n FROM tank.router_scoreboard
                       WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND bench_n>0''', tenant_id, region, task_type)}
    with tenant_scope(platform_tenant):
        async with pool.acquire() as conn:
            bench_prices = {r['model']: _money(r['bench_cost_usd']) for r in await conn.fetch(
                '''SELECT model,bench_cost_usd FROM tank.router_scoreboard WHERE tenant_id=$1 AND region=$2
                AND task_type=$3 AND difficulty=-1 AND bench_cost_usd IS NOT NULL''', platform_tenant, region, task_type)}
    evidence = aggregate([(_model_name(r['model']), r['difficulty'], r['agreement'], _deepeval(r['quality']))
                          for r in [*shadows, *proofs]])
    by_model = {r['model']: r for r in receipts}
    golds = {r['model']: r for r in gold}
    models = set(by_model) | set(golds) | {m for m, _ in evidence} | {m for m, _ in benched}
    now = _now()
    written = 0
    with tenant_scope(tenant_id):
        async with pool.acquire() as conn, conn.transaction():
            for model in sorted(models):
                receipt = by_model.get(model)
                price = None
                if receipt is not None and receipt['priced'] >= 1:
                    price = _money(receipt['price'])
                if price is None:
                    price = bench_prices.get(model)
                if price is None and model in engine_runtime.LOCAL:
                    price = Decimal(0)  # The zero-token-cost rung; still needs evidence to pass.
                cooldown = None
                if receipt is not None and receipt['last_failure'] is not None:
                    until = receipt['last_failure'] + timedelta(seconds=COOLDOWN_S)
                    cooldown = until if until > now else None
                common = {
                    'p50_ms': int(receipt['p50']) if receipt is not None and receipt['p50'] is not None else None,
                    'p95_ms': int(receipt['p95']) if receipt is not None and receipt['p95'] is not None else None,
                    'error_rate': _finite(receipt['error_rate']) if receipt is not None else None,
                    'calls': int(receipt['calls']) if receipt is not None else 0,
                    'price': price,
                    'available': model in roster and engine_runtime.available(model),
                    'cooldown_until': cooldown,
                }
                buckets = sorted({b for m, b in evidence if m == model} | {b for m, b in benched if m == model} | {ALL})
                for b in buckets:
                    slot = evidence.get((model, b), {'agree': 0.0, 'agree_n': 0, 'deep': 0.0, 'deep_n': 0})
                    g = golds.get(model) if b == ALL else None
                    gold_value = _finite(g['agreement']) if g is not None else None
                    gold_n = int(g['samples']) if g is not None else 0
                    shadow = slot['agree'] / slot['agree_n'] if slot['agree_n'] else None
                    deep = slot['deep'] / slot['deep_n'] if slot['deep_n'] else None
                    quality, quality_n = compose((gold_value, gold_n), benched.get((model, b), (None, 0)), (shadow, slot['agree_n']),
                                                 (deep, slot['deep_n']), whole_task=b == ALL)
                    await _upsert(conn, tenant_id, region, task_type, model, b, {
                        **common, 'gold': gold_value, 'gold_n': gold_n, 'shadow': shadow,
                        'shadow_n': slot['agree_n'], 'deepeval': deep, 'deepeval_n': slot['deep_n'],
                        'quality': quality, 'quality_n': quality_n})
                    written += 1
    return written


async def record_bench(pool, *, platform_tenant: uuid.UUID, region: str, task_type: str, model: str,
                       score: float | None, cost_per_call: Any, samples: int,
                       per_case: list[tuple[float | None, float]] | None = None) -> None:
    """The nightly bench's write: platform rows only, from platform evals and held-out gold."""
    from tenant_db import tenant_scope
    rows: dict[int, tuple[float | None, int]] = {ALL: (_finite(score), int(samples))}
    for difficulty, value in per_case or []:
        b = bucket(difficulty)
        if b is None or _finite(value) is None:
            continue
        total, n = rows.get(b, (0.0, 0))
        rows[b] = ((total or 0.0) + float(value), n + 1)
    with tenant_scope(platform_tenant):
        async with pool.acquire() as conn, conn.transaction():
            for b, (value, n) in rows.items():
                if b != ALL and n:
                    value = value / n
                await conn.execute('''INSERT INTO tank.router_scoreboard
                    (tenant_id,region,task_type,model,difficulty,bench_score,bench_n,bench_cost_usd,bench_at,price_usd,refreshed_at)
                    VALUES($1,$2,$3,$4,$5,$6,$7,$8,now(),$8,now())
                    ON CONFLICT(tenant_id,region,task_type,model,difficulty) DO UPDATE SET
                    bench_score=excluded.bench_score,bench_n=excluded.bench_n,bench_cost_usd=excluded.bench_cost_usd,
                    bench_at=now(),price_usd=coalesce(tank.router_scoreboard.price_usd,excluded.price_usd),
                    refreshed_at=now()''', platform_tenant, region, task_type, model, b, value, n,
                    _money(cost_per_call) if b == ALL else None)
                row = await conn.fetchrow('''SELECT gold_agreement,gold_n,bench_score,bench_n,shadow_agreement,shadow_n,
                    deepeval_score,deepeval_n FROM tank.router_scoreboard WHERE tenant_id=$1 AND region=$2
                    AND task_type=$3 AND model=$4 AND difficulty=$5''', platform_tenant, region, task_type, model, b)
                quality, quality_n = compose((row['gold_agreement'], row['gold_n']), (row['bench_score'], row['bench_n']),
                                             (row['shadow_agreement'], row['shadow_n']),
                                             (row['deepeval_score'], row['deepeval_n']), whole_task=b == ALL)
                await conn.execute('''UPDATE tank.router_scoreboard SET quality=$6,quality_n=$7
                    WHERE tenant_id=$1 AND region=$2 AND task_type=$3 AND model=$4 AND difficulty=$5''',
                    platform_tenant, region, task_type, model, b, quality, quality_n)


async def record_bench_run(pool, *, platform_tenant: uuid.UUID, region: str, task_type: str, model: str,
                           score: float | None, cost_per_call: Any, case_scores: list[tuple[list[dict], float]]) -> None:
    """Bench hook: score each case's difficulty on CPU (no model call), then write the board.

    A missing RouteLLM checkpoint only drops the per-difficulty rows; a board
    failure never fails the bench run it describes.
    """
    import asyncio
    import logging
    import routellm_shadow
    per_case: list[tuple[float | None, float]] = []
    for messages, value in case_scores:
        prompt = next((str(m.get('content') or '') for m in reversed(messages) if m.get('role') == 'user'), '')
        try:
            difficulty = await asyncio.to_thread(routellm_shadow.score, prompt)
        except Exception:
            difficulty = None
        per_case.append((difficulty, value))
    try:
        await record_bench(pool, platform_tenant=platform_tenant, region=region, task_type=task_type, model=model,
                           score=score, cost_per_call=cost_per_call, samples=len(case_scores), per_case=per_case)
    except Exception as exc:
        logging.getLogger(__name__).warning('Router scoreboard bench write failed (%s)', type(exc).__name__)
