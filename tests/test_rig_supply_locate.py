"""Offline supplier network tests. Never import fixture data into a live store."""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))
from rigbox.locate import SupplyStore, locate
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
                   active=False, supply_eligible=True, attributes={})
    await store.upsert_product(TENANT, product)
    await store.save_rule(TENANT, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
    # Locate is Optional per store and off by default. These tests opt in.
    await store.put_retailer(TENANT, "desk-shop", None, None, "Desk shop", locate_enabled=True)
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
    raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/rig_feed_formats/distributor.csv").read_text()
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
    raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/rig_feed_formats/distributor.csv").read_text()
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
            await store.put_retailer(TENANT, "desk-shop", None, None, "Desk shop", locate_enabled=True)
            supply = SupplyStore(store)
            await supply.source(TENANT, dict(id="approved", approved=True, priority=1, max_offer_age_seconds=3600))
            raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/rig_feed_formats/distributor.csv").read_text()
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
                # Policy activation is opt-in; exercise it only in this disposable DB.
                policy = (Path(__file__).resolve().parents[1] / "db/migrations/tenant_rls/agent_rig.sql").read_text()
                await conn.execute(policy)
                await conn.execute("CREATE ROLE rig_supply_test_reader")
                try:
                    await conn.execute("GRANT USAGE ON SCHEMA agent_rig TO rig_supply_test_reader")
                    await conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA agent_rig TO rig_supply_test_reader")
                    await conn.execute("SET ROLE rig_supply_test_reader")
                    await conn.execute("SELECT set_config('app.tenant_id',$1,false)", OTHER)
                    for table in ("supply_sources", "supply_offers", "supply_sku_map", "supply_sale_receipts"):
                        assert await conn.fetchval("SELECT count(*) FROM agent_rig." + table) == 0
                    await conn.execute("SELECT set_config('app.tenant_id',$1,false)", TENANT)
                    assert await conn.fetchval("SELECT count(*) FROM agent_rig.supply_offers") == 1
                finally:
                    await conn.execute("RESET ROLE")
                    await conn.execute("DROP OWNED BY rig_supply_test_reader")
                    await conn.execute("DROP ROLE rig_supply_test_reader")
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_disabled_product_is_not_resurrected_by_available_offer():
    store, _, product, _ = await network()
    product["supply_eligible"] = False
    await store.upsert_product(TENANT, product)
    assert not (await Service(store).search(TENANT, "Desk", 12))["results"]
    assert (await Service(store).locate(TENANT, "desk"))["status"] == "unavailable"


@pytest.mark.asyncio
async def test_feed_retains_explicit_disabled_versus_zero_stock():
    from rigbox.feeds.catalogue import map_catalogue
    raw = "sku,name,brand,category,price,image_url,quantity,active\nx,Desk,Workshop,furniture,40,https://example.com/x.png,0,true\n"
    row = map_catalogue({"format": "csv", "currency": "USD"}, raw)["rows"][0]
    assert row["supply_eligible"] and not row["active"]
    row = map_catalogue({"format": "csv", "currency": "USD"}, raw.replace(",0,true", ",0,false"))["rows"][0]
    assert not row["supply_eligible"] and not row["active"]


@pytest.mark.asyncio
async def test_http_locate_and_admin_ingestion_boundaries(monkeypatch):
    """Route authorization calls use stand-ins; existing auth suite covers keys."""
    import httpx
    from fastapi import FastAPI
    from rigbox.api import mount
    from rigbox.service import RigError, RecordingHandoff
    from rigbox.quotes.api import router as admin_router
    from rigbox.quotes.service import QuoteService
    from rigbox.quotes.store import MemoryQuotes
    store, _, _, _ = await network()
    service = QuoteService(store, None, RecordingHandoff(), MemoryQuotes(store))
    async def public_auth(role, address):
        if role not in ("public-test-role", "other-test-role"):
            raise RigError("unauthorized", "The request is not valid.", 401)
        return {"tenant_id": OTHER if role == "other-test-role" else TENANT, "origins": []}
    async def admin_auth(role):
        if role != "admin-test-role":
            raise RigError("unauthorized", "The request is not valid.", 401)
        return {"tenant_id": TENANT}
    monkeypatch.setattr(service, "authenticate", public_auth)
    monkeypatch.setattr(service, "authenticate_admin", admin_auth)
    app = FastAPI()
    app.state.rig = service
    mount(app)
    app.include_router(admin_router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://offline.example") as http:
        assert (await http.post("/v1/rig/locate", json={"product_id": "desk"})).status_code == 401
        public_headers = {"X-Rig-Key": "public-test-role"}
        found = await http.post("/v1/rig/locate", headers=public_headers, json={"product_id": "desk"})
        assert found.status_code == 200 and found.json()["status"] == "available_to_order"
        assert set(found.json()) == {"status", "eta", "price"}
        other = {"X-Rig-Key": "other-test-role"}
        # Locate is off for the other store: refused before any lookup.
        assert (await http.post("/v1/rig/locate", headers=other, json={"product_id": "desk"})).status_code == 403
        await store.put_retailer(OTHER, "other", None, None, "Other", locate_enabled=True)
        # Switched on, it still cannot see this store's product or offers.
        assert (await http.post("/v1/rig/locate", headers=other, json={"product_id": "desk"})).status_code == 404
        data = dict(id="new-source", approved=True, max_offer_age_seconds=500)
        assert (await http.post("/v1/rig/admin/supply/sources", headers=public_headers, json=data)).status_code == 401
        admin_headers = {"X-Rig-Key": "admin-test-role"}
        assert (await http.post("/v1/rig/admin/supply/sources", headers=admin_headers, json=data)).status_code == 200
        raw = (Path(__file__).resolve().parents[1] / "tests/fixtures/rig_feed_formats/distributor.csv").read_text()
        request = dict(source_id="new-source", record={"format": "csv", "currency": "USD"}, contents=raw, seen_at=NOW.isoformat())
        response = await http.post("/v1/rig/admin/supply/import", headers=admin_headers, json=request)
        assert response.status_code == 200 and response.json()["imported"] == 1
        mapping = dict(product_sku="desk", source_id="new-source", offer_sku="SAMPLE-DESK")
        assert (await http.post("/v1/rig/admin/supply/sku-map", headers=admin_headers, json=mapping)).status_code == 200
        response = await http.get("/v1/rig/admin/analytics", headers=admin_headers)
        assert response.status_code == 200 and response.json()["supply"]["kept_revenue"] is None


@pytest.mark.asyncio
async def test_supplier_rule_overrides_region_and_priority_breaks_ties():
    store, supply, product, offer = await network()
    await supply.source(TENANT, dict(id="approved", approved=True, priority=5, max_offer_age_seconds=3600,
                                    provider="existing-provider", site="existing-site", feed_id="existing-feed"))
    await store.save_rule(TENANT, {"freight": "99", "scopes": {
        "region:US": {"freight": "10"},
        "supplier:existing-provider:existing-site:existing-feed": {"freight": "1"}}})
    assert (await locate(store, TENANT, product))["public"]["price"]["amount"] == "41.00"
    await supply.source(TENANT, dict(id="second", approved=True, priority=1, max_offer_age_seconds=3600,
                                    provider="existing-provider", site="existing-site", feed_id="existing-feed"))
    store.supply_state[TENANT]["offers"].append({**offer, "source_id": "second"})
    assert (await locate(store, TENANT, product))["store"]["source_id"] == "second"


@pytest.mark.asyncio
@pytest.mark.parametrize("quantity", ["NaN", "Infinity", "-1"])
async def test_import_rejects_invalid_quantity_atomically(quantity):
    store, supply, _, _ = await network()
    raw = "sku,name,brand,category,price,image_url,quantity\nx,Desk,Workshop,furniture,40,https://example.com/x.png," + quantity + "\n"
    result = await supply.import_catalogue(TENANT, "approved", {"format": "csv", "currency": "USD"}, raw, NOW)
    assert result["imported"] == 0 and result["rejected"]
    assert len((await supply.snapshot(TENANT))[1]) == 1
