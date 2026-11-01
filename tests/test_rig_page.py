"""The Rig search page at GET /. No database and no network."""

from __future__ import annotations

from rig_fixture_loader import load_catalogue

import hashlib
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

EXAMPLE = ROOT / "tests" / "fixtures" / "rig_catalogues" / "example"
DEMO = ROOT / "tests" / "fixtures" / "rig_catalogues" / "customnation"
ARCHON = ROOT / "tests" / "fixtures" / "rig_catalogues" / "archon"
PAGE = ROOT / "agents" / "rig" / "rigbox" / "page"
ORIGIN = "https://rig.tervory.com"
PRODUCT = "Example Rifle 308 20in"


class Models:
    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type, messages
        return ""


def _publish() -> dict:
    return json.loads((EXAMPLE / "publish.json").read_text(encoding="utf-8"))


def _demo_publish() -> dict:
    return json.loads((DEMO / "publish.json").read_text(encoding="utf-8"))


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


def _archon_publish() -> dict:
    return json.loads((ARCHON / "publish.json").read_text(encoding="utf-8"))


def test_rig_app_serves_a_search_page() -> None:
    """Root serves the v5 shell without selecting an offline fixture catalogue."""
    import asyncio

    rig_app = _load_rig_app()
    status, body, content_type = asyncio.run(_body(rig_app.app, "/"))
    assert status == 200
    assert content_type.startswith("text/html")
    html = body.decode()
    assert "What are you building?" in html
    assert 'data-skin="rig"' in html
    assert "__RIG_KEY__" not in html
    assert "__RIG_SKIN__" not in html
    assert json.dumps(_archon_publish()["keys"][0]["key"]) not in html
    assert _publish()["keys"][0]["key"] not in html
    assert "live distributor keys are off" not in html
    assert "Demo · keys off" not in html
    assert "Archon Type B" not in html
    digest = hashlib.sha256((PAGE / "v5/rig.js").read_bytes()).hexdigest()
    assert f'src="/page/v5/assets/{digest}/rig.js"' in html
    assert "api-base" not in html


@pytest.mark.asyncio
async def test_offline_fixture_search_stays_available_without_live_page_defaults() -> None:
    store = MemoryStore()
    service = Service(store, Models(), RecordingHandoff())
    demo = await load_catalogue(service, DEMO)
    example = await load_catalogue(service, EXAMPLE)
    archon = await load_catalogue(service, ARCHON)
    assert demo["keys"] == 1
    assert example["keys"] == 1
    assert archon["keys"] == 1
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    client = TestClient(app)
    page = client.get("/")
    assert page.status_code == 200
    archon_key = _archon_publish()["keys"][0]["key"]
    demo_key = _demo_publish()["keys"][0]["key"]
    example_key = _publish()["keys"][0]["key"]
    assert json.dumps(archon_key) not in page.text
    assert example_key not in page.text
    assert "What are you building?" in page.text
    assert "live distributor keys are off" not in page.text
    assert "Demo · keys off" not in page.text
    assert 'alt="Tervory"' in page.text
    # Classic routes also require an explicitly configured published store.
    classic = client.get("/cn-classic")
    assert classic.status_code == 200
    assert json.dumps(demo_key) not in classic.text
    assert "Custom Nation" not in classic.text
    assert client.get("/house").status_code == 200
    found = client.get(
        "/v1/rig/search",
        params={"q": "LumaWorks", "limit": 12},
        headers={"X-Rig-Key": demo_key, "Origin": ORIGIN},
    )
    assert found.status_code == 200
    names = [item["name"] for item in found.json()["results"]]
    assert names[0] == "LumaWorks C2"
    assert all("Example" not in name for name in names)
    archon_hit = client.get(
        "/v1/rig/search",
        params={"q": "Archon Type B", "limit": 12},
        headers={"X-Rig-Key": archon_key, "Origin": ORIGIN},
    )
    assert archon_hit.status_code == 200
    assert any(item["id"] == "ARCHON-TYPE-B" for item in archon_hit.json()["results"])
    other = client.get(
        "/v1/rig/search",
        params={"q": "Rifle", "limit": 12},
        headers={"X-Rig-Key": example_key, "Origin": ORIGIN},
    )
    assert other.status_code == 200
    assert [item["name"] for item in other.json()["results"]] == [PRODUCT]
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
    assert "priceLine(product.price)" in fit_card
    assert "Market average" not in fit_card
    assert '"/v1/rig/compare"' not in shopper_js.split("async function comparePrices", 1)[0]
    assert shopper_js.count('"/v1/rig/compare"') == 1
    assert "Market average: not available" in shopper_js
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
    report = await load_catalogue(service, EXAMPLE)
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
    classic = client.get("/cn-classic")
    product_page = client.get(f"/product/{RIFLE}")
    dealer = client.get("/admin")
    assert home.status_code == product_page.status_code == dealer.status_code == classic.status_code == 200
    assert "What are you building?" in home.text
    assert "live distributor keys are off" not in home.text
    assert "Demo · keys off" not in home.text
    assert json.dumps(_archon_publish()["keys"][0]["key"]) not in home.text
    assert key not in home.text
    assert "See compatible accessories" in classic.text
    assert "Compare prices" in classic.text
    assert "See compatible accessories" in product_page.text
    assert "Market average" not in classic.text
    assert json.dumps(_demo_publish()["keys"][0]["key"]) not in classic.text
    assert "Custom Nation" not in classic.text
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


