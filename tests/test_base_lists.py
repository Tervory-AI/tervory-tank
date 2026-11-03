"""B4 offline contract tests. No provider, external network, database or real CRM."""
import json
from copy import deepcopy
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import base_list_crm as crm
import base_lists as lists
import httpx
import pytest
from base_metrics import export_records
from command import (
    ADAPTERS,
    Actor,
    PlannedAction,
    adapter_request,
    allowed_tools,
    validate_action,
)
from fastapi import FastAPI, HTTPException

TENANT, OTHER, RECORD = uuid4(), uuid4(), uuid4()
STAMP = "2026-11-02T12:00:00+00:00"
URL = "https://invented.example/contact"


def evidence(value):
    return {"value": value, "verified": True, "source_url": URL, "checked_at": STAMP, "confidence": 90}


def record():
    return {"record_id": str(RECORD), "name": "Invented Company", "licence_key": "invented",
            "state": "DC", "licence_type": "01", "checked_at": STAMP,
            "fields": {key: evidence(value) for key, value in {
                "name": "Invented Company", "city": "Washington", "state": "DC", "licence_type": "01",
                "engine_category": ["dealer"], "website": "https://invented.example/", "phone": "+12025550123",
                "email": ["invented@quality.example"], "socials": [], "email_syntax_ok": True,
                "email_disposable": False, "phone_valid": True, "technologies": ["Shopify"],
                "sells_online": True, "site_newest_year": 2026, "confidence_tier": "ready"}.items()}}


@pytest.mark.parametrize("filters", [
    {"state": "dc"}, {"city": "washington"}, {"licence_type": "01"}, {"engine_category": "dealer"},
    {"has_website": True}, {"has_phone": True}, {"has_email": True}, {"email_syntax_ok": True},
    {"email_disposable": False}, {"phone_valid": True}, {"technologies_contain": "shopify"},
    {"sells_online": True}, {"site_newest_year_at_least": 2026}, {"confidence_tier": "ready"},
    {"checked_on_or_after": "2026-11-02"},
])
def test_every_filter_accepts_verified_values(filters):
    assert lists.matches(record(), lists.FindArgs(**filters))


@pytest.mark.parametrize("filters", [
    {"state": "CA"}, {"city": "elsewhere"}, {"licence_type": "02"}, {"engine_category": "other"},
    {"has_website": False}, {"has_phone": False}, {"has_email": False}, {"email_syntax_ok": False},
    {"email_disposable": True}, {"phone_valid": False}, {"technologies_contain": "other"},
    {"sells_online": False}, {"site_newest_year_at_least": 2027}, {"confidence_tier": "review"},
    {"checked_on_or_after": "2026-11-03"},
])
def test_every_filter_rejects_nonmatching_values(filters):
    assert not lists.matches(record(), lists.FindArgs(**filters))


@pytest.mark.parametrize("key,filters", [
    ("state", {"state": "DC"}), ("city", {"city": "Washington"}), ("licence_type", {"licence_type": "01"}),
    ("engine_category", {"engine_category": "dealer"}), ("website", {"has_website": True}),
    ("phone", {"has_phone": True}), ("email", {"has_email": True}),
    ("email_syntax_ok", {"email_syntax_ok": True}), ("email_disposable", {"email_disposable": False}),
    ("phone_valid", {"phone_valid": True}), ("technologies", {"technologies_contain": "Shopify"}),
    ("sells_online", {"sells_online": True}), ("site_newest_year", {"site_newest_year_at_least": 2020}),
    ("confidence_tier", {"confidence_tier": "ready"}),
])
def test_unverified_or_missing_date_cannot_satisfy_filter(key, filters):
    for patch in ({"verified": False}, {"source_url": None}, {"checked_at": None}):
        row = record()
        row["fields"][key].update(patch)
        assert not lists.matches(row, lists.FindArgs(**filters))


def test_date_uses_original_checks_not_new_record_timestamp():
    row = record()
    row["fields"]["email"]["checked_at"] = "2020-01-01"
    assert not lists.matches(row, lists.FindArgs(checked_on_or_after=date(2026, 1, 1)))


