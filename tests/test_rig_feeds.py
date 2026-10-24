"""Feed URL import for Rig. Fixtures only. No network."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.catalogue import map_google_merchant, map_shopify, map_woocommerce  # noqa: E402
from rigbox.feeds import pull, register  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

TENANT = "11111111-1111-4111-8111-111111111111"
COLUMNS = [
    "sku",
    "gtin",
    "name",
    "brand",
    "category",
    "price",
    "currency",
    "image_url",
    "url",
    "family",
    "active",
    "attributes",
]

SHOP = {
    "products": [
        {
            "title": "Desk Lamp",
            "vendor": "North",
            "product_type": "light",
            "handle": "desk-lamp",
            "status": "active",
            "images": [{"src": "https://example.com/lamp.jpg"}],
            "variants": [
                {"sku": "LAMP-S", "price": "42.00", "barcode": "000111"},
                {"sku": "LAMP-L", "price": "54.50", "barcode": "000222"},
            ],
        }
    ]
}

WOO = [
    {
        "sku": "MUG-1",
        "name": "Stoneware Mug",
        "price": "",
        "regular_price": "18.00",
        "permalink": "https://example.com/mug",
        "status": "publish",
        "images": [{"src": "https://example.com/mug.jpg"}],
        "categories": [{"name": "tableware"}],
        "attributes": [{"name": "Brand", "options": ["Harbor"]}],
        "global_unique_id": "1234567890123",
    }
]

MERCHANT = """<?xml version="1.0"?>
<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0"><channel>
<item>
  <g:id>NOTE-1</g:id>
  <title>ignored</title>
  <g:title>Lined Notebook</g:title>
  <g:brand>Lumen</g:brand>
  <g:price>8.00 USD</g:price>
  <g:image_link>https://example.com/note.jpg</g:image_link>
  <g:link>https://example.com/note</g:link>
  <g:availability>in stock</g:availability>
  <g:product_type>stationery</g:product_type>
  <g:gtin>4006381333931</g:gtin>
