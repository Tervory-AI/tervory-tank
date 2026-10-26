"""TG2: Tank's Tiger proxy never returns or deletes another tenant's watches.

No database and no network. A stand-in HTTP client plays the Tiger room.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

ROOT = Path(__file__).resolve().parents[1]
TENANT_A = "11111111-1111-1111-1111-111111111111"
TENANT_B = "22222222-2222-2222-2222-222222222222"
WATCH_A = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
WATCH_B = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
URL_A = "https://shop-a.example/item"
URL_B = "https://shop-b.example/item"


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
    return SimpleNamespace(status_code=status, content=json.dumps(payload).encode(), headers={"content-type": "application/json"})


def _empty(status: int) -> SimpleNamespace:
    return SimpleNamespace(status_code=status, content=b"", headers={})


def _watch(tenant: str, watch_id: str, url: str) -> dict[str, object]:
    return {
        "id": watch_id,
        "tenant_id": tenant,
        "url": url,
        "label": "shelf",
        "engine": "",
        "every": "1h",
        "enabled": True,
        "threshold": "0.05",
    }


class LeakyTiger:
    """Returns every tenant's rows, and deletes only when the tenant matches."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.watches = {
            WATCH_A: _watch(TENANT_A, WATCH_A, URL_A),
            WATCH_B: _watch(TENANT_B, WATCH_B, URL_B),
        }

    async def request(self, method: str, url: str, **kwargs: object) -> SimpleNamespace:
        headers = {str(key).lower(): value for key, value in dict(kwargs.get("headers") or {}).items()}
        params = dict(kwargs.get("params") or [])
        content = kwargs.get("content")
        self.calls.append((method, url, params, content, headers))
        assert "x-tank-key" not in headers
        assert "test" not in repr(headers)
        if method == "GET" and url.endswith("/watchlist"):
            return _json(200, {"tenant_id": TENANT_B, "watches": list(self.watches.values())})
        if method == "GET" and url.endswith("/observations"):
            return _json(200, {"observations": [
                {"id": "obs-a", "tenant_id": TENANT_A, "url": URL_A, "price": "4.00", "method": "json-ld"},
                {"id": "obs-b", "tenant_id": TENANT_B, "url": URL_B, "price": "9.00", "method": "json-ld"},
            ]})
        if method == "GET" and url.endswith("/alerts"):
            return _json(200, {"alerts": [
                {"id": "alert-a", "tenant_id": TENANT_A, "url": URL_A, "kind": "price"},
                {"id": "alert-b", "tenant_id": TENANT_B, "url": URL_B, "kind": "price"},
            ]})
        if method == "DELETE" and "/watchlist/" in url:
            watch_id = url.rstrip("/").rsplit("/", 1)[-1]
            row = self.watches.get(watch_id)
            if row is None or row["tenant_id"] != params.get("tenant_id"):
                return _json(404, {"detail": "no such watch"})
            del self.watches[watch_id]
            return _empty(204)
        if method == "POST" and url.endswith("/watchlist"):
            body = json.loads(content or b"{}")
            return _json(201, _watch(str(body["tenant_id"]), WATCH_A, str(body["url"])))
        raise AssertionError(f"unexpected {method} {url}")


def test_tiger_routes_use_the_workspace_key(monkeypatch: pytest.MonkeyPatch) -> None:
    import main as tank

    monkeypatch.setenv("TANK_KEY_TIGER", "tiger-secret")
    paths: dict[str, set[str]] = {}
    from http_routes import iter_http_routes

    for route in iter_http_routes(tank.app.routes):
        path = getattr(route, "path", "")
        if not str(path).startswith("/v1/tiger"):
            continue
        paths.setdefault(path, set()).update(route.methods)
        names = [getattr(dep.call, "__name__", "") for dep in route.dependant.dependencies]
        assert "require_key" in names

    assert {"GET", "POST"} <= paths["/v1/tiger/watchlist"]
    assert "DELETE" in paths["/v1/tiger/watchlist/{watch_id}"]
    assert "GET" in paths["/v1/tiger/observations"]
    assert "POST" not in paths["/v1/tiger/observations"]
    assert "GET" in paths["/v1/tiger/alerts"]
    assert tank.TIGER_AGENT_URL == "http://agent-tiger:8000"

    async def check() -> None:
        request = _request("GET", "/v1/tiger/watchlist", f"tenant_id={TENANT_A}")
        assert await tank.require_key(request, tank.TANK_API_KEY) is None
        with pytest.raises(HTTPException) as caught:
            await tank.require_key(request, "tiger-secret")
        assert caught.value.status_code == 403

    asyncio.run(check())


def test_one_tenant_cannot_read_another_tenants_watches() -> None:
    import main as tank

    fake = LeakyTiger()
    previous = tank._http
    tank._http = fake
    try:
        async def check() -> None:
            listed = await tank.tiger_list_watches(_request("GET", "/v1/tiger/watchlist", f"tenant_id={TENANT_A}"))
            body = json.loads(listed.body)
            assert listed.status_code == 200
            assert [row["id"] for row in body["watches"]] == [WATCH_A]
            assert TENANT_B not in listed.body.decode()
            method, url, params, _content, _headers = fake.calls[-1]
            assert method == "GET"
            assert url == "http://agent-tiger:8000/watchlist"
            assert params == {"tenant_id": TENANT_A}

            seen = await tank.tiger_observations(_request("GET", "/v1/tiger/observations", f"tenant_id={TENANT_A}&url={URL_A}"))
            observations = json.loads(seen.body)["observations"]
            assert [row["tenant_id"] for row in observations] == [TENANT_A]

            heard = await tank.tiger_alerts(_request("GET", "/v1/tiger/alerts", f"tenant_id={TENANT_A}"))
            alerts = json.loads(heard.body)["alerts"]
            assert [row["tenant_id"] for row in alerts] == [TENANT_A]

            other = await tank.tiger_list_watches(_request("GET", "/v1/tiger/watchlist", f"tenant_id={TENANT_B}"))
            assert [row["id"] for row in json.loads(other.body)["watches"]] == [WATCH_B]
            assert TENANT_A not in other.body.decode()

        asyncio.run(check())
    finally:
        tank._http = previous


