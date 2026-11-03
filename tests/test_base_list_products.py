"""B7: sourced product snapshots and tenant-only free downloads; no live services."""
import ast
import csv
import io
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import base_lists as lists
import command
import httpx
import pytest
from base_metrics import csv_text, export_records
from fastapi import FastAPI
from test_base_lists import OTHER, RECORD, STAMP, TENANT, Pool, record

ROOT = Path(__file__).resolve().parents[1]


def product(**changes):
    return {"name": "placeholder product", "sku": "placeholder-sku", "gtin": "placeholder-gtin",
            "mpn": "placeholder-mpn", "brand": "placeholder brand", "price": 0,
            "currency": "USD", "availability": "InStock", "url": "https://placeholder.example/product",
            "source_url": "https://placeholder.example/catalogue", "checked_at": STAMP, **changes}


def projected(products):
    return lists.project({"id": RECORD, "raw": {}, "passes": {}, "updated_at": STAMP,
                          "profile": {"products": {"value": products, "source": "site:code", "confidence": 90}}})


def test_projection_retains_individual_sources_and_drops_unsourced_products():
    first = product()
    second = product(name="placeholder second", source_url="https://placeholder.example/second", checked_at="2026-10-01")
    values = [product(source_url=None), first, product(checked_at=None), second,
              product(source_url="javascript:placeholder"), product(checked_at=" "), "placeholder"]
    before = deepcopy(values)
    result = projected(values)
    assert result["fields"]["products"] == lists.field([first, second], second["source_url"], second["checked_at"])
    assert values == before
    for value in ([], None, "placeholder", {"name": "placeholder"}, [product(source_url=None)], [product(checked_at=None)]):
        assert "products" not in projected(value)["fields"]


@pytest.mark.parametrize("present", [False, True])
def test_has_products_filters_missing_and_verified_products(present):
    row = projected([product()] if present else [])
    assert lists.matches(row, lists.FindArgs(has_products=present))
    assert not lists.matches(row, lists.FindArgs(has_products=not present))
    assert lists.matches(row, lists.FindArgs())
    if present:
        for patch in ({"verified": False}, {"source_url": None}, {"checked_at": None}):
            invalid = deepcopy(row)
            invalid["fields"]["products"].update(patch)
            assert lists.matches(invalid, lists.FindArgs(has_products=False))
            assert not lists.matches(invalid, lists.FindArgs(has_products=True))


@pytest.mark.asyncio
async def test_products_survive_saved_snapshot_without_changing_main_csv():
    pool = Pool()
    store = lists.Store(pool)
    row = record()
    original = export_records([row]).encode()
    row["fields"]["products"] = projected([product()])["fields"]["products"]
    async def scan(conn, tenant, filters, ids=None):
        assert tenant == TENANT and filters.has_products is True
        yield deepcopy(row)
    store.scan = scan
    saved = await store.save(TENANT, "placeholder products", lists.FindArgs(has_products=True))
    row["fields"]["products"]["value"].clear()
    snapshot = await store.show(TENANT, saved["list_id"])
    assert snapshot["records"][0]["fields"]["products"]["value"] == [product()]
    assert json.loads(pool.saved[TENANT, saved["list_id"]]["filters"])["has_products"] is True
    assert export_records(snapshot["records"]).encode() == original


@pytest.mark.asyncio
async def test_product_download_tenant_scope_columns_and_real_zero_dollar_receipt(monkeypatch):
    ledger = []
    ledger_id = uuid4()
    class ReceiptPool(Pool):
        async def fetchval(self, sql, *args):
            assert "INSERT INTO tank.ledger" in sql and "'code',0,0,0" in sql
            assert args == (TENANT, "us-east", "base.list.products")
            ledger.append((sql, args))
            return ledger_id
    pool = ReceiptPool()
    own, foreign = uuid4(), uuid4()
    rows = [record(), record()]
    rows[0]["fields"].update(projected([product(), product(name="placeholder second", source_url="https://placeholder.example/second", checked_at="2026-10-01")])["fields"])
    rows[1]["record_id"] = str(uuid4())
    rows[1]["name"] = "placeholder second business"
    rows[1]["fields"].update(projected([product(name="=placeholder formula")])["fields"])
    for tenant, key in ((TENANT, own), (OTHER, foreign)):
        pool.saved[tenant, key] = {"records": json.dumps(rows), "filters": "{}", "name": "placeholder list"}
    actor = command.Actor(TENANT, "placeholder-user", False, frozenset({"base"}))
    monkeypatch.setattr(command, "db", lambda: pool)
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(pool=lambda: pool, box_region=lambda: "us-east"))
    app = FastAPI()
    app.include_router(lists.build_router())
    app.dependency_overrides[command.identity] = lambda: actor
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder") as client:
        response = await client.get("/v1/command/base/lists/products", params={"list_id": str(own)})
        assert response.status_code == 200
        result = response.json()
        assert result == {"total": 3, "url": f"https://app.tervory.com/base/download?list_id={own}&kind=products",
                          "cost_usd": 0, "ledger_id": str(ledger_id)}
        assert len(ledger) == 1
        response = await client.get("/v1/command/base/lists/products.csv", params={"list_id": str(own), "tenant_id": str(OTHER)})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "private, no-store"
        assert response.headers["content-disposition"] == 'attachment; filename="base-products.csv"'
        assert response.content.startswith(b"\xef\xbb\xbf")
        reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
        assert reader.fieldnames == ["record_id", "licence_key", "business_name", "name", "sku", "gtin", "mpn", "brand", "price", "currency", "availability", "url", "source_url", "checked_at"]
        output = list(reader)
        assert len(output) == 3
        assert output[0] == {"record_id": rows[0]["record_id"], "licence_key": rows[0]["licence_key"],
                             "business_name": rows[0]["name"], **{k: str(v) for k, v in product().items()}}
        assert output[1]["source_url"] == "https://placeholder.example/second"
        assert output[1]["checked_at"] == "2026-10-01"
        assert output[2]["business_name"] == "placeholder second business"
        assert output[2]["name"] == "'=placeholder formula"
        assert len(ledger) == 1  # CSV follows the existing download receipt policy.
        for path in ("products", "products.csv"):
            response = await client.get("/v1/command/base/lists/" + path, params={"list_id": str(foreign)})
            assert response.status_code == 404
        assert len(ledger) == 1
        response = await client.get("/v1/command/base/lists/products.csv", params={"list_id": "placeholder-invalid"})
        assert response.status_code == 422
        actor = command.Actor(TENANT, "placeholder-user", False, frozenset({"tiger"}))
        for path in ("products", "products.csv"):
            response = await client.get("/v1/command/base/lists/" + path, params={"list_id": str(own)})
            assert response.status_code == 403


