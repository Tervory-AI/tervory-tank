"""Offline case-study proof against real PostgreSQL and the actual Tank routes."""
from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, date, datetime
from pathlib import Path

import asyncpg
import httpx
import pytest
import pytest_asyncio
from case_study_templates import PRODUCTS, TANK, empty_figures

ROOT = Path(__file__).resolve().parents[1]
A = uuid.UUID("ca5e0000-0000-4000-8000-000000000001")
B = uuid.UUID("ca5e0000-0000-4000-8000-000000000002")
AT = datetime(2026, 10, 2, 12, tzinfo=UTC)
WINDOW = {"start": "2026-10-01", "end": "2026-10-03"}


def headers(tenant=A, user="client-a"):
    return {"X-Tank-Key": "local-fixture", "X-Tervory-Tenant": str(tenant), "X-Tervory-User": user}


@pytest_asyncio.fixture
async def api(monkeypatch):
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("Set POOL_SCHEMA_DATABASE_URL to a disposable local PostgreSQL")
    from urllib.parse import urlsplit
    assert urlsplit(url).hostname in {"127.0.0.1", "localhost"}
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "unused-offline")
    import main
    admin = await asyncpg.connect(url)
    name = "case_study_" + uuid.uuid4().hex
    await admin.execute(f'CREATE DATABASE "{name}"')
    pool = await asyncpg.create_pool(url, database=name, min_size=1, max_size=5)
    try:
        async with pool.acquire() as conn:
            await conn.execute((ROOT / "tank/schema.sql").read_text())
            # An existing product's own schema, just as on a deployed box.
            await conn.execute("CREATE SCHEMA IF NOT EXISTS agent_trigger")
            await conn.execute((ROOT / "agents/trigger/schema.sql").read_text())
            await conn.execute((ROOT / "tank/schema.sql").read_text())
        monkeypatch.setattr(main, "_pool", pool)
        monkeypatch.setattr(main, "TANK_API_KEY", "local-fixture")
        monkeypatch.setattr(main, "box_region", lambda: "us-east")
        monkeypatch.setenv("TANK_API_KEY", "local-fixture")
        monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "fixture-founder")
        # All product reads for these reports are local; never contact a model.
        async def no_network(*args, **kwargs):
            raise AssertionError("Case-study reports must not call an external service")
        monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", no_network)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://fixture", headers=headers()) as client:
            yield pool, client
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}"')
        await admin.close()


async def grant(pool, tenant, product):
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.tenant_squad(tenant_id,agent,enabled_by) VALUES($1,$2,'fixture-founder') ON CONFLICT DO NOTHING", tenant, product)


async def read(client, product, tenant=A, user="client-a"):
    response = await client.get("/v1/case-studies/" + product, params=WINDOW, headers=headers(tenant, user))
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "private, no-store"
    return response.json()


def figures(report):
    return {item["id"]: item for item in [*report["tank"], *report["figures"]]}


def assert_complete(report, product):
    specs = (*TANK, *PRODUCTS[product])
    found = figures(report)
    assert len(found) == len(specs)
    assert set(found) == {spec.id for spec in specs}
    for spec in specs:
        assert found[spec.id]["type"] == spec.type
        assert found[spec.id]["unit"] == spec.unit


@pytest.mark.parametrize("product", PRODUCTS)
def test_fixed_template_has_every_figure_and_period_zeros(product):
    rows = empty_figures(product, date(2026, 10, 1), date(2026, 10, 3))
    assert len(rows) == 6 + len(PRODUCTS[product])
    for row in rows.values():
        if row["type"] == "number":
            assert row["value"] == 0
        else:
            assert all(item["value"] == 0 for item in row["value"])
        if row["type"] == "series":
            assert [item["date"] for item in row["value"]] == ["2026-10-01", "2026-10-02", "2026-10-03"]


@pytest.mark.asyncio
async def test_signup_and_added_products_register_once_before_any_work(api):
    pool, client = api
    for product in ("base", "tiger"):
        await grant(pool, A, product)
    first = await client.post("/v1/case-studies/ensure")
    assert first.status_code == 200 and first.json()["products"] == ["base", "tiger"]
    assert (await client.post("/v1/case-studies/ensure")).json() == first.json()
    for product in ("base", "tiger"):
        report = await read(client, product)
        assert_complete(report, product)
        for item in figures(report).values():
            assert item["value"] == 0 if item["type"] == "number" else all(row["value"] == 0 for row in item["value"])
    # Grant through the real existing founder endpoint, not a report endpoint.
    added = await client.put("/v1/command/squads/rig", headers=headers(A, "fixture-founder"), json={"enabled": True})
    assert added.status_code == 200, added.text
    async with pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.case_study_reports WHERE tenant_id=$1 AND product='rig'", A) == 1
        await conn.execute((ROOT / "tank/schema.sql").read_text())
        assert await conn.fetchval("SELECT count(*) FROM tank.case_study_reports WHERE tenant_id=$1", A) == 3
    assert_complete(await read(client, "rig"), "rig")


