"""Pay on Accept follow-ups 3 (#531 review N1-N4): quotes stuck at
"reconciling" from ordered are claimed and settled, a failing attempt-time
write is reported, the draft-list summary is accurate, and the PO insert
targets UNIQUE (tenant_id, number). Synthetic values only."""
import inspect
import logging
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "tests"))
from rigbox.fulfilment import RigOrders
from rigbox.store import MemoryStore, PgStore
from test_rig_locate_checkout import TENANT
from test_rig_optional_auto_order import no_network_mail  # noqa: F401  (autouse SMTP refusal)
from test_rig_optional_blind_ship import LOCATED, PRICE as BLIND_PRICE
from test_rig_optional_pay_followup2 import OLD, PRICE, SANDBOX, _pg, raw, state_of
from test_rig_optional_pay_on_accept import RefundFailsOnce, failing_accept, later, paid_shop


def stuck(auto=True, source="ordered", at=OLD):
    # A reconciler claimed it from ordered and stopped before writing back.
    return {"state": "reconciling", "reconcile_from": source, "reconcile_at": at, "ordered_at": OLD,
            "auto_order": auto, "price": PRICE, "payment": {"reference": "ch_test_stuck"}}


async def placed(store, quote_id, sent):
    await RigOrders(store).place_located_order(tenant_id=TENANT, quote_id=quote_id, located=LOCATED,
                                               price=BLIND_PRICE, env=SANDBOX)
    if sent:
        assert await store.supplier_po_sent(TENANT, quote_id, {"outbox": "synthetic"})


# N1. Stuck "reconciling" quotes are claimed, not listed forever.

@pytest.mark.asyncio
async def test_100_stuck_reconciling_quotes_with_sent_pos_no_longer_starve_a_newer_refund(monkeypatch, tmp_path):
    store, service, _ = await failing_accept(monkeypatch, tmp_path, RefundFailsOnce(), "order")
    newest = store.quotes[-1]["id"]
    ids = [f"req_sent{i:03d}" for i in range(100)]
    store.quotes[:0] = [raw(quote_id, stuck()) for quote_id in ids]
    for quote_id in ids:
        await placed(store, quote_id, sent=True)
    first = await service.reconcile_payments(TENANT, now=later(30))
    assert sorted(item["quote_id"] for item in first["reconciled"]) == ids
    assert {item["to"] for item in first["reconciled"]} == {"supplier_ordered"}
    second = await service.reconcile_payments(TENANT, now=later(60))
    assert second["reconciled"] == [{"quote_id": newest, "from": "refund_due", "to": "order_failed_refunded"}]
    assert all(state_of(store, quote_id)["state"] == "supplier_ordered" for quote_id in ids)


@pytest.mark.asyncio
async def test_a_stuck_reconciling_quote_is_settled_by_its_order(monkeypatch, tmp_path):
    store, service, *_ = await paid_shop(monkeypatch, tmp_path)
    store.quotes[:0] = [raw("req_sent", stuck()), raw("req_draft", stuck(auto=False)),
                        raw("req_unconf", stuck(source="supplier_order_unconfirmed")),
                        raw("req_none", stuck()), raw("req_fresh", stuck(at=later(25).isoformat()))]
    for quote_id, sent in (("req_sent", True), ("req_draft", False), ("req_unconf", True), ("req_fresh", True)):
        await placed(store, quote_id, sent)
    result = await service.reconcile_payments(TENANT, now=later(30))
    assert sorted((item["quote_id"], item["from"], item["to"]) for item in result["reconciled"]) == [
        ("req_sent", "ordered", "supplier_ordered"),
        ("req_unconf", "supplier_order_unconfirmed", "supplier_ordered")]
    assert state_of(store, "req_sent")["purchase_order_state"] == "sent"
    draft = state_of(store, "req_draft")
    assert draft["state"] == "ordered" and "reconcile_from" not in draft  # back for the draft-PO list
    assert result["needs_review"] == ["req_none"] and state_of(store, "req_none")["needs_review"] is True
    assert state_of(store, "req_fresh")["state"] == "reconciling"  # not past the cutoff: maybe in flight
    assert store.locate_orders[(TENANT, "req_draft")]["purchase_order"]["state"] == "draft"


