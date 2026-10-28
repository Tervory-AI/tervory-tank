"""The five G5 review findings, exercised offline through real readers/stores."""
from datetime import timedelta
import json
from pathlib import Path
import subprocess

import pytest

from test_alerts import A, B, NOW, URL, PEER, watched, checked, context, listing
from test_tiger_alert_email import catcher  # noqa: F401 — existing loopback SMTP
from tiger_works.fixture import extract, no_paid_call
from alert_email import deliver_pending
from watch import DomainLimiter, run_check


def microdata(count, identity):
    products = []
    for index in range(count):
        identifier = (f'<meta itemprop="{identity}" content="product-{index}">'
                      if identity in {"sku", "gtin"} else "")
        address = (f'<link itemprop="url" href="https://shop.example/product/{index}">'
                   if identity == "url" else "")
        products.append(f'''<article itemscope itemtype="https://schema.org/Product">
            <span itemprop="name">Controlled item {index}</span>{identifier}
            <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
            {address}<meta itemprop="price" content="10"><meta itemprop="priceCurrency" content="USD">
            <link itemprop="availability" href="https://schema.org/InStock"></div></article>''')
    return '<html><head><title>Controlled category</title></head><body>' + ''.join(products) + '</body></html>'


def product_page(*, price=None, stock=None, url=URL):
    offer = {"@type": "Offer"}
    if price is not None:
        offer.update(price=price, priceCurrency="USD")
    if stock is not None:
        offer["availability"] = "https://schema.org/" + stock
    data = {"@context": "https://schema.org", "@type": "Product", "name": "Controlled item",
            "url": url, "sku": "own-item", "offers": offer}
    return '<html><head><title>Controlled item</title><script type="application/ld+json">' + json.dumps(data) + '</script></head><body></body></html>'


@pytest.mark.asyncio
@pytest.mark.parametrize("identity", ["url", "sku", "gtin", "name_price"])
async def test_microdata_third_product_sends_one_new_product_email(store, catcher, identity):  # noqa: F811 (pytest fixture parameter)
    for tenant in (A, B):
        watch = await watched(store, tenant)
        assert (await checked(store, watch, html=microdata(2, identity)))["alerts"] == []
        added = await checked(store, watch, html=microdata(3, identity), at=1)
        assert [(a["kind"], a["after"]) for a in added["alerts"]] == [("new_product", "Controlled item 2")]
        assert (await checked(store, watch, html=microdata(3, identity), at=2))["alerts"] == []
        recipient = ("a" if tenant == A else "b") + "@example.test"
        sent = await deliver_pending(store, tenant, transport=catcher.transport, recipient=recipient,
                                     clock=lambda: NOW + timedelta(days=1))
        assert sent["sent"] == 1
    assert len(catcher.messages) == 2
    assert all(m["Subject"] == "New product listed: Controlled item 2" for m in catcher.messages)


@pytest.mark.asyncio
async def test_below_cost_ten_against_fifteen_needs_no_stock(store):
    for tenant, cost in ((A, "15"), (B, "5")):
        watch = await watched(store, tenant, alert_market_gap=False)
        for minute in (0, 1):
            result = await checked(store, watch, html=product_page(price="10"), ctx=context(tenant, cost=cost), at=minute)
            assert result["observation"]["price"] == "10.00"
            assert result["observation"]["availability"] is None
            assert [a["kind"] for a in result["alerts"]] == (["below_cost"] if tenant == A and minute == 0 else [])


@pytest.mark.asyncio
async def test_market_gap_all_competitors_out_without_prices(store):
    for tenant in (A, B):
        first = await watched(store, tenant, alert_below_cost=False)
        second = await watched(store, tenant, url=PEER, alert_below_cost=False)
        ctx = context(tenant, active=tenant == A, cost=None)
        async def stock_check(watch, minute):
            async def render(*args):
                return {"ok": True, "html": product_page(stock="OutOfStock", url=watch["url"]),
                        "png_base64": "offline-image-must-not-trigger-ocr"}
            async def product_context(*args):
                return ctx
            return await run_check(store, tenant, watch, "tiger", render, extract, no_paid_call,
                                   no_paid_call, DomainLimiter(0), now=lambda: NOW + timedelta(minutes=minute),
                                   product_context=product_context)
        result = await stock_check(first, 0)
        assert result["observation"]["price"] is None
        assert result["observation"]["availability"] == "OutOfStock"
        assert result["alerts"] == []  # the second competitor has not been read
        result = await stock_check(second, 1)
        assert [a["kind"] for a in result["alerts"]] == (["market_gap"] if tenant == A else [])
        assert (await stock_check(second, 2))["alerts"] == []


@pytest.mark.asyncio
async def test_watch_url_change_starts_new_baseline_and_peer_reading(store):
    for tenant in (A, B):
        watch = await watched(store, tenant)
        await checked(store, watch, html=listing())
        updated = await store.update_watch(tenant, watch["id"], {"url": PEER})
        assert (await checked(store, updated, html=listing(added=True), at=1))["alerts"] == []
        assert (await checked(store, updated, html=listing(added=True), at=2))["alerts"] == []
        # The old watch's out-of-stock reading must not stand in for a new URL.
        old = await watched(store, tenant, url=URL)
        await checked(store, old, stock="OutOfStock", ctx=context(tenant), at=3)
        moved = await store.update_watch(tenant, old["id"], {"url": "https://third.example/item"})
        ctx = context(tenant, urls=[PEER, moved["url"]])
        result = await checked(store, updated, stock="OutOfStock", ctx=ctx, at=4)
        assert not any(a["kind"] == "market_gap" for a in result["alerts"])


def test_workspace_omits_g5_rows_until_figma_and_keeps_existing_alerts():
    cases = []
    for kind, before, after in (("new_product", None, "Controlled saw"), ("below_cost", "15", "10"),
                               ("market_gap", "InStock", "OutOfStock"), ("price", "15", "10"),
                               ("stock", "InStock", "OutOfStock")):
        cases.append({"alert": {"id": kind, "kind": kind, "before": before, "after": after,
                                "url": URL, "ts": NOW.isoformat()},
                      "observation": {"id": "reading", "url": URL, "ts": NOW.isoformat(),
                                      "currency": "USD", "product_name": "Controlled item", "price": "10",
                                      "method": "jsonld", "availability": "OutOfStock"}})
    result = subprocess.run(["node", "tests/tiger_alert_email/page_copy.cjs"],
                            cwd=Path(__file__).resolve().parents[2], input=json.dumps(cases),
                            text=True, capture_output=True, check=True)
    rows = json.loads(result.stdout)
    assert rows[:3] == [None, None, None]
    assert [r["id"] for r in rows[3:]] == ["price", "stock"]
    assert all(r["reason"] is None for r in rows[3:])
