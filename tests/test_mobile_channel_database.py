import base64
import hashlib
import os
from pathlib import Path
import re
from types import SimpleNamespace
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID, uuid4

import asyncpg
import pytest
from fastapi import HTTPException

import mobile
import mobile_push
from command import Actor
from tenant_db import TenantPool, tenant_scope


@pytest.mark.asyncio
async def test_mobile_sessions_shares_and_notify_with_forced_tenant_rls(monkeypatch):
    url = os.environ.get("MOBILE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("MOBILE_TEST_DATABASE_URL opts into a disposable local database")
    parsed = urlsplit(url)
    assert parsed.hostname in {"127.0.0.1", "localhost"}
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("TANK_API_KEY", "placeholder-mobile-workspace")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "placeholder-mobile-import")
    name = "mobile_test_" + uuid4().hex
    role = name + "_role"
    admin = await asyncpg.connect(url)
    raw = None
    try:
        create_database = await admin.fetchval("SELECT format('CREATE DATABASE %I', $1::text)", name)
        await admin.execute(create_database)
        create_role = await admin.fetchval("SELECT format('CREATE ROLE %I LOGIN NOSUPERUSER NOBYPASSRLS', $1::text)", role)
        await admin.execute(create_role)
        database = urlunsplit((parsed.scheme, parsed.netloc, "/" + name, "", ""))
        owner = await asyncpg.connect(database)
        try:
            schema = (Path(__file__).parents[1] / "tank/schema.sql").read_text()
            await owner.execute("CREATE SCHEMA tank")
            for table in ("command_threads", "command_attachments"):
                statement = re.search(r"CREATE TABLE IF NOT EXISTS tank\." + table + r" \(.*?\n\);", schema, re.S)
                assert statement
                await owner.execute(statement.group())
            await owner.execute("ALTER TABLE tank.command_threads ADD COLUMN trigger_signin_issuer text NOT NULL DEFAULT ''")
            # Install the actual platform policies on the isolated command tables,
            # rather than enabling RLS without any policy (which denies every row).
            platform_rls = (Path(__file__).parents[1] / "db/migrations/tenant_rls/tank.sql").read_text()
            await owner.execute(platform_rls)
            migration = schema.split("-- BEGIN mobile\n", 1)[1].split("-- END mobile", 1)[0]
            await owner.execute(migration)
            await owner.execute(migration)
            grant_schema = await owner.fetchval("SELECT format('GRANT USAGE ON SCHEMA tank TO %I', $1::text)", role)
            await owner.execute(grant_schema)
            grant_tables = await owner.fetchval("SELECT format('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA tank TO %I', $1::text)", role)
            await owner.execute(grant_tables)
        finally:
            await owner.close()
        authority = f"{role}@{parsed.hostname}:{parsed.port or 5432}"
        raw = await asyncpg.create_pool(urlunsplit((parsed.scheme, authority, "/" + name, "", "")), min_size=1, max_size=2)
        store = TenantPool(raw)
        monkeypatch.setattr(mobile, "db", lambda: store)
        monkeypatch.setenv("TANK_VAULT_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode())
        actor = Actor(uuid4(), "signed-in-user", False)
        other = Actor(uuid4(), "another-user", False)
        from contextvars import ContextVar
        from trigger_signin_fakes import native_provider, ORG
        import trigger_signin_config as registry
        provider = native_provider(monkeypatch, {ORG: str(actor.tenant_id)})
        monkeypatch.setenv("TANK_REGION", "us-east")
        monkeypatch.setattr(registry, "_issuer", ContextVar("mobile_db_fixture", default=provider.issuer))
        verifier = "v" * 43
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        with tenant_scope(actor.tenant_id):
            code = (await mobile.handshake(mobile.Handshake(challenge=challenge, org_id=ORG, org_name="Test"), actor))["code"]
        with pytest.raises(HTTPException):
            await mobile.exchange(mobile.Exchange(code=code, code_verifier="b" * 43, redirect_uri=mobile.CALLBACK))
        session = await mobile.exchange(mobile.Exchange(code=code, code_verifier=verifier, redirect_uri=mobile.CALLBACK))
        with pytest.raises(HTTPException):
            await mobile.exchange(mobile.Exchange(code=code, code_verifier=verifier, redirect_uri=mobile.CALLBACK))
        assert (await mobile.session_identity(session["token"]))["userId"] == actor.user_id
        with tenant_scope(actor.tenant_id):
            async with store.acquire() as conn:
                await conn.execute("UPDATE tank.mobile_sessions SET expires_at=now()-interval '1 second' WHERE tenant_id=$1", actor.tenant_id)
        with pytest.raises(HTTPException):
            await mobile.session_identity(session["token"])
        with tenant_scope(actor.tenant_id):
            async with store.acquire() as conn:
                await conn.execute("UPDATE tank.mobile_sessions SET expires_at=now()+interval '7 days' WHERE tenant_id=$1", actor.tenant_id)
        request = SimpleNamespace(headers={"x-mobile-session": session["token"]})
        with tenant_scope(actor.tenant_id):
            assert (await mobile.register_device(mobile.Device(platform="ios", token="a" * 64), request, actor))["registered"]
            body = mobile.Share(share_id="proof", text="https://example.org", files=[mobile.SharedFile(name="proof.txt", data="aGVsbG8=")])
            draft = await mobile.create_share(body, actor)
            assert await mobile.create_share(body, actor) == draft
            saved = await mobile.get_share(UUID(draft["draft_id"]), actor)
            assert saved["text"] == body.text
            async with store.acquire() as conn:
                assert await conn.fetchval("SELECT trigger_signin_issuer FROM tank.command_threads WHERE tenant_id=$1 AND thread_id=$2", actor.tenant_id, UUID(saved["thread_id"])) == provider.issuer
            assert saved["attachments"][0]["model_readable"] is False
        with tenant_scope(other.tenant_id):
            with pytest.raises(HTTPException) as failure:
                await mobile.get_share(UUID(draft["draft_id"]), other)
            assert failure.value.status_code == 404
            async with store.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM tank.mobile_devices WHERE tenant_id=$1", actor.tenant_id) == 0
                assert await conn.fetchval("SELECT count(*) FROM tank.command_threads WHERE tenant_id=$1", actor.tenant_id) == 0
                assert await conn.fetchval("SELECT count(*) FROM tank.command_attachments WHERE tenant_id=$1", actor.tenant_id) == 0
        delivered = []
        class FakePhone:
            async def deliver(self, platform, token, message):
                delivered.append(message.link)
                return "sent"
        assert (await mobile_push.notify(actor.tenant_id, "An update", "Ready", "/chats?proof=1", user_id=actor.user_id, provider=FakePhone()))["sent"] == 1
        assert delivered == ["/chats?proof=1"]
        await mobile.revoke(mobile.Session(token=session["token"]))
        with pytest.raises(HTTPException):
            await mobile.session_identity(session["token"])
        assert (await mobile_push.notify(actor.tenant_id, "An update", "Ready", provider=FakePhone()))["sent"] == 0
    finally:
        if raw is not None:
            await raw.close()
        drop_database = await admin.fetchval("SELECT format('DROP DATABASE IF EXISTS %I WITH (FORCE)', $1::text)", name)
        await admin.execute(drop_database)
        drop_role = await admin.fetchval("SELECT format('DROP ROLE IF EXISTS %I', $1::text)", role)
        await admin.execute(drop_role)
        await admin.close()
