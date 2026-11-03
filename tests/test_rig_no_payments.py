"""Store-owned settlement: offline routes and an isolated Postgres database."""
import asyncio
import copy
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from rigbox.api import mount
from rigbox.locate import SupplyStore
from rigbox.quotes.privacy import shopper_body
from rigbox.quotes.senders import DeliveryError
from rigbox.quotes.service import QuoteService
from rigbox.quotes.store import MemoryQuotes, PgQuotes
from rigbox.retailer import Retailer
from rigbox.retailer_api import router as retailer_router
from rigbox.service import RigError
from rigbox.store import PgStore
from fixtures.rig_quote_sample import KEY
from test_rig_locate_checkout import OTHER, TENANT, Live, available, rate_stub, shop
from test_rig_optional_auto_order import SOURCE, auto_shop
from test_rig_optional_blind_ship import HandoffDouble

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("inserted", [False, True])
async def test_transient_placement_retries_once_without_duplicate_orders(monkeypatch, tmp_path, inserted):
    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    quote_id = (await service.locate_accept(TENANT, body))["request_id"]
    original = service.fulfilment.place_located_order
    calls = 0

    async def transient(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            if inserted:
                await original(**kwargs)
            raise ConnectionError("placeholder-transient")
        return await original(**kwargs)

    monkeypatch.setattr(service.fulfilment, "place_located_order", transient)
    first = await service.confirm_store_payment(TENANT, quote_id)
    state = (await store.quote_for(TENANT, quote_id))["payload"]["locate_state"]
    assert first["state"] == "store_confirmed" and state["attempted_at"] is None
    assert state["attempt_id"] is None and not list(tmp_path.glob("*.eml"))
    second = await service.confirm_store_payment(TENANT, quote_id)
    assert second["state"] == "supplier_ordered" and calls == 2
    await service.confirm_store_payment(TENANT, quote_id)
    assert calls == 2 and len(store.locate_orders) == 1 and len(list(tmp_path.glob("*.eml"))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("error", ["order_mismatch", "order_rejected"])
async def test_permanent_placement_error_needs_person(monkeypatch, tmp_path, error):
    from unittest.mock import AsyncMock
    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    quote_id = (await service.locate_accept(TENANT, body))["request_id"]
    place = AsyncMock(side_effect=DeliveryError(error))
    monkeypatch.setattr(service.fulfilment, "place_located_order", place)
    assert (await service.confirm_store_payment(TENANT, quote_id))["state"] == "needs_person"
    assert (await service.confirm_store_payment(TENANT, quote_id))["state"] == "needs_person"
    assert place.await_count == 1 and not store.locate_orders
    assert not list(tmp_path.glob("*.eml"))


@pytest.mark.asyncio
async def test_lost_lease_http_returns_current_tenant_quote_state(monkeypatch, tmp_path):
    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    quote_id = (await service.locate_accept(TENANT, body))["request_id"]
    original = service.fulfilment.place_located_order

    async def takeover(**kwargs):
        order = await original(**kwargs)
        state = (await store.quote_for(TENANT, quote_id))["payload"]["locate_state"]
        await store.locate_state(TENANT, quote_id, {**state, "attempt_id": "placeholder-new-owner",
                                                 "state": "ordered"})
        return order

    monkeypatch.setattr(service.fulfilment, "place_located_order", takeover)
    monkeypatch.setenv("RIG_RETAILER_KEY", KEY)
    app = FastAPI()
    app.state.rig = service
    mount(app)
    app.include_router(retailer_router)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://placeholder.invalid") as client:
        headers = {"x-rig-retailer-key": KEY}
        path = "/internal/retailer/confirm-store-payment"
        response = await client.post(path, json={"tenant_id": TENANT, "data": {"quote_id": quote_id}}, headers=headers)
        assert response.status_code == 200
        assert response.json() == {"request_id": quote_id, "confirmed": True, "state": "ordered",
                                   "items": [shopper_body((await store.quote_for(TENANT, quote_id))["payload"]["product"])]}
        denied = await client.post(path, json={"tenant_id": OTHER, "data": {"quote_id": quote_id}}, headers=headers)
        assert denied.status_code == 404
    assert len(store.locate_orders) == 1


def test_no_provider_module_route_setting_or_call_remains():
    assert not (ROOT / "agents/rig/rigbox/payments.py").exists()
    forbidden = re.compile(
        r"rigbox[ .]payments|from\s+\.\s+import\s+payments|self\.payments|"
        r"reconcile_payments|_capture_or_void|refund_or_leave_due|payment_webhook|"
        r"/locate/payments/|payment_token|RIG_LOCATE_PAYMENTS_MODE|"
        r"[\"'](?:payment_pending|payment_failed|payment_refused|captured|refunded)[\"']"
    )
    paths = list((ROOT / "agents/rig").rglob("*.py"))
    paths += list(ROOT.glob("*compose*.yml")) + [ROOT / ".env.example"]
    for path in paths:
        assert not forbidden.search(path.read_text()), str(path.relative_to(ROOT))
    app = FastAPI()
    mount(app)
    assert all("payments" not in path for path in app.openapi()["paths"])


@pytest.mark.asyncio
async def test_accept_without_order_configuration_stores_and_hands_off_only(monkeypatch, tmp_path):
    store, service, handoff, held, body = await auto_shop(monkeypatch, tmp_path)
    monkeypatch.delenv("RIG_LOCATE_ORDER_MODE")
    monkeypatch.delenv("RIG_LOCATE_OUTBOX_DIR")
    result = await service.locate_accept(TENANT, body)
    assert result["state"] == "accepted" and result["price"] == held["price"]
    assert len(handoff.sent) == 1 and not store.locate_orders and not list(tmp_path.iterdir())
    quote = await store.quote_for(TENANT, result["request_id"])
    assert quote["payload"]["locate_state"]["state"] == "accepted"
    assert result["items"][0]["delivery"] == {"ship_days": 10, "eta": "2026-11-12", "back_order": False}
    assert "payment" not in json.dumps(result)


@pytest.mark.asyncio
async def test_failed_handoff_retries_existing_quote_without_ordering(monkeypatch, tmp_path):
    store, service, handoff, _, body = await auto_shop(monkeypatch, tmp_path)

    async def fail(**kwargs):
        raise DeliveryError("retailer_unavailable")

    service.handoff.send = fail
    accepted = await service.locate_accept(TENANT, body)
    assert accepted["delivery"] == "pending" and not store.locate_orders
    for _ in range(5):
        await service.quote_store.retry_now(TENANT, accepted["request_id"])
        await service.retry_pending(TENANT)
    assert (await service.quote_store.status(TENANT, accepted["request_id"]))["status"] == "needs_person"
    assert not store.locate_orders
    service.handoff = HandoffDouble()
    await service.quote_store.retry_now(TENANT, accepted["request_id"], resume=True)
    await service.retry_pending(TENANT)
    assert len(service.handoff.sent) == 1 and len(store.quotes) == 1 and not store.locate_orders


@pytest.mark.asyncio
async def test_confirmation_is_concurrent_idempotent_and_tenant_scoped(monkeypatch, tmp_path):
    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    accepted = await service.locate_accept(TENANT, body)
    quote_id = accepted["request_id"]
    with pytest.raises(RigError) as denied:
        await service.confirm_store_payment(OTHER, quote_id)
    assert denied.value.status == 404 and not store.locate_orders
    await asyncio.gather(*(service.confirm_store_payment(TENANT, quote_id) for _ in range(8)))
    before = copy.deepcopy(store.locate_orders)
    state = copy.deepcopy((await store.quote_for(TENANT, quote_id))["payload"]["locate_state"])
    assert (await service.confirm_store_payment(TENANT, quote_id))["state"] == "supplier_ordered"
    assert store.locate_orders == before and len(before) == 1 and len(list(tmp_path.glob("*.eml"))) == 1
    assert (await store.quote_for(TENANT, quote_id))["payload"]["locate_state"] == state
    assert state["store_confirmed_at"] and state["auto_order"] is True


@pytest.mark.asyncio
async def test_stale_confirmation_lease_recovers_same_saved_order_and_outbox(monkeypatch, tmp_path):
    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    accepted = await service.locate_accept(TENANT, body)
    quote_id = accepted["request_id"]
    await service.confirm_store_payment(TENANT, quote_id)
    before = copy.deepcopy(store.locate_orders)
    state = (await store.quote_for(TENANT, quote_id))["payload"]["locate_state"]
    await store.locate_state(TENANT, quote_id, {**state, "state": "store_confirmed",
        "attempted_at": (datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()})
    result = await service.confirm_store_payment(TENANT, quote_id)
    assert result["state"] == "supplier_ordered" and store.locate_orders == before
    assert len(list(tmp_path.glob("*.eml"))) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy_state", ["payment_pending", "payment_failed", "payment_refused", "captured", "refunded", "ordered"])
async def test_historical_provider_state_is_preserved_and_cannot_place_an_order(monkeypatch, tmp_path, legacy_state):
    store, service, _, _, _ = await auto_shop(monkeypatch, tmp_path)
    historical = {"state": legacy_state, "payment": {"reference": "placeholder-audit-reference"}}
    await store.add_quote(TENANT, "placeholder-historical", {"locate_state": historical}, {})
    with pytest.raises(RigError):
        await service.confirm_store_payment(TENANT, "placeholder-historical")
    assert (await store.quote_for(TENANT, "placeholder-historical"))["payload"]["locate_state"] == historical
    assert not store.locate_orders


@pytest.mark.asyncio
async def test_quote_items_expose_store_time_offer_time_or_back_order_without_provenance():
    store = await rate_stub(await shop())
    await store.put_retailer(TENANT, "placeholder-store", "placeholder-store@example.invalid", None, "placeholder-store",
                             delivery={"min_days": 2, "max_days": 3})
    service = QuoteService(store, None, HandoffDouble(), MemoryQuotes(store))
    body = {"product_id": "part-1", "contact": {"name": "placeholder-shopper", "email": "placeholder-shopper@example.invalid"}}
    located = await service.quote(TENANT, body)
    assert located["items"][0]["delivery"] == {"ship_days": 10, "eta": "2026-11-12", "back_order": False}
    store.supply_state[TENANT]["offers"] = []
    back_order = await service.quote(TENANT, body)
    assert back_order["items"][0]["delivery"]["back_order"] is True
    product = (await store.products(TENANT))[0]
    product["attributes"] = {"stock": {"status": "in_stock"}}
    await store.upsert_product(TENANT, product)
    stocked = await service.quote(TENANT, body)
    assert stocked["items"][0]["delivery"] == {"min_days": 2, "max_days": 3, "back_order": False}
    for result in (located, back_order, stocked):
        public = json.dumps(shopper_body(result))
        assert all(marker not in public for marker in ("other-store", "other.example", "source_id", "unit_cost", '"cost"'))


@pytest.mark.asyncio
async def test_every_setup_item_carries_delivery_metadata():
    from fixtures.rig_quote_sample import seed
    from rigbox.store import MemoryStore
    store = MemoryStore()
    await seed(store, TENANT)
    await store.put_retailer(TENANT, "placeholder-store", "placeholder-store@example.invalid", None, "placeholder-store",
                             delivery={"min_days": 2, "max_days": 3})
    service = QuoteService(store, None, HandoffDouble(), MemoryQuotes(store))
    setup = (await service.setups(TENANT, "CORE-1"))["setups"][0]
    unavailable = setup["parts"][-1]["product"]["id"]
    row = next(row for row in await store.products(TENANT) if row["sku"] == unavailable)
    await store.upsert_product(TENANT, {**row, "attributes": {"stock": {"status": "out_of_stock"}}})
    quote = await service.quote(TENANT, {"setup": setup, "contact": {"name": "placeholder-shopper", "email": "placeholder-shopper@example.invalid"}})
    assert len(quote["items"]) == len(setup["parts"])
    assert all("delivery" in item for item in quote["items"])
    assert quote["items"][-1]["delivery"]["back_order"] is True
    assert quote["items"][0]["delivery"] == {"min_days": 2, "max_days": 3, "back_order": False}


@pytest.mark.asyncio
async def test_store_delivery_range_is_validated_and_preserved():
    store = await rate_stub(await shop())
    retailer = Retailer(QuoteService(store, None, HandoffDouble(), MemoryQuotes(store)))
    base = {"name": "placeholder-store", "email": "placeholder-store@example.invalid"}
    for bad in (None, {"min_days": 2}, {"min_days": True, "max_days": 3},
                {"min_days": 4, "max_days": 2}, {"min_days": 0, "max_days": 366}):
        with pytest.raises(ValueError):
            await retailer.set_settings(TENANT, {**base, "delivery": bad})
    await retailer.set_settings(TENANT, {**base, "delivery": {"min_days": 2, "max_days": 3}})
    await retailer.set_settings(TENANT, base)
    assert (await store.retailer(TENANT))["delivery"] == {"min_days": 2, "max_days": 3}


@pytest.mark.asyncio
async def test_retailer_http_confirmation_requires_existing_control_auth_and_only_quote_id(monkeypatch, tmp_path):
    store, service, _, _, body = await auto_shop(monkeypatch, tmp_path)
    accepted = await service.locate_accept(TENANT, body)
    monkeypatch.setenv("RIG_RETAILER_KEY", KEY)
    app = FastAPI()
    app.state.rig = service
    mount(app)
    app.include_router(retailer_router)
    request = {"tenant_id": TENANT, "data": {"quote_id": accepted["request_id"]}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://rig-placeholder.invalid") as client:
        url = "/internal/retailer/confirm-store-payment"
        assert (await client.post(url, json=request)).status_code == 401
        headers = {"x-rig-retailer-key": KEY}
        invalid = await client.post(url, json={**request, "data": {**request["data"], "bank_details": "placeholder-refused"}}, headers=headers)
        assert invalid.status_code == 422 and not store.locate_orders
        other = await client.post(url, json={**request, "tenant_id": OTHER}, headers=headers)
        assert other.status_code == 404 and not store.locate_orders
        first = await client.post(url, json=request, headers=headers)
        second = await client.post(url, json=request, headers=headers)
        assert first.status_code == second.status_code == 200
        assert first.json() == second.json() and len(store.locate_orders) == 1
        assert all(marker not in first.text for marker in ("source_id", "vendor_name", "unit_cost", "other.example"))


@pytest.mark.asyncio
async def test_postgres_store_confirmation_schema_twice_and_tenant_isolation(monkeypatch, tmp_path):
    import asyncpg
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from test_rig_optional_auto_order import env

    env(monkeypatch, tmp_path)
    admin, database = _admin_url(), "rig_nopay_placeholder_" + uuid4().hex[:12]
    await _create_database(admin, database)
    pool = None
    try:
        pool = await asyncpg.create_pool(_database_url(admin, database))
        store = PgStore(pool)
        await store.apply_schema()
        await store.apply_schema()
        fixture = await shop()
        await store.upsert_product(TENANT, (await fixture.products(TENANT))[0])
        await store.save_rule(TENANT, {"freight": "5", "duty_percent": "0", "margin_percent": "20"})
        await store.put_retailer(TENANT, "placeholder-store", "placeholder-store@example.invalid", None, "placeholder-store", locate_enabled=True,
                                 auto_order=True, delivery={"min_days": 2, "max_days": 3})
        await store.save_rate(TENANT, "USD", "18", "ZAR")
        supply = SupplyStore(store)
        await supply.source(TENANT, SOURCE)
        from decimal import Decimal
        offers = fixture.supply_state[TENANT]["offers"]
        for offer in offers:
            offer["cost"], offer["quantity"] = Decimal(offer["cost"]), Decimal(offer["quantity"])
        await supply._write(TENANT, SOURCE["id"], offers, datetime.now(timezone.utc))
        service = QuoteService(store, None, HandoffDouble(), PgQuotes(pool))
        service.locate_checker = Live(available("45.00"))
        held = await service.locate_confirm(TENANT, "part-1")
        accepted = await service.locate_accept(TENANT, {"product_id": "part-1", "hold": held["hold"],
            "contact": {"name": "placeholder-shopper", "email": "placeholder-shopper@example.invalid"}})
        assert await pool.fetchval("SELECT count(*) FROM agent_rig.locate_orders") == 0
        with pytest.raises(RigError):
            await service.confirm_store_payment(OTHER, accepted["request_id"])
        await asyncio.gather(*(service.confirm_store_payment(TENANT, accepted["request_id"]) for _ in range(6)))
        assert (await service.confirm_store_payment(TENANT, accepted["request_id"]))["state"] == "supplier_ordered"
        assert await pool.fetchval("SELECT count(*) FROM agent_rig.locate_orders") == 1
        assert await pool.fetchval("SELECT count(*) FROM agent_rig.supplier_purchase_orders WHERE state='sent'") == 1
        assert (await store.retailer(TENANT))["delivery"] == {"min_days": 2, "max_days": 3}
        assert len(list(tmp_path.glob("*.eml"))) == 1
    finally:
        if pool is not None:
            await pool.close()
        await _drop_database(admin, database)
