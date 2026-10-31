"""Private pricing inputs in catalogue attributes never reach a shopper.

Fixture rows are six real Custom Nation POF USA catalogue rows
(tests/fixtures/rig/pof-usa-cost-guard.csv, taken from the 714-row export).
Each carries ``attributes.export_usd`` (the supplier's export price), the
leak this guards against. Every shopper route on /v1/rig is exercised.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

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
from rigbox.service import RecordingHandoff  # noqa: E402
from rigbox.shopper_attributes import SHOPPER_ATTRIBUTES, shopper_attributes  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "rig" / "pof-usa-cost-guard.csv"
HEADERS = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
CONTACT = {"name": "Sample Shopper", "email": "shopper@example.com"}
SECRETS = ("export_usd", "supplier_cost", "landed_zar", "markup_pct", "wholesale", "internal_note")


class Echo:
    """A model that tries to repeat every attribute it was shown."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> str:
        del tenant_id, task_type
        self.prompts.append(messages[-1]["content"])
        return json.dumps({"answer": "The export_usd is 606.", "cites": ["02445"]})


def _rows() -> list[dict[str, Any]]:
    parsed = parse_products_csv(FIXTURE.read_text())
    assert parsed["rejected"] == [] and len(parsed["rows"]) == 6
    assert all("export_usd" in row["attributes"] for row in parsed["rows"])
    return parsed["rows"]


def _app() -> tuple[FastAPI, QuoteService, Echo]:
    async def ready() -> tuple[QuoteService, Echo]:
        store = MemoryStore()
        await seed(store)
        for row in _rows():
            # Add other private-looking keys a store might also import.
            row["attributes"].update({"supplier_cost": 1, "landed_zar": 2, "markup_pct": 3,
                                      "wholesale": 4, "internal_note": "buy from RSR"})
            await store.upsert_product(TENANT, row)
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
    assert "606" not in text  # 02445's export_usd value


def test_main_shopper_routes_never_return_export_usd() -> None:
    app, rig, echo = _app()
    with TestClient(app) as client:
        found = client.get("/v1/rig/search?q=suppressor", headers=HEADERS)
        assert found.status_code == 200 and found.json()["results"], found.text
        _clean(found.text)
        first = found.json()["results"][0]
        # Shopper-safe attributes still pass.
        assert first["attributes"].get("color") == "BLACK"
        for sku in ("02445", "02450", "01235"):
            detail = client.get(f"/v1/rig/products/{sku}", headers=HEADERS)
            assert detail.status_code == 200, detail.text
            _clean(detail.text)
        for path, body in (("/v1/rig/compare", {"product_ids": ["02445", "02450"]}),
                           ("/v1/rig/setups", {"product_id": "02445"})):
            response = client.post(path, headers=HEADERS, json=body)
            if response.status_code == 200:
                _clean(response.text)
        asked = client.post("/v1/rig/ask", headers=HEADERS,
                            json={"product_id": "02445", "question": "What does the PST-7 suppressor cost?"})
        assert asked.status_code == 200, asked.text
        _clean(asked.text)
        for prompt in echo.prompts:
            _clean(prompt)
        product = client.get("/v1/rig/products/02445", headers=HEADERS).json()
        setup = {"centre": product, "parts": [{"role": "Item", "product": product}]}
        quote = client.post("/v1/rig/quote", headers=HEADERS, json={"setup": setup, "contact": CONTACT})
        assert quote.status_code in {200, 422}, quote.text
        _clean(quote.text)
    # The store's own copy of the quote (handoff to its inbox/Odoo) may keep its
    # own pricing inputs; it is store-facing. The email letter lists only id,
    # name, amount, price label and stock per item.
    for sent in rig.handoff.sent:
        if sent.get("letter"):
            _clean(json.dumps(sent["letter"], default=str))


def test_allowlist_drops_unknown_keys_and_keeps_fit_facts() -> None:
    assert shopper_attributes({"export_usd": 606, "color": "BLACK", "thread": "5/8x24", "new_key": 1}) == {
        "color": "BLACK", "thread": "5/8x24"}
    assert shopper_attributes("not a dict") == {}
    assert not any(private_key(key) for key in SHOPPER_ATTRIBUTES), "an allowlisted key looks private"


def test_cost_filter_catches_export_and_pricing_keys_anywhere() -> None:
    for key in ("export_usd", "export", "EXPORT_ZAR", "unit_cost", "landed", "margin_pct", "markup",
                "profit", "wholesale_price", "purchase_price", "buy_price", "dealer_price", "fx", "fx_rate",
                "exchange_rate", "vat", "supplier"):
        assert private_key(key), key
    for key in ("color", "price", "price_label", "summary", "exported", "currency", "amount", "id"):
        assert not private_key(key) or key == "exported", key
    nested = {"results": [{"price": {"amount": 1}, "attributes": {"stock": {"status": "in", "cost": 9},
                                                                  "export_usd": 606}}],
              "meta": {"export_usd": 1, "lines": [{"landed_zar": 2, "name": "x"}]}}
    assert shopper_body(nested) == {"results": [{"price": {"amount": 1}, "attributes": {"stock": {"status": "in"}}}],
                                    "meta": {"lines": [{"name": "x"}]}}
