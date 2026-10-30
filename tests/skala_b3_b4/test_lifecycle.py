"""Offline B3/B4 contracts; real disposable Postgres, stubbed model transport."""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import HTTPException

import skala
import skala_probation
import skala_revalidation
from gold import PLATFORM_TENANT

ROOT = Path(__file__).resolve().parents[2]
TASK = "test.b3.write"
TENANT = UUID("00000000-0000-0000-0000-000000000011")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def package(tmp_path, name="base.b3", version="1.0.0", task=TASK, code=False):
    path = tmp_path / name / version
    (path / "evals").mkdir(parents=True)
    meta = {"id": name, "version": version, "agent": "base", "rung": 3 if code else 1,
            "task_type": task, "eval_threshold": 1.0}
    (path / "skill.yaml").write_text(json.dumps(meta))
    source = '''async def run(payload, ctx):
    if not payload.get("text"):
        return {"refused": True}
    text = await ctx.model([{"role": "user", "content": payload["text"]}], "TASK")
    return {"text": text}
'''.replace('"TASK"', repr(task))
    if code:
        source = 'async def run(payload, ctx):\n    return {"text": "good"}\n'
    (path / "run.py").write_text(source)
    cases = [{"input": {"text": word}, "model": "good", "expected": {"text": "good"}, "tolerance": "contains"}
             for word in ("one", "two", "three", "four")]
    cases.append({"input": {}, "expected": {"refused": True}, "must_refuse": True})
    (path / "evals/cases.jsonl").write_text("\n".join(json.dumps(c) for c in cases))
    return skala._parse_package(path / "skill.yaml", path)


@pytest_asyncio.fixture
async def env(monkeypatch):
    dsn = os.environ.get("SKALA_B3_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Disposable cloud Postgres is required")
    assert urlsplit(dsn).hostname in {"skala-b3-pg", "localhost", "127.0.0.1"}
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("TANK_API_KEY", "")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "")
    import main as tank
    db = await asyncpg.create_pool(dsn, min_size=1, max_size=6)
    async with db.acquire() as conn:
        await conn.execute((ROOT / "tank/schema.sql").read_text())
        await conn.execute((ROOT / "tank/schema.sql").read_text())
        await conn.execute("TRUNCATE tank.skill_revalidations,tank.skill_evals,tank.skill_approvals,tank.agent_skill_submissions,tank.skills CASCADE")
        await conn.execute("DELETE FROM tank.policy WHERE task_type LIKE $1", "test.b3.%")
        await conn.execute("DELETE FROM tank.ledger WHERE tenant_id=$1 AND task_type LIKE $2", PLATFORM_TENANT, "test.b3.%")
    monkeypatch.setattr(tank, "_pool", db)
    monkeypatch.setattr(tank, "_packages", {})
    monkeypatch.setattr(skala, "_run_cache", {})
    async def forbidden(*args, **kwargs):
        raise AssertionError("No router, shadow or judge call is allowed during revalidation")
    monkeypatch.setattr(tank, "run_route", forbidden)
    monkeypatch.setattr(tank, "_shadow", forbidden)
    calls = []
    async def model(name, messages, max_tokens, *, receipt):
        calls.append((name, messages, max_tokens))
        receipt.update(model=name, cost=0, tokens_in=2, tokens_out=1)
        return ("wrong" if name == "astra" else "good"), 0.0
    monkeypatch.setattr(tank, "_llm", model)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: (_ for _ in ()).throw(AssertionError("No network")))) as http:
        monkeypatch.setattr(tank, "_http", http)
        yield SimpleNamespace(tank=tank, db=db, calls=calls)
    await db.close()


async def seed(env, pkg, state="approved", approved_at=START):
    env.tank._packages[(pkg.id, pkg.version)] = pkg
    await env.db.execute(
        """INSERT INTO tank.skills(id,version,agent,rung,task_type,state,eval_threshold,cases,approved_at,present)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,true)""",
        pkg.id, pkg.version, pkg.agent, pkg.rung, pkg.task_type, state,
        pkg.eval_threshold, len(pkg.cases), approved_at if state != "candidate" else None)


async def policy(env, model="luna", task=TASK, tenant=None):
    return await env.tank.put_policy(task, env.tank.PolicyRow(task_type=task, model=model, tenant_id=tenant))


async def jobs(env):
    return await env.db.fetch("SELECT * FROM tank.skill_revalidations WHERE tenant_id=$1 ORDER BY queued_at,id", PLATFORM_TENANT)


