"""Offline package, room boundary, approval and rollback proof. No model calls."""
from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

import asyncpg
import httpx
import pytest
import pytest_asyncio

import skala
import skala_intake

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "agents"), str(ROOT / "agents/_chassis"), str(ROOT / "agents/tiger")]
from chassis.tank import TankClient
from trigger import checkers
from trigger.voice import Voice, VoiceStore

TENANT = UUID("00000000-0000-0000-0000-000000000011")
OTHER = UUID("00000000-0000-0000-0000-000000000012")
PACKAGES = {k: p for k, p in skala.load_packages().items() if p.id in skala_intake.IDS and p.version == "1.0.0"}
RESPONSES = json.loads(Path(__file__).with_name("languagetool-responses.json").read_text())
CONFIG_HASH = hashlib.sha256((ROOT / "agents/trigger/languagetool.properties").read_bytes()).hexdigest()


async def no_model(**kwargs):
    raise AssertionError("No model is allowed in this intake")


def context(pkg, http):
    return skala.SkillContext(TENANT, pkg.ref, pkg.agent, None, no_model, http)


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", sorted(PACKAGES))
async def test_each_package_meets_real_skala_gate(identity, monkeypatch):
    monkeypatch.setenv("TANK_KEY_TRIGGER", "offline-test-fixture")
    def reply(request):
        assert str(request.url) == "http://agent-trigger:8000/skala/languagetool"
        body = json.loads(request.content)
        assert body["tenant_id"] == str(TENANT)
        return httpx.Response(200, json={"result": RESPONSES[body["text"]], "config_sha256": CONFIG_HASH})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
        pkg = PACKAGES[identity]
        result = await skala.run_evals(pkg, lambda: context(pkg, http))
        assert result["eligible"]
        assert result["score"] == result["threshold"] == 1.0, [d for d in result["details"] if not d["passed"]]
        assert result["total"] >= 20 and result["cost_usd"] == 0
        assert not any(d["used_model"] for d in result["details"])


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 404, 500, 503])
async def test_client_never_falls_back_on_a_service_or_auth_failure(status):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json={}))) as http:
        client = TankClient("http://tank:8000", "offline-test-fixture", "trigger", http)
        with pytest.raises(httpx.HTTPStatusError):
            await client.approved_skill(str(TENANT), "trigger.proselint", {"text": "A draft."})


@pytest.mark.asyncio
async def test_absence_allows_legacy_but_post_approval_failure_does_not():
    calls = []
    def reply(request):
        calls.append(request.method)
        return httpx.Response(409, json={"detail": "trigger.proselint has no approved version"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(reply)) as http:
        client = TankClient("http://tank:8000", "offline-test-fixture", "trigger", http)
        assert await client.approved_skill(str(TENANT), "trigger.proselint", {"text": "A draft."}) is None
        assert calls == ["GET"]
    def retired_between_calls(request):
        return httpx.Response(200, json={"version": "1.0.0"}) if request.method == "GET" else httpx.Response(409)
    async with httpx.AsyncClient(transport=httpx.MockTransport(retired_between_calls)) as http:
        client = TankClient("http://tank:8000", "offline-test-fixture", "trigger", http)
        with pytest.raises(RuntimeError, match="409"):
            await client.approved_skill(str(TENANT), "trigger.proselint", {"text": "A draft."})


@pytest.mark.asyncio
async def test_tampered_rule_archive_is_refused(tmp_path):
    original = PACKAGES[("trigger.voice_check", "1.0.0")]
    destination = tmp_path / "1.0.1"
    shutil.copytree(original.path, destination)
    (destination / "rules.zip").write_bytes(b"changed rules")
    pkg = dataclasses.replace(original, version="1.0.1", path=destination)
    async with httpx.AsyncClient() as http:
        with pytest.raises(ValueError, match="Pinned checker data changed"):
            await skala._import_run_uncached(pkg)({"text": "The cat sits."}, context(pkg, http))


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["version", "config", "incomplete"])
async def test_languagetool_runtime_mismatch_never_silently_passes(change, monkeypatch):
    monkeypatch.setenv("TANK_KEY_TRIGGER", "offline-test-fixture")
    result = json.loads(json.dumps(RESPONSES["This is a test."]))
    digest = CONFIG_HASH
    if change == "version": result["software"]["version"] = "other"
    if change == "config": digest = "changed"
    if change == "incomplete": result["warnings"] = {"incompleteResults": True}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"result": result, "config_sha256": digest}))) as http:
        pkg = PACKAGES[("trigger.languagetool", "1.0.0")]
        with pytest.raises((ValueError, RuntimeError)):
            await skala.run_skill(pkg, {"text": "This is a test."}, context(pkg, http))


