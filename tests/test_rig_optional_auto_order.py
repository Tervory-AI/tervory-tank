"""Optional auto-order: send the confirmed PO to the approved source.

Per-store ``auto_order`` switch, off by default. Sandbox only: the supplier
"email" is a file in a local outbox (RIG_LOCATE_OUTBOX_DIR); nothing is sent.
The vendor is a real res.partner (store-entered vendor name and order inbox),
not the source's URL. Idempotent, and any failure after payment refunds.
"""
import email
import json
import smtplib
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox import supplier_orders
from rigbox.locate import SupplyStore
from rigbox.quotes.privacy import shopper_body
from rigbox.quotes.senders import DeliveryError, OdooHandoff, sandbox_orders
from rigbox.quotes.service import QuoteService
from rigbox.quotes.store import MemoryQuotes
from rigbox.retailer import Retailer
from rigbox.service import RigError, Service
from test_rig_locate_checkout import TENANT, FakeProvider, Live, available, rate_stub, shop
from test_rig_optional_blind_ship import ADDRESS, LOCATED, OdooDouble

SOURCE = dict(id="other-store", approved=True, priority=1, max_offer_age_seconds=3600, provider="tiger",
              site="https://other.example", neutral_slip_required=True, vendor_name="Other Store Wholesale LLC",
              order_email="orders@other.example")
READY = {**LOCATED, "source": {**LOCATED["source"], "vendor_name": SOURCE["vendor_name"],
                               "order_email": SOURCE["order_email"]}}
PURCHASE = {"id": 40, "name": "P00040", "state": "draft"}


@pytest.fixture(autouse=True)
def no_network_mail(monkeypatch):
    """Auto-order must never open SMTP. Any attempt fails the test."""
    def refuse(*args, **kwargs):
        raise AssertionError("SMTP must never be used by auto-order")
    monkeypatch.setattr(smtplib, "SMTP", refuse)
    monkeypatch.setattr(smtplib, "SMTP_SSL", refuse)


