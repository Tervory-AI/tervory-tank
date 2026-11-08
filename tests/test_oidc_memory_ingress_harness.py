"""OIDC → Tank assertion → product signed actor → MemoryClient → Hermes (PG).

Proof boundary (honest):
- Exercised production code: TriggerSigninMiddleware, product_identity.attach
  (via paid_http), chassis.user_assertion.signed_user, trigger.refuse_scope_widen,
  agents.opli.gates_memory (_remember / view / edit / forget / require_owned_record),
  chassis.MemoryClient, hermes create_app + Records SQL ownership, Publisher.publish.
- Local RSA OIDC issuer: tests/trigger_signin_fakes.Provider (not a cloud IdP).
- Thin ASGI mount only wires those production calls; it does NOT invent ownership
  checks. Edit/forget foreign ids rely on gates_memory.require_owned_record + Hermes.
- Hermes verifies the existing v1 tenant+user assertion and durably consumes its nonce.
  Agent-key alone cannot assert a personal user_id.
- OIDC itself is verified at Tank ingress; Hermes verifies the forwarded assertion.
"""
from __future__ import annotations


import json
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from chassis.memory import MemoryClient
from chassis.user_assertion import PostgresNonces, signed_user
from hermes.publishing import Publisher
from hermes.service import create_app
from hermes.store import InMemoryStore
from hermes.user_scope import TENANT_WIDE_KINDS
import product_identity as identity
from test_agent_memory_records import Encoder, inventory, memory as memory_fixture

memory = memory_fixture

USER_A = "placeholder-user-a"
USER_B = "placeholder-user-b"
ATTACKER = "placeholder-attacker"
KIND = "opli.receipt"  # personal Opli kind
AGENT_KEY = "placeholder-product-agent-key"
PLACEHOLDER_WORKSPACE_KEY = "placeholder-workspace-key"


def _oidc_stack(monkeypatch, tenant: str, subject: str = USER_A):
    import identity_oidc as oidc
    from trigger_signin_fakes import Provider, ORG, install_registry
    from trigger_signin_guard import TriggerSigninMiddleware

    monkeypatch.setitem(
        sys.modules,
        "main",
        SimpleNamespace(TANK_API_KEY=PLACEHOLDER_WORKSPACE_KEY, box_region=lambda: "us-east"),
    )
    monkeypatch.setenv("TANK_KEY_TRIGGER", AGENT_KEY)
    monkeypatch.setenv("TANK_API_KEY", PLACEHOLDER_WORKSPACE_KEY)
    provider = Provider("us-east")
    provider.claims["sub"] = subject
    install_registry(monkeypatch, [provider], {ORG: tenant})
    monkeypatch.setattr(
        oidc, "http_client", lambda: httpx.AsyncClient(transport=httpx.MockTransport(provider))
    )
    oidc._cache.clear()
    return provider, TriggerSigninMiddleware, ORG


def _assert_headers(token: str) -> dict:
    return {identity.HEADER: token, "Content-Type": "application/json"}


