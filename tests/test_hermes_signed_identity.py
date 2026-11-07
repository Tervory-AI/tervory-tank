"""Hermes verifies lifecycle-bound tenant+user for personal memory ops.

Closes: agent-key + forged body user_id without matching signed identity.
Tenant-wide declared kinds remain agent-key-only (no user).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import httpx
import pytest
from chassis.memory import MemoryClient

from hermes_lifecycle import personal_headers
from test_agent_memory_records import memory as memory_fixture, Encoder

memory = memory_fixture
KEY = "placeholder-agent-key"
USER_A = "placeholder-user-a"
ATTACKER = "placeholder-attacker"


@pytest.mark.asyncio
async def test_direct_agent_key_forged_user_denied_valid_signed_succeeds(memory, monkeypatch):
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    from hermes.user_scope import TENANT_WIDE_KINDS

    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), KEY)
    monkeypatch.setitem(TENANT_WIDE_KINDS, m.agent, frozenset({"placeholder.shared"}))
    hermes = create_app(InMemoryStore(), Encoder(), records=m.records)

    forged_body = {
        "tenant_id": m.tenant,
        "text": "forged-personal",
        "kind": "placeholder.personal",
        "source": "urn:placeholder:forged",
        "user_id": ATTACKER,
        "meta": {"user_id": ATTACKER},
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=hermes), base_url="http://hermes"
    ) as hc:
        # Bypass: agent key + forged user_id, no lifecycle → denied.
        denied = await hc.post(
            "/memories", headers={"X-Tank-Key": KEY}, json=forged_body
        )
        assert denied.status_code == 401, denied.text

        # Tampered signature → denied.
        headers, raw = personal_headers(
            KEY, "POST", "/memories", tenant=m.tenant, user=ATTACKER, body=forged_body
        )
        headers["X-Lifecycle-Signature"] = "0" * 64
        assert (await hc.post("/memories", headers=headers, content=raw)).status_code == 401

        # Header user vs body user mismatch → 403.
        headers, raw = personal_headers(
            KEY, "POST", "/memories", tenant=m.tenant, user=USER_A, body=forged_body
        )
        # Re-sign would bind USER_A but body says ATTACKER — personal_headers used USER_A
        # while body still has ATTACKER → mismatch after verify.
        # Actually personal_headers signed with USER_A and body bytes include ATTACKER.
        # verify checks header user == body user → 403.
        mismatched = await hc.post("/memories", headers=headers, content=raw)
        assert mismatched.status_code == 403, mismatched.text

        # Missing lifecycle with personal user on recall → 401.
        recall_body = {
            "tenant_id": m.tenant,
            "query": "forged",
            "user_id": ATTACKER,
        }
        assert (
            await hc.post("/recall", headers={"X-Tank-Key": KEY}, json=recall_body)
        ).status_code == 401

        # Tenant-wide (no user) still works with agent key only.
        shared = await hc.post(
            "/memories",
            headers={"X-Tank-Key": KEY},
            json={
                "tenant_id": m.tenant,
                "text": "shared-ok",
                "kind": "placeholder.shared",
                "source": "urn:placeholder:shared",
            },
        )
        assert shared.status_code == 201, shared.text

        # Valid MemoryClient (production path) succeeds for personal CRUD/list.
        client = MemoryClient("http://hermes", KEY, m.agent, hc, user_id=USER_A)
        saved = await client.remember(
            m.tenant,
            "signed-personal-ok",
            "placeholder.personal",
            "urn:placeholder:ok",
            user_id=USER_A,
            meta={"task": "signed"},
        )
        assert saved["id"]
        rows = await client.records(m.tenant, user_id=USER_A)
        assert saved["id"] in {r["id"] for r in rows}
        hits = await client.recall(m.tenant, "signed-personal", user_id=USER_A)
        assert saved["id"] in {r["id"] for r in hits}
        edited = await client.remember(
            m.tenant,
            "signed-personal-edited",
            "placeholder.personal",
            "urn:placeholder:edit",
            user_id=USER_A,
            record_id=saved["id"],
            replace=True,
            meta={"user_id": USER_A, "edited": True},
        )
        assert edited["id"] == saved["id"]
        await client.forget(saved["id"], m.tenant, user_id=USER_A)
        assert saved["id"] not in {r["id"] for r in await client.records(m.tenant, user_id=USER_A)}

        # Unsigned list with user_id denied.
        assert (
            await hc.get(
                "/records",
                headers={"X-Tank-Key": KEY},
                params={"tenant_id": m.tenant, "user_id": USER_A},
            )
        ).status_code == 401

        # Unsigned list without user (tenant-wide only) allowed.
        bare = await hc.get(
            "/records",
            headers={"X-Tank-Key": KEY},
            params={"tenant_id": m.tenant},
        )
        assert bare.status_code == 200, bare.text
        assert shared.json()["id"] in {r["id"] for r in bare.json()["memories"]}
