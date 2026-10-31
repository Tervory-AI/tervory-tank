"""Optional pay on Accept: provider-agnostic PaymentAdapter, test mode only.

create_intent on Accept, capture, refund, and HMAC-SHA256 webhook verification,
all behind payments.guard (RIG_LOCATE_PAYMENTS_MODE=test, no live-looking key).
The built-in TestAdapter runs Accept -> pay -> auto-order -> refund-on-failure
end to end. No provider SDK, no keys, no live mode.
"""
import asyncio
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox import payments
from rigbox.api import mount
from rigbox.quotes.privacy import shopper_body
from rigbox.quotes.senders import DeliveryError
from rigbox.service import RigError
from test_rig_locate_checkout import TENANT
from test_rig_optional_auto_order import auto_shop, no_network_mail  # noqa: F401  (autouse SMTP refusal)

TEST_ENV = {"RIG_LOCATE_PAYMENTS_MODE": "test"}


async def paid_shop(monkeypatch, outbox, adapter=None, **options):
    store, service, orders, held, body = await auto_shop(monkeypatch, outbox, **options)
    service.payments = adapter or payments.TestAdapter()
    return store, service, orders, held, body


def kinds(adapter):
    return [kind for kind, _key in adapter.calls]


# 1. Webhook signature verification.

def test_webhook_signature_accepts_only_a_fresh_exact_hmac():
    adapter = payments.TestAdapter()
    body, header = adapter.event("evt_1", "charge.refunded", f"rig:{TENANT}:req_{'a' * 32}")
    assert payments.verify_webhook(adapter, body, header, env=TEST_ENV)["id"] == "evt_1"
    stamp = int(header.split(",")[0][2:])
    rotated = f"t={stamp},v1={'0' * 64},v1={header.split('v1=')[1]}"  # any valid v1 passes (secret rotation)
    assert payments.verify_webhook(adapter, body, rotated, env=TEST_ENV)["type"] == "charge.refunded"
    other = payments.TestAdapter()
    bad = [
        (body.replace(b"evt_1", b"evt_2"), header, "webhook_signature"),          # tampered body
        (body, other.event("evt_1", "charge.refunded", "x")[1], "webhook_signature"),  # wrong secret
        (body, "", "webhook_signature"),
        (body, "v1=" + header.split("v1=")[1], "webhook_signature"),             # no timestamp
        (body, f"t={stamp}", "webhook_signature"),                               # no signature
        (body, header.replace(f"t={stamp}", f"t={stamp + 1}"), "webhook_signature"),
        (b"x" * (payments.WEBHOOK_MAX_BYTES + 1), header, "webhook_signature"),
    ]
    for raw, sig, code in bad:
        with pytest.raises(payments.PaymentRefused, match=code):
            payments.verify_webhook(adapter, raw, sig, env=TEST_ENV)
    old_body, old = adapter.event("evt_old", "charge.refunded", "x", timestamp=int(time.time()) - 301)
    future_body, future = adapter.event("evt_new", "charge.refunded", "x", timestamp=int(time.time()) + 301)
    for raw, sig in ((old_body, old), (future_body, future)):
        with pytest.raises(payments.PaymentRefused, match="webhook_stale"):
            payments.verify_webhook(adapter, raw, sig, env=TEST_ENV)
    unsigned = b'{"type":"charge.refunded","data":{}}'
    with pytest.raises(payments.PaymentRefused, match="webhook_payload"):
        payments.verify_webhook(adapter, unsigned, payments.sign(adapter.webhook_secret(), unsigned, int(time.time())),
                                env=TEST_ENV)


def test_webhook_verification_sits_behind_the_test_mode_guard():
    adapter = payments.TestAdapter()
    body, header = adapter.event("evt_1", "charge.refunded", "x")
    for env in ({}, {"RIG_LOCATE_PAYMENTS_MODE": "live"}):
        with pytest.raises(payments.PaymentRefused, match="payments_mode"):
            payments.verify_webhook(adapter, body, header, env=env)
    with pytest.raises(payments.PaymentRefused, match="payments_not_configured"):
        payments.verify_webhook(None, body, header, env=TEST_ENV)
    live = payments.TestAdapter(secret="whsec_live_example")
    with pytest.raises(payments.PaymentRefused, match="live_key_refused"):
        payments.verify_webhook(live, *live.event("evt_1", "charge.refunded", "x"), env=TEST_ENV)
    with pytest.raises(payments.PaymentRefused, match="live_key_refused"):
        payments.verify_webhook(adapter, body, header, env={**TEST_ENV, "STRIPE_SECRET_KEY": "sk_live_example"})