def env(monkeypatch, outbox):
    monkeypatch.setenv("RIG_LOCATE_HOLD_SECRET", "s" * 40)
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "test")
    monkeypatch.setenv("RIG_LOCATE_OUTBOX_DIR", str(outbox))
    for name in ("STRIPE_SECRET_KEY", "PAYSTACK_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)


class AutoOrders:
    """Sandbox Odoo double; the supplier email goes through the real outbox code."""

    def __init__(self, *, fail_supplier=False):
        self.sent, self.placed, self.supplied, self.fail_supplier = [], [], [], fail_supplier

    async def send(self, *, tenant_id, email, webhook, quote):
        self.sent.append(quote["id"])

    async def place_located_order(self, *, tenant_id, quote_id, located, ship=None):
        sandbox_orders()
        self.placed.append(quote_id)
        return {"sale_order": {"name": "S00001", "state": "sale"},
                "purchase_order": dict(PURCHASE, dropship=ship is not None)}

    async def send_supplier_order(self, *, tenant_id, quote_id, located, order, ship=None, store_name="",
                                  store_email=None):
        if self.fail_supplier:
            raise DeliveryError("odoo_rejected")
        message = supplier_orders.compose(tenant_id=tenant_id, quote_id=quote_id, store_name=store_name,
                                          store_email=store_email, located=located,
                                          purchase=order["purchase_order"], ship=ship)
        sent = supplier_orders.write(message, tenant_id=tenant_id, quote_id=quote_id)
        self.supplied.append(sent)
        return {"purchase_order": {**order["purchase_order"], "state": "purchase"}, "supplier_order": sent}


async def auto_shop(monkeypatch, outbox, *, auto=True, blind=True, source=SOURCE, fail_supplier=False):
    env(monkeypatch, outbox)
    store = await rate_stub(await shop())
    await store.put_retailer(TENANT, "shop", "shop@example.com", None, "Shop", blind_ship=blind, auto_order=auto)
    await SupplyStore(store).source(TENANT, dict(source))
    orders = AutoOrders(fail_supplier=fail_supplier)
    service = QuoteService(store, None, orders, MemoryQuotes(store))
    service.locate_checker = Live(available("45.00"))
    service.payments = FakeProvider()
    held = await service.locate_confirm(TENANT, "part-1")
    body = {"product_id": "part-1", "hold": held["hold"], "payment_token": "tok_test_visa",
            "contact": {"name": "Thandi Mokoena", "email": "thandi@example.com"}, "delivery": dict(ADDRESS)}
    return store, service, orders, held, body


# 1. Switch and source config.

@pytest.mark.asyncio
async def test_auto_order_is_off_by_default_and_needs_a_boolean():
    store = await rate_stub(await shop())
    assert (await store.retailer(TENANT))["auto_order"] is False
    retailer = Retailer(Service(store))
    base = {"name": "Shop", "email": "shop@example.com"}
    for bad in ("true", 1, None, "live"):
        with pytest.raises(ValueError):
            await retailer.set_settings(TENANT, {**base, "auto_order": bad})
    await retailer.set_settings(TENANT, {**base, "auto_order": True})
    assert (await retailer.panel(TENANT))["settings"]["auto_order"] is True
    await retailer.set_settings(TENANT, base)
    assert (await retailer.panel(TENANT))["settings"]["auto_order"] is True


@pytest.mark.asyncio
async def test_source_order_email_is_validated_and_supplier_ready_needs_both_fields():
    store = await rate_stub(await shop())
    supply = SupplyStore(store)
    for bad in ("orders", "a@b", "x@y.com, evil@z.com", "a@b.com\r\nBcc: z@z.com"):
        with pytest.raises(ValueError):
            await supply.source(TENANT, {**SOURCE, "order_email": bad})
    await supply.source(TENANT, SOURCE)
    assert supplier_orders.supplier_ready((await supply.snapshot(TENANT))[0][0])
    assert not supplier_orders.supplier_ready({**SOURCE, "vendor_name": ""})
    assert not supplier_orders.supplier_ready({**SOURCE, "order_email": ""})


# 2. Outbox: sandbox only, configured folder only, exactly once.

def test_outbox_refuses_outside_sandbox_or_without_folder(tmp_path):
    for env_values in ({}, {"RIG_LOCATE_ORDER_MODE": "live", "RIG_LOCATE_OUTBOX_DIR": str(tmp_path)},
                       {"RIG_LOCATE_ORDER_MODE": "sandbox"},
                       {"RIG_LOCATE_ORDER_MODE": "sandbox", "RIG_LOCATE_OUTBOX_DIR": str(tmp_path / "missing")}):
        with pytest.raises(DeliveryError):
            supplier_orders.outbox(env_values)
    assert supplier_orders.outbox({"RIG_LOCATE_ORDER_MODE": "sandbox", "RIG_LOCATE_OUTBOX_DIR": str(tmp_path)}) == tmp_path


def test_there_is_no_live_transport():
    text = (ROOT / "agents" / "rig" / "rigbox" / "supplier_orders.py").read_text()
    code = text.split('"""', 2)[2]  # code after the module docstring
    for word in ("smtplib", "SmtpMailer", "import socket", "httpx", "requests", "urllib", "send_message", "MODE_LIVE",
                 '== "live"', "== 'live'"):
        assert word not in code, word


def test_supplier_email_carries_po_address_and_blind_instruction_but_no_shop_pricing(tmp_path):
    message = supplier_orders.compose(tenant_id=TENANT, quote_id="q1", store_name="Custom Nation",
                                      store_email="orders@customnation.example", located=READY,
                                      purchase=PURCHASE, ship={"address": {**ADDRESS, "country": "ZA"}})
    body = message.get_content()
    assert message["To"] == "orders@other.example" and message["Reply-To"] == "orders@customnation.example"
    assert message["Subject"] == "Purchase order P00040 from Custom Nation"
    assert "Other Store Wholesale LLC" in body and "RSR|POF00307" in body and "45.00 USD" in body
    assert "12 Long Street" in body and "Cape Town" in body and "SHIP BLIND" in body
    # The store's own shopper price, landed cost and margin never go to the supplier.
    for private in ("1125", "landed", "margin", "duty", "thandi@example.com"):
        assert private not in body
    unflagged = supplier_orders.compose(tenant_id=TENANT, quote_id="q1", store_name="Custom Nation", store_email=None,
        located={**READY, "source": {**READY["source"], "neutral_slip_required": False}}, purchase=PURCHASE,
        ship={"address": {**ADDRESS, "country": "ZA"}})
    assert "SHIP BLIND" not in unflagged.get_content() and unflagged["Reply-To"] is None
    with pytest.raises(DeliveryError, match="supplier_not_configured"):
        supplier_orders.compose(tenant_id=TENANT, quote_id="q1", store_name="x", store_email=None,
                                located=LOCATED, purchase=PURCHASE, ship=None)


def test_outbox_write_is_idempotent(tmp_path):
    values = {"RIG_LOCATE_ORDER_MODE": "sandbox", "RIG_LOCATE_OUTBOX_DIR": str(tmp_path)}
    message = supplier_orders.compose(tenant_id=TENANT, quote_id="q1", store_name="Shop", store_email=None,
                                      located=READY, purchase=PURCHASE, ship=None)
    first = supplier_orders.write(message, tenant_id=TENANT, quote_id="q1", env=values)
    second = supplier_orders.write(message, tenant_id=TENANT, quote_id="q1", env=values)
    assert first["duplicate"] is False and second["duplicate"] is True and first["file"] == second["file"]
    files = list(tmp_path.iterdir())
    assert len(files) == 1 and oct(files[0].stat().st_mode & 0o777) == "0o600"
    parsed = email.message_from_bytes(files[0].read_bytes())
    assert parsed["To"] == "orders@other.example" and parsed["X-Rig-Reference"] == f"rig:{TENANT}:q1"


# 3. Accept -> pay -> order -> supplier email.

@pytest.mark.asyncio
async def test_accept_auto_orders_once_through_the_sandbox_outbox(monkeypatch, tmp_path):
    store, service, orders, held, body = await auto_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, body)
    assert result["state"] == "ordered" and result["ships_direct"] is True
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "supplier_ordered" and state["purchase_order_state"] == "purchase"
    assert state["supplier_order"]["transport"] == "sandbox_outbox" and state["supplier_order"]["duplicate"] is False
    assert len(list(tmp_path.iterdir())) == 1 and len(service.payments.captured) == 1
    text = json.dumps(shopper_body(result))
    for marker in ("other-store", "other.example", "Other Store Wholesale", "orders@", "outbox", "P00040"):
        assert marker not in text
    with pytest.raises(RigError) as raised:  # the hold is single use: no second payment or order
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 410
    assert len(list(tmp_path.iterdir())) == 1 and len(service.payments.captured) == 1


