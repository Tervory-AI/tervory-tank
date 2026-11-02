"""The live page never chooses the saved catalogues; fixtures remain offline."""

from rig_fixture_loader import load_catalogue

from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from test_rig_v5_page import _client, ARCHON, KEY
from test_rig_page import _load_rig_app
from rigbox.page_route import mount_page
from rigbox.service import Service
from rigbox.store import MemoryStore


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/v5",
        "/v5/cn",
        "/house",
        "/cn-classic",
        "/product/unknown",
        "/page/v5/rig.js",
        "/page/v5/rig.css",
    ],
)
def test_live_pages_do_not_select_or_return_fixture_text(path, monkeypatch):
    monkeypatch.delenv("RIG_WIDGET_PUBLISHABLE_KEY", raising=False)
    response = _client().get(path)
    assert response.status_code == 200
    assert not any(
        word in response.text.lower() for word in ["archon", "demo price", "sample"]
    )
    assert KEY not in response.text


def test_fixture_files_remain_offline_only():
    client = _client()
    assert (ARCHON / "products.csv").is_file()
    assert client.get("/page/v5/sample-suppliers.json").status_code == 404
    assert client.get("/catalogues/archon/products.csv").status_code == 404


@pytest.mark.asyncio
async def test_configured_page_requires_its_own_published_products(monkeypatch):
    # Reuse existing non-secret offline fixture IDs, exercising the actual store.
    root = ARCHON.parent
    publish = json.loads((root / "second/publish.json").read_text())
    service = Service(MemoryStore())
    await load_catalogue(service, ARCHON)
    await load_catalogue(service, root / "second")
    monkeypatch.setenv("RIG_WIDGET_PUBLISHABLE_KEY", publish["keys"][0]["key"])
    app = FastAPI()
    app.state.rig = service
    mount_page(app)
    client = TestClient(app)
    page = client.get("/").text
    assert publish["keys"][0]["key"] in page
    assert KEY not in page
    assert "Archon" not in page
    # Removing only the configured fixture tenant's products cannot borrow Archon.
    service.store._products = {
        key: value
        for key, value in service.store._products.items()
        if key[0] != publish["tenant_id"]
    }
    page = client.get("/").text
    assert 'window.RIG_KEY = "";' in page
    assert publish["keys"][0]["key"] not in page and KEY not in page


@pytest.mark.asyncio
@pytest.mark.parametrize("setting", [None, "bundled", "/app/catalogues"])
async def test_production_startup_never_imports_bundled_catalogues(
    setting, monkeypatch
):
    module = _load_rig_app()
    if setting is None:
        monkeypatch.delenv("CATALOGUE_DIR", raising=False)
    else:
        monkeypatch.setenv(
            "CATALOGUE_DIR",
            str(Path(module.__file__).parent / "catalogues")
            if setting == "bundled"
            else setting,
        )

    @asynccontextmanager
    async def context(*args):
        yield SimpleNamespace()

    store = SimpleNamespace(
        apply_schema=AsyncMock(), tenant_ids=AsyncMock(return_value=[])
    )
    service = SimpleNamespace(load_catalogues=AsyncMock(return_value=[]))
    application = FastAPI()
    application.state.pool = SimpleNamespace(acquire=context)
    application.state.http = None
    application.state.tank = None
    monkeypatch.setattr(module, "_inner", context)
    monkeypatch.setattr(module, "PgStore", lambda pool: store)
    monkeypatch.setattr(module, "QuoteService", lambda *args: service)
    monkeypatch.setattr(module, "serve_retailer", context)
    monkeypatch.setattr(module, "ensure_schedules", AsyncMock())
    async with module._lifespan(application):
        pass
    service.load_catalogues.assert_not_called()
