"""Offline Base test providers and bracket harness. Never imported by production."""
from __future__ import annotations

import importlib
import json
import sys
from uuid import uuid4
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from pydantic import Field

ROOT = Path(__file__).resolve().parents[1]
# Match the room image's flat module layout without lint suppressions in callers.
sys.path.insert(0, str(ROOT / "agents/base"))
base_brain = importlib.import_module("base_brain")
gates = importlib.import_module("gates_memory")
api = importlib.import_module("memory_api")
memory_kinds = gates.memory_kinds
_text_has_secret = gates._text_has_secret
usage_from_model_receipts = gates.usage_from_model_receipts
RoomSessionUser = api.RoomSessionUser
room_session_user = api.room_session_user
_memory_client = api._memory_client
normalize_memory_control = gates.normalize_memory_control
product_to_brain_tank_memory = gates.product_to_brain_tank_memory
MemoryScopeError = gates.MemoryScopeError
MemoryControlError = gates.MemoryControlError
task_input_hash = gates.task_input_hash


class FakeMemory:
    """In-process fake for offline gates 7+8 tests. No network."""

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.recalls = 0
        self.remembers = 0
        self.forgets = 0

    async def remember(
        self,
        tenant_id: str,
        text: str,
        kind: str,
        source: str,
        *,
        meta: dict | None = None,
        **_: Any,
    ) -> dict[str, Any]:
        if kind not in memory_kinds():
            raise ValueError("unsupported Base memory kind")
        if _text_has_secret(text):
            raise ValueError("Base memory refuses secret-bearing text")
        row = {
            "id": str(uuid4()),
            "tenant_id": str(tenant_id),
            "text": text,
            "kind": kind,
            "source": source,
            "meta": dict(meta or {}),
        }
        self.rows.append(row)
        self.remembers += 1
        return {"id": row["id"], "seen": self.remembers}

    async def recall(
        self,
        tenant_id: str,
        query: str,
        *,
        kind: str | None = None,
        limit: int | None = None,
        **_: Any,
    ) -> list[dict[str, Any]]:
        self.recalls += 1
        tenant = str(tenant_id)
        matches = [
            row
            for row in self.rows
            if row["tenant_id"] == tenant
            and (kind is None or row["kind"] == kind)
            and (
                not query
                or query.lower() in row["text"].lower()
                or query == (row.get("meta") or {}).get("task_key")
            )
        ]
        if limit is not None:
            matches = matches[:limit]
        return deepcopy(matches)

    async def records(self, tenant_id, *, user_id=None, **kwargs):
        return deepcopy([r for r in self.rows if r["tenant_id"] == str(tenant_id)
                         and (r.get("meta") or {}).get("user_id") == user_id])

    async def forget(self, memory_id: str, tenant_id: str, **_: Any) -> None:
        tenant = str(tenant_id)
        before = len(self.rows)
        self.rows = [
            row
            for row in self.rows
            if not (row["id"] == str(memory_id) and row["tenant_id"] == tenant)
        ]
        if len(self.rows) == before:
            raise RuntimeError("memory not found")
        self.forgets += 1


def _load_pilot_model_receipts() -> list[dict[str, Any]]:
    """Read model_receipts from the real pilot fixture file (fake offline, not billing)."""
    path = ROOT / "agents/base/pilot/receipt.json"
    if not path.is_file():
        # Flat room image may omit pilot/; keep the recorded four-row fixture shape.
        return [
            {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
            {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
            {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
            {"cost_usd": 0.00014, "tokens_in": 100, "tokens_out": 20, "model": "fixture-recorded"},
        ]
    data = json.loads(path.read_text())
    rows = data.get("model_receipts")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("pilot receipt.json missing model_receipts")
    return list(rows)


# Loaded from agents/base/pilot/receipt.json when present — fake offline, not live billing.
PILOT_FIXTURE_MODEL_RECEIPTS = tuple(_load_pilot_model_receipts())


def pilot_fixture_first_usage() -> dict[str, float | int]:
    return usage_from_model_receipts(list(PILOT_FIXTURE_MODEL_RECEIPTS))


def pilot_fixture_repeat_usage_after_correction() -> dict[str, float | int]:
    """Safe repeat after a stored correction: no paid brain/Tank model call."""
    return {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}


def pilot_fixture_identical_repeat_usage() -> dict[str, float | int]:
    """Same unmodified task again (no correction): no paid brain/Tank model call."""
    return {"cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0, "tokens_total": 0}


class MemoryBracketBody(RoomSessionUser):
    task_key: str = Field(min_length=1, max_length=120)
    task: dict[str, Any] = Field(default_factory=dict)
    memory_control: Literal["off", "view", "edit", "forget"] = "edit"
    cost_usd: float = 0.00056
    tokens_in: int = 400
    tokens_out: int = 80


def attach_test_bracket(app: FastAPI) -> None:
    @app.post("/__test__/base/memory/bracket")
    async def memory_bracket(body: MemoryBracketBody) -> dict[str, Any]:
        """Offline fixture boundary; never attached by production code."""
        user = room_session_user(tenant_id=body.tenant_id, user_id=body.user_id)
        control = normalize_memory_control(body.memory_control)
        memory = _memory_client(app)
        task = dict(body.task or {})
        task.setdefault("batch", body.task_key)
        paid_calls = {"n": 0}
        fixed = {
            "cost_usd": float(body.cost_usd),
            "tokens_in": int(body.tokens_in),
            "tokens_out": int(body.tokens_out),
        }

        async def paid_call(_task: dict[str, Any]) -> dict[str, Any]:
            paid_calls["n"] += 1
            return {
                **fixed,
                "result": {
                    "verified": ["entry"],
                    "sources": ["tank-receipts"],
                    "checkpoint": "bracket-entry",
                    "correction": (_task.get("correction") if isinstance(_task, dict) else None),
                },
            }

        try:
            receipt = await product_to_brain_tank_memory(
                memory,
                tenant_id=str(body.tenant_id),
                user_id=user,
                task_key=body.task_key,
                task=task,
                brain_tank_call=paid_call,
                memory_control=control,
            )
        except MemoryScopeError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        except MemoryControlError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {
            "tenant_id": str(body.tenant_id),
            "user_id": user,
            "task_key": body.task_key,
            "input_hash": task_input_hash(task),
            "memory_control": control,
            "paid_calls": receipt["paid_calls"],
            "paid_invocations": paid_calls["n"],
            "cost_usd": receipt["cost_usd"],
            "tokens_in": receipt["tokens_in"],
            "tokens_out": receipt["tokens_out"],
            "answered_from_memory": receipt.get("answered_from_memory"),
            "steps": receipt.get("steps"),
            "result": receipt.get("result"),
        }


def signed_test_client(app, tenant, user, key='room-fixture-key'):
    """Real wire verifier with a disposable in-memory nonce store; SQL proof is central."""
    import httpx
    from types import SimpleNamespace
    from chassis.user_assertion import HEADER, SignedUser, sign_assertion
    pool = SimpleNamespace()
    class Nonces:
        def __init__(self):
            self.pool, self.seen = pool, set()
        async def claim(self, tenant, nonce, expires):
            pair = (tenant, nonce)
            if pair in self.seen:
                return False
            self.seen.add(pair)
            return True
    app.state.pool = pool
    app.state.product_nonce_stores = {'base': Nonces()}
    async def sign(request):
        if request.url.path.startswith('/v1/base/memory'):
            request.headers[HEADER] = sign_assertion('base', SignedUser(tenant, user, 'member'),
                request.method, request.url.raw_path.decode('ascii'), request.content, key=key)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://base',
                             event_hooks={'request': [sign]})