@pytest.mark.asyncio
async def test_oidc_ingress_to_hermes_full_personal_crud_list_publish(memory, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "agents"))
    from agents.opli import gates_memory
    from trigger.app import SignedInActor, refuse_scope_widen

    m = memory
    monkeypatch.setenv("TANK_KEY_" + m.agent.upper(), AGENT_KEY)
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", f"{USER_A},{USER_B}")
    monkeypatch.setenv("OPLI_MEMORY_ENABLED", "true")
    monkeypatch.setitem(
        TENANT_WIDE_KINDS,
        m.agent,
        frozenset({"opli.repo_map", "opli.convention"}),
    )
    monkeypatch.setattr(
        gates_memory,
        "TENANT_WIDE_KINDS",
        frozenset({"opli.repo_map", "opli.convention"}),
    )

    hermes = create_app(InMemoryStore(), Encoder(), records=m.records)
    nonces = PostgresNonces(m.pool, m.agent)
    provider, TriggerSigninMiddleware, ORG = _oidc_stack(monkeypatch, m.tenant, USER_A)

    product = FastAPI()

    @product.api_route("/memory/{op}", methods=["GET", "POST", "PATCH"])
    async def memory_op(op: str, request: Request):
        raw = await request.body() if request.method != "GET" else b""
        body = json.loads(raw) if raw else {}
        tenant = str(body.get("tenant_id") or request.query_params.get("tenant_id") or "")
        # Production assertion verify (chassis).
        actor = await signed_user(
            request,
            tenant_id=tenant,
            product="trigger",
            key=AGENT_KEY,
            nonces=nonces,
            required=True,
        )
        # Production Trigger refuse_scope_widen (body cannot replace signed actor).
        signed = SignedInActor(UUID(actor.tenant_id), actor.user_id)
        body_tenant = None
        if body.get("tenant_id"):
            body_tenant = UUID(str(body["tenant_id"]))
        refuse_scope_widen(
            signed,
            body_tenant_id=body_tenant,
            body_user_id=body.get("user_id"),
        )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=hermes), base_url="http://hermes"
        ) as http:
            # Production MemoryClient bound to verified actor user_id only.
            client = MemoryClient(
                "http://hermes", AGENT_KEY, m.agent, http, user_id=actor.user_id
            )
            try:
                if op == "remember":
                    saved = await gates_memory._remember(
                        client,
                        actor.tenant_id,
                        body.get("text") or "oidc-owned-by-a",
                        body.get("kind") or KIND,
                        "urn:placeholder:oidc-harness",
                        user_id=actor.user_id,
                        meta={"task_key": body.get("task_key") or "oidc-harness", "user_id": actor.user_id},
                    )
                    return {"id": saved["id"], "user_id": actor.user_id}
                if op == "recall":
                    hits = await gates_memory._recall(
                        client,
                        actor.tenant_id,
                        body.get("query") or "oidc-owned",
                        user_id=actor.user_id,
                        kind=None,
                        limit=20,
                    )
                    return {"memories": hits, "user_id": actor.user_id}
                if op == "list":
                    # Production list path used by require_owned_record / view.
                    rows = await client.records(actor.tenant_id, user_id=actor.user_id)
                    return {"memories": rows, "user_id": actor.user_id}
                if op == "view":
                    return await gates_memory.view_memories(
                        client,
                        tenant_id=actor.tenant_id,
                        user_id=actor.user_id,
                        task_key=body.get("task_key") or "oidc-harness",
                        memory_id=body.get("memory_id"),
                    )
                if op == "edit":
                    # Production apply_memory_edit → require_owned_record → Hermes.
                    saved = await gates_memory.apply_memory_edit(
                        client,
                        memory_id=body["memory_id"],
                        tenant_id=actor.tenant_id,
                        user_id=actor.user_id,
                        text=body["text"],
                        memory_control="edit",
                    )
                    return {"id": saved["id"], "user_id": actor.user_id}
                if op == "forget":
                    await gates_memory.apply_memory_forget(
                        client,
                        memory_id=body["memory_id"],
                        tenant_id=actor.tenant_id,
                        user_id=actor.user_id,
                        memory_control="forget",
                    )
                    return {"forgotten": body["memory_id"], "user_id": actor.user_id}
                raise HTTPException(404, "unknown op")
            except gates_memory.MemoryScopeError as exc:
                raise HTTPException(403, str(exc)) from None
            except gates_memory.MemoryControlError as exc:
                raise HTTPException(403, str(exc)) from None
            except RuntimeError as exc:
                # Production MemoryClient surfaces Hermes status; do not invent ownership.
                raise HTTPException(
                    404 if "404" in str(exc) else 503, str(exc)
                ) from None

    tank = FastAPI()
    tank.add_middleware(TriggerSigninMiddleware)

    @tank.api_route("/v1/proxy/{op}", methods=["GET", "POST", "PATCH"])
    async def proxy(op: str, request: Request):
        import paid_http

        raw = await request.body()
        async with paid_http.Client(
            transport=httpx.ASGITransport(app=product), follow_redirects=False
        ) as client:
            url = f"http://agent-trigger:8000/memory/{op}"
            if request.method == "GET":
                upstream = await client.get(url, params=dict(request.query_params))
            else:
                upstream = await client.request(
                    request.method,
                    url,
                    content=raw,
                    headers={"Content-Type": "application/json"},
                )
            return Response(
                upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

    oidc_headers = {
        "X-Tank-Key": PLACEHOLDER_WORKSPACE_KEY,
        "X-Trigger-Signin-Token": provider.token(),
        "X-Trigger-Signin-Org": ORG,
        "X-Tervory-User": USER_A,
        "X-Tervory-Tenant": m.tenant,
    }

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=tank), base_url="http://tank"
    ) as client:
        good = {"tenant_id": m.tenant, "text": "oidc-owned-by-a", "task_key": "oidc-a", "kind": KIND}
        created = await client.post("/v1/proxy/remember", headers=oidc_headers, json=good)
        assert created.status_code == 200, created.text
        assert created.json()["user_id"] == USER_A
        row_a = created.json()["id"]

        # Malicious body user_id → production refuse_scope_widen 403
        attacked = await client.post(
            "/v1/proxy/remember",
            headers=oidc_headers,
            json={**good, "user_id": ATTACKER, "text": "should-not-land"},
        )
        assert attacked.status_code == 403, attacked.text

        # Spoofed identity header vs OIDC subject → middleware 403
        spoof = await client.post(
            "/v1/proxy/remember",
            headers={**oidc_headers, "X-Tervory-User": ATTACKER},
            json=good,
        )
        assert spoof.status_code == 403, spoof.text

        # Service key alone → no assertion → signed_user required → 401
        bare = await client.post(
            "/v1/proxy/remember",
            headers={"X-Tank-Key": PLACEHOLDER_WORKSPACE_KEY},
            json=good,
        )
        assert bare.status_code == 401, bare.text

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=product), base_url="http://product"
        ) as pc:
            assert (await pc.post("/memory/remember", json=good)).status_code == 401

        # Seed B via production assertion mint (not OIDC middleware) for isolation proof
        b_body = {
            "tenant_id": m.tenant,
            "text": "oidc-owned-by-b",
            "task_key": "oidc-b",
            "kind": KIND,
        }
        b_raw = json.dumps(b_body, separators=(",", ":")).encode()
        b_tok = identity.sign(
            "trigger",
            identity.User(m.tenant, USER_B, "member"),
            "POST",
            "/memory/remember",
            b_raw,
            key=AGENT_KEY,
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=product), base_url="http://product"
        ) as pc:
            b_resp = await pc.post("/memory/remember", content=b_raw, headers=_assert_headers(b_tok))
            assert b_resp.status_code == 200, b_resp.text
            row_b = b_resp.json()["id"]

        # List/recall as A never includes B (production MemoryClient + Hermes SQL)
        assert (
            await client.post(
                "/v1/proxy/list",
                headers=oidc_headers,
                json={"tenant_id": m.tenant, "user_id": ATTACKER},
            )
        ).status_code == 403
        listed = await client.post(
            "/v1/proxy/list", headers=oidc_headers, json={"tenant_id": m.tenant}
        )
        assert listed.status_code == 200, listed.text
        ids = {r["id"] for r in listed.json()["memories"]}
        assert row_a in ids and row_b not in ids

        recalled = await client.post(
            "/v1/proxy/recall",
            headers=oidc_headers,
            json={"tenant_id": m.tenant, "query": "oidc-owned"},
        )
        assert recalled.status_code == 200, recalled.text
        rids = {r["id"] for r in recalled.json()["memories"]}
        assert row_a in rids and row_b not in rids

        # Foreign edit/forget: production require_owned_record → 403
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=product), base_url="http://product"
        ) as pc:
            edit_body = {
                "tenant_id": m.tenant,
                "memory_id": row_b,
                "text": "hijack-attempt",
            }
            edit_raw = json.dumps(edit_body, separators=(",", ":")).encode()
            edit_tok = identity.sign(
                "trigger",
                identity.User(m.tenant, USER_A, "member"),
                "POST",
                "/memory/edit",
                edit_raw,
                key=AGENT_KEY,
            )
            edited = await pc.post(
                "/memory/edit", content=edit_raw, headers=_assert_headers(edit_tok)
            )
            assert edited.status_code == 403, edited.text

            forget_body = {"tenant_id": m.tenant, "memory_id": row_b}
            forget_raw = json.dumps(forget_body, separators=(",", ":")).encode()
            forget_tok = identity.sign(
                "trigger",
                identity.User(m.tenant, USER_A, "member"),
                "POST",
                "/memory/forget",
                forget_raw,
                key=AGENT_KEY,
            )
            forgotten = await pc.post(
                "/memory/forget", content=forget_raw, headers=_assert_headers(forget_tok)
            )
            assert forgotten.status_code == 403, forgotten.text
            assert await m.records.get(m.agent, m.tenant, row_b, user_id=USER_B) is not None

            # Own edit succeeds via production apply_memory_edit
            own = {
                "tenant_id": m.tenant,
                "memory_id": row_a,
                "text": "oidc-owned-by-a-edited",
            }
            own_raw = json.dumps(own, separators=(",", ":")).encode()
            own_tok = identity.sign(
                "trigger",
                identity.User(m.tenant, USER_A, "member"),
                "POST",
                "/memory/edit",
                own_raw,
                key=AGENT_KEY,
            )
            ok = await pc.post("/memory/edit", content=own_raw, headers=_assert_headers(own_tok))
            assert ok.status_code == 200, ok.text

        # Publish ownership (production Publisher SQL visible())
        await Publisher(m.records).set_policy(m.agent, m.tenant, USER_A, True, inventory())
        pub_a = await Publisher(m.records).publish(m.agent, m.tenant, row_a, USER_A)
        assert pub_a["result"] in ("published", "already_published"), pub_a
        pub_b = await Publisher(m.records).publish(m.agent, m.tenant, row_b, USER_A)
        assert pub_b["result"] == "missing", pub_b

        # Tampered assertion (wrong key)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=product), base_url="http://product"
        ) as pc:
            bad_raw = json.dumps({"tenant_id": m.tenant}, separators=(",", ":")).encode()
            bad = identity.sign(
                "trigger",
                identity.User(m.tenant, USER_A, "member"),
                "POST",
                "/memory/list",
                bad_raw,
                key="placeholder-wrong-key",
            )
            refused = await pc.post(
                "/memory/list", content=bad_raw, headers=_assert_headers(bad)
            )
            assert refused.status_code == 401

        # Direct Hermes: agent-key + forged user_id without assertion → 401 (closed).
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=hermes), base_url="http://hermes"
        ) as hc:
            forged = await hc.post(
                "/memories",
                headers={"X-Tank-Key": AGENT_KEY},
                json={
                    "tenant_id": m.tenant,
                    "text": "direct-hermes-forged",
                    "kind": KIND,
                    "source": "urn:placeholder:direct",
                    "user_id": ATTACKER,
                    "meta": {"user_id": ATTACKER},
                },
            )
            assert forged.status_code == 401, forged.text


@pytest.mark.asyncio
async def test_verified_memory_actor_used_on_opli_scope(monkeypatch):
    import command
    from integrations.tank import opli_memory

    actor = command.Actor(uuid.UUID("11111111-1111-1111-1111-111111111111"), USER_A, False)
    seen = {}

    class GM:
        class MemoryScopeError(Exception):
            pass

        @staticmethod
        def require_authenticated_scope(*, tenant_id, user_id):
            seen["tenant_id"] = str(tenant_id)
            seen["user_id"] = str(user_id)
            return str(tenant_id), str(user_id)

    monkeypatch.setattr(opli_memory, "_load_product", lambda: (GM, None))
    tenant, user = opli_memory._actor_scope(actor)
    assert (tenant, user) == (
        "11111111-1111-1111-1111-111111111111",
        USER_A,
    )
    with pytest.raises(HTTPException):
        opli_memory._actor_scope(None)