@pytest.mark.asyncio
async def test_upsert_runs_exactly_affected_approved_skills_once(env, tmp_path, monkeypatch):
    await policy(env)
    for pkg, state in [(package(tmp_path, name="base.one"), "approved"),
                       (package(tmp_path, name="base.two"), "approved"),
                       (package(tmp_path, name="base.other", task="test.b3.other"), "approved"),
                       (package(tmp_path, name="base.pending"), "candidate"),
                       (package(tmp_path, name="base.pure", task=None, code=True), "approved")]:
        await seed(env, pkg, state)
    await policy(env)  # Same-model upsert does not spend on evals.
    assert await jobs(env) == []
    await policy(env, "sol")
    assert {r["skill_id"] for r in await jobs(env)} == {"base.one", "base.two"}
    handler = AsyncMock(wraps=env.tank.run_skill_evals)
    monkeypatch.setattr(env.tank, "run_skill_evals", handler)
    counts = await asyncio.gather(skala_revalidation.drain(env.tank), skala_revalidation.drain(env.tank))
    assert sum(counts) == 2 and handler.await_count == 2
    assert {call.args[0] for call in handler.await_args_list} == {"base.one", "base.two"}
    assert len(env.calls) == 8 and {c[0] for c in env.calls} == {"sol"}
    for row in await jobs(env):
        assert row["completed_at"] and row["eval_id"] and not row["error"]
        skill = await env.db.fetchrow("SELECT * FROM tank.skills WHERE id=$1 AND version=$2", row["skill_id"], row["version"])
        validation = json.loads(skill["models_validated"])[0]
        assert validation["model"] == "sol" and validation["validated"] is True
        assert skill["state"] == "approved" and skill["last_eval_score"] == 1
        result = await env.db.fetchrow("SELECT * FROM tank.skill_evals WHERE id=$1", row["eval_id"])
        assert result["model"] == "sol" and result["revalidation_id"] == row["id"]
    assert await skala_revalidation.drain(env.tank) == 0 and len(env.calls) == 8


@pytest.mark.asyncio
async def test_failure_demotes_and_later_passing_model_never_auto_approves(env, tmp_path):
    await policy(env)
    pkg = package(tmp_path)
    await seed(env, pkg)
    await policy(env, "astra")
    await policy(env, "sol")  # Each transaction's model is pinned despite the later swap.
    assert await skala_revalidation.drain(env.tank) == 2
    assert [c[0] for c in env.calls] == ["astra"] * 4 + ["sol"] * 4
    row = await env.db.fetchrow("SELECT * FROM tank.skills WHERE id=$1 AND version=$2", pkg.id, pkg.version)
    validated = json.loads(row["models_validated"])
    assert [(v["model"], v["validated"]) for v in validated] == [("astra", False), ("sol", True)]
    assert validated[0]["score"] == 0.2  # Saved "good" fixture outputs were not reused.
    assert row["state"] == "staging" and row["last_eval_score"] == 1
    assert await env.db.fetchval("SELECT count(*) FROM tank.skill_approvals WHERE tenant_id=$1", PLATFORM_TENANT) == 0
    proof = os.environ.get("SKALA_B3_PROOF_DIR")
    if proof:
        folder = Path(proof)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "model-results.json").write_text(json.dumps({"models_validated": validated, "state": row["state"],
            "model_calls": len(env.calls)}, default=str, indent=2) + "\n")


@pytest.mark.asyncio
async def test_graduation_and_policy_rollback_are_captured(env, tmp_path):
    await policy(env)
    await seed(env, package(tmp_path))
    await env.db.execute("UPDATE tank.policy SET candidate_model=$2 WHERE task_type=$1 AND tenant_id IS NULL", TASK, "sol")
    before = dict(await env.db.fetchrow("SELECT * FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", TASK))
    move = env.tank.graduate.Move("promote", {**before, "model": "sol", "rung": 1}, "offline graduation")
    async with env.db.acquire() as conn:
        async with conn.transaction():
            await env.tank._apply_move(conn, move, before, "founder")
    assert [(r["old_model"], r["model"]) for r in await jobs(env)] == [("luna", "sol")]
    before = dict(await env.db.fetchrow("SELECT * FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", TASK))
    move = env.tank.graduate.Move("rollback", {**before, "model": "luna", "rung": 1}, "offline rollback")
    async with env.db.acquire() as conn:
        async with conn.transaction():
            await env.tank._apply_move(conn, move, before, "founder")
    assert [(r["old_model"], r["model"]) for r in await jobs(env)] == [("luna", "sol"), ("sol", "luna")]
    assert await skala_revalidation.drain(env.tank) == 2 and len(env.calls) == 8


@pytest.mark.asyncio
async def test_rolled_back_policy_transaction_creates_no_eval(env, tmp_path):
    await policy(env)
    await seed(env, package(tmp_path))
    async with env.db.acquire() as conn:
        transaction = conn.transaction()
        await transaction.start()
        await conn.execute("UPDATE tank.policy SET model=$2 WHERE task_type=$1 AND tenant_id IS NULL", TASK, "sol")
        assert await conn.fetchval("SELECT count(*) FROM tank.skill_revalidations WHERE tenant_id=$1", PLATFORM_TENANT) == 1
        await transaction.rollback()
    assert await jobs(env) == [] and await skala_revalidation.drain(env.tank) == 0
    assert env.calls == []


