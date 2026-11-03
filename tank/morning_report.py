"""D6: deterministic daily founder mail, with one durable send claim per box/day."""
from __future__ import annotations

import asyncio
from datetime import datetime, time, timedelta, timezone
from email.message import EmailMessage
import json
import logging
import os
import smtplib
import ssl
from zoneinfo import ZoneInfo

from gold import PLATFORM_TENANT
from tenant_db import tenant_scope

PACIFIC = ZoneInfo("America/Los_Angeles")
log = logging.getLogger(__name__)


def window(at: datetime):
    local = at.astimezone(PACIFIC)
    end = datetime.combine(local.date(), time(7), PACIFIC)
    if local < end:
        return None
    start = datetime.combine(local.date() - timedelta(days=1), time(7), PACIFIC)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def configured():
    return all(os.environ.get("FOUNDER_REPORT_" + name, "").strip()
               for name in ("TO", "SMTP_HOST", "SMTP_FROM"))


async def deploys(start: datetime, end: datetime) -> dict:
    """Read only the fixed deployment workflow, through the existing read token."""
    import command_repo
    if not command_repo.configured():
        return {"available": False, "reason": "repository read token is not configured", "runs": []}
    runs = []
    try:
        async with asyncio.timeout(30), command_repo.github() as client:
            for page in range(1, 11):
                async with client.stream("GET", command_repo.API + "/actions/workflows/deploy-on-merge.yml/runs",
                                         params={"branch": "main", "event": "push", "per_page": 100,
                                                 "page": page, "created": start.isoformat() + ".." + end.isoformat()}) as response:
                    response.raise_for_status()
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > command_repo.MAX_RESPONSE_BYTES:
                            raise ValueError("deployment response too large")
                    rows = json.loads(data)["workflow_runs"]
                    runs.extend({"id": row["id"], "commit": row["head_sha"], "status": row["status"],
                                 "conclusion": row.get("conclusion"), "created_at": row["created_at"]}
                                for row in rows if start <= datetime.fromisoformat(row["created_at"].replace("Z", "+00:00")) < end)
                    if len(rows) < 100:
                        return {"available": True, "runs": runs}
        return {"available": True, "runs": runs, "truncated": True}
    except Exception as exc:
        log.warning("Morning report deployment read: %s", type(exc).__name__)
        return {"available": False, "reason": "deployment history unavailable", "runs": []}


async def build(tank, start: datetime, end: datetime) -> dict:
    with tenant_scope(None, administrative=True):
        async with tank.admin_pool().acquire() as conn:
            ledger = await conn.fetchrow("""SELECT count(*) AS calls,
                count(*) FILTER (WHERE outcome='delivered') AS delivered,
                count(*) FILTER (WHERE outcome='failed') AS failed,
                count(*) FILTER (WHERE outcome='unverified') AS unverified,
                count(*) FILTER (WHERE cost_status IS DISTINCT FROM 'set') AS unknown_cost_calls,
                sum(cost_usd) FILTER (WHERE cost_status='set') AS known_cost_usd,
                sum(greatest(baseline_cost_usd-cost_usd,0)) FILTER
                  (WHERE cost_status='set' AND baseline_cost_usd IS NOT NULL) AS known_savings_usd,
                count(*) FILTER (WHERE baseline_cost_usd IS NULL) AS unknown_baseline_calls
                FROM tank.ledger WHERE region=$1 AND ts >= $2 AND ts < $3""", tank.box_region(), start, end)
            jobs = await conn.fetch("""SELECT agent,count(*) AS count FROM tank.tasks
                WHERE status='failed' AND finished_at >= $1 AND finished_at < $2 GROUP BY agent ORDER BY agent""", start, end)
            candidates = await conn.fetch("""SELECT task_type,model,candidate_model FROM tank.policy
                WHERE tenant_id IS NULL AND candidate_model IS NOT NULL ORDER BY task_type""")
    return {"region": tank.box_region(), "start": start.isoformat(), "end": end.isoformat(),
            "ledger": dict(ledger), "failed_jobs": [dict(row) for row in jobs],
            "graduation_candidates": [dict(row) for row in candidates], "deploys": await deploys(start, end)}


