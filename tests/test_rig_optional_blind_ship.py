"""Optional blind ship: Locate orders ship from the other store straight to the shopper.

Per-store ``blind_ship`` switch, off by default. Per-source
``neutral_slip_required``. The shopper's delivery address goes on the
sale.order; Odoo's Dropship route drafts the supplier PO to that address; no
supplier identity reaches the shopper. Offline here, except the Postgres test
(RIG_TEST_DATABASE_URL) and the Odoo 17 sandbox test (RIG_TEST_ODOO_SANDBOX).
"""
import asyncio
import csv
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox.api import mount
from rigbox.locate import SupplyStore
from rigbox.locate_live import confirm
from rigbox.quotes.api import mount as mount_quotes
from rigbox.quotes.sample import KEY, TENANT as SAMPLE, seed
from rigbox.quotes.senders import BLIND_INSTRUCTION, DeliveryError, OdooHandoff, sandbox_orders
from rigbox.quotes.service import QuoteService, ship_address
from rigbox.quotes.store import MemoryQuotes
from rigbox.retailer import Retailer
from rigbox.service import RigError, Service
from rigbox.store import MemoryStore
from test_rig_locate_checkout import TENANT, FakeProvider, Live, available, rate_stub, shop

ADDRESS = {"name": "Thandi Mokoena", "street": "12 Long Street", "city": "Cape Town", "zip": "8001",
           "state": "Western Cape", "country": "za", "phone": "+27 21 000 0000"}
SUPPLIER = ("other-store", "other.example", "RSR|POF00307", "RSR", "/product/cam-pin")


class BlindOrders:
    """Test double for the retailer's sandbox Odoo; records the ship argument."""

    def __init__(self, fail=False):
        self.sent, self.placed, self.fail = [], [], fail

    async def send(self, *, tenant_id, email, webhook, quote):
        self.sent.append(quote)

    async def place_located_order(self, *, tenant_id, quote_id, located, ship=None):
        sandbox_orders()
        if self.fail:
            raise DeliveryError("odoo_rejected")
        self.placed.append({"quote_id": quote_id, "source": located["source"], "ship": ship})
        return {"sale_order": {"name": "S00001", "state": "sale"},
                "purchase_order": {"name": "P00001", "state": "draft", "dropship": ship is not None}}


def env(monkeypatch):
    monkeypatch.setenv("RIG_LOCATE_HOLD_SECRET", "s" * 40)
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "test")
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)


async def blind_shop(monkeypatch, *, blind=True, neutral=True, fail=False):
    env(monkeypatch)
    store = await rate_stub(await shop())
    await store.put_retailer(TENANT, "shop", "shop@example.com", None, "Shop", blind_ship=blind)
    await SupplyStore(store).source(TENANT, dict(id="other-store", approved=True, priority=1,
        max_offer_age_seconds=3600, provider="tiger", site="https://other.example", neutral_slip_required=neutral))
    orders = BlindOrders(fail)
    service = QuoteService(store, None, orders, MemoryQuotes(store))
    service.locate_checker = Live(available("45.00"))
    service.payments = FakeProvider()
    held = await service.locate_confirm(TENANT, "part-1")
    body = {"product_id": "part-1", "hold": held["hold"], "payment_token": "tok_test_visa",
            "contact": {"name": "Thandi Mokoena", "email": "thandi@example.com"}, "delivery": dict(ADDRESS)}
    return store, service, orders, held, body


# 1. Switches: off by default, explicit booleans, persisted.

@pytest.mark.asyncio
async def test_blind_ship_is_off_by_default_and_settings_need_a_boolean():
    store = await rate_stub(await shop())
    assert (await store.retailer(TENANT))["blind_ship"] is False
    retailer = Retailer(Service(store))
    base = {"name": "Shop", "email": "shop@example.com"}
    for bad in ("true", 1, None):
        with pytest.raises(ValueError):
            await retailer.set_settings(TENANT, {**base, "blind_ship": bad})
    await retailer.set_settings(TENANT, {**base, "blind_ship": True})
    assert (await retailer.panel(TENANT))["settings"]["blind_ship"] is True
    await retailer.set_settings(TENANT, base)  # absent keeps the saved value
    assert (await retailer.panel(TENANT))["settings"]["blind_ship"] is True
    await store.put_retailer(TENANT, "shop", "a@example.com", None, "Shop", locate_enabled=False)
    assert (await store.retailer(TENANT))["blind_ship"] is True
    await retailer.set_settings(TENANT, {**base, "blind_ship": False})
    assert (await retailer.panel(TENANT))["settings"]["blind_ship"] is False