@pytest.mark.asyncio
async def test_every_product_report_present_including_trigger_and_autumbra(api):
    pool, client = api
    for product in ("base", "tiger", "market_lab", "rig", "zenas", "tisan", "radix"):
        await grant(pool, A, product)
    async with pool.acquire() as conn:
        # Trigger provisioning is its own voice, not a new chat permission.
        await conn.execute("INSERT INTO agent_trigger.voices(tenant_id,voice,revision) VALUES($1,'{\"status\":\"live\"}',1)", A)
        # Autumbra product use is recorded on Tank; outside this report period.
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,rung,model,cost_usd,ts)
            VALUES($1,'ghost','ghost.check',3,'code',0,'2026-09-01')""", A)
        assert await conn.fetchval("SELECT count(*) FROM tank.case_study_reports WHERE tenant_id=$1", A) == 9
    for product in PRODUCTS:
        report = await read(client, product)
        assert_complete(report, product)
        for item in figures(report).values():
            assert item["value"] == 0 if item["type"] == "number" else all(row["value"] == 0 for row in item["value"])


@pytest.mark.asyncio
async def test_tenant_and_founder_access_cannot_be_overridden_by_query_or_headers(api):
    pool, client = api
    await grant(pool, A, "base")
    await grant(pool, B, "base")
    for path in ("/v1/case-studies", "/v1/case-studies/base"):
        response = await client.get(path, params={**WINDOW, "tenant_id": str(B)})
        assert response.status_code == 403
        response = await client.get(path, params={**WINDOW, "tenant_id": str(B)}, headers={"X-Tervory-Admin": "fixture-founder"})
        assert response.status_code == 403  # Founder identity cannot be supplied through the unused admin header.
        response = await client.get(path, params={**WINDOW, "tenant_id": str(B)}, headers=headers(A, "fixture-founder"))
        assert response.status_code == 200 and response.json()["tenant_id"] == str(B)
    assert (await client.get("/v1/case-studies/clients")).status_code == 403
    all_clients = await client.get("/v1/case-studies/clients", headers=headers(A, "fixture-founder"))
    assert {row["tenant_id"] for row in all_clients.json()["clients"]} == {str(A), str(B)}
    for bad in ({"X-Tank-Key": ""}, {"X-Tervory-User": ""}, {"X-Tervory-Tenant": "invalid"}):
        assert (await client.get("/v1/case-studies/base", headers=bad)).status_code in {401, 422}
    assert (await client.get("/v1/case-studies/base", headers={"X-Tervory-Home-Region": "za"})).status_code == 403
    assert (await client.get("/v1/case-studies/tiger")).status_code == 404
    assert (await client.get("/v1/case-studies/unknown")).status_code == 404
    assert (await client.get("/v1/case-studies/base", params={"start": "2026-10-03", "end": "2026-10-01"})).status_code == 422


@pytest.mark.asyncio
async def test_real_tank_proof_costs_cache_and_work_stay_with_tenant_and_period(api):
    pool, client = api
    await grant(pool, A, "base")
    await grant(pool, B, "base")
    async with pool.acquire() as conn:
        # A real linked free job is eligible under the existing proof rules.
        task = await conn.fetchval("""INSERT INTO tank.tasks(tenant_id,created_by,agent,task_type,title,input,status,finished_at)
            VALUES($1,'fixture','base','base.fixture','Offline fixture','{}','done',$2) RETURNING id""", A, AT)
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,rung,model,cost_usd,ts,task_id,baseline_status,standard_cost_usd)
            VALUES($1,'base','base.fixture',3,'code',0,$2,$3,'no_tokens',0)""", A, AT, task)
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,rung,model,cost_usd,ts,cache_hit)
            VALUES($1,'base','base.fixture',2,'offline-model',2,$2,false),
                  ($1,'base','base.fixture',3,'cache',0,$2,true)""", A, AT)
        await conn.execute("""INSERT INTO tank.ledger(tenant_id,agent,task_type,rung,model,cost_usd,ts)
            VALUES($1,'base','base.fixture',2,'offline-model',999,$2),
                  ($3,'tiger','tiger.fixture',2,'offline-model',500,$2),
                  ($3,'base','base.fixture',2,'offline-model',700,'2026-09-01')""", B, AT, A)
    report = await read(client, "base")
    values = figures(report)
    assert values["tank.spend"]["value"] == 2
    assert values["tank.cost_per_task"]["value"] == pytest.approx(2 / 3)
    assert values["tank.cache_hits"]["value"] == 1
    assert values["tank.work_by_execution"]["value"] == [{"id": k, "value": 1} for k in ("code", "cache", "model")]
    assert figures(await read(client, "base", B, "client-b"))["tank.spend"]["value"] == 999
    if directory := os.environ.get("CASE_STUDY_PROOF_DIR"):
        Path(directory).mkdir(parents=True, exist_ok=True)
        Path(directory, "tenant-a-base.json").write_text(json.dumps(report, indent=2) + "\n")


@pytest.mark.asyncio
async def test_product_sources_fill_only_their_tenant_figures(api):
    pool, client = api
    for tenant in (A, B):
        for product in ("rig", "market_lab", "zenas", "tisan", "radix"):
            await grant(pool, tenant, product)
    async with pool.acquire() as conn:
        await conn.execute((ROOT / "agents/rig/schema.sql").read_text())
        await conn.execute((ROOT / "agents/market_lab/schema.sql").read_text())
        # Use the actual shared room jobs schema and Radix findings builder.
        import importlib.util
        spec = importlib.util.spec_from_file_location("fixture_chassis_db", ROOT / "agents/_chassis/chassis/db.py")
        chassis = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(chassis)
        for agent in ("tisan", "radix"):
            await chassis.ensure_schema(conn, agent)
        from agents.radix.scanlib.store import ensure_findings
        await ensure_findings(conn, "agent_radix")
        await conn.execute("CREATE SCHEMA agent_zenas")
        # The document table's real definition, without unrelated law-library seeds.
        source = (ROOT / "agents/zenas/schema.sql").read_text()
        sql = source[source.index("CREATE TABLE IF NOT EXISTS agent_zenas.documents"):].split(";", 1)[0] + ";"
        await conn.execute(sql)
        await conn.execute("""INSERT INTO agent_rig.widget_counts(tenant_id,day,event,count)
            VALUES($1,'2026-10-02','searches',8),($1,'2026-10-02','no_results',3)""", A)
        await conn.execute("INSERT INTO agent_rig.quotes(tenant_id,id,payload,sent_at) VALUES($1,'offline-quote','{}',$2)", A, AT)
        await conn.execute("""INSERT INTO agent_market_lab.reports(id,tenant_id,made_at,question,answer,citations)
            VALUES($1,$2,$3,'Offline question','Offline answer','[\"one\",\"two\"]')""", uuid.uuid4(), A, AT)
        await conn.execute("""INSERT INTO agent_zenas.documents(tenant_id,matter_id,kind,version,body,sources,created_at)
            VALUES($1,$2,'memo',1,'Offline memo','[{},{}]',$3),($1,$2,'contract',1,'Offline draft','[]',$3)""", A, uuid.uuid4(), AT)
        await conn.execute("""INSERT INTO agent_tisan.jobs(tenant_id,kind,status,result,finished_at)
            VALUES($1,'scaffold','done','{\"ok\":true,\"slug\":\"offline-site\"}',$2)""", A, AT)
        await conn.execute("INSERT INTO agent_radix.jobs(tenant_id,kind,status,finished_at) VALUES($1,'scan','done',$2)", A, AT)
        await conn.execute("INSERT INTO agent_radix.findings(tenant_id,scan_id,tool,severity,created_at) VALUES($1,$2,'offline','high',$3)", A, uuid.uuid4(), AT)
    expected = {"rig": {"searches": 8, "no_result_searches": 3, "quotes_sent": 1},
                "market_lab": {"questions_answered": 1, "sources_cited": 2},
                "zenas": {"questions": 1, "cited_answers": 1, "sources_per_answer": 2, "drafts": 1},
                "tisan": {"sites_built": 1}, "radix": {"scans": 1}}
    for product, metrics in expected.items():
        first, second = await read(client, product), await read(client, product, B, "client-b")
        assert_complete(first, product)
        for metric, value in metrics.items():
            assert figures(first)[product + "." + metric]["value"] == value
            assert figures(second)[product + "." + metric]["value"] == 0
    severity = figures(await read(client, "radix"))["radix.findings_by_severity"]["value"]
    assert next(row["value"] for row in severity if row["id"] == "high") == 1


@pytest.mark.asyncio
async def test_base_verified_confidence_and_apollo_use_real_evidence(api):
    pool, client = api
    from base_evidence import FIELDS
    for tenant in (A, B):
        await grant(pool, tenant, "base")
    async with pool.acquire() as conn:
        for tenant, confidence, state, key in ((A, 90, "CA", "a1"), (A, 50, "NY", "a2"), (B, 20, "TX", "b1")):
            record = uuid.uuid4()
            fields = {name: {"verified": name == "website", "value": "https://offline.invalid" if name == "website" else None} for name in FIELDS}
            await conn.execute("""INSERT INTO agent_base.records(id,tenant_id,raw,confidence,updated_at)
                VALUES($1,$2,'{}',$3,$4)""", record, tenant, confidence, AT)
            await conn.execute("""INSERT INTO tank.base_record_results
                (tenant_id,record_id,licence_key,state,licence_type,name,status,fields,source_revision,attempted_at,checked_at)
                VALUES($1,$2,$3,$4,'01','Offline fixture','done',$5,'offline',$6,$6)""", tenant, record, key, state, json.dumps(fields), AT)
            receipt = await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,agent,task_type,rung,model,cost_usd,ts)
                VALUES($1,'base','base.fixture',2,'offline-model',1,$2) RETURNING id""", tenant, AT)
            await conn.execute("INSERT INTO tank.base_ledger_links VALUES($1,$2,$3)", tenant, record, receipt)
        imported = uuid.uuid4()
        await conn.execute("INSERT INTO tank.base_apollo_imports VALUES($1,$2,'offline',$3)", A, imported, AT)
        await conn.execute("""INSERT INTO tank.base_apollo_records(tenant_id,import_id,licence_key,fields)
            VALUES($1,$2,'a1','{"website":"https://offline.invalid"}')""", A, imported)
    values = figures(await read(client, "base"))
    assert values["base.records_verified"]["value"] == 2
    assert values["base.cost_per_verified_record"]["value"] == 1
    assert values["base.records_by_state"]["value"] == [{"id": "CA", "value": 1}, {"id": "NY", "value": 1}]
    assert {v["id"]: v["value"] for v in values["base.confidence_histogram"]["value"]} == {"0-39": 0, "40-59": 1, "60-79": 0, "80-100": 1, "missing": 0}
    assert next(v["value"] for v in values["base.comparison_vs_apollo"]["value"] if v["id"] == "website.matches") == 1
    assert values["base.measured_accuracy"]["value"] == 0  # #390 not on this main.
    assert figures(await read(client, "base", B, "client-b"))["base.records_verified"]["value"] == 1


