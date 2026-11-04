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
    name = "mobile_test_" + uuid4().hex
    role = name + "_role"
    admin = await asyncpg.connect(url)
    raw = None
    try:
        await admin.execute(f'CREATE DATABASE "{name}"')
        await admin.execute(f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOBYPASSRLS')
        database = urlunsplit((parsed.scheme, parsed.netloc, "/" + name, "", ""))
        owner = await asyncpg.connect(database)
        try:
            schema = (Path(__file__).parents[1] / "tank/schema.sql").read_text()
            await owner.execute("CREATE SCHEMA tank")
            for table in ("command_threads", "command_attachments"):
                statement = re.search(r"CREATE TABLE IF NOT EXISTS tank\." + table + r" \(.*?\n\);", schema, re.S)
                assert statement
                await owner.execute(statement.group())
            migration = schema[schema.index("CREATE TABLE IF NOT EXISTS tank.mobile_codes"):]
            await owner.execute(migration)
            await owner.execute(migration)
            await owner.execute(f'GRANT USAGE ON SCHEMA tank TO "{role}"')
            await owner.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA tank TO "{role}"')
        finally:
            await owner.close()
        authority = f"{role}@{parsed.hostname}:{parsed.port or 5432}"
        raw = await asyncpg.create_pool(urlunsplit((parsed.scheme, authority, "/" + name, "", "")), min_size=1, max_size=2)
        store = TenantPool(raw)
        monkeypatch.setattr(mobile, "db", lambda: store)
        monkeypatch.setenv("TANK_VAULT_KEY", base64.urlsafe_b64encode(bytes(range(32))).decode())
        actor = Actor(uuid4(), "signed-in-user", False)
        other = Actor(uuid4(), "another-user", False)
        verifier = "v" * 43
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        with tenant_scope(actor.tenant_id):
            code = (await mobile.handshake(mobile.Handshake(challenge=challenge, org_id="org-test", org_name="Test"), actor))["code"]
        with pytest.raises(HTTPException):
            await mobile.exchange(mobile.Exchange(code=code, code_verifier="b" * 43, redirect_uri=mobile.CALLBACK))
        session = await mobile.exchange(mobile.Exchange(code=code, code_verifier=verifier, redirect_uri=mobile.CALLBACK))
        with pytest.raises(HTTPException):
            await mobile.exchange(mobile.Exchange(code=code, code_verifier=verifier, redirect_uri=mobile.CALLBACK))
        assert (await mobile.session_identity(session["token"]))["userId"] == actor.user_id
        request = SimpleNamespace(headers={"x-mobile-session": session["token"]})
        with tenant_scope(actor.tenant_id):
            assert (await mobile.register_device(mobile.Device(platform="ios", token="a" * 64), request, actor))["registered"]
            body = mobile.Share(share_id="proof", text="https://example.org", files=[mobile.SharedFile(name="proof.txt", data="aGVsbG8=")])
            draft = await mobile.create_share(body, actor)
            assert await mobile.create_share(body, actor) == draft
            saved = await mobile.get_share(UUID(draft["draft_id"]), actor)
            assert saved["text"] == body.text
            assert saved["attachments"][0]["model_readable"] is False
        with tenant_scope(other.tenant_id):
            with pytest.raises(HTTPException) as failure:
                await mobile.get_share(UUID(draft["draft_id"]), other)
            assert failure.value.status_code == 404
            async with store.acquire() as conn:
                assert await conn.fetchval("SELECT count(*) FROM tank.mobile_devices WHERE tenant_id=$1", actor.tenant_id) == 0
        delivered = []
        class FakePhone:
            async def deliver(self, platform, token, message):
                delivered.append(message.link)
                return "sent"
        assert (await mobile_push.notify(actor.tenant_id, "An update", "Ready", "/chats?proof=1", user_id=actor.user_id, provider=FakePhone()))["sent"] == 1
        assert delivered == ["/chats?proof=1"]
        await mobile.revoke(mobile.Session(token=session["token"]))
        assert (await mobile_push.notify(actor.tenant_id, "An update", "Ready", provider=FakePhone()))["sent"] == 0
    finally:
        if raw is not None:
            await raw.close()
        await admin.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        await admin.execute(f'DROP ROLE IF EXISTS "{role}"')
        await admin.close()
