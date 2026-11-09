"""Replay completed job receipts; serialize claims and commit code work atomically."""
from contextvars import ContextVar
from functools import wraps
import json
import asyncio
import logging
from uuid import UUID

active_ledger = ContextVar('market_job_ledger', default=None)
after_commit = ContextVar('market_job_effects', default=None)
# Dispatch channels persist their own sending/uncertain receipts; never enclose
# those external side effects in a transaction that could roll them back.
INCREMENTAL = {'alerts', 'refresh', 'feed_links'}


def defer(callback):
    pending = after_commit.get()
    if pending is None:
        return False
    pending.append(callback)
    return True


async def publish(*args, **kwargs):
    from chassis.events import publish as send
    if defer(lambda: send(*args, **kwargs)):
        return True
    return await send(*args, **kwargs)


def guarded(handler, connection):
    @wraps(handler)
    async def run(ctx):
        ident = getattr(ctx, 'job_id', None)
        if not ident:
            result = await handler(ctx)
            from core.savings import record
            receipt = await record(connection, ctx.tenant_id, handler.__name__,
                {k:v for k,v in getattr(ctx, 'input', {}).items() if k in {'question','engine','areas','signals','passages','source','backfill'}}, result,
                cached=bool(result.get('cache_hit')))
            return {**result, 'run_receipt': receipt}
        owner, job = UUID(ctx.tenant_id), UUID(ident)
        effects = []
        async with connection(memory=ctx.memory) as ledger, ledger.conn.transaction():
            row = await ledger.conn.fetchrow('''SELECT kind,status,result FROM agent_market_lab.jobs
                WHERE tenant_id=$1 AND id=$2 FOR UPDATE''', owner, job)
            if row is None or row['kind'] != ctx.kind:
                raise ValueError('Job does not belong to this tenant and handler')
            completed = await ledger.conn.fetchval('SELECT result FROM agent_market_lab.executions WHERE tenant_id=$1 AND job_id=$2', owner, job)
            if completed is not None:
                return json.loads(completed) if isinstance(completed, str) else dict(completed)
            if row['status'] == 'done':
                return json.loads(row['result']) if isinstance(row['result'], str) else dict(row['result'])
            if row['status'] not in {'queued', 'running'}:
                raise ValueError('Job is not runnable')
            token = active_ledger.set(None if ctx.kind in INCREMENTAL else ledger)
            effect_token = after_commit.set(None if ctx.kind in INCREMENTAL else effects)
            try:
                result = await handler(ctx)
                from core.savings import record
                receipt = await record(connection, ctx.tenant_id, ctx.kind,
                    {k:v for k,v in getattr(ctx, 'input', {}).items() if k in {'question','engine','areas','signals','passages','source','backfill'}},
                    result, run_id=ident, cached=bool(result.get('cache_hit')))
                result = {**result, 'run_receipt': receipt}
                await ledger.conn.execute('''INSERT INTO agent_market_lab.executions(tenant_id,job_id,result)
                    VALUES($1,$2,$3::jsonb) ON CONFLICT DO NOTHING''', owner, job, json.dumps(result))
            finally:
                active_ledger.reset(token)
                after_commit.reset(effect_token)
        for callback in effects:
            try:
                async with asyncio.timeout(10):
                    await callback()
            except Exception as exc:
                logging.getLogger('agent').warning('Job notification unavailable (%s)', type(exc).__name__)
        return result
    return run
