"""Real Postgres proof of candidate immutability and approved-only room export."""
import json
import os
import uuid
from pathlib import Path

import asyncpg
import httpx
import pytest

import agent_skills
import skala

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
async def test_schema_export_submission_and_existing_run_guard(monkeypatch, tmp_path):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("Set POOL_SCHEMA_DATABASE_URL to an isolated test Postgres")
    admin = await asyncpg.connect(url)
    db = "agent1_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{db}"')
    pool = None
    try:
        from urllib.parse import urlsplit, urlunsplit
        parts = urlsplit(url)
        pool = await asyncpg.create_pool(urlunsplit(parts._replace(path="/" + db)), min_size=1, max_size=2)
        sql = (ROOT / "tank/schema.sql").read_text()
        async with pool.acquire() as conn:
            await conn.execute(sql)
            await conn.execute(sql)
            assert await conn.fetchval("SELECT count(*) FROM tank.policy WHERE task_type='agent.base.think'") == 1
            assert await conn.fetchval("SELECT auto_promote FROM tank.policy WHERE task_type='agent.base.think'") is False
            await conn.execute("UPDATE tank.policy SET baseline_model='founder-selected' WHERE task_type='agent.base.think'")
            await conn.execute(sql)
            assert await conn.fetchval("SELECT baseline_model FROM tank.policy WHERE task_type='agent.base.think'") == "founder-selected"
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("LITELLM_MASTER_KEY", uuid.uuid4().hex)
        monkeypatch.setenv("TANK_API_KEY", uuid.uuid4().hex)
        import main as tank
        packages = skala.load_packages(ROOT / "tank/skills")
        monkeypatch.setattr(tank, "_pool", pool)
        monkeypatch.setattr(tank, "_packages", packages)
        monkeypatch.setattr(tank, "_http", object())
        monkeypatch.setattr(agent_skills, "SUBMISSIONS", tmp_path / "submissions")
        monkeypatch.setenv("TANK_REGION", "us-east")
        key = uuid.uuid4().hex
        monkeypatch.setenv("TANK_KEY_BASE", key)
        monkeypatch.setenv("TANK_KEY_TIGER", uuid.uuid4().hex)
        await tank.register_packages()
        tenant, other = uuid.uuid4(), uuid.uuid4()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE tank.skills SET state='approved' WHERE id='base.normalize' AND version='1.0.0'")
            await conn.execute("UPDATE tank.skills SET state='retired' WHERE id='base.resolve'")
            before = await conn.fetch("SELECT * FROM tank.skills ORDER BY id,version")
        headers = {"X-Tank-Key": key}
        body = {"tenant_id": str(tenant), "home_region": "us-east", "skill_id": "base.learned.echo", "version": "1.0.0",
                "description": "Echo a checked public field", "instructions": "Return the checked field unchanged.",
                "run_py": "async def run(input, ctx):\n    return input\n", "cases": [
                    *[{"input": {"name": "public " + str(i)}, "expected": {"name": "public " + str(i)}} for i in range(5)],
                    {"input": {"refused": True}, "expected": {"refused": True}, "must_refuse": True}]}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
            exported = await client.get("/v1/agents/base/skills", params={"tenant_id": str(tenant)}, headers=headers)
            assert exported.status_code == 200
            assert [(r["id"], r["version"]) for r in exported.json()["skills"]] == [("base.normalize", "1.0.0")]
            assert exported.json()["skills"][0]["files"]["SKILL.md"].startswith("---\n")
            created = await client.post("/v1/agents/base/skills/candidates", headers=headers, json=body)
            assert created.status_code == 201 and created.json()["state"] == "candidate"
            assert created.json()["submitted_by_room"] == "base"
            duplicate = await client.post("/v1/agents/base/skills/candidates", headers=headers, json={**body, "run_py": "async def run(input, ctx):\n    return {}\n"})
            assert duplicate.status_code == 409
            candidate_run = await client.post("/v1/skala/base.learned.echo/run", headers=headers,
                json={"tenant_id": str(tenant), "input": {}, "version": "1.0.0", "preview": True})
            assert candidate_run.status_code == 403
            exported = await client.get("/v1/agents/base/skills", params={"tenant_id": str(tenant)}, headers=headers)
            assert all(r["id"] != "base.learned.echo" for r in exported.json()["skills"])
            for path, method, payload in [
                ("/v1/agents/tiger/skills", "GET", None),
                ("/v1/agents/base/skills", "GET", None),
                ("/v1/agents/base/skills/candidates", "POST", body),
            ]:
                refused = await client.request(method, path, params={"tenant_id": str(tenant)}, json=payload,
                    headers={"X-Tank-Key": os.environ["TANK_KEY_TIGER"]})
                assert refused.status_code in (401, 403)
        async with pool.acquire() as conn:
            after = await conn.fetch("SELECT * FROM tank.skills WHERE id<>'base.learned.echo' ORDER BY id,version")
            assert before == after
            stored = await conn.fetchrow("SELECT * FROM tank.agent_skill_submissions WHERE skill_id='base.learned.echo'")
            assert stored["tenant_id"] == tenant and stored["submitted_by_room"] == "base"
            assert json.loads(stored["package"])["run.py"] == body["run_py"]
        # Existing lifecycle only: evals, founder source review, then approval.
        evaluated = await tank.run_skill_evals("base.learned.echo", "1.0.0")
        assert evaluated["state"] == "staging"
        from fastapi import HTTPException
        with pytest.raises(HTTPException, match="Review every Python file") as unreviewed:
            await tank.approve_skill("base.learned.echo", "1.0.0", tank.Approval(by="test-founder"))
        assert unreviewed.value.status_code == 409
        review = await tank.review_skill_source("base.learned.echo", "1.0.0", tank.Approval(by="test-founder"))
        assert {file["path"]: file["source"] for file in review["files"]}["run.py"] == body["run_py"]
        await tank.approve_skill("base.learned.echo", "1.0.0", tank.Approval(
            by="test-founder", confirmed=True, review_token=review["review_token"]))
        # Free recovery removes paid capabilities without modifying approved code.
        pkg = packages[("base.learned.echo", "1.0.0")]
        ctx = tank.make_ctx(pkg, tenant)
        ctx.env["BRAVE_API_KEY"] = uuid.uuid4().hex
        task = uuid.uuid4()
        free = tank.SkillRun(tenant_id=tenant, input={"_base_brain_free": True, "_base_brain_task": str(task)}, version="1.0.0")
        await agent_skills.guard_base_run(tank, pkg, free, ctx)
        assert free.input == {} and ctx.task_id == task
        assert "BRAVE_API_KEY" not in ctx.env
        with pytest.raises(HTTPException, match="deferred"):
            await ctx.model([], "base.extract")
        assert "base.learned.echo" in [s["id"] for s in (await agent_skills.export_skills(tank, tenant, "us-east"))["skills"]]
        assert "base.learned.echo" not in [s["id"] for s in (await agent_skills.export_skills(tank, other, "us-east"))["skills"]]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank") as client:
            allowed = await client.post("/v1/skala/base.learned.echo/run", headers=headers,
                json={"tenant_id": str(tenant), "input": {"name": "public field"}, "version": "1.0.0"})
            assert allowed.status_code == 200 and allowed.json()["name"] == "public field"
            refused = await client.post("/v1/skala/base.learned.echo/run", headers=headers,
                json={"tenant_id": str(other), "input": {}, "version": "1.0.0"})
            assert refused.status_code == 403
            hijack = await client.post("/v1/agents/base/skills/candidates", headers=headers,
                json={**body, "tenant_id": str(other), "version": "1.1.0"})
            assert hijack.status_code == 403
            async with pool.acquire() as conn:
                approved_before = await conn.fetchrow("SELECT * FROM tank.skills WHERE id='base.learned.echo' AND version='1.0.0'")
            newer = await client.post("/v1/agents/base/skills/candidates", headers=headers, json={**body, "version": "1.1.0"})
            assert newer.status_code == 201 and newer.json()["state"] == "candidate"
            async with pool.acquire() as conn:
                assert approved_before == await conn.fetchrow("SELECT * FROM tank.skills WHERE id='base.learned.echo' AND version='1.0.0'")
        # Reconstruct source after a restart; preserve the founder's approved state.
        packages.pop(("base.learned.echo", "1.0.0"))
        packages.pop(("base.learned.echo", "1.1.0"))
        await agent_skills.restore(tank)
        assert await tank.skill_state("base.learned.echo", "1.0.0") == "approved"
    finally:
        if pool:
            await pool.close()
        await admin.execute(f'DROP DATABASE "{db}" WITH (FORCE)')
        await admin.close()
