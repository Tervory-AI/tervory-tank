"""Founder-only, tenant-scoped evidence and exports. No prompts or secrets."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from decimal import Decimal
from io import StringIO
import json
from typing import Any
import uuid

from fastapi import APIRouter, Depends, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import Response

from admin import require_admin
from gold import runtime

router = APIRouter(prefix='/v1/proof', dependencies=[Depends(require_admin)])


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0))


# Identical predicates drive SQL totals and the paged receipts.
LIVE = "agent NOT IN ('bench','shadow') AND task_type NOT LIKE '%#shadow'"
SCOPE = "($1::uuid IS NULL OR tenant_id=$1) AND region=$2 AND ($3::text IS NULL OR task_type=$3)"
WINDOW = "($4::timestamptz IS NULL OR ts >= $4) AND ts < $5"
TOTALS = """count(*)::int AS calls,
    count(baseline_cost_usd)::int AS priced_calls,
    coalesce(sum(cost_usd) FILTER (WHERE baseline_cost_usd IS NOT NULL),0) AS actual_usd,
    coalesce(sum(baseline_cost_usd),0) AS baseline_usd,
    coalesce(sum(baseline_cost_usd-cost_usd),0) AS saved_usd,
    count(*) FILTER (WHERE baseline_status='backfilled' AND baseline_cost_usd IS NOT NULL)::int AS backfilled_calls,
    count(*) FILTER (WHERE baseline_cost_usd IS NULL)::int AS unpriced_calls,
    count(*) FILTER (WHERE rung=3 AND NOT cache_hit AND cost_usd=0 AND outcome='delivered')::int AS code_calls"""
PAGE_SIZE = 100


async def snapshot(tenant: uuid.UUID | None, task: str | None = None,
                   start: datetime | None = None, end: datetime | None = None, page: int = 0) -> dict:
    region = runtime().box_region()
    end = end or datetime.now(timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    end = end.astimezone(timezone.utc)
    if start and start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if start:
        start = start.astimezone(timezone.utc)
    if start and start >= end:
        from fastapi import HTTPException
        raise HTTPException(422, 'Start must precede end.')
    args = (tenant, region, task, start, end)
    where = f"{SCOPE} AND {WINDOW} AND {LIVE}"
    async with runtime().pool().acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        tasks = [dict(r) for r in await conn.fetch(f"SELECT task_type,{TOTALS} FROM tank.ledger WHERE {where} GROUP BY task_type ORDER BY task_type", *args)]
        all_total = dict(await conn.fetchrow(f"SELECT {TOTALS} FROM tank.ledger WHERE region=$1 AND ts < $2 AND {LIVE}", region, end))
        tenants = [str(r['tenant_id']) for r in await conn.fetch('SELECT DISTINCT tenant_id FROM tank.ledger WHERE region=$1 ORDER BY tenant_id', region)]
        ledger = [dict(r) for r in await conn.fetch(f"""SELECT l.id,l.tenant_id,l.ts,l.task_type,l.agent,l.model,l.rung,l.tokens_in,l.tokens_out,
            l.cost_usd,l.baseline_model,l.baseline_cost_usd,l.baseline_status,l.baseline_priced_at,l.cache_hit,l.outcome,
            l.baseline_cost_usd-l.cost_usd AS saved_usd,
            l.baseline_cost_usd < l.cost_usd AS baseline_below_actual,
            (SELECT a.family<>b.family FROM tank.proof_prices a,tank.proof_prices b
             WHERE a.model=l.model AND b.model=l.baseline_model) AS baseline_family_mismatch
            FROM tank.ledger l WHERE {where} ORDER BY ts DESC,id DESC LIMIT $6 OFFSET $7""", *args, PAGE_SIZE+1, page*PAGE_SIZE)]
        shadow_from = """FROM tank.shadow s JOIN tank.ledger l ON l.id=s.ledger_id AND l.tenant_id=s.tenant_id
            WHERE ($1::uuid IS NULL OR s.tenant_id=$1) AND l.region=$2 AND ($3::text IS NULL OR s.task_type=$3)
            AND ($4::timestamptz IS NULL OR l.ts >= $4) AND l.ts < $5"""
        comparisons = [dict(r) for r in await conn.fetch("""SELECT s.task_type,s.primary_model,s.candidate_model,
            count(*)::int AS samples,avg(s.agreement) AS agreement,sum(s.primary_cost_usd) AS primary_cost_usd,
            sum(s.candidate_cost_usd) AS could_have_cost_usd """+shadow_from+" GROUP BY s.task_type,s.primary_model,s.candidate_model", *args)]
        shadows = [dict(r) for r in await conn.fetch("""SELECT s.id,s.tenant_id,s.ledger_id,s.task_type,s.primary_model,s.candidate_model,
            s.primary_cost_usd,s.candidate_cost_usd,s.agreement,s.method,s.created_at """+shadow_from+
            " ORDER BY l.ts DESC,s.id DESC LIMIT $6 OFFSET $7", *args, PAGE_SIZE+1, page*PAGE_SIZE)]
        runs = [dict(r) for r in await conn.fetch(f"""SELECT id,tenant_id,task_type,model,comparison_model,suite_hash,expected_n,
            score,cost_per_call,status,error,started_at,finished_at FROM tank.bench_runs
            WHERE {SCOPE} AND ($4::timestamptz IS NULL OR started_at >= $4) AND started_at < $5
            ORDER BY started_at DESC,id DESC LIMIT $6 OFFSET $7""", *args, PAGE_SIZE+1, page*PAGE_SIZE)]
        cases = [dict(r) for r in await conn.fetch("""SELECT c.id,c.tenant_id,c.run_id,r.task_type,r.model,c.case_ref,c.case_kind,
            c.ledger_id,c.score,c.reserved_usd,c.charged_usd,c.status,c.created_at,
            l.cost_usd,l.tokens_in,l.tokens_out,l.outcome
            FROM tank.bench_calls c JOIN tank.bench_runs r ON r.id=c.run_id AND r.tenant_id=c.tenant_id AND r.region=c.region
            LEFT JOIN tank.ledger l ON l.id=c.ledger_id AND l.tenant_id=c.tenant_id AND l.region=c.region
            WHERE ($1::uuid IS NULL OR c.tenant_id=$1) AND c.region=$2 AND ($3::text IS NULL OR r.task_type=$3)
            AND ($4::timestamptz IS NULL OR c.created_at >= $4) AND c.created_at < $5
            ORDER BY c.created_at DESC,c.id DESC LIMIT $6 OFFSET $7""", *args, PAGE_SIZE+1, page*PAGE_SIZE)]
        policies = [dict(r) for r in await conn.fetch("""SELECT tenant_id,task_type,model,candidate_model,baseline_model,auto_promote
            FROM tank.policy WHERE ($1::uuid IS NULL OR tenant_id=$1 OR tenant_id IS NULL) AND ($2::text IS NULL OR task_type=$2)
            ORDER BY task_type,tenant_id NULLS LAST""", tenant, task)]
        promotions = [dict(r) for r in await conn.fetch("""SELECT id,task_type,action,from_model,to_model,created_at
            FROM tank.policy_log WHERE action IN ('promote','rollback') AND ($1::text IS NULL OR task_type=$1)
            AND ($2::timestamptz IS NULL OR created_at >= $2) AND created_at < $3
            ORDER BY created_at DESC,id DESC LIMIT $4 OFFSET $5""", task, start, end, PAGE_SIZE+1, page*PAGE_SIZE)]
        state = [dict(r) for r in await conn.fetch("""SELECT task_type,bench_at,bench_status,bench_error FROM tank.search_state
            WHERE ($1::text IS NULL OR task_type=$1) ORDER BY task_type""", task)]
    by_task = {r['task_type']: r for r in tasks}
    for name in sorted({r['task_type'] for group in (comparisons,runs,policies) for r in group} - by_task.keys()):
        row = dict(task_type=name, calls=0, priced_calls=0,actual_usd=0,baseline_usd=0,saved_usd=0,backfilled_calls=0,unpriced_calls=0,code_calls=0)
        tasks.append(row)
    for row in tasks:
        row['code_share'] = row['code_calls']/row['calls'] if row['calls'] else None
        row['shadow_pairs'] = [p for p in comparisons if p['task_type']==row['task_type']]
    sections = dict(ledger=ledger,shadows=shadows,runs=runs,cases=cases,promotions=promotions)
    more = {name: len(rows)>PAGE_SIZE for name,rows in sections.items()}
    page_rows = ledger[:PAGE_SIZE]
    return jsonable_encoder({'tenant_id': str(tenant) if tenant else 'all', 'region': region,
        'tenants': tenants, 'all_tenant_total': all_total, 'tasks': tasks,
        **{name: rows[:PAGE_SIZE] for name,rows in sections.items()}, 'policies': policies, 'state': state,
        'window': {'start': start, 'end': end}, 'page': page, 'page_size': PAGE_SIZE, 'has_more': more,
        'receipt_page_total': {'calls':len(page_rows), 'saved_usd':sum((money(r['saved_usd']) for r in page_rows),Decimal(0))}})


@router.get('')
async def proof(tenant_id: uuid.UUID | None = None, task: str | None = Query(default=None, max_length=200),
                start: datetime | None = None, end: datetime | None = None, page: int = Query(default=0, ge=0, le=100000)) -> dict:
    return await snapshot(tenant_id, task, start, end, page)


def csv_export(data: dict) -> str:
    stream = StringIO(newline='')
    writer = csv.writer(stream)
    writer.writerow(['section', 'tenant_id', 'region', 'task_type', 'row_id', 'field', 'value'])
    for section in ('metadata','tasks','ledger','shadows','runs','cases','promotions','policies','state'):
        for row in ([{k:v for k,v in data.items() if k not in ('tasks','ledger','shadows','runs','cases','promotions','policies','state')}] if section=='metadata' else data[section]):
            for key, value in row.items():
                if isinstance(value, (list,dict)):
                    value = json.dumps(value, sort_keys=True)
                # Spreadsheet formula injection protection for all text cells.
                cells = [section, row.get('tenant_id',data['tenant_id']), data['region'], row.get('task_type',''), row.get('id',''), key, '' if value is None else str(value)]
                writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in cells])
    return stream.getvalue()


def pdf_export(data: dict) -> bytes:
    """Small, dependency-free, paginated PDF containing totals and the selected evidence page."""
    import textwrap
    lines = ['Tervory | Tank proof', f"Region: {data['region']}  Tenant: {data['tenant_id']}",
             'Savings = priced baseline - actual. Backfilled rows use the current price book.',
             'Code excludes cache. Benchmark/shadow costs are separate from live savings.',
             'Totals cover the selected time window. Evidence contains the selected page only.']
    for section in ('metadata','tasks','ledger','shadows','runs','cases','promotions','policies','state'):
        lines.append(section.upper())
        for row in ([{k:v for k,v in data.items() if k not in ('tasks','ledger','shadows','runs','cases','promotions','policies','state')}] if section=='metadata' else data[section]):
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
async def export(format: str, tenant_id: uuid.UUID | None = None, task: str | None = Query(default=None, max_length=200),
                 start: datetime | None = None, end: datetime | None = None, page: int = Query(default=0, ge=0, le=100000)) -> Response:
    from fastapi import HTTPException
    if format not in ('csv','pdf'):
        raise HTTPException(404, 'not found')
    data = await snapshot(tenant_id, task, start, end, page)
    content = csv_export(data) if format=='csv' else pdf_export(data)
    return Response(content, media_type='text/csv' if format=='csv' else 'application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="tank-proof.{format}"', 'Cache-Control': 'no-store'})
