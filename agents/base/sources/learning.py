"""Keep vendor answers separate from official truth and serving profiles."""
from __future__ import annotations

from datetime import date
import json
import uuid

from base_gold.gold_sources import _host, _text
from sources.vendor_ledger import PLATFORM_TENANT, decoded


def value(profile, key):
    found = profile.get(key)
    return found.get('value') if isinstance(found, dict) else found


def lesson(raw, code, vendor, truth, source, *, region, observed_on):
    result = {'code': code, 'vendor': vendor, 'official': truth, 'label_source': source,
              'status': 'unverified', 'candidates': []}
    if vendor.get('status') != 'candidate' or not truth or not source:
        return result
    fields = vendor.get('fields') or {}
    for key in fields.keys() & truth.keys():
        normalize = _host if key == 'website' else _text
        if not normalize(fields[key]) or normalize(fields[key]) != normalize(truth[key]):
            result['status'] = 'disagrees'
            return result
    site = fields.get('website')
    if not site or not _host(site) or _host(site) != _host(truth.get('website')):
        return result
    result['status'] = 'checked'
    if not value(code, 'website'):
        identity = {key: value(code, key) or raw.get(key) or raw.get('premise_' + key, '')
                    for key in ('name', 'address', 'city', 'state', 'zip')}
        identity['name'] = identity['name'] or raw.get('business_name') or raw.get('license_name', '')
        if identity['name']:
            result['candidates'] = [{
                'skill_id': 'base.find_site', 'input': identity,
                'expected': {'website': {'value': site.rstrip('/')}}, 'region': region,
                'public': True, 'needs_network': True,
                'label_family': 'context-dev:base.find_site:' + date.fromisoformat(observed_on).strftime('%Y-%m'),
                'label_source': source,
            }]
    return result


async def save_lesson(conn, tenant, run, record, vendor):
    row = await conn.fetchrow(
        "SELECT raw,profile,passes->'context_dev_learning' AS learning FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 AND id=$3",
        tenant, run, uuid.UUID(record['record_id']))
    if row is None:
        raise ValueError('learning record not found in this batch')
    if row.get('learning') is not None:
        return decoded(row['learning'])
    import os
    learned = lesson(decoded(row['raw']), decoded(row['profile']), vendor,
                     record.get('checked_answers') or {}, record.get('label_source'),
                     region=os.environ.get('TANK_REGION', 'us-east'),
                     observed_on=vendor.get('observed_on') or date.today().isoformat())
    await conn.execute(
        "UPDATE agent_base.records SET passes=jsonb_set(passes,'{context_dev_learning}',$4::jsonb),updated_at=now() "
        'WHERE tenant_id=$1 AND task_id=$2 AND id=$3',
        tenant, run, uuid.UUID(record['record_id']), json.dumps(learned))
    return learned


async def read_lessons(pool, limit, region):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT passes->'context_dev_learning' AS lesson FROM agent_base.records "
            "WHERE tenant_id=$1 AND passes->'context_dev_learning'->>'status'='checked' "
            'ORDER BY updated_at DESC,id LIMIT $2', uuid.UUID(PLATFORM_TENANT), limit)
    result = []
    for row in rows:
        for candidate in decoded(row['lesson']).get('candidates', []):
            if candidate.get('region') == region:
                result.append(candidate)
    return result[:limit]
