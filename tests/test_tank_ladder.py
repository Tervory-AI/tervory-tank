"""Foreground ladder and learning proof on real SQL, with two tenants and no paid calls."""
import json

import httpx
import pytest
import pytest_asyncio

import skala
from test_tank_tenant_boundaries import boundary  # noqa: F401 -- shared isolated Postgres fixture

REAL_RUN = skala.run_skill


@pytest_asyncio.fixture
async def ladder(boundary, monkeypatch):  # noqa: F811 -- pytest fixture injection
    b = boundary
    monkeypatch.setattr(skala, "run_skill", REAL_RUN)
    monkeypatch.setattr(b.tank, "_packages", skala.load_packages())
    await b.tank.register_packages()
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET state='approved' WHERE id IN ('base.normalize','base.extract')")
        # The fixture explicitly approves and selects code. Fresh production seeds
        # leave unapproved versions on the automatic Luna fallback.
        await conn.execute("""UPDATE tank.policy SET model='skill:'||task_type||'@'||
            CASE task_type WHEN 'base.normalize' THEN '1.0.0' ELSE '2.0.0' END
            WHERE tenant_id IS NULL AND task_type IN ('base.normalize','base.extract')""")
        await conn.execute("UPDATE tank.policy SET cache_scope='none' WHERE task_type='base.normalize'")
    b.sent = []

    class Provider:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            b.sent.append(kwargs["json"])
            return httpx.Response(200, headers={"content-type": "application/json", "x-litellm-response-cost": "0.001"},
                json={"choices": [{"message": {"content": json.dumps({"answer": "paid fixture"})}}], "usage": {"prompt_tokens": 12, "completion_tokens": 6}},
                request=httpx.Request("POST", url))

    monkeypatch.setattr(b.tank.httpx, "AsyncClient", Provider)
    return b


def request(b, tenant, *, task="base.normalize", text=None, **extra):
    payload = {"name": "Fixture Tools LLC", "address": "", "city": "Boston", "state": "MA", "zip": "02108", "phone": "6175550100"}
    return b.tank.RouteRequest(tenant_id=tenant, agent="base", task_type=task,
        messages=[b.tank.Message(role="user", content=text or json.dumps(payload))], **extra)


