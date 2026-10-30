"""Offline page -> ordinary alert rows -> unchanged local SMTP delivery."""
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest

from test_tiger import TENANT_A as A, TENANT_B as B, _watch
from test_tiger_alert_email import catcher  # noqa: F401 — existing local SMTP fixture
from tiger_works.fixture import extract, saved_page, no_paid_call, LABEL
from alert_email import deliver_pending
from g5_alerts import listing_products, room
from watch import DomainLimiter, run_check, PgStore, ensure_tables

URL = "https://shop.example/category"
NOW = datetime(2030, 1, 1, tzinfo=timezone.utc)
PEER = "https://competitor.example/item"
KINDS = ("new_product", "below_cost", "market_gap")


def listing(added=False, empty=False):
    html = (Path(__file__).parent / "fixtures/category.html").read_text()
    prefix, script = html.split('<script type="application/ld+json">', 1)
    data, suffix = script.split("</script>", 1)
    doc = json.loads(data)
    if empty:
        doc["itemListElement"] = []
    if added:
        doc["itemListElement"].append({"@type": "ListItem", "position": 2,
            "item": {"@type": "Product", "name": "Fixture saw", "sku": "saw", "url": "/saw"}})
    doc["numberOfItems"] = len(doc["itemListElement"])
    return prefix + '<script type="application/ld+json">' + json.dumps(doc) + "</script>" + suffix


async def watched(store, tenant=A, url=URL, **flags):
    return await store.create_watch({**_watch(tenant), "url": url, "alert_price": False, "alert_stock": False, **flags})


def context(tenant=A, cost="125", active=True, urls=None, currency="USD"):
    return {"tenant_id": tenant, "urls": urls or [URL, PEER], "product": {
        "sku": "own-item", "name": LABEL, "active": active, "url": "https://own.example/item",
        "cost": cost, "cost_currency": currency}}
  # noqa: F811 (pytest fixture parameter)

async def checked(store, watch, *, html=None, price="120", stock="InStock", at=0, ctx=None, blocked=False):
    async def render(*args):
        return {"ok": not blocked, "challenge": blocked, "html": saved_page(price, stock) if html is None else html}

    async def product_context(tenant, url):
        return ctx

    return await run_check(store, watch["tenant_id"], watch, "tiger", render, extract,
                           no_paid_call, no_paid_call, DomainLimiter(0),
                           now=lambda: NOW + timedelta(minutes=at), product_context=product_context)


