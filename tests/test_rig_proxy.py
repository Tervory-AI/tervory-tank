"""Tank proxies Rig reads. No database and no network.

The room key is a test stand-in. Shopper keys are not used.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

ROOT = Path(__file__).resolve().parents[1]
TENANT = "11111111-1111-4111-8111-111111111111"
OTHER = "22222222-2222-4222-8222-222222222222"
ROOM_KEY = "room-test-key"
EXAMPLE = ROOT / "agents" / "rig" / "catalogues" / "example"
SCOPE = "EXAMPLE-SCOPE-01"


def _request(method: str, path: str, query: str = "", body: bytes | None = None) -> Request:
    async def receive():
        return {"type": "http.request", "body": body or b"", "more_body": False}

    headers = [(b"content-type", b"application/json")] if body else []
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query.encode(),
            "headers": headers,
            "client": ("127.0.0.1", 9),
            "server": ("tank", 80),
        },
        receive,
    )


def _json(status: int, payload: object) -> SimpleNamespace:
    return SimpleNamespace(
        status_code=status,
        content=json.dumps(payload).encode(),
        headers={"content-type": "application/json"},
    )


class RigRoom:
    """Stand-in for the Rig room. Records the call and can fail to answer."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.down = False
        self.payload: object = {"ok": True}
        self.status = 200

    async def request(self, method: str, url: str, **kwargs: object) -> SimpleNamespace:
        headers = {str(key).lower(): value for key, value in dict(kwargs.get("headers") or {}).items()}
        self.calls.append((method, url, kwargs.get("params"), kwargs.get("content"), headers, kwargs.get("follow_redirects")))
        if self.down:
            raise httpx.ConnectError("down")
        return _json(self.status, self.payload)


def _install(monkeypatch: pytest.MonkeyPatch, room: RigRoom):
    import main as tank

    monkeypatch.setenv("TANK_KEY_RIG", ROOM_KEY)
    previous = tank._http
    tank._http = room
    return tank, previous


def _restore(tank, previous) -> None:
    tank._http = previous


def test_rig_routes_are_reads_and_use_the_workspace_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import main as tank

    monkeypatch.setenv("TANK_KEY_RIG", ROOM_KEY)
    paths: dict[str, set[str]] = {}
    from http_routes import iter_http_routes

    for route in iter_http_routes(tank.app.routes):
        path = str(getattr(route, "path", ""))
        if not path.startswith("/v1/rig"):
            continue
        paths.setdefault(path, set()).update(getattr(route, "methods", set()))
        names = [getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies]
        assert "require_key" in names

    assert paths["/v1/rig/search"] == {"GET"}
    assert paths["/v1/rig/graph/{product_id}"] == {"GET"}
    assert paths["/v1/rig/products/{product_id}"] == {"GET"}
    assert paths["/v1/rig/catalogues"] == {"GET"}
    assert paths["/v1/rig/compare"] == {"POST"}
    assert paths["/v1/rig/ask"] == {"POST"}
    for closed in ("/v1/rig/setups", "/v1/rig/quote", "/v1/rig/swap", "/v1/rig/link-quote", "/v1/rig/admin/fits"):
        assert closed not in paths
    assert tank.RIG_AGENT_URL == "http://agent-rig:8000"

    async def check() -> None:
        request = _request("GET", "/v1/rig/search", f"tenant_id={TENANT}")
        assert await tank.require_key(request, tank.TANK_API_KEY) is None
        with pytest.raises(HTTPException) as caught:
            await tank.require_key(request, ROOM_KEY)
        assert caught.value.status_code == 403

    asyncio.run(check())