@pytest.mark.asyncio
async def test_tiger_delivery_and_price_bands_do_not_invent_detection_time(api, monkeypatch):
    pool, client = api
    monkeypatch.syspath_prepend(str(ROOT / "agents/_chassis"))
    monkeypatch.syspath_prepend(str(ROOT / "agents/tiger"))
    import importlib.util
    spec = importlib.util.spec_from_file_location("case_study_tiger_watch", ROOT / "agents/tiger/watch.py")
    watch = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(watch)
    for tenant in (A, B):
        await grant(pool, tenant, "tiger")
    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA agent_tiger")
        await watch.ensure_tables(conn)
        await conn.execute("INSERT INTO agent_tiger.watchlist(tenant_id,url,every) VALUES($1,'https://offline.invalid','1h')", A)
        await conn.execute("INSERT INTO agent_tiger.observations(tenant_id,url,ts) VALUES($1,'https://offline.invalid',$2)", A, AT)
        for i, after in enumerate(("49", "50", "90", "100", "110", "150", "unread")):
            alert = await conn.fetchval("""INSERT INTO agent_tiger.alerts(tenant_id,url,ts,kind,before,after)
                VALUES($1,'https://offline.invalid',$2,'price','100',$3) RETURNING id""", A, AT, after)
            await conn.execute("""INSERT INTO agent_tiger.alert_mail(tenant_id,alert_id,url,kind,letter,status,sent_at)
                VALUES($1,$2,'https://offline.invalid','price','{}',$3,$4)""", A, alert, "sent" if i == 0 else "pending", AT if i == 0 else None)
    values = figures(await read(client, "tiger"))
    for name, count in (("pages_watched", 1), ("checks_run", 1), ("changes_caught", 7), ("alerts_sent", 1)):
        assert values["tiger." + name]["value"] == count
        assert figures(await read(client, "tiger", B, "client-b"))["tiger." + name]["value"] == 0
    assert all(row["value"] == 1 for row in values["tiger.price_change_histogram"]["value"])
    assert values["tiger.price_change_histogram"]["unmeasured"] == 1
    assert values["tiger.time_to_detect"]["value"] == 0
    assert values["tiger.time_to_detect"]["status"] == "missing_source"


