"""Production-path gates 7+8: real drive_batch with fresh task UUIDs (not /memory/bracket)."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from base_memory_fixtures import (
    FakeMemory,
    base_brain,
)
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from gates_memory import business_task_payload, task_input_hash
from memory_api import attach_memory_routes

FIXED = {"cost_usd": 0.00056, "tokens_in": 400, "tokens_out": 80}


def _model_receipts():
    return [
        {
            "cost_usd": 0.00014,
            "tokens_in": 100,
            "tokens_out": 20,
            "ledger_id": str(uuid4()),
        }
        for _ in range(4)
    ]


class _Conn:
    def __init__(self, store: dict):
        self.store = store

    async def execute(self, sql, *args):
        # Capture last input JSON when status done / finished.
        if len(args) >= 3 and isinstance(args[2], str):
            try:
                parsed = json.loads(args[2])
                if isinstance(parsed, dict) and "brain_receipt" in parsed:
                    self.store["cfg"] = parsed
            except json.JSONDecodeError:
                parsed = None
        self.store.setdefault("executes", []).append((sql, args))

    async def fetch(self, *a, **k):
        return [{"raw": raw} for raw in self.store["records"]]

    async def fetchrow(self, *a, **k):
        return None


class _Pool:
    def __init__(self, count=2, *, records=None):
        self.store: dict = {"executes": [], "records": records if records is not None else [{"name": "placeholder-business"} for _ in range(count)]}

    def acquire(self):
        pool = self

        class CM:
            async def __aenter__(self_inner):
                return _Conn(pool.store)

            async def __aexit__(self_inner, *exc):
                return False

        return CM()


def _business_cfg(tenant: str, user: str, *, batch="Delaware ATF", count=2, engine=None):
    # created_by mirrors Workspace currentTenant().userId on POST /v1/base/run.
    return {
        "tenant_id": tenant,
        "user_id": user,
        "created_by": user,
        # Internal worker fixture represents the trusted ingress-persisted row.
        "verified_user_id": user,
        "batch": batch,
        "count": count,
        "engine": engine,
        "preview": False,
        "registry": None,
        "memory_control": "edit",
        "model_spend": 0,
    }


@pytest.mark.asyncio
async def test_drive_batch_fresh_task_uuids_identical_business_zero_second_paid(monkeypatch):
    """Actual drive_batch: new task_id each run, same business cfg → second unpaid."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    paid = {"n": 0}
    monkeypatch.setenv("BASE_BRAIN_URL", "http://base-brain.test")
    monkeypatch.setenv("TANK_REGION", "us-east")

    async def fake_invoke(skills, *, tenant_id, task_id, batch, count, engine=None, **_):
        paid["n"] += 1
        return {
            **FIXED,
            "result": {
                "tenant_id": tenant_id,
                "task_id": task_id,
                "room": "base",
                "status": "done",
                "steps": [{"action": "pipeline_run", "status": "done"}],
                "model_receipts": _model_receipts(),
                "summary": "fixture brain done",
                "verified": ["record-1"],
            },
        }

    import brain_route as route_mod

    monkeypatch.setattr(route_mod, "invoke_brain_task", fake_invoke)

    skills = SimpleNamespace(
        memory=memory,
        _base="http://tank.test",
        _http=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(status_code=404))),
        _headers=lambda: {"X-Tank-Key": "room"},
    )
    call = AsyncMock(return_value={})

    # Nested business UUIDs retained; only top-level run keys are out-of-band.
    nested_id = str(uuid4())
    t1 = {
        "batch": "Delaware ATF",
        "count": 2,
        "engine": None,
        "preview": False,
        "registry": [{"id": nested_id, "name": "map"}],
        "task_id": str(uuid4()),
    }
    t2 = {
        "batch": "Delaware ATF",
        "count": 2,
        "engine": None,
        "preview": False,
        "registry": [{"id": nested_id, "name": "map"}],
        "task_id": str(uuid4()),
    }
    assert "id" in business_task_payload(t1).get("registry")[0]
    assert task_input_hash(t1) == task_input_hash(t2)

    task_a, task_b = uuid4(), uuid4()
    assert task_a != task_b

    cfg1 = _business_cfg(tenant, user)
    await base_brain.drive_batch(_Pool(), skills, task_a, cfg1, call)
    assert paid["n"] == 1
    assert cfg1["brain_receipt"]["status"] == "done"
    # Paid path stamps answered_from_memory=False under memory_bracket (not top-level).
    assert cfg1["brain_receipt"]["memory_bracket"]["answered_from_memory"] is False
    assert cfg1["brain_spend"] == pytest.approx(FIXED["cost_usd"])
    assert memory.remembers >= 1

    cfg2 = _business_cfg(tenant, user)
    await base_brain.drive_batch(_Pool(), skills, task_b, cfg2, call)
    assert paid["n"] == 1  # no second paid brain/Tank invocation
    br = cfg2["brain_receipt"]
    assert br["answered_from_memory"] is True
    assert br["cost_usd"] == 0.0
    assert br.get("tokens_in", 0) == 0 and br.get("tokens_out", 0) == 0
    assert br.get("model_receipts") == []
    assert any(s.get("action") == "identical_reuse" for s in (br.get("steps") or []))

    # Meaningful business change (count) misses — new paid call at fixed fake price.
    cfg3 = _business_cfg(tenant, user, count=3)
    await base_brain.drive_batch(_Pool(count=3), skills, uuid4(), cfg3, call)
    assert paid["n"] == 2
    assert cfg3["brain_spend"] == pytest.approx(FIXED["cost_usd"])

    # User isolation: other user pays again for same business shape.
    cfg4 = _business_cfg(tenant, str(uuid4()), count=2)
    await base_brain.drive_batch(_Pool(), skills, uuid4(), cfg4, call)
    assert paid["n"] == 3

    # Tenant isolation
    cfg5 = _business_cfg(str(uuid4()), user, count=2)
    await base_brain.drive_batch(_Pool(), skills, uuid4(), cfg5, call)
    assert paid["n"] == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("control", ["off", None])
