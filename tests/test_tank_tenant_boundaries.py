"""Part A: exercise Tank's real handlers and SQL with two isolated tenants."""
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def boundary(monkeypatch, tmp_path):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("Set POOL_SCHEMA_DATABASE_URL to isolated test Postgres")
    admin = await asyncpg.connect(url)
    db = "boundaries_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{db}"')
    pool = None
    try:
        pool = await asyncpg.create_pool(urlunsplit(urlsplit(url)._replace(path="/" + db)), min_size=1, max_size=2)
        key = uuid.uuid4().hex
        monkeypatch.setenv("DATABASE_URL", url)
        monkeypatch.setenv("LITELLM_MASTER_KEY", uuid.uuid4().hex)
        monkeypatch.setenv("TANK_API_KEY", key)
        monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-fixture")
        monkeypatch.setenv("TANK_REGION", "us-east")
        import main as tank
        import skala
        monkeypatch.setattr(tank, "TANK_API_KEY", key)
        monkeypatch.setattr(tank, "_pool", pool)
        monkeypatch.setattr(tank, "_http", object())
        monkeypatch.setattr(tank, "_agent_keys_synced", True)
        tenants = (uuid.uuid4(), uuid.uuid4())
        packages = {}
        calls = []

        async def run(pkg, payload, ctx):
            calls.append((pkg.id, ctx.tenant_id))
            return dict(payload)

        monkeypatch.setattr(skala, "run_skill", run)
        async with pool.acquire() as conn:
            await conn.execute((ROOT / "tank/schema.sql").read_text())
            for i, tenant in enumerate(tenants):
                skill = f"base.private{i}"
                path = tmp_path / skill
                path.mkdir()
                (path / "skill.yaml").write_text("shared_with: [ghost]\n")
                packages[skill, "1.0.0"] = skala.SkillPackage(
                    skill, "1.0.0", "base", 3, "fixture.boundary", "private fixture",
                    {}, {}, 0.95, path,
                )
                await conn.execute("INSERT INTO tank.skills(id,version,agent,task_type,state) VALUES($1,'1.0.0','base','fixture.boundary','approved')", skill)
                await conn.execute("INSERT INTO tank.agent_skill_submissions(skill_id,version,tenant_id,region,submitted_by_room,package,sha256) VALUES($1,'1.0.0',$2,'us-east','base','{}','fixture')", skill, tenant)
                for _ in range(i + 1):
                    await conn.execute("INSERT INTO tank.evals(tenant_id,task_type,input,expected) VALUES($1,'fixture.boundary',$2::jsonb,'\"secret answer\"')", tenant, json.dumps({"text": f"client secret {i}"}))
                await conn.execute("INSERT INTO tank.transcripts(ledger_id,tenant_id,task_type,messages,content) VALUES($1,$2,'fixture.boundary',$3::jsonb,'private result')", uuid.uuid4(), tenant, json.dumps([{"role": "user", "content": f"client transcript {i}"}]))
            await conn.execute("INSERT INTO tank.skills(id,version,agent,task_type,state) VALUES('base.public','1.0.0','base','fixture.boundary','approved')")
        monkeypatch.setattr(tank, "_packages", packages)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=tank.app), base_url="http://tank", headers={"X-Tank-Key": key}) as client:
            yield SimpleNamespace(tank=tank, pool=pool, client=client, tenants=tenants, calls=calls, key=key)
    finally:
        if pool:
            await pool.close()
        await admin.execute(f'DROP DATABASE "{db}" WITH (FORCE)')
        await admin.close()


@pytest.mark.asyncio
async def test_evals_summary_requires_tenant_and_founder_for_totals(boundary):
    b = boundary
    for i, tenant in enumerate(b.tenants):
        result = await b.client.get("/v1/evals/summary", params={"tenant_id": str(tenant)})
        assert result.status_code == 200
        assert result.json() == [{"task_type": "fixture.boundary", "cases": i + 1, "accepted": 0, "rejected": 0, "manual": i + 1}]
    assert (await b.client.get("/v1/evals/summary")).status_code == 422
    for headers in ({}, {"X-Tervory-Admin": "ordinary-user"}, {"X-Tervory-Role": "founder"}):
        assert (await b.client.get("/v1/evals/summary", params={"all_tenants": True}, headers=headers)).status_code == 404
    result = await b.client.get("/v1/evals/summary", params={"all_tenants": True}, headers={"X-Tervory-Admin": "founder-fixture"})
    assert result.status_code == 200 and result.json()[0]["cases"] == 3