@pytest.mark.parametrize("url", ["/", "/v5", "/v5/cn", "/v5?skin=cn"])
def test_page_asset_urls_survive_a_stale_legacy_cache(monkeypatch, tmp_path, url):
    """A new HTML response must not reuse a cached URL for changed bytes."""
    import re
    import shutil
    from rigbox import page_route

    source = PAGE / "v5"
    for name in ("index.html", "rig.css", "rig.js"):
        (tmp_path / name).write_bytes((source / name).read_bytes())
    shutil.copytree(source / "assets", tmp_path / "assets")
    monkeypatch.setattr(page_route, "_V5", tmp_path)
    # No configured store or credentials are needed for the published shell.
    monkeypatch.delenv("RIG_WIDGET_PUBLISHABLE_KEY", raising=False)
    app = FastAPI()
    mount_page(app)
    client = TestClient(app)
    original = client.get(url)
    assert original.headers["cache-control"] == "no-store"
    urls = re.findall(r'(?:href|src)="(/page/v5/assets/[^"]+)"', original.text)
    assert len(urls) == 2
    cache = {path: client.get(path).content for path in urls}
    css_url = next(path for path in urls if path.endswith("rig.css"))
    js_url = next(path for path in urls if path.endswith("rig.js"))
    assert client.get(css_url).headers["cache-control"] == "public, max-age=31536000, immutable"
    legacy_cached = client.get("/page/v5/rig.css").content
    assert client.get("/page/v5/rig.css").headers["cache-control"] == "no-cache"
    changed = legacy_cached + b"\n/* offline deployment revision */\n"
    (tmp_path / "rig.css").write_bytes(changed)
    (tmp_path / "assets" / (hashlib.sha256(changed).hexdigest() + "-rig.css")).write_bytes(changed)
    updated = client.get(url)
    expected = f"/page/v5/assets/{hashlib.sha256(changed).hexdigest()}/rig.css"
    assert expected in updated.text and css_url not in updated.text
    assert js_url in updated.text  # Unchanged assets retain their cache identity.
    assert expected not in cache
    fetched = client.get(expected)
    assert fetched.status_code == 200 and fetched.content == changed
    assert hashlib.sha256(fetched.content).hexdigest() in expected
    assert legacy_cached != fetched.content
    old_response = client.get(css_url)
    assert old_response.status_code == 200 and old_response.content == legacy_cached
    assert hashlib.sha256(old_response.content).hexdigest() in css_url
    # Corrupt archives cannot impersonate an immutable object.
    (tmp_path / "assets" / (hashlib.sha256(legacy_cached).hexdigest() + "-rig.css")).write_bytes(changed)
    assert client.get(css_url).status_code == 404
    archived = tmp_path / "assets" / (hashlib.sha256(legacy_cached).hexdigest() + "-rig.css")
    outside = tmp_path / "outside.css"
    outside.write_bytes(legacy_cached)
    archived.unlink()
    archived.symlink_to(outside)
    assert client.get(css_url).status_code == 404
    assert client.get("/page/v5/assets/not-a-digest/rig.css").status_code == 404
    assert client.get("/page/v5/assets/anything/index.html").status_code == 404
    assert client.get(url).text == updated.text


@pytest.mark.parametrize("name", ["rig.css", "rig.js"])
def test_current_assets_have_retained_published_objects(name):
    data = (PAGE / "v5" / name).read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    assert (PAGE / "v5/assets" / f"{digest}-{name}").read_bytes() == data