def test_export_drops_unverified_or_invalid_snapshot_products():
    row = record()
    row["fields"]["products"] = lists.field([product(), product(source_url=None), product(checked_at=None)], product()["source_url"], STAMP)
    assert len(lists.product_rows([row])) == 1
    row["fields"]["products"]["verified"] = False
    assert lists.product_rows([row]) == []
    row["fields"].pop("products")
    assert lists.product_rows([row]) == []


def test_products_adapter_is_read_only_scoped_and_uses_existing_confirmation_flow(monkeypatch):
    monkeypatch.setitem(sys.modules, "main", SimpleNamespace(box_region=lambda: "us-east"))
    actor = command.Actor(TENANT, "placeholder-user", False, frozenset({"base"}))
    assert "base.list.products" in command.allowed_tools(actor)
    action = command.validate_action(command.PlannedAction(tool="base.list.products", arguments={"list_id": str(RECORD)}), actor)
    adapter = command.ADAPTERS[action.tool]
    assert not adapter.paid
    method, path, params, body = command.adapter_request(action, actor)
    assert method == "GET" and path == "/v1/command/base/lists/products" and body is None
    assert params["list_id"] == str(RECORD)
    sets = [node for node in ast.walk(ast.parse((ROOT / "tank/command.py").read_text())) if isinstance(node, ast.Set)]
    assert all("base.list.products" not in [item.value for item in node.elts if isinstance(item, ast.Constant)] for node in sets)


def test_products_workspace_download_and_existing_card_labels():
    result = subprocess.run(["node", "tests/base_list_products.cjs"], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr



def test_preview_omits_products_without_changing_the_saved_snapshot():
    row = projected([product()])
    before = deepcopy(row)
    preview = lists.preview([row])["records"][0]
    assert "products" not in preview["fields"]
    assert "products" not in json.loads(preview["summary"])
    assert row == before and row["fields"]["products"]["value"] == [product()]


@pytest.mark.parametrize("reverse", [False, True])
def test_product_cutoff_uses_oldest_observation_in_either_order(reverse):
    products = [product(), product(source_url="https://placeholder.example/older", checked_at="2026-10-01")]
    row = projected(list(reversed(products)) if reverse else products)
    assert row["fields"]["products"]["checked_at"] == "2026-10-01"
    assert row["fields"]["products"]["source_url"] == "https://placeholder.example/older"
    assert not lists.matches(row, lists.FindArgs(checked_on_or_after="2026-10-02"))
    assert lists.matches(row, lists.FindArgs(checked_on_or_after="2026-10-01"))


def test_products_alone_cannot_create_a_confidence_tier():
    row = lists.project({"id": RECORD, "raw": {}, "updated_at": STAMP, "passes": {"7": {"placeholder": True}},
                         "profile": {"products": {"value": [product()]},
                                     "tier": {"value": "ready", "source": "verify"}}})
    assert row["fields"]["products"]["verified"]
    assert "confidence_tier" not in row["fields"]


@pytest.mark.parametrize("url,expected", [("https://placeholder.example/item?placeholder=query#fragment", "https://placeholder.example/item"),
                                           ("javascript:placeholder", None), (None, None)])
def test_product_url_normalization_applies_to_projection_and_saved_csv(url, expected):
    original = product(url=url, source_url="https://placeholder.example/catalogue?placeholder=query#fragment")
    normalized = lists.sourced_products([original])[0]
    assert normalized["url"] == expected
    assert normalized["source_url"] == "https://placeholder.example/catalogue"
    assert original["source_url"].endswith("#fragment")
    row = record()
    row["fields"]["products"] = lists.field([original], "https://placeholder.example/catalogue", STAMP)
    output = lists.product_rows([row])[0]
    assert output["url"] == expected and output["source_url"] == "https://placeholder.example/catalogue"


@pytest.mark.parametrize("prefix", ["+", "-", "@", "\t"])
@pytest.mark.parametrize("column", ["sku", "brand", "url"])
def test_products_csv_neutralizes_formula_prefixes(prefix, column):
    row = record()
    row["fields"]["products"] = lists.field([product(**{column: prefix + "placeholder"})],
                                              "https://placeholder.example/catalogue", STAMP)
    text = csv_text(lists.product_rows([row]), lists.PRODUCT_COLUMNS)
    cells = list(csv.DictReader(io.StringIO(text.lstrip("\ufeff"))))
    assert cells[0][column] == ("" if column == "url" else "'" + prefix + "placeholder")
