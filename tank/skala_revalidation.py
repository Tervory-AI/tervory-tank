"""B3: durable policy-change evals through the existing Skala endpoint handler.

No policy selection, approval, cache, shadow, judge or paid search occurs here.
Only the model calls requested by the package's eval cases may execute.
"""
from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from gold import PLATFORM_TENANT

ACTIVE: contextvars.ContextVar[dict | None] = contextvars.ContextVar("skala_revalidation", default=None)
WORKER_LOCK = 73202103
log = logging.getLogger(__name__)


def eval_context(tank: Any, pkg: Any, ctx: Any) -> Any:
    job = ACTIVE.get()
    if job is None:
        return ctx
    policy = job["policy"]
    if isinstance(policy, str):
        policy = json.loads(policy)
    ctx.live_evaluation = True

    async def model(**kwargs):
        if kwargs["task_type"] != job["task_type"]:
            raise ValueError("Revalidation task type does not match the package")
        messages = list(kwargs["messages"])
        if policy.get("system_prompt"):
            messages.insert(0, {"role": "system", "content": policy["system_prompt"]})
        ceiling = int(policy["max_tokens_out"])
        max_tokens = min(kwargs.get("max_tokens") or ceiling, ceiling)
        owner = job["policy_tenant_id"] or PLATFORM_TENANT
        target = job["model"]
        receipt: dict = {}
        started = time.perf_counter()
        cost, outcome, error = 0.0, "unverified", None
        try:
            if tank.graduate.is_skill(target):
                request = tank.RouteRequest(tenant_id=owner, agent=pkg.agent,
                    task_type=job["task_type"], skill=pkg.ref + "#preview",
                    messages=[tank.Message(**m) for m in messages])
                content, cost = await tank._run_code_candidate(request, target, messages)
            else:
                if tank.graduate.router_cannot_serve(target):
                    raise ValueError("Unsupported model target")
                blocked = tank.model_call_refusal(
                    "\n".join(str(m.get("content", "")) for m in messages), target,
                    box=tank.box_region(), tenant_id=str(owner), task_type=job["task_type"], skill=pkg.ref)
                if blocked:
                    raise ValueError("Model evaluation is not permitted in this region")
                # Existing Tank helper: disables provider fallbacks when receipt
                # is supplied and refuses an answer from a different model.
                content, cost = await tank._llm(target, messages, max_tokens, receipt=receipt)
            return {"content": content, "cost_usd": cost}
        except Exception:
            ctx.calls += 1  # SkillContext counts successful calls on return.
            cost = max(cost, float(receipt.get("cost") or 0))
            ctx.cost_usd += cost
            outcome, error = "failed", "skill_revalidation_call_failed"
            raise RuntimeError("Model revalidation call failed") from None
        finally:
            async with tank.pool().acquire() as conn:
                await conn.execute(
                    """INSERT INTO tank.ledger
                    (tenant_id,region,agent,skill,task_type,rung,model,priority,tokens_in,tokens_out,
                     cost_usd,latency_ms,cache_hit,outcome,error)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,'standard',$8,$9,$10,$11,false,$12,$13)""",
                    PLATFORM_TENANT, tank.box_region(), pkg.agent, pkg.ref + "#preview",
                    job["task_type"], 3 if tank.graduate.is_skill(target) else 1, target,
                    receipt.get("tokens_in", 0), receipt.get("tokens_out", 0), cost,
                    int((time.perf_counter() - started) * 1000), outcome, error,
                )
    ctx._model = model
    return ctx


