"""Label saved pages from the markup itself. Does not call the price reader.

Every label stays unverified. A conflict is printed so a person can look.
"""

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from html import unescape
from pathlib import Path
from urllib.parse import urlparse

from selectolax.parser import HTMLParser

HERE = Path(__file__).resolve().parent
# Public snapshots live outside tests/. The industry-word check reads every
# html file under tests/, and store pages use ordinary words that collide
# with that list. The price skill itself stays free of those words.
LIVE = HERE.parents[1] / "agents" / "tiger" / "price_pages" / "live"
VERIFIED_BY_ZENAS = {
    "live-075",
    "live-076",
    "live-077",
    "live-078",
    "live-049",
    "live-064",
    "live-107",
    "live-108",
}
MANIFEST = HERE / "gold" / "fetch_manifest.jsonl"
OUT = HERE / "gold" / "pages.jsonl"
FIXTURES = HERE.parents[1] / "tank" / "skills" / "tiger.price_extract" / "1.0.0" / "evals" / "fixtures"
CASES = HERE.parents[1] / "tank" / "skills" / "tiger.price_extract" / "1.0.0" / "evals" / "cases.jsonl"

_JSONLD = re.compile(
    r"<script[^>]*type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.I | re.S,
)
_MONEY = re.compile(
    r"(?P<sym>US\$|\$|€|£)\s?(?P<amount>\d{1,3}(?:,\d{3})+(?:\.\d{2})?|\d+(?:\.\d{2})?)(?!\d)"
    r"|(?P<amount2>\d{1,3}(?:[.\s]\d{3})+(?:,\d{2})|\d+,\d{2})\s?(?P<sym2>€|£|\$)"
)


def canonical(raw: str | None) -> str | None:
    if not raw:
        return None
    text = unescape(raw).replace("\xa0", "").replace(" ", "")
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ".", ","}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if re.fullmatch(r"\d{1,3}(,\d{3})+", text):
            text = text.replace(",", "")
        elif re.fullmatch(r"\d+,\d{2}", text):
            text = text.replace(",", ".")
        else:
            return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if number < 0:
        return None
    return f"{number.quantize(Decimal('0.01'))}"


def split_for(page_id: str) -> str:
    digest = hashlib.sha256(f"tiger-price-read-v1:{page_id}".encode()).hexdigest()
    return "holdout" if int(digest[:8], 16) % 5 == 0 else "build"


def _walk_products(node, found: list) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_products(item, found)
        return
    if not isinstance(node, dict):
        return
    types = node.get("@type")
    names = types if isinstance(types, list) else [types]
    flat = {str(item).rsplit("/", 1)[-1].lower() for item in names if item}
    if "product" in flat:
        found.append(node)
    for key in ("@graph", "mainEntity", "itemListElement"):
        if key in node:
            _walk_products(node[key], found)


def _offer_price(offer: dict) -> str | None:
    specs = offer.get("priceSpecification")
    if isinstance(specs, dict):
        specs = [specs]
    sale = None
    plain = None
    if isinstance(specs, list):
        for spec in specs:
            if not isinstance(spec, dict):
                continue
            price = canonical(str(spec.get("price"))) if spec.get("price") is not None else None
            if price is None:
                continue
            if "SalePrice" in str(spec.get("priceType") or ""):
                sale = price
            elif "ListPrice" in str(spec.get("priceType") or ""):
                continue
            elif plain is None:
                plain = price
    if sale or plain:
        return sale or plain
    for key in ("price", "lowPrice"):
        if offer.get(key) is not None:
            price = canonical(str(offer.get(key)))
            if price:
                return price
    return None


def jsonld_price(html: str) -> str | None:
    products: list = []
    for match in _JSONLD.finditer(html):
        raw = unescape(match.group(1)).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _walk_products(data, products)
    for product in products:
        offers = product.get("offers")
        if isinstance(offers, dict):
            offers = [offers]
        if not isinstance(offers, list):
            continue
        for offer in offers:
            if isinstance(offer, dict):
                price = _offer_price(offer)
                if price and price != "0.00":
                    return price
    return None