def test_each_route_forwards_with_the_room_key(monkeypatch: pytest.MonkeyPatch) -> None:
    room = RigRoom()
    tank, previous = _install(monkeypatch, room)
    try:
        async def check() -> None:
            query = f"tenant_id={TENANT}&q=scope&limit=12"
            await tank.rig_search(_request("GET", "/v1/rig/search", query))
            await tank.rig_graph(SCOPE, _request("GET", f"/v1/rig/graph/{SCOPE}", f"tenant_id={TENANT}"))
            await tank.rig_product(SCOPE, _request("GET", f"/v1/rig/products/{SCOPE}", f"tenant_id={TENANT}"))
            compare = json.dumps({"product_ids": [SCOPE]}).encode()
            await tank.rig_compare(_request("POST", "/v1/rig/compare", f"tenant_id={TENANT}", compare))
            ask = json.dumps({"product_id": SCOPE, "question": "scope"}).encode()
            await tank.rig_ask(_request("POST", "/v1/rig/ask", f"tenant_id={TENANT}", ask))
            room.payload = {"products": 3, "fits": 3}
            listed = await tank.rig_catalogues(_request("GET", "/v1/rig/catalogues", f"tenant_id={TENANT}"))

            expected = [
                ("GET", "http://agent-rig:8000/v1/rig/search"),
                ("GET", f"http://agent-rig:8000/v1/rig/graph/{SCOPE}"),
                ("GET", f"http://agent-rig:8000/v1/rig/products/{SCOPE}"),
                ("POST", "http://agent-rig:8000/v1/rig/compare"),
                ("POST", "http://agent-rig:8000/v1/rig/ask"),
                ("GET", "http://agent-rig:8000/catalogues"),
            ]
            assert [(method, url) for method, url, *_rest in room.calls] == expected
            for method, url, params, content, headers, redirects in room.calls:
                assert redirects is False
                assert headers["x-tank-key"] == ROOM_KEY
                assert headers["x-tank-key"] != tank.TANK_API_KEY
                assert "x-rig-key" not in headers
                assert ROOM_KEY not in url
                assert dict(params)["tenant_id"] == TENANT
                if method == "POST":
                    forwarded = json.loads(content)
                    assert "tenant_id" not in forwarded
                    assert ROOM_KEY not in content.decode()
            ask_call = room.calls[4]
            assert ask_call[0] == "POST"
            assert json.loads(ask_call[3]) == {"product_id": SCOPE, "question": "scope"}
            assert json.loads(listed.body) == {"products": 3, "fits": 3}
            assert "litellm" not in " ".join(url for _method, url, *_rest in room.calls)

        asyncio.run(check())
    finally:
        _restore(tank, previous)


def test_wrong_tenant_is_refused_before_the_room_is_called(monkeypatch: pytest.MonkeyPatch) -> None:
    room = RigRoom()
    tank, previous = _install(monkeypatch, room)
    try:
        async def check() -> None:
            body = json.dumps({"product_ids": [SCOPE], "tenant_id": OTHER}).encode()
            with pytest.raises(HTTPException) as caught:
                await tank.rig_compare(_request("POST", "/v1/rig/compare", f"tenant_id={TENANT}", body))
            assert caught.value.status_code == 403
            assert caught.value.detail == "tenant mismatch"
            assert room.calls == []

            with pytest.raises(HTTPException) as missing:
                await tank.rig_search(_request("GET", "/v1/rig/search", "q=scope"))
            assert missing.value.status_code == 400
            assert room.calls == []

            room.payload = {"tenant_id": OTHER, "products": 9, "fits": 9}
            with pytest.raises(HTTPException) as foreign:
                await tank.rig_catalogues(_request("GET", "/v1/rig/catalogues", f"tenant_id={TENANT}"))
            assert foreign.value.status_code == 403
            assert OTHER not in str(foreign.value.detail)

        asyncio.run(check())
    finally:
        _restore(tank, previous)


def test_rig_down_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    room = RigRoom()
    room.down = True
    tank, previous = _install(monkeypatch, room)
    try:
        async def check() -> None:
            with pytest.raises(HTTPException) as caught:
                await tank.rig_search(_request("GET", "/v1/rig/search", f"tenant_id={TENANT}&q=scope"))
            assert caught.value.status_code == 502
            assert caught.value.detail == "Rig did not answer."

        asyncio.run(check())
    finally:
        _restore(tank, previous)


def test_catalogue_response_drops_key_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    room = RigRoom()
    room.payload = {"products": 4, "fits": 2, "webhook": "https://hooks.example/private", "keys": ["hidden"]}
    tank, previous = _install(monkeypatch, room)
    try:
        async def check() -> None:
            listed = await tank.rig_catalogues(_request("GET", "/v1/rig/catalogues", f"tenant_id={TENANT}"))
            assert json.loads(listed.body) == {"products": 4, "fits": 2}
            text = listed.body.decode()
            assert "webhook" not in text
            assert "hidden" not in text
            assert "private" not in text

        asyncio.run(check())
    finally:
        _restore(tank, previous)