async def trigger(store, watch, kind, at=0):
    if kind == "new_product":
        await checked(store, watch, html=listing(), at=at)
        return await checked(store, watch, html=listing(added=True), at=at + 1)
    return await checked(store, watch, ctx=context(watch["tenant_id"]),
                         stock="OutOfStock" if kind == "market_gap" else "InStock", at=at + 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
async def test_each_type_exact_email_and_no_repeat_for_two_tenants(store, catcher, kind):  # noqa: F811 (pytest fixture parameter)
    watches = [await watched(store, t, **{"alert_" + k: k == kind for k in KINDS}) for t in (A, B)]
    expected = {
        "new_product": "New product listed: Fixture saw",
        "below_cost": "Competitor price $120.00 is below your cost $125.00",
        "market_gap": "All watched competitors are out of stock. You are in stock.",
    }[kind]
    for watch in watches:
        result = await trigger(store, watch, kind)
        assert [a["kind"] for a in result["alerts"]] == [kind]
        # Repeat the same observed condition, without restoring the old listing.  # noqa: F811 (pytest fixture parameter)
        repeated = await checked(store, watch, at=2,
            html=listing(added=True) if kind == "new_product" else None,
            stock="OutOfStock" if kind == "market_gap" else "InStock", ctx=context(watch["tenant_id"]))
        assert repeated["alerts"] == []
        tenant = watch["tenant_id"]
        rows = await store.list_alerts(tenant, None)
        assert len(rows) == 1 and rows[0]["tenant_id"] == tenant
        result = await deliver_pending(store, tenant, transport=catcher.transport,
            recipient=("a" if tenant == A else "b") + "@example.test", clock=lambda: NOW + timedelta(days=1))
        assert result["sent"] == 1
        again = await deliver_pending(store, tenant, transport=catcher.transport,
            recipient="a@example.test", clock=lambda: NOW + timedelta(days=1))
        assert again["sent"] == 0
    assert len(catcher.messages) == 2
    for message in catcher.messages:
        assert message["Subject"] == expected
        assert message.get_content().strip().splitlines() == ["Fixture saw" if kind == "new_product" else LABEL, expected, URL]
    assert [m["To"] for m in catcher.messages] == ["a@example.test", "b@example.test"]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("disable_after_queue", [False, True])
async def test_switch_off_prevents_email_and_preserves_other_tenant(store, catcher, kind, disable_after_queue):  # noqa: F811 (pytest fixture parameter)
    watch = await watched(store, **{"alert_" + k: k == kind for k in KINDS})
    other = await watched(store, B, **{"alert_" + k: k == kind for k in KINDS})
    if not disable_after_queue:
        watch = await store.update_watch(A, watch["id"], {"alert_" + kind: False})
    await trigger(store, watch, kind)
    if disable_after_queue:
        await store.update_watch(A, watch["id"], {"alert_" + kind: False})
    await trigger(store, other, kind)
    for tenant in (A, B):
        sent = await deliver_pending(store, tenant, transport=catcher.transport,
            recipient=("a" if tenant == A else "b") + "@example.test", clock=lambda: NOW + timedelta(days=1))
        assert sent["sent"] == (1 if tenant == B else 0)
    assert len(catcher.messages) == 1 and catcher.messages[0]["To"] == "b@example.test"


@pytest.mark.asyncio
async def test_listing_empty_baseline_reorder_failed_check_and_recovery(store):
    watch = await watched(store)
    assert (await checked(store, watch, html=listing(empty=True)))["alerts"] == []
    first = await checked(store, watch, html=listing(), at=1)
    assert [a["after"] for a in first["alerts"]] == ["Fixture drill"]
    assert (await checked(store, watch, blocked=True, at=2))["alerts"] == []
    assert (await checked(store, watch, html='<script type="application/ld+json">{"broken"</script>', at=3))["alerts"] == []
    assert (await checked(store, watch, html=listing(), at=4))["alerts"] == []
    added = await checked(store, watch, html=listing(True), at=5)
    assert [a["after"] for a in added["alerts"]] == ["Fixture saw"]
    reordered = listing(True).replace('"position": 1', '"position": 3')
    assert (await checked(store, watch, html=reordered, at=6))["alerts"] == []


@pytest.mark.asyncio
async def test_cost_requires_own_matching_row_currency_and_transition(store):
    a, b = await watched(store), await watched(store, B)
    for minute, ctx in enumerate([None, context(B), context(cost=None), context(currency="EUR"), context(urls=[PEER])]):
        assert (await checked(store, a, ctx=ctx, at=minute))["alerts"] == []
    assert (await checked(store, b, ctx=context(B, cost="100"), at=5))["alerts"] == []
    first = await checked(store, a, ctx=context(), at=5)
    assert [r["kind"] for r in first["alerts"]] == ["below_cost"]
    assert (await checked(store, a, ctx=context(), blocked=True, at=6))["alerts"] == []
    assert (await checked(store, a, ctx=context(), at=7))["alerts"] == []
    assert (await checked(store, a, ctx=context(), price="130", at=8))["alerts"] == []
    again = await checked(store, a, ctx=context(), at=9)
    assert [r["kind"] for r in again["alerts"]] == ["below_cost"]


@pytest.mark.asyncio
async def test_market_gap_counts_muted_competitor_unknowns_own_stock_and_staleness(store):
    a = await watched(store, alert_below_cost=False)
    peer = await watched(store, url=PEER, alert_below_cost=False, alert_market_gap=False)
    b = await watched(store, B, alert_below_cost=False)
    assert (await checked(store, a, ctx=context(), stock="OutOfStock"))["alerts"] == []  # peer unread
    assert (await checked(store, peer, ctx=context(), at=1))["alerts"] == []  # muted peer still in stock
    assert (await checked(store, a, ctx=context(), stock="OutOfStock", at=2))["alerts"] == []
    # All out, but client's own stock is out: no gap.
    assert (await checked(store, peer, ctx=context(active=False), stock="OutOfStock", at=3))["alerts"] == []
    found = await checked(store, a, ctx=context(), stock="OutOfStock", at=4)
    assert [r["kind"] for r in found["alerts"]] == ["market_gap"]
    # One product-level event, even when a different competitor completes next.
    assert (await checked(store, peer, ctx=context(), stock="OutOfStock", at=5))["alerts"] == []
    assert (await checked(store, a, ctx=context(), blocked=True, at=6))["alerts"] == []
    assert (await checked(store, a, ctx=context(), stock="OutOfStock", at=7))["alerts"] == []
    assert (await checked(store, peer, ctx=context(), at=8))["alerts"] == []  # resets gap
    assert (await checked(store, a, ctx=context(), stock="OutOfStock", at=70))["alerts"] == []  # overdue peer
    next_gap = await checked(store, peer, ctx=context(), stock="OutOfStock", at=71)
    assert [r["kind"] for r in next_gap["alerts"]] == ["market_gap"]
    # Same URL/SKU in another tenant uses only its own watches/readings.
    assert (await checked(store, b, ctx=context(B, active=False), stock="OutOfStock", at=72))["alerts"] == []
    assert await store.list_alerts(B, None) == []


@pytest.mark.asyncio
async def test_concurrent_checks_create_one_alert_and_state_rolls_back_with_mail(database, monkeypatch):
    store = PgStore(database)
    watch = await watched(store)
    await checked(store, watch, html=listing())
    write = store._save_alert
    async def broken(conn, row):
        await write(conn, row)
        raise RuntimeError("offline failed transaction")
    monkeypatch.setattr(store, "_save_alert", broken)
    with pytest.raises(RuntimeError):
        await checked(store, watch, html=listing(True), at=1)
    assert await store.list_alerts(A, None) == []
    assert await store.pending_mail(A, NOW + timedelta(days=1)) == []
    monkeypatch.setattr(store, "_save_alert", write)
    observation = await store.latest_observation(A, URL)
    results = await asyncio.gather(*[PgStore(database).product_alerts(A, observation, listing_products(listing(True), URL, []), None) for _ in range(2)])
    assert sorted(len(rows) for rows in results) == [0, 1]
    assert (await checked(store, watch, html=listing(True), at=2))["alerts"] == []
    assert len(await store.list_alerts(A, None)) == 1
    assert len(await store.pending_mail(A, NOW + timedelta(days=1))) == 1


@pytest.mark.asyncio
async def test_migration_twice_preserves_switches_and_rejects_schema_injection(database):
    store = PgStore(database)
    a, b = await watched(store), await watched(store, B)
    assert all(a["alert_" + kind] for kind in KINDS)
    await store.update_watch(A, a["id"], {"alert_" + kind: False for kind in KINDS})
    async with database.acquire() as conn:
        await ensure_tables(conn)
        await ensure_tables(conn)
        with pytest.raises(ValueError):
            async with room(conn, 'agent_tiger; DROP SCHEMA agent_rig'):
                pytest.fail("schema injection entered room")
    a = await store.get_watch_by_id(A, a["id"])
    b = await store.get_watch_by_id(B, b["id"])
    assert not any(a["alert_" + kind] for kind in KINDS)
    assert all(b["alert_" + kind] for kind in KINDS)
    assert await store.update_watch(B, a["id"], {"alert_new_product": True}) is None