async def test_drive_batch_off_skips_memory_and_pays_each_run(monkeypatch, control):
    """memory_control=off takes the historical brain HTTP path (no memory ops)."""
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    posts = {"n": 0}
    monkeypatch.delenv("BASE_MEMORY_CONTROL", raising=False)
    monkeypatch.setenv("BASE_BRAIN_URL", "http://base-brain.test")
    monkeypatch.setenv("TANK_REGION", "us-east")

    class FakeResponse:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self._payload = payload

        def json(self):
            return self._payload

    class FakeHTTP:
        async def post(self, url, headers=None, content=None, **kwargs):
            import json
            payload = json.loads(content)
            posts["n"] += 1
            tid = str(payload["task_id"])
            return FakeResponse(
                200,
                {
                    "tenant_id": str(payload["tenant_id"]),
                    "task_id": tid,
                    "room": "base",
                    "status": "done",
                    "steps": [{"action": "pipeline_run", "status": "done"}],
                    "model_receipts": _model_receipts(),
                    "summary": "off-path brain done",
                },
            )

        async def get(self, *a, **k):
            return FakeResponse(404, {})

        async def delete(self, *a, **k):
            return FakeResponse(200, {})

    class _AsyncCM:
        def __init__(self, http):
            self.http = http

        async def __aenter__(self):
            return self.http

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        __import__("brain_route").httpx, "AsyncClient", lambda timeout=30: _AsyncCM(FakeHTTP())
    )

    # Seed would-be reusable memory — must be ignored when control=off.
    await memory.remember(
        tenant,
        "seed",
        "base.receipt",
        "base:task:Delaware ATF",
        meta={
            "user_id": user,
            "task_key": "Delaware ATF",
            "input_hash": task_input_hash(
                {
                    "batch": "Delaware ATF",
                    "count": 2,
                    "engine": None,
                    "preview": False,
                    "registry": None,
                }
            ),
            "reusable_result": {"verified": ["x"]},
        },
    )
    skills = SimpleNamespace(
        memory=memory,
        _base="http://tank.test",
        _http=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(status_code=404))),
        _headers=lambda: {"X-Tank-Key": "room"},
    )
    call = AsyncMock(return_value={})
    cfg = _business_cfg(tenant, user)
    cfg["memory_control"] = control
    await base_brain.drive_batch(_Pool(), skills, uuid4(), cfg, call)
    cfg2 = _business_cfg(tenant, user)
    cfg2["memory_control"] = control
    await base_brain.drive_batch(_Pool(), skills, uuid4(), cfg2, call)
    assert posts["n"] == 2
    assert cfg["brain_spend"] == pytest.approx(FIXED["cost_usd"])
    assert cfg2["brain_spend"] == pytest.approx(FIXED["cost_usd"])
    # Memory was not consulted for reuse (historical path).
    assert memory.recalls == 0
    assert memory.remembers == 1  # Only the seed above; neither run writes memory.


