"""The /v1/zenas proxy stays on this server and stores nothing for the other home."""
from __future__ import annotations

import json
import os

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import pytest
from fastapi import HTTPException
from starlette.requests import Request

import main

SECRET = "laws-africa-secret-value"


def _request(method: str, path: str, body: bytes = b"", query: bytes = b"") -> Request:
    sent = {"done": False}

    async def receive() -> dict:
        if sent["done"]:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": query,
        "headers": [(b"content-type", b"application/json")],
        "client": ("127.0.0.1", 1),
        "server": ("test", 80),
    }
    return Request(scope, receive)


class _Room:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.calls: list[str] = []

    async def request(self, method: str, url: str, **kwargs: object) -> object:
        self.calls.append(url)

        class _Response:
            content = self.payload
            status_code = 200
            headers = {"content-type": "application/json"}

        return _Response()


def test_upstream_is_only_the_local_room(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://agent-zenas:8000")
    assert main.zenas_upstream("matters") == "http://agent-zenas:8000/matters"
    assert main.zenas_upstream("matters/11111111-1111-1111-1111-111111111111/documents").endswith("/documents")
    monkeypatch.setenv("ZENAS_AGENT_URL", "https://za-api.tervory.com")
    with pytest.raises(HTTPException) as caught:
        main.zenas_upstream("matters")
    assert caught.value.status_code == 403
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://10.1.2.3:8000")
    with pytest.raises(HTTPException) as caught:
        main.zenas_upstream("pool/status")
    assert caught.value.status_code == 403
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://agent-zenas:8000")
    with pytest.raises(HTTPException) as caught:
        main.zenas_upstream("../postgres")
    assert caught.value.status_code == 404


def test_feed_payload_keeps_the_key_name_and_drops_the_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAWS_AFRICA_API_TOKEN", SECRET)
    cleaned = main.annotate_key_set(
        main.public_feed(
            {
                "sources": [
                    {
                        "source_id": "laws-africa",
                        "key_name": "LAWS_AFRICA_API_TOKEN",
                        "api_key": SECRET,
                        "token": SECRET,
                        "documents": 4,
                    }
                ]
            }
        )
    )
    encoded = json.dumps(cleaned)
    assert SECRET not in encoded
    assert cleaned["sources"][0]["key_name"] == "LAWS_AFRICA_API_TOKEN"
    assert cleaned["sources"][0]["key_set"] is True
    assert "api_key" not in cleaned["sources"][0]


@pytest.mark.asyncio
async def test_proxy_refuses_the_other_home_and_does_not_call_the_room(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://agent-zenas:8000")
    room = _Room(b"{}")
    monkeypatch.setattr(main, "_http", room)
    body = json.dumps({"tenant_id": "11111111-1111-1111-1111-111111111111", "home_region": "za", "title": "NDA"}).encode()
    with pytest.raises(HTTPException) as caught:
        await main.zenas_proxy("matters", _request("POST", "/v1/zenas/matters", body))
    assert caught.value.detail == main.ZA_HOME_MESSAGE
    assert room.calls == []


@pytest.mark.asyncio
async def test_proxy_forwards_only_inside_the_region_and_strips_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://agent-zenas:8000")
    monkeypatch.setenv("LAWS_AFRICA_API_TOKEN", SECRET)
    room = _Room(
        json.dumps(
            {"sources": [{"source_id": "laws-africa", "key_name": "LAWS_AFRICA_API_TOKEN", "api_key": SECRET, "documents": 2}]}
        ).encode()
    )
    monkeypatch.setattr(main, "_http", room)
    response = await main.zenas_proxy(
        "pool/status",
        _request("GET", "/v1/zenas/pool/status", query=b"home_region=za"),
    )
    assert room.calls == ["http://agent-zenas:8000/pool/status"]
    assert SECRET.encode() not in response.body
    payload = json.loads(response.body)
    assert payload["sources"][0]["key_set"] is True


@pytest.mark.asyncio
async def test_a_foreign_room_url_is_not_called(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.setenv("ZENAS_AGENT_URL", "http://us-east.tervory.com")
    room = _Room(b"{}")
    monkeypatch.setattr(main, "_http", room)
    with pytest.raises(HTTPException) as caught:
        await main.zenas_proxy("health", _request("GET", "/v1/zenas/health"))
    assert caught.value.status_code == 403
    assert room.calls == []