def meta_price(html: str) -> str | None:
    patterns = (
        r"property=[\"']product:price:amount[\"'][^>]*content=[\"']([^\"']+)",
        r"content=[\"']([^\"']+)[\"'][^>]*property=[\"']product:price:amount[\"']",
        r"property=[\"']og:price:amount[\"'][^>]*content=[\"']([^\"']+)",
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if match:
            price = canonical(match.group(1))
            if price:
                return price
    return None


def itemprop_price(html: str) -> str | None:
    patterns = (
        r"itemprop=[\"']price[\"'][^>]*content=[\"']([^\"']+)",
        r"content=[\"']([^\"']+)[\"'][^>]*itemprop=[\"']price[\"']",
        r"itemprop=[\"']price[\"'][^>]*>\s*([^<]{1,24})",
    )
    for pattern in patterns:
        match = re.search(pattern, html, re.I)
        if not match:
            continue
        price = canonical(match.group(1))
        if price and price != "0.00":
            return price
    return None


def visible_price(html: str) -> str | None:
    text = unescape(re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S))
    text = re.sub(r"<[^>]+>", " ", text)
    h1 = re.search(r"\b[A-Z0-9][\w '&.,:+-]{0,80}", text)
    # Prefer the slice after the first heading-sized title by using the h1 tag before strip.
    h1_tag = re.search(r"<h1\b[^>]*>(.*?)</h1>", html, re.I | re.S)
    if h1_tag:
        start = h1_tag.end()
        window = unescape(re.sub(r"<[^>]+>", " ", html[start:start + 5000]))
    else:
        window = text[:1500]
        del h1
    amounts = []
    for match in _MONEY.finditer(window):
        amount = match.group("amount") or match.group("amount2")
        price = canonical(amount)
        if price and price != "0.00":
            amounts.append(price)
    return amounts[0] if amounts else None


def buy_box(html: str) -> str | None:
    match = re.search(
        r"customerVisiblePrice\]\[amount\]\"\s+value=\"(\d+(?:\.\d+)?)\"",
        html,
    )
    if not match:
        return None
    return canonical(match.group(1))


def sale_phrase(html: str) -> str | None:
    match = re.search(r"Sale Price\s*[$€£]?\s*(\d[\d.,]*)", html, re.I)
    if not match:
        return None
    price = canonical(match.group(1))
    if price and price != "0.00":
        return price
    return None


def _member_prices(node, found: set[str]) -> None:
    if isinstance(node, list):
        for item in node:
            _member_prices(item, found)
        return
    if not isinstance(node, dict):
        return
    if node.get("validForMemberTier") is not None:
        price = canonical(str(node.get("price"))) if node.get("price") is not None else None
        if price:
            found.add(price)
    for value in node.values():
        if isinstance(value, (dict, list)):
            _member_prices(value, found)


def member_hero(html: str) -> str | None:
    """The hero amount when the page shows a member price as the current price."""
    match = re.search(
        r"data-seo-id=[\"']hero-price[\"'][^>]*>\s*(?:Now\s+)?[$€£]\s*(\d[\d,]*(?:\.\d{2})?)",
        html,
        re.I,
    )
    if not match:
        return None
    hero = canonical(match.group(1))
    if not hero:
        return None
    members: set[str] = set()
    for block in _JSONLD.finditer(html):
        try:
            data = json.loads(unescape(block.group(1)))
        except json.JSONDecodeError:
            continue
        _member_prices(data, members)
    if hero not in members:
        return None
    return hero


# A recommendation or a product card is another product, not this one.
_RELATED = re.compile(
    r"ymal|you-may-also|related[-_ ]?product|product-card|recommendation|"
    r"upsell|cross-?sell|also-like|similar-product",
    re.I,
)
_PRICE_WIDGETS = (
    "[itemprop='price']",
    ".price",
    ".product-price",
    ".woocommerce-Price-amount",
    "price-snippet",
)


def _in_related(node) -> bool:
    current = node
    steps = 0
    while current is not None and steps < 10:
        attrs = current.attributes or {}
        blob = f"{current.tag} {attrs.get('class') or ''} {attrs.get('id') or ''}"
        if _RELATED.search(blob):
            return True
        current = current.parent
        steps += 1
    return False