@pytest.mark.asyncio
async def test_tenant_override_compares_effective_default_and_records_its_scope(env, tmp_path):
    await policy(env)
    await seed(env, package(tmp_path))
    await policy(env, tenant=TENANT)
    assert await jobs(env) == []
    await policy(env, "sol", tenant=TENANT)
    assert (await jobs(env))[0]["policy_tenant_id"] == TENANT
    await skala_revalidation.drain(env.tank)
    data = await env.db.fetchval("SELECT models_validated FROM tank.skills WHERE id=$1 AND version=$2", "base.b3", "1.0.0")
    assert json.loads(data)[0]["policy_tenant_id"] == str(TENANT)
    assert await env.db.fetchval("SELECT count(*) FROM tank.ledger WHERE tenant_id=$1 AND skill=$2", TENANT, "base.b3@1.0.0#preview") == 0


@pytest.mark.asyncio
async def test_graduation_to_code_calls_no_model(env, tmp_path):
    await policy(env)
    await seed(env, package(tmp_path))
    code = package(tmp_path, name="base.code", task=None, code=True)
    await seed(env, code)
    await env.tank.put_policy(TASK, env.tank.PolicyRow(task_type=TASK, model="skill:base.code@1.0.0", rung=3))
    assert await skala_revalidation.drain(env.tank) == 1
    assert env.calls == []
    row = await env.db.fetchrow("SELECT * FROM tank.skills WHERE id=$1 AND version=$2", "base.b3", "1.0.0")
    assert row["state"] == "approved" and json.loads(row["models_validated"])[0]["validated"]


@pytest.mark.parametrize("days,allowed", [(29, False), (30, True)])
def test_frozen_clean_window(days, allowed):
    ok, at = skala_probation.clean_window(START, None, None, START + timedelta(days=days))
    assert ok is allowed and at == START + timedelta(days=30)


@pytest.mark.parametrize("failure,rollback,days,allowed", [
    (15, None, 44, False), (15, None, 45, True),
    (None, 20, 49, False), (None, 20, 50, True), (15, 20, 45, False),
])
def test_failure_or_founder_rollback_resets_the_clean_window(failure, rollback, days, allowed):
    failed_at = START + timedelta(days=failure) if failure is not None else None
    rollback_at = START + timedelta(days=rollback) if rollback is not None else None
    assert skala_probation.clean_window(START, failed_at, rollback_at, START + timedelta(days=days))[0] is allowed


@pytest.mark.asyncio
async def test_retire_day_29_refused_day_30_allowed_files_kept_and_rollback_works(env, tmp_path):
    old = package(tmp_path, version="1.0.0")
    newer = package(tmp_path, version="2.0.0")
    await seed(env, old, "staging", START - timedelta(days=1))
    await seed(env, newer, "approved", START)
    source = (old.path / "run.py").read_bytes()
    with pytest.raises(HTTPException) as error:
        await skala.retire_version(env.db, old.id, old.version, "founder", now=START + timedelta(days=29))
    assert error.value.status_code == 409 and error.value.detail["code"] == "retirement_probation"
    result = await skala.retire_version(env.db, old.id, old.version, "founder", now=START + timedelta(days=30))
    assert result["state"] == "retired" and (old.path / "run.py").read_bytes() == source
    assert (old.path / "evals/cases.jsonl").is_file()
    await skala.change_version(env.db, old, "founder", "rollback", region="us-east", confirmed=True)
    rows = await env.db.fetch("SELECT version,state FROM tank.skills WHERE id=$1", old.id)
    assert {r["version"]: r["state"] for r in rows} == {"1.0.0": "approved", "2.0.0": "staging"}
    assert await env.db.fetchval("SELECT count(*) FROM tank.skill_approvals WHERE tenant_id=$1 AND skill_id=$2 AND action='rollback'", PLATFORM_TENANT, old.id) == 1


@pytest.mark.asyncio
async def test_new_approval_does_not_retire_any_version(env, tmp_path):
    old = package(tmp_path, version="1.0.0")
    newer = package(tmp_path, version="2.0.0")
    await seed(env, old)
    await seed(env, newer, "staging")
    async with env.db.acquire() as conn:
        async with conn.transaction():
            await skala.lock_approvals(conn)
            await skala.promote(conn, newer, "founder", {})
    assert await env.db.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2", old.id, old.version) == "staging"
    await skala.change_version(env.db, old, "founder", "rollback", region="us-east", confirmed=True)
    assert await env.db.fetchval("SELECT state FROM tank.skills WHERE id=$1 AND version=$2", old.id, old.version) == "approved"


