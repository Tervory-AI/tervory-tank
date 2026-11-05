"""Run the existing approved vendor rung only after a public code batch finishes."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from decimal import Decimal

from pipeline import val
from sources.trial import run_trial
from sources.trial_selection import official_truth, select_records
from sources.vendor_ledger import PLATFORM_TENANT, decoded


def has_gaps(profile):
    return (not val(profile, 'website') or not (val(profile, 'phones') or val(profile, 'phone')
            or val(profile, 'emails')) or not val(profile, 'categories'))


async def run_gaps(pool, http, tenant_id, run_id):
    if str(tenant_id) != PLATFORM_TENANT or not os.environ.get('CONTEXT_DEV_API_KEY'):
        return {'status': 'not_configured', 'records_sent': 0, 'lessons': 0}
    tenant, run = uuid.UUID(str(tenant_id)), uuid.UUID(str(run_id))
    async with pool.acquire() as conn:
        if await conn.fetchval('SELECT 1 FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2 AND status=\'done\'', tenant, run) != 1:
            return {'status': 'code_pending', 'records_sent': 0, 'lessons': 0}
        rows = await conn.fetch(
            'SELECT id,raw,profile FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 '
            "AND status='done' ORDER BY created_at,id", tenant, run)
    from engines.ffl.atf_gold import licence_id
    public = [row for row in rows if licence_id(decoded(row['raw'])) and has_gaps(decoded(row['profile']))]
    truth = await asyncio.to_thread(official_truth)
    receipt = {'status': 'done', 'records_sent': 0, 'lessons': 0, 'credits': 0,
               'code_records': len(rows), 'vendor_records': 0,
               'cost_usd': None, 'unpriced_calls': 0}
    cost, charged = Decimal(0), 0
    for offset in range(0, len(public), 50):
        selected = select_records(public[offset:offset + 50], truth)
        if not selected:
            continue
        result = await run_trial(pool, http, str(tenant), str(run), selected)
        receipt['records_sent'] += result['records_sent']
        for record in result['results']:
            receipt['lessons'] += record.get('lessons', 0)
            receipt['vendor_records'] += record.get('status') == 'candidate'
            units = record.get('credits')
            if isinstance(units, (int, float)) and not isinstance(units, bool):
                receipt['credits'] += units
            entry = record.get('receipt') or {}
            if record.get('status') in ('candidate', 'failed', 'transport_error', 'unknown'):
                charged += 1
                if entry.get('cost_status') != 'set' or entry.get('cost_usd') is None:
                    receipt['unpriced_calls'] += 1
                else:
                    cost += Decimal(entry['cost_usd'])
        if result.get('status') == 'credit_limit':
            receipt['status'] = 'credit_limit'
            break
    receipt['cost_usd'] = str(cost) if charged and not receipt['unpriced_calls'] else None
    return receipt


async def finish_context(pool, http, task_id, cfg):
    if cfg['tenant_id'] != PLATFORM_TENANT or not os.environ.get('CONTEXT_DEV_API_KEY'):
        return
    tenant = uuid.UUID(cfg['tenant_id'])
    cfg['context_pending'] = True
    async with pool.acquire() as conn:
        await conn.execute('UPDATE agent_base.tasks SET input=$3::jsonb WHERE id=$1 AND tenant_id=$2',
                           task_id, tenant, json.dumps(cfg))
    receipt = await run_gaps(pool, http, tenant, task_id)
    receipt['pipeline_model_spend'] = cfg.get('model_spend')
    cfg['context_receipt'] = receipt
    cfg.pop('context_pending', None)
    async with pool.acquire() as conn:
        await conn.execute('UPDATE agent_base.tasks SET input=$3::jsonb WHERE id=$1 AND tenant_id=$2',
                           task_id, tenant, json.dumps(cfg))