def test_projection_never_promotes_unverified_uploaded_identity():
    row = {"id": RECORD, "raw": {"name": "uploaded", "city": "Washington", "state": "DC"},
           "profile": {"name": {"value": "uploaded", "confidence": 100}}, "passes": {}, "status": "done", "updated_at": STAMP}
    assert "name" not in lists.project(row)["fields"]
    assert not lists.matches(lists.project(row), lists.FindArgs(state="DC"))
    row["raw"]["_base_reference"] = {"source_url": URL, "checked_at": STAMP, "name": "official", "state": "DC",
                                        "licence_type": "01", "address": {"city": "Washington"}}
    projected = lists.project(row)
    assert projected["fields"]["name"]["value"] == "official"
    assert lists.matches(projected, lists.FindArgs(state="DC", city="Washington", licence_type="01"))


def test_base_only_and_no_paid_adapters_or_identity_arguments(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(box_region=lambda: "us-east"))
    base = Actor(TENANT, "invented", False, frozenset({"base"}))
    tiger = Actor(TENANT, "invented", False, frozenset({"tiger"}))
    for name in ("base.find", "base.list.save", "base.lists", "base.list.show", "base.list.export", "base.list.to_crm"):
        assert name in allowed_tools(base)
        assert name not in allowed_tools(tiger)
        assert not ADAPTERS[name].paid
    action = validate_action(PlannedAction(tool="base.find", arguments={"state": "DC"}), base)
    method, _, _, body = adapter_request(action, base)
    assert method == "GET" and body is None
    for foreign in ("tenant_id", "user_id", "region"):
        with pytest.raises(HTTPException):
            validate_action(PlannedAction(tool="base.find", arguments={foreign: str(OTHER)}), base)
    with pytest.raises(HTTPException):
        validate_action(action, tiger)


class Pool:
    """A SQL boundary double that enforces the same explicit tenant predicates."""
    def __init__(self):
        self.saved = {}
        self.seen = []
    def acquire(self):
        return self
    def transaction(self, **kwargs):
        return self
    async def execute(self, sql, tenant, list_id, chunk):
        assert "WHERE tenant_id=$1 AND list_id=$2" in sql
        saved = self.saved[tenant, list_id]
        saved["records"] = json.dumps(json.loads(saved["records"]) + json.loads(chunk))
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def fetchrow(self, sql, *args):
        self.seen.append((sql, args))
        if sql.startswith("INSERT"):
            tenant, name, filters, ids = args
            records = "[]"
            key = uuid4()
            self.saved[tenant, key] = {"list_id": key, "name": name, "filters": filters, "record_ids": ids,
                                       "records": records, "created_at": STAMP}
            return {k: self.saved[tenant, key][k] for k in ("list_id", "name", "created_at")}
        assert "WHERE tenant_id=$1 AND list_id=$2" in sql
        return deepcopy(self.saved.get(tuple(args)))


@pytest.mark.asyncio
async def test_saved_list_is_fixed_tenant_snapshot_and_csv_identical():
    pool = Pool()
    store = lists.Store(pool)
    rows = [record()]
    async def scan(conn, tenant, filters, ids=None):
        assert tenant == TENANT
        for row in deepcopy(rows):
            yield row
    store.scan = scan
    saved = await store.save(TENANT, "Invented list", lists.FindArgs(state="DC"))
    rows.clear()
    snapshot = await store.show(TENANT, saved["list_id"])
    assert snapshot["record_ids"] == [RECORD]
    assert snapshot["records"] == [record()]
    assert export_records(snapshot["records"]).encode() == export_records([record()]).encode()
    with pytest.raises(HTTPException) as error:
        await store.show(OTHER, saved["list_id"])
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_find_query_always_scopes_record_reads_to_tenant():
    class ReadPool(Pool):
        async def cursor(self, sql, tenant, *args, **kwargs):
            assert "FROM agent_base.records" in sql and "WHERE tenant_id=$1" in sql
            assert tenant == TENANT
            assert kwargs["prefetch"] == 200
            for row in []:
                yield row
    assert await lists.Store(ReadPool()).find(TENANT, lists.FindArgs()) == {"total": 0, "records": []}


@pytest.mark.asyncio
async def test_no_binding_sends_nothing_and_returns_each_record(monkeypatch):
    import trigger_crm
    def absent(actor):
        raise HTTPException(503, "CRM is not configured for this tenant")
    async def forbidden(*args, **kwargs):
        pytest.fail("No request may reach CRM without a binding")
    monkeypatch.setattr(trigger_crm, "binding", absent)
    monkeypatch.setattr(trigger_crm, "upstream", forbidden)
    result = await crm.send(SimpleNamespace(tenant_id=TENANT), [record(), record()])
    assert len(result) == 2 and all(row["message"] == "CRM is not configured for this tenant" for row in result)


