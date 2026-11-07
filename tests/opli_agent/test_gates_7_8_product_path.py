"""Product-path gates 7+8: live /v1/command/opli/* → Tank code_turn; Hermes edge only faked."""
from __future__ import annotations

import json
import sys
import types
import uuid
from pathlib import Path
from unittest.mock import AsyncMock

import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "opli"))
sys.path.insert(0, str(ROOT / "integrations" / "tank"))

from chassis.memory import MemoryClient
from fixed_fake import FIXED_FAKE_PER_CALL

from opli_agent.test_tank_contract import proposed as proposed_fixture, runtime as runtime_fixture, TENANT
proposed = proposed_fixture
runtime = runtime_fixture
import test_command
import opli_memory


class HermesEdge:
    """Network-edge fake for chassis MemoryClient._send (Hermes HTTP only)."""

    def __init__(self) -> None:
        self.rows: list[dict] = []

    async def request(self, method, url, json=None, headers=None):
        from urllib.parse import parse_qs, urlparse

        path = url.split("http://hermes:8000", 1)[-1]
        if (method == "POST" and path.endswith("/memories")) or (method == "PATCH" and "/memories/" in path):
            body = dict(json or {})
            row_id = body.get("id") or str(uuid.uuid4())
            for row in self.rows:
                if row["id"] == row_id and row["tenant_id"] == str(body["tenant_id"]):
                    assert method == "PATCH"
                    assert row["meta"]["user_id"] == body["user_id"]
                    row.update({
                        "text": body["text"],
                        "kind": body["kind"],
                        "source": body["source"],
                        "meta": body.get("meta") or {},
                    })
                    return FakeResp({"id": row_id})
            assert method == "POST"
            row = {
                "id": row_id,
                "tenant_id": str(body["tenant_id"]),
                "text": body["text"],
                "kind": body["kind"],
                "source": body["source"],
                "meta": body.get("meta") or {},
            }
            self.rows.append(row)
            return FakeResp({"id": row_id})
        if method == "POST" and path.endswith("/recall"):
            body = dict(json or {})
            tenant = str(body["tenant_id"])
            query = str(body.get("query") or "")
            kind = body.get("kind")
            matches = [
                row for row in self.rows
                if row["tenant_id"] == tenant
                and (kind is None or row["kind"] == kind)
                and (
                    not query
                    or query.lower() in row["text"].lower()
                    or query == (row.get("meta") or {}).get("task_key")
                    or query == (row.get("meta") or {}).get("control")
                )
            ]
            limit = body.get("limit")
            if limit is not None:
                matches = matches[: int(limit)]
            return FakeResp({"memories": matches})
        if method == "GET" and path.startswith("/records"):
            qs = parse_qs(urlparse("http://x" + path).query)
            tenant = (qs.get("tenant_id") or [None])[0]
            rows = [r for r in self.rows if tenant is None or r["tenant_id"] == tenant]
            return FakeResp({"memories": rows})
        if method == "DELETE" and "/memories/" in path:
            mem_id = path.split("/memories/")[1].split("?")[0]
            self.rows = [r for r in self.rows if r["id"] != mem_id]
            return FakeResp({}, empty=True)
        raise AssertionError(f"unexpected hermes call {method} {path}")


class FakeResp:
    def __init__(self, payload, status_code=200, empty=False):
        self.status_code = status_code
        self._payload = payload
        self.content = b"" if empty else json.dumps(payload).encode()

    def json(self):
        return self._payload


@pytest_asyncio.fixture
async def product_api(proposed, runtime, monkeypatch):
    """Live Tank command app with opli_memory.install + MemoryClient (Hermes faked)."""
    generator = test_command.command_pool.__wrapped__()
    pool = await anext(generator)
    try:
        from opli_agent.proposal import proposed_files
        files = proposed_files()
        if "tank/schema.sql" in files:
            schema = files["tank/schema.sql"].split("-- BEGIN opli\n")[1].split("-- END opli")[0]
            await pool.execute(schema)
            await pool.execute(schema)
        runtime.pool = lambda: pool
        monkeypatch.setattr(proposed, "db", lambda: pool)

        edge = HermesEdge()
        # Chassis MemoryClient; only Hermes HTTP is faked at the edge.
        memory = MemoryClient(
            base_url="http://hermes:8000",
            api_key="opli-placeholder-agent-key",
            agent="opli",
            http=edge,
        )
        app = FastAPI()
        app.include_router(proposed.router)
        app.state.memory = memory
        proposed.app = app
        # Clear wrap flag if a prior test left it (module-level on proposed)
        if getattr(proposed, "_opli_memory_code_turn_wrapped", False):
            proposed.code_turn = proposed._opli_original_code_turn
            proposed._opli_memory_code_turn_wrapped = False
        opli_memory.install(proposed)

        headers = {
            "x-tank-key": runtime.TANK_API_KEY,
            "x-tervory-tenant": str(TENANT),
            "x-tervory-user": "member-user-1",
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://fixture",
            headers=headers,
        ) as client:
            yield client, pool, proposed, edge, memory
    finally:
        await generator.aclose()


