"""Tank proxies Market Lab quarantine for a founder. No database and no network.

The room key is a test stand-in. The workspace key is a different stand-in.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "workspace-key")

import gold  # noqa: E402
import main as tank  # noqa: E402
import training  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TENANT = uuid.UUID("11111111-1111-4111-8111-111111111111")
ROOM_KEY = "room-test-key"
FOUNDER = gold.Reviewer("user_founder", TENANT, True)
OTHER = gold.Reviewer("user_other", TENANT, False)


def _json(status: int, payload: object) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, content=json.dumps(payload).encode())


class Room:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.down = False
        self.status = 200
        self.payload: object = {"batches": []}

    async def request(self, method: str, url: str, **kwargs: object) -> SimpleNamespace:
        headers = {str(key).lower(): value for key, value in dict(kwargs.get("headers") or {}).items()}
        self.calls.append((method, url, headers, kwargs.get("follow_redirects")))
        if self.down:
            raise httpx.ConnectError("down")
        return _json(self.status, self.payload)


class _Pool:
    def acquire(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, *_exc: object) -> None:
        return None


def _install(monkeypatch: pytest.MonkeyPatch, room: Room):
    monkeypatch.setenv("TANK_KEY_MARKET_LAB", ROOM_KEY)
    monkeypatch.setattr(tank, "_http", room)
    monkeypatch.setattr(tank, "pool", lambda: _Pool())
    retired: list[tuple] = []

    async def retire(conn, tenant, batch_id):
        retired.append((tenant, batch_id, conn))
        return ["org/model"]

    monkeypatch.setattr(training, "retire_batch", retire)
    return retired


def test_routes_are_founder_only() -> None:
    paths: dict[str, set[str]] = {}
    for route in tank.app.routes:
        path = str(getattr(route, "path", ""))
        if not path.startswith("/v1/market/quarantine"):
            continue
        paths.setdefault(path, set()).update(getattr(route, "methods", set()))
        names = [getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies]
        assert "require_reviewer" in names
    assert paths["/v1/market/quarantine"] == {"GET"}
    assert paths["/v1/market/quarantine/{batch_id}/{action}"] == {"POST"}
    assert tank.MARKET_AGENT_URL == "http://agent-market-lab:8000"


@pytest.mark.asyncio
async def test_a_missing_room_key_does_not_call_the_room(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    retired = _install(monkeypatch, room)
    monkeypatch.delenv("TANK_KEY_MARKET_LAB", raising=False)
    with pytest.raises(HTTPException) as caught:
        await tank.market_quarantine_list(FOUNDER)
    assert caught.value.status_code == 502
    assert caught.value.detail == "Market Lab did not answer."
    assert room.calls == []
    assert retired == []


@pytest.mark.asyncio
async def test_an_unreachable_room_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    room.down = True
    retired = _install(monkeypatch, room)
    with pytest.raises(HTTPException) as caught:
        await tank.market_quarantine_act("batch-ok", "remove", FOUNDER)
    assert caught.value.status_code == 502
    assert caught.value.detail == "Market Lab did not answer."
    assert retired == []


@pytest.mark.asyncio
async def test_a_non_2xx_room_does_not_retire_the_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    room.status = 500
    room.payload = {"detail": "room failed"}
    retired = _install(monkeypatch, room)
    with pytest.raises(HTTPException) as caught:
        await tank.market_quarantine_act("batch-ok", "remove", FOUNDER)
    assert caught.value.status_code == 502
    assert caught.value.detail == "Market Lab did not answer."
    assert retired == []
    assert room.calls[0][0] == "POST"
    assert room.calls[0][1] == "http://agent-market-lab:8000/quarantine/batch-ok/remove"


@pytest.mark.asyncio
async def test_release_forwards_the_room_key_and_does_not_retire(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    room.payload = {"id": "batch-ok", "status": "pooled"}
    retired = _install(monkeypatch, room)
    body = await tank.market_quarantine_act("batch-ok", "release", FOUNDER)
    assert body["status"] == "pooled"
    assert "models" not in body
    assert retired == []
    assert room.calls[0][2]["x-tank-key"] == ROOM_KEY
    assert room.calls[0][2]["x-tank-key"] != "workspace-key"
    assert room.calls[0][3] is False


@pytest.mark.asyncio
async def test_remove_marks_lineage_only_after_the_room_accepts(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    room.payload = {"id": "batch-ok", "status": "removed"}
    retired = _install(monkeypatch, room)
    body = await tank.market_quarantine_act("batch-ok", "remove", FOUNDER)
    assert body["models"] == ["org/model"]
    assert retired == [(TENANT, "batch-ok", retired[0][2])]
    assert room.calls[0][1].endswith("/quarantine/batch-ok/remove")


@pytest.mark.asyncio
async def test_lineage_failure_after_a_room_accept_is_still_an_error(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    room.payload = {"id": "batch-ok", "status": "removed"}
    _install(monkeypatch, room)

    async def boom(*_args: object):
        raise RuntimeError("lineage")

    monkeypatch.setattr(training, "retire_batch", boom)
    with pytest.raises(HTTPException) as caught:
        await tank.market_quarantine_act("batch-ok", "remove", FOUNDER)
    assert caught.value.status_code == 502
    assert len(room.calls) == 1


@pytest.mark.asyncio
async def test_a_non_founder_is_not_found_and_the_room_is_not_called(monkeypatch: pytest.MonkeyPatch) -> None:
    room = Room()
    retired = _install(monkeypatch, room)
    for call in (
        tank.market_quarantine_list(OTHER),
        tank.market_quarantine_act("batch-ok", "release", OTHER),
        tank.market_quarantine_act("../secret", "remove", FOUNDER),
        tank.market_quarantine_act("batch-ok", "drop", FOUNDER),
    ):
        with pytest.raises(HTTPException) as caught:
            await call
        assert caught.value.status_code == 404
    assert room.calls == []
    assert retired == []


def test_the_workspace_calls_only_tank() -> None:
    folder = ROOT / "workspace" / "app" / "market-lab"
    assert not (folder / "quarantine-store.ts").exists()
    names = ("quarantine.ts", "quarantine-server.ts", "quarantine-actions.ts", "quarantine-view.tsx", "page.tsx")
    text = "\n".join((folder / name).read_text(encoding="utf-8") for name in names)
    for banned in (
        "TANK_KEY_MARKET_LAB",
        "agent-market-lab",
        "node:sqlite",
        "FEEDS_DATABASE_URL",
        "MARKET_LAB_URL",
        "quarantine-store",
        "writeFeedBatch",
        "readFeedBatches",
        "/v1/training/batches",
    ):
        assert banned not in text
    actions = (folder / "quarantine-actions.ts").read_text(encoding="utf-8")
    server = (folder / "quarantine-server.ts").read_text(encoding="utf-8")
    view = (folder / "quarantine-view.tsx").read_text(encoding="utf-8")
    assert 'redirect("/market-lab?quarantine_error=1")' in actions
    assert "/v1/market/quarantine" in actions
    assert "TANK_API_KEY" in actions
    assert "/v1/market/quarantine" in server
    assert "TANK_API_KEY" in server
    assert 'role="alert"' in view
    assert "listFailed" in view
    assert "goldIdentity" not in (folder / "page.tsx").read_text(encoding="utf-8")