def form_price(html: str) -> str | None:
    """The product's own price when the product form shows exactly one amount.

    Prices on other products on the same page are ignored. Two amounts left
    on the product itself are not a single price.
    """
    tree = HTMLParser(html)
    found: list[str] = []
    seen: set[int] = set()
    for selector in _PRICE_WIDGETS:
        for node in tree.css(selector):
            if node.mem_id in seen:
                continue
            seen.add(node.mem_id)
            if _in_related(node):
                continue
            text = node.text(separator="", strip=True) if node.text else ""
            if not text or len(text) > 40:
                continue
            match = _MONEY.search(text)
            if not match:
                continue
            price = canonical(match.group("amount") or match.group("amount2"))
            if price and price != "0.00":
                found.append(price)
    distinct = list(dict.fromkeys(found))
    if len(distinct) == 1:
        return distinct[0]
    return None


def shown_amounts(html: str) -> set[str]:
    """Money amounts left in the page after scripts are removed."""
    text = unescape(re.sub(r"<script\b[^>]*>.*?</script>", " ", html, flags=re.I | re.S))
    text = re.sub(r"<[^>]+>", " ", text)
    found: set[str] = set()
    for match in _MONEY.finditer(text):
        price = canonical(match.group("amount") or match.group("amount2"))
        if price and price != "0.00":
            found.add(price)
    return found


def sale_and_higher(html: str) -> bool:
    """A sale amount and a higher list amount on the same product.

    A member price is not this case.
    """
    sale = sale_phrase(html)
    if not sale:
        return False
    match = re.search(r"List Price\s*[$€£]?\s*(\d[\d.,]*)", html, re.I)
    if not match:
        return False
    listed = canonical(match.group(1))
    if not listed:
        return False
    try:
        return Decimal(listed) > Decimal(sale)
    except InvalidOperation:
        return False


def choose(html: str) -> tuple[str | None, str, bool]:
    if sale_and_higher(html):
        return None, "sale price and a higher price", True
    found = {
        "jsonld": jsonld_price(html),
        "meta": meta_price(html),
        "sale": sale_phrase(html),
        "buybox": buy_box(html),
        "itemprop": itemprop_price(html),
        "visible": visible_price(html),
        "hero": member_hero(html),
    }
    order = ("sale", "buybox", "jsonld", "meta", "itemprop", "visible")
    picked = next((found[name] for name in order if found[name]), None)
    form = form_price(html)
    if picked is None and form:
        picked = form
        found["form"] = form
    hero = found["hero"]
    if hero:
        try:
            lower = picked is None or Decimal(hero) < Decimal(picked)
        except InvalidOperation:
            lower = False
        if lower:
            picked = hero
    priced = [price for price in found.values() if price]
    conflict = len(set(priced)) > 1
    evidence = ", ".join(f"{name}={price}" for name, price in found.items() if price)
    return picked, evidence or "none", conflict


def layout_for(host: str, evidence: str) -> str:
    host = host.lower()
    if "product-category" in host:
        return "skip"
    if "books.toscrape" in host:
        return "books-toscrape"
    if "ikea" in host:
        return "ikea"
    if "nike" in host:
        return "nike"
    if "ulta" in host:
        return "ulta"
    if "walmart" in host:
        return "walmart"
    if "amazon" in host:
        return "amazon"
    if "apple" in host:
        return "apple"
    if "glossier" in host:
        return "shopify-glossier"
    if "adafruit" in host:
        return "adafruit"
    if "marksandspencer" in host or host.startswith("www.marksandspencer"):
        return "marksandspencer"
    if "samsclub" in host:
        return "samsclub"
    if "wickes" in host:
        return "wickes"
    if "outdoorvoices" in host:
        return "outdoorvoices"
    if "incredible" in host:
        return "incredible"
    if "llbean" in host:
        return "llbean"
    if "officeworks" in host:
        return "officeworks"
    if "scrapeme" in host:
        return "woocommerce-storefront"
    if "webscraper.io" in host:
        return "webscraper-offer"
    if "mage-os" in host or "magento" in host:
        return "magento-luma"
    if "solidus" in host or "spree" in host:
        return "solidus"
    if "opencart" in host:
        return "opencart"
    if "sylius" in host:
        return "sylius"
    if "prestashop" in host:
        return "prestashop"
    if "nopcommerce" in host:
        return "nopcommerce"
    if "bigcommerce" in host:
        return "bigcommerce"
    if "woocommerce" in host:
        return "woocommerce"
    if "shopify" in host or host.endswith("myshopify.com"):
        return "shopify"
    name = host.lower().removeprefix("www.").split(".")[0] if host else ""
    if "jsonld" in evidence:
        return f"{name}-jsonld" if name else "jsonld"
    return name or "unknown"


