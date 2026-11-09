"""Bridge from the existing Base worker to its room-owned Hermes process."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import socket
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

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
    job: asyncio.Task | None = None
    operation: str | None = None
    result: dict | None = None


active: dict[tuple[uuid.UUID, uuid.UUID], ActiveBatch] = {}


def receipt_spend(rows):
    """Unknown charges block further work instead of becoming zero savings."""
    from decimal import Decimal, InvalidOperation
    total = Decimal(0)
    for row in rows:
        try:
            value = Decimal(str(row.get("cost_usd")))
            if not value.is_finite() or value < 0:
                raise ValueError()
        except (InvalidOperation, ValueError, TypeError):
            raise RuntimeError("Base model cost is not recorded. Check the run receipt before retrying.") from None
        total += value
    return float(total)


async def run_code_first(pool: Any, skills: Any, task_id: uuid.UUID, cfg: dict, call: Any) -> None:
    """Run the existing free passes before asking the brain to recover gaps."""
    from room import _run_batch

    tenant = uuid.UUID(str(cfg["tenant_id"]))
    if cfg.get("preview"):
        raise RuntimeError("Base's brain may use only approved skills")

    async def free_skill(skill_id: str, payload: dict) -> dict:
        return await call(skill_id, {**payload, "_base_brain_task": str(task_id), "_base_brain_free": True})

    await _run_batch(pool, task_id, cfg, free_skill, planning=True)
    from sources.continuation import finish_context
    await finish_context(pool, getattr(skills, "_http", None), task_id, cfg)
    outcome = await results(ActiveBatch(pool, cfg, call), Task(tenant_id=tenant, task_id=task_id))
    if outcome["pipeline_status"] == "running":
        outcome["pipeline_status"] = "done"
        if not outcome["unresolved"]:
            await pool.execute("UPDATE agent_base.tasks SET status='done',finished_at=now() WHERE tenant_id=$1 AND id=$2 AND status='running'", tenant, task_id)
    # A pause/failure is not permission to spend. Completed, sourced code
    # answers need no model conversation or paid continuation.
    if outcome["pipeline_status"] != "done" or not outcome["unresolved"]:
        return
    await drive_batch(pool, skills, task_id, cfg, call, free_result=outcome)


async def batch_memory_payload(pool, tenant, task_id, cfg):
    """Bind reuse to the persisted record multiset and the worker's pinned inputs."""
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT raw FROM agent_base.records WHERE task_id=$1 AND tenant_id=$2",
            task_id, tenant,
        )
    if not rows or len(rows) != int(cfg["count"]):
        raise RuntimeError("Base batch inputs are incomplete; memory reuse is unavailable")
    # Record order is immaterial to independent enrichment. Retain duplicates and
    # every raw field, including nested source IDs/digests; database row/run IDs stay out.
    records = []
    for row in rows:
        raw = json.loads(row["raw"]) if isinstance(row["raw"], str) else row["raw"]
        if not isinstance(raw, dict):
            raise TypeError("Base batch input is not a record")
        records.append(json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False))
    digest = hashlib.sha256(json.dumps(sorted(records), separators=(",", ":")).encode()).hexdigest()
    return {
        "input_version": 2,
        "records_sha256": digest,
        "batch": cfg.get("batch"),
        "count": len(records),
        "engine": cfg.get("engine"),
        "preview": cfg.get("preview"),
        "registry": cfg.get("registry"),
        "refs": cfg.get("refs"),
        "engine_data_version": cfg.get("engine_data_version"),
        "region": cfg.get("region") or os.environ.get("TANK_REGION", "us-east"),
    }


