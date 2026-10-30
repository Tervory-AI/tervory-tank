"""PR #334 review regressions: real SQL/handlers, two tenants, stubbed spend."""
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
import skala

from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder, policy, request  # noqa: F401


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["Tools a < b LLC", "where cost < budget"])
@pytest.mark.parametrize("path", ["code", "skill", "paid"])
async def test_plain_comparisons_keep_receipts_and_transcripts(ladder, text, path):  # noqa: F811
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, **({"model": "luna", "rung": 1} if path == "paid" else {"confidence_floor": 0}))
        payload = {"name": text}
        if path == "skill":
            result = await b.tank._run_one_skill("base.normalize", b.tank.SkillRun(
                tenant_id=tenant, version="1.0.0", input=payload), None)
            ledger_id = uuid.UUID(result["_ledger_id"])
        else:
            result = await b.tank.run_route(request(b, tenant, text=text if path == "paid" else json.dumps(payload)))
            ledger_id = result.ledger_id
        async with b.pool.acquire() as conn:
            row = await conn.fetchrow("""SELECT l.rung,l.cost_usd,t.messages FROM tank.ledger l
                JOIN tank.transcripts t ON t.ledger_id=l.id AND t.tenant_id=l.tenant_id
                WHERE l.id=$1 AND l.tenant_id=$2""", ledger_id, tenant)
            assert row and row["rung"] == (1 if path == "paid" else 3)
            assert text in row["messages"]
            if path != "paid":
                assert row["cost_usd"] == 0
    assert len(b.sent) == (2 if path == "paid" else 0)
    if path == "paid":
        assert all(call["messages"][-1]["content"] == text for call in b.sent)


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["flag rows where qty <min and price >max",
                                 "flag rows where qty <input and price >max",
                                 "flag rows where qty <br and price >max"])
async def test_comparison_prompt_reaches_provider_unchanged(ladder, text):  # noqa: F811
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1)
        result = await b.tank.run_route(request(b, tenant, text=text))
        assert b.sent[-1]["messages"][-1]["content"] == text
        async with b.pool.acquire() as conn:
            saved = await conn.fetchval("SELECT messages FROM tank.transcripts WHERE ledger_id=$1 AND tenant_id=$2", result.ledger_id, tenant)
            assert json.loads(saved)[0]["content"] == text


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["code", "skill", "paid"])
async def test_unmaskable_input_refused_before_execution_with_receipt(ladder, monkeypatch, path):  # noqa: F811
    from fastapi import HTTPException
    b = ladder
    executed = AsyncMock(side_effect=AssertionError("skill must not execute"))
    monkeypatch.setattr(skala, "run_skill", executed)
    def unavailable(value):
        raise ValueError("fixture masker unavailable")
    monkeypatch.setattr(b.tank, "_screen_mask", unavailable)
    for tenant in b.tenants:
        await policy(b, tenant, **({"model": "luna", "rung": 1} if path == "paid" else {"confidence_floor": 0}))
        with pytest.raises(HTTPException) as refused:
            if path == "skill":
                await b.tank._run_one_skill("base.normalize", b.tank.SkillRun(tenant_id=tenant, version="1.0.0", input={"name": "private fixture"}), None)
            else:
                await b.tank.run_route(request(b, tenant, text="private fixture"))
        assert refused.value.status_code == 422
        assert refused.value.detail["error"] == "Input could not be masked; no execution was started"
        receipt = refused.value.detail["receipt"]
        assert receipt["cost_usd"] == 0
        async with b.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", uuid.UUID(receipt["ledger_id"]), tenant)
            assert row["outcome"] == "failed" and row["cost_usd"] == 0
            assert "private fixture" not in await conn.fetchval("SELECT messages FROM tank.transcripts WHERE ledger_id=$1", row["id"])
    assert not b.sent and executed.await_count == 0


@pytest.mark.asyncio
async def test_response_mask_failure_cannot_abort_billed_request(ladder, monkeypatch):  # noqa: F811
    import training
    b = ladder
    original = b.tank._screen_mask
    def output_unavailable(value):
        if isinstance(value, str) and "paid fixture" in value:
            raise ValueError("fixture output cannot be masked")
        return original(value)
    monkeypatch.setattr(b.tank, "_screen_mask", output_unavailable)
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, cache_scope="tenant")
        result = await b.tank.run_route(request(b, tenant, text="plain request"))
        assert result.content == '{"answer": "paid fixture"}'
        async with b.pool.acquire() as conn:
            assert await conn.fetchval("SELECT content FROM tank.transcripts WHERE ledger_id=$1 AND tenant_id=$2", result.ledger_id, tenant) == "[omitted: masking unavailable]"
            assert await conn.fetchval("SELECT count(*) FROM tank.route_cache WHERE tenant_id=$1", tenant) == 0
            await conn.execute("UPDATE tank.ledger SET accept_after=now()-interval '1 second' WHERE id=$1 AND tenant_id=$2", result.ledger_id, tenant)
            await training.collect_ledger(conn, tenant)
            assert await conn.fetchval("SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1", tenant) == 0
    assert len(b.sent) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["candidate", "retired"])