@pytest.mark.asyncio
async def test_neutral_slip_flag_is_per_source_boolean_and_reaches_the_private_hold():
    store = await rate_stub(await shop())
    supply = SupplyStore(store)
    base = dict(id="other-store", approved=True, priority=1, max_offer_age_seconds=3600, provider="tiger",
                site="https://other.example")
    with pytest.raises(ValueError):
        await supply.source(TENANT, {**base, "neutral_slip_required": "yes"})
    sources, _, _ = await supply.snapshot(TENANT)
    assert sources[0]["neutral_slip_required"] is False  # default
    await supply.source(TENANT, {**base, "neutral_slip_required": True})
    result = await confirm(store, TENANT, (await store.products(TENANT))[0], Live(available()), secret=b"t" * 40)
    assert result["store"]["source"]["neutral_slip_required"] is True
    assert "neutral_slip_required" not in json.dumps(result["public"])


def test_ship_address_is_strict():
    assert ship_address(ADDRESS)["country"] == "ZA"
    for bad in (None, "12 Long Street", {**ADDRESS, "country": "ZAF"}, {**ADDRESS, "street": ""},
                {**ADDRESS, "zip": None}, {**ADDRESS, "city": "x" * 121}, {**ADDRESS, "name": "a\r\nBcc: x"},
                {**ADDRESS, "company": "x"}, {**ADDRESS, "street": 12}):
        with pytest.raises(RigError) as raised:
            ship_address(bad)
        assert raised.value.status == 422


# 2. Accept with blind ship.

@pytest.mark.asyncio
async def test_blind_accept_sends_the_shopper_address_and_neutral_flag_to_the_order(monkeypatch):
    store, service, orders, held, body = await blind_shop(monkeypatch)
    result = await service.locate_accept(TENANT, body)
    assert result["state"] == "ordered" and result["ships_direct"] is True
    [placed] = orders.placed
    assert placed["ship"] == {"address": {**ADDRESS, "country": "ZA"}}
    assert placed["source"]["neutral_slip_required"] is True
    quote = next(q for q in store.quotes if q["id"] == result["request_id"])
    assert quote["payload"]["ship_to"]["city"] == "Cape Town"
    assert quote["payload"]["locate_state"]["blind_ship"] is True


@pytest.mark.asyncio
async def test_blind_accept_without_address_refuses_before_hold_or_payment(monkeypatch):
    store, service, orders, held, body = await blind_shop(monkeypatch)
    for delivery in (None, {**ADDRESS, "street": ""}):
        with pytest.raises(RigError) as raised:
            await service.locate_accept(TENANT, {**body, "delivery": delivery})
        assert raised.value.status == 422
    assert service.payments.captured == [] and orders.sent == [] and orders.placed == []
    hold_id = held["hold"].split(".")[0]
    assert store.supply_state[TENANT]["holds"][hold_id]["used_at"] is None
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"


@pytest.mark.asyncio
async def test_switch_off_keeps_the_existing_ship_to_store_order(monkeypatch):
    store, service, orders, held, body = await blind_shop(monkeypatch, blind=False)
    result = await service.locate_accept(TENANT, body)
    assert result["state"] == "ordered" and "ships_direct" not in result
    assert orders.placed[0]["ship"] is None
    assert "ship_to" not in store.quotes[-1]["payload"]


@pytest.mark.asyncio
async def test_blind_order_failure_refunds(monkeypatch):
    store, service, orders, _, body = await blind_shop(monkeypatch, fail=True)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "order_failed_refunded"
    assert service.payments.refunded == ["order_failed"]


# 3. Shopper HTTP responses: no supplier identity, no export_usd (real POF rows).

def pof_row(sku):
    with (ROOT / "tests" / "fixtures" / "rig" / "pof-usa-cost-guard.csv").open(encoding="utf-8") as handle:
        row = next(r for r in csv.DictReader(handle) if r["sku"] == sku)
    attributes = {**json.loads(row["attributes"]), "stock": {"status": "out_of_stock"}}
    return dict(sku=sku, id=sku, gtin=row["gtin"], name=row["name"], brand=row["brand"], category=row["category"],
                price=row["price"], currency=row["currency"], image_url=row["image_url"], active=True,
                attributes=attributes)


