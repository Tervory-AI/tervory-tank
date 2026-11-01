"""A publishable key from one catalogue never returns another tenant's products.

Uses the in-memory store, the same way tests/test_rig.py does. No database and no network.
"""

from __future__ import annotations

async def load_catalogue(service, folder):
    from rig_fixture_loader import load_catalogue as load
    return await load(service, folder)


import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

EXAMPLE = ROOT / "tests" / "fixtures" / "rig_catalogues" / "example"
SECOND = ROOT / "tests" / "fixtures" / "rig_catalogues" / "second"
EXAMPLE_TENANT = "11111111-1111-4111-8111-111111111111"
SECOND_TENANT = "22222222-2222-4222-8222-222222222222"
EXAMPLE_KEY = "rk_pub_examplebrand"
SECOND_KEY = "rk_pub_secondtenant"
EXAMPLE_ORIGIN = "https://rig.tervory.com"
SECOND_ORIGIN = "https://second.example"
EXAMPLE_RIFLE = "EXAMPLE-RIFLE-01"
SECOND_PRODUCT = "SECOND-LAMP-01"


def _client(service: Service) -> TestClient:
    app = FastAPI()
    app.state.rig = service
    mount(app)
    return TestClient(app)


def _headers(key: str, origin: str) -> dict[str, str]:
    return {"X-Rig-Key": key, "Origin": origin}


async def _loaded() -> Service:
    service = Service(MemoryStore())
    example = await load_catalogue(service, EXAMPLE)
    second = await load_catalogue(service, SECOND)
    assert example["tenant_id"] == EXAMPLE_TENANT
    assert example["products"] == {"added": 3, "updated": 0, "rejected": []}
    assert example["keys"] == 1
    assert second["tenant_id"] == SECOND_TENANT
    assert second["products"] == {"added": 2, "updated": 0, "rejected": []}
    assert second["fits"] == {"added": 1, "updated": 0, "rejected": []}
    assert second["keys"] == 1
    return service


def _ids(body: dict) -> list[str]:
    return [item["id"] for item in body["results"]]


@pytest.mark.asyncio
async def test_a_key_never_returns_another_tenants_catalogue() -> None:
    service = await _loaded()
    client = _client(service)
    example = _headers(EXAMPLE_KEY, EXAMPLE_ORIGIN)
    second = _headers(SECOND_KEY, SECOND_ORIGIN)

    own_rifle = client.get("/v1/rig/search", params={"q": "rifle"}, headers=example)
    assert own_rifle.status_code == 200
    assert EXAMPLE_RIFLE in _ids(own_rifle.json())

    foreign_rifle = client.get("/v1/rig/search", params={"q": "rifle"}, headers=second)
    assert foreign_rifle.status_code == 200
    assert EXAMPLE_RIFLE not in _ids(foreign_rifle.json())
    assert EXAMPLE_RIFLE not in foreign_rifle.text

    foreign_rifle_by_sku = client.get("/v1/rig/search", params={"q": EXAMPLE_RIFLE}, headers=second)
    assert foreign_rifle_by_sku.status_code == 200
    assert EXAMPLE_RIFLE not in _ids(foreign_rifle_by_sku.json())
    assert all(not item["id"].startswith("EXAMPLE-") for item in foreign_rifle_by_sku.json()["results"])

    hidden_rifle = client.get(f"/v1/rig/products/{EXAMPLE_RIFLE}", headers=second)
    assert hidden_rifle.status_code == 404
    assert hidden_rifle.json()["error"]["code"] == "not_found"
    assert EXAMPLE_RIFLE not in hidden_rifle.text

    own_lamp = client.get("/v1/rig/search", params={"q": "lamp"}, headers=second)
    assert own_lamp.status_code == 200
    assert SECOND_PRODUCT in _ids(own_lamp.json())

    foreign_lamp = client.get("/v1/rig/search", params={"q": "lamp"}, headers=example)
    assert foreign_lamp.status_code == 200
    assert SECOND_PRODUCT not in _ids(foreign_lamp.json())
    assert SECOND_PRODUCT not in foreign_lamp.text
    assert "SECOND-" not in foreign_lamp.text

    foreign_lamp_by_sku = client.get("/v1/rig/search", params={"q": SECOND_PRODUCT}, headers=example)
    assert foreign_lamp_by_sku.status_code == 200
    foreign_body = foreign_lamp_by_sku.json()
    assert SECOND_PRODUCT not in _ids(foreign_body)
    assert all(not str(item["id"]).startswith("SECOND-") for item in foreign_body["results"])
    # The caller typed this sku. Quoting it in "no exact match" is not the other catalogue.
    echoed = str(foreign_body.get("message") or "")
    assert SECOND_PRODUCT not in echoed or echoed == f"No exact match for {SECOND_PRODUCT}."
    rendered = foreign_lamp_by_sku.text.replace(echoed, "")
    assert "SECOND-" not in rendered
    assert "Second Desk Lamp" not in foreign_lamp_by_sku.text

    hidden_lamp = client.get(f"/v1/rig/products/{SECOND_PRODUCT}", headers=example)
    assert hidden_lamp.status_code == 404
    assert hidden_lamp.json()["error"]["code"] == "not_found"

    seen_rifle = client.get(f"/v1/rig/products/{EXAMPLE_RIFLE}", headers=example)
    assert seen_rifle.status_code == 200
    assert seen_rifle.json()["id"] == EXAMPLE_RIFLE

    seen_lamp = client.get(f"/v1/rig/products/{SECOND_PRODUCT}", headers=second)
    assert seen_lamp.status_code == 200
    assert seen_lamp.json()["id"] == SECOND_PRODUCT
