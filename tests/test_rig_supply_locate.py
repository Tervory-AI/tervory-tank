"""Offline supplier network tests. Never import fixture data into a live store."""
import copy
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))
from rigbox.locate import SupplyStore, catalogue, locate
from rigbox.service import Service
from rigbox.store import MemoryStore
from rigbox.quotes.privacy import shopper_body

NOW = datetime.now(timezone.utc)
TENANT = "00000000-0000-0000-0000-000000000101"
OTHER = "00000000-0000-0000-0000-000000000102"


async def network():
    store = MemoryStore()
    product = dict(sku="desk", id="desk", gtin="000000000123", mpn="D-1", name="Desk", brand="Workshop",
                   category="furniture", price="70", currency="USD", image_url="https://example.com/desk.png",
                   active=False, attributes={})
    await store.upsert_product(TENANT, product)
    await store.save_rule(TENANT, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
    supply = SupplyStore(store)
    await supply.source(TENANT, dict(id="approved", approved=True, priority=1, max_offer_age_seconds=3600))
    offer = dict(tenant_id=TENANT, source_id="approved", sku="supplier-desk", gtin="000000000123",
                 brand="Workshop", mpn="D-1", quantity="4", status="available", eta="2026-11-06",
                 ship_days=6, region="US", cost="40", currency="USD", seen_at=NOW)
    store.supply_state[TENANT]["offers"] = [offer]
    return store, supply, product, offer


@pytest.mark.asyncio
async def test_out_of_stock_search_and_quote_private_block():
    store, _, product, _ = await network()
    service = Service(store)
    found = await service.search(TENANT, "Desk", 12)
    assert found["results"][0]["availability"] == {"status": "available_to_order", "eta": "2026-11-06"}
    assert found["results"][0]["price"]["amount"] == 56.25
    payload, _ = await service.quote_payload(TENANT, {"product_id": "desk", "contact": {"name": "Offline", "email": "offline@example.com"}})
    assert payload["locate"][0]["store"]["source_id"] == "approved"
    public = json.dumps(shopper_body(payload))
    assert '"store"' not in public and '"cost"' not in public and "supplier-desk" not in public
    assert (await store.products(TENANT))[0]["active"] is False


@pytest.mark.asyncio
async def test_no_cross_store_even_with_injected_rows():
    store, _, product, offer = await network()
    assert (await locate(store, OTHER, product))["public"]["status"] == "unavailable"
    offer["tenant_id"] = OTHER
    assert (await locate(store, TENANT, product))["public"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_stale_degrades_and_saved_search_not_reused():
    store, _, product, offer = await network()
    service = Service(store)
    assert (await service.search(TENANT, "Desk", 12))["results"]
    offer["seen_at"] = NOW - timedelta(hours=2)
    assert (await locate(store, TENANT, product))["public"] == {"status": "check_with_store"}
    assert not (await service.search(TENANT, "Desk", 12))["results"]


@pytest.mark.asyncio
async def test_matching_precedence_and_explicit_mapping():
    store, supply, product, offer = await network()
    second = {**offer, "sku": "mapped", "gtin": "999999999999", "mpn": "OTHER", "cost": "1"}
    store.supply_state[TENANT]["offers"].append(second)
    await supply.map_sku(TENANT, "desk", "approved", "mapped")
    assert (await locate(store, TENANT, product))["store"]["sku"] == offer["sku"]
    product["gtin"] = ""
    assert (await locate(store, TENANT, product))["store"]["sku"] == offer["sku"]
    product["mpn"] = ""
    assert (await locate(store, TENANT, product))["store"]["sku"] == "mapped"
    with pytest.raises(ValueError):
        await supply.map_sku(OTHER, "desk", "approved", "mapped")


@pytest.mark.asyncio
async def test_rank_landed_cost_ship_days_priority_stable_tie():
    store, _, product, offer = await network()
    other = {**offer, "sku": "other", "ship_days": 2}
    store.supply_state[TENANT]["offers"].append(other)
    assert (await locate(store, TENANT, product))["store"]["sku"] == "other"
    other["cost"] = "41"
    assert (await locate(store, TENANT, product))["store"]["sku"] == "supplier-desk"
    offer["quantity"] = "0"
    assert (await locate(store, TENANT, product))["store"]["sku"] == "other"


@pytest.mark.asyncio
async def test_unapproved_missing_rule_fx_unknown_quantity_fail_closed():
    store, _, product, offer = await network()
    store.supply_state[TENANT]["sources"][0]["approved"] = False
    assert (await locate(store, TENANT, product))["public"]["status"] == "unavailable"
    store.supply_state[TENANT]["sources"][0]["approved"] = True
    offer["currency"] = "EUR"
    assert (await locate(store, TENANT, product))["public"]["status"] == "unavailable"
    offer["currency"] = "USD"
    offer["quantity"] = None
    assert (await locate(store, TENANT, product))["public"]["status"] == "unavailable"
    offer["quantity"] = 4
    store.private_rules.clear()
    assert (await locate(store, TENANT, product))["public"]["status"] == "unavailable"


@pytest.mark.asyncio
async def test_offline_distributor_import_reuses_parser_retains_quantity_eta():
    store, supply, product, _ = await network()
    raw = (Path(__file__).resolve().parents[1] / "agents/rig/catalogues/samples/distributor.csv").read_text()
    # This file is offline-only and has a non-standard sample UPC: map explicitly.
    result = await supply.import_catalogue(TENANT, "approved", {"format": "csv", "currency": "USD"}, raw, NOW)
    assert result == {"imported": 1, "rejected": []}
    await supply.map_sku(TENANT, "desk", "approved", "SAMPLE-DESK")
    product.update(gtin="", mpn="")
    found = await locate(store, TENANT, product)
    assert found["store"]["quantity"] == "12"
    assert found["public"]["eta"] is None  # No invented ETA from the sample.
    raw = raw.replace("url,family", "url,family,ETA,LeadTimeDays,MPN,Region").replace("sample-office\n", "sample-office,2026-11-09,9,D-2,US\n")
    await supply.import_catalogue(TENANT, "approved", {"format": "csv", "currency": "USD"}, raw, NOW)
    assert (await locate(store, TENANT, product))["public"]["eta"] == "2026-11-09"
    _, offers, _ = await supply.snapshot(TENANT)
    row = next(o for o in offers if o["sku"] == "SAMPLE-DESK")
    assert row["mpn"] == "D-2" and row["ship_days"] == 9 and row["region"] == "US"


@pytest.mark.asyncio
async def test_old_import_cannot_overwrite_new_observation():
    store, supply, _, _ = await network()
    raw = (Path(__file__).resolve().parents[1] / "agents/rig/catalogues/samples/distributor.csv").read_text()
    record = {"format": "csv", "currency": "USD"}
    await supply.import_catalogue(TENANT, "approved", record, raw, NOW)
    await supply.import_catalogue(TENANT, "approved", record, raw.replace(",12,", ",0,"), NOW - timedelta(minutes=5))
    _, offers, _ = await supply.snapshot(TENANT)
    assert next(o for o in offers if o["sku"] == "SAMPLE-DESK")["quantity"] == 12


def test_redaction_recurses_private_supplier_fields():
    assert shopper_body({"x": [{"supplier": "private", "ship_from": "US", "region": "US", "cost": 12,
                                 "store": {"sku": "secret"}, "status": "available_to_order"}]}) == {
                                     "x": [{"status": "available_to_order"}]}


@pytest.mark.asyncio
async def test_revenue_requires_receipt_retries_dont_inflate_and_currencies_separate():
    from datetime import date
    from rigbox.quotes.service import QuoteService
    from rigbox.quotes.store import MemoryQuotes
    from rigbox.service import RecordingHandoff
    from rigbox.supply_accounting import record_receipt, analytics
    store, _, _, _ = await network()
    service = QuoteService(store, None, RecordingHandoff(), MemoryQuotes(store))
    before = await analytics(service, TENANT, date.min)
    assert before["located_count"] == 0 and before["kept_revenue"] is None
    payload, contact = await service.quote_payload(TENANT, {"product_id": "desk", "contact": {"name": "Offline", "email": "offline@example.com"}})
    await service.quote_store.create(TENANT, {"id": "offline-quote", "payload": payload, "contact": contact})
    result = await analytics(service, TENANT, date.min)
    assert result["located_count"] == 1 and result["kept_revenue"] is None
    receipt = dict(receipt_id="receipt-1", quote_id="offline-quote", product_id="desk", amount="53.21",
                   currency="USD", source_ref="offline-receipt-reference", received_at=NOW.isoformat())
    assert await record_receipt(service, TENANT, receipt)
    assert not await record_receipt(service, TENANT, receipt)
    with pytest.raises(ValueError):
        await record_receipt(service, TENANT, {**receipt, "amount": "99"})
    with pytest.raises(ValueError):
        await record_receipt(service, OTHER, receipt)
    await record_receipt(service, TENANT, {**receipt, "receipt_id": "refund-1", "amount": "-3.21"})
    await record_receipt(service, TENANT, {**receipt, "receipt_id": "receipt-eur", "amount": "7", "currency": "EUR"})
    result = await analytics(service, TENANT, date.min)
    assert result["kept_revenue"] == {"EUR": "7", "USD": "50.00"}
    assert result["kept_revenue_provenance"] == "store_reported_sale_receipts"
    assert result["receipt_count"] == 3 and result["located_count"] == 1


@pytest.mark.asyncio
async def test_real_postgres_schema_twice_import_isolation_and_receipt_atomicity():
    import asyncpg
    from datetime import date
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _database_url, _create_database, _drop_database
    from rigbox.store import PgStore
    from rigbox.quotes.store import PgQuotes
    from rigbox.quotes.service import QuoteService
    from rigbox.service import RecordingHandoff
    from rigbox.supply_accounting import record_receipt, analytics
    admin = _admin_url()
    name = "rig_supply_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            await store.apply_schema()
            _, _, product, _ = await network()
            await store.upsert_product(TENANT, product)
            assert (await store.products(TENANT))[0]["mpn"] == "D-1"
            await store.save_rule(TENANT, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
            supply = SupplyStore(store)
            await supply.source(TENANT, dict(id="approved", approved=True, priority=1, max_offer_age_seconds=3600))
            raw = (Path(__file__).resolve().parents[1] / "agents/rig/catalogues/samples/distributor.csv").read_text()
            await supply.import_catalogue(TENANT, "approved", {"format": "csv", "currency": "USD"}, raw, NOW)
            await supply.map_sku(TENANT, "desk", "approved", "SAMPLE-DESK")
            assert (await locate(store, TENANT, product))["public"]["status"] == "available_to_order"
            assert (await locate(store, OTHER, product))["public"]["status"] == "unavailable"
            service = QuoteService(store, None, RecordingHandoff(), PgQuotes(pool))
            payload, contact = await service.quote_payload(TENANT, {"product_id": "desk", "contact": {"name": "Offline", "email": "offline@example.com"}})
            await service.quote_store.create(TENANT, {"id": "offline-pg-quote", "payload": payload, "contact": contact})
            receipt = dict(receipt_id="pg-receipt-1", quote_id="offline-pg-quote", product_id="desk", amount="53.21",
                           currency="USD", source_ref="offline-pg-reference", received_at=NOW.isoformat())
            import asyncio
            results = await asyncio.gather(*(record_receipt(service, TENANT, receipt) for _ in range(3)))
            assert results.count(True) == 1
            assert (await analytics(service, TENANT, date.min))["kept_revenue"] == {"USD": "53.21"}
            async with pool.acquire() as conn:
                row = await conn.fetchrow("SELECT sum(located_count) AS n FROM agent_rig.widget_counts WHERE tenant_id=$1", __import__('uuid').UUID(TENANT))
                assert row["n"] == 1
                rows = await conn.fetch("SELECT kept_revenue FROM agent_rig.widget_counts WHERE tenant_id=$1", __import__('uuid').UUID(TENANT))
                assert any(json.loads(r["kept_revenue"]).get("USD") == "53.21" for r in rows)
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_odoo_supplier_note_internal_and_retry_reconciles_lost_response():
    import httpx
    from test_rig_quotes import OdooStub, adapter
    from rigbox.quotes.senders import DeliveryError
    class Stub(OdooStub):
        def __init__(self):
            super().__init__()
            self.notes = []
            self.lose_response = True
        def __call__(self, request):
            params = json.loads(request.content)["params"]
            if params["service"] == "object":
                _, _, _, model, method, args, kwargs = params["args"]
                if model == "mail.message" and method == "search":
                    return httpx.Response(200, json={"result": [1] if self.notes else []})
                if model == "sale.order" and method == "message_post":
                    assert kwargs["subtype_xmlid"] == "mail.mt_note"
                    assert kwargs["message_type"] == "comment"
                    self.notes.append(kwargs["body"])
                    if self.lose_response:
                        self.lose_response = False
                        raise httpx.ReadTimeout("offline lost response", request=request)
                    return httpx.Response(200, json={"result": 1})
            return super().__call__(request)
    stub = Stub()
    store, _, _, _ = await network()
    payload, contact = await Service(store).quote_payload(TENANT, {"product_id": "desk", "contact": {
        "name": "Offline", "email": "offline@example.com"}})
    quote = {"id": "offline-odoo", "payload": payload, "contact": contact}
    async with httpx.AsyncClient(transport=httpx.MockTransport(stub)) as http:
        sender = adapter(http)
        with pytest.raises(DeliveryError):
            await sender.send(tenant_id=TENANT, email=None, webhook=None, quote=quote)
        await sender.send(tenant_id=TENANT, email=None, webhook=None, quote=quote)
    assert len(stub.orders) == len(stub.notes) == 1
    order = stub.orders[0]
    assert "supplier-desk" not in json.dumps(order)
    assert "supplier-desk" in stub.notes[0]
    assert all(method not in ("action_confirm", "action_invoice_create", "action_post") for _, method, _, _ in stub.calls)