def test_locate_confirm_accept_responses_have_no_supplier_or_export_usd(monkeypatch):
    env(monkeypatch)

    async def ready():
        store = MemoryStore()
        await seed(store)
        await store.upsert_product(SAMPLE, pof_row("02445"))
        await store.save_rule(SAMPLE, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
        retailer = await store.retailer(SAMPLE)
        await store.put_retailer(SAMPLE, retailer["slug"], retailer["email"], retailer["webhook"], retailer["name"],
                                 locate_enabled=True, blind_ship=True)
        await SupplyStore(store).source(SAMPLE, dict(id="other-store", approved=True, priority=1,
            max_offer_age_seconds=3600, provider="tiger", site="https://other.example", neutral_slip_required=True))
        from datetime import datetime, timezone
        store.supply_state[SAMPLE]["offers"] = [dict(
            tenant_id=SAMPLE, source_id="other-store", sku="RSR|POF02445", gtin="847313024459", brand="POF-USA",
            mpn=None, quantity="1", status="available", eta="2026-11-20", ship_days=8, region="US",
            cost="606", currency="USD", seen_at=datetime.now(timezone.utc),
            url="https://other.example/product/cam-pin/")]
        await rate_stub(store)
        service = QuoteService(store, None, BlindOrders(), MemoryQuotes(store))
        service.locate_checker = Live(available("606.00"))
        service.payments = FakeProvider()
        return service

    app = FastAPI()
    app.state.rig = asyncio.run(ready())
    mount(app)
    mount_quotes(app)
    headers = {"X-Rig-Key": KEY, "Origin": "http://127.0.0.1:8001"}
    with TestClient(app) as client:
        located = client.post("/v1/rig/locate", json={"product_id": "02445"}, headers=headers)
        held = client.post("/v1/rig/locate/confirm", json={"product_id": "02445"}, headers=headers)
        product = client.get("/v1/rig/products/02445", headers=headers)
        assert located.status_code == held.status_code == product.status_code == 200, (located.text, held.text)
        assert held.json()["status"] == "available_to_order"
        accepted = client.post("/v1/rig/locate/accept", headers=headers, json={
            "product_id": "02445", "hold": held.json()["hold"], "payment_token": "tok_test_visa",
            "contact": {"name": "Thandi Mokoena", "email": "thandi@example.com"}, "delivery": ADDRESS})
        assert accepted.status_code == 200, accepted.text
        assert accepted.json()["ships_direct"] is True
    for response in (located, held, product, accepted):
        text = response.text
        assert "export_usd" not in text and "606" not in text
        assert "neutral_slip" not in text and "landed" not in text
        for marker in ("other-store", "other.example", "RSR|POF02445", "RSR", "tiger"):
            assert marker not in text, (marker, text)
    assert app.state.rig.handoff.placed[0]["ship"]["address"]["city"] == "Cape Town"


# 4. Odoo adapter: the blind path against a JSON-RPC double (shape and refusals).

class OdooDouble:
    """Minimal JSON-RPC double. Records every execute_kw call."""

    def __init__(self, *, dropship=True, linked_po=True, sale_state="draft"):
        self.calls, self.dropship, self.linked_po, self.sale_state = [], dropship, linked_po, sale_state
        self.created, self.writes = [], []

    def __call__(self, request):
        params = json.loads(request.content)["params"]
        if params["service"] == "common":
            return httpx.Response(200, json={"result": {"server_version_info": [17, 0]}
                                             if params["method"] == "version" else 2})
        _, _, _, model, method, args, kwargs = params["args"]
        self.calls.append((model, method))
        result = self.answer(model, method, args, kwargs)
        return httpx.Response(200, json={"result": result})

    def answer(self, model, method, args, kwargs):
        if (model, method) == ("sale.order", "search_read"):
            return [{"id": 7, "state": self.sale_state, "order_line": [70]}]
        if (model, method) == ("sale.order", "read"):
            return [{"id": 7, "name": "S00007", "state": "sale" if ("sale.order", "action_confirm") in self.calls
                     else self.sale_state, "partner_id": [11, "Thandi Mokoena"], "partner_shipping_id": [11, "x"]}]
        if model == "res.country":
            return [200]
        if model == "res.country.state":
            return [300]
        if (model, method) == ("res.partner", "search"):
            return []
        if method == "create":
            self.created.append((model, args[0]))
            return {"res.partner": 12 if args[0].get("type") == "delivery" else 13}.get(model, 50)
        if model == "ir.model.data":
            return [{"res_id": 9}] if self.dropship else []
        if (model, method) == ("product.product", "search_read"):
            return [{"id": 5, "product_tmpl_id": [6, "part"]}]
        if (model, method) == ("sale.order.line", "search"):
            return [70]
        if model == "res.currency":
            return [1]
        if (model, method) == ("product.supplierinfo", "search"):
            return []
        if method == "write":
            self.writes.append((model, args[0], args[1]))
            return True
        if method == "action_confirm":
            return True
        if (model, method) == ("purchase.order.line", "search_read"):
            return [{"order_id": [40, "P00040"]}] if self.linked_po else []
        if (model, method) == ("purchase.order", "read"):
            return [{"name": "P00040", "state": "draft", "partner_id": [13, "v"], "dest_address_id": [12, "ship"]}]
        raise AssertionError((model, method))


LOCATED = {"product_sku": "part-1", "offer": {"sku": "RSR|POF00307", "url": "https://other.example/p"},
           "live": {"price": "45.00", "currency": "USD"},
           "source": {"id": "other-store", "provider": "tiger", "site": "https://other.example",
                      "neutral_slip_required": True}}


async def place(double, located=LOCATED):
    async with httpx.AsyncClient(transport=httpx.MockTransport(double)) as http:
        sender = OdooHandoff(http, url="https://odoo.example.com", database="db", user="u", api_key="k")
        return await sender.place_located_order(tenant_id=TENANT, quote_id="q1", located=located,
                                                ship={"address": {**ADDRESS, "country": "ZA"}})


@pytest.mark.asyncio
async def test_odoo_blind_order_sets_address_route_then_confirms_and_marks_the_po(monkeypatch):
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    double = OdooDouble()
    result = await place(double)
    assert result["purchase_order"] == {"id": 40, "name": "P00040", "state": "draft", "dropship": True}
    delivery = next(values for model, values in double.created if model == "res.partner" and values.get("type"))
    assert delivery["parent_id"] == 11 and delivery["city"] == "Cape Town" and delivery["state_id"] == 300
    assert delivery["ref"] == f"rig:{TENANT}:q1:ship"
    vendor = next(values for model, values in double.created if model == "res.partner" and not values.get("type"))
    assert vendor["ref"] == f"rig-supply:{TENANT}:other-store"
    order = [c for c in double.calls if c[0] in ("sale.order", "sale.order.line")]
    # Address and route are written before the confirm.
    assert order.index(("sale.order", "write")) < order.index(("sale.order", "action_confirm"))
    assert order.index(("sale.order.line", "write")) < order.index(("sale.order", "action_confirm"))
    assert ("sale.order", [7], {"partner_shipping_id": 12}) in double.writes
    assert ("sale.order.line", [70], {"route_id": 9}) in double.writes
    po = next(values for model, _, values in double.writes if model == "purchase.order")
    assert po["notes"] == BLIND_INSTRUCTION and po["partner_ref"] == "RSR|POF00307"
    # Nothing written to customer-facing records names the other store.
    customer = json.dumps([w for w in double.writes if w[0].startswith("sale.")] + [delivery])
    for marker in ("other-store", "other.example", "RSR"):
        assert marker not in customer


@pytest.mark.asyncio
async def test_odoo_blind_order_without_neutral_flag_has_no_instruction(monkeypatch):
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    double = OdooDouble()
    await place(double, {**LOCATED, "source": {**LOCATED["source"], "neutral_slip_required": False}})
    po = next(values for model, _, values in double.writes if model == "purchase.order")
    assert "notes" not in po


@pytest.mark.asyncio
@pytest.mark.parametrize("double,code", [
    (OdooDouble(dropship=False), "odoo_dropship_missing"),
    (OdooDouble(linked_po=False), "odoo_purchase_mapping"),
    (OdooDouble(sale_state="cancel"), "odoo_order_state"),
])
async def test_odoo_blind_order_refuses_without_dropship_or_linked_po(monkeypatch, double, code):
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    with pytest.raises(DeliveryError, match=code):
        await place(double)
    if code == "odoo_dropship_missing":
        assert ("sale.order", "action_confirm") not in double.calls


# 5. Real Postgres: defaults false, values persist.

@pytest.mark.asyncio
async def test_real_postgres_blind_ship_and_neutral_slip_defaults_and_persistence():
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    admin = _admin_url()
    name = "rig_blind_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            await store.apply_schema()
            await store.put_retailer(TENANT, "shop", None, None, "Shop")
            assert (await store.retailer(TENANT))["blind_ship"] is False
            await store.put_retailer(TENANT, "shop", None, None, "Shop", blind_ship=True)
            await store.put_retailer(TENANT, "shop", "a@example.com", None, "Shop", locate_enabled=True)
            assert (await store.retailer(TENANT))["blind_ship"] is True
            supply = SupplyStore(store)
            base = dict(id="other-store", approved=True, priority=1, max_offer_age_seconds=3600, provider="tiger",
                        site="https://other.example")
            await supply.source(TENANT, base)
            assert (await supply.snapshot(TENANT))[0][0]["neutral_slip_required"] is False
            await supply.source(TENANT, {**base, "neutral_slip_required": True})
            assert (await supply.snapshot(TENANT))[0][0]["neutral_slip_required"] is True
            defaults = await pool.fetch("""SELECT table_name, column_default, is_nullable FROM information_schema.columns
                WHERE table_schema='agent_rig' AND column_name IN ('blind_ship', 'neutral_slip_required')""")
            assert {(r["table_name"], r["column_default"], r["is_nullable"]) for r in defaults} == {
                ("retailers", "false", "NO"), ("supply_sources", "false", "NO")}
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


# 6. Real Odoo 17 sandbox (box-local, opt-in): the Dropship route end to end.

def odoo_sandbox():
    url = os.environ.get("RIG_TEST_ODOO_SANDBOX", "")
    if not url:
        pytest.skip("RIG_TEST_ODOO_SANDBOX is not set (url|database|user|password of a local Odoo 17 sandbox)")
    return url.split("|")


@pytest.mark.asyncio
async def test_real_odoo_sandbox_blind_dropship(monkeypatch):
    url, database, user, password = odoo_sandbox()
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    from uuid import uuid4
    quote_id = "blind-" + uuid4().hex[:8]
    quote = {"id": quote_id, "contact": {"name": "Thandi Mokoena", "email": "thandi@example.com"},
             "payload": {"kind": "product", "product": {"id": "part-1", "name": "Locate test part",
                                                         "price": {"amount": "1125.00", "currency": "ZAR"}}}}
    async with httpx.AsyncClient() as http:
        sender = OdooHandoff(http, url=url, database=database, user=user, api_key=password)
        execute = await sender._session()
        await sender.send(tenant_id=TENANT, email=None, webhook=None, quote=quote)
        ship = {"address": {**ADDRESS, "country": "ZA"}}
        first = await sender.place_located_order(tenant_id=TENANT, quote_id=quote_id, located=LOCATED, ship=ship)
        again = await sender.place_located_order(tenant_id=TENANT, quote_id=quote_id, located=LOCATED, ship=ship)
        assert again["purchase_order"]["id"] == first["purchase_order"]["id"]  # idempotent
        assert first["sale_order"]["state"] == "sale" and first["purchase_order"]["dropship"] is True
        sale = (await execute("sale.order", "read", [[first["sale_order"]["id"]]],
                              fields=["partner_id", "partner_shipping_id", "note", "order_line", "picking_ids"]))[0]
        shipping = (await execute("res.partner", "read", [[sale["partner_shipping_id"][0]]],
                                  fields=["type", "parent_id", "street", "city", "zip", "country_id"]))[0]
        assert shipping["type"] == "delivery" and shipping["parent_id"][0] == sale["partner_id"][0]
        assert (shipping["street"], shipping["city"], shipping["zip"]) == ("12 Long Street", "Cape Town", "8001")
        lines = await execute("sale.order.line", "read", [sale["order_line"]], fields=["name", "route_id"])
        assert lines[0]["route_id"] and "Dropship" in lines[0]["route_id"][1]
        po = (await execute("purchase.order", "read", [[first["purchase_order"]["id"]]],
                            fields=["dest_address_id", "picking_type_id", "notes", "partner_id", "origin", "state"]))[0]
        assert po["dest_address_id"][0] == sale["partner_shipping_id"][0]
        assert "Dropship" in po["picking_type_id"][1] and po["state"] == "draft"
        assert "Ship blind" in po["notes"] and po["origin"] == first["sale_order"]["name"]
        # The store's own warehouse does not ship this order.
        assert sale["picking_ids"] == []
        customer = json.dumps([sale, shipping, lines])
        for marker in ("other-store", "other.example", "RSR"):
            assert marker not in customer
        print("ODOO_SANDBOX", json.dumps({"sale_order": first["sale_order"], "purchase_order": first["purchase_order"],
              "dest_address": po["dest_address_id"][1], "picking_type": po["picking_type_id"][1],
              "line_route": lines[0]["route_id"][1], "po_notes": po["notes"]}))