async def _fixed_route_code(proposed, pool, monkeypatch):
    """Fake only the model/network edge (route_code); code_turn itself stays real."""
    ledger = uuid.uuid4()
    fixed = FIXED_FAKE_PER_CALL
    await pool.execute(
        "INSERT INTO tank.ledger(id,tenant_id,agent,task_type,model,cost_usd,tokens_in,tokens_out) "
        "VALUES($1,$2,'orchestrator','command.code','placeholder-allowed',$3,$4,$5)",
        ledger, TENANT, fixed["cost_usd"], fixed["tokens_in"], fixed["tokens_out"],
    )
    content = {"answer": "repo map ready", "requests": []}
    stub = AsyncMock(return_value=types.SimpleNamespace(ledger_id=ledger, content=json.dumps(content)))
    monkeypatch.setattr(proposed, "route_code", stub)
    return stub


@pytest.mark.asyncio
async def test_live_opli_code_turn_uses_tank_agent_then_memory_repeat(product_api, monkeypatch):
    client, pool, proposed, edge, memory = product_api
    assert memory is not None

    thread = (await client.post("/v1/command/threads", json={})).json()["thread_id"]
    stub = await _fixed_route_code(proposed, pool, monkeypatch)
    body = {
        "thread_id": thread,
        "text": "Summarize the repo map",
        "model": "placeholder-allowed",
        "repo": "acme/app",
    }
    first = await client.post("/v1/command/opli/code-turn", json=body)
    assert first.status_code == 200, first.text
    payload = first.json()
    bracket = payload["memory_bracket"]
    assert bracket["paid_calls"] == 1
    assert bracket["cost_usd"] == pytest.approx(FIXED_FAKE_PER_CALL["cost_usd"])
    assert bracket["tokens_in"] == FIXED_FAKE_PER_CALL["tokens_in"]
    assert bracket["tokens_out"] == FIXED_FAKE_PER_CALL["tokens_out"]
    assert stub.await_count == 1
    assert any(s["action"] == "remember" for s in bracket["steps"])
    assert any(s["action"] == "tank_route" for s in bracket["steps"])
    assert any(s["action"] == "recall" for s in bracket["steps"])

    # Exact repeat: memory short-circuit, Tank agent not called again.
    second = await client.post("/v1/command/opli/code-turn", json=body)
    assert second.status_code == 200, second.text
    bracket2 = second.json()["memory_bracket"]
    assert bracket2["paid_calls"] == 0
    assert bracket2["cost_usd"] == 0.0
    assert bracket2["tokens_in"] == 0 and bracket2["tokens_out"] == 0
    assert bracket2["answered_from_memory"] is True
    assert stub.await_count == 1
    assert any(s["action"] == "identical_reuse" for s in bracket2["steps"])


@pytest.mark.asyncio
async def test_live_endpoint_refuses_empty_tenant_or_user(product_api):
    client, pool, proposed, edge, memory = product_api
    # Missing authenticated user header → Tank identity fails closed (401)
    missing_user = await client.post(
        "/v1/command/opli/code-turn",
        headers={"x-tervory-user": ""},
        json={
            "thread_id": str(uuid.uuid4()),
            "text": "hello",
            "model": "placeholder-allowed",
        },
    )
    assert missing_user.status_code in {401, 422}
    # Re-import after install so class identity matches any product reload.
    from agents.opli.gates_memory import MemoryScopeError as ScopeErr, require_authenticated_scope as require_scope
    with pytest.raises(ScopeErr):
        require_scope(tenant_id=str(TENANT), user_id="")
    with pytest.raises(ScopeErr):
        require_scope(tenant_id="", user_id="member")
    with pytest.raises(ScopeErr):
        require_scope(tenant_id=str(TENANT), user_id=str(TENANT))


