"""Private pricing inputs in catalogue attributes never reach a shopper.

Fixture rows (tests/fixtures/rig/sample-cost-guard.csv) are invented: SKUs,
GTINs, names, prices and costs are synthetic, shaped like Custom Nation's
catalogue rows. This repo is public, so real supplier costs never go in it.
Real data is checked only by the full-export test, which reads the CSV from
the box (RIG_CN_EXPORT) and skips when it is absent (CI).
Each costed row carries ``attributes.export_usd`` (the supplier's export
price), the leak this guards against, plus the same cost hidden inside
``verified`` in the shapes a store could use (named, unnamed, labelled
elsewhere, bare pairs).

Two kinds of store are exercised:
- ``imported``: rows go through the catalogue import, which moves pricing
  inputs out of attributes into the private table.
- ``legacy``: rows still carry the cost inside attributes, as live rows do
  until schema.sql's migration runs. The boundary and search allowlists must
  hold on their own.

Every shopper route on /v1/rig is exercised, and search must not be an
oracle for a cost: searching for a cost number or a private key name returns
exactly what it returns when the cost is not stored at all.
"""

from __future__ import annotations

import asyncio
import csv
import json
import logging
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.api import mount  # noqa: E402
from rigbox.catalogue import parse_products_csv  # noqa: E402
from rigbox.quotes.api import mount as mount_quotes  # noqa: E402
from rigbox.quotes.privacy import private_key, shopper_body  # noqa: E402
from rigbox.quotes.sample import KEY, TENANT, seed  # noqa: E402
from rigbox.quotes.service import QuoteService  # noqa: E402
from rigbox.quotes.store import MemoryQuotes  # noqa: E402
from rigbox.service import RecordingHandoff, Service  # noqa: E402
from rigbox.shopper_attributes import _PRICING, PRIVATE_KEY_PATTERN, SHOPPER_ATTRIBUTES, shopper_attributes  # noqa: E402
from rigbox.store import MemoryStore, PgStore  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "rig" / "sample-cost-guard.csv"
# The full Custom Nation export holds every real supplier cost, so it is not
# committed. Point RIG_CN_EXPORT at it (the shared box keeps a copy here).
CN_EXPORT = Path(os.environ.get("RIG_CN_EXPORT") or "/workspace/rig-smtp-quote/pof-usa-rig-products.csv")
HEADERS = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
CONTACT = {"name": "Sample Shopper", "email": "shopper@example.com"}
EXTRA = {"supplier_cost": 1, "landed_zar": 2, "markup_pct": 3, "wholesale": 4}
SECRETS = ("export_usd", "supplier_cost", "landed_zar", "markup_pct", "wholesale", "internal_note")
ARCHON_SHOP = {"search": True, "centre_sku": "90101", "not_stocked": []}


