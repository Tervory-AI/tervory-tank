"""Closed-catalogue shopper journey. Demo sheets only. No network and no live feed."""

from __future__ import annotations

import json
import re
import sys
import time
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

CN = ROOT / "agents" / "rig" / "catalogues" / "customnation"
EXAMPLE = ROOT / "agents" / "rig" / "catalogues" / "example"
SECOND = ROOT / "agents" / "rig" / "catalogues" / "second"
TENANT = "33333333-3333-4333-8333-333333333333"
EXAMPLE_TENANT = "11111111-1111-4111-8111-111111111111"
SECOND_TENANT = "22222222-2222-4222-8222-222222222222"
KEY = "rk_pub_customnation"
EXAMPLE_KEY = "rk_pub_examplebrand"
SECOND_KEY = "rk_pub_secondtenant"
ORIGIN = "https://rig.tervory.com"
PISTOL = "STI-P-9"
ALLOWED_HOSTS = {"rig.tervory.com", "127.0.0.1:5173", "assets.local"}


class Models:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, messages
        self.calls.append(task_type)
        raise AssertionError(task_type)


def _urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s,\"']+", text)


def _host(url: str) -> str:
    return url.split("://", 1)[1].split("/", 1)[0]


@pytest.mark.asyncio
async def test_staccato_accessories_stay_in_the_closed_catalogue() -> None:
    for path in CN.iterdir():
        if not path.is_file():
            continue
        for url in _urls(path.read_text(encoding="utf-8")):
            assert _host(url) in ALLOWED_HOSTS
    publish = json.loads((CN / "publish.json").read_text(encoding="utf-8"))
    assert "feed" not in publish
    assert publish["name"] == "Tervory"
    assert "Example" not in (CN / "products.csv").read_text(encoding="utf-8")

    store = MemoryStore()
    models = Models()
    service = Service(store, models)
    report = await service.load_folder(CN)
    assert report["products"]["rejected"] == []
    assert report["fits"]["rejected"] == []
    assert report["market"]["rejected"] == []
    assert report["market"]["rows"] == 32
    await service.load_folder(EXAMPLE)
    await service.load_folder(SECOND)
    looked: list[str] = []
    original = store.market_for

    async def watch(tenant_id: str, skus: list[str]) -> list[dict]:
        looked.append(tenant_id)
        return await original(tenant_id, skus)

    store.market_for = watch

    found = await service.search(TENANT, "Staccato", 12)
    assert [item["name"] for item in found["results"]] == ["Staccato C2", "Staccato P", "Staccato XC"]
    assert all("market" not in item for item in found["results"])
    assert looked == []

    graph = await service.graph(TENANT, PISTOL)
    assert looked == []
    assert [branch["category"] for branch in graph["branches"]] == [
        "Aftermarket sights",
        "Grips",
        "Holsters",
        "Lights",
        "Magazines",
        "Optics",
        "Triggers",
    ]
    assert all(branch["role"] == branch["category"] for branch in graph["branches"])
    grouped = {branch["category"]: [item["name"] for item in branch["products"]] for branch in graph["branches"]}
    assert grouped["Optics"] == ["Holosun 507C X2", "Trijicon RMR Type 2"]
    assert grouped["Grips"] == ["Cheely E2 grip"]
    assert grouped["Holsters"] == ["Safariland ALS duty holster"]
    assert "Streamlight TLR-1 HL" in grouped["Lights"]
    assert all("market" not in item for branch in graph["branches"] for item in branch["products"])
    assert all(item["price"]["currency"] == "ZAR" for branch in graph["branches"] for item in branch["products"])

    compact = await service.graph(TENANT, "STI-C2-9")
    compact_groups = {branch["category"]: [item["id"] for item in branch["products"]] for branch in compact["branches"]}
    assert compact_groups["Grips"] == ["CHEELY-C2"]
    assert "CHEELY-E2" not in compact_groups["Grips"]
    assert compact_groups["Magazines"] == ["MAG-16"]

    await store.upsert_product(
        TENANT,
        {
            "sku": "QUIET-DOT",
            "name": "Quiet Dot",
            "brand": "Quiet",
            "category": "Optics",
            "price": "100.00",
            "currency": "ZAR",
            "image_url": "https://assets.local/quiet.jpg",
            "active": True,
            "attributes": {},
            "family": "",
        },
    )
    await store.upsert_fit(
        TENANT,
        {
            "part_sku": "QUIET-DOT",
            "fits_sku": PISTOL,
            "fits_family": None,
            "rule": {},
            "source": "suggested",
            "approved": False,
            "note": "Held back",
            "confidence": 0.2,
        },
    )
    hidden = await service.graph(TENANT, PISTOL)
    assert "Quiet Dot" not in json.dumps(hidden)
    assert looked == []

    app = FastAPI()
    app.state.rig = service
    mount(app)
    client = TestClient(app)
    shopper = {"X-Rig-Key": KEY, "Origin": ORIGIN}
    listed = client.get("/v1/rig/search", params={"q": "Staccato"}, headers=shopper)
    assert listed.status_code == 200
    assert [item["name"] for item in listed.json()["results"]] == ["Staccato C2", "Staccato P", "Staccato XC"]
    assert looked == []

    both = client.post(
        "/v1/rig/compare",
        headers=shopper,
        json={"product_ids": ["TRIJ-RMR-T2", "SL-TLR1", "TEN8-REAR"]},
    )
    assert both.status_code == 200
    body = both.json()
    assert body["retailer"] == "Tervory"
    by_id = {line["id"]: line for line in body["lines"]}
    assert by_id["TRIJ-RMR-T2"]["price"]["amount"] == 9999
    assert by_id["TRIJ-RMR-T2"]["market"]["amount"] == 10000
    assert by_id["TRIJ-RMR-T2"]["market"]["currency"] == "ZAR"
    assert by_id["SL-TLR1"]["price"]["amount"] == 2799
    assert by_id["SL-TLR1"]["market"] is None
    assert by_id["TEN8-REAR"]["market"] is None
    assert looked == [TENANT]

    rows = await original(TENANT, ["TRIJ-RMR-T2"])
    rows.append({"sku": "TRIJ-RMR-T2", "source": "Demo Shop C", "price": "100.00", "currency": "USD", "seen_at": ""})
    await store.replace_market(TENANT, rows)
    again = await service.compare(TENANT, ["TRIJ-RMR-T2"])
    assert again["lines"][0]["market"]["amount"] == 10000
    assert models.calls == []

    other = client.get("/v1/rig/search", params={"q": "Staccato"}, headers={"X-Rig-Key": EXAMPLE_KEY, "Origin": ORIGIN})
    assert other.status_code == 200
    assert other.json()["results"] == []
    foreign = client.post(
        "/v1/rig/compare",
        headers={"X-Rig-Key": SECOND_KEY, "Origin": "https://second.example"},
        json={"product_ids": [PISTOL]},
    )
    assert foreign.status_code == 404
    assert PISTOL not in foreign.text

    await service.graph(TENANT, PISTOL)
    await service.compare(TENANT, [PISTOL, "TRIJ-RMR-T2", "SL-TLR1"])
    started = time.perf_counter()
    for _ in range(15):
        await service.graph(TENANT, PISTOL)
        await service.compare(TENANT, [PISTOL, "TRIJ-RMR-T2", "SL-TLR1"])
    assert time.perf_counter() - started < 0.3
    assert models.calls == []


@pytest.mark.asyncio
async def test_a_market_sheet_cannot_add_a_sku_the_catalogue_does_not_have(tmp_path: Path) -> None:
    folder = tmp_path / "standin"
    folder.mkdir()
    (folder / "publish.json").write_text(
        json.dumps({"tenant_id": TENANT, "name": "Stand In"}),
        encoding="utf-8",
    )
    (folder / "products.csv").write_text(
        "sku,gtin,name,brand,category,price,currency,image_url,product_url,family,active,attributes\n"
        "STAND-1,,Stand In Item,Stand,Widgets,10.00,ZAR,https://assets.local/stand.jpg,,,yes,{}\n",
        encoding="utf-8",
    )
    (folder / "market.csv").write_text(
        "sku,source,price,currency,seen_at\nOUTSIDE-1,Demo Shop A,5.00,ZAR,2026-03-01\n",
        encoding="utf-8",
    )
    service = Service(MemoryStore(), Models())
    report = await service.load_folder(folder)
    assert report["products"]["added"] == 1
    assert report["market"]["rows"] == 0
    assert report["market"]["rejected"][0]["reason"] == "sku is not in this catalogue"
    assert await service.store.market_for(TENANT, ["OUTSIDE-1", "STAND-1"]) == []