def test_one_tenant_cannot_delete_another_tenants_watch() -> None:
    import main as tank

    fake = LeakyTiger()
    previous = tank._http
    tank._http = fake
    try:
        async def check() -> None:
            denied = await tank.tiger_delete_watch(
                uuid.UUID(WATCH_B),
                _request("DELETE", f"/v1/tiger/watchlist/{WATCH_B}", f"tenant_id={TENANT_A}"),
            )
            assert denied.status_code == 404
            assert WATCH_B in fake.watches
            assert fake.watches[WATCH_B]["tenant_id"] == TENANT_B
            method, url, params, content, _headers = fake.calls[-1]
            assert method == "DELETE"
            assert url == f"http://agent-tiger:8000/watchlist/{WATCH_B}"
            assert params == {"tenant_id": TENANT_A}
            assert content is None

            gone = await tank.tiger_delete_watch(
                uuid.UUID(WATCH_B),
                _request("DELETE", f"/v1/tiger/watchlist/{WATCH_B}", f"tenant_id={TENANT_B}"),
            )
            assert gone.status_code == 204
            assert WATCH_B not in fake.watches
            assert WATCH_A in fake.watches

        asyncio.run(check())
    finally:
        tank._http = previous


def test_a_foreign_watch_in_the_upstream_body_is_not_returned() -> None:
    import main as tank

    class Foreign:
        def __init__(self) -> None:
            self.calls = 0

        async def request(self, method: str, url: str, **kwargs: object) -> SimpleNamespace:
            self.calls += 1
            assert method == "DELETE"
            return _json(200, _watch(TENANT_B, WATCH_B, URL_B))

    fake = Foreign()
    previous = tank._http
    tank._http = fake
    try:
        async def check() -> None:
            response = await tank.tiger_delete_watch(
                uuid.UUID(WATCH_B),
                _request("DELETE", f"/v1/tiger/watchlist/{WATCH_B}", f"tenant_id={TENANT_A}"),
            )
            assert response.status_code == 404
            assert TENANT_B not in response.body.decode()
            assert json.loads(response.body)["detail"] == "no such watch"

        asyncio.run(check())
    finally:
        tank._http = previous


def test_mismatched_tenant_is_refused_before_tiger_is_called() -> None:
    import main as tank

    fake = LeakyTiger()
    previous = tank._http
    tank._http = fake
    try:
        async def check() -> None:
            body = json.dumps({"tenant_id": TENANT_B, "url": URL_B, "every": "1h"}).encode()
            with pytest.raises(HTTPException) as caught:
                await tank.tiger_create_watch(_request("POST", "/v1/tiger/watchlist", f"tenant_id={TENANT_A}", body))
            assert caught.value.status_code == 403
            assert fake.calls == []

            with pytest.raises(HTTPException) as missing:
                await tank.tiger_list_watches(_request("GET", "/v1/tiger/watchlist"))
            assert missing.value.status_code == 400

            tank._http = None
            with pytest.raises(HTTPException) as down:
                await tank.tiger_list_watches(_request("GET", "/v1/tiger/watchlist", f"tenant_id={TENANT_A}"))
            assert down.value.status_code == 503

        asyncio.run(check())
    finally:
        tank._http = previous


def test_create_forwards_only_the_callers_tenant() -> None:
    import main as tank

    fake = LeakyTiger()
    previous = tank._http
    tank._http = fake
    try:
        async def check() -> None:
            body = json.dumps({
                "tenant_id": TENANT_A,
                "url": URL_A,
                "label": "shelf",
                "every": "1h",
                "threshold": 0.05,
            }).encode()
            created = await tank.tiger_create_watch(_request("POST", "/v1/tiger/watchlist", body=body))
            assert created.status_code == 201
            saved = json.loads(created.body)
            assert saved["tenant_id"] == TENANT_A
            _method, url, params, content, _headers = fake.calls[-1]
            assert url == "http://agent-tiger:8000/watchlist"
            assert params == {}
            forwarded = json.loads(content)
            assert forwarded["tenant_id"] == TENANT_A
            assert forwarded["url"] == URL_A
            assert "x-tank-key" not in content.decode()

        asyncio.run(check())
    finally:
        tank._http = previous


def test_prices_page_says_when_a_site_blocks_and_calls_tank() -> None:
    page_dir = ROOT / "workspace" / "app" / "prices"
    source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(page_dir.rglob("*")) if path.suffix in {".ts", ".tsx"})
    assert "This site blocks automated checks" in source
    assert "agent-tiger" not in source
    assert "litellm" not in source.lower()
    assert "TANK_API_KEY" not in source
    assert "fetch(" not in source
    page = (page_dir / "page.tsx").read_text(encoding="utf-8")
    actions = (page_dir / "actions.ts").read_text(encoding="utf-8")
    assert not page.startswith('"use client"')
    assert 'from "@/lib/tank"' in page
    assert 'from "@/lib/tank"' in actions
    client = (ROOT / "workspace" / "lib" / "tank.ts").read_text(encoding="utf-8")
    for path in ("/v1/tiger/watchlist", "/v1/tiger/observations", "/v1/tiger/alerts"):
        assert path in client
    assert "agent-tiger" not in client