# 2. Adapter idempotency and live refusal.

@pytest.mark.asyncio
async def test_test_adapter_moves_money_at_most_once_per_key():
    adapter = payments.TestAdapter()
    first = await payments.create_intent(adapter, amount="1125.00", currency="ZAR", token="tok_test_visa",
                                         reference="rig:t:q1", metadata={}, env=TEST_ENV)
    again = await payments.create_intent(adapter, amount="1125.00", currency="ZAR", token="tok_test_visa",
                                         reference="rig:t:q1", metadata={}, env=TEST_ENV)
    assert first == again and first.status == "requires_capture" and first.amount == Decimal("1125.00")
    charge = await payments.capture_intent(adapter, first, reference="rig:t:q1", env=TEST_ENV)
    assert charge == await payments.capture_intent(adapter, first, reference="rig:t:q1", env=TEST_ENV) and charge.status == "captured"
    refund = await payments.refund(adapter, charge, "order_failed", env=TEST_ENV)
    assert refund == await payments.refund(adapter, charge, "order_failed", env=TEST_ENV)
    assert kinds(adapter) == ["create_intent", "capture", "refund"]
    assert adapter.calls[0][1] == "rig:t:q1:intent" and adapter.calls[1][1] == "rig:t:q1:capture"


class LiveAdapter(payments.TestAdapter):
    """Claims success but cannot prove test mode."""

    async def create_intent(self, **kwargs):
        intent = await super().create_intent(**kwargs)
        return payments.Intent(intent.reference, intent.status, intent.amount, intent.currency, False)


@pytest.mark.asyncio
async def test_live_mode_is_refused_before_any_adapter_call(monkeypatch, tmp_path):
    for name, value in (("RIG_LOCATE_PAYMENTS_MODE", "live"), ("STRIPE_SECRET_KEY", "sk_live_example")):
        store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
        monkeypatch.setenv(name, value)
        with pytest.raises(RigError) as raised:
            await service.locate_accept(TENANT, body)
        assert raised.value.status == 503 and service.payments.calls == [] and store.locate_orders == {}
        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=LiveAdapter())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 402 and kinds(service.payments) == ["create_intent"] and store.locate_orders == {}
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_refused"


def test_the_test_adapter_is_not_wired_into_the_app_and_there_is_no_live_mode():
    sources = [path.read_text() for path in (ROOT / "agents" / "rig").rglob("*.py") if path.name != "payments.py"]
    assert not any("TestAdapter" in text for text in sources)
    code = (ROOT / "agents" / "rig" / "rigbox" / "payments.py").read_text()
    for word in ("import stripe", "import paystack", "httpx", "requests", 'MODE_ENV, "") == "live"', "live_mode"):
        assert word not in code, word


# 3. Accept -> pay -> auto-order -> refund on failure, end to end.