@pytest.mark.asyncio
async def test_pending_revalidation_blocks_retirement_even_after_30_days(env, tmp_path):
    await policy(env)
    old = package(tmp_path, version="1.0.0")
    newer = package(tmp_path, version="2.0.0")
    await seed(env, old, "staging")
    await seed(env, newer)
    await policy(env, "sol")
    with pytest.raises(HTTPException) as error:
        await skala.retire_version(env.db, old.id, old.version, "founder", now=START + timedelta(days=60))
    assert error.value.detail["pending_revalidation"] is True
    await skala_revalidation.drain(env.tank)
    assert (await skala.retire_version(env.db, old.id, old.version, "founder", now=START + timedelta(days=60)))["state"] == "retired"


@pytest.mark.asyncio
async def test_missing_package_is_failed_without_spending(env, tmp_path):
    await policy(env)
    pkg = package(tmp_path)
    await seed(env, pkg)
    await policy(env, "sol")
    env.tank._packages.clear()
    assert await skala_revalidation.drain(env.tank) == 1
    row = await env.db.fetchrow("SELECT * FROM tank.skills WHERE id=$1 AND version=$2", pkg.id, pkg.version)
    assert row["state"] == "staging" and not json.loads(row["models_validated"])[0]["validated"]
    assert env.calls == [] and (await jobs(env))[0]["error"] == "eval_gate_failed"


@pytest.mark.asyncio
async def test_failed_transport_retains_cost_without_exposing_error(env, tmp_path, monkeypatch):
    await policy(env)
    await seed(env, package(tmp_path))
    await policy(env, "sol")
    async def broken(name, messages, max_tokens, *, receipt):
        receipt.update(cost=0.01)
        raise RuntimeError("private transport response")
    monkeypatch.setattr(env.tank, "_llm", broken)
    await skala_revalidation.drain(env.tank)
    result = await env.db.fetchrow("SELECT * FROM tank.skill_evals WHERE revalidation_id=$1", (await jobs(env))[0]["id"])
    assert float(result["cost_usd"]) == 0.04
    assert "private transport response" not in result["details"]
    assert float(await env.db.fetchval("SELECT sum(cost_usd) FROM tank.ledger WHERE tenant_id=$1 AND task_type=$2", PLATFORM_TENANT, TASK)) == 0.04


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["failed_eval", "rollback"])
async def test_database_probation_uses_failure_and_rollback_history(env, tmp_path, event):
    old, newer = package(tmp_path), package(tmp_path, version="2.0.0")
    await seed(env, old, "staging")
    await seed(env, newer)
    at = START + timedelta(days=15)
    if event == "failed_eval":
        await env.db.execute("INSERT INTO tank.skill_evals(skill_id,version,score,passed,total,ran_at,details) VALUES($1,$2,.8,4,5,$3,'[]'::jsonb)", newer.id, newer.version, at)
    else:
        await env.db.execute("INSERT INTO tank.skill_approvals(tenant_id,skill_id,version,action,acted_by,acted_at) VALUES($1,$2,$3,'rollback','founder',$4)", PLATFORM_TENANT, old.id, old.version, at)
    with pytest.raises(HTTPException):
        await skala.retire_version(env.db, old.id, old.version, "founder", now=START + timedelta(days=44))
    assert (await skala.retire_version(env.db, old.id, old.version, "founder", now=START + timedelta(days=45)))["state"] == "retired"


@pytest.mark.asyncio
async def test_background_worker_drains_policy_swap_and_stops_before_pool(env, tmp_path, monkeypatch):
    from fastapi import FastAPI
    app = FastAPI()
    closed = []
    async def close_pool():
        closed.append(True)
    app.router.on_shutdown.append(close_pool)
    skala_revalidation.install(app, env.tank)
    await policy(env)
    await seed(env, package(tmp_path))
    await policy(env, "astra")
    # A superseded staging version exposes the same existing rollback control.
    await seed(env, package(tmp_path, name="base.history", task=None, code=True), "staging")
    await seed(env, package(tmp_path, name="base.history", version="2.0.0", task=None, code=True))
    async with app.router.lifespan_context(app):
        async with asyncio.timeout(5):
            while not (await jobs(env))[0]["completed_at"]:
                await asyncio.sleep(.01)
        row = await env.db.fetchrow("SELECT * FROM tank.skills WHERE id=$1 AND version=$2", "base.b3", "1.0.0")
        assert row["state"] == "staging" and float(row["last_eval_score"]) == .2
        proof = os.environ.get("SKALA_B3_PROOF_DIR")
        if proof:
            folder = Path(proof)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "skills.json").write_text(json.dumps(await env.tank.list_skills(), default=str, indent=2) + "\n")
    assert closed == [True] and len(env.calls) == 4
