"""Entry-point integration: room_auth + session user channel for memory controls."""
from __future__ import annotations

import hmac
import os
from uuid import uuid4

import httpx
import pytest
from base_memory_fixtures import (
    FakeMemory,
    attach_test_bracket,
)
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from gates_memory import (
    build_memory_text,
    resolve_authenticated_user_id,
)
from memory_api import attach_memory_routes

FIXED = {"cost_usd": 0.00056, "tokens_in": 400, "tokens_out": 80}


def _app_with_room_auth(memory: FakeMemory, tank_key: str = "room-fixture-key") -> FastAPI:
    app = FastAPI()
    app.state.memory = memory

    @app.middleware("http")
    async def room_auth(request, call_next):
        if request.url.path != "/health":
            expected = os.environ.get("TANK_KEY", "")
            supplied = request.headers.get("X-Tank-Key", "")
            if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
                return JSONResponse({"detail": "Base room key required"}, status_code=401)
        return await call_next(request)

    attach_memory_routes(app)
    attach_test_bracket(app)
    os.environ["TANK_KEY"] = tank_key
    return app


@pytest.mark.asyncio
async def test_memory_routes_require_room_key_and_session_user():
    memory = FakeMemory()
    app = _app_with_room_auth(memory)
    tenant, user = str(uuid4()), str(uuid4())
    headers = {"X-Tank-Key": "room-fixture-key"}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://base"
    ) as client:
        assert (
            await client.get(
                "/v1/base/memory",
                params={"tenant_id": tenant, "user_id": user, "task_key": "t1"},
            )
        ).status_code == 401
        assert (
            await client.get(
                "/v1/base/memory",
                params={"tenant_id": tenant, "user_id": user, "task_key": "t1"},
                headers={"X-Tank-Key": "wrong"},
            )
        ).status_code == 401
        # Missing user_id → 422 from FastAPI query validation
        assert (
            await client.get(
                "/v1/base/memory",
                params={"tenant_id": tenant, "task_key": "t1"},
                headers=headers,
            )
        ).status_code == 422
        # Tenant-as-user refused
        denied = await client.get(
            "/v1/base/memory",
            params={"tenant_id": tenant, "user_id": tenant, "task_key": "t1"},
            headers=headers,
        )
        assert denied.status_code == 401


@pytest.mark.asyncio
async def test_entry_identical_repeat_fixed_price_and_zero_incremental():
    memory = FakeMemory()
    app = _app_with_room_auth(memory)
    tenant, user = str(uuid4()), str(uuid4())
    headers = {"X-Tank-Key": "room-fixture-key"}
    body = {
        "tenant_id": tenant,
        "user_id": user,
        "task_key": "entry-batch",
        "task": {"name": "Same", "count": 1},
        "memory_control": "edit",
        **FIXED,
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://base"
    ) as client:
        first = await client.post("/__test__/base/memory/bracket", json=body, headers=headers)
        assert first.status_code == 200
        f = first.json()
        assert f["paid_calls"] == f["paid_invocations"] == 1
        assert f["cost_usd"] == pytest.approx(FIXED["cost_usd"])
        assert f["tokens_in"] == FIXED["tokens_in"] and f["tokens_out"] == FIXED["tokens_out"]

        second = await client.post("/__test__/base/memory/bracket", json=body, headers=headers)
        assert second.status_code == 200
        s = second.json()
        assert s["paid_calls"] == s["paid_invocations"] == 0
        assert s["cost_usd"] == 0.0
        assert s["tokens_in"] == s["tokens_out"] == 0
        assert s["answered_from_memory"] is True
        assert "identical_reuse" in [step["action"] for step in s["steps"]]
        assert "brain_route" not in [step["action"] for step in s["steps"]]

        # Changed input misses; fixed per-call price unchanged.
        changed = dict(body)
        changed["task"] = {"name": "Same", "count": 2}
        third = await client.post("/__test__/base/memory/bracket", json=changed, headers=headers)
        assert third.status_code == 200
        t = third.json()
        assert t["paid_calls"] == t["paid_invocations"] == 1
        assert t["cost_usd"] == pytest.approx(FIXED["cost_usd"])
        assert t["tokens_in"] == FIXED["tokens_in"]