@pytest.mark.asyncio
async def test_accept_pays_then_auto_orders_once(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, body)
    state = store.quotes[-1]["payload"]["locate_state"]
    assert result["state"] == "ordered" and result["payment"]["test"] is True
    assert result["payment"]["reference"].startswith("ch_test_")
    assert state["state"] == "supplier_ordered" and state["payment"]["provider"] == "test-adapter"
    assert kinds(service.payments) == ["create_intent", "capture"] and len(list(tmp_path.iterdir())) == 1
    saved = await store.locate_order(TENANT, result["request_id"])  # Rig's own order + PO, no ERP
    assert saved["order"]["state"] == "placed" and saved["order"]["price"] == result["price"]["amount"]
    assert saved["purchase_order"]["state"] == "sent"
    charged = service.payments.charges[f"rig:{TENANT}:{result['request_id']}:capture"]
    assert charged.amount == Decimal(result["price"]["amount"]) and charged.currency == result["price"]["currency"]
    text = json.dumps(shopper_body(result))
    for marker in ("pi_test_", "test-adapter", "other.example", "Other Store", "orders@", "45.00"):
        assert marker not in text
    with pytest.raises(RigError) as raised:  # replayed Accept: hold is single use, nothing charged again
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 410 and kinds(service.payments) == ["create_intent", "capture"]
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_supplier_order_failure_refunds_the_captured_payment(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, fail_supplier=True)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    state = store.quotes[-1]["payload"]["locate_state"]
    assert raised.value.status == 502 and state["state"] == "supplier_order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "refund"] and list(tmp_path.iterdir()) == []
    assert list(service.payments.refunds.values())[0].status == "refunded"
    saved = await store.locate_order(TENANT, store.quotes[-1]["id"])
    assert (saved["order"]["state"], saved["purchase_order"]["state"]) == ("cancelled", "cancelled")


@pytest.mark.asyncio
async def test_order_failure_refunds_the_captured_payment(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)

    async def fail(**kwargs):
        raise DeliveryError("order_unavailable")
    service.fulfilment.place_located_order = fail
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "refund"] and store.locate_orders == {}
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("token,calls", [("tok_decline", ["create_intent"]),
                                         ("tok_capture_fails", ["create_intent", "capture", "cancel_intent"])])
async def test_declined_or_failed_capture_places_no_order(monkeypatch, tmp_path, token, calls):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, {**body, "payment_token": token})
    assert raised.value.status == 402 and kinds(service.payments) == calls
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_failed"
    assert store.locate_orders == {} and list(tmp_path.iterdir()) == []
    if token == "tok_capture_fails":  # the authorization is voided, not left to expire
        assert store.quotes[-1]["payload"]["locate_state"]["cancel"] == {"status": "canceled"}
        assert list(service.payments.canceled.values())[0].status == "canceled"


class CancelFailsOnce(payments.TestAdapter):
    """The cancel call after a failed capture is lost once (provider outage)."""

    def __init__(self) -> None:
        super().__init__()
        self.cancel_failures = 1

    async def cancel_intent(self, *, intent, idempotency_key):
        if self.cancel_failures:
            self.cancel_failures -= 1
            raise ConnectionError("cancel response lost")
        return await super().cancel_intent(intent=intent, idempotency_key=idempotency_key)


def later(minutes=20):
    from datetime import datetime, timedelta, timezone
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


@pytest.mark.asyncio
async def test_a_lost_capture_response_is_resolved_by_the_cancel_call(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, {**body, "payment_token": "tok_capture_lost"})
    # cancel reports "captured": the shopper was charged, so the order goes ahead (once).
    assert result["state"] == "ordered"
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent"]
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "supplier_ordered"
    assert service.payments.refunds == {} and len(list(tmp_path.iterdir())) == 1


@pytest.mark.asyncio
async def test_capture_failure_with_a_lost_cancel_is_settled_by_reconcile(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=CancelFailsOnce())
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, {**body, "payment_token": "tok_capture_fails"})
    state = store.quotes[-1]["payload"]["locate_state"]
    assert raised.value.status == 502 and state["state"] == "payment_pending"
    assert state["note"] == "capture_unconfirmed" and store.locate_orders == {}
    assert (await service.reconcile_payments(TENANT))["reconciled"] == []  # too recent: maybe in flight
    fixed = await service.reconcile_payments(TENANT, now=later())
    assert fixed == {"checked": 1, "reconciled": [{"quote_id": store.quotes[-1]["id"], "from": "payment_pending",
                                                   "to": "payment_failed"}]}
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["reconciled"] is True and state["cancel"] == {"status": "canceled"}
    assert service.payments.refunds == {} and store.locate_orders == {}
    assert await service.reconcile_payments(TENANT, now=later()) == {"checked": 0, "reconciled": []}


