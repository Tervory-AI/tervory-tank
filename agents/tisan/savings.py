"""Tisan run evidence: Tank spend and a separately priced all-paid comparison."""
from __future__ import annotations

import asyncio
from contextvars import ContextVar
from functools import lru_cache
import hashlib
import json
import os
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

ACTIVE = ContextVar('tisan_savings_run', default=None)


def run_id(tenant, operation, kind):
    return uuid5(NAMESPACE_URL, 'tisan.run:' + str(UUID(str(tenant))) + ':' + kind + ':' + str(UUID(str(operation))))


@lru_cache(maxsize=1)
def encoding():
    import tiktoken
    from tiktoken.load import load_tiktoken_bpe
    vocabulary = Path(__file__).with_name('cl100k_base.tiktoken')
    if not vocabulary.is_file():
        vocabulary = Path(__file__).resolve().parents[2] / 'vendor/tervory-tank/tank/cl100k_base.tiktoken'
    ranks = load_tiktoken_bpe(str(vocabulary),
        expected_hash='223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7')
    # Same reference encoding as Tank's agent_skills.input_encoding.
    return tiktoken.Encoding(name='tisan-cl100k', mergeable_ranks=ranks, special_tokens={},
        pat_str=r"'(?i:[sdmt]|ll|ve|re)|[^\r\n\p{L}\p{N}]?+\p{L}++|\p{N}{1,3}+| ?[^\s\p{L}\p{N}]++[\r\n]*+|\s++$|\s*[\r\n]|\s+(?!\S)|\s")


def tokens(value):
    return len(encoding().encode_ordinary(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))))


def routing():
    run = ACTIVE.get()
    if run is not None:
        run['pending'] += 1


def routed(reply):
    run = ACTIVE.get()
    if run is not None:
        try:
            identifier = str(UUID(str(reply['ledger_id'])))
        except (KeyError, TypeError, ValueError):
            return  # A missing receipt is unknown spend, never a free call.
        run['ids'].append(identifier)
        run['pending'] -= 1


def unpack(value):
    return json.loads(value) if isinstance(value, str) else value


async def complete(conn, tenant, operation, kind, payload, result, *, ids=(), uncertain=False, measurement=None):
    """Called only after an authenticated job/Command action supplied its scope.

    The ledger contains the real route spend plus a zero-cost code envelope.
    Its companion snapshot carries the run total and the all-paid comparison;
    never bill that comparison or add the aggregate to the model ledger again.
    """
    tenant, operation = UUID(str(tenant)), UUID(str(operation))
    identifier = run_id(tenant, operation, kind)
    digest = (measurement['input_hash'] if measurement is not None else
        hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest())
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtext($1),hashtext($2))', str(tenant), str(operation))
        old = await conn.fetchrow('SELECT input_hash,route_ids,uncertain FROM agent_tisan.run_receipts WHERE tenant_id=$1 AND id=$2 FOR UPDATE', tenant, identifier)
        if old and old['input_hash'] != digest:
            raise ValueError('run input changed')
        ids = sorted(set(str(UUID(str(i))) for i in ids) | set(unpack(old['route_ids']) if old else []))
        uncertain = uncertain or bool(old and old['uncertain'])
        rows = await conn.fetch('SELECT id,cost_usd,cost_status,tokens_in,tokens_out FROM tank.ledger WHERE tenant_id=$1 AND id=ANY($2::uuid[])', tenant, [UUID(i) for i in ids])
        if len(rows) != len(ids):
            raise ValueError('run receipt outside tenant or missing')
        cost = None if uncertain or any(r['cost_status'] == 'not_set' for r in rows) else sum(r['cost_usd'] for r in rows)
        # A founder task override wins; otherwise reuse the existing paid
        # reporting standard. Never introduce a serving model or a price here.
        price = await conn.fetchrow('''SELECT p.model,p.input_usd,p.output_usd FROM tank.proof_prices p
            WHERE p.model=coalesce((SELECT override_model FROM tank.baseline_settings WHERE task_type='tisan.plan'),
                tank.standard_model_for('openai')) AND p.active''')
        before_in, before_out = ((measurement['tokens_in'], measurement['tokens_out']) if measurement is not None
                                 else (tokens(payload), tokens(result)))
        baseline = before_in * price['input_usd'] + before_out * price['output_usd'] if price else None
        await conn.execute('''INSERT INTO tank.ledger(id,tenant_id,region,agent,task_type,rung,model,cost_usd,tokens_in,tokens_out)
            VALUES($1,$2,$3,'tisan',$4,3,'code',0,0,0) ON CONFLICT(id) DO NOTHING''',
            identifier, tenant, os.environ.get('TANK_REGION', 'us-east'), 'tisan.' + kind)
        saved = await conn.fetchrow('''INSERT INTO agent_tisan.run_receipts
            (tenant_id,id,input_hash,kind,route_ids,uncertain,cost_usd,baseline_model,baseline_cost_usd,baseline_tokens_in,baseline_tokens_out,tokens_in,tokens_out)
            VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,$10,$11,$12,$13)
            ON CONFLICT(tenant_id,id) DO UPDATE SET route_ids=excluded.route_ids,uncertain=excluded.uncertain,
                cost_usd=excluded.cost_usd,baseline_model=excluded.baseline_model,baseline_cost_usd=excluded.baseline_cost_usd,
                baseline_tokens_in=excluded.baseline_tokens_in,baseline_tokens_out=excluded.baseline_tokens_out,
                tokens_in=excluded.tokens_in,tokens_out=excluded.tokens_out
            RETURNING *''', tenant, identifier, digest, kind, json.dumps(ids), uncertain, cost,
            price['model'] if price else None, baseline, before_in, before_out,
            sum(r['tokens_in'] for r in rows), sum(r['tokens_out'] for r in rows))
    return public(saved)