@pytest.mark.asyncio
async def test_entry_user_and_tenant_isolation():
    memory = FakeMemory()
    app = _app_with_room_auth(memory)
    tenant_a, tenant_b = str(uuid4()), str(uuid4())
    user_a, user_b = str(uuid4()), str(uuid4())
    headers = {"X-Tank-Key": "room-fixture-key"}
    task = {"name": "Iso", "count": 1}
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://base"
    ) as client:
        seed = await client.post(
            "/__test__/base/memory/bracket",
            json={
                "tenant_id": tenant_a,
                "user_id": user_a,
                "task_key": "iso",
                "task": task,
                "memory_control": "edit",
                **FIXED,
            },
            headers=headers,
        )
        assert seed.json()["paid_calls"] == 1

        other_user = await client.post(
            "/__test__/base/memory/bracket",
            json={
                "tenant_id": tenant_a,
                "user_id": user_b,
                "task_key": "iso",
                "task": task,
                "memory_control": "edit",
                **FIXED,
            },
            headers=headers,
        )
        assert other_user.json()["paid_calls"] == 1
        assert other_user.json()["answered_from_memory"] is False

        other_tenant = await client.post(
            "/__test__/base/memory/bracket",
            json={
                "tenant_id": tenant_b,
                "user_id": user_a,
                "task_key": "iso",
                "task": task,
                "memory_control": "edit",
                **FIXED,
            },
            headers=headers,
        )
        assert other_tenant.json()["paid_calls"] == 1


@pytest.mark.asyncio
async def test_entry_edit_correction_override_and_explicit_forget_and_off():
    memory = FakeMemory()
    app = _app_with_room_auth(memory)
    tenant, user = str(uuid4()), str(uuid4())
    headers = {"X-Tank-Key": "room-fixture-key"}
    task_key = "corr-entry"
    from base_memory_fixtures import signed_test_client
    async with signed_test_client(app, tenant, user) as client:
        # edit: first paid stores receipt
        first = await client.post(
            "/__test__/base/memory/bracket",
            json={
                "tenant_id": tenant,
                "user_id": user,
                "task_key": task_key,
                "task": {"name": "A", "count": 1},
                "memory_control": "edit",
                **FIXED,
            },
            headers=headers,
        )
        assert first.json()["paid_calls"] == 1
        mem_id = memory.rows[0]["id"]

        # Seed a correction that overrides/invalidates stale identical.
        await memory.remember(
            tenant,
            build_memory_text(summary=f"Base task {task_key}", correction="prefer-public-alias"),
            "base.correction",
            f"base:task:{task_key}",
            meta={"user_id": user, "task_key": task_key},
        )
        corrected = await client.post(
            "/__test__/base/memory/bracket",
            json={
                "tenant_id": tenant,
                "user_id": user,
                "task_key": task_key,
                "task": {"name": "A", "count": 1},
                "memory_control": "edit",
                **FIXED,
            },
            headers=headers,
        )
        c = corrected.json()
        assert c["paid_calls"] == c["paid_invocations"] == 0
        assert c["cost_usd"] == 0.0
        assert "apply_correction" in [s["action"] for s in c["steps"]]
        assert "identical_reuse" not in [s["action"] for s in c["steps"]]

        # view lists scoped rows
        viewed = await client.get(
            "/v1/base/memory",
            params={
                "tenant_id": tenant,
                "user_id": user,
                "task_key": task_key,
                "memory_control": "view",
            },
            headers=headers,
        )
        assert viewed.status_code == 200
        assert len(viewed.json()["memories"]) >= 1

        # off: empty view, bracket pays without recall/reuse
        off_view = await client.get(
            "/v1/base/memory",
            params={
                "tenant_id": tenant,
                "user_id": user,
                "task_key": task_key,
                "memory_control": "off",
            },
            headers=headers,
        )
        assert off_view.json()["memories"] == []
        off_bracket = await client.post(
            "/__test__/base/memory/bracket",
            json={
                "tenant_id": tenant,
                "user_id": user,
                "task_key": task_key,
                "task": {"name": "A", "count": 1},
                "memory_control": "off",
                **FIXED,
            },
            headers=headers,
        )
        assert off_bracket.json()["paid_calls"] == 1
        assert off_bracket.json()["cost_usd"] == pytest.approx(FIXED["cost_usd"])

        # explicit forget
        forgotten = await client.post(
            "/v1/base/memory/forget",
            json={
                "tenant_id": tenant,
                "user_id": user,
                "memory_id": mem_id,
                "memory_control": "forget",
            },
            headers=headers,
        )
        assert forgotten.status_code == 200
        assert forgotten.json()["forgotten"] is True
        assert all(row["id"] != mem_id for row in memory.rows)

        # Cross-user forget refused
        other = str(uuid4())
        again = await memory.remember(
            tenant,
            build_memory_text(summary="owner"),
            "base.task",
            "base:task:owner",
            meta={"user_id": user, "task_key": "owner"},
        )
        cross = await client.post(
            "/v1/base/memory/forget",
            json={
                "tenant_id": tenant,
                "user_id": other,
                "memory_id": again["id"],
                "memory_control": "forget",
            },
            headers=headers,
        )
        assert cross.status_code == 403
        assert any(row["id"] == again["id"] for row in memory.rows)


