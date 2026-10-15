"""TANK_HOMES_KEY: the ZA Tank lets it set a za tenant's home and nothing else.

Network mocked: the Zenas room is a fake. No database.
"""
from __future__ import annotations

import asyncio
import json
import os

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import main

HOMES = "homes-key-for-tests-only"
TENANT = "11111111-1111-1111-1111-111111111111"


def _request(method: str, path: str, body: bytes = b"", query: bytes = b"") -> Request:
    sent = {"done": False}

    async def receive() -> dict:
        if sent["done"]:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": method, "scheme": "http", "path": path, "raw_path": path.encode(),
        "query_string": query, "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1), "server": ("test", 80),
    }
    return Request(scope, receive)


class _Room:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def request(self, method: str, url: str, **kwargs: object) -> object:
        self.calls.append(f"{method} {url}")

        class _Response:
            content = json.dumps({"ok": True, "created": True}).encode()
            status_code = 200
            headers = {"content-type": "application/json"}

        return _Response()


@pytest.fixture
def za(monkeypatch: pytest.MonkeyPatch) -> _Room:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.setenv("TANK_HOMES_KEY", HOMES)
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://agent-zenas:8000")
    monkeypatch.setattr(main, "_pool", None)
    room = _Room()
    monkeypatch.setattr(main, "_http", room)
    return room


def _tenant_body(home: str = "za", **extra: str) -> bytes:
    return json.dumps({"tenant_id": TENANT, "home_region": home, **extra}).encode()


def _auth(method: str, path: str, body: bytes = b"", query: bytes = b""):
    return asyncio.run(main.require_key(_request(method, path, body, query), x_tank_key=HOMES))


def test_homes_key_sets_a_za_home_through_the_proxy(za: _Room) -> None:
    body = _tenant_body()
    assert _auth("POST", "/v1/zenas/tenants", body, b"home_region=za") == main.HOMES_PRINCIPAL
    resp = asyncio.run(main.zenas_proxy("tenants", _request("POST", "/v1/zenas/tenants", body, b"home_region=za")))
    assert resp.status_code == 200
    assert za.calls == ["POST http://agent-zenas:8000/tenants"]


@pytest.mark.parametrize(
    ("method", "path", "body", "query"),
    [
        ("GET", "/v1/zenas/tenants", b"", b""),
        ("POST", "/v1/zenas/matters", _tenant_body(), b""),
        ("GET", "/v1/zenas/pool/status", b"", b"home_region=za"),
        ("POST", "/v1/route", b"{}", b""),
        ("GET", "/health", b"", b""),
        ("POST", "/v1/zenas/tenants", _tenant_body("us-east"), b""),
        ("POST", "/v1/zenas/tenants", _tenant_body(), b"home_region=us-east"),
        ("POST", "/v1/zenas/tenants", b"not json", b""),
        ("POST", "/v1/zenas/tenants", _tenant_body(name="Jane"), b""),
    ],
)
def test_homes_key_is_refused_everywhere_else(za: _Room, method: str, path: str, body: bytes, query: bytes) -> None:
    with pytest.raises(HTTPException) as caught:
        _auth(method, path, body, query)
    assert caught.value.status_code == 403
    assert za.calls == []


def test_homes_key_does_nothing_on_a_us_tank(monkeypatch: pytest.MonkeyPatch, za: _Room) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    with pytest.raises(HTTPException) as caught:
        _auth("POST", "/v1/zenas/tenants", _tenant_body())
    assert caught.value.status_code == 403


def test_unset_homes_key_matches_nothing(monkeypatch: pytest.MonkeyPatch, za: _Room) -> None:
    monkeypatch.setenv("TANK_HOMES_KEY", "")
    with pytest.raises(HTTPException) as caught:
        asyncio.run(main.require_key(_request("POST", "/v1/zenas/tenants", _tenant_body()), x_tank_key=""))
    assert caught.value.status_code == 401


def test_homes_key_is_not_an_agent_key() -> None:
    assert not "TANK_HOMES_KEY".startswith("TANK_KEY_")