@pytest.mark.asyncio
async def test_duplicates_by_email_or_website_and_within_card_are_skipped(monkeypatch):
    import trigger_crm
    sent = []
    monkeypatch.setattr(trigger_crm, "binding", lambda actor: None)
    async def upstream(actor, resource, method="GET", **kwargs):
        assert actor.tenant_id == TENANT and resource == "leads"
        if method == "GET":
            return {"open_leads": {"open_leads": [{"email": "existing@quality.example", "website": "https://duplicate.example"}], "leads_count": 1},
                    "close_leads": {"close_leads": [], "leads_count": 0}}
        sent.append(kwargs["data"])
        return {"lead_obj": {"id": str(uuid4())}}
    monkeypatch.setattr(trigger_crm, "upstream", upstream)
    first, second, fresh, repeated = [record() for _ in range(4)]
    first["fields"]["email"] = evidence(["existing@quality.example"])
    second["fields"]["website"] = evidence("https://www.duplicate.example/")
    fresh["fields"]["phone"]["verified"] = False
    repeated = deepcopy(fresh)
    result = await crm.send(SimpleNamespace(tenant_id=TENANT), [first, second, fresh, repeated])
    assert [row["status"] for row in result] == ["skipped", "skipped", "created", "skipped"]
    assert len(sent) == 1 and "phone" not in sent[0]
    assert sent[0]["source"] == "Base" and sent[0]["company_name"] == "Invented Company"
    assert URL in sent[0]["description"] and STAMP in sent[0]["description"]
    assert "phone:" not in sent[0]["description"]