def test_created_by_resolves_as_session_user_on_batch_cfg():
    tenant = str(uuid4())
    user = str(uuid4())
    assert resolve_authenticated_user_id({"created_by": user}, tenant) == user
    assert resolve_authenticated_user_id({"user_id": user}, tenant) == user
    assert resolve_authenticated_user_id({"created_by": tenant}, tenant) is None
    assert resolve_authenticated_user_id({}, tenant) is None


def test_business_hash_ignores_fresh_run_uuids():
    from gates_memory import business_task_payload, task_input_hash

    a = {
        "batch": "Delaware ATF",
        "count": 2,
        "engine": None,
        "preview": False,
        "task_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "run_id": str(uuid4()),
    }
    b = {
        "batch": "Delaware ATF",
        "count": 2,
        "engine": None,
        "preview": False,
        "task_id": str(uuid4()),
        "tenant_id": str(uuid4()),
        "run_id": str(uuid4()),
    }
    assert business_task_payload(a) == {
        "batch": "Delaware ATF",
        "count": 2,
        "engine": None,
        "preview": False,
    }
    assert task_input_hash(a) == task_input_hash(b)
    changed = dict(b)
    changed["count"] = 3
    assert task_input_hash(a) != task_input_hash(changed)


@pytest.mark.asyncio
async def test_product_entry_same_business_different_run_uuids_zero_second_paid():
    """Production-shaped: new task UUIDs each run; business input identical → reuse."""
    memory = FakeMemory()
    app = _app_with_room_auth(memory)
    tenant, user = str(uuid4()), str(uuid4())
    headers = {"X-Tank-Key": "room-fixture-key"}
    business = {"batch": "Delaware ATF", "count": 2, "engine": None, "preview": False}

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://base"
    ) as client:
        first_body = {
            "tenant_id": tenant,
            "user_id": user,
            "task_key": "Delaware ATF",
            "task": {**business, "task_id": str(uuid4()), "tenant_id": tenant},
            "memory_control": "edit",
            **FIXED,
        }
        first = await client.post("/__test__/base/memory/bracket", json=first_body, headers=headers)
        assert first.status_code == 200
        f = first.json()
        assert f["paid_calls"] == f["paid_invocations"] == 1
        assert f["cost_usd"] == pytest.approx(0.00056)
        assert f["tokens_in"] == 400 and f["tokens_out"] == 80

        second_body = {
            "tenant_id": tenant,
            "user_id": user,
            "task_key": "Delaware ATF",
            # Fresh run UUID — must not bust identical reuse.
            "task": {**business, "task_id": str(uuid4()), "tenant_id": tenant},
            "memory_control": "edit",
            **FIXED,
        }
        assert first_body["task"]["task_id"] != second_body["task"]["task_id"]
        second = await client.post("/__test__/base/memory/bracket", json=second_body, headers=headers)
        assert second.status_code == 200
        s = second.json()
        assert s["paid_calls"] == s["paid_invocations"] == 0
        assert s["cost_usd"] == 0.0
        assert s["tokens_in"] == s["tokens_out"] == 0
        assert s["answered_from_memory"] is True
        assert "identical_reuse" in [step["action"] for step in s["steps"]]
        # Meaningful business change still misses.
        miss_body = {
            "tenant_id": tenant,
            "user_id": user,
            "task_key": "Delaware ATF",
            "task": {**business, "count": 3, "task_id": str(uuid4())},
            "memory_control": "edit",
            **FIXED,
        }
        miss = await client.post("/__test__/base/memory/bracket", json=miss_body, headers=headers)
        assert miss.json()["paid_calls"] == 1
        assert miss.json()["cost_usd"] == pytest.approx(0.00056)


@pytest.mark.asyncio
async def test_production_memory_routes_cannot_issue_synthetic_receipts():
    """The shipped router exposes controls only; request costs never become receipts."""
    memory = FakeMemory()
    app = FastAPI()
    app.state.memory = memory
    attach_memory_routes(app)
    assert {route.path for route in app.routes if route.path.startswith("/v1/base/")} == {
        "/v1/base/memory", "/v1/base/memory/forget",
        "/v1/base/memory/edit", "/v1/base/memory/control",
    }
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://base"
    ) as client:
        response = await client.post("/v1/base/memory/bracket", json={
            "tenant_id": str(uuid4()), "user_id": str(uuid4()),
            "task_key": "placeholder-batch", "task": {"count": 1},
            "memory_control": "edit", "cost_usd": 1000000,
            "tokens_in": 1000000, "tokens_out": 1000000,
        })
    assert response.status_code == 404
    assert memory.recalls == memory.remembers == memory.forgets == 0
    assert memory.rows == []
    schema = app.openapi()
    assert "MemoryBracketBody" not in schema["components"]["schemas"]
    assert all("cost_usd" not in model.get("properties", {})
               for model in schema["components"]["schemas"].values())
