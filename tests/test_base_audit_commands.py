"""Offline founder/Confirm/attachment boundaries for the existing audit store."""
from contextlib import asynccontextmanager
import csv
import io
import sys
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI, HTTPException

import admin
import base_audit_commands as commands
import command
from base_audit import audit_csv, checked_verdicts, measure
from trigger_commands import CONFIRMED
from test_base_audit import audit_db, campaign  # noqa: F401 -- register shared isolated PostgreSQL fixture

TENANT, OTHER, CAMPAIGN, AUDIT, ATTACHMENT = (uuid4() for _ in range(5))
USER = "placeholder-founder"
ACTOR = command.Actor(TENANT, USER, True)
HEADERS = {"x-tank-key": "placeholder", "x-tervory-admin": USER}


def saved():
    records = [{"record_id": str(uuid4()), "confidence": 80, "checked_at": "2026-11-03",
                "name": "placeholder", "fields": {name: {"value": None, "verified": False}
                for name in ("email", "phone", "website", "socials")}} for _ in range(200)]
    return {"id": AUDIT, "campaign_id": CAMPAIGN, "seed": 42, "population_size": 240,
            "population_sha256": "placeholder", "records": records, "verdicts": {}, "measurement": measure({})}


def reviewed_csv(audit, *, tamper=False):
    reader = csv.DictReader(io.StringIO(audit_csv(audit).lstrip("\ufeff")))
    rows = list(reader)
    for row in rows:
        row["verdict"] = "correct"
    if tamper:
        rows[0]["name"] = "placeholder changed"
    out = io.StringIO()
    writer = csv.DictWriter(out, reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode()


@pytest.fixture
def corridor(monkeypatch):
    audit = saved()
    state = {"actor": ACTOR, "owner": USER, "tenant": TENANT, "content": reviewed_csv(audit), "created": [], "reviewed": []}
    async def guard(key, user):
        assert key == "placeholder" and user == USER
    monkeypatch.setattr(admin, "require_admin", guard)
    async def receipt(tenant, tool):
        assert tenant == TENANT and tool.startswith("base.audit.")
        return str(uuid4())
    monkeypatch.setattr(commands, "receipt", receipt)
    class Conn:
        async def fetchrow(self, sql, attachment, tenant, user):
            assert "attachment_id=$1 AND tenant_id=$2 AND user_id=$3" in sql
            if (attachment, tenant, user) == (ATTACHMENT, state["tenant"], state["owner"]):
                return {"name": "placeholder.csv", "content": state["content"]}
    class Pool:
        @asynccontextmanager
        async def acquire(self):
            yield Conn()
    monkeypatch.setattr(command, "db", lambda: Pool())
    async def create(self, tenant, campaign, seed, actor):
        assert (tenant, campaign, seed, actor) == (TENANT, CAMPAIGN, 42, USER)
        state["created"].append(seed)
        return audit
    async def get(self, tenant, campaign, identity):
        if (tenant, campaign, identity) != (TENANT, CAMPAIGN, AUDIT):
            raise HTTPException(404, "Audit not found.")
        return audit
    async def histogram(self, tenant, campaign):
        assert (tenant, campaign) == (TENANT, CAMPAIGN)
        return {"verified_records": 240}
    async def review(self, tenant, campaign, identity, text, actor, fields):
        assert (tenant, campaign, identity, actor) == (TENANT, CAMPAIGN, AUDIT, USER)
        verdicts = checked_verdicts(text, audit)
        state["reviewed"].append(fields)
        return {**audit, "measurement": measure(verdicts)}
    for name, fn in (("create", create), ("get", get), ("histogram", histogram), ("review", review)):
        monkeypatch.setattr(commands.AuditStore, name, fn)
    app = FastAPI()
    app.include_router(commands.build_router())
    app.dependency_overrides[command.identity] = lambda: state["actor"]
    return app, state, audit


def binding(tool, args):
    return CONFIRMED.set((TENANT, USER, uuid4(), tool, args))


@pytest.mark.asyncio
async def test_start_requires_confirm_and_returns_store_result(corridor):
    app, state, _ = corridor
    args = {"campaign_id": str(CAMPAIGN), "seed": 42}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder", headers=HEADERS) as client:
        assert (await client.post("/v1/command/base/audits/start", json=args)).status_code == 409
        assert not state["created"]
        token = binding("base.audit.start", args)
        try:
            first = await client.post("/v1/command/base/audits/start", json=args)
        finally:
            CONFIRMED.reset(token)
        assert first.status_code == 200
        assert first.json()["audit_id"] == str(AUDIT)
        assert first.json()["histogram"]["verified_records"] == 240
        assert first.json()["ledger_id"] and first.json()["cost_usd"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("tool,path,method", [("base.audit.start", "start", "POST"), ("base.audit.csv", "export", "GET"), ("base.audit.review", "review", "POST")])
async def test_tools_founder_only(corridor, tool, path, method):
    app, state, _ = corridor
    state["actor"] = command.Actor(TENANT, "placeholder-member", False, frozenset({"base"}))
    assert tool not in command.allowed_tools(state["actor"])
    args = {"campaign_id": str(CAMPAIGN)}
    args.update({"seed": 42} if path == "start" else {"audit_id": str(AUDIT)})
    if path == "review":
        args["attachment_id"] = str(ATTACHMENT)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder", headers=HEADERS) as client:
        response = await client.request(method, "/v1/command/base/audits/" + path, **({"params": args} if method == "GET" else {"json": args}))
        assert response.status_code == 403


@pytest.mark.asyncio
async def test_csv_read_is_free_and_tenant_scoped(corridor):
    app, state, audit = corridor
    args = {"campaign_id": str(CAMPAIGN), "audit_id": str(AUDIT)}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder", headers=HEADERS) as client:
        response = await client.get("/v1/command/base/audits/export", params=args)
        assert response.status_code == 200 and response.json()["cost_usd"] == 0
        assert response.json()["ledger_id"] and "audit_id=" in response.json()["url"]
        response = await client.get("/v1/command/base/audits/csv", params=args)
        assert response.text == audit_csv(audit)
        state["actor"] = command.Actor(OTHER, USER, True)
        assert (await client.get("/v1/command/base/audits/csv", params=args)).status_code == 404


@pytest.mark.asyncio
async def test_review_binding_attachment_owner_and_unchanged_csv(corridor):
    app, state, audit = corridor
    args = {"campaign_id": str(CAMPAIGN), "audit_id": str(AUDIT), "attachment_id": str(ATTACHMENT)}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder", headers=HEADERS) as client:
        assert (await client.post("/v1/command/base/audits/review", json=args)).status_code == 409
        token = binding("base.audit.review", args)
        try:
            state["owner"] = "placeholder-other"
            assert (await client.post("/v1/command/base/audits/review", json=args)).status_code == 404
            state["owner"], state["tenant"] = USER, OTHER
            assert (await client.post("/v1/command/base/audits/review", json=args)).status_code == 404
            state["tenant"] = TENANT
            state["content"] = reviewed_csv(audit, tamper=True)
            assert (await client.post("/v1/command/base/audits/review", json=args)).status_code == 422
            state["content"] = reviewed_csv(audit)
            response = await client.post("/v1/command/base/audits/review", json=args)
            assert response.status_code == 200
            assert response.json()["measurement"]["accuracy"] == 1
            assert response.json()["measurement"]["confidence_interval"]["lower"] < 1
        finally:
            CONFIRMED.reset(token)


def test_adapters_supply_actor_identity_without_body_scope(monkeypatch):
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(box_region=lambda: "us-east"))
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", USER)
    for tool, args in (("base.audit.start", {"campaign_id": str(CAMPAIGN), "seed": 42}),
                       ("base.audit.review", {"campaign_id": str(CAMPAIGN), "audit_id": str(AUDIT), "attachment_id": str(ATTACHMENT)})):
        action = command.validate_action(command.PlannedAction(tool=tool, arguments=args), ACTOR)
        _, _, params, body = command.adapter_request(action, ACTOR)
        assert params == {} and body == args
        assert not command.ADAPTERS[tool].paid


def test_workspace_audit_download_preserves_bytes_and_status():
    import subprocess
    from pathlib import Path
    result = subprocess.run(["node", "tests/base_audit_download.cjs"],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.asyncio
@pytest.mark.usefixtures("audit_db")
async def test_start_same_seed_uses_real_saved_audit(request, monkeypatch):
    pool, rt, _ = request.getfixturevalue("audit_db")
    campaign_id, _ = await campaign(pool, tenant=TENANT)
    monkeypatch.setattr(command, "db", lambda: pool)
    monkeypatch.setenv("TANK_API_KEY", "placeholder")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", USER)
    async def receipt(tenant, tool):
        assert (tenant, tool) == (TENANT, "base.audit.start")
        return str(uuid4())
    monkeypatch.setattr(commands, "receipt", receipt)
    app = FastAPI()
    app.include_router(commands.build_router())
    app.dependency_overrides[command.identity] = lambda: ACTOR
    args = {"campaign_id": str(campaign_id), "seed": 42}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder", headers=HEADERS) as client:
        assert (await client.post("/v1/command/base/audits/start", json=args)).status_code == 409
        token = binding("base.audit.start", args)
        try:
            first = await client.post("/v1/command/base/audits/start", json=args)
            second = await client.post("/v1/command/base/audits/start", json=args)
        finally:
            CONFIRMED.reset(token)
    assert first.status_code == second.status_code == 200, (first.text, second.text)
    assert first.json()["audit_id"] == second.json()["audit_id"]
    from uuid import UUID
    store = commands.AuditStore(rt)
    original = await store.get(TENANT, campaign_id, UUID(first.json()["audit_id"]))
    reopened = await store.create(TENANT, campaign_id, 42, USER)
    assert reopened["id"] == original["id"]
    assert len(original["records"]) == 200 and reopened["records"] == original["records"]
    assert reopened["population_sha256"] == original["population_sha256"]
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT count(*) FROM tank.base_audits WHERE tenant_id=$1 AND campaign_id=$2 AND seed=$3", TENANT, campaign_id, 42)
    assert count == 1
