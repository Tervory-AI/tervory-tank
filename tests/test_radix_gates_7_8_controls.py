"""Gates 7+8 live product-surface controls: VIEW/EDIT/FORGET/OFF with auth.

Eight real-handler denial tests = four controls × (other user same tenant + other tenant).
Full store/settings/receipts before-after identical for all denials. Includes valid owner
and missing/forged identity cases. Routes are the signed-in product surface.
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "radix"))

from radix_memory_fakes import FakeMemory
from radix_memory import (
    MemoryScopeError,
    build_memory_text,
    require_authenticated_scope,
)
from radix_memory_api import attach_memory_routes
from radix_gates78_identity import SignedUnitActor, UnitNonces, install_verifier

TENANT = "11111111-1111-4111-8111-111111111111"
OTHER_TENANT = "22222222-2222-4222-8222-222222222222"
OWNER = "member-user-1"
OTHER_USER = "other-member"
RADIX_AGENT_KEY = "placeholder-radix-agent-key-controls"
WORKSPACE_KEY = "placeholder-workspace-key-controls"


def _app(memory: FakeMemory) -> FastAPI:
    app = FastAPI()
    app.state.memory = memory
    app.state.pool = object()
    app.state.product_nonce_stores = {"radix": UnitNonces(app.state.pool)}
    attach_memory_routes(app)
    return app


def _headers(tenant: str = TENANT, user: str = OWNER, *, key: str | None = None) -> dict[str, str]:
    """Tank EXISTING signed request headers: product agent key + verified Actor."""
    return {
        "x-tank-key": RADIX_AGENT_KEY if key is None else key,
        "x-tervory-tenant": tenant,
        "x-tervory-user": user,
    }


def _store_snapshot(memory: FakeMemory) -> list[dict]:
    return copy.deepcopy(memory.rows)


@pytest.fixture(autouse=True)
def _radix_agent_key_env(monkeypatch, tmp_path):
    install_verifier(monkeypatch, tmp_path)
    monkeypatch.setenv("TANK_KEY_RADIX", RADIX_AGENT_KEY)
    monkeypatch.setenv("TANK_KEY", RADIX_AGENT_KEY)
    monkeypatch.setenv("TANK_API_KEY", WORKSPACE_KEY)


@pytest.mark.asyncio
async def test_owner_view_edit_forget_and_off():
    memory = FakeMemory()
    app = _app(memory)
    seeded = await memory.remember(
        TENANT,
        build_memory_text(
            summary="Radix owner seed", outcome="keep", sites_scanned=["a.test"],
            findings=["f1"], fixes=["fix1"], accepted_risks=["none"],
            false_positives=["none"], receipt="cost=0.05;tokens_in=10;tokens_out=3",
        ),
        "radix.receipt", "radix:task:owned",
        meta={"user_id": OWNER, "task_key": "owned", "input_hash": "abc",
              "reusable_result": {"outcome": "keep"}, "invalidated": False},
    )
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=SignedUnitActor()) as client:
        control = await client.post("/v1/radix/memory/control", headers=_headers(), json={"control": "edit"})
        assert control.status_code == 200 and control.json()["memory_control"] == "edit"

        viewed = await client.get(
            f"/v1/radix/memory?task_key=owned&memory_id={seeded['id']}", headers=_headers(),
        )
        assert viewed.status_code == 200
        assert any(row["id"] == seeded["id"] for row in viewed.json()["memories"])

        edited = await client.post(
            "/v1/radix/memory/edit", headers=_headers(),
            json={"memory_id": seeded["id"],
                  "text": build_memory_text(
                      summary="Radix owner edited", outcome="changed",
                      sites_scanned=["a.test"], findings=["f1"], fixes=["fix2"],
                      accepted_risks=["none"], false_positives=["none"], receipt="cost=0"),
                  "memory_control": "edit"},
        )
        assert edited.status_code == 200, edited.text

        await client.post("/v1/radix/memory/control", headers=_headers(), json={"control": "forget"})
        forgotten = await client.post(
            "/v1/radix/memory/forget", headers=_headers(),
            json={"memory_id": seeded["id"], "memory_control": "forget"},
        )
        assert forgotten.status_code == 200, forgotten.text

        off = await client.post("/v1/radix/memory/control", headers=_headers(), json={"control": "off"})
        assert off.status_code == 200
        # Seed a fresh row then confirm view under off returns empty
        await memory.remember(
            TENANT, build_memory_text(
                summary="after-off", outcome="x", sites_scanned=["b"], findings=["f"],
                fixes=["z"], accepted_risks=["none"], false_positives=["none"], receipt="cost=0"),
            "radix.task", "radix:task:after",
            meta={"user_id": OWNER, "task_key": "after"},
        )
        viewed_off = await client.get("/v1/radix/memory?task_key=after", headers=_headers())
        assert viewed_off.status_code == 200
        assert viewed_off.json()["memory_control"] == "off"
        assert viewed_off.json()["memories"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "control,denial",
    [
        ("view", "other_user"),
        ("view", "other_tenant"),
        ("edit", "other_user"),
        ("edit", "other_tenant"),
        ("forget", "other_user"),
        ("forget", "other_tenant"),
        ("off", "other_user"),
        ("off", "other_tenant"),
    ],
)
async def test_live_memory_control_refuses_foreign_tenant_or_user(control, denial):
    memory = FakeMemory()
    app = _app(memory)
    seeded = await memory.remember(
        TENANT,
        build_memory_text(
            summary="Radix owner seed", outcome="keep", sites_scanned=["a.test"],
            findings=["f1"], fixes=["fix1"], accepted_risks=["none"],
            false_positives=["none"], receipt="cost=0.05;tokens_in=10;tokens_out=3",
        ),
        "radix.receipt", "radix:task:owned",
        meta={"user_id": OWNER, "task_key": "owned", "input_hash": "abc",
              "reusable_result": {"outcome": "keep"}, "invalidated": False},
    )
    await memory.remember(
        TENANT,
        build_memory_text(
            summary=f"Radix memory_control for user {OWNER}", outcome="control:edit",
            sites_scanned=["memory-control"], findings=["control-set"], fixes=["set-control-edit"],
            accepted_risks=["none"], false_positives=["none"], receipt="control=edit",
        ),
        "radix.memory_control", "radix:memory_control",
        meta={"user_id": OWNER, "control": "edit", "task_key": "memory_control"},
    )
    before = _store_snapshot(memory)

    if denial == "other_user":
        headers = _headers(user=OTHER_USER)
    else:
        headers = _headers(tenant=OTHER_TENANT, user=OWNER)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=SignedUnitActor()) as client:
        if control == "view":
            resp = await client.get(
                f"/v1/radix/memory?task_key=owned&memory_id={seeded['id']}", headers=headers,
            )
        elif control == "edit":
            resp = await client.post(
                "/v1/radix/memory/edit", headers=headers,
                json={"memory_id": seeded["id"],
                      "text": build_memory_text(
                          summary="hacked", outcome="changed", sites_scanned=["a"],
                          findings=["f"], fixes=["z"], accepted_risks=["none"],
                          false_positives=["none"], receipt="cost=0"),
                      "memory_control": "edit"},
            )
        elif control == "forget":
            resp = await client.post(
                "/v1/radix/memory/forget", headers=headers,
                json={"memory_id": seeded["id"], "memory_control": "forget"},
            )
        else:
            resp = await client.post(
                "/v1/radix/memory/control", headers=headers,
                json={"control": "off", "memory_id": seeded["id"]},
            )

    assert resp.status_code == 403, (control, denial, resp.status_code, resp.text)
    after = _store_snapshot(memory)
    assert after == before, f"store changed on {control}/{denial} denial"
    owner_controls = [
        r for r in after
        if r.get("kind") == "radix.memory_control"
        and (r.get("meta") or {}).get("user_id") == OWNER
        and r.get("tenant_id") == TENANT
    ]
    assert owner_controls and owner_controls[-1]["meta"]["control"] == "edit"
    owned = next(r for r in after if r["id"] == seeded["id"])
    assert "outcome=keep" in owned["text"]
    assert owned["meta"].get("reusable_result", {}).get("outcome") == "keep"


@pytest.mark.asyncio
async def test_missing_and_forged_identity_fail_closed():
    memory = FakeMemory()
    app = _app(memory)
    seeded = await memory.remember(
        TENANT,
        build_memory_text(
            summary="seed", outcome="keep", sites_scanned=["a"], findings=["f"],
            fixes=["z"], accepted_risks=["none"], false_positives=["none"], receipt="cost=0",
        ),
        "radix.task", "radix:task:x",
        meta={"user_id": OWNER, "task_key": "x"},
    )
    before = _store_snapshot(memory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=SignedUnitActor()) as client:
        missing = await client.get(f"/v1/radix/memory?memory_id={seeded['id']}")
        assert missing.status_code == 401
        forged = await client.get(
            f"/v1/radix/memory?memory_id={seeded['id']}&user_id={OTHER_USER}",
            headers=_headers(),
        )
        assert forged.status_code == 403
        forged_body = await client.post(
            "/v1/radix/memory/edit",
            headers=_headers(),
            json={"memory_id": seeded["id"], "text": "x", "user_id": OTHER_USER},
        )
        # extra field forbidden by model → 422; either way nothing changes
        assert forged_body.status_code in {403, 422}
    assert _store_snapshot(memory) == before
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id=TENANT, user_id="")
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id="", user_id=OWNER)
    with pytest.raises(MemoryScopeError):
        require_authenticated_scope(tenant_id=TENANT, user_id=TENANT)


@pytest.mark.asyncio
async def test_shared_workspace_key_refused_and_missing_key():
    """Point 7: identity cannot trust tenant/user headers + shared service key."""
    memory = FakeMemory()
    app = _app(memory)
    before = _store_snapshot(memory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", auth=SignedUnitActor()) as client:
        shared = await client.get(
            "/v1/radix/memory",
            headers=_headers(key=WORKSPACE_KEY),
        )
        assert shared.status_code == 403
        missing = await client.get(
            "/v1/radix/memory",
            headers={"x-tervory-tenant": TENANT, "x-tervory-user": OWNER},
        )
        assert missing.status_code == 401
        wrong = await client.get(
            "/v1/radix/memory",
            headers=_headers(key="placeholder-wrong-key"),
        )
        assert wrong.status_code == 401
    assert _store_snapshot(memory) == before


@pytest.mark.asyncio
async def test_agent_key_and_user_headers_without_assertion_cannot_claim_an_owner():
    memory = FakeMemory()
    app = _app(memory)
    before = _store_snapshot(memory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://placeholder") as client:
        for path in ("/v1/radix/memory", "/v1/radix/memory?user_id=" + OWNER):
            assert (await client.get(path, headers=_headers())).status_code == 401
        response = await client.post("/v1/radix/memory/control", headers=_headers(), json={"control": "edit"})
        assert response.status_code == 401
    assert _store_snapshot(memory) == before


@pytest.mark.asyncio
async def test_product_assertion_binds_body_and_rejects_a_replayed_control():
    memory = FakeMemory()
    app = _app(memory)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://placeholder", auth=SignedUnitActor()) as client:
        first = await client.post("/v1/radix/memory/control", headers=_headers(), json={"control": "edit"})
        assert first.status_code == 200
        before = _store_snapshot(memory)
        replay = await client.send(first.request)
        assert replay.status_code == 401
        assert _store_snapshot(memory) == before
        tampered = await client.post("/v1/radix/memory/control", headers=dict(first.request.headers), json={"control": "off"})
        assert tampered.status_code == 401
        assert _store_snapshot(memory) == before
