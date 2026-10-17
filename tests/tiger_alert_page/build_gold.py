"""Write the gold files.

Each expected alert is written on the case. This file does not decide alerts
by replaying the stock table, the cent rounding, or the threshold.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
FIXTURES = PACKAGE / "fixtures"
GOLD = PACKAGE / "gold"
sys.path.insert(0, str(ROOT / "agents" / "tiger"))
sys.path.insert(0, str(PACKAGE.parent))

import page_guard  # noqa: E402
from tiger_alert_page.mutate import changed as mutate_page, price_still_on_page  # noqa: E402

EXTRACT_PATH = ROOT / "tank" / "skills" / "tiger.price_extract" / "1.0.0" / "run.py"

# Held out on purpose. Hard price moves, not every fifth series.
HOLDOUT_IDS = {
    "ca-cent",
    "ca-big-drop",
    "ca-threshold",
    "ca-just-over",
    "ca-euro-rise",
    "ca-thousands",
    "ca-round-comma",
    "ca-round-cents",
    "ca-stock",
    "ca-from-zero",
    "ca-both",
    "ca-promo",
    "ca-micro-fixture",
    "ca-attic-live",
    "ca-adafruit-live",
    "ca-webscraper-live",
    "ca-restock",
    "ca-preorder",
    "ca-blocked-then",
    "ca-missing-then",
    "ca-stock-words",
    "ca-after-unknown",
    "ca-prompt-page",
    "ca-strip-decoy",
}

# Page holdout is the harder edits, not the foreign-page swap.
HOLDOUT_PAGES = {
    "blank": None,
    "strip": {"sale", "attic", "adafruit", "pattern", "automation"},
    "prompt": {"micro", "web-1", "bulbasaur", "lamp", "velvet"},
    "foreign": {"bowl", "hat"},
}


def _p(
    show,
    seen,
    what: str,
    *,
    alert: bool,
    kinds: tuple[str, ...] = (),
    availability: str | None = "https://schema.org/InStock",
    page: str = "jsonld",
    stock: str | None = None,
    status: str | None = None,
    file: str | None = None,
    edits: list[list[str]] | None = None,
) -> dict:
    row: dict = {
        "price": show,
        "availability": availability,
        "page": "file" if file else page,
        "expect_alert": alert,
        "expect_kinds": list(kinds),
        "expect_price": seen,
        "what": what,
        "verified": False,
    }
    if stock is not None:
        row["expect_stock"] = stock
    if status is not None:
        row["expect_status"] = status
    if file:
        row["file"] = file
    if edits:
        row["edits"] = edits
    return row


def _series(sid: str, threshold: str, what: str, points: list[dict], source: str) -> dict:
    return {
        "id": sid,
        "skill": "change-alerts",
        "source": source,
        "threshold": threshold,
        "what": what,
        "trap": False,
        "verified": False,
        "split": "heldout" if sid in HOLDOUT_IDS else "build",
        "points": points,
    }


def alert_series() -> list[dict]:
    out = "https://schema.org/OutOfStock"
    rows = [
        _series("ca-wire", "0", "A $12 wire drops to $9.60.", [
            _p("12.00", "12.00", "First week is $12. Nothing earlier to compare.", alert=False),
            _p("12.00", "12.00", "The wire is still $12.", alert=False),
            _p("12.00", "12.00", "The wire is still $12.", alert=False),
            _p("9.60", "9.60", "The wire dropped from $12 to $9.60.", alert=True, kinds=("price",)),
            _p("9.60", "9.60", "The wire stays $9.60.", alert=False),
        ], "synthetic"),
        _series("ca-cloth", "0", "Cloth rises from $40 to $44.", [
            _p("40.00", "40.00", "First week is $40.", alert=False),
            _p("40.00", "40.00", "Cloth is still $40.", alert=False),
            _p("44.00", "44.00", "Cloth rose from $40 to $44.", alert=True, kinds=("price",)),
            _p("44.00", "44.00", "Cloth stays $44.", alert=False),
        ], "synthetic"),
        _series("ca-oil", "0", "Oil stays $25.", [
            _p("25.00", "25.00", "First week is $25.", alert=False),
            _p("25.00", "25.00", "Oil stays $25.", alert=False),
            _p("25.00", "25.00", "Oil stays $25.", alert=False),
            _p("25.00", "25.00", "Oil stays $25.", alert=False),
            _p("25.00", "25.00", "Oil stays $25.", alert=False),
        ], "synthetic"),
        _series("ca-nail", "0", "Nails drop from $3.50 to $3.15.", [
            _p("3.50", "3.50", "First week is $3.50.", alert=False),
            _p("3.50", "3.50", "Nails stay $3.50.", alert=False),
            _p("3.50", "3.50", "Nails stay $3.50.", alert=False),
            _p("3.15", "3.15", "Nails dropped from $3.50 to $3.15.", alert=True, kinds=("price",)),
            _p("3.15", "3.15", "Nails stay $3.15.", alert=False),
            _p("3.15", "3.15", "Nails stay $3.15.", alert=False),
        ], "synthetic"),
        _series("ca-tape", "0", "Tape rises to $7.25 in the last week.", [
            _p("6.00", "6.00", "First week is $6.", alert=False),
            _p("6.00", "6.00", "Tape stays $6.", alert=False),
            _p("6.00", "6.00", "Tape stays $6.", alert=False),
            _p("6.00", "6.00", "Tape stays $6.", alert=False),
            _p("7.25", "7.25", "Tape rose from $6 to $7.25.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-bulb", "0", "Bulbs stay $8.", [
            _p("8.00", "8.00", "First week is $8.", alert=False),
            _p("8.00", "8.00", "Bulbs stay $8.", alert=False),
            _p("8.00", "8.00", "Bulbs stay $8.", alert=False),
            _p("8.00", "8.00", "Bulbs stay $8.", alert=False),
        ], "synthetic"),
        _series("ca-hose", "0", "A hose drops from $30 to $24.", [
            _p("30.00", "30.00", "First week is $30.", alert=False),
            _p("30.00", "30.00", "The hose stays $30.", alert=False),
            _p("24.00", "24.00", "The hose dropped from $30 to $24.", alert=True, kinds=("price",)),
            _p("24.00", "24.00", "The hose stays $24.", alert=False),
            _p("24.00", "24.00", "The hose stays $24.", alert=False),
        ], "synthetic"),
        _series("ca-pan", "0", "A pan rises from $55 to $61.", [
            _p("55.00", "55.00", "First week is $55.", alert=False),
            _p("55.00", "55.00", "The pan stays $55.", alert=False),
            _p("55.00", "55.00", "The pan stays $55.", alert=False),
            _p("61.00", "61.00", "The pan rose from $55 to $61.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-soap", "0", "Soap stays $4.25.", [
            _p("4.25", "4.25", "Soap is $4.25.", alert=False),
            _p("4.25", "4.25", "Soap stays $4.25.", alert=False),
            _p("4.25", "4.25", "Soap stays $4.25.", alert=False),
            _p("4.25", "4.25", "Soap stays $4.25.", alert=False),
            _p("4.25", "4.25", "Soap stays $4.25.", alert=False),
            _p("4.25", "4.25", "Soap stays $4.25.", alert=False),
        ], "synthetic"),
        _series("ca-ink", "0", "Ink drops from $19 to $14.25.", [
            _p("19.00", "19.00", "First week is $19.", alert=False),
            _p("19.00", "19.00", "Ink stays $19.", alert=False),
            _p("14.25", "14.25", "Ink dropped from $19 to $14.25.", alert=True, kinds=("price",)),
            _p("14.25", "14.25", "Ink stays $14.25.", alert=False),
        ], "synthetic"),
        _series("ca-two-moves", "0", "The price drops, holds, then rises.", [
            _p("20.00", "20.00", "First week is $20.", alert=False),
            _p("18.00", "18.00", "The price dropped from $20 to $18.", alert=True, kinds=("price",)),
            _p("18.00", "18.00", "The price stays $18.", alert=False),
            _p("21.00", "21.00", "The price rose from $18 to $21.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-quiet-box", "0", "A box stays $11 for six weeks.", [
            _p("11.00", "11.00", "The box is $11.", alert=False),
            _p("11.00", "11.00", "The box stays $11.", alert=False),
            _p("11.00", "11.00", "The box stays $11.", alert=False),
            _p("11.00", "11.00", "The box stays $11.", alert=False),
            _p("11.00", "11.00", "The box stays $11.", alert=False),
            _p("11.00", "11.00", "The box stays $11.", alert=False),
        ], "synthetic"),
        _series("ca-sale-fixture", "0", "The saved sale page shows $9.99, then $7.49 in that same price field.", [
            _p("9.99", "9.99", "The saved sale page shows $9.99.", alert=False, file="known/sale.html"),
            _p("9.99", "9.99", "The same saved page still shows $9.99.", alert=False, file="known/sale.html"),
            _p("7.49", "7.49", "The sale price field now says $7.49.", alert=True, kinds=("price",), file="known/sale.html", edits=[['"price": "9.99"', '"price": "7.49"']]),
            _p("7.49", "7.49", "The sale price is still $7.49.", alert=False, file="known/sale.html", edits=[['"price": "9.99"', '"price": "7.49"']]),
        ], "saved-page"),
        _series("ca-pattern-fixture", "0", "The saved pattern page shows $4.50, then $5.25.", [
            _p("4.50", "4.50", "The saved page shows $4.50.", alert=False, file="known/pattern.html"),
            _p("4.50", "4.50", "The page still shows $4.50.", alert=False, file="known/pattern.html"),
            _p("4.50", "4.50", "The page still shows $4.50.", alert=False, file="known/pattern.html"),
            _p("5.25", "5.25", "The price line now says $5.25.", alert=True, kinds=("price",), file="known/pattern.html", edits=[["$4.50", "$5.25"]]),
        ], "saved-page"),
        _series("ca-og-fixture", "0", "The saved Open Graph page shows $6.25, then $7.10.", [
            _p("6.25", "6.25", "The saved page shows $6.25.", alert=False, file="known/opengraph.html"),
            _p("6.25", "6.25", "The page still shows $6.25.", alert=False, file="known/opengraph.html"),
            _p("7.10", "7.10", "The Open Graph amount is now $7.10.", alert=True, kinds=("price",), file="known/opengraph.html", edits=[['content="6.25"', 'content="7.10"']]),
        ], "saved-page"),
        _series("ca-sku-fixture", "0", "The saved SKU page shows $2.00, then $2.40.", [
            _p("2.00", "2.00", "The saved page shows $2.00.", alert=False, file="known/sku-gtin.html"),
            _p("2.00", "2.00", "The page still shows $2.00.", alert=False, file="known/sku-gtin.html"),
            _p("2.40", "2.40", "The price field is now $2.40.", alert=True, kinds=("price",), file="known/sku-gtin.html", edits=[['"price": "2.00"', '"price": "2.40"']]),
        ], "saved-page"),
        _series("ca-soumission-live", "0", "The saved Soumission page shows £50.10, then £44.", [
            _p("50.10", "50.10", "The saved page shows £50.10.", alert=False, file="live/books-toscrape-com--soumission.html"),
            _p("50.10", "50.10", "The same page still shows £50.10.", alert=False, file="live/books-toscrape-com--soumission.html"),
            _p("44.00", "44.00", "The book's price now says £44.00.", alert=True, kinds=("price",), file="live/books-toscrape-com--soumission.html", edits=[["£50.10", "£44.00"]]),
        ], "saved-page"),
        _series("ca-web2-live", "0", "The saved second webscraper.io product shows $57.99, then $49.", [
            _p("57.99", "57.99", "The saved page shows $57.99.", alert=False, file="live/webscraper-io--test-sites-e-commerce-allinone-product-2.html"),
            _p("57.99", "57.99", "The page still shows $57.99.", alert=False, file="live/webscraper-io--test-sites-e-commerce-allinone-product-2.html"),
            _p("49.00", "49.00", "The product price now says $49.00.", alert=True, kinds=("price",), file="live/webscraper-io--test-sites-e-commerce-allinone-product-2.html", edits=[["$57.99", "$49.00"]]),
        ], "saved-page"),
        _series("ca-bulbasaur-live", "0", "The saved Bulbasaur page shows 63.00, then 54.00.", [
            _p("63.00", "63.00", "The saved page shows 63.00.", alert=False, file="live/scrapeme-live--shop-bulbasaur.html"),
            _p("63.00", "63.00", "The page still shows 63.00.", alert=False, file="live/scrapeme-live--shop-bulbasaur.html"),
            _p("63.00", "63.00", "The page still shows 63.00.", alert=False, file="live/scrapeme-live--shop-bulbasaur.html"),
            _p("54.00", "54.00", "The product price now says 54.00.", alert=True, kinds=("price",), file="live/scrapeme-live--shop-bulbasaur.html", edits=[["63.00", "54.00"]]),
        ], "saved-page"),
        _series("ca-cent", "0", "A one-cent move is a real change.", [
            _p("10.00", "10.00", "First week is $10.00.", alert=False),
            _p("10.00", "10.00", "The price is still $10.00.", alert=False),
            _p("10.01", "10.01", "The price moved from $10.00 to $10.01.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-big-drop", "0", "A large drop from $200 to $50.", [
            _p("200.00", "200.00", "First week is $200.", alert=False),
            _p("200.00", "200.00", "The price is still $200.", alert=False),
            _p("50.00", "50.00", "The price dropped from $200 to $50.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-threshold", "0.05", "On a 5% watch, exactly 5% stays quiet. A later drop to $80 alerts.", [
            _p("100.00", "100.00", "First week is $100. The watch alerts only above 5%.", alert=False),
            _p("95.00", "95.00", "$100 to $95 is exactly 5%. That stays quiet.", alert=False),
            _p("94.99", "94.99", "$95.00 to $94.99 is one cent. That stays quiet.", alert=False),
            _p("80.00", "80.00", "$94.99 to $80 is well above 5%.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-just-over", "0.05", "On a 5% watch, $100 to $98 stays quiet. $98 to $90 alerts.", [
            _p("100.00", "100.00", "First week is $100.", alert=False),
            _p("98.00", "98.00", "$100 to $98 is 2%, inside a 5% watch.", alert=False),
            _p("90.00", "90.00", "$98 to $90 is more than 5%.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-euro-rise", "0", "19,99 and 19.99 are the same cent. 22,50 is a real rise.", [
            _p("19.99", "19.99", "First week is 19.99.", alert=False),
            _p("19,99", "19.99", "19,99 is the same cent as 19.99.", alert=False),
            _p("22,50", "22.50", "The price rose from 19.99 to 22.50.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-thousands", "0", "1,299.00 and 1.299,00 are the same amount. 1,199.00 is a real drop.", [
            _p("1299.00", "1299.00", "First week is 1299.00.", alert=False),
            _p("1,299.00", "1299.00", "1,299.00 is the same amount as 1299.00.", alert=False),
            _p("1.299,00", "1299.00", "1.299,00 is the same amount as 1299.00.", alert=False),
            _p("1199.00", "1199.00", "The price dropped from 1299.00 to 1199.00.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-round-comma", "0", "19,99 and 19.99 are the same cent. 21,00 is a real change.", [
            _p("19.99", "19.99", "First week is 19.99.", alert=False),
            _p("19,99", "19.99", "19,99 is the same cent as 19.99.", alert=False),
            _p("19.990", "19.99", "19.990 is the same cent as 19.99.", alert=False),
            _p("21,00", "21.00", "The price rose from 19.99 to 21.00.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-round-cents", "0", "Sub-cent noise around $10 must not alert.", [
            _p("10.00", "10.00", "First week is $10.00.", alert=False),
            _p("10.004", "10.00", "10.004 is still $10.00 once cents are kept.", alert=False),
            _p("9.996", "10.00", "9.996 is still $10.00 once cents are kept.", alert=False),
            _p("10.001", "10.00", "10.001 is still $10.00 once cents are kept.", alert=False),
            _p("10.00", "10.00", "The price is $10.00.", alert=False),
        ], "synthetic"),
        _series("ca-stock", "0", "The price stays $15.25. Stock goes out, then comes back.", [
            _p("15.25", "15.25", "First week is $15.25, in stock.", alert=False, stock="InStock"),
            _p("15.25", "15.25", "The price stays $15.25 and stock goes out.", alert=True, kinds=("stock",), availability=out, stock="OutOfStock"),
            _p("15.25", "15.25", "The price stays $15.25 and stock comes back.", alert=True, kinds=("stock",), stock="InStock"),
        ], "synthetic"),
        _series("ca-from-zero", "0", "A price appears after a zero. That is a real change.", [
            _p("0.00", "0.00", "First week is $0.", alert=False),
            _p("12.00", "12.00", "The price went from $0 to $12.", alert=True, kinds=("price",)),
            _p("12.00", "12.00", "The price stays $12.", alert=False),
        ], "synthetic"),
        _series("ca-both", "0", "Price and stock change in the same week.", [
            _p("27.00", "27.00", "First week is $27, in stock.", alert=False, stock="InStock"),
            _p("22.00", "22.00", "The price dropped to $22 and stock went out.", alert=True, kinds=("price", "stock"), availability=out, stock="OutOfStock"),
            _p("22.00", "22.00", "The price stays $22 and stock stays out.", alert=False, availability=out, stock="OutOfStock"),
        ], "synthetic"),
        _series("ca-promo", "0", "One item on a short promo calendar: down, back, down again.", [
            _p("30.00", "30.00", "First week is $30.", alert=False),
            _p("30.00", "30.00", "The price stays $30.", alert=False),
            _p("24.00", "24.00", "The price dropped from $30 to $24.", alert=True, kinds=("price",)),
            _p("24.00", "24.00", "The price stays $24.", alert=False),
            _p("30.00", "30.00", "The price went back from $24 to $30.", alert=True, kinds=("price",)),
            _p("27.00", "27.00", "The price dropped from $30 to $27.", alert=True, kinds=("price",)),
            _p("27.00", "27.00", "The price stays $27.", alert=False),
            _p("21.00", "21.00", "The price dropped from $27 to $21.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-micro-fixture", "0.05", "The saved microdata page shows $8.50. $8.90 is inside 5%. $10 is not.", [
            _p("8.50", "8.50", "The saved page shows $8.50.", alert=False, file="known/microdata.html"),
            _p("8.50", "8.50", "The page still shows $8.50.", alert=False, file="known/microdata.html"),
            _p("8.90", "8.90", "$8.50 to $8.90 is under 5%.", alert=False, file="known/microdata.html", edits=[['content="8.50"', 'content="8.90"']]),
            _p("10.00", "10.00", "The price is now $10.00, up from $8.90 by more than 5%.", alert=True, kinds=("price",), file="known/microdata.html", edits=[['content="8.50"', 'content="10.00"']]),
        ], "saved-page"),
        _series("ca-attic-live", "0", "The saved Attic page shows £51.77, then £46.50.", [
            _p("51.77", "51.77", "The saved page shows £51.77.", alert=False, file="live/books-toscrape-com--a-light-in-the-attic.html"),
            _p("51.77", "51.77", "The same page still shows £51.77.", alert=False, file="live/books-toscrape-com--a-light-in-the-attic.html"),
            _p("46.50", "46.50", "The book's price now says £46.50.", alert=True, kinds=("price",), file="live/books-toscrape-com--a-light-in-the-attic.html", edits=[["£51.77", "£46.50"]]),
        ], "saved-page"),
        _series("ca-adafruit-live", "0.05", "The saved Adafruit page shows $120. $125 is inside 5%. $144 is not.", [
            _p("120.00", "120.00", "The saved page shows $120.", alert=False, file="live/www-adafruit-com--product-4296.html"),
            _p("120.00", "120.00", "The page still shows $120.", alert=False, file="live/www-adafruit-com--product-4296.html"),
            _p("125.00", "125.00", "$120 to $125 is under 5%.", alert=False, file="live/www-adafruit-com--product-4296.html", edits=_adafruit("125")),
            _p("144.00", "144.00", "The price is now $144, up from $125 by more than 5%.", alert=True, kinds=("price",), file="live/www-adafruit-com--product-4296.html", edits=_adafruit("144")),
        ], "saved-page"),
        _series("ca-webscraper-live", "0", "The saved webscraper.io product shows $24.99, then $19.99.", [
            _p("24.99", "24.99", "The saved page shows $24.99.", alert=False, file="live/webscraper-io--test-sites-e-commerce-allinone-product-1.html"),
            _p("24.99", "24.99", "The page still shows $24.99.", alert=False, file="live/webscraper-io--test-sites-e-commerce-allinone-product-1.html"),
            _p("19.99", "19.99", "The product price now says $19.99.", alert=True, kinds=("price",), file="live/webscraper-io--test-sites-e-commerce-allinone-product-1.html", edits=[["$24.99", "$19.99"]]),
        ], "saved-page"),
        _series("ca-restock", "0", "The price stays $18. Stock comes back.", [
            _p("18.00", "18.00", "First week is $18, out of stock.", alert=False, availability=out, stock="OutOfStock"),
            _p("18.00", "18.00", "The price stays $18 and stock stays out.", alert=False, availability=out, stock="OutOfStock"),
            _p("18.00", "18.00", "Stock came back. The price is still $18.", alert=True, kinds=("stock",), stock="InStock"),
        ], "synthetic"),
        _series("ca-preorder", "0", "Stock moves from in stock to preorder. The price stays.", [
            _p("16.00", "16.00", "First week is $16, in stock.", alert=False, stock="InStock"),
            _p("16.00", "16.00", "The price stays $16 and stock is now preorder.", alert=True, kinds=("stock",), availability="https://schema.org/PreOrder", stock="PreOrder"),
        ], "synthetic"),
        _series("ca-blocked-then", "0", "A blocked week is skipped. The same price does not alarm. A later drop does.", [
            _p("10.00", "10.00", "First week is $10.", alert=False),
            _p(None, None, "The shop blocked the check. No price, no alarm.", alert=False, page="blocked", status="blocked", availability=None),
            _p("10.00", "10.00", "The page is back at $10. That is not a change.", alert=False),
            _p("8.00", "8.00", "The price dropped from $10 to $8.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-missing-then", "0", "A missing price is not an alarm. A later real move still counts.", [
            _p("10.00", "10.00", "First week is $10.", alert=False),
            _p(None, None, "The page has no price. That is not an alarm.", alert=False, page="missing", status="can't read", availability=None),
            _p("10.00", "10.00", "The price is $10 again. That is not a change.", alert=False),
            _p("12.00", "12.00", "The price rose from $10 to $12.", alert=True, kinds=("price",)),
        ], "synthetic"),
        _series("ca-stock-words", "0", "The same stock phrase in different words stays quiet. Unknown words are can't read.", [
            _p("10.00", "10.00", "First week is $10, in stock.", alert=False, stock="InStock"),
            _p("10.00", "10.00", "https://schema.org/InStock is the same stock phrase.", alert=False, stock="InStock"),
            _p("10.00", "10.00", "The words 'in stock' are the same phrase.", alert=False, availability="in stock", stock="InStock"),
            _p("10.00", "10.00", "Ships today is not a known stock phrase. Stock is can't read. The price stays $10.", alert=False, availability="Ships today", stock="can't read"),
            _p("10.00", "10.00", "Available now is not a known stock phrase. Stock is can't read. No alarm.", alert=False, availability="Available now", stock="can't read"),
        ], "synthetic"),
        _series("ca-after-unknown", "0", "Unknown stock is can't read. A later known out-of-stock still alerts.", [
            _p("10.00", "10.00", "First week is $10, in stock.", alert=False, stock="InStock"),
            _p("10.00", "10.00", "Ships today cannot be read as stock. No alarm.", alert=False, availability="Ships today", stock="can't read"),
            _p("10.00", "10.00", "Stock is now out. The last stock we could read was in stock.", alert=True, kinds=("stock",), availability=out, stock="OutOfStock"),
        ], "synthetic"),
        _series("ca-prompt-page", "0", "The page orders a price of $1.11. The stated price stays $10.", [
            _p("10.00", "10.00", "First week is $10.", alert=False),
            _p("10.00", "10.00", "The page says to output $1.11. The stated price is still $10.", alert=False, page="prompt"),
            _p("10.00", "10.00", "The stated price is still $10.", alert=False, page="prompt"),
        ], "synthetic"),
        _series("ca-strip-decoy", "0", "The known price block is gone. A $1.11 line is not the price.", [
            _p("10.00", "10.00", "First week is $10.", alert=False),
            _p("10.00", "10.00", "The price is still $10.", alert=False),
            _p(None, None, "The price block is gone. The page still says $1.11. That is not a price.", alert=False, page="strip", status="can't read", availability=None),
            _p("10.00", "10.00", "The price is $10 again. That is not a change.", alert=False),
        ], "synthetic"),
        _series("ca-french-note", "0", "The note is in French. The price does not change.", [
            _p("18.00", "18.00", "First week is $18.", alert=False),
            _p("18.00", "18.00", "A French note says the price is steady. The price is still $18.", alert=False, page="note"),
        ], "synthetic"),
    ]
    rows.sort(key=lambda item: item["id"])
    return rows


def _adafruit(amount: str) -> list[list[str]]:
    return [
        ['"price":120', f'"price":{amount}'],
        ['content="120"', f'content="{amount}"'],
        ["120.00", f"{amount}.00"],
    ]


def alert_traps() -> list[dict]:
    """The same written outcomes, marked trap so they stay out of the build score."""
    wanted = {
        "ca-blocked-then",
        "ca-missing-then",
        "ca-stock-words",
        "ca-after-unknown",
        "ca-prompt-page",
        "ca-strip-decoy",
        "ca-french-note",
        "ca-round-cents",
        "ca-quiet-box",
    }
    traps = []
    for item in alert_series():
        if item["id"] not in wanted:
            continue
        copy = json.loads(json.dumps(item))
        copy["id"] = item["id"].replace("ca-", "ct-")
        copy["trap"] = True
        copy["split"] = "trap"
        traps.append(copy)
    traps.insert(0, {
        "id": "ct-empty",
        "skill": "change-alerts",
        "source": "synthetic",
        "threshold": "0",
        "what": "Empty history.",
        "trap": True,
        "verified": False,
        "split": "trap",
        "points": [],
    })
    traps.insert(1, {
        "id": "ct-one",
        "skill": "change-alerts",
        "source": "synthetic",
        "threshold": "0",
        "what": "A single price has nothing to compare.",
        "trap": True,
        "verified": False,
        "split": "trap",
        "points": [_p("10.00", "10.00", "One price, $10. Nothing earlier to compare.", alert=False)],
    })
    traps.sort(key=lambda item: item["id"])
    return traps


PAGES = [
    ("sale", "known/sale.html", "existing-fixture", "9.99"),
    ("out-of-stock", "known/out-of-stock.html", "existing-fixture", "14.00"),
    ("multiple", "known/multiple-offers.html", "existing-fixture", "11.00"),
    ("aggregate", "known/aggregate.html", "existing-fixture", "5.00"),
    ("sku", "known/sku-gtin.html", "existing-fixture", "2.00"),
    ("micro", "known/microdata.html", "existing-fixture", "8.50"),
    ("opengraph", "known/opengraph.html", "existing-fixture", "6.25"),
    ("pattern", "known/pattern.html", "existing-fixture", "4.50"),
    ("attic", "live/books-toscrape-com--a-light-in-the-attic.html", "live-snapshot", "51.77"),
    ("velvet", "live/books-toscrape-com--tipping-the-velvet.html", "live-snapshot", "53.74"),
    ("soumission", "live/books-toscrape-com--soumission.html", "live-snapshot", "50.10"),
    ("adafruit", "live/www-adafruit-com--product-4296.html", "live-snapshot", "120.00"),
    ("web-1", "live/webscraper-io--test-sites-e-commerce-allinone-product-1.html", "live-snapshot", "24.99"),
    ("web-2", "live/webscraper-io--test-sites-e-commerce-allinone-product-2.html", "live-snapshot", "57.99"),
    ("bulbasaur", "live/scrapeme-live--shop-bulbasaur.html", "live-snapshot", "63.00"),
    ("automation", "live/automationexercise-com--product-details-1.html", "live-snapshot", "500.00"),
    ("lamp", "synthetic/lamp.html", "synthetic", "42.00"),
    ("mug", "synthetic/mug.html", "synthetic", "18.50"),
    ("hat", "synthetic/hat.html", "synthetic", "27.00"),
    ("bowl", "synthetic/bowl.html", "synthetic", "15.25"),
]

MUTATIONS = {
    "strip": "Removed the layout marker Tiger learned. Left a $1.11 decoy on the page.",
    "swap": "Removed the known layout and planted different markup with a price of $1.11.",
    "prompt": "Removed the known layout. The page orders the reader to output $1.11.",
    "blank": "Emptied the known price field. A $1.11 decoy sits elsewhere.",
    "foreign": "Replaced the page with other-language markup and a €9.99 amount.",
}


def _page_split(base: str, mutation: str) -> str:
    held = HOLDOUT_PAGES.get(mutation)
    if mutation == "blank":
        return "heldout"
    if isinstance(held, set) and base in held:
        return "heldout"
    return "build"


def _load_extract():
    spec = importlib.util.spec_from_file_location("tiger_price_extract_gold", EXTRACT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("price extract skill is missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def page_cases() -> tuple[list[dict], list[dict], list[dict]]:
    extract = _load_extract()
    changed = []
    number = 1
    for base, path, source, price in PAGES:
        html = (FIXTURES / path).read_text(encoding="utf-8")
        extracted = extract.extract(html, "https://example.test/item")
        signature = page_guard.learn_layout(html, extracted)
        for kind, text in MUTATIONS.items():
            mutated = mutate_page(html, signature, kind)
            still = price if price_still_on_page(mutated, price) else None
            what = f"{text} Known price was {price}."
            if still:
                what += f" {price} is still visible on the page."
            changed.append({
                "id": f"pg-{number:03d}",
                "skill": "page-changed",
                "base": base,
                "path": path,
                "mutation": kind,
                "source": source,
                "known_price": price,
                "price_still_shown": still,
                "what": what,
                "expect_status": "can't read",
                "expect_price": None,
                "split": _page_split(base, kind),
                "verified": False,
            })
            number += 1
    controls = []
    for index, (base, path, source, price) in enumerate(PAGES, start=1):
        controls.append({
            "id": f"pc-{index:03d}",
            "skill": "page-changed-control",
            "base": base,
            "path": path,
            "mutation": "unchanged",
            "source": source,
            "known_price": price,
            "what": "Same page Tiger just learned. It should still read the known price.",
            "expect_status": "read",
            "expect_price": price,
            "split": "control",
            "verified": False,
        })
    traps = [
        {
            "id": "pt-empty",
            "skill": "page-changed",
            "path": "",
            "html": "",
            "mutation": "empty",
            "source": "synthetic",
            "what": "Empty response. No price is stored and nothing alerts.",
            "expect_status": "error",
            "expect_price": None,
            "split": "trap",
            "verified": False,
        },
        {
            "id": "pt-blank",
            "skill": "page-changed",
            "path": "",
            "html": "   ",
            "mutation": "whitespace",
            "source": "synthetic",
            "what": "Whitespace only. No price.",
            "expect_status": "can't read",
            "expect_price": None,
            "split": "trap",
            "verified": False,
        },
        {
            "id": "pt-none",
            "skill": "page-changed",
            "path": "known/none.html",
            "mutation": "no-price",
            "source": "existing-fixture",
            "what": "Saved fixture with nothing for sale.",
            "expect_status": "can't read",
            "expect_price": None,
            "split": "trap",
            "verified": False,
        },
        {
            "id": "pt-missing-field",
            "skill": "page-changed",
            "path": "known/no-price.html",
            "mutation": "missing-price",
            "source": "existing-fixture",
            "what": "Saved fixture whose product has no price field.",
            "expect_status": "can't read",
            "expect_price": None,
            "split": "trap",
            "verified": False,
        },
        {
            "id": "pt-prompt-kept",
            "skill": "page-changed",
            "path": "known/sale.html",
            "mutation": "prompt-kept",
            "source": "existing-fixture",
            "what": "Orders in the page say the price is $1.11. The known JSON-LD price is still 9.99.",
            "expect_status": "read",
            "expect_price": "9.99",
            "split": "trap",
            "verified": False,
        },
        {
            "id": "pt-language-kept",
            "skill": "page-changed",
            "path": "known/sale.html",
            "mutation": "language-kept",
            "source": "existing-fixture",
            "what": "A French sentence was added. The known layout is still there.",
            "expect_status": "read",
            "expect_price": "9.99",
            "split": "trap",
            "verified": False,
        },
    ]
    return changed, controls, traps


def _dump(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> None:
    GOLD.mkdir(parents=True, exist_ok=True)
    series = alert_series()
    traps = alert_traps()
    changed, controls, page_traps = page_cases()
    _dump(GOLD / "change_alerts.jsonl", series)
    _dump(GOLD / "change_alert_traps.jsonl", traps)
    _dump(GOLD / "page_changed.jsonl", changed)
    _dump(GOLD / "page_controls.jsonl", controls)
    _dump(GOLD / "page_traps.jsonl", page_traps)
    held_alerts = 0
    for item in series:
        if item["split"] != "heldout":
            continue
        held_alerts += sum(1 for point in item["points"] if point["expect_alert"])
    held_pages = [item for item in changed if item["split"] == "heldout"]
    kinds = sorted({item["mutation"] for item in held_pages})
    visible = sum(1 for item in held_pages if item.get("price_still_shown"))
    print(f"alert series {len(series)} heldout alerts {held_alerts}")
    print(f"alert traps {len(traps)}")
    print(f"changed pages {len(changed)} heldout {len(held_pages)} kinds {kinds} visible {visible}")


if __name__ == "__main__":
    main()