class _Models:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del messages
        self.calls.append((tenant_id, task_type))
        return json.dumps({"cites": [SCOPE], "fields": ["name"]})


def _load_rig_app():
    sys.path.insert(0, str(ROOT / "agents" / "rig"))
    sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
    path = ROOT / "agents" / "rig" / "app.py"
    spec = importlib.util.spec_from_file_location("rig_proxy_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rig_proxy_app"] = module
    spec.loader.exec_module(module)
    return module


async def _loaded_service():
    from rigbox.service import Service
    from rigbox.store import MemoryStore

    models = _Models()
    service = Service(MemoryStore(), models)
    report = await service.load_folder(EXAMPLE)
    assert report["products"]["added"] == 3
    assert report["fits"]["added"] == 3
    return service, models


def test_room_catalogues_return_counts_and_refuse_a_write(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_rig_app()
    service, models = asyncio.run(_loaded_service())
    module.app.state.rig = service
    monkeypatch.setenv("TANK_KEY", ROOM_KEY)
    transport = httpx.ASGITransport(app=module.app)

    async def check() -> None:
        async with httpx.AsyncClient(transport=transport, base_url="http://rig") as client:
            missing = await client.get("/catalogues", params={"tenant_id": TENANT})
            assert missing.status_code == 401

            listed = await client.get(
                "/catalogues",
                params={"tenant_id": TENANT},
                headers={"X-Tank-Key": ROOM_KEY},
            )
            assert listed.status_code == 200
            assert listed.json() == {"products": 3, "fits": 3}
            assert "rk_" not in listed.text

            empty = await client.get(
                "/catalogues",
                params={"tenant_id": str(uuid.uuid4())},
                headers={"X-Tank-Key": ROOM_KEY},
            )
            assert empty.status_code == 200
            assert empty.json() == {"products": 0, "fits": 0}

            shopper = await client.get("/v1/rig/search", params={"q": "scope", "tenant_id": TENANT})
            assert shopper.status_code == 401

            found = await client.get(
                "/v1/rig/search",
                params={"q": "scope", "tenant_id": TENANT},
                headers={"X-Tank-Key": ROOM_KEY},
            )
            assert found.status_code == 200
            assert SCOPE in found.text
            assert "rk_" not in found.text

            compared = await client.post(
                "/v1/rig/compare",
                params={"tenant_id": TENANT},
                headers={"X-Tank-Key": ROOM_KEY},
                json={"product_ids": [SCOPE]},
            )
            assert compared.status_code == 200
            assert SCOPE in compared.text
            assert "rk_" not in compared.text

            asked = await client.post(
                "/v1/rig/ask",
                params={"tenant_id": TENANT},
                headers={"X-Tank-Key": ROOM_KEY},
                json={"product_id": SCOPE, "question": "scope"},
            )
            assert asked.status_code == 200
            assert models.calls == [(TENANT, "rig.ask")]
            assert "rk_" not in asked.text

            quote = await client.post(
                "/v1/rig/quote",
                headers={"X-Tank-Key": ROOM_KEY},
                json={"product_id": SCOPE},
            )
            assert quote.status_code == 401
            approve = await client.post(
                "/v1/rig/admin/fits/approve",
                headers={"X-Tank-Key": ROOM_KEY},
                json={"part_sku": "EXAMPLE-RINGS-30", "fits_sku": "EXAMPLE-RIFLE-01"},
            )
            assert approve.status_code == 401

    asyncio.run(check())


def test_room_ask_reaches_tank_through_the_route_client() -> None:
    """The production model client posts rig.ask to Tank /v1/route, the ledger path."""
    source = (ROOT / "agents" / "rig" / "app.py").read_text(encoding="utf-8")
    start = source.split("class _TankModels", 1)[1].split("def _public_report", 1)[0]
    assert "self.tank.route" in start
    assert "task_type" in start
    ask = (ROOT / "agents" / "rig" / "rigbox" / "service.py").read_text(encoding="utf-8")
    assert '"rig.ask"' in ask