@pytest.mark.asyncio
async def test_supplier_order_failure_refunds(monkeypatch, tmp_path):
    store, service, orders, _, body = await auto_shop(monkeypatch, tmp_path, fail_supplier=True)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "supplier_order_failed_refunded" and state["refund"] == {"status": "refunded"}
    assert service.payments.refunded == ["supplier_order_failed"] and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_source_without_vendor_or_inbox_refuses_before_payment(monkeypatch, tmp_path):
    store, service, orders, _, body = await auto_shop(monkeypatch, tmp_path,
                                                      source={**SOURCE, "vendor_name": "", "order_email": ""})
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 503
    assert service.payments.captured == [] and orders.placed == [] and orders.sent == []


@pytest.mark.asyncio
async def test_missing_outbox_refuses_before_hold_or_payment(monkeypatch, tmp_path):
    store, service, orders, held, body = await auto_shop(monkeypatch, tmp_path)
    monkeypatch.setenv("RIG_LOCATE_OUTBOX_DIR", str(tmp_path / "missing"))
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 503 and service.payments.captured == []
    assert store.supply_state[TENANT]["holds"][held["hold"].split(".")[0]]["used_at"] is None


@pytest.mark.asyncio
async def test_switch_off_keeps_the_draft_po_and_writes_nothing(monkeypatch, tmp_path):
    store, service, orders, _, body = await auto_shop(monkeypatch, tmp_path, auto=False)
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "ordered"
    assert orders.supplied == [] and list(tmp_path.iterdir()) == []