def public(row):
    cost, baseline = row['cost_usd'], row['baseline_cost_usd']
    return {'ledger_id': str(row['id']), 'cost_usd': float(cost) if cost is not None else None,
        'baseline_cost_usd': float(baseline) if baseline is not None else None,
        'saved_usd': float(baseline-cost) if baseline is not None and cost is not None else None,
        'tokens_in': row['tokens_in'], 'tokens_out': row['tokens_out'],
        'cost_status': 'recorded' if cost is not None else 'pending',
        'baseline_status': 'recorded' if baseline is not None else 'baseline pending',
        'baseline_basis': 'cl100k reference estimate of all input/output at the paid default rate'}


async def remote(conn, tenant, operation, kind, payload, result, *, ids=(), uncertain=False):
    """Room roles own only agent_tisan; Tank alone reads prices and its ledger."""
    import httpx
    try:
        from agents.tisan import upstream
    except ModuleNotFoundError:
        import upstream
    tenant, operation = UUID(str(tenant)), UUID(str(operation))
    identifier = run_id(tenant, operation, kind)
    measurement = {'input_hash': hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                   'tokens_in': tokens(payload), 'tokens_out': tokens(result)}
    base, key = os.environ.get('TANK_URL', ''), os.environ.get('TANK_KEY', '')
    if base and key:
        try:
            # Idempotent receipt writes use their durable run identity. A lost
            # acknowledgement is reconciled by a later read/retry, never resent.
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False, timeout=15) as client:
                response = await upstream.post(client, base.rstrip('/') + '/v1/command/tisan/pipeline/receipts',
                    headers={'X-Tank-Key': key, 'X-Tervory-Tenant': str(tenant),
                             'X-Tervory-Region': os.environ.get('TANK_REGION', 'us-east')},
                    json={'tenant_id': str(tenant), 'operation_id': str(operation), 'kind': kind,
                          'measurement': measurement, 'route_ids': list(map(str, ids)), 'uncertain': uncertain},
                    timeout=15, follow_redirects=False)
                response.raise_for_status()
                data = response.json()
                if (data['tenant_id'] != str(tenant) or data['operation_id'] != str(operation)
                        or data['receipt']['ledger_id'] != str(identifier)):
                    raise ValueError('receipt scope mismatch')
                return data['receipt']
        except (httpx.HTTPError, ValueError, KeyError, TypeError, TimeoutError):
            pass
    # Missing configuration/a Tank outage cannot turn a completed code action
    # into a failure, nor label an unanswered model request as free. Keep local
    # evidence for reconciliation, with the comparison explicitly pending.
    async with conn.transaction():
        await conn.execute('SELECT pg_advisory_xact_lock(hashtext($1),hashtext($2))', str(tenant), str(operation))
        old = await conn.fetchrow('SELECT * FROM agent_tisan.run_receipts WHERE tenant_id=$1 AND id=$2 FOR UPDATE', tenant, identifier)
        if old:
            if old['input_hash'] != measurement['input_hash']:
                raise ValueError('run input changed')
            new_ids = set(map(str, ids)) - set(unpack(old['route_ids']))
            if new_ids or (uncertain and not old['uncertain']):
                saved = await conn.fetchrow('''UPDATE agent_tisan.run_receipts SET
                    route_ids=$3::jsonb,uncertain=$4,cost_usd=NULL WHERE tenant_id=$1 AND id=$2 RETURNING *''',
                    tenant, identifier, json.dumps(sorted(set(unpack(old['route_ids'])) | set(map(str, ids)))),
                    uncertain or old['uncertain'])
                return public(saved)
            # A lost successful reply must not overwrite Tank's durable snapshot.
            return public(old)
        saved = await conn.fetchrow('''INSERT INTO agent_tisan.run_receipts
            (tenant_id,id,input_hash,kind,route_ids,uncertain,cost_usd,baseline_tokens_in,baseline_tokens_out,tokens_in,tokens_out)
            VALUES($1,$2,$3,$4,$5::jsonb,$6,$7,$8,$9,0,0) RETURNING *''',
            tenant, identifier, measurement['input_hash'], kind, json.dumps(list(map(str, ids))), uncertain,
            None if ids or uncertain else 0, measurement['tokens_in'], measurement['tokens_out'])
    return public(saved)