async def policy(b, tenant, **values):
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.policy SELECT (jsonb_populate_record(NULL::tank.policy,
            to_jsonb(p)||$2::jsonb||jsonb_build_object('tenant_id',$1::uuid))).*
            FROM tank.policy p WHERE task_type='base.normalize' AND tenant_id IS NULL""", tenant, json.dumps(values))


@pytest.mark.asyncio
async def test_rung_three_receipts_transcripts_and_direct_skill_runs(ladder):
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, confidence_floor=0)
        result = await b.tank.run_route(request(b, tenant))
        assert result.rung == 3 and result.cost_usd == 0 and not b.sent
        assert json.loads(result.content)["match_key"]
        async with b.pool.acquire() as conn:
            ledger = await conn.fetchrow("SELECT * FROM tank.ledger WHERE id=$1 AND tenant_id=$2", result.ledger_id, tenant)
            transcript = await conn.fetchrow("SELECT * FROM tank.transcripts WHERE ledger_id=$1 AND tenant_id=$2", result.ledger_id, tenant)
            assert ledger["rung"] == 3 and ledger["cost_usd"] == 0 and transcript
        direct = await b.tank._run_one_skill("base.normalize", b.tank.SkillRun(tenant_id=tenant, input={"name": "Fixture"}, version="1.0.0"), None)
        assert direct["_receipt"]["rung"] == 3 and direct["_receipt"]["cost_usd"] == 0
        assert direct["_ledger_id"] != str(result.ledger_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["low_confidence", "not_answerable", "skill_error"])
async def test_code_escalates_with_receipt_and_no_raw_html(ladder, monkeypatch, kind):
    b = ladder

    async def code(*args):
        if kind == "skill_error":
            raise RuntimeError("fixture exception")
        return json.dumps({"confidence": 0.1} if kind == "low_confidence" else {"answerable": False}), 0

    monkeypatch.setattr(b.tank, "_run_code_candidate", code)
    for tenant in b.tenants:
        result = await b.tank.run_route(request(b, tenant, text=json.dumps({"text": "visible", "html": "<p>raw</p><script>secret</script>"})))
        assert result.rung == 2 and result.model == "luna"
        assert result.escalation[0]["reason"] == kind
        sent = json.dumps(b.sent[-1])
        assert "visible" in sent and "<" not in sent and "secret" not in sent and "raw" not in sent
        async with b.pool.acquire() as conn:
            rows = await conn.fetch("SELECT rung,cost_usd,escalation FROM tank.ledger WHERE tenant_id=$1 ORDER BY ts", tenant)
            assert [r["rung"] for r in rows] == [3, 2]
            assert rows[0]["cost_usd"] == 0 and json.loads(rows[1]["escalation"])[0]["to_rung"] == 2


@pytest.mark.asyncio
async def test_exact_semantic_cache_tenant_matter_policy_and_rejection(ladder):
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, model="haiku", rung=1, cache_scope="platform", semantic_cache=True, matter_matching=True)
    a, other = b.tenants
    first = await b.tank.run_route(request(b, a, text="Please summarize the fixture", case_ref="matter-a"))
    exact = await b.tank.run_route(request(b, a, text="Please summarize the fixture", case_ref="matter-a"))
    semantic = await b.tank.run_route(request(b, a, text="Summarise the fixture", case_ref="matter-a"))
    assert first.rung == 1 and exact.rung == semantic.rung == 4 and len(b.sent) == 1
    assert exact.ledger_id != first.ledger_id and exact.cost_usd == 0
    assert (await b.tank.run_route(request(b, other, text="Summarise the fixture", case_ref="matter-a"))).rung == 1
    assert (await b.tank.run_route(request(b, a, text="Summarise the fixture", case_ref="matter-b"))).rung == 1
    assert (await b.tank.run_route(request(b, a, text="Summarise not the fixture", case_ref="matter-a"))).rung == 1
    assert (await b.tank.run_route(request(b, a, text="Summarise the fixture"))).rung == 1
    assert (await b.tank.run_route(request(b, a, text="Please summarize the fixture"))).rung == 1  # no matter: semantic off
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.policy SET system_prompt='New instructions',updated_at=now() WHERE tenant_id=$1", a)
    assert (await b.tank.run_route(request(b, a, text="Please summarize the fixture", case_ref="matter-a"))).rung == 1
    await b.tank.ledger_feedback(first.ledger_id, b.tank.Feedback(tenant_id=a, feedback="rejected"))
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.route_cache WHERE tenant_id=$1", a) == 0
        assert await conn.fetchval("SELECT count(*) FROM tank.route_cache WHERE tenant_id=$1", other) == 1


@pytest.mark.asyncio
async def test_acceptance_window_negative_pairs_and_shadow_are_tenant_local(ladder):
    import training
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, confidence_floor=0)
        result = await b.tank.run_route(request(b, tenant))
        async with b.pool.acquire() as conn:
            await training.collect_ledger(conn, tenant)
            assert await conn.fetchval("SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1", tenant) == 0
            await conn.execute("UPDATE tank.ledger SET accept_after=now()-interval '1 second' WHERE tenant_id=$1 AND id=$2", tenant, result.ledger_id)
            await training.collect_ledger(conn, tenant)
            positive = await conn.fetchrow("SELECT * FROM tank.training_pairs WHERE tenant_id=$1", tenant)
            assert positive["source"] == "client_accepted" and positive["gold_id"] is None and positive["active"]
        await b.tank.ledger_feedback(result.ledger_id, b.tank.Feedback(tenant_id=tenant, feedback="rejected"))
        await b.tank.ledger_feedback(result.ledger_id, b.tank.Feedback(tenant_id=tenant, feedback="rejected"))
        async with b.pool.acquire() as conn:
            rows = await conn.fetch("SELECT source,polarity,active FROM tank.training_pairs WHERE tenant_id=$1", tenant)
            assert {r["source"] for r in rows} == {"client_accepted", "client_rejected"}
            assert all(not r["active"] for r in rows)
            assert float(await conn.fetchval("SELECT shadow_rate FROM tank.policy WHERE tenant_id=$1 AND task_type='base.normalize'", tenant)) == pytest.approx(0.1)
            assert await conn.fetchval("SELECT count(*) FROM tank.gold_examples WHERE tenant_id=$1", tenant) == 0
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT shadow_rate FROM tank.policy WHERE tenant_id IS NULL AND task_type='base.normalize'") == 0


@pytest.mark.asyncio
async def test_version_ownership_and_cancellation_stay_closed(ladder):
    b = ladder
    from fastapi import HTTPException
    for tenant in b.tenants:
        async with b.pool.acquire() as conn:
            task = await conn.fetchval("INSERT INTO tank.tasks(tenant_id,title,status,input) VALUES($1,'cancel fixture','cancelled','[]') RETURNING id", tenant)
        with pytest.raises(HTTPException) as cancelled:
            await b.tank.run_route(request(b, tenant), task_id=task)
        assert cancelled.value.status_code == 409
        with pytest.raises(HTTPException) as foreign:
            await b.tank.run_route(request(b, b.tenants[1-b.tenants.index(tenant)]), task_id=task)
        assert foreign.value.status_code == 404
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.skills SET state='retired' WHERE id='base.normalize'")
    for tenant in b.tenants:
        result = await b.tank.run_route(request(b, tenant))
        assert result.rung == 2 and result.escalation[0]["reason"] == "skill_not_approved"
    assert len(b.sent) == 2


@pytest.mark.asyncio
async def test_first_fixture_graduation_promotes_itself_and_serves_two_tenants(ladder, monkeypatch):
    import asyncio
    from datetime import datetime, timezone
    b = ladder
    expected = {}
    async with b.pool.acquire() as conn:
        await conn.execute("""UPDATE tank.policy SET model='haiku',rung=1,candidate_model='skill:base.normalize@1.0.0',
            shadow_rate=1,auto_promote=true,min_shadow_samples=30,eval_threshold=0.97,confidence_floor=0.8
            WHERE task_type='base.normalize' AND tenant_id IS NULL""")

    class FixtureProvider:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, **kwargs):
            payload = json.loads(kwargs["json"]["messages"][-1]["content"])
            return httpx.Response(200, headers={"content-type": "application/json", "x-litellm-response-cost": "0.001"},
                json={"choices": [{"message": {"content": json.dumps(expected[payload["name"]])}}],
                      "usage": {"prompt_tokens": 50, "completion_tokens": 100}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(b.tank.httpx, "AsyncClient", FixtureProvider)
    for i in range(30):
        name = f"Fixture Shop {i:02}"
        payload = {"name": name, "address": "Main Street", "city": "Boston", "state": "MA", "zip": "02108", "phone": "6175550100"}
        # Independent expected fixture answers: the provider stub never calls the code candidate.
        fields = {"name": (name, 95), "name_key": (name.lower(), 90), "street": ("main st", 85),
                  "city": ("Boston", 90), "state": ("MA", 95), "zip": ("02108", 95), "phone": ("+16175550100", 90)}
        expected[name] = {"fields": {k: {"value": v, "source": "input", "confidence": c} for k, (v, c) in fields.items()},
                          "match_key": f"{name.lower()}|boston|ma"}
        res = await b.tank.run_route(request(b, b.tenants[i % 2], text=json.dumps(payload)))
        assert res.rung == 1
        if b.tank._background:
            await asyncio.gather(*list(b.tank._background))
    async with b.pool.acquire() as conn:
        policy_row = await conn.fetchrow("SELECT * FROM tank.policy WHERE task_type='base.normalize' AND tenant_id IS NULL")
        log = await conn.fetchrow("SELECT * FROM tank.policy_log WHERE task_type='base.normalize' AND action='promote'")
        stats = await conn.fetchrow("SELECT count(*) n,avg(agreement) agreement FROM tank.shadow WHERE task_type='base.normalize'")
        assert policy_row["model"] == 'skill:base.normalize@1.0.0' and policy_row["rung"] == 3
        assert log["by_user"] == "tank" and json.loads(log["detail"])["automatic"]
        assert stats["n"] == 30 and float(stats["agreement"]) == 1
    for tenant in b.tenants:
        delivered = await b.tank.run_route(request(b, tenant, text=json.dumps(payload)))
        assert delivered.rung == 3 and delivered.cost_usd == 0
    print("FIRST_GRADUATION " + json.dumps({"task": "base.normalize", "date": datetime.now(timezone.utc).isoformat(),
        "skill": policy_row["model"], "samples": stats["n"], "tenants": 2, "agreement": float(stats["agreement"]),
        "before_usd_per_call": 0.001, "after_usd_per_call": 0, "automatic": True,
        "traffic": "independent synthetic fixtures; provider stub; actual provider spend zero"}))


@pytest.mark.asyncio
async def test_seed_rows_are_repeatable_and_tenant_overrides_survive(ladder):  # noqa: F811
    from pathlib import Path
    b = ladder
    async with b.pool.acquire() as conn:
        for tenant in b.tenants:
            await policy(b, tenant, model="luna", rung=2, confidence_floor=0.9)
        sql = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
        before = await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        await conn.execute(sql)
        await conn.execute(sql)
        assert before == await conn.fetch("SELECT * FROM tank.policy ORDER BY task_type,tenant_id")
        base = await conn.fetch("SELECT task_type,rung,model,escalation_model FROM tank.policy WHERE tenant_id IS NULL AND task_type IN ('base.normalize','base.extract','base.business_data','agent.base.think')")
        assert len(base) == 4 and all(r["rung"] == 3 and r["escalation_model"] == "luna" for r in base)
        zenas = await conn.fetch("SELECT model,rung,semantic_cache,matter_matching FROM tank.policy WHERE tenant_id IS NULL AND task_type LIKE 'zenas.%'")
        assert len(zenas) == 9 and all(r["model"] == "astra" and r["rung"] == 1 and r["semantic_cache"] and r["matter_matching"] for r in zenas)


@pytest.mark.asyncio
async def test_cache_expiry_and_private_code_ownership_before_reuse(ladder):  # noqa: F811
    import uuid
    from fastapi import HTTPException
    b = ladder
    for tenant in b.tenants:
        await policy(b, tenant, confidence_floor=0, cache_scope="tenant")
        first = await b.tank.run_route(request(b, tenant))
        assert first.rung == 3
        assert (await b.tank.run_route(request(b, tenant))).rung == 4
        async with b.pool.acquire() as conn:
            await conn.execute("UPDATE tank.route_cache SET expires_at=now()-interval '1 second' WHERE tenant_id=$1", tenant)
        assert (await b.tank.run_route(request(b, tenant))).rung == 3
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.agent_skill_submissions(skill_id,version,tenant_id,region,submitted_by_room,package,sha256)
            VALUES('base.normalize','1.0.0',$1,'us-east','base','{}','fixture')""", b.tenants[0])
        quotes = await b.tank._code_quotes(conn)
        assert 'skill:base.normalize@1.0.0' not in {q.name for q in quotes}
        base_task = uuid.uuid4()
        await conn.execute("INSERT INTO agent_base.tasks(id,tenant_id,title,status) VALUES($1,$2,'free pipeline completed','done')", base_task, b.tenants[0])
    assert (await b.tank.run_route(request(b, b.tenants[0]), task_id=base_task)).rung == 4
    with pytest.raises(HTTPException) as denied:
        await b.tank.run_route(request(b, b.tenants[1]))
    assert denied.value.status_code == 403
    with pytest.raises(HTTPException) as bad_task:
        await b.tank.run_route(request(b, b.tenants[1]), task_id=base_task)
    assert bad_task.value.status_code == 404
