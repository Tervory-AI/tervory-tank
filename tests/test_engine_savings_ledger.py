"""Savings ledger, dated baselines and statements on real Tank SQL; the model and Stripe are fakes."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import json
import uuid

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

import savings_ledger
from test_tank_tenant_boundaries import boundary as boundary_fixture
from test_tank_ladder import ladder as ladder_fixture, policy, request, selected_policy_protocol
from tenant_db import bind_tenant_endpoints

boundary = boundary_fixture
ladder = ladder_fixture
ROOT = Path(__file__).resolve().parents[1]
FOUNDER = "founder-fixture"
# The ladder fixture replaces httpx.AsyncClient with its model fake; keep the real one.
REAL_CLIENT = httpx.AsyncClient
OFF_VALUES = [None, "", "1", "TRUE", "True", "yes", " true", "true "]


def month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def engine_ledger_ddl() -> str:
    schema = (ROOT / "tank/schema.sql").read_text()
    return schema.split("-- BEGIN engine_ledger\n")[1].split("-- END engine_ledger")[0]


async def prepare(b, monkeypatch):
    selected_policy_protocol(monkeypatch)
    async with b.pool.acquire() as conn:
        await conn.execute("""INSERT INTO tank.proof_prices(model,family,input_usd,output_usd) VALUES
            ('haiku','anthropic/claude',.00001,.00005),('sonnet','anthropic/claude',.0001,.0005),
            ('opus-fixture','anthropic/claude',.0005,.0025)
            ON CONFLICT(model) DO UPDATE SET input_usd=EXCLUDED.input_usd,output_usd=EXCLUDED.output_usd,
              family=EXCLUDED.family,active=true""")
        await conn.execute("""INSERT INTO tank.provider_standards(provider,model) VALUES('anthropic','sonnet')
            ON CONFLICT(provider) DO UPDATE SET model=EXCLUDED.model""")
    for tenant in b.tenants:
        await policy(b, tenant, model="haiku", rung=1, cache_scope="none", semantic_cache=False,
                     candidate_model=None, shadow_rate=0)


def set_ledger(monkeypatch, value):
    if value is None:
        monkeypatch.delenv(savings_ledger.SETTING, raising=False)
    else:
        monkeypatch.setenv(savings_ledger.SETTING, value)


async def route(b, tenant, text="placeholder ledger input"):
    response = await b.client.post("/v1/route", json=request(b, tenant, text=text).model_dump(mode="json"))
    assert response.status_code == 200, response.text
    return response.json()


def stable(body):
    """The response with only per-call identifiers and timing taken out."""
    text = json.dumps({key: value for key, value in body.items() if key != "latency_ms"}, sort_keys=True)
    return json.loads(text.replace(body["ledger_id"], "placeholder-ledger-id"))


def app_for(b):
    app = FastAPI()
    app.include_router(savings_ledger.build_router(b.tank))
    bind_tenant_endpoints(app)
    return REAL_CLIENT(transport=httpx.ASGITransport(app=app), base_url="http://tank",
                             headers={"X-Tank-Key": b.key})


def headers(tenant, user, role=None):
    return {"x-tervory-user": user, "x-tervory-tenant": str(tenant), **({"x-tervory-role": role} if role else {})}


async def count(b, table):
    async with b.pool.acquire() as conn:
        return await conn.fetchval(f"SELECT count(*) FROM tank.{table}")


@pytest.mark.asyncio
@pytest.mark.parametrize("value", OFF_VALUES)
async def test_unset_or_non_literal_setting_keeps_main_http_behaviour(ladder, monkeypatch, value):
    b = ladder
    await prepare(b, monkeypatch)
    tenant = b.tenants[0]
    set_ledger(monkeypatch, value)
    assert not savings_ledger.enabled() and not savings_ledger.metering_enabled()
    monkeypatch.setenv(savings_ledger.METERING_SETTING, "true")
    assert not savings_ledger.metering_enabled()
    assert savings_ledger.build_router(b.tank).routes == []
    actual = await route(b, tenant)
    real_record = savings_ledger.record

    async def main_behaviour(rt, req, answer):
        return answer

    monkeypatch.setattr(savings_ledger, "record", main_behaviour)
    baseline = await route(b, tenant)
    monkeypatch.setattr(savings_ledger, "record", real_record)
    assert stable(actual) == stable(baseline) and actual["cost_usd"] == .001
    for table in ("savings_ledger", "savings_baselines", "savings_meter_events"):
        assert await count(b, table) == 0
    seen = set()
    for sent in ({}, headers(tenant, FOUNDER), headers(tenant, "placeholder-owner", "org:admin")):
        for method, path in [("GET", "/v1/engine/ledger/statement"), ("GET", "/v1/engine/ledger/founder/statement"),
                             ("POST", "/v1/engine/ledger/founder/baselines"), ("POST", "/v1/engine/ledger/founder/meter"),
                             ("POST", "/v1/engine/ledger/founder/backfill"), ("POST", "/v1/engine/ledger/statement")]:
            params = {"month": month(), "tenant_id": str(tenant)}
            unknown = await b.client.request(method, "/v1/engine/ledger-not-a-route", params=params, headers=sent)
            response = await b.client.request(method, path, params=params, headers=sent)
            assert (response.status_code, response.json()) == (unknown.status_code, unknown.json())
            seen.add(response.status_code)
    assert 404 in seen
    # The receipt hook does no I/O when off and hands back the very same object.
    answer = b.tank.RouteResponse(ledger_id=uuid.uuid4(), model="haiku", rung=1, content="", tokens_in=0,
                                  tokens_out=0, cost_usd=0, latency_ms=0)
    assert await savings_ledger.record(None, None, answer) is answer


@pytest.mark.asyncio
async def test_literal_true_appends_receipt_without_changing_the_route_response(ladder, monkeypatch):
    b = ladder
    await prepare(b, monkeypatch)
    tenant = b.tenants[0]
    set_ledger(monkeypatch, None)
    off = await route(b, tenant)
    set_ledger(monkeypatch, "true")
    on = await route(b, tenant)
    assert stable(on) == stable(off)
    chain = await savings_ledger.rows(b.pool, tenant)
    assert len(chain) == 1
    row = chain[0]
    async with b.pool.acquire() as conn:
        ledger = await conn.fetchrow("SELECT * FROM tank.ledger WHERE tenant_id=$1 AND id=$2", tenant, uuid.UUID(on["ledger_id"]))
        base = await conn.fetchrow("SELECT * FROM tank.savings_baselines WHERE task_type=$1", ledger["task_type"])
    assert row["ledger_id"] == ledger["id"] and row["seq"] == 1 and row["prev_hash"] == savings_ledger.GENESIS
    assert row["cost_usd"] == ledger["cost_usd"] == Decimal("0.001")
    assert (row["task_type"], row["rung"], row["model"], row["cache_layer"]) == ("base.normalize", 1, "haiku", None)
    # Today's rule: the provider default first, the top model second.
    assert (row["baseline_model"], row["top_model"]) == ("sonnet", "opus-fixture") == (base["baseline_model"], base["top_model"])
    assert row["input_usd"] == Decimal("0.0001") and row["output_usd"] == Decimal("0.0005")
    assert row["would_have_cost_usd"] == Decimal("0.00420000") == ledger["standard_cost_usd"]
    assert row["top_cost_usd"] == Decimal("0.02100000") and row["price_date"] == base["effective_from"].astimezone(timezone.utc).date()
    assert base["recorded_by"] == "first use"
    assert row["row_hash"] == savings_ledger.digest(row)
    # A repeated append of the same receipt never adds or changes a row.
    assert await savings_ledger.append(b.pool, tenant, ledger["id"]) is None
    assert await savings_ledger.rows(b.pool, tenant) == chain
    assert (await savings_ledger.verify(b.pool, tenant))["intact"]


@pytest.mark.asyncio
async def test_rows_cannot_be_changed_or_removed_even_by_the_owning_app_role(ladder, monkeypatch):
    b = ladder
    await prepare(b, monkeypatch)
    set_ledger(monkeypatch, "true")
    tenant = b.tenants[0]
    for index in range(3):
        await route(b, tenant, text=f"placeholder ledger input {index}")
    assert (await savings_ledger.verify(b.pool, tenant)) == {
        "intact": True, "rows": 3, "broken_at_seq": None, "head": (await savings_ledger.rows(b.pool, tenant))[-1]["row_hash"]}
    before = await savings_ledger.rows(b.pool, tenant)
    role = "placeholder_ledger_app_" + uuid.uuid4().hex[:8]
    await b.pool.execute(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS")
    try:
        await b.pool.execute(f"GRANT USAGE ON SCHEMA tank TO {role}")
        await b.pool.execute(f"GRANT SELECT,INSERT,UPDATE,DELETE,TRUNCATE ON tank.savings_ledger,tank.savings_baselines TO {role}")
        # The app role that owns the tables is refused too, not only a grantee.
        for statement in ("ALTER TABLE tank.savings_ledger OWNER TO {r}", "ALTER TABLE tank.savings_baselines OWNER TO {r}"):
            await b.pool.execute(statement.format(r=role))
        for as_role in (None, role):
            for sql in ("UPDATE tank.savings_ledger SET cost_usd=0 WHERE tenant_id=$1",
                        "DELETE FROM tank.savings_ledger WHERE tenant_id=$1",
                        "UPDATE tank.savings_baselines SET input_usd=0 WHERE $1::uuid IS NOT NULL",
                        "DELETE FROM tank.savings_baselines WHERE $1::uuid IS NOT NULL"):
                async with b.pool.acquire() as conn:
                    with pytest.raises(asyncpg.RestrictViolationError, match="append-only"):
                        async with conn.transaction():
                            if as_role:
                                await conn.execute(f"SET LOCAL ROLE {as_role}")
                            await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(tenant))
                            await conn.execute(sql, tenant)
            for table in ("savings_ledger", "savings_baselines"):
                async with b.pool.acquire() as conn:
                    with pytest.raises(asyncpg.RestrictViolationError, match="append-only"):
                        async with conn.transaction():
                            if as_role:
                                await conn.execute(f"SET LOCAL ROLE {as_role}")
                            await conn.execute(f"TRUNCATE tank.{table} CASCADE")
        assert await savings_ledger.rows(b.pool, tenant) == before
        # Re-applying the schema keeps every guard in place.
        await b.pool.execute(engine_ledger_ddl())
        with pytest.raises(asyncpg.RestrictViolationError):
            await b.pool.execute("DELETE FROM tank.savings_ledger WHERE tenant_id=$1", tenant)
    finally:
        await b.pool.execute("ALTER TABLE tank.savings_ledger OWNER TO CURRENT_USER")
        await b.pool.execute("ALTER TABLE tank.savings_baselines OWNER TO CURRENT_USER")
        await b.pool.execute(f"DROP OWNED BY {role}")
        await b.pool.execute(f"DROP ROLE {role}")
    # Only a superuser switching triggers off can edit a row; the chain then exposes it.
    async with b.pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL session_replication_role=replica")
        await conn.execute("UPDATE tank.savings_ledger SET cost_usd=0 WHERE tenant_id=$1 AND seq=2", tenant)
    assert await savings_ledger.verify(b.pool, tenant) == {"intact": False, "rows": 3, "broken_at_seq": 2}
    async with b.pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL session_replication_role=replica")
        await conn.execute("DELETE FROM tank.savings_ledger WHERE tenant_id=$1 AND seq=2", tenant)
    assert await savings_ledger.verify(b.pool, tenant) == {"intact": False, "rows": 2, "broken_at_seq": 3}


@pytest.mark.asyncio
async def test_baseline_change_never_moves_past_savings(ladder, monkeypatch):
    b = ladder
    await prepare(b, monkeypatch)
    set_ledger(monkeypatch, "true")
    tenant = b.tenants[0]
    await route(b, tenant, text="placeholder before the change")
    first = (await savings_ledger.rows(b.pool, tenant))[0]
    before = await savings_ledger.statement(b.pool, tenant, month())
    # A provider price change reprices tank.ledger comparisons, never this ledger.
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.proof_prices SET input_usd=.0002,output_usd=.001 WHERE model='sonnet'")
        await conn.execute("UPDATE tank.ledger SET comparison_revision=comparison_revision+1 WHERE tenant_id=$1", tenant)
        repriced = await conn.fetchval("SELECT standard_cost_usd FROM tank.ledger WHERE id=$1", first["ledger_id"])
    assert repriced != first["would_have_cost_usd"]
    await route(b, tenant, text="placeholder still on the dated price")
    second = (await savings_ledger.rows(b.pool, tenant))[1]
    assert second["baseline_id"] == first["baseline_id"] and second["input_usd"] == Decimal("0.0001")
    async with app_for(b) as client:
        founder = headers(b.tenants[0], FOUNDER)
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        refused = await client.post("/v1/engine/ledger/founder/baselines", headers=founder,
                                    json={"task_type": "base.normalize", "model": "sonnet", "effective_from": past})
        assert refused.status_code == 422
        member = await client.post("/v1/engine/ledger/founder/baselines", headers=headers(tenant, "placeholder-member"),
                                   json={"task_type": "base.normalize", "model": "sonnet"})
        assert member.status_code == 403
        pinned = await client.post("/v1/engine/ledger/founder/baselines", headers=founder,
                                   json={"task_type": "base.normalize", "model": "sonnet"})
        assert pinned.status_code == 200 and pinned.json()["top_model"] == "opus-fixture"
        listed = await client.get("/v1/engine/ledger/founder/baselines", headers=founder, params={"task_type": "base.normalize"})
        assert [row["recorded_by"] for row in listed.json()] == ["first use", FOUNDER]
    with pytest.raises(asyncpg.CheckViolationError):
        await b.pool.execute("""INSERT INTO tank.savings_baselines(task_type,baseline_model,input_usd,output_usd,effective_from,recorded_by)
            VALUES('base.normalize','sonnet',0,0,now()-interval '1 second','placeholder-backdate')""")
    await route(b, tenant, text="placeholder after the change")
    chain = await savings_ledger.rows(b.pool, tenant)
    assert chain[0] == first and chain[1] == second
    assert chain[2]["baseline_id"] == pinned.json()["id"] and chain[2]["input_usd"] == Decimal("0.0002")
    assert chain[2]["would_have_cost_usd"] == Decimal("0.00840000")
    after = await savings_ledger.statement(b.pool, tenant, month())
    assert Decimal(after["would_have_cost_usd"]) == (Decimal(before["would_have_cost_usd"]) * 2 + Decimal("0.0084"))
    assert after["compared_with"]["standard"] == ["sonnet"] and after["compared_with"]["top"] == ["opus-fixture"]


@pytest.mark.asyncio
async def test_statement_reconciles_exactly_and_fee_comes_only_from_settings(ladder, monkeypatch):
    b = ladder
    await prepare(b, monkeypatch)
    set_ledger(monkeypatch, "true")
    tenant = b.tenants[0]
    for index in range(4):
        await route(b, tenant, text=f"placeholder statement input {index}")
    # A receipt with no list price stays unpriced: it is never counted as saving.
    async with b.pool.acquire() as conn:
        unpriced = await conn.fetchval("""INSERT INTO tank.ledger(tenant_id,agent,task_type,model,tokens_in,tokens_out,cost_usd)
            VALUES($1,'base','fixture.unpriced','vendor:placeholder',10,10,.002) RETURNING id""", tenant)
    assert await savings_ledger.backfill(b.pool, tenant, datetime.now(timezone.utc) - timedelta(hours=1)) == 1
    assert await savings_ledger.backfill(b.pool, tenant, datetime.now(timezone.utc) - timedelta(hours=1)) == 0
    chain = await savings_ledger.rows(b.pool, tenant)
    assert chain[-1]["ledger_id"] == unpriced and chain[-1]["would_have_cost_usd"] is None
    async with b.pool.acquire() as conn:
        sums = await conn.fetchrow("""SELECT count(*) AS calls,sum(cost_usd) AS cost,sum(would_have_cost_usd) AS would,
              sum(cost_usd) FILTER (WHERE would_have_cost_usd IS NOT NULL) AS priced,
              sum(tokens_in) AS tokens_in,sum(tokens_out) AS tokens_out,
              encode(sha256(convert_to(string_agg(row_hash,'' ORDER BY seq),'UTF8')),'hex') AS digest
            FROM tank.savings_ledger WHERE tenant_id=$1""", tenant)
    result = await savings_ledger.statement(b.pool, tenant, month())
    assert result["calls"] == sums["calls"] == 5 and result["unpriced_calls"] == 1
    assert Decimal(result["cost_usd"]) == sums["cost"] == Decimal("0.006")
    assert Decimal(result["would_have_cost_usd"]) == sums["would"]
    assert Decimal(result["saving_usd"]) == sums["would"] - sums["priced"]
    assert (result["tokens_in"], result["tokens_out"]) == (sums["tokens_in"], sums["tokens_out"])
    assert result["rows_digest"] == sums["digest"] and (result["first_seq"], result["last_seq"]) == (1, 5)
    assert result["fee"] == {"plan": "none", "amount_usd": "0.00", "flat_usd": None, "share": None, "status": "ok"}
    assert "cost_breakdown" not in result and "chain" not in result
    saving = Decimal(result["saving_usd"])
    assert saving == Decimal("0.0128")
    for plan, flat, share, amount, status in [
            ("flat", "25", None, "25.00", "ok"), ("share", None, "0.5", str((saving / 2).quantize(Decimal("0.01"))), "ok"),
            ("base_plus_share", "10", "0.25", str((10 + saving / 4).quantize(Decimal("0.01"))), "ok"),
            ("flat", None, None, None, "price not set"), ("share", None, "2", None, "price not set"),
            ("base_plus_share", "10", None, None, "price not set"), ("monthly", "1", "1", None,
             "fee plan setting is not one of none, flat, share, base_plus_share")]:
        monkeypatch.setenv(savings_ledger.FEE_PLAN_SETTING, plan)
        for name, value in ((savings_ledger.FEE_FLAT_SETTING, flat), (savings_ledger.FEE_SHARE_SETTING, share)):
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, value)
        fee = (await savings_ledger.statement(b.pool, tenant, month()))["fee"]
        assert (fee["plan"], fee["amount_usd"], fee["status"]) == (plan, amount, status)
    founder = await savings_ledger.statement(b.pool, tenant, month(), founder=True)
    lines = founder["cost_breakdown"]["lines"]
    assert sum(Decimal(line["cost_usd"]) for line in lines) == Decimal(founder["cost_breakdown"]["serving_cost_usd"]) == sums["cost"]
    assert sum(line["calls"] for line in lines) == 5 and founder["chain"]["intact"]
    assert {(line["rung_name"], line["model"]) for line in lines} == {("frontier", "haiku"), ("frontier", "vendor:placeholder")}
    empty = await savings_ledger.statement(b.pool, tenant, "2020-01")
    assert empty["calls"] == 0 and empty["cost_usd"] == "0" and empty["closed"]


@pytest.mark.asyncio
async def test_tenant_isolation_in_code_http_and_row_level_security(ladder, monkeypatch):
    b = ladder
    await prepare(b, monkeypatch)
    set_ledger(monkeypatch, "true")
    first, second = b.tenants
    await route(b, first, text="placeholder first tenant")
    for index in range(2):
        await route(b, second, text=f"placeholder second tenant {index}")
    async with app_for(b) as client:
        own = await client.get("/v1/engine/ledger/statement", params={"month": month()},
                               headers=headers(first, "placeholder-owner", "org:admin"))
        assert own.status_code == 200 and own.json()["calls"] == 1 and own.json()["tenant_id"] == str(first)
        assert "cost_breakdown" not in own.json()
        # A tenant_id parameter cannot widen a client's view.
        widened = await client.get("/v1/engine/ledger/statement", params={"month": month(), "tenant_id": str(second)},
                                   headers=headers(first, "placeholder-owner", "org:admin"))
        assert widened.status_code == 200 and widened.json()["tenant_id"] == str(first) and widened.json()["calls"] == 1
        member = await client.get("/v1/engine/ledger/statement", params={"month": month()},
                                  headers=headers(first, "placeholder-member"))
        assert member.status_code == 403
        for path in ("/v1/engine/ledger/founder/statement",):
            refused = await client.get(path, params={"month": month(), "tenant_id": str(second)},
                                       headers=headers(first, "placeholder-owner", "org:admin"))
            assert refused.status_code == 403
        founder = await client.get("/v1/engine/ledger/founder/statement", params={"month": month(), "tenant_id": str(second)},
                                   headers=headers(first, FOUNDER))
        assert founder.status_code == 200 and founder.json()["calls"] == 2 and founder.json()["chain"]["rows"] == 2
        bad = await client.get("/v1/engine/ledger/statement", params={"month": "2026-13"},
                               headers=headers(first, "placeholder-owner", "org:admin"))
        assert bad.status_code == 422
    # Each tenant's chain is its own: sequence numbers restart per tenant.
    assert [r["seq"] for r in await savings_ledger.rows(b.pool, second)] == [1, 2]
    assert (await savings_ledger.verify(b.pool, first))["rows"] == 1
    # Row-level security follows the existing rollout and then holds for a non-bypass role.
    assert not await b.pool.fetchval("""SELECT bool_or(relrowsecurity) FROM pg_class
        WHERE relnamespace='tank'::regnamespace AND relname IN ('savings_ledger','savings_meter_events')""")
    await b.pool.execute("ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY")
    await b.pool.execute(engine_ledger_ddl())
    await b.pool.execute(engine_ledger_ddl())
    assert await b.pool.fetchval("""SELECT bool_and(relrowsecurity AND relforcerowsecurity) FROM pg_class
        WHERE relnamespace='tank'::regnamespace AND relname IN ('savings_ledger','savings_meter_events')""")
    role = "placeholder_ledger_rls_" + uuid.uuid4().hex[:8]
    await b.pool.execute(f"CREATE ROLE {role} NOLOGIN NOBYPASSRLS")
    try:
        await b.pool.execute(f"GRANT USAGE ON SCHEMA tank TO {role}")
        await b.pool.execute(f"GRANT SELECT,INSERT ON tank.savings_ledger,tank.savings_meter_events TO {role}")
        async with b.pool.acquire() as conn, conn.transaction():
            await conn.execute(f"SET LOCAL ROLE {role}")
            await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(first))
            assert await conn.fetchval("SELECT count(*) FROM tank.savings_ledger") == 1
            assert await conn.fetchval("SELECT count(*) FROM tank.savings_ledger WHERE tenant_id=$1", second) == 0
        async with b.pool.acquire() as conn:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                async with conn.transaction():
                    await conn.execute(f"SET LOCAL ROLE {role}")
                    await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(first))
                    await conn.execute("""INSERT INTO tank.savings_meter_events(tenant_id,period,identifier,value_cents,rows_digest)
                        VALUES($1,'2020-01','placeholder-foreign',0,'placeholder')""", second)
        async with b.pool.acquire() as conn, conn.transaction():
            await conn.execute(f"SET LOCAL ROLE {role}")
            await conn.execute("SELECT set_config('app.tenant_id','',true)")
            assert await conn.fetchval("SELECT count(*) FROM tank.savings_ledger") == 0
    finally:
        await b.pool.execute(f"DROP OWNED BY {role}")
        await b.pool.execute(f"DROP ROLE {role}")


@pytest.mark.asyncio
async def test_stripe_metering_has_its_own_setting_and_sends_once_with_fakes(ladder, monkeypatch):
    b = ladder
    await prepare(b, monkeypatch)
    set_ledger(monkeypatch, "true")
    tenant = b.tenants[0]
    await route(b, tenant)
    sent = []

    def stripe(request):
        sent.append(request)
        if request.url.path == "/v1/customers/search":
            return httpx.Response(200, json={"data": [{"id": "cus_placeholder"}]})
        return httpx.Response(200, json={"object": "billing.meter_event"})

    monkeypatch.setattr(savings_ledger, "stripe_client", lambda: REAL_CLIENT(
        base_url=savings_ledger.STRIPE_API, transport=httpx.MockTransport(stripe)))
    monkeypatch.setenv(savings_ledger.FEE_PLAN_SETTING, "flat")
    monkeypatch.setenv(savings_ledger.FEE_FLAT_SETTING, "12.345")
    for value in OFF_VALUES:
        if value is None:
            monkeypatch.delenv(savings_ledger.METERING_SETTING, raising=False)
        else:
            monkeypatch.setenv(savings_ledger.METERING_SETTING, value)
        with pytest.raises(savings_ledger.HTTPException) as refused:
            await savings_ledger.meter(b.pool, tenant, month())
        assert refused.value.status_code == 404
    monkeypatch.setenv(savings_ledger.METERING_SETTING, "true")
    async with app_for(b) as client:
        member = await client.post("/v1/engine/ledger/founder/meter", headers=headers(tenant, "placeholder-member"),
                                   json={"tenant_id": str(tenant), "period": month()})
        assert member.status_code == 403
        still_open = await client.post("/v1/engine/ledger/founder/meter", headers=headers(tenant, FOUNDER),
                                       json={"tenant_id": str(tenant), "period": month()})
        assert still_open.status_code == 409
        start, end = savings_ledger.period(month())
        monkeypatch.setattr(savings_ledger, "_now", lambda: end + timedelta(seconds=1))
        unconfigured = await client.post("/v1/engine/ledger/founder/meter", headers=headers(tenant, FOUNDER),
                                         json={"tenant_id": str(tenant), "period": month()})
        assert unconfigured.status_code == 503 and not sent
        monkeypatch.setenv(savings_ledger.STRIPE_KEY_SETTING, "placeholder-not-a-key")
        monkeypatch.setenv(savings_ledger.METER_EVENT_SETTING, "placeholder_savings_fee")
        first = await client.post("/v1/engine/ledger/founder/meter", headers=headers(tenant, FOUNDER),
                                  json={"tenant_id": str(tenant), "period": month()})
        again = await client.post("/v1/engine/ledger/founder/meter", headers=headers(tenant, FOUNDER),
                                  json={"tenant_id": str(tenant), "period": month()})
    assert first.status_code == again.status_code == 200
    assert first.json()["sent"] and first.json()["value_cents"] == 1235
    assert again.json()["already_sent"] and again.json()["identifier"] == first.json()["identifier"]
    assert [request.url.path for request in sent] == ["/v1/customers/search", "/v1/billing/meter_events"]
    form = dict(httpx.QueryParams(sent[1].content.decode()))
    assert form["event_name"] == "placeholder_savings_fee" and form["payload[value]"] == "1235"
    assert form["payload[stripe_customer_id]"] == "cus_placeholder" and form["identifier"] == first.json()["identifier"]
    assert all(request.url.host == "api.stripe.com" for request in sent)
    assert json.loads(json.dumps(first.json()))["rows_digest"] == (await savings_ledger.statement(b.pool, tenant, month()))["rows_digest"]
