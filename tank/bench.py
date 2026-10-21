"""Platform-only nightly roster bench. No policy.model writes or provider keys.

The router lifespan owns the worker. PostgreSQL locks serialize replicas; durable
reservations survive a crash and remain charged until a known receipt settles them.
Only platform evals and platform held-out gold from this box are replayed.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import logging
import math
import os
import re
import uuid
from typing import Any

from fastapi import APIRouter
import httpx

import graduate
from gold import PLATFORM_TENANT, encoded, obj, runtime

log = logging.getLogger(__name__)
LOCK_ID = 218001


def price_book(rows: list[dict]) -> dict[str, dict]:
    book = {}
    for row in rows:
        info = row.get('model_info') or {}
        a, b = info.get('input_cost_per_token'), info.get('output_cost_per_token')
        if a is None or b is None or not all(math.isfinite(float(x)) and float(x) >= 0 for x in (a, b)):
            continue
        provider = str((row.get('litellm_params') or {}).get('model') or '')
        # Family is provider + product line, not an alias (luna/sol/astra -> openai/gpt).
        family = re.sub(r'[-\d].*$', '', provider.rsplit('/', 1)[-1])
        family = provider.split('/')[0] + '/' + family if '/' in provider else provider
        if not family:
            family = row['model_name']
        book[row['model_name']] = {'input': Decimal(str(a)), 'output': Decimal(str(b)), 'family': family}
    return book


def fingerprints(book: dict) -> tuple[str, str]:
    digest = lambda value: hashlib.sha256(encoded(value).encode()).hexdigest()
    return digest(sorted(book)), digest(book)


def due(state: dict | None, now: datetime, roster: str, prices: str) -> bool:
    return not state or not state.get('bench_at') or (
        state['bench_at'].date() < now.date()
        or state.get('bench_roster_fingerprint') != roster
        or state.get('bench_price_fingerprint') != prices
    )


def choose_candidate(results: list[dict], comparison: str, serving: str) -> str | None:
    complete = {r['model']: r for r in results if r['status'] == 'complete'}
    current = complete.get(comparison)
    if not current:
        return None
    eligible = [r for r in complete.values() if r['model'] not in (comparison, serving)
                and r['score'] >= current['score'] and r['cost_per_call'] < current['cost_per_call']]
    return min(eligible, key=lambda r: (r['cost_per_call'], r['model']))['model'] if eligible else None


def messages_for(value: Any, system: str | None) -> list[dict]:
    raw = value.get('messages') if isinstance(value, dict) else value if isinstance(value, list) else None
    if isinstance(raw, list) and raw and all(isinstance(m, dict) and m.get('role') in ('user','assistant','system')
                                             and isinstance(m.get('content'), str) for m in raw):
        messages = [{'role': m['role'], 'content': m['content']} for m in raw]
    else:
        messages = [{'role': 'user', 'content': value if isinstance(value, str) else encoded(value)}]
    return ([{'role': 'system', 'content': system}] if system else []) + messages


def reserve_quote(messages: list[dict], max_tokens: int, book: dict) -> Decimal:
    # UTF-8 bytes bound text token counts; allowance covers chat framing. Use the
    # highest rates, so a gateway fallback cannot evade the daily reservation.
    upper_input = len(encoded(messages).encode('utf-8')) + 1024
    return max(p['input'] for p in book.values()) * upper_input + max(p['output'] for p in book.values()) * max_tokens


async def sync_prices(conn, book: dict) -> None:
    async with conn.transaction():
        await conn.execute('UPDATE tank.proof_prices SET active=false WHERE active')
        for name, p in book.items():
            await conn.execute('''INSERT INTO tank.proof_prices(model,family,input_usd,output_usd)
                VALUES ($1,$2,$3,$4) ON CONFLICT(model) DO UPDATE SET family=$2,input_usd=$3,output_usd=$4,
                active=true,updated_at=CASE WHEN (tank.proof_prices.input_usd,tank.proof_prices.output_usd)
                IS DISTINCT FROM ($3,$4) THEN now() ELSE tank.proof_prices.updated_at END''',
                name, p['family'], p['input'], p['output'])
        await conn.execute('''UPDATE tank.policy p SET baseline_model=(
            SELECT b.model FROM tank.proof_prices a JOIN tank.proof_prices b ON b.family=a.family AND b.active
            WHERE a.model=p.model ORDER BY b.input_usd+b.output_usd DESC,b.model LIMIT 1)
            WHERE p.tenant_id IS NULL AND p.baseline_model IS NULL''')


async def backfill(conn, tenant: uuid.UUID, region: str) -> None:
    # A current price-book estimate, explicitly marked; never rewrites a receipt
    # already priced at call time. Tenant policies override platform defaults.
    await conn.execute('''WITH pending AS (
        SELECT l.id,coalesce((SELECT coalesce(p.baseline_model,(SELECT b.model FROM tank.proof_prices a
          JOIN tank.proof_prices b ON b.family=a.family AND b.active WHERE a.model=p.model
          ORDER BY b.input_usd+b.output_usd DESC,b.model LIMIT 1)) FROM tank.policy p
          WHERE p.task_type=l.task_type AND (p.tenant_id=l.tenant_id OR p.tenant_id IS NULL)
          ORDER BY p.tenant_id NULLS LAST LIMIT 1),l.model) AS baseline
        FROM tank.ledger l WHERE l.tenant_id=$1 AND l.region=$2 AND l.baseline_status='pending'
    ) UPDATE tank.ledger l SET baseline_model=p.baseline,
        baseline_cost_usd=CASE WHEN l.vendor IS NOT NULL THEN l.cost_usd
          WHEN l.tokens_in=0 AND l.tokens_out=0 THEN 0 ELSE l.tokens_in*b.input_usd+l.tokens_out*b.output_usd END,
        baseline_status='backfilled',baseline_priced_at=b.updated_at
        FROM pending p LEFT JOIN tank.proof_prices b ON b.model=p.baseline
        WHERE l.id=p.id AND l.tenant_id=$1 AND l.region=$2
          AND (b.model IS NOT NULL OR l.vendor IS NOT NULL OR (l.tokens_in=0 AND l.tokens_out=0))''', tenant, region)


async def cases_for(conn, task: str, region: str) -> list[dict]:
    rows = await conn.fetch('''SELECT id,input,expected,'eval' AS kind FROM tank.evals
        WHERE task_type=$1 AND (tenant_id=$2 OR tenant_id IS NULL) AND verdict='accepted' ORDER BY id''', task, PLATFORM_TENANT)
    cases = [{'ref': str(r['id']), 'kind': r['kind'], 'input': obj(r['input']), 'expected': obj(r['expected'])} for r in rows]
    # Approved package evals are valid without any live traffic or checked gold.
    for pkg in sorted(runtime()._packages.values(), key=lambda p: p.ref):
        if pkg.task_type == task:
            state = await conn.fetchval('SELECT state FROM tank.skills WHERE id=$1 AND version=$2', pkg.id, pkg.version)
            if state != 'approved':
                continue
            for i, case in enumerate(pkg.cases):
                cases.append({'ref': f'{pkg.ref}:{i}', 'kind': 'package', 'input': case['input'], 'expected': case['expected']})
    gold = await conn.fetch('''SELECT id,input,expected FROM tank.gold_examples WHERE tenant_id=$1 AND region=$2
        AND status='checked' AND holdout AND (NOT auto_label OR auto_approved)
        AND (skill_id=$3 OR skill_id IN (SELECT id FROM tank.skills WHERE task_type=$3)) ORDER BY id''', PLATFORM_TENANT, region, task)
    cases.extend({'ref': str(r['id']), 'kind': 'holdout', 'input': obj(r['input']), 'expected': obj(r['expected'])} for r in gold)
    return cases


async def reserve(conn, run_id: uuid.UUID, region: str, case: dict, amount: Decimal, cap: Decimal) -> uuid.UUID | None:
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock($1)', LOCK_ID + 1)
        spent = await conn.fetchval('''SELECT coalesce(sum(coalesce(charged_usd,reserved_usd)),0)
            FROM tank.bench_calls WHERE tenant_id=$1 AND region=$2 AND day=(now() AT TIME ZONE 'UTC')::date''', PLATFORM_TENANT, region)
        if Decimal(spent) + amount > cap:
            return None
        return await conn.fetchval('''INSERT INTO tank.bench_calls(run_id,tenant_id,region,day,case_ref,case_kind,reserved_usd)
            VALUES($1,$2,$3,(now() AT TIME ZONE 'UTC')::date,$4,$5,$6) RETURNING id''', run_id, PLATFORM_TENANT, region, case['ref'], case['kind'], amount)


async def call_model(model: str, messages: list[dict], max_tokens: int) -> dict:
    rt = runtime()
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f'{rt.LITELLM_URL}/v1/chat/completions',
            headers={'Authorization': f'Bearer {rt.LITELLM_MASTER_KEY}'},
            json={'model': model, 'messages': messages, 'max_tokens': max_tokens,
                  'temperature': 0, 'disable_fallbacks': True, 'num_retries': 0})
    # Never retain upstream error bodies: they can contain prompt data or keys.
    data = response.json() if response.is_success else {}
    usage = data.get('usage') or {}
    raw_cost = response.headers.get('x-litellm-response-cost')
    cost = Decimal(raw_cost) if raw_cost is not None else None
    if cost is not None and (not cost.is_finite() or cost < 0):
        cost = None
    return {'model': response.headers.get('x-litellm-model-group') or model,
            'content': rt._choice_answer(data)[0] if response.is_success else '',
            'tokens_in': int(usage.get('prompt_tokens') or 0), 'tokens_out': int(usage.get('completion_tokens') or 0),
            'cost': cost, 'ok': response.is_success and bool(usage), 'http_status': response.status_code}


async def bench_model(conn, policy: dict, model: str, cases: list[dict], book: dict, region: str, cap: Decimal, comparison: str) -> dict:
    suite_hash = hashlib.sha256(encoded({'cases': cases, 'system_prompt': policy.get('system_prompt'),
        'max_tokens_out': policy['max_tokens_out'], 'tolerance': policy.get('number_tolerance')}).encode()).hexdigest()
    run_id = await conn.fetchval('''INSERT INTO tank.bench_runs(tenant_id,region,task_type,model,comparison_model,suite_hash,expected_n)
        VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id''', PLATFORM_TENANT, region, policy['task_type'], model, comparison, suite_hash, len(cases))
    status, error = 'complete', None
    scores, costs = [], []
    for case in cases:
        messages = messages_for(case['input'], policy.get('system_prompt'))
        ceiling = reserve_quote(messages, policy['max_tokens_out'], book)
        call_id = await reserve(conn, run_id, region, case, ceiling, cap)
        if call_id is None:
            status, error = 'capped', 'Daily bench budget exhausted.'
            break
        try:
            result = await call_model(model, messages, policy['max_tokens_out'])
        except Exception:
            result = {'model': model, 'content': '', 'tokens_in': 0, 'tokens_out': 0, 'cost': None, 'ok': False}
        valid = result['ok'] and result['model'] == model and result['cost'] is not None and result['cost'] <= ceiling
        score = graduate.score_pair(case['expected'], result['content'], tolerance=float(policy.get('number_tolerance') or .01)) if valid else None
        # Even failures leave a receipt; unknown cost retains its budget reservation.
        async with conn.transaction():
            ledger_id = await conn.fetchval('''INSERT INTO tank.ledger
                (tenant_id,region,agent,task_type,model,tokens_in,tokens_out,cost_usd,outcome,error,eval_score)
                VALUES($1,$2,'bench',$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id''',
                PLATFORM_TENANT, region, policy['task_type'], result['model'], result['tokens_in'], result['tokens_out'],
                result['cost'] or Decimal(0), 'delivered' if valid else 'unverified',
                None if valid else 'Bench call unverified; unknown spend remains reserved.', score)
            await conn.execute('''UPDATE tank.bench_calls SET ledger_id=$2,charged_usd=$3,score=$4,status=$5
                WHERE id=$1 AND tenant_id=$6 AND region=$7''', call_id, ledger_id, result['cost'], score,
                'complete' if valid else 'unverified', PLATFORM_TENANT, region)
        if not valid:
            status, error = 'failed', 'Unverified model, usage, price or provider response; no proposal.'
            break
        scores.append(score)
        costs.append(result['cost'])
    score = sum(scores)/len(scores) if scores and status == 'complete' else None
    cost = sum(costs)/len(costs) if costs and status == 'complete' else None
    await conn.execute('''UPDATE tank.bench_runs SET score=$2,cost_per_call=$3,status=$4,error=$5,finished_at=now()
        WHERE id=$1 AND tenant_id=$6 AND region=$7''', run_id, score, cost, status, error, PLATFORM_TENANT, region)
    if status == 'complete':
        await conn.execute('''INSERT INTO tank.route_evidence(task_type,model,rung,bench_run_id,bench_score,bench_cost_per_call,bench_n,bench_at)
            VALUES($1,$2,1,$3,$4,$5,$6,now()) ON CONFLICT(task_type,model,rung) DO UPDATE SET
            bench_run_id=$3,bench_score=$4,bench_cost_per_call=$5,bench_n=$6,bench_at=now()''',
            policy['task_type'], model, run_id, score, cost, len(scores))
    return {'model': model, 'score': score, 'cost_per_call': cost, 'status': status}


async def tick() -> None:
    rt = runtime()
    cap = Decimal(os.environ.get('TANK_BENCH_MAX_USD') or '5')
    if not cap.is_finite() or cap < 0:
        raise ValueError('TANK_BENCH_MAX_USD must be finite and nonnegative')
    region = rt.box_region()
    async with rt.pool().acquire() as conn:
        if not await conn.fetchval('SELECT pg_try_advisory_lock($1)', LOCK_ID):
            return
        try:
            roster = await rt._roster_models()
            book = price_book(roster)
            if not book:
                raise RuntimeError('No priced roster available; bench unchanged')
            await sync_prices(conn, book)
            # Explicit tenant scopes: no client rows are used as platform examples.
            tenants = await conn.fetch('SELECT DISTINCT tenant_id FROM tank.ledger WHERE region=$1', region)
            for tenant in tenants:
                await backfill(conn, tenant['tenant_id'], region)
            roster_fp, price_fp = fingerprints(book)
            roster_fp = hashlib.sha256(encoded(roster).encode()).hexdigest()
            policies = await conn.fetch("SELECT * FROM tank.policy WHERE tenant_id IS NULL AND rung IN (1,2) ORDER BY task_type")
            for row in policies:
                policy = dict(row)
                state = await conn.fetchrow('SELECT * FROM tank.search_state WHERE task_type=$1', policy['task_type'])
                if not due(dict(state) if state else None, datetime.now(timezone.utc), roster_fp, price_fp):
                    continue
                cases = await cases_for(conn, policy['task_type'], region)
                comparison = policy.get('candidate_model') or policy['model']
                results = []
                if cases:
                    # Unknown prices cannot be budgeted safely; retain an explicit
                    # failure for every skipped roster entry instead of hiding it.
                    for entry in roster:
                        if entry['model_name'] not in book:
                            await conn.execute('''INSERT INTO tank.bench_runs
                                (tenant_id,region,task_type,model,comparison_model,suite_hash,expected_n,status,error,finished_at)
                                VALUES($1,$2,$3,$4,$5,$6,$7,'failed','Token prices unavailable; no call made.',now())''',
                                PLATFORM_TENANT, region, policy['task_type'], entry['model_name'], comparison,
                                hashlib.sha256(encoded(cases).encode()).hexdigest(), len(cases))
                            results.append({'model': entry['model_name'], 'status': 'failed'})
                    for model in sorted(book, key=lambda m: (book[m]['input']+book[m]['output'], m)):
                        result = await bench_model(conn, policy, model, cases, book, region, cap, comparison)
                        results.append(result)
                        if result['status'] == 'capped':
                            break
                proposal = choose_candidate(results, comparison, policy['model'])
                status = 'no_cases' if not cases else 'capped' if any(r['status']=='capped' for r in results) else 'failed' if any(r['status']=='failed' for r in results) else 'complete'
                async with conn.transaction():
                    if proposal:
                        # Compare-and-set: never overwrite a concurrent founder choice.
                        await conn.execute('''UPDATE tank.policy SET candidate_model=$2,auto_promote=false,updated_at=now()
                            WHERE task_type=$1 AND tenant_id IS NULL AND model=$3 AND candidate_model IS NOT DISTINCT FROM $4''',
                            policy['task_type'], proposal, policy['model'], policy.get('candidate_model'))
                    await conn.execute('''INSERT INTO tank.search_state(task_type,bench_roster_fingerprint,bench_price_fingerprint,bench_at,bench_status,bench_error)
                        VALUES($1,$2,$3,now(),$4,$5) ON CONFLICT(task_type) DO UPDATE SET
                        bench_roster_fingerprint=$2,bench_price_fingerprint=$3,bench_at=now(),bench_status=$4,bench_error=$5''',
                        policy['task_type'], roster_fp, price_fp, status,
                        'See benchmark receipts.' if status in ('failed','capped') else 'No platform evals or held-out gold.' if status=='no_cases' else None)
        finally:
            await conn.execute('SELECT pg_advisory_unlock($1)', LOCK_ID)


async def loop() -> None:
    while True:
        try:
            await tick()
        except Exception as exc:
            log.error('Bench unavailable (%s); retrying in five minutes', type(exc).__name__)
        await asyncio.sleep(300)


@asynccontextmanager
async def lifespan(_app):
    task = asyncio.create_task(loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


router = APIRouter(lifespan=lifespan)
