"""Optional local PostgreSQL fixture proof. See tests/base_proof/README.md."""
from contextlib import asynccontextmanager
from datetime import datetime
from decimal import Decimal
import json
import os
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
import uuid

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

from base_product_fixtures import AT, TENANT, OTHER, raw, finished
from agents.base.engines.ffl.reference import project
from base_repository import BaseStore, encoded
from base_product import build_router
import vendor_meter as meter


@pytest_asyncio.fixture
async def database(monkeypatch):
    address = os.environ.get("BASE_TEST_DATABASE_URL")
    if not address:
        pytest.skip("Explicit local PostgreSQL fixture proof: set BASE_TEST_DATABASE_URL")
    assert urlsplit(address).hostname in {"localhost", "127.0.0.1"}, "Fixture proof accepts only a local database"
    conn = await asyncpg.connect(address)
    await conn.execute((Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text())
    await conn.execute((Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text())
    transaction = conn.transaction(isolation="repeatable_read")
    await transaction.start()
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield conn
    rt = SimpleNamespace(pool=lambda: Pool(), box_region=lambda: "us-east", BASE_AGENT_URL="http://fixture-room")
    monkeypatch.setattr(meter, "runtime", lambda: rt)
    monkeypatch.setenv("TANK_API_KEY", "local-fixture")
    monkeypatch.setenv("TANK_KEY_BASE", "local-room-fixture")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "fixture-founder")
    try:
        yield conn, rt
    finally:
        await transaction.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_existing_platform_adoption_refresh_batch_pairs_and_isolation(database):
    conn, rt = database
    source_rows = [raw(), raw(2, "CA", "07"), raw(3, kind="03")]
    # Reproduce a pre-existing immutable seed, only inside a rolled-back local fixture transaction.
    await conn.execute("SET LOCAL session_replication_role='replica'")
    for source in source_rows:
        await conn.execute("INSERT INTO base.records(tenant_id,raw) VALUES($1,$2::jsonb)", meter.PLATFORM, encoded(source))
    await conn.execute("SET LOCAL session_replication_role='origin'")
    store = BaseStore(rt)
    async def engine(payload):
        assert "rows" in payload, "Adoption must not download the existing reference"
        return {"rows": [project(row) for row in payload["rows"]]}
    store.engine = engine
    await store.adopt()
    await store.adopt()
    assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_files WHERE owner_id=$1", meter.PLATFORM) == 1
    assert await conn.fetchval("SELECT count(*) FROM tank.base_reference_entries WHERE raw IS NOT NULL") == 0
    old = await store.latest_file()
    await store.install({"published_on": "2026-10-01", "source_url": "https://www.atf.gov/fixture-october", "checked_at": AT,
                         "sha256": "fixture-new-month", "rows": [project(raw(street="New address")), project(raw(4)), project(raw(3, kind="03"))]})
    assert len(await store.reference(old["id"])) == 3
    assert len(await store.reference()) == 3
    with pytest.raises(ValueError, match="cannot replace"):
        await store.install({"published_on": "2026-09-01", "sha256": "changed", "rows": [project(raw())]})
    submitted = []
    async def room(request):
        payload = json.loads(request.content)
        submitted.append(payload)
        task = uuid.uuid4()
        await conn.execute("INSERT INTO agent_base.tasks(id,tenant_id,title,input,status) VALUES($1,$2,'Fixture batch',$3::jsonb,'queued')", task, TENANT, encoded(payload))
        return httpx.Response(202, json={"task": {"id": str(task)}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as upstream:
        rt._http = upstream
        app = FastAPI()
        app.include_router(build_router(rt, store, background=False))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
            body = {"tenant_id": str(TENANT), "request_id": str(uuid.uuid4()), "created_by": "fixture", "states": ["TX"], "types": ["01"]}
            started = await client.post("/v1/base-product/reference/batches", json=body)
            assert started.status_code == 200, started.text
            assert started.json()["records"] == 2 and len(submitted) == 1
            await client.post("/v1/base-product/reference/batches", json=body)
            assert len(submitted) == 1
            task = (await store.campaigns(TENANT))[0]["task_id"]
            for entry in submitted[0]["records"]:
                row = finished(project(entry))
                site = row["profile"]["website"]["value"]
                extra = "sales@" + urlsplit(site).hostname
                row["profile"]["emails"]["value"].append(extra)
                row["profile"]["socials"]["value"]["instagram"] = "https://instagram.com/fixture-business"
                row["passes"]["2b"]["field_observations"].append({
                    "source_url": site + "team", "checked_at": "2026-10-27T10:00:00+00:00", "emails": [extra],
                    "phones": [], "links": ["https://instagram.com/fixture-business"],
                })
                await conn.execute("""INSERT INTO agent_base.records(id,tenant_id,task_id,batch,raw,profile,passes,status,updated_at)
                    VALUES($1,$2,$3,$4,$5::jsonb,$6::jsonb,$7::jsonb,'done',$8)""",
                    row["id"], TENANT, task, submitted[0]["batch"], encoded(entry), encoded(row["profile"]), encoded(row["passes"]), datetime.fromisoformat(AT))
            assert await store.collect(TENANT) == 2
            assert await store.collect(TENANT) == 0
            summary = await client.get("/v1/base-product/numbers", params={"tenant_id": str(TENANT)})
            assert summary.status_code == 200, summary.text
            texas = next(row for row in summary.json()["groups"] if row["state"] == "TX")
            assert texas["attempted"] == texas["website"] == texas["phone"] == texas["email_and_phone"] == 2
            csv = await client.get("/v1/base-product/records.csv", params={"tenant_id": str(TENANT), "metric": "email_and_phone"})
            assert csv.status_code == 200 and "/contact" in csv.text and "phone_checked_at" in csv.text
            import csv as csv_reader
            import io
            exported = list(csv_reader.DictReader(io.StringIO(csv.text.lstrip("\ufeff"))))
            assert len(exported) == 2 and "[" not in csv.text and "{" not in csv.text
            for item in exported:
                assert item["email"].startswith("info@") and item["other_emails"].startswith("sales@")
                assert item["email_source_url"] == item["website"] + "contact"
                assert item["other_emails_source_url"] == item["instagram_source_url"] == item["website"] + "team"
                assert item["other_emails_checked_at"] == item["instagram_checked_at"] == "2026-10-27T10:00:00+00:00"
                assert item["instagram"] == "https://instagram.com/fixture-business" and item["x"] == ""
            pairs = await conn.fetch("SELECT * FROM tank.training_pairs WHERE tenant_id=$1 AND source='base_verified'", TENANT)
            assert len(pairs) == 8 and all(pair["gold_id"] is None and not pair["public"] for pair in pairs)
            private = await client.get("/v1/base-product/pairs", params={"tenant_id": str(OTHER)})
            assert private.json()["rows"] == []
            assert await store.results(OTHER) == [] and await store.campaigns(OTHER) == []
            assert (await client.get("/v1/base-product/reference", params={"tenant_id": str(OTHER)})).json()["total_all"] == 3


@pytest.mark.asyncio
async def test_status_prices_precise_receipts_founder_only_and_history(database, monkeypatch):
    conn, rt = database
    columns = await conn.fetch("""SELECT table_name,column_name,is_nullable,numeric_precision,numeric_scale
        FROM information_schema.columns WHERE table_schema='tank' AND
        ((table_name='price_book' AND column_name='unit_price') OR (table_name='ledger' AND column_name='cost_usd'))""")
    assert len(columns) == 2
    assert all(row["is_nullable"] == "NO" and row["numeric_precision"] == 18 and row["numeric_scale"] == 8 for row in columns)
    app = FastAPI()
    app.include_router(build_router(rt, background=False))
    token = meter.current.set(meter.Run(TENANT, "us-east", "base", "base.find_site", None, uuid.uuid4()))
    try:
        first = httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search")
        await meter.request_hook(first)
        await meter.response_hook(httpx.Response(200, request=first))
        old = dict(await conn.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1", TENANT))
        assert old["cost_status"] == "not_set" and old["cost_usd"] == 0
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-fixture"}) as client:
            price = {"unit_price": "0.000792"}
            assert (await client.put("/v1/base-product/prices/brave.search.query", json=price)).status_code == 404
            saved = await client.put("/v1/base-product/prices/brave.search.query", json=price, headers={"X-Tervory-Admin": "fixture-founder"})
            assert saved.status_code == 200, saved.text
            second = httpx.Request("GET", "https://api.search.brave.com/res/v1/web/search")
            await meter.request_hook(second)
            await meter.response_hook(httpx.Response(200, request=second))
            assert dict(await conn.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND id=$2", TENANT, old["id"])) == old
            new = await conn.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND id<>$2", TENANT, old["id"])
            assert new["cost_status"] == "set" and new["cost_usd"] == Decimal("0.000792")
            receipts = (await client.get("/v1/base-product/ledger", params={"tenant_id": str(TENANT), "limit": 1})).json()
            assert receipts["total"] == 2 and len(receipts["rows"]) == 1
            next_page = (await client.get("/v1/base-product/ledger", params={"tenant_id": str(TENANT), "limit": 1, "offset": 1})).json()
            pages = {item["id"]: item for item in receipts["rows"] + next_page["rows"]}
            assert len(pages) == 2
            assert pages[str(old["id"])]["cost_usd"] is None and pages[str(old["id"])]["status"] == "price not set"
            assert Decimal(pages[str(new["id"])]["cost_usd"]) == Decimal("0.000792")
            assert (await client.get("/v1/base-product/ledger", params={"tenant_id": str(OTHER)})).json()["rows"] == []
            excluded = (await client.get("/v1/base-product/ledger", params={"tenant_id": str(TENANT), "cost_status": "not_set"})).json()
            assert excluded["total"] == 1 and excluded["rows"][0]["id"] == str(old["id"])
            assert excluded["rows"][0]["status"] == "price not set"
            assert (await client.get("/v1/base-product/ledger", params={"tenant_id": str(OTHER), "cost_status": "not_set"})).json()["rows"] == []
            endpoint = "/v1/base-product/founder/unpriced"
            assert (await client.get(endpoint)).status_code == 404
            assert (await client.get(endpoint, headers={"X-Tervory-Admin": "not-founder"})).status_code == 404
            founder = {"X-Tervory-Admin": "fixture-founder"}
            params = {"tenant_id": str(TENANT), "day": old["ts"].date().isoformat(), "task": "base.find_site", "agent": "base"}
            response = await client.get(endpoint, params=params, headers=founder)
            assert response.status_code == 200, response.text
            evidence = response.json()
            assert evidence["total"] == 1 and evidence["rows"][0]["id"] == str(old["id"])
            assert evidence["rows"][0]["cost_usd"] is None and evidence["rows"][0]["cost_status"] == "price not set"
            for changed in ({"tenant_id": str(OTHER)}, {"day": "2020-01-01"}, {"task": "different"}, {"agent": "different"}, {"offset": 1}):
                assert (await client.get(endpoint, params={**params, **changed}, headers=founder)).json()["rows"] == []
            assert (await client.get(endpoint, params={"days": 30, "tenant_id": str(TENANT)}, headers=founder)).json()["total"] == 1

            import proof
            monkeypatch.setattr(proof, "runtime", lambda: rt)
            report = await proof.snapshot(TENANT)
            assert report["tasks"][0]["unknown_cost_calls"] == 1
            assert Decimal(str(report["tasks"][0]["actual_usd"])) == Decimal("0.000792")
            assert next(row for row in report["ledger"] if row["id"] == str(old["id"]))["cost_status"] == "price not set"
            receipt = {"id": str(uuid.uuid4()), "tenant_id": str(meter.PLATFORM), "record_id": str(uuid.uuid4()),
                       "run_id": str(uuid.uuid4()), "units": 2, "outcome": "delivered", "region": "us-east"}
            posted = await client.post("/v1/base-product/context-dev", json=receipt, headers={"X-Tank-Key": "local-room-fixture"})
            assert posted.status_code == 200, posted.text
            credit = await conn.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND id=$2", meter.PLATFORM, uuid.UUID(receipt["id"]))
            assert credit["units"] == 2 and credit["cost_usd"] == Decimal("0.001584") and credit["cost_status"] == "set"
    finally:
        meter.current.reset(token)


@pytest.mark.asyncio
async def test_context_observer_links_model_and_code_receipts_without_changing_routing(database):
    from fastapi import Request
    conn, rt = database
    app = FastAPI()
    rt.app = app
    routed = []
    async def model(**kwargs):
        routed.append(kwargs)
        identity = uuid.uuid4()
        await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,skill,model,rung,cost_usd) VALUES($1,$2,'base','base.fixture','base.fixture@1','fixture-model',2,0.02)", identity, kwargs["tenant_id"])
        return {"ledger_id": identity, "cost_usd": .02, "content": "checked"}
    def context(pkg, tenant_id, **kwargs):
        return SimpleNamespace(tenant_id=tenant_id, skill_ref="base.fixture@1", task_id=None, _model=model)
    rt.make_ctx = context
    meter.install(rt)
    @app.post("/v1/skala/base.fixture/run")
    async def skill(request: Request):
        body = await request.json()
        assert "_base_record_id" not in body["input"]
        ctx = rt.make_ctx(None, uuid.UUID(body["tenant_id"]))
        if body["input"].get("model"):
            await ctx._model(tenant_id=ctx.tenant_id, task_type="base.fixture")
        return {"answer": "checked"}
    record = uuid.uuid4()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture", headers={"X-Tank-Key": "local-room-fixture"}) as client:
        for paid in (True, False):
            result = await client.post("/v1/skala/base.fixture/run", json={"tenant_id": str(TENANT), "input": {"_base_record_id": str(record), "model": paid}})
            assert result.status_code == 200, result.text
    receipts = await conn.fetch("SELECT l.* FROM tank.ledger l JOIN tank.base_ledger_links b ON b.tenant_id=$1 AND b.ledger_id=l.id WHERE l.tenant_id=$1 AND b.record_id=$2 ORDER BY l.rung", TENANT, record)
    assert [row["rung"] for row in receipts] == [2, 3]
    assert [row["cost_usd"] for row in receipts] == [Decimal("0.02"), Decimal(0)]
    assert len(routed) == 1 and meter.current.get() is None


@pytest.mark.asyncio
async def test_fifty_states_are_submitted_one_after_another(database):
    from agents.base.engines.ffl.reference import STATES
    conn, rt = database
    store = BaseStore(rt)
    await store.install({"published_on": "2026-09-01", "source_url": "https://www.atf.gov/fixture-september", "checked_at": AT,
                         "sha256": "fixture-states", "rows": [project(raw(i + 1, state)) for i, state in enumerate(STATES)]})
    file = await store.latest_file()
    entries = await store.reference()
    await store.create_campaign(TENANT, uuid.uuid4(), "All states", "fixture", file["id"], {}, {row["state"]: [row] for row in entries})
    submitted = []
    async def room(request):
        payload = json.loads(request.content)
        state = payload["records"][0]["_base_reference"]["state"]
        assert not await conn.fetchval("SELECT 1 FROM agent_base.tasks WHERE tenant_id=$1 AND status='queued'", TENANT)
        submitted.append(state)
        task = uuid.uuid4()
        await conn.execute("INSERT INTO agent_base.tasks(id,tenant_id,title,input,status) VALUES($1,$2,'Fixture state',$3::jsonb,'queued')", task, TENANT, encoded(payload))
        return httpx.Response(202, json={"task": {"id": str(task)}})
    async with httpx.AsyncClient(transport=httpx.MockTransport(room)) as client:
        rt._http = client
        for number, state in enumerate(sorted(STATES), 1):
            await store.dispatch(TENANT)
            assert submitted[-1] == state and len(submitted) == number
            await store.dispatch(TENANT)
            assert len(submitted) == number
            await conn.execute("UPDATE agent_base.tasks SET status='done' WHERE tenant_id=$1 AND status='queued'", TENANT)
        await store.dispatch(TENANT)
    assert len(submitted) == 50
    assert all(row["status"] == "done" for row in await store.campaigns(TENANT))


@pytest.mark.asyncio
async def test_in_progress_attempt_is_counted_but_not_saved_as_failed_training(database):
    from base_queries import numbers
    conn, rt = database
    row = finished(project(raw()))
    await conn.execute("""INSERT INTO agent_base.records(id,tenant_id,raw,status) VALUES($1,$2,$3::jsonb,'queued')""",
                       row["id"], TENANT, encoded(row["raw"]))
    receipt = uuid.uuid4()
    await conn.execute("INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd) VALUES($1,$2,'base','base.normalize','code',0)", receipt, TENANT)
    await conn.execute("INSERT INTO tank.base_ledger_links(tenant_id,record_id,ledger_id) VALUES($1,$2,$3)", TENANT, row["id"], receipt)
    store = BaseStore(rt)
    assert await store.collect(TENANT) == 1
    assert await conn.fetchval("SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1 AND source='base_verified'", TENANT) == 0
    group = (await numbers(store, TENANT, [], [], False))["groups"][0]
    assert group["attempted"] == 1 and group["verified"] == group["failed"] == 0
    await conn.execute("UPDATE agent_base.records SET status='failed',updated_at=now()+interval '1 second' WHERE tenant_id=$1 AND id=$2", TENANT, row["id"])
    assert await store.collect(TENANT) == 1
    assert await conn.fetchval("SELECT count(*) FROM tank.training_pairs WHERE tenant_id=$1 AND source='base_verified'", TENANT) == 4


@pytest.mark.asyncio
async def test_sql_numbers_keep_priced_cost_and_link_only_excluded_receipts(database):
    from base_queries import numbers, ledger_page
    conn, rt = database
    row = finished(project(raw()))
    await conn.execute("""INSERT INTO agent_base.records(id,tenant_id,raw,profile,passes,status,updated_at)
        VALUES($1,$2,$3::jsonb,$4::jsonb,$5::jsonb,'done',$6)""", row["id"], TENANT,
        encoded(row["raw"]), encoded(row["profile"]), encoded(row["passes"]), datetime.fromisoformat(AT))
    store = BaseStore(rt)
    await store.collect(TENANT)
    excluded = uuid.uuid4()
    for identity, status, amount in ((uuid.uuid4(), "set", Decimal("0.000792")), (excluded, "not_set", Decimal(0))):
        await conn.execute("""INSERT INTO tank.ledger(id,tenant_id,ts,agent,task_type,model,vendor,rung,cost_usd,cost_status)
            VALUES($1,$2,$3,'base','base.find_site','vendor:brave.search','brave.search',1,$4,$5)""",
            identity, TENANT, datetime.fromisoformat(AT), amount, status)
        await conn.execute("INSERT INTO tank.base_ledger_links(tenant_id,record_id,ledger_id) VALUES($1,$2,$3)", TENANT, row["id"], identity)
    result = await numbers(store, TENANT, ["TX"], ["01"], False)
    cost = result["costs"][0]
    assert cost["unpriced"] == 1 and cost["verified_records"] == 1
    assert cost["vendors"] == ["brave.search"]
    assert Decimal(cost["known_cost_usd"]) == Decimal(cost["cost_per_verified_record"]) == Decimal("0.000792")
    assert cost["cost_usd"] is None and cost["status"] == "price not set"
    assert (await numbers(store, OTHER, ["TX"], ["01"], False))["costs"] == []
    receipts = await ledger_page(store, TENANT, "TX", "2026-10", 1, ["01"], False, 0, 100, "not_set")
    assert receipts["total"] == 1 and receipts["rows"][0]["id"] == excluded
    assert receipts["rows"][0]["cost_usd"] is None and receipts["rows"][0]["status"] == "price not set"
