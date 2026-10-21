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
    coalesce(sum(cost_usd) FILTER (WHERE research_cost_status IS DISTINCT FROM 'unknown'),0) AS actual_usd,
    coalesce(sum(cost_usd) FILTER (WHERE baseline_cost_usd IS NOT NULL),0) AS compared_actual_usd,
    count(*) FILTER (WHERE research_cost_status='unknown')::int AS unknown_cost_calls,
    coalesce(sum(baseline_cost_usd),0) AS baseline_usd,
    coalesce(sum(baseline_cost_usd-cost_usd),0) AS saved_usd,
    count(*) FILTER (WHERE baseline_status='backfilled' AND baseline_cost_usd IS NOT NULL)::int AS backfilled_calls,
    count(*) FILTER (WHERE baseline_cost_usd IS NULL)::int AS unpriced_calls,
    count(*) FILTER (WHERE rung=3 AND NOT cache_hit AND cost_usd=0 AND outcome='delivered' AND research_cost_status IS DISTINCT FROM 'unknown')::int AS code_calls"""
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
            CASE WHEN l.research_cost_status='unknown' THEN NULL ELSE l.cost_usd END AS cost_usd,l.research_cost_status,l.baseline_model,l.baseline_cost_usd,l.baseline_status,l.baseline_priced_at,l.cache_hit,l.outcome,
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
        row = dict(task_type=name, calls=0, priced_calls=0,actual_usd=0,compared_actual_usd=0,unknown_cost_calls=0,baseline_usd=0,saved_usd=0,backfilled_calls=0,unpriced_calls=0,code_calls=0)
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
                cells = [section, row.get('tenant_id',data['tenant_id']), data['region'], row.get('task_type',''), row.get('id',''), key, '' if value is None else value]
                writer.writerow(["'"+v if isinstance(v,str) and v.startswith(('=','+','-','@','\t','\r')) else v for v in cells])
    return stream.getvalue()


def pdf_export(data: dict) -> bytes:
    """Small, dependency-free, paginated PDF containing totals and the selected evidence page."""
    import textwrap
    lines = ['Tervory | Tank proof', f"Region: {data['region']}  Tenant: {data['tenant_id']}",
             'Savings = priced baseline - actual. Backfilled rows use the current price book.',
             'Code excludes cache. Benchmark/shadow costs are separate from live savings.',
             'Totals cover the selected time window. Evidence contains the selected page only.']
    if data.get('description'):
        lines = ['Tervory | Client savings', f"Region: {data['region']}  Client: {data['tenant_id']}",
                 data['description'], 'Free work includes tools and reused answers with verified zero cost.',
                 'No billing data yet: no payment or margin is inferred.']
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


# CORE-2: a single, conservative population powers graphs and their drill-downs.
# A job link is required so every amount can be explained without exposing call IDs.
# No-token tools/cache can prove zero cost without a model-family comparison.
SAVINGS_CTE = """WITH linked AS (
    SELECT l.*, t.id AS job_id, t.title AS job_title,
      (l.cost_usd=0 AND l.tokens_in=0 AND l.tokens_out=0
       AND (l.rung=3 OR l.cache_hit) AND l.outcome='delivered') AS free_work,
      a.family AS actual_family, b.family AS baseline_family
    FROM tank.ledger l
    LEFT JOIN tank.proof_prices a ON a.model=l.model
    LEFT JOIN tank.proof_prices b ON b.model=l.baseline_model
    LEFT JOIN LATERAL (SELECT id,title FROM tank.tasks t
      WHERE t.tenant_id=l.tenant_id AND t.status='done' AND t.finished_at < $3
        AND (t.id=l.task_id OR t.ledger_id=l.id)
      ORDER BY (t.id=l.task_id) DESC NULLS LAST,t.id LIMIT 1) t ON true
    WHERE ($1::uuid IS NULL OR l.tenant_id=$1) AND l.region=$2 AND l.ts < $3
      AND l.agent NOT IN ('bench','shadow') AND l.task_type NOT LIKE '%#shadow'
), checked AS (
    SELECT *, CASE
      WHEN research_cost_status='unknown' THEN 'Unknown actual cost'
      WHEN vendor IS NOT NULL OR model LIKE 'vendor:%' THEN 'Fee without a comparable baseline'
      WHEN baseline_cost_usd IS NULL OR baseline_status NOT IN ('measured','backfilled','no_tokens')
        THEN 'Unknown baseline'
      WHEN baseline_priced_at > $3 THEN 'Comparison checked after this snapshot'
      WHEN cost_usd < 0 OR baseline_cost_usd < cost_usd THEN 'Baseline below actual cost'
      WHEN actual_family IS NOT NULL AND baseline_family IS NOT NULL AND actual_family<>baseline_family
        THEN 'Different model family'
      WHEN NOT (free_work AND baseline_cost_usd=0) AND (actual_family IS NULL OR baseline_family IS NULL)
        THEN 'Unknown model family'
      WHEN outcome <> 'delivered' THEN 'Work not delivered'
      WHEN job_id IS NULL THEN 'No linked job'
      ELSE NULL END AS excluded_reason,
      CASE agent WHEN 'base' THEN 'Base' WHEN 'tiger' THEN 'Tiger'
        WHEN 'market_lab' THEN 'Market Lab' WHEN 'market-lab' THEN 'Market Lab'
        WHEN 'zenas' THEN 'Zenas' WHEN 'rig' THEN 'Rig' WHEN 'tisan' THEN 'Tisan'
        WHEN 'radix' THEN 'Radix' ELSE 'Other work' END AS member
    FROM linked
), eligible AS (SELECT * FROM checked WHERE excluded_reason IS NULL) """
SAVINGS_TOTALS = """count(*)::int AS work_count, count(DISTINCT job_id)::int AS jobs_count,
    coalesce(sum(cost_usd),0) AS spent, coalesce(sum(baseline_cost_usd),0) AS would_have_cost,
    coalesce(sum(baseline_cost_usd-cost_usd),0) AS saved,
    count(*) FILTER (WHERE free_work)::int AS free_count"""


def savings_encoded(value: Any) -> Any:
    # Decimal strings preserve the receipt precision through JSON and exports.
    return jsonable_encoder(value, custom_encoder={Decimal: str})


def savings_end(end: datetime | None) -> datetime:
    from fastapi import HTTPException
    now = datetime.now(timezone.utc)
    end = end or now
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    end = end.astimezone(timezone.utc)
    if end > now:
        raise HTTPException(422, 'End cannot be in the future.')
    return end


async def savings_snapshot(tenant: uuid.UUID | None, end: datetime | None = None,
                           founder: bool = False) -> dict:
    end = savings_end(end)
    args = (tenant, runtime().box_region(), end)
    async with runtime().pool().acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        total = dict(await conn.fetchrow(SAVINGS_CTE+f'SELECT {SAVINGS_TOTALS} FROM eligible', *args))
        month = dict(await conn.fetchrow(SAVINGS_CTE+f"SELECT {SAVINGS_TOTALS} FROM eligible WHERE ts >= $4",
                                        *args, end.replace(day=1,hour=0,minute=0,second=0,microsecond=0)))
        daily = [dict(r) for r in await conn.fetch(SAVINGS_CTE+f"""SELECT (ts AT TIME ZONE 'UTC')::date::text AS day,
            {SAVINGS_TOTALS}, sum(sum(baseline_cost_usd-cost_usd)) OVER (ORDER BY (ts AT TIME ZONE 'UTC')::date) AS cumulative
            FROM eligible GROUP BY (ts AT TIME ZONE 'UTC')::date ORDER BY day""", *args)]
        members = [dict(r) for r in await conn.fetch(SAVINGS_CTE+f'SELECT member,{SAVINGS_TOTALS} FROM eligible GROUP BY member ORDER BY member', *args)]
        revision = await conn.fetchrow('SELECT count(*) AS n,max(finished_at) AS last FROM tank.tasks WHERE ($1::uuid IS NULL OR tenant_id=$1) AND finished_at IS NOT NULL', tenant)
        data = dict(as_of=end, total=total, month=month, daily=daily, members=members, revision=f"{revision['n']}:{revision['last']}")
        if founder:
            # No payment amount is stored in billing_events. A price-book rate is
            # not proof of payment, so neither paid nor margin can be inferred.
            cost_totals = """coalesce(sum(cost_usd) FILTER (WHERE research_cost_status IS DISTINCT FROM 'unknown'),0) AS actual,
                count(*) FILTER (WHERE research_cost_status='unknown')::int AS unknown_costs,
                coalesce(sum(baseline_cost_usd),0) AS baseline,
                count(*) FILTER (WHERE baseline_cost_usd IS NULL)::int AS unknown_baselines"""
            costs = dict(await conn.fetchrow(SAVINGS_CTE+f'SELECT {cost_totals} FROM checked', *args))
            cost_days = [dict(r) for r in await conn.fetch(SAVINGS_CTE+f"SELECT (ts AT TIME ZONE 'UTC')::date::text AS day,{cost_totals} FROM checked GROUP BY (ts AT TIME ZONE 'UTC')::date ORDER BY day", *args)]
            tenants = [str(r['tenant_id']) for r in await conn.fetch("""SELECT DISTINCT tenant_id FROM tank.ledger WHERE region=$1
                UNION SELECT $2::uuid ORDER BY tenant_id""", args[1], uuid.UUID('00000000-0000-0000-0000-000000000001'))]
            excluded = [dict(r) for r in await conn.fetch(SAVINGS_CTE+'SELECT excluded_reason,count(*)::int AS count FROM checked WHERE excluded_reason IS NOT NULL GROUP BY excluded_reason ORDER BY excluded_reason', *args)]
            data.update(tenant_id=str(tenant) if tenant else 'all', tenants=tenants, region=args[1], excluded=excluded,
                        margin=dict(status='no billing data yet', paid=None, margin=None, margin_percent=None,
                                    total=costs, daily=cost_days))
    return savings_encoded(data)


async def savings_rows(tenant: uuid.UUID | None, end: datetime, page: int = 0,
                       start: datetime | None = None, until: datetime | None = None,
                       member: str | None = None, free_only: bool = False,
                       population: str = 'eligible') -> dict:
    end = savings_end(end)
    # Population comes only from the founder-authorized endpoint, never SQL input.
    source = {'eligible':'eligible', 'excluded':'checked', 'costs':'checked'}[population]
    condition = ' AND excluded_reason IS NOT NULL' if population=='excluded' else ''
    where = f"FROM {source} WHERE ($4::timestamptz IS NULL OR ts >= $4) AND ($5::timestamptz IS NULL OR ts < $5) AND ($6::text IS NULL OR member=$6) AND (NOT $7::boolean OR free_work){condition}"
    args = (tenant, runtime().box_region(), end, start, until, member, free_only)
    async with runtime().pool().acquire() as conn, conn.transaction(isolation='repeatable_read', readonly=True):
        total = dict(await conn.fetchrow(SAVINGS_CTE+f'SELECT {SAVINGS_TOTALS} '+where, *args))
        fields = """job_id,job_title,member,(ts AT TIME ZONE 'UTC')::date::text AS day,
            CASE WHEN research_cost_status='unknown' THEN NULL ELSE cost_usd END AS spent,
            baseline_cost_usd AS would_have_cost,baseline_cost_usd-cost_usd AS saved,free_work"""
        if population != 'eligible':
            fields += ',id,tenant_id,model,baseline_model,baseline_status,excluded_reason'
        rows = [dict(r) for r in await conn.fetch(SAVINGS_CTE+'SELECT '+fields+' '+where+
                ' ORDER BY ts DESC,id DESC LIMIT $8 OFFSET $9', *args, PAGE_SIZE+1, page*PAGE_SIZE)]
    return savings_encoded(dict(rows=rows[:PAGE_SIZE], total=total, page=page, has_more=len(rows)>PAGE_SIZE, as_of=end))


@router.get('/savings')
async def founder_savings(tenant_id: uuid.UUID | None = None, end: datetime | None = None) -> dict:
    return await savings_snapshot(tenant_id, end, founder=True)


@router.get('/savings/rows')
async def founder_savings_rows(end: datetime, tenant_id: uuid.UUID | None = None,
        page: int = Query(default=0, ge=0, le=100000), start: datetime | None = None,
        until: datetime | None = None, member: str | None = Query(default=None, max_length=80),
        free_only: bool = False, population: str = Query(default='eligible', pattern='^(eligible|excluded|costs)$')) -> dict:
    return await savings_rows(tenant_id, end, page, start, until, member, free_only, population)


@router.get('/savings/export/{format}')
async def savings_export(format: str, end: datetime, tenant_id: uuid.UUID | None = None,
                         page: int = Query(default=0, ge=0, le=100000)) -> Response:
    from fastapi import HTTPException
    if format not in ('csv', 'pdf'):
        raise HTTPException(404, 'not found')
    report = await savings_snapshot(tenant_id, end, founder=True)
    evidence = await savings_rows(tenant_id, end, page)
    # Reuse the bounded, formula-safe, dependency-free evidence exporters.
    data = dict(tenant_id=report['tenant_id'], region=report['region'], as_of=report['as_of'],
                description='Client savings: defensible linked work only. Totals cover all history; evidence is the selected page.',
                page=page, has_more=evidence['has_more'], page_size=PAGE_SIZE,
                tasks=[report['total'],dict(this_month=report['month']),dict(team_members=report['members']),dict(margin=report['margin'])],
                ledger=evidence['rows'], shadows=[], runs=[], cases=[], promotions=[], policies=[], state=report['daily'])
    content = csv_export(data) if format=='csv' else pdf_export(data)
    return Response(content, media_type='text/csv' if format=='csv' else 'application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="client-savings.{format}"', 'Cache-Control':'no-store'})


# Registered separately: no founder dependency and no optional/all-tenant scope.
from dashboards import workspace_only
client_router = APIRouter(prefix='/v1/client-savings', dependencies=[Depends(workspace_only)])


@client_router.get('')
async def client_savings(tenant_id: uuid.UUID) -> dict:
    return await savings_snapshot(tenant_id)


@client_router.get('/rows')
async def client_savings_rows(tenant_id: uuid.UUID, end: datetime,
        page: int = Query(default=0, ge=0, le=100000), start: datetime | None = None,
        until: datetime | None = None, member: str | None = Query(default=None, max_length=80), free_only: bool = False) -> dict:
    return await savings_rows(tenant_id, end, page, start, until, member, free_only)


@client_router.get('/revision')
async def client_savings_revision(tenant_id: uuid.UUID) -> dict:
    # Poll a cheap job watermark, then refresh graphs as soon as a completion is observed.
    async with runtime().pool().acquire() as conn:
        row = await conn.fetchrow("SELECT count(*) AS n,max(finished_at) AS last FROM tank.tasks WHERE tenant_id=$1 AND finished_at IS NOT NULL", tenant_id)
    return {'revision': f"{row['n']}:{row['last']}"}