async def drive_batch(pool, skills, task_id, cfg, call, *, free_result: dict | None = None):
    """Recover unresolved work; the queue enters through run_code_first."""
    tenant = uuid.UUID(str(cfg["tenant_id"]))
    identity = (tenant, task_id)
    if cfg.get("preview"):
        raise RuntimeError("Base's brain may use only approved skills")
    async def scoped_call(skill_id, payload):
        return await call(skill_id, {**payload, "_base_brain_task": str(task_id)})
    batch = ActiveBatch(pool, cfg, scoped_call)
    if free_result is not None:
        # The brain's pipeline_run tool receives the completed free pass. It
        # must not repeat reads or charge for work the queue already did.
        batch.ran, batch.operation, batch.result = True, "pipeline", free_result
    receipt = None
    memory = getattr(skills, "memory", None)
    from gates_memory import normalize_memory_control, resolve_authenticated_user_id
    # Fail closed for memory: no synthetic tenant-as-user identity.
    user_id = resolve_authenticated_user_id(cfg if isinstance(cfg, dict) else {}, tenant)
    # Only the verified ingress may persist this marker in the queued row.
    # Historical created_by/user_id values alone must never grant personal memory.
    if not user_id or cfg.get("verified_user_id") != user_id:
        user_id = None
    task_key = str(cfg.get("batch") or task_id)
    memory_control = normalize_memory_control(
        (cfg.get("memory_control") if isinstance(cfg, dict) else None)
        or os.environ.get("BASE_MEMORY_CONTROL")
        or "off"
    )
    skip_storage = False
    if memory is not None and user_id is not None and memory_control != "off":
        # Persisted personal OFF wins over request overrides and survives restarts.
        try:
            rows = await memory.records(str(tenant), user_id=user_id)
        except (RuntimeError, TimeoutError, ConnectionError) as exc:
            from gates_memory import storage_unavailable
            if not storage_unavailable(exc):
                raise
            rows, skip_storage = [], True
        for row in rows:
            meta = row.get("meta") or {}
            if (row.get("tenant_id") == str(tenant) and meta.get("user_id") == user_id
                    and meta.get("base_control") in {"off", "view", "edit", "forget"}):
                memory_control = meta["base_control"]
    use_memory = memory is not None and user_id is not None and memory_control != "off"
    active[identity] = batch
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE agent_base.tasks SET status='running',started_at=coalesce(started_at,now()),finished_at=NULL "
                "WHERE tenant_id=$1 AND id=$2", tenant, task_id)

        async def _brain_tank_paid(task_payload: dict) -> dict:
            from brain_route import invoke_brain_task
            return await invoke_brain_task(
                skills,
                tenant_id=str(tenant),
                task_id=str(task_id),
                batch=str(cfg["batch"]),
                count=int(cfg["count"]),
                engine=cfg.get("engine"), user_id=user_id,
                evidence=(batch.result or {}).get("unresolved", []),
            )

        if memory is not None and user_id is None:
            logging.getLogger("base.brain").info(
                "Memory bracket skipped: no authenticated user_id (fail closed for memory scope)")
        if memory is not None and memory_control == "off":
            logging.getLogger("base.brain").info(
                "Memory bracket skipped: memory_control=off (historical path, no memory ops)")

        if use_memory:
            from gates_memory import product_to_brain_tank_memory
            # Memory enabled: bracket failures fail closed (no silent paid direct path).
            bracket = await product_to_brain_tank_memory(
                memory,
                tenant_id=str(tenant),
                user_id=user_id,
                task_key=task_key,
                task=await batch_memory_payload(pool, tenant, task_id, cfg),
                brain_tank_call=_brain_tank_paid,
                memory_control=memory_control, skip_storage=skip_storage,
            )
            if bracket.get("answered_from_memory"):
                reuse = ((bracket.get("result") or {}) if isinstance(bracket.get("result"), dict) else {}).get("reuse")
                summary = (
                    "Identical task reused from memory; paid brain/Tank route skipped."
                    if reuse == "identical_receipt"
                    else "Applied memory correction; paid brain/Tank route skipped."
                )
                receipt = {
                    "tenant_id": str(tenant),
                    "task_id": str(task_id),
                    "room": "base",
                    "status": "done",
                    "steps": bracket["steps"],
                    "model_receipts": [],
                    "summary": summary + " " + json.dumps(bracket.get("result") or {}, sort_keys=True),
                    "answered_from_memory": True,
                    "cost_usd": 0.0,
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "tokens_total": 0,
                }
                from gates_memory import usage_from_model_receipts
                original = bracket.get("result") or {}
                comparison = usage_from_model_receipts(original.get("model_receipts", []))
                receipt.update(paid_calls=0, would_have_cost=comparison["cost_usd"],
                    comparison_status="prior_recorded_run" if comparison["cost_usd"] is not None else "unknown")
                cfg["brain_receipt"] = receipt
                cfg["brain_spend"] = 0.0
                async with pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE agent_base.tasks SET input=$3::jsonb,status='done',error=NULL,finished_at=now() "
                        "WHERE tenant_id=$1 AND id=$2", tenant, task_id, json.dumps(cfg))
                return
            paid_result = bracket.get("result") or {}
            receipt = paid_result if isinstance(paid_result, dict) and paid_result.get("task_id") else None
            if receipt is None:
                raise RuntimeError("Brain memory bracket returned no receipt")
            receipt = {
                **receipt,
                **{field: bracket[field] for field in ("cost_usd", "tokens_in", "tokens_out", "tokens_total", "paid_calls")},
                "answered_from_memory": False,
                "memory_bracket": {
                    "steps": bracket["steps"],
                    "cost_usd": bracket["cost_usd"],
                    "tokens_in": bracket["tokens_in"],
                    "tokens_out": bracket["tokens_out"],
                    "tokens_total": bracket["tokens_total"],
                    "answered_from_memory": False,
                    "memory_control": memory_control,
                    "memory_unavailable": bool(bracket.get("memory_unavailable")),
                },
            }

        if not use_memory:
            if user_id is None:
                # Historical ownerless rows stay on the unchanged code/skill path.
                # They never enter personal memory or a fabricated shared actor.
                from room import _run_batch
                if batch.ran:
                    await run_phase(batch, Task(tenant_id=tenant, task_id=task_id, finish=True))
                else:
                    await _run_batch(pool, task_id, cfg, scoped_call)
                return
            paid = await _brain_tank_paid({})
            receipt = dict(paid['result'])
            receipt.update({field: paid[field] for field in ('cost_usd', 'tokens_in', 'tokens_out', 'tokens_total')})
            receipt.update(paid_calls=len(receipt.get('model_receipts', [])), answered_from_memory=False)
        cfg["brain_receipt"] = receipt
        if (bracket["cost_usd"] if use_memory else receipt.get("cost_usd")) is None:
            # The work already ran. Retain its receipt and unknown spend; never
            # retry a paid edge or publish a zero total after a ledger outage.
            cfg["brain_spend"] = cfg["model_spend"] = None
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agent_base.tasks SET input=$3::jsonb,status='failed',error=$4,finished_at=now() "
                    "WHERE tenant_id=$1 AND id=$2", tenant, task_id, json.dumps(cfg),
                    "Base model cost is not recorded. Check the run receipt before retrying.",
                )
            raise RuntimeError("Base model cost is not recorded. Check the run receipt before retrying.")
        cost = receipt_spend(receipt.get("model_receipts", []))
        previous_brain_cost = float(cfg.get("brain_spend") or 0)
        cost = max(previous_brain_cost, cost)
        cfg["brain_spend"] = cost
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
            "SELECT id,raw,profile,status FROM agent_base.records WHERE tenant_id=$1 AND task_id=$2 "
            "AND (status<>'done' OR confidence<80) ORDER BY created_at LIMIT 20", body.tenant_id, body.task_id)
        task = await conn.fetchrow("SELECT status,result FROM agent_base.tasks WHERE tenant_id=$1 AND id=$2", body.tenant_id, body.task_id)
    unresolved = []
    for row in rows:
        raw, profile = row["raw"], row["profile"]
        raw = json.loads(raw) if isinstance(raw, str) else raw
        profile = json.loads(profile) if isinstance(profile, str) else profile
        def value(key):
            item = profile.get(key) or raw.get(key) or ""
            return str(item.get("value") or "") if isinstance(item, dict) else str(item)
        unresolved.append({"id": str(row["id"]), "name": value("name")[:120],
            "raw_name": str(raw.get("name") or "")[:120],
            "website": value("website")[:160], "status": row["status"]})
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


