"""Pay on Accept follow-ups 2 (#530 review): the reconciler's lists rotate by
last attempt, stranded-refund drafts are auto-order only, the supplier PO
number clash matches between stores, and "checked" is documented.
Synthetic values only."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox import fulfilment
from rigbox.fulfilment import RigOrders
from rigbox.quotes.senders import DeliveryError
from rigbox.store import MemoryStore
from test_rig_locate_checkout import TENANT
from test_rig_optional_auto_order import no_network_mail  # noqa: F401  (autouse SMTP refusal)
from test_rig_optional_blind_ship import LOCATED, PRICE as BLIND_PRICE
from test_rig_optional_pay_on_accept import RefundFailsOnce, failing_accept, kinds, later, paid_shop

PRICE = {"amount": "1125.00", "currency": "ZAR"}
OLD = "2026-10-01T00:00:00+00:00"
SANDBOX = {"RIG_LOCATE_ORDER_MODE": "sandbox"}


def state_of(store, quote_id):
    return next(row for row in store.quotes if row["id"] == quote_id)["payload"]["locate_state"]


def raw(quote_id, state):
    return {"tenant_id": TENANT, "id": quote_id, "payload": {"kind": "product", "locate_state": state},
            "contact": {}, "sent_at": None}


class StuckRefunds(RefundFailsOnce):
    """Refunds for req_stuck* quotes fail on every call; the first other
    refund (at Accept) fails once, then others go through."""

    async def refund(self, **kwargs):
        if ":req_stuck" in kwargs["idempotency_key"]:
            raise ConnectionError("provider unreachable")
        return await super().refund(**kwargs)


# 1. Both lists rotate by last attempt, least recent first.

@pytest.mark.asyncio
async def test_unflagged_refunds_that_fail_every_run_rotate_behind_a_newer_refund(monkeypatch, tmp_path):
    adapter = StuckRefunds()
    store, service, _ = await failing_accept(monkeypatch, tmp_path, adapter, "order")
    newest = store.quotes[-1]["id"]
    assert state_of(store, newest)["state"] == "refund_due"
    stuck = [f"req_stuck{i:03d}" for i in range(100)]  # older than newest, refund fails every run
    store.quotes[:0] = [raw(quote_id, {"state": "refund_due", "refund_due_at": OLD,
                                       "refund_reason": "supplier_order_failed", "price": PRICE,
                                       "payment": {"reference": "ch_test_stuck"}}) for quote_id in stuck]
    first = await service.reconcile_payments(TENANT, now=later(30))
    assert first["reconciled"] == [] and state_of(store, newest)["state"] == "refund_due"
    assert all(state_of(store, quote_id)["reconcile_error"] is True for quote_id in stuck)
    second = await service.reconcile_payments(TENANT, now=later(60))
    assert second["reconciled"] == [{"quote_id": newest, "from": "refund_due", "to": "order_failed_refunded"}]
    assert all(state_of(store, quote_id)["state"] == "refund_due" for quote_id in stuck)


@pytest.mark.asyncio
async def test_a_flagged_quote_behind_120_older_flagged_quotes_is_reached(monkeypatch, tmp_path):
    store, service, _ = await failing_accept(monkeypatch, tmp_path, RefundFailsOnce(), "supplier")
    target = store.quotes[-1]["id"]
    store.quotes[-1]["payload"]["locate_state"].update(needs_review=True, reconcile_error=True)
    flagged = [f"req_flag{i:03d}" for i in range(120)]  # cancelling, no order: flagged again every run
    store.quotes[:0] = [raw(quote_id, {"state": "cancelling", "cancelling_at": OLD,
                                       "cancel_reason": "supplier_order_failed", "price": PRICE,
                                       "payment": {"reference": "ch_test_flag"}, "needs_review": True,
                                       "reconcile_error": True}) for quote_id in flagged]
    first = await service.reconcile_payments(TENANT, now=later(30))
    assert first["reconciled"] == [] and len(first["needs_review"]) == 100
    second = await service.reconcile_payments(TENANT, now=later(60))
    assert second["reconciled"] == [{"quote_id": target, "from": "refund_due", "to": "supplier_order_failed_refunded"}]
    assert set(first["needs_review"]) | set(second["needs_review"]) == set(flagged)  # all still shown to a person
    state = state_of(store, target)
    assert "needs_review" not in state and "reconcile_error" not in state
    assert kinds(service.payments).count("refund") == 1


@pytest.mark.asyncio
async def test_memory_store_lists_least_recently_tried_first():
    store = MemoryStore()
    for quote_id in ("q_a", "q_b", "q_c"):
        await store.add_quote(TENANT, quote_id, {"kind": "product", "locate_state": {"state": "refund_due"}},
                              {"name": "T"})
    assert [quote for quote, _ in await store.open_locate_payments(TENANT)] == ["q_a", "q_b", "q_c"]
    await store.locate_attempt(TENANT, "q_a", later(30))
    await store.locate_attempt(TENANT, "q_b", later(20))
    await store.locate_attempt("00000000-0000-4000-8000-000000000999", "q_c", later(40))  # other tenant: no-op
    assert [quote for quote, _ in await store.open_locate_payments(TENANT)] == ["q_c", "q_b", "q_a"]
    assert [quote for quote, _ in await store.open_locate_payments(TENANT, 1)] == ["q_c"]


# 2. The stranded-refund path lists auto-order drafts only.

@pytest.mark.asyncio
@pytest.mark.parametrize("manual", [99, 100, 250])
async def test_manual_drafts_never_block_a_stranded_auto_order_refund(monkeypatch, tmp_path, manual):
    class Crash(Exception):
        pass

    async def killed(self, **kwargs):
        raise Crash()
    store, service, _, _, body = await paid_shop(monkeypatch, tmp_path)
    orders = RigOrders(store)
    for i in range(manual):  # placed without auto-order: they stay draft for a person, older than the quote
        await orders.place_located_order(tenant_id=TENANT, quote_id=f"req_manual{i:03d}", located=LOCATED,
                                         price=BLIND_PRICE, env=SANDBOX)
    monkeypatch.setattr(RigOrders, "send_supplier_order", killed)
    with pytest.raises(Crash):
        await service.locate_accept(TENANT, body)
    quote_id = store.quotes[-1]["id"]
    assert state_of(store, quote_id)["state"] == "ordered"
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["reconciled"] == [{"quote_id": quote_id, "from": "ordered", "to": "supplier_order_failed_refunded"}]
    assert kinds(service.payments).count("refund") == 1
    manual_rows = [row for (_t, quote), row in store.locate_orders.items() if quote.startswith("req_manual")]
    assert len(manual_rows) == manual
    assert {(row["order"]["state"], row["purchase_order"]["state"]) for row in manual_rows} == {("placed", "draft")}
    print("RIG_PAY_FOLLOWUP2_DRAFTS", manual, json.dumps(result["reconciled"]))


@pytest.mark.asyncio
async def test_memory_store_auto_only_drafts_rotate_and_default_is_unchanged():
    store = MemoryStore()
    orders = RigOrders(store)
    for quote_id, auto in (("q_manual", False), ("q_auto1", True), ("q_auto2", True)):
        await store.add_quote(TENANT, quote_id, {"kind": "product",
                                                 "locate_state": {"state": "ordered", "auto_order": auto}},
                              {"name": "T"})
        await orders.place_located_order(tenant_id=TENANT, quote_id=quote_id, located=LOCATED, price=BLIND_PRICE,
                                         env=SANDBOX)
    assert await store.draft_supplier_orders(TENANT) == ["q_manual", "q_auto1", "q_auto2"]
    assert await store.draft_supplier_orders(TENANT, auto_only=True) == ["q_auto1", "q_auto2"]
    await store.locate_attempt(TENANT, "q_auto1", later(30))
    assert await store.draft_supplier_orders(TENANT, auto_only=True) == ["q_auto2", "q_auto1"]
    assert await store.draft_supplier_orders(TENANT, 1, auto_only=True) == ["q_auto2"]


# 3. A supplier PO number clash is order_mismatch in both stores, nothing saved.

def _po_clash(monkeypatch):
    _taken_order, taken_po = fulfilment.numbers(TENANT, "req_a")
    monkeypatch.setattr(fulfilment, "numbers", lambda tenant, quote: ("RIG-OTHER00001", taken_po))


@pytest.mark.asyncio
async def test_memory_store_po_number_clash_is_order_mismatch(monkeypatch):
    store = MemoryStore()
    orders = RigOrders(store)
    await orders.place_located_order(tenant_id=TENANT, quote_id="req_a", located=LOCATED, price=BLIND_PRICE,
                                     env=SANDBOX)
    _po_clash(monkeypatch)
    with pytest.raises(DeliveryError, match="order_mismatch"):
        await orders.place_located_order(tenant_id=TENANT, quote_id="req_b", located=LOCATED, price=BLIND_PRICE,
                                         env=SANDBOX)
    assert await store.locate_order(TENANT, "req_b") is None and len(store.locate_orders) == 1


async def _pg(prefix):
    import asyncpg
    from uuid import uuid4
    from test_rig_postgres import _admin_url, _create_database, _database_url
    admin = _admin_url()
    name = prefix + uuid4().hex[:12]
    await _create_database(admin, name)
    return admin, name, await asyncpg.create_pool(_database_url(admin, name))


@pytest.mark.asyncio
async def test_real_postgres_po_number_clash_is_order_mismatch_and_saves_nothing(monkeypatch):
    from test_rig_postgres import _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    admin, name, pool = await _pg("rig_poclash_")
    try:
        try:
            store = PgStore(pool)
            await store.apply_schema()
            orders = RigOrders(store)
            with tenant_scope(TENANT):
                await orders.place_located_order(tenant_id=TENANT, quote_id="req_a", located=LOCATED,
                                                 price=BLIND_PRICE, env=SANDBOX)
                _po_clash(monkeypatch)
                with pytest.raises(DeliveryError, match="order_mismatch"):
                    await orders.place_located_order(tenant_id=TENANT, quote_id="req_b", located=LOCATED,
                                                     price=BLIND_PRICE, env=SANDBOX)
                assert await store.locate_order(TENANT, "req_b") is None
            counts = [await pool.fetchval(f"SELECT count(*) FROM agent_rig.{table}")
                      for table in ("locate_orders", "supplier_purchase_orders")]
            assert counts == [1, 1]  # the order row rolled back with the PO
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


@pytest.mark.asyncio
async def test_real_postgres_lists_rotate_by_last_attempt_and_drafts_are_auto_only():
    from test_rig_postgres import _drop_database
    from rigbox.store import PgStore
    from chassis.tenant_db import tenant_scope
    admin, name, pool = await _pg("rig_rotate_")
    try:
        try:
            store = PgStore(pool)
            await store.apply_schema()
            await store.apply_schema()  # repeat-safe
            assert await pool.fetchval(
                "SELECT count(*) FROM information_schema.columns WHERE table_schema = 'agent_rig'"
                " AND table_name = 'quotes' AND column_name = 'locate_attempt_at'") == 1
            orders = RigOrders(store)
            with tenant_scope(TENANT):
                for quote_id in ("q_a", "q_b", "q_c"):
                    await store.add_quote(TENANT, quote_id, {"kind": "product",
                                                             "locate_state": {"state": "refund_due"}}, {"name": "T"})
                assert [q for q, _ in await store.open_locate_payments(TENANT)] == ["q_a", "q_b", "q_c"]
                await store.locate_attempt(TENANT, "q_a", later(30))
                await store.locate_attempt(TENANT, "q_b", later(20))
                await store.locate_attempt("00000000-0000-4000-8000-000000000999", "q_c", later(40))
                assert [q for q, _ in await store.open_locate_payments(TENANT)] == ["q_c", "q_b", "q_a"]
                for quote_id, auto in (("d_manual", False), ("d_auto1", True), ("d_auto2", True)):
                    await store.add_quote(TENANT, quote_id, {"kind": "product", "locate_state": {
                        "state": "ordered", "auto_order": auto}}, {"name": "T"})
                    await orders.place_located_order(tenant_id=TENANT, quote_id=quote_id, located=LOCATED,
                                                     price=BLIND_PRICE, env=SANDBOX)
                assert await store.draft_supplier_orders(TENANT) == ["d_manual", "d_auto1", "d_auto2"]
                assert await store.draft_supplier_orders(TENANT, auto_only=True) == ["d_auto1", "d_auto2"]
                await store.locate_attempt(TENANT, "d_auto1", later(30))
                assert await store.draft_supplier_orders(TENANT, auto_only=True) == ["d_auto2", "d_auto1"]
                assert await store.draft_supplier_orders(TENANT, auto_only=True, before=later(60)) == [
                    "d_auto2", "d_auto1"]
                assert await store.draft_supplier_orders(TENANT, 1, auto_only=True) == ["d_auto2"]
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)


# 4. "checked" and the rotation wording are documented, not overstated.

def test_reconcile_docstrings_describe_rotation_and_the_checked_count():
    from rigbox.quotes.service import QuoteService
    from rigbox.store import PgStore
    doc = " ".join(QuoteService.reconcile_payments.__doc__.split())
    assert "least recently tried first" in doc and "3 x limit" in doc
    assert "never crowd" not in doc and "never starves" not in doc
    for store in (MemoryStore, PgStore):
        listed = " ".join(store.open_locate_payments.__doc__.split())
        assert "Least recently tried first" in listed and "never crowd" not in listed


@pytest.mark.asyncio
async def test_checked_counts_each_list_so_it_can_exceed_limit(monkeypatch, tmp_path):
    adapter = StuckRefunds()
    store, service, _ = await failing_accept(monkeypatch, tmp_path, adapter, "order")
    store.quotes[:0] = [raw(f"req_stuck{i}", {"state": "refund_due", "refund_due_at": OLD, "price": PRICE,
                                              "payment": {"reference": "ch_test_stuck"},
                                              "needs_review": i % 2 == 0}) for i in range(6)]
    result = await service.reconcile_payments(TENANT, now=later(30), limit=2)
    assert 2 < result["checked"] <= 3 * 2