# N2. A failing attempt-time write is reported, not silent.

@pytest.mark.asyncio
async def test_a_failing_attempt_write_is_reported_in_the_result_and_logged(monkeypatch, tmp_path, caplog):
    store, service, *_ = await paid_shop(monkeypatch, tmp_path)
    store.quotes[:0] = [raw("req_due", {"state": "refund_due", "refund_due_at": OLD,
                                        "refund_reason": "supplier_order_failed", "price": PRICE,
                                        "payment": {"reference": "ch_test_due"}})]

    real = store.locate_attempt

    async def broken(*args, **kwargs):
        raise ConnectionError("database blip")
    monkeypatch.setattr(store, "locate_attempt", broken)
    with caplog.at_level(logging.WARNING, logger="agent"):
        result = await service.reconcile_payments(TENANT, now=later(30))
    assert result["attempt_unrecorded"] == ["req_due"]
    assert result["reconciled"] == [{"quote_id": "req_due", "from": "refund_due",
                                     "to": "supplier_order_failed_refunded"}]  # the claim still stands
    assert any(record.levelno == logging.ERROR and "will not rotate" in record.getMessage()
               for record in caplog.records)
    monkeypatch.setattr(store, "locate_attempt", real)
    clean = await service.reconcile_payments(TENANT, now=later(60))
    assert "attempt_unrecorded" not in clean  # only present when a write failed


# N3 + N4.

def test_draft_list_summary_and_po_conflict_target():
    summary = inspect.getdoc(PgStore.draft_supplier_orders).splitlines()[0]
    assert "oldest first" not in summary
    assert "least recently tried first" in inspect.getdoc(PgStore.draft_supplier_orders)
    source = inspect.getsource(PgStore.place_locate_order)
    assert "ON CONFLICT (tenant_id, number) DO NOTHING RETURNING true" in source
    assert inspect.getdoc(MemoryStore.draft_supplier_orders)


@pytest.mark.asyncio
async def test_real_postgres_po_conflict_target_is_exactly_a_unique_index(monkeypatch):
    from chassis.tenant_db import tenant_scope
    from rigbox import fulfilment
    from rigbox.quotes.senders import DeliveryError
    from test_rig_postgres import _drop_database
    admin, name, pool = await _pg("rig_potarget_")
    try:
        try:
            store = PgStore(pool)
            await store.apply_schema()
            unique = await pool.fetch(
                "SELECT array_agg(a.attname ORDER BY k.ord) AS cols FROM pg_index i"
                " CROSS JOIN LATERAL unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord)"
                " JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum"
                " WHERE i.indrelid = 'agent_rig.supplier_purchase_orders'::regclass AND i.indisunique"
                " GROUP BY i.indexrelid")
            assert ["tenant_id", "number"] in [list(row["cols"]) for row in unique]
            with tenant_scope(TENANT):
                await RigOrders(store).place_located_order(tenant_id=TENANT, quote_id="req_a", located=LOCATED,
                                                           price=BLIND_PRICE, env=SANDBOX)
                taken_po = fulfilment.numbers(TENANT, "req_a")[1]
                monkeypatch.setattr(fulfilment, "numbers", lambda tenant, quote: ("RIG-OTHER00002", taken_po))
                with pytest.raises(DeliveryError, match="order_mismatch"):
                    await RigOrders(store).place_located_order(tenant_id=TENANT, quote_id="req_b",
                                                               located=LOCATED, price=BLIND_PRICE, env=SANDBOX)
            counts = [await pool.fetchval(f"SELECT count(*) FROM agent_rig.{table}")
                      for table in ("locate_orders", "supplier_purchase_orders")]
            assert counts == [1, 1]
        finally:
            await pool.close()
    finally:
        await _drop_database(admin, name)