</item>
</channel></rss>"""


def test_shopify_variants_use_the_product_columns() -> None:
    mapped = map_shopify(SHOP, "usd")
    assert mapped["rejected"] == []
    assert [row["sku"] for row in mapped["rows"]] == ["LAMP-S", "LAMP-L"]
    assert list(mapped["rows"][0]) == COLUMNS
    assert mapped["rows"][0]["name"] == "Desk Lamp"
    assert mapped["rows"][0]["brand"] == "North"
    assert mapped["rows"][0]["category"] == "light"
    assert mapped["rows"][0]["price"] == "42.00"
    assert mapped["rows"][1]["price"] == "54.50"
    assert mapped["rows"][0]["currency"] == "USD"
    assert mapped["rows"][0]["gtin"] == "000111"
    assert mapped["rows"][0]["image_url"] == "https://example.com/lamp.jpg"
    assert mapped["rows"][0]["url"] == "desk-lamp"
    assert mapped["rows"][0]["family"] == ""
    assert mapped["rows"][0]["attributes"] == {}
    assert mapped["rows"][0]["active"] is True


def test_woocommerce_and_merchant_use_the_same_columns() -> None:
    woo = map_woocommerce(WOO, "EUR")
    assert woo["rejected"] == []
    assert list(woo["rows"][0]) == COLUMNS
    assert woo["rows"][0]["sku"] == "MUG-1"
    assert woo["rows"][0]["brand"] == "Harbor"
    assert woo["rows"][0]["price"] == "18.00"
    assert woo["rows"][0]["currency"] == "EUR"
    assert woo["rows"][0]["gtin"] == "1234567890123"
    assert woo["rows"][0]["url"] == "https://example.com/mug"
    merchant = map_google_merchant(MERCHANT)
    assert merchant["rejected"] == []
    assert list(merchant["rows"][0]) == COLUMNS
    assert merchant["rows"][0]["sku"] == "NOTE-1"
    assert merchant["rows"][0]["name"] == "Lined Notebook"
    assert merchant["rows"][0]["currency"] == "USD"
    assert merchant["rows"][0]["category"] == "stationery"
    assert merchant["rows"][0]["active"] is True


def test_out_of_stock_and_draft_stay_rows_with_active_off() -> None:
    parked = map_google_merchant(
        MERCHANT.replace("in stock", "out of stock")
    )
    assert parked["rejected"] == []
    assert parked["rows"][0]["active"] is False
    draft = map_shopify(
        {"products": [{**SHOP["products"][0], "status": "draft", "variants": [SHOP["products"][0]["variants"][0]]}]},
        "USD",
    )
    assert draft["rejected"] == []
    assert draft["rows"][0]["active"] is False
    assert draft["rows"][0]["sku"] == "LAMP-S"


def test_a_bad_row_rejects_the_whole_feed() -> None:
    shop = map_shopify(
        {
            "products": [
                SHOP["products"][0],
                {
                    "title": "Bare Shelf",
                    "vendor": "North",
                    "product_type": "storage",
                    "handle": "bare-shelf",
                    "variants": [{"sku": "SHELF-1", "price": "30.00"}],
                },
            ]
        },
        "USD",
    )
    assert shop["rows"] == []
    assert shop["rejected"] == [{"row": 2, "reason": "missing image_url"}]
    woo = map_woocommerce(
        [
            WOO[0],
            {
                "sku": "BAD-1",
                "name": "Cracked Mug",
                "price": "nope",
                "permalink": "https://example.com/bad",
                "images": [{"src": "https://example.com/bad.jpg"}],
                "categories": [{"name": "tableware"}],
                "brands": [{"name": "Harbor"}],
            },
        ],
        "EUR",
    )
    assert woo["rows"] == []
    assert woo["rejected"] == [{"row": 2, "reason": "price is not a number"}]
    merchant = map_google_merchant(
        MERCHANT.replace(
            "</item>",
            "</item><item><g:id>NOTE-2</g:id><g:title>Blank Notebook</g:title>"
            "<g:price>4.00 USD</g:price><g:image_link>https://example.com/blank.jpg</g:image_link>"
            "<g:availability>in stock</g:availability><g:product_type>stationery</g:product_type></item>",
        )
    )
    assert merchant["rows"] == []
    assert merchant["rejected"] == [{"row": 2, "reason": "missing brand"}]


def test_repeated_sku_and_bad_documents_import_nothing() -> None:
    repeated = map_woocommerce(
        [WOO[0], {**WOO[0], "name": "Second Mug"}],
        "EUR",
    )
    assert repeated["rows"] == []
    assert repeated["rejected"] == [{"row": 2, "reason": "sku is repeated"}]
    assert map_shopify("{", "USD")["rejected"] == [{"row": 0, "reason": "shopify feed is not JSON"}]
    assert map_woocommerce({"error": "no"}, "EUR")["rejected"][0]["reason"] == "woocommerce feed has no products list"
    assert map_google_merchant("<rss>")["rejected"] == [{"row": 0, "reason": "merchant feed is not XML"}]
    assert map_google_merchant("<rss><channel></channel></rss>")["rejected"] == [
        {"row": 0, "reason": "merchant feed has no items"}
    ]
    negative = map_shopify(
        {
            "products": [
                {
                    **SHOP["products"][0],
                    "variants": [{"sku": "LAMP-S", "price": "-1.00", "barcode": "000111"}],
                }
            ]
        },
        "USD",
    )
    assert negative["rows"] == []
    assert negative["rejected"][0]["reason"] == "price is negative"


def test_register_once_and_pull_maps_a_fetched_body() -> None:
    record = register("https://shop.example/products.json", "Shopify", "usd")
    again = register("https://shop.example/products.json", "shopify", "USD")
    assert record == again == {
        "format": "shopify",
        "url": "https://shop.example/products.json",
        "currency": "USD",
    }
    assert pull(record, SHOP) == map_shopify(SHOP, "USD")
    merchant = register("https://shop.example/feed.xml", "google")
    assert merchant["currency"] == ""
    assert pull(merchant, MERCHANT) == map_google_merchant(MERCHANT)
    with pytest.raises(ValueError, match="https"):
        register("http://shop.example/products.json", "shopify", "USD")
    with pytest.raises(ValueError, match="feed format must be"):
        register("https://shop.example/feed", "magento", "USD")
    with pytest.raises(ValueError, match="currency is required"):
        register("https://shop.example/products.json", "woocommerce", "")
    assert pull({"format": "unsupported"}, SHOP)["rejected"] == [{"row": 0, "reason": "unknown feed format"}]
    assert register("https://shop.example/feed.csv", "csv", "NZD")["format"] == "csv"


def test_feed_package_does_not_fetch_or_schedule() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / "agents" / "rig" / "rigbox" / "feeds").rglob("*.py")
    )
    for word in ("urlopen", "httpx", "requests", "aiohttp", "cron", "ensure_schedules"):
        assert word not in text


@pytest.mark.asyncio
async def test_existing_caller_imports_nothing_when_a_row_is_bad() -> None:
    store = MemoryStore()
    service = Service(store)
    record = register("https://example.com/products.json", "shopify", "USD")
    await store.put_feed(TENANT, record["format"], record["url"], record["currency"])
    body = {
        "products": [
            {
                "title": "Desk Lamp",
                "vendor": "North",
                "product_type": "light",
                "handle": "desk-lamp",
                "status": "active",
                "images": [{"src": "https://example.com/lamp.jpg"}],
                "variants": [{"sku": "LAMP-1", "price": "42.00", "barcode": "000"}],
            },
            {
                "title": "Bare Shelf",
                "vendor": "North",
                "product_type": "storage",
                "variants": [{"sku": "SHELF-1", "price": "30.00"}],
            },
        ]
    }

    async def fetch(_url: str) -> dict:
        return body

    pulled = await service.pull_feeds(TENANT, fetch)
    assert pulled == [
        {
            "format": "shopify",
            "added": 0,
            "updated": 0,
            "rejected": [{"row": 2, "reason": "missing image_url"}],
        }
    ]
    assert await store.product_exists(TENANT, "LAMP-1") is False
    assert await store.product_exists(TENANT, "SHELF-1") is False
