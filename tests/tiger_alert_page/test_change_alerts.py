"""Watch a price history. Pass: 95%+ of real changes, under 2% false alarms."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "tiger"))
sys.path.insert(0, str(ROOT / "tests"))

from tiger_alert_page.score import (  # noqa: E402
    ALERT_MEAN_MS,
    COST_TARGET_USD,
    _rows,
    run_series,
    score_alerts,
)
from watch import DomainLimiter, MemoryStore, run_check  # noqa: E402

TENANT = "11111111-1111-1111-1111-111111111111"


def _point(price: str, availability: str) -> dict:
    return {
        "price": price,
        "availability": availability,
        "page": "jsonld",
    }


def test_hand_checked_boundaries() -> None:
    series = {
        "id": "boundary",
        "threshold": "0.05",
        "points": [
            _point("100.00", "https://schema.org/InStock"),
            _point("100.004", "https://schema.org/InStock"),
            _point("95.00", "https://schema.org/InStock"),
            _point("94.99", "https://schema.org/OutOfStock"),
            _point("80.00", "https://schema.org/OutOfStock"),
        ],
    }
    got = asyncio.run(run_series(series))
    assert [_alert_kinds(row) for row in got[:3]] == [[], [], []]
    assert _alert_kinds(got[3]) == ["stock"]
    assert _alert_kinds(got[4]) == ["price"]


def _alert_kinds(row: dict) -> list[str]:
    return [alert["kind"] for alert in row["alerts"]]


def test_known_phrase_with_extra_words_is_in_stock() -> None:
    """A known phrase with extra words is in stock. One looser line does not veto it."""
    attic = (
        ROOT / "tests" / "tiger_alert_page" / "fixtures" / "live"
        / "books-toscrape-com--a-light-in-the-attic.html"
    ).read_text(encoding="utf-8")
    counted = (
        "<p class=\"stock in-stock\">45 in stock</p>"
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"63.00","priceCurrency":"GBP",'
        '"availability":"https://schema.org/InStock"}}'
        "</script>"
    )
    loose = (
        "<p class=\"stock in-stock\">Ships today</p>"
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"10.00","priceCurrency":"USD",'
        '"availability":"https://schema.org/InStock"}}'
        "</script>"
    )
    ships = (
        "<p class=\"stock in-stock\">Ships today</p>" + _product_html_price("10.00")
    )
    plain = "<p class=\"instock availability\">In stock</p>" + _product_html_price("10.00")

    async def check() -> None:
        store = MemoryStore()
        await _raw(store, "https://stock.test/attic", attic, "51.77", "InStock", [])
        await _raw(store, "https://stock.test/attic", attic, "51.77", "InStock", [])
        await _raw(store, "https://stock.test/counted", counted, "63.00", "InStock", [])
        await _raw(store, "https://stock.test/loose", loose, "10.00", "InStock", [])
        await _raw(store, "https://stock.test/ships", ships, "10.00", "can't read", [])
        await _raw(store, "https://stock.test/plain", plain, "10.00", "InStock", [])

    asyncio.run(check())


def _product_html_price(price: str) -> str:
    return (
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"' + price + '","priceCurrency":"USD"}}'
        "</script>"
    )


def test_clear_out_of_stock_wording_is_out_of_stock() -> None:
    """Negation wins. Clear out-of-stock wording is out of stock and alerts when it changes."""
    negated = (
        "<p class=\"stock\">not in stock</p>"
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"10.00","priceCurrency":"USD",'
        '"availability":"https://schema.org/InStock"}}'
        "</script>"
    )
    steps = [
        ("https://stock.test/out", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/out", "In stock (22 available)", "InStock", []),
        ("https://stock.test/out", "45 in stock", "InStock", []),
        ("https://stock.test/out", "not in stock", "OutOfStock", ["stock"]),
        ("https://stock.test/out", "out of stock", "OutOfStock", []),
        ("https://stock.test/out", "sold out", "OutOfStock", []),
        ("https://stock.test/out", "currently unavailable", "OutOfStock", []),
        ("https://stock.test/out", "Ships today", "can't read", []),
        ("https://stock.test/out", "Available now", "can't read", []),
    ]

    async def check() -> None:
        store = MemoryStore()
        for url, availability, stock, kinds in steps:
            await _once(store, url, "10.00", availability, stock, kinds)
        await _raw(store, "https://stock.test/negated", negated, "10.00", "OutOfStock", [])

    asyncio.run(check())


def test_negation_before_a_stock_phrase() -> None:
    """not, no, no longer, isn't, none, and 0 before a stock phrase flip it."""
    longer = (
        "<p class=\"stock\">no longer in stock</p>"
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"10.00","priceCurrency":"USD",'
        '"availability":"https://schema.org/InStock"}}'
        "</script>"
    )
    back = "<p class=\"stock\">not out of stock</p>" + _product_html_price("10.00")
    steps = [
        ("https://stock.test/flip", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/flip", "not out of stock", "InStock", []),
        ("https://stock.test/flip", "no longer in stock", "OutOfStock", ["stock"]),
        ("https://stock.test/flip", "not currently in stock", "OutOfStock", []),
        ("https://stock.test/flip", "isn't in stock", "OutOfStock", []),
        ("https://stock.test/flip", "none in stock", "OutOfStock", []),
        ("https://stock.test/flip", "0 in stock", "OutOfStock", []),
        ("https://stock.test/flip", "no stock", "OutOfStock", []),
        ("https://stock.test/flip", "Ships today", "can't read", []),
        ("https://stock.test/flip", "Available now", "can't read", []),
    ]

    async def check() -> None:
        store = MemoryStore()
        for url, availability, stock, kinds in steps:
            await _once(store, url, "10.00", availability, stock, kinds)
        await _raw(store, "https://stock.test/longer", longer, "10.00", "OutOfStock", [])
        await _raw(store, "https://stock.test/back", back, "10.00", "InStock", [])

    asyncio.run(check())


def test_negation_is_a_class_of_words() -> None:
    """Any n't contraction, not/no/never/none/nothing/without, or zero flips a stock phrase."""
    gone = (
        "<p class=\"stock\">hasn't been in stock</p>"
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"10.00","priceCurrency":"USD",'
        '"availability":"https://schema.org/InStock"}}'
        "</script>"
    )
    steps = [
        ("https://stock.test/kinds", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/kinds", "not out of stock", "InStock", []),
        ("https://stock.test/kinds", "isn't out of stock", "InStock", []),
        ("https://stock.test/kinds", "not sold out", "InStock", []),
        ("https://stock.test/kinds", "never been out of stock", "InStock", []),
        ("https://stock.test/kinds", "hasn't been in stock", "OutOfStock", ["stock"]),
        ("https://stock.test/kinds", "aren't in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "zero in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "hadn't been in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "wasn't in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "weren't in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "won't be in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "doesn't come in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "don't have it in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "never in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "nothing left in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "have not been in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "without stock", "OutOfStock", []),
        ("https://stock.test/kinds", "zero units in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "0 in stock", "OutOfStock", []),
        ("https://stock.test/kinds", "In stock (22 available)", "InStock", ["stock"]),
        ("https://stock.test/kinds", "45 in stock", "InStock", []),
        ("https://stock.test/kinds", "Ships today", "can't read", []),
        ("https://stock.test/kinds", "Available now", "can't read", []),
    ]

    async def check() -> None:
        store = MemoryStore()
        for url, availability, stock, kinds in steps:
            await _once(store, url, "10.00", availability, stock, kinds)
        await _raw(store, "https://stock.test/hasnt", gone, "10.00", "OutOfStock", [])

    asyncio.run(check())


def test_demand_wording_is_not_a_current_outage() -> None:
    """Selling-fast lines are can't read. A positive keep or hold is in stock."""
    both = (
        "<p class=\"stock\">Couldn't keep it in stock</p>"
        "<script type=\"application/ld+json\">"
        '{"@type":"Product","offers":{"@type":"Offer","price":"10.00","priceCurrency":"USD",'
        '"availability":"https://schema.org/OutOfStock"}}'
        "</script>"
    )
    steps = [
        ("https://stock.test/demand", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/demand", "couldn't keep it in stock", "can't read", []),
        ("https://stock.test/demand", "can't keep them in stock", "can't read", []),
        ("https://stock.test/demand", "hard to keep in stock", "can't read", []),
        ("https://stock.test/demand", "not out of stock", "InStock", []),
        ("https://stock.test/demand", "out of stock", "OutOfStock", ["stock"]),
        ("https://stock.test/demand", "isn't in stock", "OutOfStock", []),
        ("https://stock.test/demand", "zero in stock", "OutOfStock", []),
        ("https://stock.test/demand-plain", "Couldn't keep it in stock. Out of stock.", "OutOfStock", []),
        ("https://stock.test/demand-plain", "Couldn't keep it in stock. In stock.", "InStock", ["stock"]),
        ("https://stock.test/demand-only-in", "Couldn't keep it in stock. In stock.", "InStock", []),
        ("https://stock.test/hold", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/hold", "couldn't hold it in stock", "can't read", []),
        ("https://stock.test/hold", "can't hold them in stock", "can't read", []),
        ("https://stock.test/hold", "having trouble keeping this in stock", "can't read", []),
        ("https://stock.test/hold", "a challenge to keep it in stock", "can't read", []),
        ("https://stock.test/hold", "hard to stay in stock", "can't read", []),
        ("https://stock.test/hold", "selling too fast to stay in stock", "can't read", []),
        ("https://stock.test/hold", "could not carry it in stock", "can't read", []),
        ("https://stock.test/hold", "out of stock", "OutOfStock", ["stock"]),
        ("https://stock.test/separate", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/separate", "We could not keep it in stock. It is out of stock.", "OutOfStock", ["stock"]),
        ("https://stock.test/separate", "not out of stock", "InStock", ["stock"]),
        ("https://stock.test/state", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/state", "The repaired unit is out of stock", "OutOfStock", ["stock"]),
        ("https://stock.test/state", "The listed item is in stock", "InStock", ["stock"]),
        ("https://stock.test/state", "couldn't really maintain it in stock", "can't read", []),
        ("https://stock.test/state", "to quickly remain in stock", "InStock", []),
        ("https://stock.test/remain", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/remain", "We tried to remain in stock. Sold out.", "OutOfStock", ["stock"]),
        ("https://stock.test/remain", "sold out", "OutOfStock", []),
        ("https://stock.test/gap", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/gap", "Couldn't keep it well in stock", "can't read", []),
        ("https://stock.test/gap", "couldn't keep it often in stock", "can't read", []),
        ("https://stock.test/gap", "Couldn't well carry it in stock", "can't read", []),
        ("https://stock.test/gap", "This item is currently out of stock", "OutOfStock", ["stock"]),
        ("https://stock.test/gap", "To remain well in stock", "InStock", ["stock"]),
        ("https://stock.test/gap", "to well offer it in stock", "InStock", []),
        ("https://stock.test/gap", "The repaired unit is out of stock", "OutOfStock", ["stock"]),
        ("https://stock.test/gap", "The listed item is in stock", "InStock", ["stock"]),
        ("https://stock.test/positive", "https://schema.org/OutOfStock", "OutOfStock", []),
        ("https://stock.test/positive", "held in stock", "InStock", ["stock"]),
        ("https://stock.test/positive", "we keep it in stock", "InStock", []),
        ("https://stock.test/positive-quiet", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/positive-quiet", "held in stock", "InStock", []),
        ("https://stock.test/positive-quiet", "We keep it in stock", "InStock", []),
        ("https://stock.test/counts", "only 4 left", "InStock", []),
        ("https://stock.test/counts", "8 available", "InStock", []),
        ("https://stock.test/counts", "only 0 left", "OutOfStock", ["stock"]),
        ("https://stock.test/counts", "0 available", "OutOfStock", []),
    ]

    async def check() -> None:
        store = MemoryStore()
        for url, availability, stock, kinds in steps:
            await _once(store, url, "10.00", availability, stock, kinds)
        await _raw(store, "https://stock.test/both", both, "10.00", "OutOfStock", [])

    asyncio.run(check())


def test_unknown_stock_wording_is_visible() -> None:
    """Unknown stock words are can't read. The same phrase in other words is not an alert."""
    pages = [
        ("https://stock.test/same", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/same", "in stock", "InStock", []),
        ("https://stock.test/same", "https://schema.org/InStock", "InStock", []),
    ]
    unknown = [
        ("https://stock.test/unknown", "https://schema.org/InStock", "InStock", []),
        ("https://stock.test/unknown", "Ships today", "can't read", []),
        ("https://stock.test/unknown", "https://schema.org/OutOfStock", "OutOfStock", ["stock"]),
    ]

    async def check() -> None:
        store = MemoryStore()
        for url, availability, stock, kinds in pages + unknown:
            await _once(store, url, "10.00", availability, stock, kinds)

    asyncio.run(check())


async def _raw(store: MemoryStore, url: str, html: str, price: str, stock: str, kinds: list[str]) -> None:
    from tiger_alert_page.score import _load_extract

    extract = _load_extract()
    if await store.get_watch(TENANT, url) is None:
        await store.create_watch({
            "tenant_id": TENANT,
            "url": url,
            "label": "stock",
            "engine": "core",
            "every": "1h",
            "enabled": True,
            "threshold": "0",
        })
    tick = {"n": len(store.observations)}

    def clock() -> datetime:
        tick["n"] += 1
        return datetime(2026, 10, 16, tzinfo=timezone.utc) + timedelta(seconds=tick["n"])

    async def render(page_url: str, session: str, agent: str, tenant: str) -> dict:
        return {"ok": True, "challenge": False, "html": html, "png_base64": None}

    async def extract_html(page: str, page_url: str) -> dict:
        return extract.extract(page, page_url)

    async def ocr(png: str, page_url: str) -> dict:
        raise AssertionError("a known page is not guessed from a screenshot")

    async def fetch_text(page_url: str) -> str:
        return ""

    watch = await store.get_watch(TENANT, url)
    assert watch is not None
    out = await run_check(
        store, TENANT, watch, "tiger", render, extract_html, ocr, fetch_text, DomainLimiter(0), now=clock,
    )
    assert out["status"] == "observed", out
    assert out["price"] == price
    assert out["stock"] == stock
    assert out["observation"]["availability"] == stock
    assert _alert_kinds(out) == kinds
    if stock == "can't read":
        assert "can't read" in str(out["observation"]["evidence"])


async def _once(store: MemoryStore, url: str, price: str, availability: str, stock: str, kinds: list[str]) -> None:
    from tiger_alert_page.score import _load_extract, _product_html

    extract = _load_extract()
    if await store.get_watch(TENANT, url) is None:
        await store.create_watch({
            "tenant_id": TENANT,
            "url": url,
            "label": "stock",
            "engine": "core",
            "every": "1h",
            "enabled": True,
            "threshold": "0",
        })
    html = _product_html(price, availability)
    tick = {"n": len(store.observations)}

    def clock() -> datetime:
        tick["n"] += 1
        return datetime(2026, 10, 16, tzinfo=timezone.utc) + timedelta(seconds=tick["n"])

    async def render(page_url: str, session: str, agent: str, tenant: str) -> dict:
        return {"ok": True, "challenge": False, "html": html, "png_base64": None}

    async def extract_html(page: str, page_url: str) -> dict:
        return extract.extract(page, page_url)

    async def ocr(png: str, page_url: str) -> dict:
        raise AssertionError("a known page is not guessed from a screenshot")

    async def fetch_text(page_url: str) -> str:
        return ""

    watch = await store.get_watch(TENANT, url)
    assert watch is not None
    out = await run_check(
        store, TENANT, watch, "tiger", render, extract_html, ocr, fetch_text, DomainLimiter(0), now=clock,
    )
    assert out["status"] == "observed"
    assert out["price"] == price
    assert out["stock"] == stock
    assert out["observation"]["availability"] == stock
    assert _alert_kinds(out) == kinds
    if stock == "can't read":
        assert "can't read" in str(out["observation"]["evidence"])


def test_gold_change_alerts_meet_the_bar() -> None:
    report = score_alerts(_rows("change_alerts.jsonl"))
    build = report["summary"]["build"]
    held = report["summary"]["heldout"]
    assert build["catch_n"] > 0 and build["quiet_n"] > 0
    assert held["catch_n"] > 7
    assert build["catch_pct"] >= 95
    assert build["false_pct"] < 2
    assert held["catch_pct"] >= 95
    assert held["false_pct"] < 2
    assert report["cost_usd"] == COST_TARGET_USD
    assert report["mean_ms"] <= ALERT_MEAN_MS
    assert all(row["verified"] == "no" for row in report["rows"])
    failed = [row["id"] for row in report["rows"] if not row["pass"]]
    assert not failed


def test_labels_are_written_and_the_score_uses_the_watch() -> None:
    source = (ROOT / "tests" / "tiger_alert_page" / "build_gold.py").read_text(encoding="utf-8")
    assert "def _moved" not in source
    assert "def label_series" not in source
    assert "def _norm" not in source
    scorer = (ROOT / "tests" / "tiger_alert_page" / "score.py").read_text(encoding="utf-8")
    assert "run_check" in scorer
    assert "change_alert.replay" not in scorer
    assert ".replay(" not in scorer
    held = [row for row in _rows("change_alerts.jsonl") if row["split"] == "heldout"]
    alerts = sum(1 for row in held for point in row["points"] if point["expect_alert"])
    assert alerts > 7
    hard = {row["id"] for row in held}
    assert {"ca-cent", "ca-threshold", "ca-round-cents", "ca-stock-words", "ca-strip-decoy"} <= hard


def test_alert_traps() -> None:
    report = score_alerts(_rows("change_alert_traps.jsonl"))
    assert report["rows"]
    assert all(row["pass"] for row in report["rows"])
    failed = [row["id"] for row in report["rows"] if not row["pass"]]
    assert not failed