def public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified


async def check_website(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise HTTPException(422, "A public website URL without credentials is required.")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if port != (443 if parsed.scheme == "https" else 80):
        raise HTTPException(422, "Use a standard public web port.")
    try:
        answers = await asyncio.get_running_loop().getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)
        if not answers or not all(public_address(answer[4][0]) for answer in answers):
            raise ValueError("private address")
    except (ValueError, OSError):
        raise HTTPException(403, "Private or internal website refused.") from None


async def phase_result(batch: ActiveBatch) -> dict:
    if batch.job is None and batch.result is not None:
        return batch.result
    if batch.job is None or not batch.job.done():
        return {"pipeline_status": "running"}
    return batch.result or {"pipeline_status": "failed", "error": "Pipeline could not finish."}


async def run_phase(batch: ActiveBatch, body: Task, retry: Retry | None = None):
    from room import _run_batch
    try:
        if retry:
            async with batch.pool.acquire() as conn:
                changed = await conn.fetchval(
                    "UPDATE agent_base.records SET raw=jsonb_set(raw,'{website}',to_jsonb($4::text)),status='queued',error=NULL "
                    "WHERE tenant_id=$1 AND task_id=$2 AND id=$3 AND (status<>'done' OR confidence<80) RETURNING id",
                    body.tenant_id, body.task_id, retry.record_id, retry.website)
            if changed is None:
                raise RuntimeError("No unresolved record in this task")
        if body.finish:
            async with batch.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE agent_base.records SET status='queued',error=NULL WHERE tenant_id=$1 AND task_id=$2 "
                    "AND (status<>'done' OR confidence<80 OR passes->'2c' ? 'skipped' OR passes->'5' ? 'skipped')",
                    body.tenant_id, body.task_id)
        await _run_batch(batch.pool, body.task_id, batch.cfg, batch.call if body.finish else free_call(batch))
        batch.result = await pipeline_result(batch, body)
        if batch.result["pipeline_status"] == "queued":
            batch.result["pipeline_status"] = "paused"
    except Exception:
        batch.result = {"pipeline_status": "failed", "error": "Pipeline could not finish; completed work retained."}


