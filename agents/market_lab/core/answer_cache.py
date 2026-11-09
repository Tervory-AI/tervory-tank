"""Exact questions, private sources and fresh prediction gates define cache reuse."""
import asyncio
import copy
import hashlib
import json
import os
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID
from weakref import WeakValueDictionary

from core.documents import records
from core.evidence import gated_facts, latest_checks

_locks = WeakValueDictionary()


def key(question, engine):
    return hashlib.sha256(json.dumps([question.strip(), engine], ensure_ascii=False).encode()).hexdigest()


@asynccontextmanager
async def flight(tenant, question, engine):
    ident = (tenant, key(question, engine))
    lock = _locks.setdefault(ident, asyncio.Lock())
    await asyncio.wait_for(lock.acquire(), timeout=180)
    try:
        yield
    finally:
        lock.release()


async def generation(ledger, tenant):
    checks = await latest_checks(ledger, tenant)
    uploads = await records(ledger, tenant)
    if hasattr(ledger, 'conn'):
        batches = [dict(r) for r in await ledger.conn.fetch('SELECT id,status FROM agent_market_lab.batches WHERE tenant_id=$1 ORDER BY id', UUID(tenant))]
    else:
        batches = {k: v for k, v in getattr(getattr(ledger, 'pool', None), 'batches', {}).items()
                   if str(v.get('tenant_id')) == tenant}
    return hashlib.sha256(json.dumps([checks, uploads, batches], sort_keys=True, default=str).encode()).hexdigest()


async def get(ledger, tenant, question, engine):
    cache_key = key(question, engine)
    if hasattr(ledger, 'conn'):
        row = await ledger.conn.fetchrow('SELECT generation,result FROM agent_market_lab.answer_cache WHERE tenant_id=$1 AND cache_key=$2 AND expires_at>now()', UUID(tenant), cache_key)
        value = dict(row) if row else None
        if value and isinstance(value['result'], str):
            value['result'] = json.loads(value['result'])
    else:
        value = copy.deepcopy(getattr(ledger, 'answer_cache', {}).get((tenant, cache_key)))
        if value and value['expires_at'] <= datetime.now(UTC):
            value = None
    if not value or value['generation'] != await generation(ledger, tenant):
        return None
    result = value['result']
    if await gated_facts(ledger, tenant, result.get('facts', [])) != result.get('facts', []):
        return None
    return copy.deepcopy(result)


async def put(ledger, tenant, question, engine, result):
    if not result.get('facts'):
        return
    try:
        ttl = max(0, int(os.environ.get('TANK_CACHE_TTL_S', str(7*24*3600))))
    except ValueError:
        ttl = 7*24*3600
    clean = {k: copy.deepcopy(result[k]) for k in ('content','facts','sources','report_id','answer','citations') if k in result}
    # Public feeds already refresh daily; never retain a web answer longer than
    # that cadence, even when Tank's general model-cache window is longer.
    stamp = datetime.now(UTC) + timedelta(seconds=min(ttl, 24*3600))
    version = await generation(ledger, tenant)
    if hasattr(ledger, 'conn'):
        await ledger.conn.execute('''INSERT INTO agent_market_lab.answer_cache(tenant_id,cache_key,generation,expires_at,result)
            VALUES($1,$2,$3,$4,$5::jsonb) ON CONFLICT(tenant_id,cache_key) DO UPDATE
            SET generation=excluded.generation,expires_at=excluded.expires_at,result=excluded.result''',
            UUID(tenant), key(question,engine), version, stamp, json.dumps(clean))
    else:
        ledger.answer_cache = getattr(ledger, 'answer_cache', {})
        ledger.answer_cache[(tenant,key(question,engine))] = {'generation':version,'result':clean,'expires_at':stamp}