@pytest.mark.asyncio
async def test_trigger_checker_results_acceptance_and_voice_hits_are_tenant_scoped(api):
    pool, client = api
    async with pool.acquire() as conn:
        for tenant in (A, B):
            await conn.execute("INSERT INTO agent_trigger.voices VALUES($1,'{\"status\":\"live\"}',1,$2)", tenant, AT)
        ids = []
        for feedback in ("accepted", "rejected", None):
            ids.append(await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,ts,feedback,feedback_at)
                VALUES($1,'trigger','trigger.write','offline-model',$2,$3,$2) RETURNING id""", A, AT, feedback))
        card = {"status": "confirmed", "tool": "trigger.write", "result": {"ledger_id": str(ids[0]),
            "report": {"issue_count": 3, "issues": [{"source": "voice"}, {"source": "voice"}, {"source": "grammar"}]}}}
        for tenant in (A, B):
            # B's forged card must not borrow A's receipt or report evidence.
            await conn.execute("""INSERT INTO tank.command_threads(tenant_id,user_id,title,state)
                VALUES($1,'offline','Offline',$2)""", tenant, json.dumps({"cards": {"one": card, "repeat": card}}))
    values = figures(await read(client, "trigger"))
    for metric, value in (("drafts", 3), ("acceptance_rate", 50), ("checker_issues_per_draft", 3), ("voice_rule_hits", 2)):
        assert values["trigger." + metric]["value"] == value
        assert figures(await read(client, "trigger", B, "client-b"))["trigger." + metric]["value"] == 0


@pytest.mark.asyncio
async def test_report_savings_reuses_core_population_and_graduation_excludes_other_tenants(api):
    pool, client = api
    from proof import savings_cte
    async with pool.acquire() as conn:
        await conn.execute("INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES('offline-actual','offline-family',1,1),('offline-baseline','offline-family',10,10)")
        for tenant in (A, B):
            task = await conn.fetchval("""INSERT INTO tank.tasks(tenant_id,created_by,agent,task_type,title,input,status,finished_at)
                VALUES($1,'offline','base','base.offline','Offline','{}','done',$2) RETURNING id""", tenant, AT)
            ledger = await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,task_id,agent,task_type,model,cost_usd,ts)
                VALUES($1,$2,'base','base.offline','offline-actual',2,$3) RETURNING id""", tenant, task, AT)
            await conn.execute("""UPDATE tank.ledger SET standard_model='offline-baseline',standard_cost_usd=10,
                baseline_model='offline-baseline',baseline_cost_usd=10,baseline_status='measured',baseline_priced_at=$2 WHERE id=$1""", ledger, AT)
            await conn.execute("""INSERT INTO tank.shadow(tenant_id,ledger_id,task_type,primary_model,candidate_model,primary_content,agreement,created_at)
                SELECT $1,$2,'base.offline','offline-actual','offline-candidate','',1,$3 FROM generate_series(1,$4::int)""", tenant, ledger, AT, 2 if tenant == A else 20)
            await conn.execute("""INSERT INTO tank.shadow(tenant_id,ledger_id,task_type,primary_model,candidate_model,primary_content,agreement,created_at)
                VALUES($1,$2,'base.offline','offline-actual','offline-candidate','',NULL,$3),
                      ($1,$2,'base.offline','offline-actual','offline-candidate','',1,'2026-10-10')""", tenant, ledger, AT)
        expected = await conn.fetchval(savings_cte() + "SELECT sum(standard_cost_usd-cost_usd) FROM eligible", A, "us-east", datetime(2026, 10, 4, tzinfo=UTC))
    values = figures(await read(client, "base"))
    assert values["tank.savings_vs_baseline"]["value"] == expected == 8
    progress = values["tank.graduation_progress"]["value"]
    assert len(progress) == 1 and progress[0]["samples"] == 2
    assert progress[0]["value"] == 1
    assert "offline-candidate" not in json.dumps(values)