def register(app):
    from fastapi.responses import JSONResponse

    @app.post("/brain/pipeline")
    async def pipeline(body: Task, x_tank_key: str = Header(default="")):
        batch = selected(body, x_tank_key)
        operation = "finish" if body.finish else "pipeline"
        async with batch.lock:
            if batch.operation == operation and (batch.job or batch.result is not None):
                result = await phase_result(batch)
                return JSONResponse(result, status_code=202 if batch.job and not batch.job.done() else 200)
            if batch.job and not batch.job.done():
                raise HTTPException(409, "Another pipeline operation is still running.")
            if body.finish:
                if not batch.ran or batch.finished:
                    raise HTTPException(409, "Free recovery must finish once before paid continuation.")
                batch.finished = True
            elif batch.ran:
                raise HTTPException(409, "This pipeline already ran.")
            else:
                batch.ran = True
            batch.operation, batch.result = operation, None
            batch.job = asyncio.create_task(run_phase(batch, body))
            return JSONResponse({"pipeline_status": "running"}, status_code=202)

    @app.get("/brain/pipeline")
    async def poll_pipeline(tenant_id: uuid.UUID, task_id: uuid.UUID, finish: bool = False,
                            x_tank_key: str = Header(default="")):
        body = Task(tenant_id=tenant_id, task_id=task_id, finish=finish)
        batch = selected(body, x_tank_key)
        if batch.operation != ("finish" if finish else "pipeline"):
            raise HTTPException(404, "No matching pipeline operation.")
        return await phase_result(batch)

    @app.post("/brain/retry")
    async def retry(body: Retry, x_tank_key: str = Header(default="")):
        batch = selected(body, x_tank_key)
        await check_website(body.website)
        async with batch.lock:
            if not batch.ran or batch.finished or (batch.job and not batch.job.done()):
                raise HTTPException(409, "The default pipeline must finish first.")
            batch.operation, batch.result = "retry:" + str(body.record_id), None
            batch.job = asyncio.create_task(run_phase(batch, body, retry=body))
            return JSONResponse({"pipeline_status": "running"}, status_code=202)

    @app.get("/brain/retry")
    async def poll_retry(tenant_id: uuid.UUID, task_id: uuid.UUID, record_id: uuid.UUID,
                        x_tank_key: str = Header(default="")):
        batch = selected(Task(tenant_id=tenant_id, task_id=task_id), x_tank_key)
        if batch.operation != "retry:" + str(record_id):
            raise HTTPException(404, "No matching retry.")
        return await phase_result(batch)
