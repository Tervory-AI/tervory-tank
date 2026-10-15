"""The Rig search page at GET /. No database and no network."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.page_route import mount_page  # noqa: E402
from rigbox.service import RecordingHandoff, Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

EXAMPLE = ROOT / "agents" / "rig" / "catalogues" / "example"
PAGE = ROOT / "agents" / "rig" / "rigbox" / "page"
ORIGIN = "https://rig.tervory.com"
PRODUCT = "Example Rifle 308 20in"


class Models:
    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type, messages
        return ""


def _publish() -> dict:
    return json.loads((EXAMPLE / "publish.json").read_text(encoding="utf-8"))


def _load_rig_app():
    path = ROOT / "agents" / "rig" / "app.py"
    spec = importlib.util.spec_from_file_location("rig_search_page_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rig_search_page_app"] = module
    spec.loader.exec_module(module)
    return module


async def _body(app, path: str) -> tuple[int, bytes, str]:
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 9),
            "server": ("rig.tervory.com", 443),
        },
        receive,
        send,
    )
    status = int(sent[0]["status"])
    content_type = ""
    for key, value in sent[0]["headers"]:
        if key == b"content-type":
            content_type = value.decode()
    body = b"".join(message.get("body") or b"" for message in sent if message["type"] == "http.response.body")
    return status, body, content_type


def test_example_key_allows_the_public_origin() -> None:
    origins = _publish()["keys"][0]["origins"]
    assert ORIGIN in origins


def test_page_assets_use_the_brand_and_the_official_logo() -> None:
    css = (PAGE / "search.css").read_text(encoding="utf-8")
    assert css.count("#E80008") == 1
    assert "#001840" in css
    assert "#B8BFD0" in css
    assert "#F4F6FB" in css
    assert "form.search button" in css
    script = (PAGE / "search.js").read_text(encoding="utf-8")
    assert 'fetch("/v1/rig/search?' in script
    assert "mock" not in script
    assert "https://" not in script
    logo = PAGE / "tervory-logo-on-white.png"
    official = ROOT / "workspace" / "public" / "brand" / "tervory-logo-on-white.png"
    assert logo.read_bytes() == official.read_bytes()
    dockerfile = (ROOT / "agents" / "rig" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY rig/rigbox /app/rigbox" in dockerfile


def test_rig_app_serves_a_search_page() -> None:
    import asyncio

    rig_app = _load_rig_app()
    status, body, content_type = asyncio.run(_body(rig_app.app, "/"))
    assert status == 200
    assert content_type.startswith("text/html")
    html = body.decode()
    assert 'type="search"' in html
    assert 'role="search"' in html
    assert "__RIG_PUBLISHABLE_KEY__" not in html
    assert json.dumps(_publish()["keys"][0]["key"]) in html
    assert 'src="/page/search.js"' in html
    assert 'src="/page/tervory-logo-on-white.png"' in html
    assert "api-base" not in html
    assert "mock" not in html


@pytest.mark.asyncio
async def test_search_on_the_page_returns_the_example_product() -> None:
    store = MemoryStore()
    service = Service(store, Models(), RecordingHandoff())
    report = await service.load_folder(EXAMPLE)
    assert report["keys"] == 1
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    key = _publish()["keys"][0]["key"]
    assert json.dumps(key) in page.text
    found = client.get(
        "/v1/rig/search",
        params={"q": "Rifle", "limit": 12},
        headers={"X-Rig-Key": key, "Origin": ORIGIN},
    )
    assert found.status_code == 200
    names = [item["name"] for item in found.json()["results"]]
    assert names == [PRODUCT]
    script = client.get("/page/search.js")
    assert script.status_code == 200
    assert 'fetch("/v1/rig/search?' in script.text
    logo = client.get("/page/tervory-logo-on-white.png")
    assert logo.status_code == 200
    assert logo.content == (PAGE / "tervory-logo-on-white.png").read_bytes()