@pytest.mark.asyncio
async def test_mixed_approval_uses_only_unapproved_legacy_sections(monkeypatch):
    def forbidden(*args): raise AssertionError("Approved proselint must not run from the room")
    monkeypatch.setattr(checkers, "LintFile", forbidden)
    class Skills:
        async def approved_skill(self, tenant, skill, payload):
            assert tenant == str(TENANT)
            if skill == "trigger.proselint":
                return {"issues": [], "_skill": skill + "@1.0.0"}
            return None
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"matches": []}))) as http:
        report = await checkers.check("It was completed by the team.", None, http, tank=Skills(), tenant_id=TENANT)
        assert report["complete"]
        assert any(i["rule"] == "passive_voice" for i in report["issues"])


@pytest_asyncio.fixture
async def database():
    dsn = os.environ.get("SKALA_INTAKE_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("Disposable cloud Postgres is required for persisted approval proof")
    assert urlsplit(dsn).hostname in {"skala-intake-pg", "127.0.0.1", "localhost"}
    db = await asyncpg.create_pool(dsn, min_size=1, max_size=4)
    async with db.acquire() as conn:
        await conn.execute((ROOT / "tank/schema.sql").read_text())
        await conn.execute((ROOT / "tank/schema.sql").read_text())
        await conn.execute("CREATE SCHEMA IF NOT EXISTS agent_trigger")
        await conn.execute((ROOT / "agents/trigger/schema.sql").read_text())
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_persisted_ready_bulk_approval_room_execution_tenant_scope_and_rollback(database, monkeypatch, tmp_path):
    import main as tank
    # Keep this disposable database isolated from every other test/package.
    monkeypatch.setattr(tank, "_pool", database)
    monkeypatch.setattr(tank, "_packages", dict(PACKAGES))
    monkeypatch.setattr(tank, "_agent_keys_synced", True)
    monkeypatch.setattr(tank, "TANK_API_KEY", "workspace-offline-fixture")
    monkeypatch.setenv("TANK_KEY_TRIGGER", "offline-test-fixture")
    monkeypatch.setattr(tank, "_model_for_skill", no_model)
    await tank.register_packages()
    transport = httpx.ASGITransport(app=tank.app)
    async def dispatch(request):
        if request.url.host == "tank":
            return await transport.handle_async_request(request)
        if request.url.host == "agent-trigger":
            assert request.headers["x-tank-key"] == "offline-test-fixture"
            body = json.loads(request.content)
            return httpx.Response(200, json={"result": RESPONSES[body["text"]], "config_sha256": CONFIG_HASH})
        if request.url.host == "trigger-languagetool":
            from urllib.parse import parse_qs
            text = parse_qs(request.content.decode())["text"][0]
            return httpx.Response(200, json=RESPONSES[text])
        raise AssertionError("Unexpected network destination")
    async with httpx.AsyncClient(transport=httpx.MockTransport(dispatch)) as http:
        monkeypatch.setattr(tank, "_http", http)
        client = TankClient("http://tank:8000", "offline-test-fixture", "trigger", http)
        voice = Voice(brand="Offline test brand", status="live", revision=1, bannedTerms=["test"])
        store = VoiceStore(database)
        await store.put(TENANT, voice)
        await store.put(OTHER, Voice(brand="Other offline test brand", status="live", revision=1, bannedTerms=["tool"]))
        own = await store.get(TENANT)
        assert own.bannedTerms == ["test"] and (await store.get(OTHER)).bannedTerms == ["tool"]
        legacy = await checkers.check("This is a test.", own, http)
        before = await checkers.check("This is a test.", own, http, tank=client, tenant_id=TENANT)
        assert before == legacy
        # A room cannot select a candidate or smuggle preview permission.
        for preview, version in [(False, None), (False, "1.0.0"), (True, "1.0.0")]:
            response = await http.post("http://tank:8000/v1/skala/trigger.proselint/run",
                headers={"X-Tank-Key": "offline-test-fixture"},
                json={"tenant_id": str(TENANT), "input": {"text": "A draft."}, "version": version, "preview": preview})
            assert response.status_code in {403, 409}
        assert await skala_intake.stage_ready(tank) == []
        async with database.acquire() as conn:
            count = await conn.fetchval("SELECT count(*) FROM tank.skill_evals")
        assert await skala_intake.stage_ready(tank) == []
        async with database.acquire() as conn:
            assert await conn.fetchval("SELECT count(*) FROM tank.skill_evals") == count
        # Passing evals alone do not change client execution.
        assert await client.approved_skill(str(TENANT), "trigger.proselint", {"text": "A draft."}) is None
        preview = await tank.preview_skill_approvals(tank.Approval(by="offline-founder"))
        assert {i["id"] for i in preview["items"]} == skala_intake.IDS
        result = await tank.confirm_skill_approvals(tank.Approval(by="offline-founder", token=preview["token"], confirmed=True))
        assert len(result["approved"]) == 7
        # Every approved checker must skip the room implementation.
        def forbidden(*args): raise AssertionError("Approved checker called room code")
        monkeypatch.setattr(checkers, "LintFile", forbidden)
        monkeypatch.setattr(checkers.detectors_mech, "run", forbidden)
        monkeypatch.setattr(checkers.detectors_struct, "run", forbidden)
        after = await checkers.check("This is a test.", own, http, tank=client, tenant_id=TENANT)
        assert after["issues"] == legacy["issues"]
        assert len(after["skills"]) == 6 and after["complete"] and after["model_calls"] == 0
        async with database.acquire() as conn:
            rows = await conn.fetch("SELECT tenant_id,cost_usd,rung FROM tank.ledger WHERE tenant_id=$1", TENANT)
        assert len(rows) == 6 and all(r["rung"] == 3 and r["cost_usd"] == 0 for r in rows)
        foreign = await checkers.check("This is a test.", await store.get(OTHER), http, tank=client, tenant_id=OTHER)
        assert not any(i["rule"] == "banned_term" for i in foreign["issues"])
        # A future version is created only in this test's temporary directory.
        original = PACKAGES[("trigger.voice_check", "1.0.0")]
        target = tmp_path / "1.1.0"
        shutil.copytree(original.path, target)
        (target / "skill.yaml").write_text((target / "skill.yaml").read_text().replace("version: 1.0.0", "version: 1.1.0"))
        newer = skala._parse_package(target / "skill.yaml", target)
        tank._packages[(newer.id, newer.version)] = newer
        await tank.register_packages()
        assert (await tank.run_skill_evals(newer.id, newer.version))["gate"] == "passed"
        await tank.approve_skill(newer.id, newer.version, tank.Approval(by="offline-founder"))
        assert (await client.approved_skill(str(TENANT), newer.id, {"text": "A draft."}))["_skill"].endswith("@1.1.0")
        await tank.rollback_skill(original.id, original.version, tank.Approval(by="offline-founder", confirmed=True))
        assert (await client.approved_skill(str(TENANT), original.id, {"text": "A draft."}))["_skill"].endswith("@1.0.0")
        skala._run_cache.pop((newer.id, newer.version), None)
