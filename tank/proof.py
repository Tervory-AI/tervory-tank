"""Founder-only, tenant-scoped evidence and exports. No prompts or secrets."""
from __future__ import annotations

import csv
from decimal import Decimal
from io import StringIO
import json
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

from admin import require_admin
from gold import PLATFORM_TENANT, runtime

router = APIRouter(prefix='/v1/proof', dependencies=[Depends(require_admin)])


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0))


def summarize(ledger: list[dict], shadows: list[dict], runs: list[dict], policies: list[dict]) -> list[dict]:
    tasks = sorted({r['task_type'] for group in (ledger, shadows, runs, policies) for r in group})
    result = []
    for task in tasks:
        # Benchmark/shadow costs are reported separately, never credited as client savings.
        calls = [r for r in ledger if r['task_type']==task and r['agent'] not in ('bench','shadow') and not r['task_type'].endswith('#shadow')]
        priced = [r for r in calls if r['baseline_cost_usd'] is not None]
        actual = sum((money(r['cost_usd']) for r in priced), Decimal(0))
        baseline = sum((money(r['baseline_cost_usd']) for r in priced), Decimal(0))
        pairs = [r for r in shadows if r['task_type']==task]
        groups = {}
        for row in pairs:
            key = (row['primary_model'], row['candidate_model'])
            groups.setdefault(key, []).append(row)
        comparisons = []
        for (primary, candidate), rows in groups.items():
            judged = [money(r['agreement']) for r in rows if r['agreement'] is not None]
            comparisons.append({'primary_model': primary, 'candidate_model': candidate, 'samples': len(rows),
                'agreement': sum(judged)/len(judged) if judged else None,
                'primary_cost_usd': sum((money(r['primary_cost_usd']) for r in rows), Decimal(0)),
                'could_have_cost_usd': sum((money(r['candidate_cost_usd']) for r in rows), Decimal(0)),
                'row_ids': [str(r['id']) for r in rows]})
        result.append({'task_type': task, 'calls': len(calls), 'priced_calls': len(priced),
            'actual_usd': actual, 'baseline_usd': baseline, 'saved_usd': baseline-actual,
            'backfilled_calls': sum(r['baseline_status']=='backfilled' for r in priced),
            'unpriced_calls': len(calls)-len(priced),
            'code_calls': sum(r['rung']==3 and not r['cache_hit'] and money(r['cost_usd'])==0 and r['outcome']=='delivered' for r in calls),
            'code_share': sum(r['rung']==3 and not r['cache_hit'] and money(r['cost_usd'])==0 and r['outcome']=='delivered' for r in calls)/len(calls) if calls else None,
            'shadow_pairs': comparisons})
    return result


async def snapshot(tenant: uuid.UUID, task: str | None = None) -> dict:
    region = runtime().box_region()
    async with runtime().pool().acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        ledger = [dict(r) for r in await conn.fetch('''SELECT id,ts,task_type,agent,model,rung,tokens_in,tokens_out,
            cost_usd,baseline_model,baseline_cost_usd,baseline_status,baseline_priced_at,cache_hit,outcome,
            baseline_cost_usd-cost_usd AS saved_usd FROM tank.ledger
            WHERE tenant_id=$1 AND region=$2 AND ($3::text IS NULL OR task_type=$3) ORDER BY ts DESC,id''', tenant, region, task)]
        shadows = [dict(r) for r in await conn.fetch('''SELECT s.id,s.ledger_id,s.task_type,s.primary_model,s.candidate_model,
            s.primary_cost_usd,s.candidate_cost_usd,s.agreement,s.method,s.created_at
            FROM tank.shadow s JOIN tank.ledger l ON l.id=s.ledger_id AND l.tenant_id=s.tenant_id
            WHERE s.tenant_id=$1 AND l.region=$2 AND ($3::text IS NULL OR s.task_type=$3) ORDER BY s.created_at DESC,s.id''', tenant, region, task)]
        runs = [dict(r) for r in await conn.fetch('''SELECT id,task_type,model,comparison_model,suite_hash,expected_n,
            score,cost_per_call,status,error,started_at,finished_at FROM tank.bench_runs
            WHERE tenant_id=$1 AND region=$2 AND ($3::text IS NULL OR task_type=$3) ORDER BY started_at DESC,id''', tenant, region, task)]
        cases = [dict(r) for r in await conn.fetch('''SELECT c.id,c.run_id,r.task_type,r.model,c.case_ref,c.case_kind,
            c.ledger_id,c.score,c.reserved_usd,c.charged_usd,c.status,c.created_at FROM tank.bench_calls c
            JOIN tank.bench_runs r ON r.id=c.run_id AND r.tenant_id=c.tenant_id AND r.region=c.region
            WHERE c.tenant_id=$1 AND c.region=$2 AND ($3::text IS NULL OR r.task_type=$3) ORDER BY c.created_at DESC,c.id''', tenant, region, task)]
        policies = [dict(r) for r in await conn.fetch('''SELECT DISTINCT ON(task_type) task_type,model,candidate_model,baseline_model,auto_promote
            FROM tank.policy WHERE (tenant_id=$1 OR tenant_id IS NULL) AND ($2::text IS NULL OR task_type=$2)
            ORDER BY task_type,tenant_id NULLS LAST''', tenant, task)]
        # Legacy policy history contains only global policies. No tenant rows are joined.
        promotions = [dict(r) for r in await conn.fetch('''SELECT id,task_type,action,from_model,to_model,created_at
            FROM tank.policy_log WHERE action IN ('promote','rollback') AND ($1::text IS NULL OR task_type=$1)
            ORDER BY created_at DESC,id''', task)]
        state = [dict(r) for r in await conn.fetch('''SELECT task_type,bench_at,bench_status,bench_error FROM tank.search_state
            WHERE ($1::text IS NULL OR task_type=$1) ORDER BY task_type''', task)]
    return jsonable_encoder({'tenant_id': str(tenant), 'region': region,
        'tasks': summarize(ledger, shadows, runs, policies), 'ledger': ledger,
        'shadows': shadows, 'runs': runs, 'cases': cases, 'promotions': promotions, 'policies': policies, 'state': state})