@pytest.mark.asyncio
async def test_late_room_provisioning_registers_without_a_workspace_visit(api):
    pool, client = api
    from case_studies import reconcile_provisioned
    async with pool.acquire() as conn:
        # Model the real fresh-stack ordering: Tank starts before this room's table.
        await conn.execute("DROP TRIGGER case_study_trigger_provisioned ON agent_trigger.voices")
        await conn.execute("INSERT INTO agent_trigger.voices VALUES($1,'{\"status\":\"live\"}',1,$2)", A, AT)
        assert await conn.fetchval("SELECT count(*) FROM tank.case_study_reports WHERE tenant_id=$1", A) == 0
    await reconcile_provisioned()
    await reconcile_provisioned()
    assert_complete(await read(client, "trigger"), "trigger")
    assert (await client.get("/v1/case-studies")).json()["reports"][0]["product"] == "trigger"
    assert (await client.get("/v1/case-studies", headers=headers(B, "client-b"))).json()["reports"] == []


@pytest.mark.asyncio
async def test_room_role_registers_voice_without_reading_or_writing_tank_tables(api):
    pool, client = api
    role = "case_study_room_" + uuid.uuid4().hex
    async with pool.acquire() as conn:
        await conn.execute(f'CREATE ROLE "{role}" NOLOGIN')
        try:
            await conn.execute(f'GRANT USAGE ON SCHEMA agent_trigger TO "{role}"')
            await conn.execute(f'GRANT INSERT ON agent_trigger.voices TO "{role}"')
            async with conn.transaction():
                await conn.execute(f'SET LOCAL ROLE "{role}"')
                await conn.execute("INSERT INTO agent_trigger.voices VALUES($1,'{\"status\":\"live\"}',1,$2)", A, AT)
                with pytest.raises(asyncpg.InsufficientPrivilegeError):
                    async with conn.transaction():
                        await conn.fetch("SELECT * FROM tank.case_study_reports")
        finally:
            await conn.execute(f'DROP OWNED BY "{role}"')
            await conn.execute(f'DROP ROLE "{role}"')
    assert_complete(await read(client, "trigger"), "trigger")


