"""Follow-ups to pay on Accept (#511 review, non-blocking items A-D) and the
in-memory order-number check (#528 nit). Synthetic values only."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox.fulfilment import RigOrders
from rigbox.quotes.senders import DeliveryError
from rigbox.service import RigError
from rigbox.store import MemoryStore
from test_rig_locate_checkout import TENANT
from test_rig_optional_auto_order import no_network_mail  # noqa: F401  (autouse SMTP refusal)
from test_rig_optional_pay_on_accept import RefundFailsOnce, failing_accept, kinds, later, paid_shop

PRICE = {"amount": "1125.00", "currency": "ZAR"}
OLD = "2026-10-01T00:00:00+00:00"


def state_of(store, quote_id):
    return next(row for row in store.quotes if row["id"] == quote_id)["payload"]["locate_state"]


# A. Flagged quotes never starve newer refunds.

@pytest.mark.asyncio
async def test_a_backlog_of_flagged_quotes_never_starves_a_newer_refund(monkeypatch, tmp_path):
    store, service, error = await failing_accept(monkeypatch, tmp_path, RefundFailsOnce(), "supplier")
    newest = store.quotes[-1]["id"]
    assert state_of(store, newest)["state"] == "refund_due"
    # 100 older quotes a person must settle: cancelling with no order, so each
    # run flags them again. Put them ahead of the newer refund (oldest first).
    flagged = [f"req_flag{i:03d}" for i in range(100)]
    rows = []
    for quote_id in flagged:
        state = {"state": "cancelling", "cancelling_at": OLD, "cancel_reason": "supplier_order_failed",
                 "price": PRICE, "payment": {"reference": "ch_test_flag"}, "needs_review": True,
                 "reconcile_error": True}
        rows.append({"tenant_id": TENANT, "id": quote_id, "payload": {"kind": "product", "locate_state": state},
                     "contact": {}, "sent_at": None})
    store.quotes[:0] = rows
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": newest, "from": "refund_due", "to": "supplier_order_failed_refunded"}]
    assert sorted(result["needs_review"]) == flagged  # still listed for a person, every run
    assert kinds(service.payments).count("refund") == 1
    again = await service.reconcile_payments(TENANT, now=later(60))
    assert again["reconciled"] == [] and sorted(again["needs_review"]) == flagged


@pytest.mark.asyncio
async def test_memory_store_lists_flagged_quotes_only_in_their_own_pass():
    store = MemoryStore()
    for quote_id, extra in (("q_plain", {}), ("q_flag", {"needs_review": True}), ("q_false", {"needs_review": False})):
        await store.add_quote(TENANT, quote_id, {"kind": "product", "locate_state": {"state": "refund_due", **extra}},
                              {"name": "T"})
    assert [quote for quote, _ in await store.open_locate_payments(TENANT)] == ["q_plain", "q_false"]
    assert [quote for quote, _ in await store.open_locate_payments(TENANT, flagged=True)] == ["q_flag"]


@pytest.mark.asyncio
async def test_real_postgres_lists_flagged_quotes_only_in_their_own_pass():
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url, _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    admin = _admin_url()
    name = "rig_payflag_" + uuid4().hex[:12]
    await _create_database(admin, name)
    try:
        pool = await asyncpg.create_pool(_database_url(admin, name))
        try:
            store = PgStore(pool)
            await store.apply_schema()
            ids = {key: "req_" + uuid4().hex for key in ("plain", "flag", "false", "done")}
            with tenant_scope(TENANT):
                for key, state in (("plain", {"state": "refund_due"}),
                                   ("flag", {"state": "cancelling", "needs_review": True}),
                                   ("false", {"state": "paid", "needs_review": False}),
                                   ("done", {"state": "supplier_ordered", "needs_review": True})):
                    await store.add_quote(TENANT, ids[key], {"kind": "product", "locate_state": state}, {"name": "T"})
                plain = [quote for quote, _ in await store.open_locate_payments(TENANT)]
                flag = [quote for quote, _ in await store.open_locate_payments(TENANT, flagged=True)]
                one = await store.open_locate_payments(TENANT, 1)
            assert plain == [ids["plain"], ids["false"]] and flag == [ids["flag"]] and len(one) == 1
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


# B. An unrecorded cancel at Accept is left at cancelling, never refunded there.

@pytest.mark.asyncio
async def test_an_unrecorded_cancel_at_accept_is_left_cancelling_and_finished_by_reconcile(monkeypatch, tmp_path):
    async def send_refused(self, **kwargs):
        raise DeliveryError("order_mode")
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "send_supplier_order", send_refused)
    real, failures = store.cancel_locate_order, [1]

    async def blip(tenant_id, quote_id, reason):
        if failures[0]:
            failures[0] -= 1
            raise ConnectionError("database blip")
        return await real(tenant_id, quote_id, reason)
    monkeypatch.setattr(store, "cancel_locate_order", blip)
    with pytest.raises(RigError) as raised:
        await service.locate_accept(TENANT, body)
    assert raised.value.status == 502 and "will be refunded" in raised.value.message
    quote_id = store.quotes[-1]["id"]
    assert state_of(store, quote_id)["state"] == "cancelling"
    assert "refund" not in kinds(service.payments)  # no refund while the order may still stand
    row = store.locate_orders[(TENANT, quote_id)]
    assert (row["order"]["state"], row["purchase_order"]["state"]) == ("placed", "draft")
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "cancelling",
                                     "to": "supplier_order_failed_refunded"}]
    row = store.locate_orders[(TENANT, quote_id)]
    assert (row["order"]["state"], row["purchase_order"]["state"]) == ("cancelled", "cancelled")
    assert kinds(service.payments).count("refund") == 1
    assert (await service.reconcile_payments(TENANT, now=later(60)))["reconciled"] == []


# C. A quote that settles drops needs_review and reconcile_error.

@pytest.mark.asyncio
async def test_review_flags_are_cleared_when_a_flagged_quote_settles(monkeypatch, tmp_path):
    real_place = RigOrders.place_located_order

    async def saved_then_raises(self, **kwargs):
        await real_place(self, **kwargs)
        raise DeliveryError("order_mismatch")
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    monkeypatch.setattr(RigOrders, "place_located_order", saved_then_raises)
    with pytest.raises(RigError):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    first = await service.reconcile_payments(TENANT, now=later(30))
    assert first["needs_review"] == [quote_id]
    assert state_of(store, quote_id)["needs_review"] is True and state_of(store, quote_id)["reconcile_error"] is True
    del store.locate_orders[(TENANT, quote_id)]  # a person removed the stray order
    second = await service.reconcile_payments(TENANT, now=later(60))
    assert second["reconciled"] == [{"quote_id": quote_id, "from": "refund_due", "to": "order_failed_refunded"}]
    state = state_of(store, quote_id)
    assert state["state"] == "order_failed_refunded"
    assert "needs_review" not in state and "reconcile_error" not in state


@pytest.mark.asyncio
async def test_reconcile_error_is_cleared_when_a_retried_refund_settles(monkeypatch, tmp_path):
    class Crash(Exception):
        pass

    async def killed(self, **kwargs):
        raise Crash()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path, adapter=RefundFailsOnce())
    monkeypatch.setattr(RigOrders, "send_supplier_order", killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    await service.reconcile_payments(TENANT, now=later(30))
    assert state_of(store, quote_id)["reconcile_error"] is True
    await service.reconcile_payments(TENANT, now=later(60))
    state = state_of(store, quote_id)
    assert state["state"] == "supplier_order_failed_refunded" and "reconcile_error" not in state


# D. The reconciler skips the outbox check when Accept's send refused before writing.

@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["outbox_not_configured", "order_mode"])
async def test_reconcile_cancels_an_unsent_po_when_the_send_refused_before_writing(monkeypatch, tmp_path, code):
    class Killed(Exception):
        pass

    async def send_refused(self, **kwargs):
        raise DeliveryError(code)

    async def killed(self, *args, **kwargs):
        raise Killed()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    real_cancel = RigOrders.cancel
    monkeypatch.setattr(RigOrders, "send_supplier_order", send_refused)
    monkeypatch.setattr(RigOrders, "cancel", killed)
    with pytest.raises(Killed):
        await service.locate_accept(TENANT, body)
    monkeypatch.setattr(RigOrders, "cancel", real_cancel)
    quote_id = store.quotes[-1]["id"]
    assert state_of(store, quote_id)["state"] == "cancelling" and state_of(store, quote_id)["error"] == code
    monkeypatch.delenv("RIG_LOCATE_OUTBOX_DIR")  # the outbox can't be checked now
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "cancelling",
                                     "to": "supplier_order_failed_refunded"}]
    assert result["needs_review"] == [] and kinds(service.payments).count("refund") == 1
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "cancelled"


@pytest.mark.asyncio
async def test_reconcile_stays_strict_for_other_send_errors(monkeypatch, tmp_path):
    class Killed(Exception):
        pass

    async def send_fails(self, **kwargs):
        raise DeliveryError("smtp_down")  # may have written: the outbox must be checked

    async def killed(self, *args, **kwargs):
        raise Killed()
    store, service, orders, _, body = await paid_shop(monkeypatch, tmp_path)
    real_cancel = RigOrders.cancel
    monkeypatch.setattr(RigOrders, "send_supplier_order", send_fails)
    monkeypatch.setattr(RigOrders, "cancel", killed)
    with pytest.raises(Killed):
        await service.locate_accept(TENANT, body)
    monkeypatch.setattr(RigOrders, "cancel", real_cancel)
    quote_id = store.quotes[-1]["id"]
    monkeypatch.delenv("RIG_LOCATE_OUTBOX_DIR")
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [] and result["needs_review"] == [quote_id]
    assert "refund" not in kinds(service.payments)
    assert store.locate_orders[(TENANT, quote_id)]["order"]["state"] == "placed"


# #528 nit: the in-memory store enforces unique order numbers, like Postgres.

@pytest.mark.asyncio
async def test_memory_store_refuses_an_order_number_taken_by_another_quote(monkeypatch):
    from rigbox import fulfilment
    from test_rig_optional_blind_ship import LOCATED, PRICE as BLIND_PRICE
    store, sandbox = MemoryStore(), {"RIG_LOCATE_ORDER_MODE": "sandbox"}
    orders = RigOrders(store)
    await orders.place_located_order(tenant_id=TENANT, quote_id="req_a", located=LOCATED, price=BLIND_PRICE,
                                     env=sandbox)
    taken = fulfilment.numbers(TENANT, "req_a")
    monkeypatch.setattr(fulfilment, "numbers", lambda tenant, quote: taken)  # forced collision
    with pytest.raises(DeliveryError, match="order_mismatch"):
        await orders.place_located_order(tenant_id=TENANT, quote_id="req_b", located=LOCATED, price=BLIND_PRICE,
                                         env=sandbox)
    assert await store.locate_order(TENANT, "req_b") is None and len(store.locate_orders) == 1
    other = "00000000-0000-4000-8000-000000000999"  # another tenant may reuse the number
    await orders.place_located_order(tenant_id=other, quote_id="req_b", located=LOCATED, price=BLIND_PRICE,
                                     env=sandbox)
    assert len(store.locate_orders) == 2
    print("RIG_PAY_FOLLOWUP_OK", json.dumps(sorted(key[1] for key in store.locate_orders)))