# 4. Odoo adapter (JSON-RPC double): confirm once, cancel when the outbox fails.

class SupplierOdoo(OdooDouble):
    def __init__(self, state="draft"):
        super().__init__()
        self.po_state = state

    def answer(self, model, method, args, kwargs):
        if (model, method) == ("res.partner", "search"):
            return [13]
        if (model, method) == ("purchase.order", "read"):
            return [{"name": "P00040", "state": self.po_state, "partner_id": [13, "Other Store Wholesale LLC"]}]
        if (model, method) == ("purchase.order", "button_confirm"):
            self.po_state = "purchase"
            return True
        if (model, method) == ("purchase.order", "button_cancel"):
            self.po_state = "cancel"
            return True
        if model == "mail.message":
            return []
        if method == "message_post":
            return 1
        return super().answer(model, method, args, kwargs)


async def supply(double, tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(double)) as http:
        sender = OdooHandoff(http, url="https://odoo.example.com", database="db", user="u", api_key="k")
        return await sender.send_supplier_order(tenant_id=TENANT, quote_id="q1", located=READY,
                                                order={"purchase_order": PURCHASE}, store_name="Shop",
                                                env={"RIG_LOCATE_ORDER_MODE": "sandbox",
                                                     "RIG_LOCATE_OUTBOX_DIR": str(tmp_path)})


@pytest.mark.asyncio
async def test_odoo_supplier_order_confirms_once_and_names_the_real_vendor(tmp_path):
    double = SupplierOdoo()
    first = await supply(double, tmp_path)
    second = await supply(double, tmp_path)
    assert first["purchase_order"]["state"] == "purchase" and first["supplier_order"]["duplicate"] is False
    assert second["supplier_order"]["duplicate"] is True
    assert double.calls.count(("purchase.order", "button_confirm")) == 1
    assert ("res.partner", [13], {"name": "Other Store Wholesale LLC", "email": "orders@other.example"}) in double.writes


@pytest.mark.asyncio
async def test_odoo_supplier_order_cancels_the_po_when_the_outbox_fails(tmp_path, monkeypatch):
    double = SupplierOdoo()

    def broken(*args, **kwargs):
        raise DeliveryError("outbox_unavailable")
    monkeypatch.setattr(supplier_orders, "write", broken)
    with pytest.raises(DeliveryError, match="outbox_unavailable"):
        await supply(double, tmp_path)
    assert double.po_state == "cancel"


@pytest.mark.asyncio
async def test_odoo_supplier_order_refuses_outside_sandbox_before_any_call(tmp_path):
    calls = []
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(500))) as http:
        sender = OdooHandoff(http, url="https://odoo.example.com", database="db", user="u", api_key="k")
        for values in ({"RIG_LOCATE_ORDER_MODE": "live", "RIG_LOCATE_OUTBOX_DIR": str(tmp_path)},
                       {"RIG_LOCATE_ORDER_MODE": "sandbox"}):
            with pytest.raises(DeliveryError):
                await sender.send_supplier_order(tenant_id=TENANT, quote_id="q1", located=READY,
                                                 order={"purchase_order": PURCHASE}, env=values)
    assert calls == []


# 5. Real Postgres: defaults and persistence.

@pytest.mark.asyncio
async def test_real_postgres_auto_order_and_vendor_fields():
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    admin = _admin_url()
    name = "rig_auto_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            await store.apply_schema()
            await store.put_retailer(TENANT, "shop", None, None, "Shop")
            assert (await store.retailer(TENANT))["auto_order"] is False
            await store.put_retailer(TENANT, "shop", None, None, "Shop", auto_order=True)
            await store.put_retailer(TENANT, "shop", "a@example.com", None, "Shop", blind_ship=True)
            saved = await store.retailer(TENANT)
            assert saved["auto_order"] is True and saved["blind_ship"] is True
            supply_store = SupplyStore(store)
            await supply_store.source(TENANT, SOURCE)
            row = (await supply_store.snapshot(TENANT))[0][0]
            assert (row["vendor_name"], row["order_email"]) == ("Other Store Wholesale LLC", "orders@other.example")
            default = await pool.fetchval("""SELECT column_default FROM information_schema.columns
                WHERE table_schema='agent_rig' AND table_name='retailers' AND column_name='auto_order'""")
            assert default == "false"
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