@pytest.mark.asyncio
async def test_optional_audit_uses_upstream_measurement_and_only_this_tenants_verdicts(api, monkeypatch):
    """#390's module/schema are optional; this exercises their integration contract."""
    import importlib.machinery
    import sys
    import types
    pool, client = api
    await grant(pool, A, "base")
    module = types.ModuleType("base_audit")
    module.__spec__ = importlib.machinery.ModuleSpec("base_audit", loader=None)
    called = []
    def measure(verdicts):
        called.append(verdicts)
        return {"accuracy": .8, "confidence_interval": {"lower": .7, "upper": .9},
                "sample_size": 200, "reviewed": 150, "denominator": 100, "unsure": 50}
    module.measure = measure
    monkeypatch.setitem(sys.modules, "base_audit", module)
    async with pool.acquire() as conn:
        # tank.base_audits ships in schema.sql (#390): write real rows, one campaign per tenant.
        records = json.dumps([{"n": i} for i in range(200)])
        for tenant, verdicts in ((A, {"own": "correct"}), (B, {"other": "wrong"})):
            campaign = await conn.fetchval(
                """INSERT INTO tank.base_campaigns(tenant_id,request_id,name,selection,created_by)
                   VALUES($1,$2,'fixture','{}'::jsonb,'test') RETURNING id""", tenant, uuid.uuid4())
            await conn.execute(
                """INSERT INTO tank.base_audits(tenant_id,campaign_id,seed,population_size,population_sha256,
                   records,verdicts,created_by,reviewed_at) VALUES($1,$2,1,200,'fixture',$3::jsonb,$4::jsonb,'test',$5)""",
                tenant, campaign, records, json.dumps(verdicts), AT)
    measured = figures(await read(client, "base"))["base.measured_accuracy"]
    assert called == [{"own": "correct"}]
    assert (measured["value"], measured["lower"], measured["upper"]) == (80, 70, 90)
    assert (measured["sample_size"], measured["reviewed"], measured["resolved"], measured["unsure"]) == (200, 150, 100, 50)