async def run(handler, ctx, pool, kind, *, recorder=complete):
    # Room-specific migrations finish after the chassis creates its worker
    # tasks. A claimed job must not do work before its evidence store exists.
    async with asyncio.timeout(15), pool.acquire() as conn:
        if not await conn.fetchval("SELECT to_regclass('agent_tisan.run_receipts')"):
            raise RuntimeError('run receipt store unavailable')
    state = {'ids': [], 'pending': 0}
    token = ACTIVE.set(state)
    result = None
    try:
        try:
            result = await handler(ctx)
        except BaseException as exc:
            # Cancellation/provider errors still leave evidence without their
            # text, prompts or upstream bodies. Preserve the original failure.
            result = {'ok': False, 'detail': type(exc).__name__}
            raise
        finally:
            if result is not None:
                async with asyncio.timeout(30), pool.acquire() as conn:
                    receipt = await recorder(conn, ctx.tenant_id, ctx.job_id, kind, ctx.input, result,
                        ids=state['ids'], uncertain=bool(state['pending']))
        return {**result, 'ledger_id': receipt['ledger_id'], 'receipt': receipt}
    finally:
        ACTIVE.reset(token)


async def overlay(conn, tenant, records):
    """Trusted snapshots for the existing Command/Window/mobile receipt view."""
    # Older Tank instances can read ordinary receipts before the room migration.
    if not await conn.fetchval("SELECT to_regclass('agent_tisan.run_receipts')"):
        return records
    snapshots = await conn.fetch('SELECT * FROM agent_tisan.run_receipts WHERE tenant_id=$1 AND id=ANY($2::uuid[])',
        UUID(str(tenant)), [UUID(str(r['id'])) for r in records if r.get('agent') == 'tisan'])
    by_id = {str(r['id']): r for r in snapshots}
    result = []
    for record in records:
        saved = by_id.get(str(record['id']))
        if saved is not None:
            record = {**record, **public(saved), 'baseline_model': saved['baseline_model'],
                      'cost_status': 'set' if saved['cost_usd'] is not None else 'not_set'}
        result.append(record)
    return result
