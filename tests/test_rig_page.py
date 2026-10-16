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
from rigbox.service import RecordingHandoff, Service, hash_key  # noqa: E402
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


TENANT = "11111111-1111-4111-8111-111111111111"
ADMIN = "rk_adm_examplebrand"
RIFLE = "EXAMPLE-RIFLE-01"
WIDGET = "SOFT-WIDGET"
WIDGET_NAME = "Soft Widget"
NOTE = "Listed for this product"


def _page_text(name: str) -> str:
    return (PAGE / name).read_text(encoding="utf-8")


def _widget(graph: dict) -> dict:
    for branch in graph.get("branches") or []:
        for product in branch.get("products") or []:
            if product.get("id") == WIDGET:
                return {"role": branch.get("role"), "product": product}
    return {}


@pytest.mark.asyncio
async def test_shopper_and_dealer_pages_and_only_approved_fits_show() -> None:
    for name in ("index.html", "admin.html", "search.js", "admin.js", "search.css"):
        text = _page_text(name)
        assert "Ask dealer" not in text
        assert "In bundle" not in text
        assert "Example" not in text
    css = _page_text("search.css")
    for token in ("--ink:", "--action:", "--line:", "--tint:", "--font:", "--heading:", "--mono:"):
        assert token in css
    assert "minmax(0, 1fr) 320px" in css
    assert "attr(data-label)" in css
    shopper_js = _page_text("search.js")
    fit_card = shopper_js.split("function fitCard", 1)[1].split("function renderBundle", 1)[0]
    assert "price" not in fit_card
    assert "Swap part" in shopper_js
    assert "Why it fits" in shopper_js
    admin_js = _page_text("admin.js")
    assert admin_js.count('"/v1/rig/admin/fits/suggest"') == 1
    before_suggest, _, _after = admin_js.partition("async function suggestFits")
    assert '"/v1/rig/admin/fits/suggest"' not in before_suggest
    calls = [
        line.strip()
        for line in admin_js.splitlines()
        if "suggestFits()" in line and not line.strip().startswith("async function")
    ]
    assert calls == ["void suggestFits();"]
    assert "sessionStorage" in admin_js

    store = MemoryStore()
    models = Models()
    models.calls = []

    async def complete(tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        models.calls.append(task_type)
        return ""

    models.complete = complete
    service = Service(store, models, RecordingHandoff())
    report = await service.load_folder(EXAMPLE)
    assert report["keys"] == 1
    await store.put_key(TENANT, hash_key(ADMIN), "admin", [])
    await store.upsert_product(
        TENANT,
        {
            "sku": WIDGET,
            "name": WIDGET_NAME,
            "brand": "Soft",
            "category": "widget",
            "price": "100.00",
            "currency": "ZAR",
            "image_url": "",
            "active": True,
            "attributes": {},
            "family": "",
        },
    )
    await store.upsert_fit(
        TENANT,
        {
            "part_sku": WIDGET,
            "fits_sku": RIFLE,
            "fits_family": None,
            "rule": {},
            "source": "suggested",
            "approved": False,
            "note": NOTE,
            "confidence": 0.4,
        },
    )
    await store.set_template(
        TENANT,
        "rifle",
        {
            "tiers": [
                {
                    "tier": "ready",
                    "label": "Ready to use",
                    "roles": [
                        {"role": "optic", "category": "optic"},
                        {"role": "mount", "category": "mount"},
                        {"role": "carry", "category": "widget"},
                    ],
                }
            ]
        },
    )
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    client = TestClient(app)
    key = _publish()["keys"][0]["key"]
    shopper = {"X-Rig-Key": key, "Origin": ORIGIN}

    home = client.get("/")
    product_page = client.get(f"/product/{RIFLE}")
    dealer = client.get("/admin")
    assert home.status_code == product_page.status_code == dealer.status_code == 200
    assert "Compatible Upgrades" in home.text
    assert "Compatible Upgrades" in product_page.text
    assert json.dumps(key) in home.text
    assert "Nothing waiting for review" in dealer.text
    assert "Suggest new fits" in dealer.text
    assert "rk_pub_" not in dealer.text
    assert "__RIG" not in dealer.text
    assert 'src="/page/tervory-logo-on-white.png"' in dealer.text
    assert "Swap part" in client.get("/page/search.js").text
    assert client.get("/page/admin.js").status_code == 200
    assert models.calls == []

    hidden = client.get(f"/v1/rig/graph/{RIFLE}", headers=shopper)
    assert hidden.status_code == 200
    assert WIDGET_NAME not in hidden.text
    assert _widget(hidden.json()) == {}
    waiting = client.get("/v1/rig/admin/fits", params={"status": "suggested"}, headers={"X-Rig-Key": ADMIN})
    assert waiting.status_code == 200
    row = waiting.json()["fits"][0]
    assert row["part_name"] == WIDGET_NAME
    assert row["part_sku"] == WIDGET
    assert row["fits_with"] == hidden.json()["centre"]["name"]
    assert row["note"] == NOTE

    approved = client.post(
        "/v1/rig/admin/fits/approve",
        headers={"X-Rig-Key": ADMIN},
        json={"part_sku": WIDGET, "fits_sku": RIFLE},
    )
    assert approved.status_code == 200
    shown = client.get(f"/v1/rig/graph/{RIFLE}", headers=shopper)
    found = _widget(shown.json())
    assert found["role"] == "carry"
    assert found["product"]["name"] == WIDGET_NAME
    assert found["product"]["why"] == NOTE
    built = client.post("/v1/rig/setups", headers=shopper, json={"product_id": RIFLE})
    assert built.status_code == 200
    setup = built.json()["setups"][0]
    assert WIDGET in [part["product"]["id"] for part in setup["parts"]]
    assert setup["total"]["amount"] == 35297 + 100
    assert "discount" not in built.text
    assert client.get("/v1/rig/admin/fits", headers={"X-Rig-Key": ADMIN}).json() == {"fits": []}

    rejected = client.post(
        "/v1/rig/admin/fits/reject",
        headers={"X-Rig-Key": ADMIN},
        json={"part_sku": WIDGET, "fits_sku": RIFLE},
    )
    assert rejected.status_code == 200
    after = client.get(f"/v1/rig/graph/{RIFLE}", headers=shopper)
    after_setups = client.post("/v1/rig/setups", headers=shopper, json={"product_id": RIFLE})
    assert WIDGET_NAME not in after.text
    assert WIDGET not in after_setups.text
    assert after_setups.json()["setups"][0]["total"]["amount"] == 35297
    assert models.calls == []