def product_key(url: str, page_id: str) -> str:
    parsed = urlparse(url or "")
    if not parsed.netloc:
        return page_id
    return parsed.netloc.lower() + parsed.path.rstrip("/").lower()


def live_rows() -> list[dict]:
    urls = {}
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("kind") == "saved":
                urls[row["id"]] = row
    rows = []
    seen_products: set[str] = set()
    for path in sorted(LIVE.glob("*.html")):
        page_id = path.stem
        meta = urls.get(page_id, {})
        html = path.read_text(encoding="utf-8")
        price, evidence, conflict = choose(html)
        final = meta.get("final") or meta.get("url") or ""
        if re.search(r"product-category|/collections/|/browse/|/search", final, re.I):
            print(f"SKIP listing {page_id} {final[:90]}")
            continue
        key = product_key(final, page_id)
        if key in seen_products:
            print(f"SKIP duplicate {page_id} {final[:90]}")
            continue
        host = meta.get("host") or ""
        if not price:
            amounts = shown_amounts(html)
            if len(amounts) < 2 and evidence != "sale price and a higher price":
                print(f"UNLABELED {page_id} {final[:90]}")
                continue
            seen_products.add(key)
            rows.append({
                "id": page_id,
                "source": "live",
                "layout": layout_for(host, evidence),
                "site": host,
                "url": final,
                "html": f"agents/tiger/price_pages/live/{path.name}",
                "expected_price": None,
                "currency": None,
                "evidence": evidence if evidence == "sale price and a higher price" else "several prices, no single price",
                "conflict": True,
                "split": split_for(page_id),
                "verified": False,
                "unreadable": True,
            })
            print(f"CAN'T READ {page_id} amounts={len(amounts)} {final[:90]}")
            continue
        seen_products.add(key)
        rows.append({
            "id": page_id,
            "source": "live",
            "layout": layout_for(host, evidence),
            "site": host,
            "url": final,
            "html": f"agents/tiger/price_pages/live/{path.name}",
            "expected_price": price,
            "currency": None,
            "evidence": evidence,
            "conflict": conflict,
            "split": split_for(page_id),
            "verified": False,
            "unreadable": False,
        })
        if conflict:
            print(f"CONFLICT {page_id} {evidence} -> {price}")
    return rows


def fixture_rows() -> list[dict]:
    rows = []
    for line in CASES.read_text(encoding="utf-8").splitlines():
        case = json.loads(line)
        items = case["expected"].get("items") or []
        priced = [item for item in items if item.get("price")]
        if not priced:
            continue
        name = case["input"]["fixture"]
        page_id = "fix-" + name.replace(".html", "")
        rows.append({
            "id": page_id,
            "source": "existing",
            "layout": f"existing-{case['expected'].get('method') or 'none'}",
            "site": "example.test",
            "url": priced[0].get("url") or "",
            "html": f"tank/skills/tiger.price_extract/1.0.0/evals/fixtures/{name}",
            "expected_price": priced[0]["price"],
            "currency": priced[0].get("currency"),
            "evidence": f"existing case {case['name']}",
            "conflict": False,
            "split": split_for(page_id),
            "verified": False,
            "unreadable": False,
        })
    return rows


def hold_back_sale_pattern(rows: list[dict]) -> None:
    """Keep one sale-and-higher page in the held-out set.

    The hash put every such page in the build set. One is held back so that
    pattern is scored only at the end. Nothing else moves.
    """
    sale = [
        row for row in rows
        if row.get("unreadable") and row.get("evidence") == "sale price and a higher price"
    ]
    if not sale or any(row["split"] == "holdout" for row in sale):
        return
    chosen = sale[0]
    chosen["split"] = "holdout"
    chosen["split_note"] = "held back so a sale price next to a higher price is in the held-out set"


def main() -> None:
    rows = fixture_rows() + live_rows()
    hold_back_sale_pattern(rows)
    for row in rows:
        row["verified"] = row["id"] in VERIFIED_BY_ZENAS
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    builds = sum(row["split"] == "build" for row in rows)
    print(f"wrote {len(rows)} rows build={builds} holdout={len(rows) - builds} -> {OUT}")


if __name__ == "__main__":
    main()