@pytest.mark.asyncio
async def test_skala_private_packages_are_owned_and_founder_gated(boundary):
    b = boundary
    for i, tenant in enumerate(b.tenants):
        result = await b.client.get("/v1/skala", params={"tenant_id": str(tenant)})
        assert result.status_code == 200
        assert {r["id"] for r in result.json()} == {"base.public", f"base.private{i}"}
    assert {r["id"] for r in (await b.client.get("/v1/skala")).json()} == {"base.public"}
    for headers in ({}, {"X-Tervory-Admin": "ordinary-user"}, {"X-Tervory-Role": "founder"}):
        assert (await b.client.get("/v1/skala", params={"all_tenants": True}, headers=headers)).status_code == 404
    result = await b.client.get("/v1/skala", params={"all_tenants": True}, headers={"X-Tervory-Admin": "founder-fixture"})
    assert {r["id"] for r in result.json()} == {"base.public", "base.private0", "base.private1"}


@pytest.mark.asyncio
@pytest.mark.parametrize("caller", [None, "base", "ghost"])
async def test_run_submission_ownership_for_every_caller(boundary, monkeypatch, caller):
    b = boundary
    headers = {}
    if caller:
        key = uuid.uuid4().hex
        monkeypatch.setenv("TANK_KEY_" + caller.upper(), key)
        headers["X-Tank-Key"] = key
    for i, tenant in enumerate(b.tenants):
        body = {"tenant_id": str(tenant), "version": "1.0.0", "input": {"answer": "fixture"}}
        result = await b.client.post(f"/v1/skala/base.private{i}/run", json=body, headers=headers)
        assert result.status_code == 200
        count = len(b.calls)
        for preview in (False, True):
            result = await b.client.post(f"/v1/skala/base.private{1-i}/run", json={**body, "preview": preview}, headers=headers)
            assert result.status_code == 403
            assert len(b.calls) == count
        async with b.pool.acquire() as conn:
            await conn.execute("UPDATE tank.agent_skill_submissions SET region='za' WHERE tenant_id=$1", tenant)
        result = await b.client.post(f"/v1/skala/base.private{i}/run", json=body, headers=headers)
        assert result.status_code == 403 and len(b.calls) == count


@pytest.mark.asyncio
async def test_global_screening_uses_only_approved_masked_platform_examples(boundary, monkeypatch):
    b = boundary
    async with b.pool.acquire() as conn:
        for tenant, status, holdout, source in [
            (b.tank.PLATFORM_TENANT, "checked", False, "allowed"),
            (b.tank.PLATFORM_TENANT, "candidate", False, "unchecked"),
            (b.tank.PLATFORM_TENANT, "checked", True, "holdout"),
            (b.tank.PLATFORM_TENANT, "checked", False, "<html>raw</html>"),
            *[(tenant, "checked", False, "client") for tenant in b.tenants],
        ]:
            await conn.execute("""INSERT INTO tank.gold_examples(tenant_id,region,skill_id,agent,input,expected,status,holdout,source,source_ref,input_hash,checked_by,checked_at)
                VALUES($1,'us-east','base.public','base',$2::jsonb,'\"fixture\"',$3,$4,'fixture',$5,$5,'founder-fixture',now())""",
                tenant, json.dumps({"text": source + " SSN 123-45-6789 email fixture@example.test"}), status, holdout, source)
        cases = await b.tank._screen_cases(conn, "fixture.boundary")
    assert len(cases) == 1
    serialized = json.dumps(cases)
    assert "allowed" in serialized
    for forbidden in ("client", "unchecked", "holdout", "123-45-6789", "fixture@example.test"):
        assert forbidden not in serialized
    sent = []

    async def llm(name, messages, tokens):
        sent.extend(messages)
        return "fixture", 0.0

    async def budget(task):
        return True

    monkeypatch.setattr(b.tank, "_llm", llm)
    monkeypatch.setattr(b.tank, "_shadow_budget_open", budget)
    assert await b.tank._screen_model("fixture", "fixture.boundary", cases, 0.01, 10) == 1.0
    assert "allowed" in json.dumps(sent) and "client" not in json.dumps(sent)
    sent.clear()
    assert await b.tank._screen_model("fixture", "fixture.boundary", [("fixture", [{"role": "user", "content": "<html>raw</html>"}], {})], 0.01, 10) is None
    assert sent == []
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", json.dumps({str(b.tank.PLATFORM_TENANT): []}))
    assert await b.tank._screen_model("fixture", "fixture.boundary", cases, 0.01, 10) is None
    assert sent == []
