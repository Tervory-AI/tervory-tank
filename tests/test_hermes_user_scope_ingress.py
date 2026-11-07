"""Residual ingress + lifecycle binding on top of merged Hermes user_scope."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest
from fastapi import FastAPI, Request

from hermes.user_scope import TENANT_WIDE_KINDS, write_meta
from test_agent_memory_records import memory as memory_fixture, Encoder

memory = memory_fixture


def test_ghost_blocked_address_is_declared_tenant_wide_not_null_default():
    assert "blocked_address" in TENANT_WIDE_KINDS["ghost"]
    # Null user_id alone never grants shared scope for undeclared kinds.
    with pytest.raises(ValueError, match="Personal memory requires meta.user_id"):
        write_meta("ghost", "ghost.personal", {})
    assert write_meta("ghost", "blocked_address", {}) == {}


def test_lifecycle_message_binds_verified_tenant_user_when_present():
    from ghost_routes import lifecycle_message
    body = b'{"ok":true}'
    plain = lifecycle_message("100", "POST", "/ghost/autumbra/enforce/list", body)
    assert plain == b"100\nPOST\n/ghost/autumbra/enforce/list\n" + body
    tenant = "11111111-1111-1111-1111-111111111111"
    user = "placeholder-user-a"
    bound = lifecycle_message("100", "POST", "/ghost/autumbra/enforce/list", body, tenant=tenant, user=user)
    assert bound == f"100\nPOST\n/ghost/autumbra/enforce/list\n{tenant}\n{user}\n".encode() + body
    assert plain != bound


@pytest.mark.asyncio
async def test_enforce_lifecycle_accepts_bound_form_and_rejects_forged_user(monkeypatch):
    from agents.ghost import enforce_api
    key = "fixture-lifecycle-key"
    monkeypatch.setenv("AUTUMBRA_LIFECYCLE_KEY", key)
    tenant = "11111111-1111-1111-1111-111111111111"
    user = "placeholder-user-a"
    body = b"{}"
    ts = str(int(time.time()))
    bound = f"{ts}\nPOST\n/ghost/autumbra/enforce/list\n{tenant}\n{user}\n".encode() + body
    sig = hmac.new(key.encode(), bound, hashlib.sha256).hexdigest()
    app = FastAPI()

    @app.post("/ghost/autumbra/enforce/list")
    async def route(request: Request):
        await enforce_api.verify_lifecycle(request, "AUTUMBRA_LIFECYCLE_KEY")
        return {"ok": True}

    headers = {
        "X-Lifecycle-Timestamp": ts,
        "X-Lifecycle-Signature": sig,
        "X-Tervory-Tenant": tenant,
        "X-Tervory-User": user,
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        assert (await client.post("/ghost/autumbra/enforce/list", content=body, headers=headers)).status_code == 200
        forged = {**headers, "X-Tervory-User": "placeholder-attacker"}
        assert (await client.post("/ghost/autumbra/enforce/list", content=body, headers=forged)).status_code == 401
        # Old three-line signatures still work when no tenant/user headers are sent.
        old = f"{ts}\nPOST\n/ghost/autumbra/enforce/list\n".encode() + body
        old_headers = {
            "X-Lifecycle-Timestamp": ts,
            "X-Lifecycle-Signature": hmac.new(key.encode(), old, hashlib.sha256).hexdigest(),
            "Content-Type": "application/json",
        }
        assert (await client.post("/ghost/autumbra/enforce/list", content=body, headers=old_headers)).status_code == 200


def test_verified_memory_actor_never_reads_body():
    from command import Actor, verified_memory_actor
    from fastapi import HTTPException
    actor = Actor(uuid.UUID("11111111-1111-1111-1111-111111111111"), "placeholder-user-a", False)
    assert verified_memory_actor(actor) == ("11111111-1111-1111-1111-111111111111", "placeholder-user-a")
    with pytest.raises(HTTPException) as refused:
        verified_memory_actor(None)
    assert refused.value.status_code == 401


@pytest.mark.asyncio
async def test_two_users_same_tenant_hermes_sql_before_vector(memory, monkeypatch):
    """Opli/Workspace acceptance criterion against current main Hermes."""
    from hermes.service import create_app
    from hermes.store import InMemoryStore
    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), "placeholder-agent-key")
    monkeypatch.setitem(TENANT_WIDE_KINDS, m.agent, frozenset({"placeholder.shared"}))
    app = create_app(InMemoryStore(), Encoder(), records=m.records)
    headers = {"X-Tank-Key": "placeholder-agent-key"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        a = (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder secret a", "kind": "placeholder.personal",
            "source": "https://placeholder.example/a", "user_id": "placeholder-user-a",
            "meta": {"user_id": "placeholder-user-a"},
        })).json()
        await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder secret b", "kind": "placeholder.personal",
            "source": "https://placeholder.example/b", "user_id": "placeholder-user-b",
            "meta": {"user_id": "placeholder-user-b"},
        })
        shared = (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder shared", "kind": "placeholder.shared",
            "source": "https://placeholder.example/s",
        })).json()
        # Missing user on personal kind refused.
        assert (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder missing", "kind": "placeholder.personal",
            "source": "https://placeholder.example/m",
        })).status_code == 422
        # Forged meta owner conflicting with body user_id refused.
        assert (await client.post("/memories", headers=headers, json={
            "tenant_id": m.tenant, "text": "placeholder forged", "kind": "placeholder.personal",
            "source": "https://placeholder.example/f", "user_id": "placeholder-user-a",
            "meta": {"user_id": "placeholder-user-b"},
        })).status_code == 422
        hits = (await client.post("/recall", headers=headers, json={
            "tenant_id": m.tenant, "query": "placeholder secret", "user_id": "placeholder-user-a",
        })).json()["memories"]
        ids = {row["id"] for row in hits}
        assert a["id"] in ids and shared["id"] in ids
        assert all((row.get("meta") or {}).get("user_id") in (None, "placeholder-user-a") or row["kind"] == "placeholder.shared"
                   for row in hits)