# 6. Real Odoo 17 sandbox (opt-in): blind dropship PO confirmed, outbox written once.

@pytest.mark.asyncio
async def test_real_odoo_sandbox_auto_order(monkeypatch, tmp_path):
    from test_rig_optional_blind_ship import odoo_sandbox
    sandbox = odoo_sandbox()  # url|database|user|credential of the local sandbox
    url, database, user = sandbox[:3]
    monkeypatch.setenv("RIG_LOCATE_ORDER_MODE", "sandbox")
    monkeypatch.setenv("RIG_LOCATE_OUTBOX_DIR", str(tmp_path))
    from uuid import uuid4
    quote_id = "auto-" + uuid4().hex[:8]
    quote = {"id": quote_id, "contact": {"name": "Thandi Mokoena", "email": "thandi@example.com"},
             "payload": {"kind": "product", "product": {"id": "part-1", "name": "Locate test part",
                                                         "price": {"amount": "1125.00", "currency": "ZAR"}}}}
    ship = {"address": {**ADDRESS, "country": "ZA"}}
    async with httpx.AsyncClient() as http:
        sender = OdooHandoff(http, url=url, database=database, user=user, api_key=sandbox[3])
        execute = await sender._session()
        await sender.send(tenant_id=TENANT, email=None, webhook=None, quote=quote)
        order = await sender.place_located_order(tenant_id=TENANT, quote_id=quote_id, located=READY, ship=ship)
        first = await sender.send_supplier_order(tenant_id=TENANT, quote_id=quote_id, located=READY, order=order,
                                                 ship=ship, store_name="Custom Nation (sandbox)")
        again = await sender.send_supplier_order(tenant_id=TENANT, quote_id=quote_id, located=READY, order=order,
                                                 ship=ship, store_name="Custom Nation (sandbox)")
        assert first["purchase_order"]["state"] == "purchase" and again["supplier_order"]["duplicate"] is True
        po = (await execute("purchase.order", "read", [[order["purchase_order"]["id"]]],
                            fields=["partner_id", "state", "picking_ids", "dest_address_id"]))[0]
        vendor = (await execute("res.partner", "read", [[po["partner_id"][0]]], fields=["name", "email", "website"]))[0]
        assert (vendor["name"], vendor["email"]) == ("Other Store Wholesale LLC", "orders@other.example")
        pickings = await execute("stock.picking", "read", [po["picking_ids"]],
                                 fields=["picking_type_id", "partner_id", "location_id", "location_dest_id", "state"])
        assert len(pickings) == 1 and "Dropship" in pickings[0]["picking_type_id"][1]
        # Odoo 17 puts the vendor on a dropship picking; the shopper address lives on the PO and SO.
        assert pickings[0]["partner_id"][0] == po["partner_id"][0]
        ship_to = (await execute("res.partner", "read", [[po["dest_address_id"][0]]], fields=["type", "ref"]))[0]
        assert ship_to["type"] == "delivery" and ship_to["ref"] == f"rig:{TENANT}:{quote_id}:ship"
        assert "Customers" in pickings[0]["location_dest_id"][1] and "Vendors" in pickings[0]["location_id"][1]
        notes = await execute("mail.message", "search_count", [[["model", "=", "purchase.order"],
            ["res_id", "=", po["id"] if "id" in po else order["purchase_order"]["id"]],
            ["body", "ilike", f"rig-supplier-order:{TENANT}:{quote_id}"]]])
        assert notes == 1
    files = list(tmp_path.iterdir())
    assert len(files) == 1
    parsed = email.message_from_bytes(files[0].read_bytes())
    print("ODOO_SANDBOX_AUTO", json.dumps({"purchase_order": first["purchase_order"], "vendor": vendor["name"],
          "picking": {k: pickings[0][k] for k in ("picking_type_id", "location_id", "location_dest_id", "state")},
          "outbox_file": files[0].name, "to": parsed["To"], "subject": parsed["Subject"]}))
    print(parsed.get_payload())
