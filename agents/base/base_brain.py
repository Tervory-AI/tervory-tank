"""Bridge from the existing Base worker to its room-owned Hermes process."""
from __future__ import annotations

import asyncio
import hmac
import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import Header, HTTPException
from pydantic import BaseModel


@dataclass
class ActiveBatch:
    pool: Any
    cfg: dict
    call: Any
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    ran: bool = False
    finished: bool = False


active: dict[tuple[uuid.UUID, uuid.UUID], ActiveBatch] = {}


async def drive_batch(pool, skills, task_id, cfg, call):
    tenant = uuid.UUID(str(cfg["tenant_id"]))
    identity = (tenant, task_id)
    if cfg.get("preview"):
        raise RuntimeError("Base's brain may use only approved skills")
    async def scoped_call(skill_id, payload):
        return await call(skill_id, {**payload, "_base_brain_task": str(task_id)})
    active[identity] = ActiveBatch(pool, cfg, scoped_call)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE agent_base.tasks SET status='running',started_at=coalesce(started_at,now()),finished_at=NULL "
                "WHERE tenant_id=$1 AND id=$2", tenant, task_id)
        async with httpx.AsyncClient(timeout=1900) as client:
            response = await client.post(os.environ["BASE_BRAIN_URL"] + "/tasks",
                headers=skills._headers(), json={"tenant_id": str(tenant), "task_id": str(task_id),
                    "home_region": os.environ.get("TANK_REGION", "us-east"), "batch": cfg["batch"],
                    "count": cfg["count"], "engine": cfg.get("engine")})
        if response.status_code != 200:
            raise RuntimeError("Base brain unavailable; task was not completed")
        receipt = response.json()
        if receipt.get("tenant_id") != str(tenant) or receipt.get("task_id") != str(task_id):
            raise RuntimeError("Brain receipt scope mismatch")
        cfg["brain_receipt"] = receipt
        cost = sum(float(r["cost_usd"]) for r in receipt.get("model_receipts", []))
        previous_brain_cost = float(cfg.get("brain_spend") or 0)
        cfg["brain_spend"] = cost
        # Tank returns every thinking receipt for this task, including an earlier
        # attempt. Replace that subtotal on rerun rather than charging it twice.
        cfg["model_spend"] = float(cfg.get("model_spend") or 0) - previous_brain_cost + cost
        failed = receipt.get("status") != "done"
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE agent_base.tasks SET input=$3::jsonb,status=$4,error=$5,ledger_id=$6,finished_at=now() "
                "WHERE tenant_id=$1 AND id=$2", tenant, task_id, json.dumps(cfg), "failed" if failed else "done",
                receipt.get("error"), uuid.UUID(receipt["model_receipts"][-1]["ledger_id"]) if receipt.get("model_receipts") else None)
        if failed:
            raise RuntimeError(receipt.get("error") or "Base's brain did not finish")
    finally:
        active.pop(identity, None)


class Task(BaseModel):
    tenant_id: uuid.UUID
    task_id: uuid.UUID
    finish: bool = False


class Retry(Task):
    record_id: uuid.UUID
    website: str


def selected(body: Task, key: str) -> ActiveBatch:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "Base room key required.")
    batch = active.get((body.tenant_id, body.task_id))
    if batch is None:
        raise HTTPException(404, "No active batch for this tenant.")
    return batch


async def results(batch: ActiveBatch, body: Task) -> dict:
    async with batch.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id,raw,profile,passes,status FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 "
            "AND (status<>'done' OR confidence<80) ORDER BY created_at LIMIT 20", body.tenant_id, body.task_id)
        task = await conn.fetchrow("SELECT status,result FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2", body.tenant_id, body.task_id)
    unresolved = []
    for row in rows:
        item = dict(row)
        item["id"] = str(item["id"])
        for key in ("raw", "profile", "passes"):
            if isinstance(item[key], str):
                item[key] = json.loads(item[key])
        unresolved.append(item)
    return {"pipeline_status": task["status"], "summary": task["result"], "unresolved": unresolved,
            "skills": batch.cfg.get("refs", {}), "cost_usd": batch.cfg.get("model_spend", 0)}


async def pipeline_result(batch: ActiveBatch, body: Task) -> dict:
    result = await results(batch, body)
    # The code pipeline finished, but recall/recovery/remember still belong to
    # this task. Publish terminal status only when the complete receipt arrives.
    async with batch.pool.acquire() as conn:
        await conn.execute(
            "UPDATE agent_base.tasks SET status='running',finished_at=NULL WHERE tenant_id=$1 AND id=$2",
            body.tenant_id, body.task_id)
    return result


async def batch_receipts(conn, tenant: uuid.UUID) -> dict:
    """Expose the receipt through the existing Tank-proxied batches response."""
    rows = await conn.fetch(
        "SELECT id,status,error,input->>'batch' AS batch,input->'brain_receipt' AS receipt "
        "FROM agent_base.tasks WHERE tenant_id=$1 AND task_type='base.enrich' "
        "ORDER BY created_at DESC LIMIT 200", tenant)
    batches: dict[str, list] = {}
    for row in rows:
        receipt = row["receipt"]
        if isinstance(receipt, str):
            receipt = json.loads(receipt)
        batches.setdefault(row["batch"], []).append({"task_id": str(row["id"]), "status": row["status"],
                                                    "error": row["error"], "receipt": receipt})
    return batches


def free_call(batch: ActiveBatch):
    async def call(skill_id, payload):
        return await batch.call(skill_id, {**payload, "_base_brain_free": True})
    return call


def register(app):
    @app.post("/brain/pipeline")
    async def pipeline(body: Task, x_tank_key: str = Header(default="")):
        batch = selected(body, x_tank_key)
        from room import _run_batch
        async with batch.lock:
            if body.finish:
                if not batch.ran or batch.finished:
                    raise HTTPException(409, "Free recovery must finish once before paid continuation.")
                batch.finished = True
                async with batch.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE agent_base.records SET status='queued',error=NULL WHERE tenant_id=$1 AND task_id=$2 "
                        "AND (status<>'done' OR confidence<80 OR passes->'2c' ? 'skipped' OR passes->'5' ? 'skipped')",
                        body.tenant_id, body.task_id)
                await _run_batch(batch.pool, body.task_id, batch.cfg, batch.call)
                return await pipeline_result(batch, body)
            if batch.ran:
                raise HTTPException(409, "This pipeline already ran.")
            batch.ran = True
            await _run_batch(batch.pool, body.task_id, batch.cfg, free_call(batch))
            return await pipeline_result(batch, body)

    @app.post("/brain/retry")
    async def retry(body: Retry, x_tank_key: str = Header(default="")):
        batch = selected(body, x_tank_key)
        parsed = urlsplit(body.website)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise HTTPException(422, "A public website URL without credentials is required.")
        from room import _run_batch
        async with batch.lock:
            if not batch.ran or batch.finished:
                raise HTTPException(409, "The default pipeline must run first.")
            async with batch.pool.acquire() as conn:
                changed = await conn.fetchval(
                    "UPDATE agent_base.records SET raw=jsonb_set(raw,'{website}',to_jsonb($4::text)),status='queued',error=NULL "
                    "WHERE tenant_id=$1 AND task_id=$2 AND id=$3 AND (status<>'done' OR confidence<80) RETURNING id",
                    body.tenant_id, body.task_id, body.record_id, body.website)
            if changed is None:
                raise HTTPException(404, "No unresolved record in this tenant's task.")
            await _run_batch(batch.pool, body.task_id, batch.cfg, free_call(batch))
            return await pipeline_result(batch, body)