@pytest.mark.asyncio
async def test_session_user_channel_rejects_forged_header_identity(monkeypatch):
    """Memory routes use body/query user_id (created_by channel), not X-User-Id."""
    import hmac

    memory = FakeMemory()
    app = FastAPI()
    app.state.memory = memory

    @app.middleware("http")
    async def room_auth(request, call_next):
        expected = os.environ.get("TANK_KEY", "")
        supplied = request.headers.get("X-Tank-Key", "")
        if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
            return JSONResponse({"detail": "Base room key required"}, status_code=401)
        return await call_next(request)

    attach_memory_routes(app)
    monkeypatch.setenv("TANK_KEY", "room-fixture-key")
    tenant, real_user, forged = str(uuid4()), str(uuid4()), str(uuid4())
    headers = {
        "X-Tank-Key": "room-fixture-key",
        "X-User-Id": forged,  # must not become the session user
    }
    from base_memory_fixtures import signed_test_client
    async with signed_test_client(app, tenant, real_user) as client:
        r = await client.get(
            "/v1/base/memory",
            params={
                "tenant_id": tenant,
                "user_id": real_user,
                "task_key": "t",
                "memory_control": "view",
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["user_id"] == real_user
        assert r.json()["user_id"] != forged


@pytest.mark.asyncio
@pytest.mark.parametrize("field", ["name", "source", "nested_id", "refs", "engine_data_version"])
async def test_drive_batch_changed_actual_inputs_never_reuse(monkeypatch, field):
    memory = FakeMemory()
    tenant, user = str(uuid4()), str(uuid4())
    invocations = []
    import brain_route

    async def paid(skills, *, tenant_id, task_id, **kwargs):
        invocations.append(task_id)
        return {**FIXED, "result": {"tenant_id": tenant_id, "task_id": task_id,
            "room": "base", "status": "done", "model_receipts": _model_receipts()}}

    monkeypatch.setattr(brain_route, "invoke_brain_task", paid)
    monkeypatch.setenv("TANK_REGION", "us-east")
    records = [{"name": "placeholder-a", "source": {"sha256": "placeholder-source-a"},
                "nested_id": str(uuid4())}, {"name": "placeholder-b"}]
    skills = SimpleNamespace(memory=memory)
    cfg = _business_cfg(tenant, user)
    cfg.update(refs={"base.normalize": "base.normalize@1.0.0"}, engine_data_version="1.0.0")
    await base_brain.drive_batch(_Pool(records=records), skills, uuid4(), dict(cfg), AsyncMock())
    # Canonical JSON ignores object-key and independent-record ordering, not contents.
    reordered = [dict(reversed(list(raw.items()))) for raw in reversed(records)]
    repeat = dict(cfg)
    await base_brain.drive_batch(_Pool(records=reordered), skills, uuid4(), repeat, AsyncMock())
    assert len(invocations) == 1
    assert repeat["brain_receipt"]["answered_from_memory"] is True
    changed = json.loads(json.dumps(records))
    other = json.loads(json.dumps(cfg))
    if field == "refs":
        other["refs"]["base.normalize"] = "base.normalize@2.0.0"
    elif field == "engine_data_version":
        other[field] = "2.0.0"
    elif field == "source":
        changed[0]["source"]["sha256"] = "placeholder-source-b"
    else:
        changed[0][field] = "placeholder-changed"
    await base_brain.drive_batch(_Pool(records=changed), skills, uuid4(), other, AsyncMock())
    assert len(invocations) == 2
    assert other["brain_receipt"]["memory_bracket"]["answered_from_memory"] is False
    assert other["brain_spend"] == pytest.approx(FIXED["cost_usd"])


@pytest.mark.asyncio
async def test_drive_batch_missing_records_refuses_reuse_before_paid(monkeypatch):
    import brain_route
    paid = AsyncMock()
    monkeypatch.setattr(brain_route, "invoke_brain_task", paid)
    cfg = _business_cfg(str(uuid4()), str(uuid4()))
    memory = FakeMemory()
    with pytest.raises(RuntimeError, match="inputs are incomplete"):
        await base_brain.drive_batch(_Pool(records=[]), SimpleNamespace(memory=memory), uuid4(), cfg, AsyncMock())
    paid.assert_not_awaited()
    assert memory.recalls == memory.remembers == 0
