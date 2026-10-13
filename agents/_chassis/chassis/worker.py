"""Resumable job worker and the in-process scheduler."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from chassis.cron import is_due
from chassis.db import as_json, schema_for
from chassis.jobs import JobContext, decide_retry, decide_timeout
from chassis.logs import log_line

Handler = Callable[[JobContext], Awaitable[dict[str, Any]]]
JOB_POLL_S = 2
SCHEDULE_POLL_S = 15


def _schema(agent: str) -> str:
    return schema_for(agent)


async def reclaim_timed_out(conn: Any, agent: str, now: datetime | None = None) -> None:
    schema = _schema(agent)
    clock = now or datetime.now(timezone.utc)
    rows = await conn.fetch(
        f"""
        SELECT id, tenant_id, status, attempts, max_attempts, timeout_s, started_at
        FROM {schema}.jobs
        WHERE status = 'running' AND tenant_id IS NOT NULL
        LIMIT 100
        """
    )
    for row in rows:
        nxt = decide_timeout(
            status=row["status"],
            started_at=row["started_at"],
            now=clock,
            timeout_s=int(row["timeout_s"]),
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
        )
        if nxt is None:
            continue
        tenant_id = row["tenant_id"]
        job_id = row["id"]
        if nxt == "queued":
            await conn.execute(
                f"""
                UPDATE {schema}.jobs
                SET status = 'queued', started_at = NULL, error = 'timed out'
                WHERE id = $1 AND tenant_id = $2 AND status = 'running'
                """,
                job_id,
                tenant_id,
            )
        else:
            await conn.execute(
                f"""
                UPDATE {schema}.jobs
                SET status = 'failed', error = 'timed out', finished_at = now()
                WHERE id = $1 AND tenant_id = $2 AND status = 'running'
                """,
                job_id,
                tenant_id,
            )
        log_line(agent, f"job {nxt} after timeout", tenant_id=str(tenant_id), job_id=str(job_id))


async def claim_next(conn: Any, agent: str) -> Any:
    schema = _schema(agent)
    async with conn.transaction():
        row = await conn.fetchrow(
            f"""
            SELECT id, tenant_id
            FROM {schema}.jobs
            WHERE status = 'queued' AND run_at <= now() AND tenant_id IS NOT NULL
            ORDER BY run_at, id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
            """
        )
        if row is None:
            return None
        return await conn.fetchrow(
            f"""
            UPDATE {schema}.jobs
            SET status = 'running', started_at = now(), attempts = attempts + 1
            WHERE id = $1 AND tenant_id = $2 AND status = 'queued'
            RETURNING id, tenant_id, kind, input, attempts, max_attempts, timeout_s
            """,
            row["id"],
            row["tenant_id"],
        )


async def _finish(conn: Any, agent: str, job_id: uuid.UUID, tenant_id: uuid.UUID, result: dict[str, Any]) -> None:
    schema = _schema(agent)
    await conn.execute(
        f"""
        UPDATE {schema}.jobs
        SET status = 'done', result = $3::jsonb, error = NULL, finished_at = now()
        WHERE id = $1 AND tenant_id = $2
        """,
        job_id,
        tenant_id,
        json.dumps(result),
    )


async def _fail(conn: Any, agent: str, job_id: uuid.UUID, tenant_id: uuid.UUID, attempts: int, max_attempts: int, error: str) -> str:
    schema = _schema(agent)
    status = decide_retry(attempts=attempts, max_attempts=max_attempts)
    detail = error[:500]
    if status == "queued":
        await conn.execute(
            f"""
            UPDATE {schema}.jobs
            SET status = 'queued', error = $3, started_at = NULL
            WHERE id = $1 AND tenant_id = $2
            """,
            job_id,
            tenant_id,
            detail,
        )
    else:
        await conn.execute(
            f"""
            UPDATE {schema}.jobs
            SET status = 'failed', error = $3, finished_at = now()
            WHERE id = $1 AND tenant_id = $2
            """,
            job_id,
            tenant_id,
            detail,
        )
    return status


async def run_claimed(conn: Any, agent: str, job: Any, handlers: dict[str, Handler], ctx_for: Callable[[Any], JobContext]) -> None:
    tenant_id = job["tenant_id"]
    job_id = job["id"]
    kind = str(job["kind"])
    log_line(agent, "job started", tenant_id=str(tenant_id), job_id=str(job_id))
    handler = handlers.get(kind)
    try:
        if handler is None:
            raise RuntimeError("unknown job kind")
        result = await handler(ctx_for(job))
        if not isinstance(result, dict):
            raise TypeError("job must return an object")
        await _finish(conn, agent, job_id, tenant_id, result)
        log_line(agent, "job done", tenant_id=str(tenant_id), job_id=str(job_id))
    except Exception as exc:  # noqa: BLE001 — record the failure; do not log secrets from the message
        status = await _fail(
            conn,
            agent,
            job_id,
            tenant_id,
            int(job["attempts"]),
            int(job["max_attempts"]),
            exc.__class__.__name__,
        )
        log_line(agent, f"job {status}", tenant_id=str(tenant_id), job_id=str(job_id), level="error")


async def enqueue_due(conn: Any, agent: str, now: datetime | None = None) -> None:
    schema = _schema(agent)
    clock = now or datetime.now(timezone.utc)
    rows = await conn.fetch(
        f"""
        SELECT id, tenant_id, cron, kind, input, last_run
        FROM {schema}.schedules
        WHERE enabled AND tenant_id IS NOT NULL
        """
    )
    for row in rows:
        if not is_due(str(row["cron"]), clock, row["last_run"]):
            continue
        tenant_id = row["tenant_id"]
        async with conn.transaction():
            current = await conn.fetchrow(
                f"SELECT last_run FROM {schema}.schedules WHERE id = $1 AND tenant_id = $2 AND enabled",
                row["id"],
                tenant_id,
            )
            if current is None or not is_due(str(row["cron"]), clock, current["last_run"]):
                continue
            await conn.execute(
                f"""
                INSERT INTO {schema}.jobs (tenant_id, kind, input, status, run_at)
                VALUES ($1, $2, $3::jsonb, 'queued', now())
                """,
                tenant_id,
                row["kind"],
                json.dumps(as_json(row["input"])),
            )
            slot = clock.astimezone(timezone.utc).replace(second=0, microsecond=0)
            await conn.execute(
                f"UPDATE {schema}.schedules SET last_run = $3 WHERE id = $1 AND tenant_id = $2",
                row["id"],
                tenant_id,
                slot,
            )
        log_line(agent, "schedule enqueued", tenant_id=str(tenant_id))


async def job_loop(pool: Any, agent: str, handlers: dict[str, Handler], ctx_for: Callable[[Any], JobContext]) -> None:
    import asyncio

    while True:
        try:
            async with pool.acquire() as conn:
                await reclaim_timed_out(conn, agent)
                job = await claim_next(conn, agent)
            if job is not None:
                async with pool.acquire() as conn:
                    await run_claimed(conn, agent, job, handlers, ctx_for)
        except Exception:  # noqa: BLE001
            log_line(agent, "job tick failed", level="error")
        await asyncio.sleep(JOB_POLL_S)


async def schedule_loop(pool: Any, agent: str) -> None:
    import asyncio

    while True:
        try:
            async with pool.acquire() as conn:
                await enqueue_due(conn, agent)
        except Exception:  # noqa: BLE001
            log_line(agent, "schedule tick failed", level="error")
        await asyncio.sleep(SCHEDULE_POLL_S)
