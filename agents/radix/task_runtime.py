"""Verified actors and resumable receipts on the existing Radix job path."""
from contextlib import asynccontextmanager
from contextvars import ContextVar
import json
import os
from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.routing import APIRoute
from chassis.app import JobIn
from chassis.job_contract import Job
from chassis.tenant_db import TenantPool, tenant_path, tenant_scope
from radix_memory import run_with_memory, task_input_hash
from radix_brain import brain_enabled, brain_then_analyze
from verify.routes import require_tank


def memory_enabled():
    return os.environ.get("RADIX_MEMORY_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


class TransactionPool:
    """Let the unchanged chassis enqueue share our atomic actor transaction."""
    def __init__(self, base):
        self.base = base
        self.current = ContextVar("radix_submission_connection", default=None)

    def __getattr__(self, name):
        return getattr(self.base, name)

    @asynccontextmanager
    async def acquire(self, **kwargs):
        connection = self.current.get()
        if connection is not None:
            yield connection
        else:
            async with self.base.acquire(**kwargs) as connection:
                yield connection


def pool_for(app):
    if not isinstance(app.state.pool, TransactionPool):
        app.state.pool = TransactionPool(app.state.pool)
    return app.state.pool


@asynccontextmanager
async def actor_lock(pool, tenant, user):
    # Serializes controls, cache reads and paid work for a person across workers.
    key = f"radix-memory:{tenant}:{user}"
    base = pool.base if isinstance(pool, TransactionPool) else pool
    options = {"autocommit": True} if isinstance(base, TenantPool) else {}
    # The production TenantPool normally opens a transaction for a checkout.
    # Use its durable-worker mode so the pre-payment checkpoint commits now.
    with tenant_scope(tenant):
        async with pool.acquire(**options) as conn:
            await conn.execute("SELECT pg_advisory_lock(hashtextextended($1,0))", key)
            try:
                yield conn
            finally:
                await conn.execute("SELECT pg_advisory_unlock(hashtextextended($1,0))", key)


def attach(app):
    original = next(route for route in app.routes if isinstance(route, APIRoute) and route.path == "/jobs" and "POST" in route.methods)
    read = next(route for route in app.routes if isinstance(route, APIRoute) and route.path == "/jobs/{job_id}" and "GET" in route.methods)

    @tenant_path("body")
    async def enqueue(request: Request, body: JobIn | Job):
        from chassis.user_assertion import signed_user, HEADER
        await require_tank(request)
        # Body selectors never establish ownership. An asserted actor must verify,
        # even when the feature is off; a service-only plain job stays supported.
        tenant = str(body.tenant_id)
        actor = await signed_user(request, tenant_id=tenant, product="radix", required=True) if request.headers.get(HEADER) else None
        if not memory_enabled() or actor is None:
            return await original.endpoint(body)
        pool = pool_for(app)
        async with pool.acquire() as conn, conn.transaction():
            token = pool.current.set(conn)
            try:
                submitted = await original.endpoint(body)
                wire = body if isinstance(body, Job) else Job.from_room(body.model_dump(), agent="radix", region=os.environ.get("TANK_REGION", "us-east"))
                execution_input = dict(wire.input)
                if wire.engine is not None:
                    execution_input["engine"] = wire.engine
                await conn.execute("""INSERT INTO agent_radix.task_context
                    (tenant_id,job_id,user_id,role,input_hash) VALUES($1,$2,$3,$4,$5)""",
                    UUID(tenant), UUID(submitted["id"]), actor.user_id, actor.role,
                    task_input_hash(execution_input))
                return submitted
            finally:
                pool.current.reset(token)

    @tenant_path("tenant_id")
    async def get_job(request: Request, job_id: UUID, tenant_id: UUID):
        from chassis.user_assertion import signed_user
        await require_tank(request)
        async with app.state.pool.acquire() as conn:
            owner = await conn.fetchval("SELECT user_id FROM agent_radix.task_context WHERE tenant_id=$1 AND job_id=$2", tenant_id, job_id)
        if owner:
            actor = await signed_user(request, tenant_id=str(tenant_id), product="radix", required=True)
            if actor.user_id != owner:
                raise HTTPException(404, "no such job")
        return await read.endpoint(job_id, tenant_id)

    # Replace only Radix's entry handlers, keeping chassis validation, insertion,
    # queue claiming, retries, timeouts, RLS and result persistence unchanged.
    app.router.routes[app.router.routes.index(original)] = APIRoute("/jobs", enqueue, methods=["POST"], status_code=201)
    app.router.routes[app.router.routes.index(read)] = APIRoute("/jobs/{job_id}", get_job, methods=["GET"])
    app.state.radix_task_runtime = True


def unpack(value):
    return json.loads(value) if isinstance(value, str) else value


async def finish_scan(app, ctx, result):
    if not memory_enabled():
        return result
    tenant, job = UUID(str(ctx.tenant_id)), UUID(str(ctx.job_id))
    async with app.state.pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM agent_radix.task_context WHERE tenant_id=$1 AND job_id=$2", tenant, job)
    if row is None:
        return result
    if row["input_hash"] != task_input_hash(ctx.input):
        raise PermissionError("Radix job input changed after authorization")
    user = row["user_id"]
    async with actor_lock(app.state.pool, tenant, user) as conn:
        row = await conn.fetchrow("SELECT * FROM agent_radix.task_context WHERE tenant_id=$1 AND job_id=$2", tenant, job)
        if row["receipt"] is not None:
            return {**result, "receipt": unpack(row["receipt"])}
        evidence = {key: result[key] for key in ("ref", "findings", "tool_status", "scan_complete", "summary") if key in result}
        task = {"evidence_hash": task_input_hash(evidence), "input_hash": row["input_hash"]}

        async def free(_):
            # Models cannot substitute for an unavailable scanner. Code handles
            # an empty scan or a disabled explanation feature on its own.
            if not brain_enabled() or not result.get("findings") or not result.get("scan_complete"):
                return {"result": evidence, "cost_usd": 0, "tokens_in": 0, "tokens_out": 0,
                        "paid_calls": 0, "status": "completed" if result.get("scan_complete") else "incomplete"}
            return None

        async def paid(_):
            if row["execution"] is not None:
                return unpack(row["execution"])
            if row["stage"] == "executing":
                return {"status": "uncertain", "result": {"status": "unknown"},
                        "paid_calls": None, "cost_usd": None, "tokens_in": None, "tokens_out": None}
            # Commit before crossing the paid boundary. A crash in the uncertain
            # window fails closed; retry must never dispatch a second payment.
            await conn.execute("UPDATE agent_radix.task_context SET stage='executing' WHERE tenant_id=$1 AND job_id=$2", tenant, job)
            try:
                # The product's owner-scoped cache is authoritative. On a miss,
                # an opaque run binding prevents Tank's tenant-wide cache from
                # resurrecting forgotten content or reusing another user's run.
                scoped = {**evidence, "run_scope": task_input_hash({"tenant": str(tenant), "user": user, "job": str(job)})}
                from chassis.user_assertion import SignedUser
                actor = SignedUser(str(tenant), user, row["role"])
                executed = await brain_then_analyze(actor, run_id=str(job), tank=ctx.tank, evidence=scoped)
            except Exception:
                executed = {"status": "failed", "result": {"status": "unknown", "error": "Tank could not complete the security review."},
                            "paid_calls": None, "cost_usd": None, "tokens_in": None, "tokens_out": None}
            await conn.execute("UPDATE agent_radix.task_context SET execution=$3::jsonb,stage='executed' WHERE tenant_id=$1 AND job_id=$2", tenant, job, json.dumps(executed))
            return executed

        receipt = await run_with_memory(ctx.memory, tenant_id=str(tenant), user_id=user,
            task_key="radix.site_risk", task=task, code_free=free, paid_call=paid)
        await conn.execute("UPDATE agent_radix.task_context SET receipt=$3::jsonb,stage='completed' WHERE tenant_id=$1 AND job_id=$2", tenant, job, json.dumps(receipt))
        return {**result, "receipt": receipt}