class Echo:
    """A model that tries to repeat every attribute it was shown."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type
        self.prompts.append(messages[-1]["content"])
        return json.dumps({"answer": "The export_usd is 437.", "cites": ["90101"]})


def _rows(path: Path = FIXTURE) -> list[dict[str, Any]]:
    parsed = parse_products_csv(path.read_text())
    assert parsed["rejected"] == []
    return parsed["rows"]


def _hidden_in_verified(row: dict[str, Any]) -> dict[str, Any]:
    """The cost again, inside ``verified``: named facts, unnamed facts, labels elsewhere, bare pairs."""
    cost = row["private_attributes"].get("export_usd")
    if cost is None:
        return row
    verified = [{"name": "export_usd", "value": cost, "source": "https://sample-arms.example/"},
                {"name": "POF export_usd", "value": cost}, {"name": "Dealer Price", "value": cost},
                {"label": "export_usd", "value": cost}, {"name": "spec", "value": cost, "note": "export_usd"},
                ["export_usd", cost], f"export_usd: {cost}", [f"export_usd={cost}"]]
    return {**row, "attributes": {**row["attributes"], "verified": verified}}


def _legacy(row: dict[str, Any]) -> dict[str, Any]:
    """The row as live stores hold it before the migration: cost inside attributes."""
    row = _hidden_in_verified(row)
    attributes = {**row["attributes"], **row["private_attributes"], **EXTRA, "internal_note": "buy from ZEPHYR"}
    return {key: value for key, value in {**row, "attributes": attributes}.items() if key != "private_attributes"}


def _clean_row(row: dict[str, Any]) -> dict[str, Any]:
    """The control: the same row with no pricing input stored anywhere."""
    return {key: value for key, value in row.items() if key != "private_attributes"}


async def _load(store: Any, rows: list[dict[str, Any]], mode: str) -> None:
    for row in rows:
        await store.upsert_product(TENANT, {"imported": _hidden_in_verified(row), "legacy": _legacy(row),
                                            "clean": _clean_row(row)}[mode])


def _app(mode: str) -> tuple[FastAPI, QuoteService, Echo]:
    async def ready() -> tuple[QuoteService, Echo]:
        store = MemoryStore()
        await seed(store)
        await _load(store, _rows(), mode)
        echo = Echo()
        return QuoteService(store, echo, RecordingHandoff(), MemoryQuotes(store)), echo

    rig, echo = asyncio.run(ready())
    app = FastAPI()
    app.state.rig = rig
    mount(app)
    mount_quotes(app)
    return app, rig, echo


def _clean(text: str) -> None:
    for word in SECRETS:
        assert word not in text, word
    assert "437" not in text  # 90101's export_usd value
    assert "ZEPHYR" not in text


def test_import_moves_export_usd_out_of_attributes() -> None:
    rows = _rows()
    assert len(rows) == 6
    for row in rows:
        assert "export_usd" not in row["attributes"], row["sku"]
        assert isinstance(row["private_attributes"]["export_usd"], (int, float)), row["sku"]
    first = next(row for row in rows if row["sku"] == "90101")
    assert first["attributes"] == {"color": "BLACK"}
    assert first["private_attributes"] == {"export_usd": 437}

    async def stored() -> None:
        store = MemoryStore()
        await _load(store, rows, "imported")
        kept = {row["sku"]: row for row in await store.products(TENANT)}
        assert all("private_attributes" not in row and "export_usd" not in row["attributes"] for row in kept.values())
        assert await store.product_private_attributes(TENANT, "90101") == {"export_usd": 437}
        # A re-import without the key clears the stale private value.
        await store.upsert_product(TENANT, {**first, "private_attributes": {}})
        assert await store.product_private_attributes(TENANT, "90101") == {}

    asyncio.run(stored())


@pytest.mark.parametrize("mode", ["imported", "legacy"])
def test_main_shopper_routes_never_return_export_usd(mode: str) -> None:
    app, rig, echo = _app(mode)
    with TestClient(app) as client:
        found = client.get("/v1/rig/search?q=suppressor", headers=HEADERS)
        assert found.status_code == 200 and found.json()["results"], found.text
        _clean(found.text)
        first = found.json()["results"][0]
        # Shopper-safe attributes still pass.
        assert first["attributes"].get("color") == "BLACK"
        for sku in ("90101", "90102", "90106"):
            detail = client.get(f"/v1/rig/products/{sku}", headers=HEADERS)
            assert detail.status_code == 200, detail.text
            _clean(detail.text)
        for path, body in (("/v1/rig/compare", {"product_ids": ["90101", "90102"]}),
                           ("/v1/rig/setups", {"product_id": "90101"})):
            response = client.post(path, headers=HEADERS, json=body)
            assert response.status_code == 200, (path, response.text)
            _clean(response.text)
        asked = client.post("/v1/rig/ask", headers=HEADERS,
                            json={"product_id": "90101", "question": "What does the KX-9 suppressor cost?"})
        assert asked.status_code == 200, asked.text
        _clean(asked.text)
        for prompt in echo.prompts:
            _clean(prompt)
        product = client.get("/v1/rig/products/90101", headers=HEADERS).json()
        setup = {"centre": product, "parts": [{"role": "Item", "product": product}]}
        quote = client.post("/v1/rig/quote", headers=HEADERS, json={"setup": setup, "contact": CONTACT})
        assert quote.status_code == 200, quote.text
        _clean(quote.text)
    # The store's own copy of the quote (handoff to its inbox) may keep its
    # own pricing inputs; it is store-facing. The email letter lists only id,
    # name, amount, price label and stock per item.
    for sent in rig.handoff.sent:
        if sent.get("letter"):
            _clean(json.dumps(sent["letter"], default=str))


def _ids(body: dict[str, Any]) -> list[str]:
    return [str(item.get("id")) for item in body.get("results") or [] if isinstance(item, dict)]


async def _service(rows: list[dict[str, Any]], mode: str, shop: dict[str, Any] | None, store: Any = None) -> Service:
    store = store or MemoryStore()
    await _load(store, rows, mode)
    service = Service(store)
    if shop is not None:
        async def _shop(tenant_id: str) -> dict[str, Any]:
            del tenant_id
            return shop
        service._shop = _shop  # type: ignore[method-assign]
    return service


def _costs(rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    by_cost: dict[str, list[str]] = {}
    for row in rows:
        cost = row["private_attributes"].get("export_usd")
        if cost is not None:
            by_cost.setdefault(str(cost), []).append(row["sku"])
    return by_cost


async def _oracle(rows: list[dict[str, Any]], shop: dict[str, Any] | None, store: Any = None,
                  control_store: Any = None, strict: bool = True) -> int:
    """Every cost number and private key name: same results as a store with no costs at all.

    ``strict`` also asserts the owning row is absent unless the number is in
    its public text (the review's probe). The full export has costs (decimals,
    small integers) that fuzzy-match other public text, so there only equality holds.
    """
    probe = await _service(rows, "legacy", shop, store)
    imported = await _service(rows, "imported", shop)
    control = await _service(rows, "clean", shop, control_store)
    checked = 0
    for cost, owners in sorted(_costs(rows).items()):
        expected = _ids(await control.search(TENANT, cost, 24))
        for service in (probe, imported):
            got = _ids(await service.search(TENANT, cost, 24))
            assert got == expected, (cost, owners, got, expected)
        for sku in owners:
            row = next(item for item in rows if item["sku"] == sku)
            public = f"{row['name']} {row['sku']} {row.get('gtin') or ''} {json.dumps(row['attributes'])}"
            if strict and cost not in re.findall(r"[0-9]+", public):
                assert sku not in expected, (cost, sku)
        checked += 1
    for word in (*SECRETS, "zephyr", "buy from"):
        for service in (probe, imported):
            assert _ids(await service.search(TENANT, word, 24)) == [], word
    return checked


@pytest.mark.parametrize("shop", [None, ARCHON_SHOP], ids=["rank", "cn-shop-search"])
def test_search_is_not_a_cost_oracle(shop: dict[str, Any] | None) -> None:
    rows = _rows()
    checked = asyncio.run(_oracle(rows, shop))
    assert checked == 6
    # The review's exact probes: q=437 used to return only 90101.
    async def probes() -> None:
        legacy = await _service(rows, "legacy", shop)
        assert "90101" not in _ids(await legacy.search(TENANT, "437", 24))
        assert _ids(await legacy.search(TENANT, "export_usd", 24)) == []
    asyncio.run(probes())


@pytest.mark.skipif(not CN_EXPORT.is_file(), reason="full Custom Nation export is not committed (real supplier costs)")
@pytest.mark.parametrize("shop", [None, ARCHON_SHOP], ids=["rank", "cn-shop-search"])
def test_full_custom_nation_export_is_not_a_cost_oracle(shop: dict[str, Any] | None) -> None:
    rows = _rows(CN_EXPORT)
    assert len(rows) == 714
    assert sum("export_usd" in row["private_attributes"] for row in rows) == 711
    assert not any(private_key(key) for row in rows for key in row["attributes"])
    checked = asyncio.run(_oracle(rows, shop, strict=False))
    assert checked == len(_costs(rows))


NESTED = {
    "color": "BLACK",
    "stock": {"status": "in_stock", "qty": 3, "location": "Showroom", "lead": "today", "label": "Stock",
              "source": "Zephyr Group", "vendor": "Sample Direct", "usd": 437},
    "options": {"finish": {"BLACK": {"price": 18810, "zephyr_price": 437, "vendor_sku": "ZEPHYR-90101"}},
                "barrel": [{"code": "b-43", "label": "4.3in", "delta": 0, "sku": "", "vendor_sku": "ZEPHYR-B43",
                            "zephyr_price": 437}, "plain"],
                "export_usd": [437]},
    "defaults": {"finish": "BLACK", "supplier": "ZEPHYR", "cost": 437, "odd": {"vendor": "ZEPHYR"}},
    "price_history": [{"price": 18810, "buy": 437, "vendor": "ZEPHYR", "on": "2 Oct"}],
    "verified": [{"name": "thread", "value": "5/8x24", "source": "https://sample-arms.example/", "vendor": "ZEPHYR"},
                 {"name": "export_usd", "value": 437}, {"name": "Supplier cost", "value": 437},
                 ["export_usd", 437], "in stock",
                 # Round 3 shapes: spaced or prefixed names, no string name, the label in another field, bare pairs.
                 {"name": " export_usd", "value": 4377}, {"name": "POF export_usd", "value": 4377},
                 {"name": "Dealer Price", "value": 4377}, {"name": "Buy price", "value": 4377},
                 {"key": "export_usd", "value": 4377}, {"label": "export_usd", "value": 4377},
                 {"name": None, "value": 4377}, {"name": {"export_usd": 1}, "value": 4377},
                 {"name": ["export_usd"], "value": 4377}, {"name": "spec", "value": "export_usd 4377"},
                 {"name": "spec", "value": ["export_usd", 4377]}, {"name": "spec", "value": 4377, "source": "export_usd"},
                 {"name": "spec", "value": 4377, "note": "Dealer price"}, ["export_usd", 4377],
                 "export_usd: 4377", ["export_usd=4377"], 4377],
    "features": ["titanium", {"vendor": "ZEPHYR"}],
    "thread": {"vendor": "ZEPHYR"},
}


def test_nested_shapes_are_allowlisted() -> None:
    shown = shopper_attributes(NESTED)
    assert shown == {
        "color": "BLACK",
        "stock": {"status": "in_stock", "qty": 3, "location": "Showroom", "lead": "today", "label": "Stock"},
        "options": {"finish": {"BLACK": {"price": 18810}},
                    "barrel": [{"code": "b-43", "label": "4.3in", "delta": 0, "sku": ""}, "plain"]},
        "defaults": {"finish": "BLACK"},
        "price_history": [{"price": 18810, "on": "2 Oct"}],
        "verified": [{"name": "thread", "value": "5/8x24", "source": "https://sample-arms.example/"}],
        "features": ["titanium"],
    }
    text = json.dumps(shown)
    for word in ("ZEPHYR", "437", "vendor", "source\": \"ZEPHYR", "zephyr_price", "buy", "export", "Dealer"):
        assert word not in text, word
    # The archon catalogue's real shapes pass unchanged.
    archon = {"stock": {"status": "low_stock", "location": "Custom Nation showroom", "lead": "Collect today",
                        "label": "Demo stock", "qty": 1},
              "price_history": {"was": 25990, "amount": 24990, "on": "2 Oct", "label": "Demo data"},
              "options": {"optic_cut": ["RMR", "RMS"], "barrel": [{"code": "barrel-43", "label": "4.3\"", "delta": 0,
                                                                   "sku": ""}]},
              "defaults": {"barrel": "barrel-43", "optic_cut": "RMR"}}
    assert shopper_attributes(archon) == archon
    assert shopper_attributes(LABELLED) == {
        "stock": {"status": "in_stock"},
        "options": {"finish": [{"code": "black"}]},
        # Under a private label every text holding a number goes, a date too; a list carrying one goes whole.
        "price_history": [{}],
        "summary": "Sample pistol",
    }


# Nit B shapes: a private label beside a number outside ``verified``.
LABELLED = {
    "stock": {"label": "export_usd", "qty": 4377, "status": "in_stock"},
    "options": {"finish": [{"label": "export_usd", "price": 4377}, {"code": "black"}], "trim": ["export_usd", 4377]},
    "price_history": [{"label": "export_usd", "price": 4377, "on": "2 Oct"}],
    "features": ["export_usd", 4377],
    "in_box": ["Dealer price: 4377"],
    "summary": "Sample pistol",
    "detail": "export_usd: 4377",
}


@pytest.mark.parametrize("nested", ["nested", "labelled"])
@pytest.mark.parametrize("shop", [None, ARCHON_SHOP], ids=["rank", "cn-shop-search"])
def test_nested_private_keys_never_reach_shopper_routes_or_search(shop: dict[str, Any] | None, nested: str) -> None:
    planted = NESTED if nested == "nested" else LABELLED

    def nested_app(nested: dict[str, Any]) -> Any:
        app, rig, _echo = _app("legacy")

        async def nest() -> None:
            rows = {row["sku"]: row for row in await rig.store.products(TENANT)}
            await rig.store.upsert_product(
                TENANT, {**rows["90101"], "attributes": {**rows["90101"]["attributes"], **nested}})
            if shop is not None:
                async def _shop(tenant_id: str) -> dict[str, Any]:
                    del tenant_id
                    return shop
                rig._shop = _shop  # type: ignore[method-assign]

        asyncio.run(nest())
        return app

    # Control: the same row holding only the allowlisted nested shape.
    app = nested_app(planted)
    control_app = nested_app(shopper_attributes(planted))
    with TestClient(app) as client, TestClient(control_app) as control:
        detail = client.get("/v1/rig/products/90101", headers=HEADERS)
        assert detail.status_code == 200, detail.text
        _clean(detail.text)
        assert "vendor" not in detail.text and "zephyr_price" not in detail.text
        assert "4377" not in detail.text and "Dealer" not in detail.text
        for query in ("suppressor", "KX-9", "ZEPHYR", "vendor", "Sample Direct", "zephyr_price", "buy", "437",
                      "4377", "Dealer", "POF", "export_usd"):
            found = client.get("/v1/rig/search", params={"q": query}, headers=HEADERS)
            assert found.status_code == 200, found.text
            body = {key: value for key, value in found.json().items() if key != "parts"}  # parts echoes q
            _clean(json.dumps(body))
            assert "vendor_sku" not in json.dumps(body) and "zephyr_price" not in json.dumps(body)
            expected = control.get("/v1/rig/search", params={"q": query}, headers=HEADERS)
            assert _ids(found.json()) == _ids(expected.json()), query
            assert "4377" not in json.dumps(body), query
            if query in ("ZEPHYR", "vendor", "buy", "437", "4377", "Dealer", "POF"):
                assert "90101" not in _ids(found.json()), query


def test_allowlist_drops_unknown_keys_and_keeps_fit_facts() -> None:
    assert shopper_attributes({"export_usd": 437, "color": "BLACK", "thread": "5/8x24", "new_key": 1}) == {
        "color": "BLACK", "thread": "5/8x24"}
    assert shopper_attributes("not a dict") == {}
    assert not any(private_key(key) for key in SHOPPER_ATTRIBUTES), "an allowlisted key looks private"


def test_cost_filter_catches_export_and_pricing_keys_anywhere() -> None:
    for key in ("export_usd", "export", "exported", "EXPORT_ZAR", "unit_cost", "landed", "margin_pct", "markup",
                "profit", "wholesale_price", "purchase_price", "buy_price", "dealer_price", "fx", "fx_rate",
                "exchange_rate", "vat", "supplier"):
        assert private_key(key), key
    for key in ("color", "price", "price_label", "summary", "currency", "amount", "id"):
        assert not private_key(key), key
    nested = {"results": [{"price": {"amount": 1}, "attributes": {"stock": {"status": "in", "cost": 9},
                                                                  "export_usd": 437}}],
              "meta": {"export_usd": 1, "lines": [{"landed_zar": 2, "name": "x"}]}}
    assert shopper_body(nested) == {"results": [{"price": {"amount": 1}, "attributes": {"stock": {"status": "in"}}}],
                                    "meta": {"lines": [{"name": "x"}]}}


def test_private_pattern_breadth_is_deliberate() -> None:
    """These keys move to the private table too: hidden from shoppers, kept for the store.

    The pattern is broad on purpose (a missed cost key is a leak; a moved
    spec key is only hidden). Store-facing code must read them from
    product_private_attributes. Change this list only on purpose.
    """
    moved = ("heavy_duty", "duty_rating", "export_restricted", "itar_export", "supplier_warranty", "costume",
             "fx_rate", "exported")
    assert all(private_key(key) for key in moved)
    for key in ("calibre", "thread", "rail", "colour", "finish", "length", "weight"):
        assert not private_key(key), key


def test_schema_migration_uses_the_same_private_pattern() -> None:
    schema = (ROOT / "agents" / "rig" / "schema.sql").read_text()
    used = re.findall(r"~\* '([^']*)'", schema)
    assert len(used) == 4 and set(used) == {PRIVATE_KEY_PATTERN}


# ---- Postgres: the same oracle, plus the stored-row migration ----

def _pg_admin() -> str:
    for name in ("RIG_TEST_DATABASE_URL", "POOL_SCHEMA_DATABASE_URL"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    if os.environ.get("GITHUB_ACTIONS"):
        pytest.fail("POOL_SCHEMA_DATABASE_URL is not set")
    pytest.skip("POOL_SCHEMA_DATABASE_URL is not set")
    return ""


async def _with_pg(admin: str, body) -> None:
    import asyncpg
    from test_rig_postgres import _create_database, _database_url, _drop_database

    names = ["rig_cost_" + uuid4().hex[:12] for _ in range(2)]
    for name in names:
        await _create_database(admin, name)
    pools = []
    try:
        for name in names:
            pools.append(await asyncpg.create_pool(_database_url(admin, name), min_size=1, max_size=4))
        stores = [PgStore(pool) for pool in pools]
        for store in stores:
            await store.apply_schema()
        await body(stores, pools)
    finally:
        for pool in pools:
            await pool.close()
        for name in names:
            await _drop_database(admin, name)


def test_postgres_search_is_not_a_cost_oracle_and_migration_moves_costs() -> None:
    admin = _pg_admin()
    rows = _rows()

    async def body(stores: list[PgStore], pools: list[Any]) -> None:
        store, control = stores
        # Service search over Postgres rows that still carry the cost (pre-migration).
        for shop in (None, ARCHON_SHOP):
            assert await _oracle(rows, shop, store=store, control_store=control) == 6
        # The SQL search text (_SEARCH / _SEARCH_FTS) uses only allowlisted attributes.
        for cost, owners in _costs(rows).items():
            found = {row["sku"] for row in await store.search_rows(TENANT, cost, 24)}
            assert not found & set(owners), (cost, found)
        for word in SECRETS:
            assert await store.search_rows(TENANT, word, 24) == [], word
        assert {row["sku"] for row in await store.search_rows(TENANT, "BLACK", 24)} >= {"90101"}
        # Migration: schema.sql copies then strips. Run it twice: repeat-safe.
        pool = pools[0]
        async with pool.acquire() as conn:
            before = await conn.fetchval(
                "SELECT count(*) FROM agent_rig.products WHERE attributes ? 'export_usd'")
            assert before == 6
        # A stale private value (export_usd 1) loses to the value still in
        # attributes: that came from the newest import (re-import after a rollback).
        await store.upsert_product(TENANT, {**_legacy(rows[0]), "private_attributes": {"export_usd": 1}})
        async with pool.acquire() as conn:
            assert await store._log_cost_guard(conn) == 6
        await store.apply_schema()
        await store.apply_schema()
        async with pool.acquire() as conn:
            assert await conn.fetchval(
                "SELECT count(*) FROM agent_rig.products WHERE attributes ?| array['export_usd','supplier_cost',"
                "'landed_zar','markup_pct','wholesale']") == 0
            moved = {row["sku"]: json.loads(row["attributes"]) if isinstance(row["attributes"], str) else row["attributes"]
                     for row in await conn.fetch("SELECT sku, attributes FROM agent_rig.product_private_attributes")}
            colour = await conn.fetchval(
                "SELECT attributes->>'color' FROM agent_rig.products WHERE tenant_id=$1 AND sku='90101'",
                __import__("uuid").UUID(TENANT))
        assert set(moved) == {row["sku"] for row in rows}
        for row in rows:
            assert moved[row["sku"]] == {**row["private_attributes"], **EXTRA}, row["sku"]
        assert colour == "BLACK"
        async with pool.acquire() as conn:
            assert await store._log_cost_guard(conn) == 0
        # Import path on Postgres: the cost goes to the private table, not attributes.
        await store.upsert_product(TENANT, rows[1])
        assert await store.product_private_attributes(TENANT, rows[1]["sku"]) == rows[1]["private_attributes"]
        assert "export_usd" not in next(r for r in await store.products(TENANT) if r["sku"] == rows[1]["sku"])["attributes"]
        # Deleting the product deletes its private row.
        async with store.atomic(TENANT) as locked:
            await locked.delete_products(TENANT, [rows[1]["sku"]])
        assert await store.product_private_attributes(TENANT, rows[1]["sku"]) == {}

    asyncio.run(_with_pg(admin, body))


# Fuzz: many spellings of a private name, in every place a store could put one.
_CANARY = 4377
_PRIVATE_WORDS = ("export_usd", "dealer price", "buy price", "unit cost", "supplier", "wholesale", "landed",
                  "markup", "margin", "purchase price", "trade price", "profit", "duty")


def _spellings(word: str) -> set[str]:
    parts = word.split()
    if len(parts) == 1:
        parts = word.split("_")
    camel = parts[0].lower() + "".join(part.title() for part in parts[1:])
    joined = {sep.join(parts) for sep in ("_", "-", ".", " ", "  ", "/")}
    out = set()
    for base in joined | {camel}:
        for variant in (base, base.upper(), base.title(), f" {base}", f"{base} ", f"POF {base}",
                        f"{base} (ZAR)", f"Sample_{base}", f"{base}:"):
            out.add(variant)
    # Glued camelCase prefixes ("pofExportUsd", "POFExportUsd"), and an invisible character inside the word
    # (zero-width space, soft hyphen, zero-width joiner) or fullwidth letters.
    glued = camel[0].upper() + camel[1:]
    out |= {f"pof{glued}", f"POF{glued}", f"net{glued}"}
    for base in ("_".join(parts), " ".join(parts).title()):
        out |= {base[:2] + mark + base[2:] for mark in ("\u200b", "\u00ad", "\u200d")}
        out.add("".join(chr(ord(ch) + 0xFEE0) if "!" <= ch <= "~" else ch for ch in base))
    return out


_FULLWIDTH_K = "".join(chr(ord(ch) + 0xFEE0) for ch in str(_CANARY))
_ARABIC_K = "".join(chr(0x0660 + int(ch)) for ch in str(_CANARY))


def _visible(shown: str) -> str:
    """What a shopper reads: fullwidth folded, every digit script as 0-9, separators gone."""
    text = "".join(ch for ch in unicodedata.normalize("NFKC", shown) if unicodedata.category(ch) != "Cf")
    text = "".join(str(unicodedata.digit(ch)) if unicodedata.digit(ch, None) is not None else ch for ch in text)
    return re.sub(r"[\s,.'\u2019_\u066b\u066c-]", "", text)


def _fuzz_shapes(name: Any) -> list[dict[str, Any]]:
    k = _CANARY
    url = "https://sample-arms.example/"
    if not isinstance(name, str):  # a missing or non-string name: it can't be screened, so the fact goes
        return [{"verified": [{"name": name, "value": k, "source": url}]},
                {"verified": [{"name": name, "value": [k]}, {"value": k}]}]
    return [
        {"verified": [{"name": name, "value": k, "source": url}]},
        {"verified": [{"name": "spec", "value": [name, k]}]},
        {"verified": [{"name": "spec", "value": k, "source": name}]},
        {"verified": [{"name": "spec", "value": k, "note": name}]},
        {"verified": [{"key": name, "value": k}, {"label": name, "value": k}, {"value": k}]},
        {"verified": [[name, k], f"{name}: {k}", [f"{name}={k}"], k]},
        {"verified": {"name": name, "value": k}},
        {"verified": f"{name} {k}"},
        {"options": {"finish": [{"label": name, "price": k}], "trim": [name, k], name: [k]}},
        {"options": {"finish": {name: {"price": k}}}},
        {"defaults": {name: k}},
        {"stock": {"label": name, "qty": k}},
        {"price_history": [{"label": name, "price": k}, {"on": name, "amount": k}]},
        {"price_history": {"label": name, "was": k}},
        {"features": [name, k]},
        {"in_box": [f"{name}: {k}"]},
        {"detail": f"{name}: {k}"},
        # Round 4: the name %-quoted in a source query, and amounts written as text beside a private label.
        {"verified": [{"name": "spec", "value": 1, "source": f"{url}p?{quote(name)}={k}"}]},
        {"price_history": [{"label": name, "price": f"R {k:,}.00"}, {"label": name, "price": f"USD {k}"}]},
        {"options": {"finish": [{"code": "x", "label": name, "price": f"ZAR{k}"}], "trim": [name, str(k)]}},
        {"stock": {"status": name, "qty": f"R{k}"}},
        {"features": [name, str(k)]},
        {"size": [name, f"R{k}"]},
        # Round 5: trailing currency, apostrophe and NBSP separators, fullwidth and Arabic-Indic digits.
        {"stock": {"status": name, "qty": f"{k} ZAR"}},
        {"price_history": [{"label": name, "price": f"{k:,} USD"}, {"label": name, "price": "4'377"}]},
        {"features": [name, f"{k}ZAR"]},
        {"stock": {"status": name, "qty": "R\u00a04\u00a0377"}},
        {"features": [name, _FULLWIDTH_K]},
        {"options": {"finish": [{"code": "x", "label": name, "price": f"USD{_FULLWIDTH_K}"}], "trim": [name, _ARABIC_K]}},
        {"stock": {"status": f"{name} {_FULLWIDTH_K}"}},
        {"detail": f"{name}: {_ARABIC_K}"},
    ]


def test_fuzz_private_names_never_leak_a_canary() -> None:
    names: list[Any] = sorted({spelling for word in _PRIVATE_WORDS for spelling in _spellings(word)})
    names += [None, 1, 2.5, True, ["export_usd"], {"name": "export_usd"}]
    checked = 0
    for name in names:
        for shape in _fuzz_shapes(name):
            shown = json.dumps(shopper_attributes(shape), ensure_ascii=False)
            assert str(_CANARY) not in _visible(shown), (name, shape, shown)
            checked += 1
    assert checked > 2000, checked


def test_fuzz_safe_names_and_archon_facts_pass_unchanged() -> None:
    url = "https://sample-arms.example/"
    for name in ("thread", "Thread pitch", "optic_cuts", "weight_oz", "Locking note", "in box", "Sold separately",
                 "Barrel length", "listed", "rail", "grip"):
        fact = {"name": name, "value": "5/8x24", "source": url}
        assert shopper_attributes({"verified": [fact]}) == {"verified": [fact]}, name
        assert shopper_attributes({"verified": [{**fact, "value": [12, 15]}]})["verified"] == [{**fact, "value": [12, 15]}]
    facts = 0
    with (ROOT / "agents" / "rig" / "catalogues" / "archon" / "products.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            attributes = json.loads(row.get("attributes") or "{}")
            verified = attributes.get("verified")
            if verified:
                assert shopper_attributes({"verified": verified}) == {"verified": verified}, row["sku"]
                facts += len(verified)
            shown = shopper_attributes(attributes)
            for key, value in attributes.items():
                if key in shown:
                    assert shown[key] == value, (row["sku"], key)
    assert facts == 35, facts


def test_cost_guard_warns_when_forced_rls_hides_every_row() -> None:
    """A startup migration under forced RLS sees no rows: the log line says so at WARNING."""
    admin = _pg_admin()
    rows = _rows()

    async def body(stores: list[PgStore], pools: list[Any]) -> None:
        store, pool = stores[0], pools[0]
        await _load(store, rows[:2], "legacy")
        records: list[logging.LogRecord] = []

        class _Keep(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)

        handler = _Keep(level=logging.DEBUG)
        logger = logging.getLogger("rigbox.store")
        logger.addHandler(handler)
        old_level = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            async with pool.acquire() as conn:
                assert not await PgStore._rls_hides_rows(conn)  # superuser: no RLS in the way
                role = "rig_rls_" + uuid4().hex[:8]
                async with conn.transaction():  # rolled back: role, grants and RLS go with it
                    await conn.execute(f"CREATE ROLE {role}")
                    await conn.execute(f"GRANT USAGE ON SCHEMA agent_rig TO {role}")
                    await conn.execute(f"GRANT SELECT ON agent_rig.products TO {role}")
                    await conn.execute("ALTER TABLE agent_rig.products ENABLE ROW LEVEL SECURITY")
                    await conn.execute("ALTER TABLE agent_rig.products FORCE ROW LEVEL SECURITY")
                    await conn.execute(f"SET LOCAL ROLE {role}")
                    assert await PgStore._rls_hides_rows(conn)
                    records.clear()
                    assert await store._log_cost_guard(conn) == 0
                    assert [r.levelno for r in records] == [logging.WARNING, logging.WARNING], records
                    assert "row-level security" in records[1].getMessage()
                records.clear()
                assert await store._log_cost_guard(conn) > 0  # legacy rows still carry the cost
                assert all("row-level security" not in r.getMessage() for r in records)
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)

    asyncio.run(_with_pg(admin, body))


def _in_script(zero: int) -> str:
    return "".join(chr(zero + int(ch)) for ch in str(_CANARY))


# The canary written every way a shopper could still read it: digit scripts, compatibility forms,
# separators, currency marks, signs, scientific notation, suffixes and invisible characters.
_AMOUNT_FORMS = (
    "4377", "4,377", _in_script(0xFF10), _in_script(0x0660), _in_script(0x06F0), _in_script(0x0966),
    _in_script(0x09E6), _in_script(0x0E50), _in_script(0x1D7CE), _in_script(0x1D7F6), _in_script(0x2775),
    "\u2074\u00b3\u2077\u2077", "\u2084\u2083\u2087\u2087", "\u2463\u2462\u2466\u2466",
    "4\u202f377", "4\u2009377", "4\u00a0377", "4\u066c377", "4377\u066b00", "4_377", "4'377", "4.377,00",
    "$4,377", "R4377", "R 4 377,00", "\u20ac4.377", "4 377 \u20ac", "\u00a34377", "US$4,377", "USD 4,377.00",
    "4377 ZAR", "4377 zar", "4377 rand", "\u00a54377", "\u20b94,377", "-4377", "\u22124377", "(4377)",
    "(R 4,377.00)", "-R4,377", "+4377", "~4377", "4.377e3", "4.377E+03", "4.377\u00d710\u00b3", "4377/ea", "4377k",
    "43\u200b77", "43\u00ad77", "R\uff14,\uff13\uff17\uff17", "approximately R4377", "\u2163\u2162\u2166\u2166",
)


def _amount_shapes(name: str, amount: str) -> list[dict[str, Any]]:
    return [
        {"stock": {"label": name, "qty": amount, "status": "in_stock"}},
        {"stock": {"status": name, "qty": amount}},
        {"stock": {"status": f"{name} {amount}"}},
        {"stock": {"location": name, "qty": amount}},
        {"price_history": [{"label": name, "price": amount, "on": "2 Oct"}, {"on": name, "amount": amount}]},
        {"price_history": [{"on": f"{name} {amount}"}]},
        {"price_history": {"label": name, "was": amount}},
        {"options": {"finish": [{"code": "x", "label": name, "price": amount}], "trim": [name, amount]}},
        {"options": {"finish": {"BLACK": {"label": name, "price": amount}}}},
        {"features": [name, amount]},
        {"size": [name, amount]},
        {"in_box": [f"{name}: {amount}", f"{name} {amount}"]},
        {"detail": f"{name}: {amount}"},
        {"detail": f"{name} = {amount}"},
        {"verified": [{"name": name, "value": amount}, {"name": "spec", "value": amount, "note": name}]},
    ]


def test_amounts_in_any_script_or_form_beside_a_private_label_never_show() -> None:
    checked = 0
    for name in ("export_usd", "Dealer price", "pofExportUsd", "Ｍarkup", "unit cost"):
        for amount in _AMOUNT_FORMS:
            for shape in _amount_shapes(name, amount):
                shown = json.dumps(shopper_attributes(shape), ensure_ascii=False)
                assert str(_CANARY) not in _visible(shown), (name, amount, shape, shown)
                checked += 1
    assert checked == 5 * len(_AMOUNT_FORMS) * 15, checked


def test_a_provenance_location_is_display_copy_and_keeps_qty() -> None:
    # "Supplier warehouse" is a real archon stock location: it labels nothing, and stays.
    stock = {"status": "in_stock", "location": "Supplier warehouse", "qty": 3, "lead": "ETA 3-4 weeks"}
    assert shopper_attributes({"stock": stock}) == {"stock": stock}
    # A pricing word in the location does label the numbers.
    assert shopper_attributes({"stock": {"location": "Dealer price", "qty": 4377, "lead": "4377"}}) == {
        "stock": {"location": "Dealer price"}}
    assert shopper_attributes({"stock": {"location": "export_usd 4377", "qty": 2}}) == {"stock": {}}
    # Every pricing word is also a private key, so the location rule never shows a key the strip would move.
    for word in ("cost", "duty", "margin", "landed", "markup", "profit", "wholesale", "export", "buy_price",
                 "purchase_price", "dealer_price", "trade_price", "vat", "fx", "exchange_rate", "pricing_rule"):
        assert private_key(word) and _PRICING.search(word), word


_TEXT_KEYS = ("detail", "summary", "tagline")


def test_every_private_pair_in_free_text_is_hidden() -> None:
    # Any clause, a leading list number or "_", a word before the amount, Roman numerals (NFKC folds them to letters).
    for text in (
        "Weight: 2 kg; Dealer price: 4377",
        "Weight: 2 kg, Dealer price: 4377",
        "Weight: 2 kg\nexport_usd = 4377",
        "Weight: 2 kg \u2022 Dealer price: R 4,377.00",
        "Weight: 2 kg | unit cost: 4377",
        "1. Dealer price: 4377",
        "_export_usd: 4377",
        "Dealer price: approximately R4377",
        "Dealer price: \u2163\u2162\u2166\u2166",
        "Dealer price, approx: 4377",
        "\uff22\uff55\uff59 \uff30\uff52\uff49\uff43\uff45: 4377",
    ):
        for key in _TEXT_KEYS:
            assert shopper_attributes({key: text}) == {}, (key, text)
        # In a list the private item carries its amount, so the list goes whole.
        assert shopper_attributes({"in_box": ["Pistol", text]}) == {}, text


def test_free_text_without_a_private_pair_is_kept() -> None:
    for text in (
        "Ships in: 3 days, Warranty = 5 years",
        "Thread: 1/2x28; Rail: 1913 Picatinny",
        "Weight: 680 g; Capacity: 17 rounds \u2022 Gen \u2163",
        "Heavy duty frame. Supplier warranty included.",
        "1. Steel slide; 2. Polymer frame",
    ):
        for key in _TEXT_KEYS:
            assert shopper_attributes({key: text}) == {key: text}, (key, text)


def test_a_private_word_beside_ordinary_copy_keeps_the_list() -> None:
    # A private word labels an amount, not copy: these lists are kept whole.
    for items in (
        ["Heavy duty", "2-year warranty"],
        ["Supplier warranty card", "2 magazines"],
        ["Heavy-duty rail", "Holds 17 rounds", "Black"],
        ["Heavy duty", "Pack of 50", "Gen 5"],
    ):
        for key in ("features", "in_box", "included"):
            assert shopper_attributes({key: items}) == {key: items}, (key, items)
    # Beside an amount (a number, a short or currency-marked string) or carrying one, the list goes.
    for items in (
        ["Dealer price", 4377],
        ["Dealer price", "4377 rand"],
        ["Dealer price", "USD 4,377.00 each"],
        ["Dealer price", "approximately R4377"],
        ["Heavy duty", "\u20ac4377 value"],
        ["Black", "Dealer price 4377"],
        ["Dealer price", "99 per unit"],
        ["Dealer price", "\u2163\u2162\u2166\u2166"],
        ["Dealer price", "\u56db\u5343\u4e09\u767e\u4e03\u5341\u4e03"],
        ["Dealer price", "NDM3Nw=="],
        # Copy with a long number beside a private word stays on the safe side.
        ["Heavy duty", "1913 Picatinny"],
    ):
        for key in ("features", "in_box", "included"):
            assert shopper_attributes({key: items}) == {}, (key, items)


def test_a_short_amount_with_a_word_beside_a_private_word_drops_the_list() -> None:
    # #529 review: a 1-2 digit amount next to an ordinary word is still the labelled amount.
    for items in (
        ["Dealer price", "85 total"], ["Cost", "85 AUD"], ["Landed", "85 bucks"], ["Supplier cost", "was 85"],
        ["Dealer price", "4.4 thousand"], ["Cost", "43 hundred"], ["Trade price", "44k total"], ["Cost", "85/box"],
        ["Wholesale", "85 rands"], ["export_usd", "85 nett"], ["Cost", "85 apiece"], ["Dealer price", "\u2078\u2075 total"],
        ["Dealer price", "43 hundred", "77 total"], ["85 total", "Supplier cost"],
    ):
        for key in ("features", "in_box", "included"):
            assert shopper_attributes({key: items}) == {}, (key, items)
        assert shopper_attributes({"options": {"trim": items}}) == {"options": {}}, items


def test_an_amount_after_a_break_following_the_separator_is_held() -> None:
    # be5300de held these (its amount window crossed the break); #529's clause split must not show them.
    for text in ("Dealer price:\n4377", "Dealer price:\r\n4377", "Dealer price =\n4377", "Cost:\nR4377",
                 "export_usd:\n4377", "Dealer price: \u2022 4377", "Dealer price: | 4377", "Dealer price:; 4377",
                 "Dealer price:\u00b74377", "Weight: 2 kg; Dealer price:\n4377"):
        for key in ("detail", "summary", "tagline"):
            assert "4377" not in json.dumps(shopper_attributes({key: text})), (key, text)
    # A private name's own clause with no number does not reach into the next clause.
    for text in ("Heavy duty: yes; Weight: 2 kg", "Supplier warranty: yes\nWeight: 680 g"):
        assert shopper_attributes({"detail": text}) == {"detail": text}, text


def test_copy_phrases_count_only_in_ascii_digits_beside_a_private_word() -> None:
    # A copy phrase is ASCII digits as written: Roman, fullwidth, Arabic-Indic, superscript or zero-width forms
    # of the same phrase still count as the labelled amount, and so do Roman numerals before a plain word.
    for amount in ("\u2167\u2165 total", "\u2167\u2165 AUD", "was \u2167\u2165", "\u2167\u2165 in stock",
                   "\u2167\u2165 rounds", "\uff18\uff15 rounds", "\u0668\u0665 magazines", "\u2078\u2075 days",
                   "8\u200b5 rounds", "Holds 8\u200b5 rounds", "Pack of \uff18\uff15", "Gen \u2167"):
        for key in ("features", "in_box", "included"):
            assert shopper_attributes({key: ["Dealer price", amount]}) == {}, (key, amount)
    for items in (["Heavy duty", "2-year warranty"], ["Supplier warranty card", "2 magazines"],
                  ["Heavy duty", "Pack of 50", "Gen 5"]):
        assert shopper_attributes({"features": items}) == {"features": items}, items


_LINE_BREAKS = ("\r", "\v", "\f", "\x85", "\u2028", "\u2029")


def test_a_second_pair_after_any_line_break_is_hidden() -> None:
    # A lone CR, VT, FF, NEL, LS or PS starts a clause like "\n" does; be5300de and #529 showed the second pair.
    for br in _LINE_BREAKS:
        for text in (f"Weight: 2 kg{br}Dealer price: 4377", f"Finish: black{br}Cost = R4377",
                     f"Weight: 2 kg{br}1. export_usd: 4377", f"Colour: black{br}Supplier cost: 4377 AUD",
                     f"Weight: 2 kg{br}Dealer price, approx: 4377", f"Weight: 2 kg{br}Dealer price:{br}4377"):
            for value in ({"detail": text}, {"summary": text}, {"tagline": text}):
                assert "4377" not in json.dumps(shopper_attributes(value)), (value, br)


def test_a_second_pair_after_any_line_break_is_hidden_inside_lists() -> None:
    for br in _LINE_BREAKS:
        text = f"Weight: 2 kg{br}Dealer price: 4377"
        for value in ({"features": [text]}, {"in_box": ["Black", text]}, {"features": ["Heavy duty", text]},
                      {"options": {"trim": [text]}}):
            assert "4377" not in json.dumps(shopper_attributes(value)), (value, br)


def test_text_split_by_any_line_break_without_a_private_pair_is_kept() -> None:
    for br in _LINE_BREAKS:
        for text in (f"Weight: 2 kg{br}Colour: black", f"Heavy duty: yes{br}Colour: black",
                     f"Supplier warranty: yes{br}Finish: black", f"Holds 17 rounds{br}Finish: black"):
            assert shopper_attributes({"detail": text}) == {"detail": text}, (text, br)