@pytest.mark.asyncio
async def test_confirmation_tenant_binding_and_list_download_endpoint(monkeypatch):
    import command
    actor = Actor(TENANT, "invented", False, frozenset({"base"}))
    monkeypatch.setattr(command, "db", lambda: None)
    app = FastAPI()
    app.include_router(lists.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async def show(self, tenant, list_id):
        assert tenant == TENANT
        return {"name": "Invented list", "records": [record()]}
    async def ledger(self, tenant, records):
        assert tenant == TENANT
        return []
    monkeypatch.setattr(lists.Store, "ledger", ledger)
    monkeypatch.setattr(lists.Store, "show", show)
    monkeypatch.setattr(command, "db", lambda: None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        response = await client.get("/v1/command/base/lists/csv", params={"list_id": str(uuid4())})
        assert response.status_code == 200
        assert response.content == export_records([record()], ledger=[]).encode()
        response = await client.post("/v1/command/base/lists/to-crm", json={"list_id": str(uuid4()), "record_ids": [str(RECORD)]})
        assert response.status_code == 409
        response = await client.post("/v1/command/base/lists/to-crm", json={"list_id": str(uuid4()), "record_ids": [str(uuid4()) for _ in range(101)]})
        assert response.status_code == 422
        response = await client.post("/v1/command/base/lists/save", json={"name": "invented"})
        assert response.status_code == 409


def test_rls_follows_personal_tokens_without_starting_rollout():
    from pathlib import Path
    schema = (Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text()
    addition = schema[schema.index("-- B4 saved Base lists"):]
    assert "'tank.command_threads'::regclass AND relrowsecurity" in addition
    assert "ENABLE ROW LEVEL SECURITY" in addition and "FORCE ROW LEVEL SECURITY" in addition
    assert "AS RESTRICTIVE FOR ALL TO PUBLIC" in addition
    assert "WITH CHECK (tenant_id=NULLIF(current_setting('app.tenant_id',true),'')::uuid)" in addition


@pytest.mark.asyncio
async def test_find_get_returns_count_first_twenty_and_free_receipt(monkeypatch):
    import command
    actor = Actor(TENANT, "invented", False, frozenset({"base"}))
    monkeypatch.setattr(command, "db", lambda: None)
    app = FastAPI()
    app.include_router(lists.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async def find(self, tenant, filters):
        assert tenant == TENANT and filters.state == "DC"
        return {**lists.preview([record() for _ in range(20)]), "total": 27}
    async def receipt(tenant, task):
        assert tenant == TENANT and task == "base.find"
        return str(uuid4())
    monkeypatch.setattr(lists.Store, "find", find)
    monkeypatch.setattr(lists, "receipt", receipt)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://fixture") as client:
        response = await client.get("/v1/command/base/lists/find", params={"state": "DC", "tenant_id": str(OTHER)})
        assert response.status_code == 200
        result = response.json()
        assert result["total"] == 27 and len(result["records"]) == 20
        assert result["cost_usd"] == 0 and result["ledger_id"]
        assert result["records"][0]["fields"]["email"]["source_url"] == URL
        assert result["records"][0]["fields"]["email"]["checked_at"] == STAMP


@pytest.mark.asyncio
async def test_base_corridor_authority_requires_own_confirmed_card(monkeypatch):
    import trigger_crm
    from trigger_commands import CONFIRMED
    base = Actor(TENANT, "invented", False, frozenset({"base"}))
    async def authorized(actor):
        return actor
    monkeypatch.setattr(trigger_crm, "authorized_actor", authorized)
    with pytest.raises(HTTPException):
        await trigger_crm.authority(base)
    token = CONFIRMED.set((TENANT, base.user_id, uuid4(), "base.list.to_crm", {}))
    try:
        assert await trigger_crm.authority(base) == base
        with pytest.raises(HTTPException):
            await trigger_crm.authority(Actor(OTHER, base.user_id, False, frozenset({"base"})))
        with pytest.raises(HTTPException):
            await trigger_crm.authority(Actor(TENANT, base.user_id, False, frozenset({"tiger"})))
    finally:
        CONFIRMED.reset(token)


# Reuse the platform's explicitly local, rolled-back PostgreSQL fixture in CI.
from test_base_database import database  # noqa: F401


@pytest.mark.asyncio
async def test_saved_list_real_postgres_snapshot_and_rls(database):  # noqa: F811 - reused pytest fixture
    from pathlib import Path

    import asyncpg
    conn, runtime = database
    store = lists.Store(runtime.pool())
    rows = [record()]
    async def scan(conn, tenant, filters, ids=None):
        for row in deepcopy(rows):
            yield row
    store.scan = scan
    saved = await store.save(TENANT, "Invented list", lists.FindArgs(state="DC"))
    rows.clear()
    assert (await store.show(TENANT, saved["list_id"]))["records"] == [record()]
    with pytest.raises(HTTPException):
        await store.show(OTHER, saved["list_id"])
    # Join a simulated existing rollout only inside this fixture transaction.
    await conn.execute("ALTER TABLE tank.command_threads ENABLE ROW LEVEL SECURITY")
    await conn.execute((Path(__file__).resolve().parents[1] / "tank/schema.sql").read_text())
    await conn.execute("CREATE ROLE b4_lists_test_reader NOLOGIN NOSUPERUSER NOBYPASSRLS")
    await conn.execute("GRANT USAGE ON SCHEMA tank TO b4_lists_test_reader")
    await conn.execute("GRANT SELECT,INSERT ON tank.base_saved_lists TO b4_lists_test_reader")
    await conn.execute("SET LOCAL ROLE b4_lists_test_reader")
    try:
        await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(OTHER))
        assert await conn.fetchval("SELECT count(*) FROM tank.base_saved_lists WHERE list_id=$1", saved["list_id"]) == 0
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            async with conn.transaction():
                await conn.execute("INSERT INTO tank.base_saved_lists(tenant_id,name,filters,record_ids,records) "
                                   "VALUES($1,'invented','{}',ARRAY[]::uuid[],'[]')", TENANT)
        await conn.execute("SELECT set_config('app.tenant_id',$1,true)", str(TENANT))
        assert await conn.fetchval("SELECT count(*) FROM tank.base_saved_lists WHERE list_id=$1", saved["list_id"]) == 1
    finally:
        await conn.execute("RESET ROLE")


def test_workspace_download_preserves_bytes_and_existing_batch_behavior():
    import subprocess
    from pathlib import Path
    result = subprocess.run(["node", "tests/base_lists_download.cjs"],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
async def test_crm_concurrency_is_five_and_results_stay_in_list_order(monkeypatch):
    import asyncio

    import trigger_crm
    active = peak = 0
    monkeypatch.setattr(trigger_crm, "binding", lambda actor: None)
    async def upstream(actor, resource, method="GET", **kwargs):
        nonlocal active, peak
        if method == "GET":
            return {"open_leads": {"open_leads": [], "leads_count": 0},
                    "close_leads": {"close_leads": [], "leads_count": 0}}
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.005)
        active -= 1
        return {"lead_obj": {"id": str(uuid4())}}
    monkeypatch.setattr(trigger_crm, "upstream", upstream)
    rows = []
    for index in range(13):
        row = record()
        row["record_id"] = str(uuid4())
        row["fields"]["email"] = evidence([f"invented{index}@quality.example"])
        row["fields"]["website"] = evidence(f"https://invented{index}.example/")
        rows.append(row)
    sent = await crm.send(SimpleNamespace(tenant_id=TENANT), rows)
    assert peak == 5 and active == 0
    assert [row["record_id"] for row in sent] == [row["record_id"] for row in rows]
    assert all(row["status"] == "created" for row in sent)
    from command import action_timeout
    assert action_timeout("base.list.to_crm") == 60 + 20 * 45 + 60


def test_new_sql_is_literal_with_bound_runtime_arguments():
    import ast
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    count = 0
    for filename in ("tank/base_lists.py", "tests/base_lists_scale.py", "tests/test_base_lists.py"):
        for node in ast.walk(ast.parse((root / filename).read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {
                "execute", "fetch", "fetchrow", "fetchval", "cursor"}:
                # Existing fixture bootstrap reads the fixed platform schema;
                # it is not a newly constructed/runtime-interpolated statement.
                if isinstance(node.args[0], ast.Call) and '"tank/schema.sql"' in ast.unparse(node.args[0]).replace("'", '"'):
                    continue
                assert isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str), filename
                if len(node.args) > 1:
                    assert "$1" in node.args[0].value, filename
                count += 1
    assert count >= 15


def test_oversized_list_failure_only_exposes_count_on_existing_error_path():
    from command import list_refusal_result
    assert list_refusal_result("base.list.save", 422, {"detail": {"total": 50000, "private": "ignored"}}) == {"total": 50000}
    for tool, status, result in (
        ("base.find", 422, {"detail": {"total": 50000}}),
        ("base.list.save", 500, {"detail": {"total": 50000}}),
        ("base.list.save", 422, {"detail": {"total": "50000"}}),
        ("base.list.save", 422, {"detail": {"total": True}}),
    ):
        assert list_refusal_result(tool, status, result) is None


@pytest.mark.asyncio
async def test_fifty_thousand_matches_keep_twenty_previews_and_refuse_save():
    from uuid import UUID
    pool = Pool()
    store = lists.Store(pool)
    seed = record()
    async def scan(conn, tenant, filters, ids=None):
        for index in range(50000):
            yield {**seed, "record_id": str(UUID(int=index + 1))}
    store.scan = scan
    found = await store.find(TENANT, lists.FindArgs())
    assert found["total"] == 50000 and len(found["records"]) == 20
    with pytest.raises(HTTPException) as error:
        await store.save(TENANT, "invented", lists.FindArgs())
    assert error.value.status_code == 422 and error.value.detail == {"total": 50000}
    assert not pool.saved


@pytest.mark.asyncio
async def test_cursor_uses_one_platform_snapshot_with_tenant_pool():
    from tenant_db import TenantPool, tenant_scope
    class Native(Pool):
        def __init__(self):
            super().__init__()
            self.transactions = []
        def transaction(self, **kwargs):
            self.transactions.append(kwargs)
            return self
        async def execute(self, sql, *args):
            assert sql == "SELECT set_config('app.tenant_id', $1, true)"
            assert args == (str(TENANT),)
        async def cursor(self, sql, tenant, *args, **kwargs):
            assert tenant == TENANT and kwargs["prefetch"] == 200
            for row in []:
                yield row
    native = Native()
    with tenant_scope(TENANT):
        store = lists.Store(TenantPool(native))
        assert await store.find(TENANT, lists.FindArgs()) == {"total": 0, "records": []}
        assert len(native.transactions) == 1
        assert native.transactions[0]["isolation"] == "repeatable_read"
        assert native.transactions[0]["readonly"] is True
        saved = await store.save(TENANT, "invented", lists.FindArgs())
        assert saved["total"] == 0
        assert len(native.transactions) == 2
        assert native.transactions[1]["isolation"] == "repeatable_read"
        assert native.transactions[1]["readonly"] is False