@router.get('')
async def proof(tenant_id: uuid.UUID = PLATFORM_TENANT, task: str | None = Query(default=None, max_length=200)) -> dict:
    return await snapshot(tenant_id, task)


def csv_export(data: dict) -> str:
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['section', 'tenant_id', 'region', 'task_type', 'row_id', 'field', 'value'])
    for section in ('tasks','ledger','shadows','runs','cases','promotions','policies','state'):
        for row in data[section]:
            for key, value in row.items():
                if isinstance(value, (list,dict)):
                    value = json.dumps(value, sort_keys=True)
                # Spreadsheet formula injection protection for all text cells.
                cells = [section, data['tenant_id'], data['region'], row.get('task_type',''), row.get('id',''), key, '' if value is None else str(value)]
                writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in cells])
    return stream.getvalue()


def pdf_export(data: dict) -> bytes:
    """Small, dependency-free, paginated PDF containing summaries and every evidence row."""
    import textwrap
    lines = ['Tervory | Tank proof', f"Region: {data['region']}  Tenant: {data['tenant_id']}",
             'Savings = priced baseline - actual. Backfilled rows use the current price book.',
             'Code excludes cache. Benchmark/shadow costs are separate from live savings.']
    for section in ('tasks','ledger','shadows','runs','cases','promotions','policies','state'):
        lines.append(section.upper())
        for row in data[section]:
            lines.extend(textwrap.wrap(json.dumps(row, sort_keys=True), width=110) or [''])
    chunks = [lines[i:i+50] for i in range(0,len(lines),50)]
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>']
    pages = []
    for chunk in chunks:
        page_id = len(objects)+1
        pages.append(page_id)
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {page_id+1} 0 R >>'.encode())
        escaped = [line.replace('\\','\\\\').replace('(','\\(').replace(')','\\)') for line in chunk]
        stream = ('BT /F1 8 Tf 32 760 Td 14 TL '+ ' T* '.join('('+s+') Tj' for s in escaped) +' ET').encode('latin-1',errors='replace')
        objects.append(f'<< /Length {len(stream)} >>\nstream\n'.encode()+stream+b'\nendstream')
    objects[1] = f"<< /Type /Pages /Count {len(pages)} /Kids [{' '.join(f'{p} 0 R' for p in pages)}] >>".encode()
    result = bytearray(b'%PDF-1.4\n')
    offsets = [0]
    for i, item in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f'{i} 0 obj\n'.encode()+item+b'\nendobj\n')
    start = len(result)
    result.extend(f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode())
    result.extend(''.join(f'{offset:010d} 00000 n \n' for offset in offsets[1:]).encode())
    result.extend(f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
    return bytes(result)


@router.get('/export/{format}')
async def export(format: str, tenant_id: uuid.UUID = PLATFORM_TENANT, task: str | None = Query(default=None, max_length=200)) -> Response:
    from fastapi import HTTPException
    if format not in ('csv','pdf'):
        raise HTTPException(404, 'not found')
    data = await snapshot(tenant_id, task)
    content = csv_export(data) if format=='csv' else pdf_export(data)
    return Response(content, media_type='text/csv' if format=='csv' else 'application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="tank-proof.{format}"', 'Cache-Control': 'no-store'})