async def test_unapproved_pin_escalates_without_executing_or_using_cache(ladder, monkeypatch, state):  # noqa: F811
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, confidence_floor=0, cache_scope="tenant")
        assert (await b.tank.run_route(request(b, tenant))).rung == 3
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET state=$1 WHERE id='base.normalize'", state)
    executed = AsyncMock(side_effect=AssertionError("unapproved skill must not run"))
    monkeypatch.setattr(b.tank, "_run_code_candidate", executed)
    for tenant in b.tenants:
        result = await b.tank.run_route(request(b, tenant))
        assert result.rung == 2 and result.model == "luna"
        assert result.escalation[0]["reason"] == "skill_not_approved"
        async with b.pool.acquire() as conn:
            attempt = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", uuid.UUID(result.escalation[0]["ledger_id"]), tenant)
            assert attempt["rung"] == 3 and attempt["cost_usd"] == 0
    assert executed.await_count == 0 and len(b.sent) == 2


@pytest.mark.asyncio
async def test_fresh_seeds_only_pin_approved_versions_and_preserve_overrides(ladder):  # noqa: F811
    b = ladder
    sql = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
    refs = {"base.normalize": "1.0.0", "base.extract": "2.0.0", "base.business_data": "2.0.0"}
    async with b.pool.acquire() as conn:
        # Reproduce schema installation with registered candidate versions.
        await conn.execute("UPDATE tank.skills SET state='candidate' WHERE id=ANY($1::text[])", list(refs))
        await conn.execute("DELETE FROM tank.policy_seeds")
        await conn.execute("DELETE FROM tank.policy WHERE task_type='base.normalize' AND tenant_id IS NULL")
        await conn.execute(sql)
        rows = await conn.fetch("SELECT task_type,model,rung FROM tank.policy WHERE task_type=ANY($1::text[]) AND tenant_id IS NULL", list(refs))
        assert len(rows) == 3 and all(r["rung"] == 3 and r["model"] == "luna" for r in rows)
    for tenant in b.tenants:
        for task in refs:
            result = await b.tank.run_route(request(b, tenant, task=task))
            assert result.rung == 2 and result.model == "luna"
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET state='approved' WHERE id=ANY($1::text[])", list(refs))
        await conn.execute("DELETE FROM tank.policy_seeds")
        await conn.execute("DELETE FROM tank.policy WHERE task_type='base.normalize' AND tenant_id IS NULL")
        await conn.execute(sql)
        for task, version in refs.items():
            assert await conn.fetchval("SELECT model FROM tank.policy WHERE task_type=$1 AND tenant_id IS NULL", task) == f"skill:{task}@{version}"
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1)
    async with b.pool.acquire() as conn:
        before = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        await conn.execute(sql)
        assert before == await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")


@pytest.mark.asyncio
async def test_startup_logs_every_unapproved_policy_pin(ladder, monkeypatch, caplog):  # noqa: F811
    from types import SimpleNamespace
    b = ladder
    for i, tenant in enumerate(b.tenants):
        # Routing strips policy whitespace; the startup audit must do so too.
        await policy(b, tenant, model="skill:base.extract@2.0.0" if i == 0 else " skill:base.extract@2.0.0 ")
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET state='candidate' WHERE id='base.extract'")
        await conn.execute("UPDATE tank.policy SET model='skill:missing.package@1.0.0' WHERE task_type='reason.brief' AND tenant_id IS NULL")
    monkeypatch.setattr(b.tank.asyncpg, "create_pool", AsyncMock(return_value=b.pool))
    monkeypatch.setattr(b.tank.aioredis, "from_url", lambda *a, **k: SimpleNamespace(ping=AsyncMock()))
    monkeypatch.setattr(b.tank, "_batch_loop", AsyncMock())
    await b.tank._startup()
    await b.tank._batch_task
    messages = [r.getMessage() for r in caplog.records if "Policy pins non-approved skill" in r.getMessage()]
    assert len(messages) == 4
    assert all(any(str(tenant) in m and "skill:base.extract@2.0.0" in m for m in messages) for tenant in b.tenants)
    assert any("reason.brief" in m and "skill:missing.package@1.0.0" in m and "missing" in m for m in messages)
    assert any("task=base.extract tenant=platform" in m for m in messages)


@pytest.mark.asyncio
async def test_explicit_html_is_refused_before_provider_with_receipt(ladder):  # noqa: F811
    from fastapi import HTTPException
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1)
        with pytest.raises(HTTPException) as refused:
            await b.tank.run_route(request(b, tenant, text="<p>visible</p><script>raw</script>"))
        assert refused.value.status_code == 422
        receipt = refused.value.detail["receipt"]
        async with b.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", uuid.UUID(receipt["ledger_id"]), tenant)
            assert row["outcome"] == "failed" and row["cost_usd"] == 0
    assert not b.sent


@pytest.mark.asyncio
async def test_existing_unapproved_seed_repair_is_one_time_and_tenant_safe(ladder):  # noqa: F811
    b = ladder
    sql = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
    for tenant in b.tenants:
        await policy(b, tenant, model="skill:base.extract@2.0.0")
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET state='candidate' WHERE id='base.extract'")
        await conn.execute("DELETE FROM tank.policy_seeds WHERE name='one-door-approved-seeds-v2'")
        overrides = await conn.fetch("SELECT * FROM tank.policy WHERE tenant_id=ANY($1::uuid[]) ORDER BY tenant_id", list(b.tenants))
        await conn.execute(sql)
        assert await conn.fetchval("SELECT model FROM tank.policy WHERE tenant_id IS NULL AND task_type='base.extract'") == "luna"
        assert await conn.fetchval("SELECT model FROM tank.policy WHERE tenant_id IS NULL AND task_type='base.normalize'") == "skill:base.normalize@1.0.0"
        assert overrides == await conn.fetch("SELECT * FROM tank.policy WHERE tenant_id=ANY($1::uuid[]) ORDER BY tenant_id", list(b.tenants))
        before = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        await conn.execute(sql)
        assert before == await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