def message(report: dict) -> EmailMessage:
    mail = EmailMessage()
    mail["From"] = os.environ["FOUNDER_REPORT_SMTP_FROM"]
    mail["To"] = os.environ["FOUNDER_REPORT_TO"]
    mail["Subject"] = "Tervory morning report — " + report["region"] + " — " + report["end"][:10]
    mail.set_content("Reporting window: " + report["start"] + " to " + report["end"] + "\n\n"
                     + json.dumps(report, indent=2, default=str, ensure_ascii=False)
                     + "\n\nMissing cost or baseline data is unknown, not zero. Deployment entries are workflow outcomes.\n")
    return mail


def send(mail: EmailMessage):
    with smtplib.SMTP(os.environ["FOUNDER_REPORT_SMTP_HOST"],
                      int(os.environ.get("FOUNDER_REPORT_SMTP_PORT") or "587"), timeout=20) as smtp:
        smtp.starttls(context=ssl.create_default_context())
        user = os.environ.get("FOUNDER_REPORT_SMTP_USER", "")
        if user:
            smtp.login(user, os.environ.get("FOUNDER_REPORT_SMTP_PASSWORD", ""))
        smtp.send_message(mail)


async def process(tank, at: datetime | None = None):
    if not configured():
        return
    period = window(at or datetime.now(timezone.utc))
    if period is None:
        return
    start, end = period
    day = end.astimezone(PACIFIC).date()
    with tenant_scope(PLATFORM_TENANT):
        async with tank.pool().acquire() as conn:
            claimed = await conn.fetchval("""INSERT INTO tank.morning_reports(tenant_id,region,report_date,status)
                VALUES($1,$2,$3,'preparing') ON CONFLICT DO NOTHING RETURNING report_date""",
                PLATFORM_TENANT, tank.box_region(), day)
        if claimed is None:
            return
        status = "failed"
        try:
            report = await build(tank, start, end)
            async with tank.pool().acquire() as conn:
                await conn.execute("""UPDATE tank.morning_reports SET payload=$4::jsonb,status='sending'
                    WHERE tenant_id=$1 AND region=$2 AND report_date=$3""",
                    PLATFORM_TENANT, tank.box_region(), day, json.dumps(report, default=str))
            status = "uncertain"
            await asyncio.wait_for(asyncio.to_thread(send, message(report)), timeout=65)
            status = "sent"
        except Exception as exc:
            log.warning("Morning report: %s", type(exc).__name__)
        finally:
            async with tank.pool().acquire() as conn:
                await conn.execute("""UPDATE tank.morning_reports SET status=$4,finished_at=now()
                    WHERE tenant_id=$1 AND region=$2 AND report_date=$3""",
                    PLATFORM_TENANT, tank.box_region(), day, status)


async def loop(tank):
    while True:
        try:
            await process(tank)
        except Exception as exc:
            log.warning("Morning report scheduler: %s", type(exc).__name__)
        await asyncio.sleep(30)


def install(app, tank):
    from fastapi import Depends, HTTPException
    from gold import require_reviewer

    @app.get('/v1/platform/morning-report')
    async def latest(actor=Depends(require_reviewer)):
        if not actor.founder:
            raise HTTPException(404, 'not found')
        with tenant_scope(PLATFORM_TENANT):
            async with tank.pool().acquire() as conn:
                row = await conn.fetchrow('''SELECT region,report_date,status,payload,finished_at
                    FROM tank.morning_reports WHERE tenant_id=$1 AND region=$2
                    ORDER BY report_date DESC LIMIT 1''', PLATFORM_TENANT, tank.box_region())
        return {'configured': configured(), 'schedule': '07:00 America/Los_Angeles',
                'report': dict(row) if row else None}

    task = None

    @app.on_event('startup')
    async def start():
        nonlocal task
        task = asyncio.create_task(loop(tank))

    async def stop():
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app.router.on_shutdown.insert(0, stop)