async def record(tank: Any, result: dict, by: str | None = None) -> dict:
    job = ACTIVE.get()
    if job is None:
        raise RuntimeError("Missing policy change")
    gate = result["score"] >= result["threshold"] and result["eligible"]
    eval_id = uuid.uuid4()
    validation = {
        "model": job["model"], "old_model": job["old_model"], "task_type": job["task_type"],
        "policy_tenant_id": str(job["policy_tenant_id"]) if job["policy_tenant_id"] else None,
        "revalidation_id": str(job["id"]), "eval_id": str(eval_id),
        "score": result["score"], "passed": result["passed"], "total": result["total"],
        "validated": gate, "validated_at": datetime.now(timezone.utc).isoformat(),
    }
    async with tank.pool().acquire() as conn:
        async with conn.transaction():
            await tank.skala.lock_approvals(conn)
            completed = await conn.fetchval(
                "SELECT completed_at FROM tank.skill_revalidations WHERE id=$1 AND tenant_id=$2 FOR UPDATE",
                job["id"], PLATFORM_TENANT)
            if completed is not None:
                return result
            await conn.execute(
                """INSERT INTO tank.skill_evals
                (skill_id,version,score,passed,total,cost_usd,details,ran_by,id,model,revalidation_id)
                VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10,$11)""",
                job["skill_id"], job["version"], result["score"], result["passed"], result["total"],
                result["cost_usd"], json.dumps(result["details"]), by or "policy model change",
                eval_id, job["model"], job["id"],
            )
            state = await conn.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2",
                                        job["skill_id"], job["version"])
            # Passing a new model never approves or restores a demoted version.
            new_state = "staging" if state == "approved" and not gate else state
            await conn.execute(
                """UPDATE tank.skills SET last_eval_score=$3,last_eval_at=now(),state=$4,
                models_validated=models_validated || $5::jsonb,updated_at=now()
                WHERE id=$1 AND version=$2""",
                job["skill_id"], job["version"], result["score"], new_state, json.dumps([validation]),
            )
            await conn.execute(
                "UPDATE tank.skill_revalidations SET completed_at=now(),eval_id=$3,error=$4 WHERE id=$1 AND tenant_id=$2",
                job["id"], PLATFORM_TENANT, eval_id, None if gate else "eval_gate_failed",
            )
    result.update(state=new_state, gate="passed" if gate else "failed", model=job["model"])
    return result


def failed_result(tank: Any, job: dict) -> dict:
    pkg = tank._packages.get((job["skill_id"], job["version"]))
    details = []
    if pkg is not None:
        for i, case in enumerate(pkg.cases):
            details.append({"case": i, "name": case.get("name"), "passed": False,
                "why": "error: revalidation unavailable", "goal": case.get("expected", {}), "result": {},
                "case_hash": tank.skala.evidence_hash(case), "package_hash": tank.skala.package_hash(pkg),
                "used_model": False})
    return {"skill": job["skill_id"] + "@" + job["version"], "score": 0.0,
            "threshold": pkg.eval_threshold if pkg else 1.0, "eligible": False,
            "passed": 0, "total": len(details), "cost_usd": 0.0, "details": details}


async def drain(tank: Any, limit: int = 20) -> int:
    """One same-box worker; completing an eval and its job is one transaction."""
    count = 0
    async with tank.pool().acquire() as lock:
        if not await lock.fetchval("SELECT pg_try_advisory_lock($1)", WORKER_LOCK):
            return 0
        try:
            for _ in range(limit):
                row = await lock.fetchrow(
                    "SELECT * FROM tank.skill_revalidations WHERE tenant_id=$1 AND completed_at IS NULL ORDER BY queued_at,id LIMIT 1",
                    PLATFORM_TENANT)
                if row is None:
                    break
                job = dict(row)
                token = ACTIVE.set(job)
                try:
                    pkg = tank.get_package(job["skill_id"], job["version"])
                    if pkg.task_type != job["task_type"]:
                        raise ValueError("Package task type changed")
                    # The exact handler used by /v1/skala/{id}/{version}/evals.
                    await tank.run_skill_evals(pkg.id, pkg.version)
                except Exception:
                    log.warning("Skala model revalidation unavailable for %s@%s", job["skill_id"], job["version"])
                    await record(tank, failed_result(tank, job))
                finally:
                    ACTIVE.reset(token)
                count += 1
        finally:
            await lock.execute("SELECT pg_advisory_unlock($1)", WORKER_LOCK)
    return count


def install(app: Any, tank: Any) -> None:
    task = None

    async def work():
        while True:
            try:
                await drain(tank)
            except Exception:
                log.warning("Skala model revalidation deferred; queued work retained")
            await asyncio.sleep(2)

    @app.on_event("startup")
    async def start():
        nonlocal task
        task = asyncio.create_task(work())

    async def stop():
        if task:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    # Cancel before Tank closes its HTTP client and database pool.
    app.router.on_shutdown.insert(0, stop)