@pytest.mark.asyncio
async def test_reconcile_refunds_a_paid_quote_with_no_order_once(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)

    async def crash(**kwargs):
        raise RuntimeError("worker killed after capture")
    service.fulfilment.place_located_order = crash
    with pytest.raises(RuntimeError):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "paid"
    assert (await service.reconcile_payments(TENANT, now=later(5)))["reconciled"] == []
    both = await asyncio.gather(service.reconcile_payments(TENANT, now=later()),
                                service.reconcile_payments(TENANT, now=later()))
    assert sum(len(item["reconciled"]) for item in both) == 1  # claimed once
    state = store.quotes[-1]["payload"]["locate_state"]
    assert state["state"] == "order_failed_refunded" and state["refund"] == {"status": "refunded"}
    assert kinds(service.payments) == ["create_intent", "capture", "refund"]
    assert [item["quote_id"] for result in both for item in result["reconciled"]] == [quote_id]
    assert store.locate_orders == {}


@pytest.mark.asyncio
async def test_reconcile_records_an_order_placed_before_the_crash_and_never_refunds_it(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    result = await service.locate_accept(TENANT, body)
    row = store.quotes[-1]
    row["payload"]["locate_state"] = {**row["payload"]["locate_state"], "state": "paid"}  # crash before "ordered"
    fixed = await service.reconcile_payments(TENANT, now=later())
    assert fixed["reconciled"] == [{"quote_id": result["request_id"], "from": "paid", "to": "ordered"}]
    state = row["payload"]["locate_state"]
    assert state["order"].startswith("RIG-") and state["purchase_order"].startswith("PO-")
    assert "refund" not in kinds(service.payments)


@pytest.mark.asyncio
async def test_reconcile_refunds_a_pending_intent_that_was_captured_before_the_crash(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    original = service.payments.capture_intent

    async def capture_then_crash(**kwargs):
        await original(**kwargs)
        raise SystemExit("worker killed after capture")  # not caught by Accept
    service.payments.capture_intent = capture_then_crash
    with pytest.raises(SystemExit):
        await service.locate_accept(TENANT, body)
    service.payments.capture_intent = original
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "payment_pending"
    fixed = await service.reconcile_payments(TENANT, now=later())
    assert fixed["reconciled"][0]["to"] == "order_failed_refunded"
    assert kinds(service.payments) == ["create_intent", "capture", "cancel_intent", "refund"]
    assert list(service.payments.refunds.values())[0].status == "refunded" and store.locate_orders == {}


@pytest.mark.asyncio
async def test_reconcile_is_test_mode_only(monkeypatch, tmp_path):
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "live")
    with pytest.raises(payments.PaymentRefused):
        await service.reconcile_payments(TENANT, now=later())
    assert service.payments.calls == []


@pytest.mark.asyncio
async def test_one_shot_providers_still_work(monkeypatch, tmp_path):
    store, service, orders, _, body = await auto_shop(monkeypatch, tmp_path)  # #463 FakeProvider, no intents
    assert not payments.intents(service.payments)
    assert (await service.locate_accept(TENANT, body))["state"] == "ordered"
    assert len(service.payments.captured) == 1


# 4. Webhook route: signed events recorded once on their quote.

def test_webhook_route_records_signed_events_once(monkeypatch, tmp_path):
    store, service, orders, _, body = asyncio.run(paid_shop(monkeypatch, tmp_path))
    quote_id = asyncio.run(service.locate_accept(TENANT, body))["request_id"]
    adapter = service.payments
    app = FastAPI()
    app.state.rig = service
    mount(app)
    route = "/v1/rig/locate/payments/webhook"
    raw, signature = adapter.event("evt_refund_1", "charge.refunded", f"rig:{TENANT}:{quote_id}")
    headers = {payments.SIGNATURE_HEADER: signature, "content-type": "application/json"}
    with TestClient(app) as client:
        first = client.post(route, content=raw, headers=headers)
        again = client.post(route, content=raw, headers=headers)
        forged = client.post(route, content=raw.replace(b"refunded", b"captured"), headers=headers)
        unsigned = client.post(route, content=raw)
        unknown = client.post(route, content=adapter.event("evt_2", "charge.refunded", "rig:nope")[0],
                              headers={payments.SIGNATURE_HEADER: adapter.event("evt_2", "charge.refunded",
                                                                                 "rig:nope")[1]})
        monkeypatch.setenv("RIG_LOCATE_PAYMENTS_MODE", "live")
        refused = client.post(route, content=raw, headers=headers)
    assert first.status_code == 200 and first.json() == {"received": True, "recorded": True}
    assert again.json() == {"received": True, "recorded": False}
    assert forged.status_code == 400 and unsigned.status_code == 400 and refused.status_code == 503
    assert unknown.json() == {"received": True, "recorded": False}
    events = store.quotes[-1]["payload"]["payment_events"]
    assert [event["id"] for event in events] == ["evt_refund_1"] and events[0]["type"] == "charge.refunded"
    assert store.quotes[-1]["payload"]["locate_state"]["state"] == "supplier_ordered"  # audit only


@pytest.mark.asyncio
async def test_real_postgres_payment_events_are_deduplicated_atomically():
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    admin = _admin_url()
    name = "rig_pay_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            quote_id = "req_" + uuid4().hex
            with tenant_scope(TENANT):
                await store.add_quote(TENANT, quote_id, {"kind": "product"}, {"name": "T"})
                event = {"id": "evt_1", "type": "charge.refunded", "received_at": "2026-10-31T00:00:00+00:00"}
                results = await asyncio.gather(*(store.payment_event(TENANT, quote_id, event) for _ in range(5)))
                second = await store.payment_event(TENANT, quote_id, {**event, "id": "evt_2"})
                other = await store.payment_event(str(uuid4()), quote_id, {**event, "id": "evt_3"})
                saved = await pool.fetchval("SELECT payload->'payment_events' FROM agent_rig.quotes WHERE id = $1",
                                            quote_id)
            assert sorted(results) == [False, False, False, False, True] and second is True and other is False
            assert [item["id"] for item in json.loads(saved)] == ["evt_1", "evt_2"]
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_real_postgres_reconcile_claims_each_stuck_quote_once(monkeypatch, tmp_path):
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    _, service, _, _, _ = await paid_shop(monkeypatch, tmp_path)
    admin = _admin_url()
    name = "rig_payrec_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            service.store = store
            price = {"amount": "1125.00", "currency": "ZAR"}
            paid, pending, done = ("req_" + uuid4().hex for _ in range(3))
            with tenant_scope(TENANT):
                for quote_id, state in ((paid, {"state": "paid", "paid_at": "2026-10-31T00:00:00+00:00",
                                                 "price": price, "payment": {"reference": "ch_test_pg"}}),
                                        (pending, {"state": "payment_pending", "pending_at": later(-1).isoformat(),
                                                   "price": price, "payment": {"intent": "pi_test_pg"}}),
                                        (done, {"state": "supplier_ordered", "price": price})):
                    await store.add_quote(TENANT, quote_id, {"kind": "product", "locate_state": state}, {"name": "T"})
                listed = await store.open_locate_payments(TENANT)
                assert [quote_id for quote_id, _ in listed] == [paid, pending]
                assert await store.open_locate_payments(str(uuid4())) == []
                old = listed[0][1]
                swaps = await asyncio.gather(*(store.swap_locate_state(TENANT, paid, old, {**old, "n": i})
                                               for i in range(5)))
                assert sorted(swaps) == [False, False, False, False, True]
                await store.swap_locate_state(TENANT, paid, (await store.open_locate_payments(TENANT))[0][1], old)
                both = await asyncio.gather(service.reconcile_payments(TENANT), service.reconcile_payments(TENANT))
                settled = await pool.fetch("SELECT id, payload->'locate_state'->>'state' AS state"
                                           " FROM agent_rig.quotes ORDER BY created_at")
            assert [item for result in both for item in result["reconciled"]] == [
                {"quote_id": paid, "from": "paid", "to": "order_failed_refunded"}]  # pending is too recent
            assert {row["id"]: row["state"] for row in settled} == {
                paid: "order_failed_refunded", pending: "payment_pending", done: "supplier_ordered"}
            assert kinds(service.payments) == ["refund"]
            print("RIG_PAY_RECONCILE_PG", json.dumps(both, sort_keys=True))
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)