@pytest.mark.asyncio
async def test_live_memory_view_edit_forget_control_via_memory_client(product_api):
    client, pool, proposed, edge, memory = product_api
    assert memory is not None
    user = "member-user-1"
    control = await client.post(
        "/v1/command/opli/memory.control",
        json={"control": "edit"},
    )
    assert control.status_code == 200, control.text
    assert control.json()["memory_control"] == "edit"

    saved = await memory.remember(
        str(TENANT),
        "Opli live seed; outcome=seed; repo=acme/app; receipt=cost=0",
        "opli.task",
        "opli:task:live",
        user_id=user, meta={"user_id": user, "task_key": "live"},
    )
    viewed = await client.get(
        "/v1/command/opli/memory.view?task_key=live&memory_control=view"
    )
    assert viewed.status_code == 200, viewed.text
    assert any(row["id"] == saved["id"] for row in viewed.json()["memories"])

    edited = await client.post(
        "/v1/command/opli/memory.edit",
        json={
            "memory_id": saved["id"],
            "text": "Opli live edited; outcome=changed; repo=acme/app; receipt=cost=0",
            "memory_control": "edit",
        },
    )
    assert edited.status_code == 200, edited.text

    await client.post("/v1/command/opli/memory.control", json={"control": "forget"})
    forgotten = await client.post(
        "/v1/command/opli/memory.forget",
        json={"memory_id": saved["id"], "memory_control": "forget"},
    )
    assert forgotten.status_code == 200, forgotten.text

    off = await client.post("/v1/command/opli/memory.control", json={"control": "off"})
    assert off.status_code == 200
    viewed_off = await client.get(
        "/v1/command/opli/memory.view?task_key=live&memory_control=view"
    )
    assert viewed_off.status_code == 200
    # control=off is stored; view_memories returns empty when control resolves to off
    assert viewed_off.json()["memory_control"] == "off"
    assert viewed_off.json()["memories"] == []


def _store_snapshot(edge: HermesEdge) -> list[dict]:
    """Full durable memory store snapshot (rows + control meta + receipt text)."""
    import copy
    return copy.deepcopy(edge.rows)


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
async def test_live_memory_control_refuses_foreign_tenant_or_user(
    product_api, control, denial,
):
    """Each control refuses when target record tenant+user ≠ signed-in actor.

    Identity comes from the authenticated actor chain only. Snapshot of the full
    store, control settings, and receipt texts must be unchanged after denial.
    """
    from opli_agent.test_tank_contract import OTHER

    client, pool, proposed, edge, memory = product_api
    owner = "member-user-1"
    # Seed owner-scoped task memory + control=edit + a receipt-shaped row
    seeded = await memory.remember(
        str(TENANT),
        "Opli owner seed; outcome=keep; repo=acme/app; receipt=cost=0.05;tokens_in=10;tokens_out=3",
        "opli.receipt",
        "opli:task:owned",
        user_id=owner, meta={
            "user_id": owner,
            "task_key": "owned",
            "input_hash": "abc",
            "reusable_result": {"outcome": "keep", "repo": "acme/app"},
            "invalidated": False,
        },
    )
    await memory.remember(
        str(TENANT),
        "Opli memory_control for user member-user-1; outcome=control:edit; receipt=control=edit",
        "opli.memory_control",
        "opli:memory_control",
        user_id=owner, meta={"user_id": owner, "control": "edit", "task_key": "memory_control"},
    )
    before = _store_snapshot(edge)
    assert any(r["id"] == seeded["id"] for r in before)

    if denial == "other_user":
        headers = {"x-tervory-user": "other-member"}
    else:
        headers = {"x-tervory-tenant": str(OTHER), "x-tervory-user": "member-user-1"}

    if control == "view":
        resp = await client.get(
            f"/v1/command/opli/memory.view?task_key=owned&memory_id={seeded['id']}",
            headers=headers,
        )
    elif control == "edit":
        resp = await client.post(
            "/v1/command/opli/memory.edit",
            headers=headers,
            json={
                "memory_id": seeded["id"],
                "text": "Opli hacked; outcome=changed; repo=acme/app; receipt=cost=0",
                "memory_control": "edit",
            },
        )
    elif control == "forget":
        resp = await client.post(
            "/v1/command/opli/memory.forget",
            headers=headers,
            json={"memory_id": seeded["id"], "memory_control": "forget"},
        )
    else:  # switch-off
        resp = await client.post(
            "/v1/command/opli/memory.control",
            headers=headers,
            json={"control": "off", "memory_id": seeded["id"]},
        )

    assert resp.status_code == 403, (control, denial, resp.status_code, resp.text)
    after = _store_snapshot(edge)
    assert after == before, f"store changed on {control}/{denial} denial"
    # Control settings for owner unchanged
    owner_controls = [
        r for r in after
        if r.get("kind") == "opli.memory_control"
        and (r.get("meta") or {}).get("user_id") == owner
        and r.get("tenant_id") == str(TENANT)
    ]
    assert owner_controls and owner_controls[-1]["meta"]["control"] == "edit"
    # Receipt text unchanged
    owned = next(r for r in after if r["id"] == seeded["id"])
    assert "outcome=keep" in owned["text"]
    assert owned["meta"].get("reusable_result", {}).get("outcome") == "keep"


@pytest.fixture(autouse=True)
def enabled_memory_layer(monkeypatch):
    monkeypatch.setenv("OPLI_MEMORY_ENABLED", "true")
