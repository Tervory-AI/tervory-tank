"""Save public product pages for Tiger's price-read gold set.

Honest browsing only: one request at a time, a real user agent, robots.txt
respected, no login, no proxy, no CAPTCHA, no challenge bypass. A blocked
host is recorded and skipped. Tests never call this module.
"""

from __future__ import annotations

import json
import re
import ssl
import time
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from http.client import InvalidURL
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
# Snapshots stay outside tests/. See label_pages.LIVE.
HTML_DIR = ROOT.parents[1] / "agents" / "tiger" / "price_pages" / "live"
MANIFEST = ROOT / "gold" / "fetch_manifest.jsonl"
UA = "TervoryTiger/0.1 (+https://tervory.com)"
DELAY_S = 2.5
SAME_HOST_DELAY_S = 8.0
TIMEOUT_S = 12
MAX_BYTES = 1_500_000
MAX_PER_HOST = 8
MAX_SAVED = 110

SKIP_PARTS = (
    "login", "signin", "sign-in", "account", "cart", "checkout", "wishlist",
    "customer", "my-account", "register", "password", "review",
)
# A single product URL, not a category, search, or brand index.
PRODUCT_URL = re.compile(
    r"("
    r"product_id=\d+"
    r"|/products?/[^/?#]+/?$"
    r"|/app/\d+"
    r"|/en/game/[^/?#]+"
    r"|/ip/[^/?#]+"
    r"|/t/[^/?#]+"
    r"|/p/[^/?#]+"
    r"|/catalogue/[a-z0-9-]{3,}_\d+/index\.html"
    r"|/itm/\d+"
    r"|/dp/[A-Z0-9]{8,}"
    r"|/gp/product/[A-Z0-9]+"
    r"|route=product/product"
    r")",
    re.I,
)
LISTING_URL = re.compile(
    r"(/category/|/categories/|/collections?/|/browse|/search|/catalogue/category/|"
    r"/cat/|/plp|/shop/?$|/shop/page/|product-category|route=product/category|[?&](_nkw|q|k|search)=)",
    re.I,
)
MONEY = re.compile(r"(?:US\$|[$€£])\s?\d|(?:USD|EUR|GBP|CAD|AUD)\s?\d", re.I)
BLOCK_TEXT = (
    "cf-browser-verification",
    "just a moment",
    "attention required",
    "cf-challenge",
    "verify you are human",
    "captcha",
    "access denied",
    "request blocked",
    "bot detection",
    "akamai",
    "pardon our interruption",
    "enable javascript and cookies",
)

# Public listing or product pages. One host is fetched slowly and dropped if it blocks.
SEEDS = [
    "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
    "https://books.toscrape.com/catalogue/soumission_998/index.html",
    "https://books.toscrape.com/catalogue/sharp-objects_997/index.html",
    "https://scrapeme.live/shop/Bulbasaur/",
    "https://scrapeme.live/shop/Ivysaur/",
    "https://scrapeme.live/shop/Charmander/",
    "https://scrapeme.live/shop/Squirtle/",
    "https://demo.opencart.com/index.php?route=product/product&language=en-gb&product_id=43",
    "https://demo.opencart.com/index.php?route=product/product&language=en-gb&product_id=40",
    "https://demo.opencart.com/index.php?route=product/product&language=en-gb&product_id=42",
    "https://demo.opencart.com/index.php?route=product/product&language=en-gb&product_id=30",
    "https://demo.opencart.com/index.php?route=product/product&language=de-de&product_id=43",
    "https://demo.mage-os.org/joust-duffle-bag.html",
    "https://demo.mage-os.org/push-it-messenger-bag.html",
    "https://demo.mage-os.org/overnight-duffle.html",
    "https://demo.mage-os.org/fusion-backpack.html",
    "https://demo.nopcommerce.com/build-your-own-computer",
    "https://demo.nopcommerce.com/apple-macbook-pro-13-inch",
    "https://demo.nopcommerce.com/nikon-d5500-dslr",
    "https://demo.nopcommerce.com/leica-t-mirrorless-digital-camera",
    "https://demo.solidus.io/products/solidus-t-shirt",
    "https://demo.solidus.io/products/ruby-on-rails-tote",
    "https://demo.solidus.io/products/ruby-on-rails-bag",
    "https://demo.solidus.io/products/ruby-on-rails-baseball-jersey",
    "https://books.toscrape.com/",
    "https://books.toscrape.com/catalogue/category/books/travel_2/index.html",
    "https://books.toscrape.com/catalogue/category/books/mystery_3/index.html",
    "https://books.toscrape.com/catalogue/category/books/poetry_23/index.html",
    "https://scrapeme.live/shop/",
    "https://scrapeme.live/shop/page/2/",
    "https://webscraper.io/test-sites/e-commerce/allinone",
    "https://webscraper.io/test-sites/e-commerce/allinone/computers/laptops",
    "https://webscraper.io/test-sites/e-commerce/allinone/phones/touch",
    "https://webscraper.io/test-sites/e-commerce/allinone/computers/tablets",
    "https://demo.opencart.com/",
    "https://demo.opencart.com/index.php?route=product/category&language=en-gb&path=20",
    "https://demo.opencart.com/index.php?route=product/category&language=en-gb&path=24",
    "https://demo.opencart.com/index.php?route=product/category&language=en-gb&path=25",
    "https://demo.opencart.com/index.php?route=product/category&language=en-gb&path=33",
    "https://demo.opencart.com/index.php?route=product/category&language=en-gb&path=34",
    "https://demo.opencart.com/index.php?route=product/category&language=de-de&path=20",
    "https://demo.mage-os.org/",
    "https://demo.mage-os.org/gear/bags.html",
    "https://demo.mage-os.org/women/tops-women.html",
    "https://magento2.demo.ubertheme.com/",
    "https://demo.mageplaza.com/default/",
    "https://demo.prestashop.com/",
    "https://demo.sylius.com/",
    "https://demo.sylius.com/en_US/",
    "https://demo.solidus.io/",
    "https://demo.spreecommerce.org/",
    "https://demostore.x-cart.com/",
    "https://demo.nopcommerce.com/",
    "https://demo.cs-cart.com/",
    "https://themes.woocommerce.com/storefront/",
    "https://themes.woocommerce.com/homestore/",
    "https://themes.woocommerce.com/boutique/",
    "https://cornerstone-light-demo.mybigcommerce.com/",
    "https://store.steampowered.com/search/?filter=topsellers",
    "https://www.gog.com/en/games",
    "https://itch.io/games/new-and-popular",
    "https://bandcamp.com/discover",
    "https://www.apple.com/shop/buy-mac/macbook-air",
    "https://www.ikea.com/us/en/cat/bookcases-bookcases-10382/",
    "https://www.bhphotovideo.com/c/browse/Digital-Cameras/ci/3342/N/4288586282",
    "https://www.adorama.com/l/Computers/Laptops",
    "https://www.crutchfield.com/g_12300/Home-Audio.html",
    "https://www.rei.com/c/backpacks",
    "https://www.newegg.com/p/pl?d=laptop",
    "https://www.bestbuy.com/site/laptop-computers/all-laptops/pcmcat138500050001.c?id=pcmcat138500050001",
    "https://www.target.com/c/laptops-computers-office-electronics/-/N-5xtfc",
    "https://www.walmart.com/browse/electronics/laptops/3944_3951_1089430",
    "https://www.homedepot.com/b/Tools-Power-Tools/N-5yc1vZc1xy",
    "https://www.lowes.com/pl/power-tools/drills/4294857973",
    "https://www.harborfreight.com/power-tools.html",
    "https://www.acehardware.com/departments/lighting-and-electrical",
    "https://www.wayfair.com/furniture/sb0/sofas-c413892.html",
    "https://www.nike.com/w/mens-shoes-nik1zy7ok",
    "https://www.adidas.com/us/men-shoes",
    "https://www.patagonia.com/shop/mens/jackets-vests",
    "https://www.allbirds.com/collections/mens",
    "https://www.glossier.com/",
    "https://www.sephora.com/shop/moisturizer-skincare",
    "https://www.ulta.com/shop/makeup/face",
    "https://www.chewy.com/b/dog-food-294",
    "https://www.staples.com/Laptops/cat_CL167285",
    "https://www.officedepot.com/b/laptops/N-1461932",
    "https://www.amazon.com/s?k=hardcover+book",
    "https://www.ebay.com/sch/i.html?_nkw=hardcover+book",
    "https://www.etsy.com/search?q=ceramic+mug",
    "https://www.monoprice.com/category/computers-networking",
    "https://www.sweetwater.com/c417--Studio_Monitors",
    "https://www.thomannmusic.com/studio_monitors.html",
    "https://www.thomann.de/de/studiomonitore.html",
    "https://www.adafruit.com/category/105",
    "https://www.sparkfun.com/categories/142",
    "https://www.digikey.com/en/products/filter/embedded/microcontrollers/685",
    "https://www.mouser.com/c/semiconductors/integrated-circuits-ics/",
    "https://bookshop.org/categories/m/fiction",
    "https://www.powells.com/browse-bestsellers",
    "https://www.barnesandnoble.com/b/books/_/N-1fZ29Z8q8",
    "https://www.waterstones.com/books/bestsellers",
    "https://www.bol.com/nl/nl/l/boeken/8299/",
    "https://www.coolblue.nl/laptops",
    "https://www.mediamarkt.de/de/category/notebooks-462737.html",
    "https://www.otto.de/technik/laptop/",
    "https://www.takealot.com/computers/laptops-26396",
    "https://www.yuppiechef.com/",
    "https://www.jbhifi.com.au/collections/laptops",
    "https://www.officeworks.com.au/shop/officeworks/c/technology/laptops",
    "https://www.argos.co.uk/browse/technology/laptops-and-pcs/laptops/c:29949/",
    "https://www.currys.co.uk/computing/laptops/laptops",
    "https://www.johnlewis.com/browse/electricals/laptops-macbooks/view-all-laptops-macbooks/_/N-a8f",
    "https://www.boots.com/health-pharmacy/medicines-treatments",
    "https://www.marksandspencer.com/l/women/dresses",
    "https://www.screwfix.com/c/tools/drills/cat830704",
    "https://www.toolstation.com/power-tools/drills/c1",
    "https://www.canadiantire.ca/en/sports-recreation.html",
    "https://www.bestbuy.ca/en-ca/collection/laptops/349028",
    "https://www.microcenter.com/category/4294967294/all-laptops",
    "https://www.parts-express.com/cat/speaker-components/14",
    "https://www.raspberrypi.com/products/",
    "https://www.abebooks.com/",
    "https://www.guitarcenter.com/Guitars.gc",
    "https://www.musiciansfriend.com/guitars",
    "https://www.cdiscount.com/informatique/ordinateurs-pc-portables/v-10709-10709.html",
    "https://www.fnac.com/n122993/Informatique/Ordinateurs-portables",
    "https://www.zalando.de/damenbekleidung-kleider/",
    "https://www.uniqlo.com/us/en/women/dresses",
    "https://www2.hm.com/en_us/women/products/dresses.html",
    "https://www.zara.com/us/en/woman-dresses-l1066.html",
    "https://www.gap.com/browse/category.do?cid=1035712",
    "https://www.everlane.com/collections/womens-all",
    "https://www.llbean.com/llb/shop/504944",
    "https://www.columbia.com/c/mens-jackets/",
    "https://www.thenorthface.com/en-us/mens/mens-jackets-and-vests-225",
    "https://www.carhartt.com/c/mens-jackets",
    "https://www.backcountry.com/camp-hike-backpacks",
    "https://www.dickssportinggoods.com/f/baseball-bats",
    "https://www.opticsplanet.com/binoculars.html",
    "https://www.sportsmans.com/hunting-gear",
    "https://www.grainger.com/category/power-tools",
    "https://www.uline.com/Cls/Office-Supplies",
    "https://www.webstaurantstore.com/food-storage-containers.html",
    "https://www.costco.com/laptops.html",
    "https://www.samsclub.com/b/laptops/1079",
    "https://www.menards.com/main/tools/power-tools/c-15090.htm",
    "https://www.tractorsupply.com/tsc/catalog/tools-garage",
    "https://www.kmart.com.au/category/technology/laptops/",
    "https://www.tesco.com/shop/en-GB/groceries",
    "https://www.sainsburys.co.uk/shop/gb/groceries",
    "https://www.asda.com/groceries",
    "https://www.homehardware.ca/en/tools",
    "https://www.thesource.ca/en-ca/computers-and-tablets/laptops",
    "https://www.walmart.ca/en/browse/electronics/laptops/10003_20037",
    "https://www.makro.co.za/",
    "https://www.game.co.za/",
    "https://www.incredible.co.za/",
    "https://superbalist.com/",
    "https://www.faithful-to-nature.co.za/",
    "https://www.blackwells.co.uk/bookshop/category/fiction",
    "https://wordery.com/fiction-books",
    "https://www.alternate.de/Notebooks",
    "https://www.conrad.de/de/o/notebooks-0701010.html",
    "https://www.diy.com/departments/tools-equipment/power-tools/drills/DIY579801.cat",
    "https://www.wickes.co.uk/Products/Tools/Power-Tools/Drills/c/1000167",
    "https://www.outdoorvoices.com/collections/womens",
    "https://www.duluthtrading.com/mens/mens-outerwear/",
    "https://www.mscdirect.com/browse/Power-Tools",
    "https://www.jcrew.com/plp/womens/categories/clothing/dresses",
    "https://oldnavy.gap.com/browse/category.do?cid=5760",
    "https://www.bananarepublic.gap.com/browse/category.do?cid=5415",
    "https://www.potterybarn.com/shop/furniture/sofas/",
    "https://www.westelm.com/shop/furniture/sofas/",
    "https://www.crateandbarrel.com/furniture/sofas/",
    "https://www.cb2.com/sofas/",
    "https://www.williams-sonoma.com/shop/electrics/coffee-makers/",
    "https://books.toscrape.com/catalogue/category/books/fiction_10/index.html",
    "https://books.toscrape.com/catalogue/category/books/poetry_23/index.html",
    "https://books.toscrape.com/catalogue/category/books/science_22/index.html",
    "https://webscraper.io/test-sites/e-commerce/allinone/phones/touch",
    "https://scrapeme.live/shop/page/3/",
    "https://demo.mage-os.org/men/tops-men.html",
    "https://demo.solidus.io/t/categories/clothing",
    "https://demo.spreecommerce.org/us/en/products",
    "https://www.adafruit.com/category/168",
    "https://www.glossier.com/collections/skincare",
    "https://www.outdoorvoices.com/collections/mens",
    "https://www.wickes.co.uk/Products/Tools/Power-Tools/Drills/c/1000167",
    "https://www.ikea.com/us/en/cat/chairs-fu002/",
    "https://www.marksandspencer.com/l/men/shirts",
    "https://www.nike.com/w/womens-shoes-5e1x6zy7ok",
]


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self.hrefs.append(value)


def _host(url: str) -> str:
    return urlparse(url).netloc.lower()


def _robots_allows(body: str, url: str) -> bool:
    """Allow when robots.txt does not disallow the path for Tiger or for everyone."""
    if not body.strip():
        return True
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []

    def flush() -> None:
        nonlocal agents, rules
        if agents or rules:
            groups.append((agents, rules))
        agents = []
        rules = []

    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if rules:
                flush()
            agents.append(value.lower())
        elif key in {"allow", "disallow"}:
            rules.append((key, value))
    flush()
    chosen: list[tuple[str, str]] | None = None
    for names, group_rules in groups:
        if any(name in {"tervorytiger", "tervorytiger/0.1"} or "tervorytiger" in name for name in names):
            chosen = group_rules
            break
    if chosen is None:
        for names, group_rules in groups:
            if "*" in names:
                chosen = group_rules
                break
    if not chosen:
        return True
    path = urlparse(url).path or "/"
    allow_len = -1
    disallow_len = -1
    for kind, prefix in chosen:
        if prefix and path.startswith(prefix):
            if kind == "allow" and len(prefix) > allow_len:
                allow_len = len(prefix)
            elif kind == "disallow" and len(prefix) > disallow_len:
                disallow_len = len(prefix)
    if disallow_len < 0:
        return True
    return allow_len >= disallow_len


def _usable(url: str) -> bool:
    if not url.startswith(("http://", "https://")):
        return False
    return not any(char in url for char in " \t\r\n{}<>\"'")


def _fetch(url: str) -> tuple[int, str, str]:
    request = Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en",
        },
    )
    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=TIMEOUT_S, context=context) as response:
            status = getattr(response, "status", 200)
            final = response.geturl()
            raw = response.read(MAX_BYTES + 1)
            ctype = response.headers.get("Content-Type", "")
    except HTTPError as exc:
        raw = exc.read(20_000) if exc.fp else b""
        text = raw.decode("utf-8", errors="replace")
        return exc.code, text, url
    except (URLError, TimeoutError, OSError, InvalidURL, ValueError) as exc:
        reason = getattr(exc, "reason", exc)
        return 0, f"url-error:{reason}", url
    if "html" not in ctype.lower() and "text/" not in ctype.lower() and "xml" not in ctype.lower():
        return status, f"not-html:{ctype[:80]}", final
    if len(raw) > MAX_BYTES:
        raw = raw[:MAX_BYTES]
    return status, raw.decode("utf-8", errors="replace"), final


def _blocked(status: int, body: str) -> str | None:
    """A block stops the host. A missing page does not."""
    if status in {401, 403, 429, 503}:
        return f"http {status}"
    if status == 0:
        return "network error"
    if status != 200:
        return None
    head = body[:4000].lower()
    for marker in BLOCK_TEXT:
        if marker in head:
            return marker
    return None


def _clean(html: str) -> str:
    """Drop scripts, frames, and review blocks. Keep JSON-LD and the price markup."""
    html = re.sub(
        r"<script\b(?![^>]*application/ld\+json)[^>]*>.*?</script>",
        "",
        html,
        flags=re.I | re.S,
    )
    html = re.sub(r"<iframe\b[^>]*>.*?</iframe>", "", html, flags=re.I | re.S)
    html = re.sub(r"<iframe\b[^>]*/>", "", html, flags=re.I)
    html = re.sub(
        r"<(div|section|ul|ol)\b[^>]*(review|comment|testimonial)[^>]*>.*?</\1>",
        "",
        html,
        flags=re.I | re.S,
    )
    return html


def _is_product(url: str, html: str) -> bool:
    """True for one product page. Related products on the same page do not make it a listing."""
    if any(part in url.lower() for part in SKIP_PARTS):
        return False
    if LISTING_URL.search(url):
        return False
    sample = html[:250_000]
    lowered = sample.lower()
    priced = bool(MONEY.search(sample)) or any(
        token in lowered
        for token in ("product:price:amount", 'itemprop="price"', "woocommerce-price-amount", "&pound;")
    )
    if not priced:
        return False
    parsed = urlparse(url)
    target = parsed.path + (("?" + parsed.query) if parsed.query else "")
    if PRODUCT_URL.search(target):
        return True
    if "/shop/" in parsed.path and not parsed.path.rstrip("/").endswith("/shop"):
        return True
    if "product:price:amount" in lowered or "og:type\" content=\"product" in lowered:
        return True
    if "class=\"product_page\"" in lowered or "body class=\"product" in lowered or "postid-" in lowered:
        return True
    marks = len(re.findall(r'"@type"\s*:\s*"product"', lowered))
    marks += len(re.findall(r"itemtype=['\"][^'\"]*product['\"]", lowered))
    return marks == 1


def _links(page_url: str, html: str) -> list[str]:
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:
        return []
    host = _host(page_url)
    found: list[str] = []
    seen: set[str] = set()
    for href in parser.hrefs:
        if href.startswith(("mailto:", "javascript:", "#", "tel:")):
            continue
        absolute = urljoin(page_url, href)
        if not _usable(absolute):
            continue
        if _host(absolute) != host:
            continue
        if any(part in absolute.lower() for part in SKIP_PARTS):
            continue
        if not PRODUCT_URL.search(absolute) and "route=product/product" not in absolute:
            continue
        absolute = absolute.split("#")[0]
        if absolute in seen:
            continue
        seen.add(absolute)
        found.append(absolute)
        if len(found) >= 12:
            break
    return found


def _append(row: dict) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _resume() -> tuple[int, dict[str, int], set[str], set[str], set[str]]:
    """Skip URLs already fetched so a restart does not repeat them."""
    saved = 0
    per_host: dict[str, int] = {}
    blocked: set[str] = set()
    seen: set[str] = set()
    robots_hosts: set[str] = set()
    if not MANIFEST.exists():
        return saved, per_host, blocked, seen, robots_hosts
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        kind = row.get("kind")
        host = row.get("host") or ""
        if row.get("url"):
            seen.add(row["url"])
        if row.get("final"):
            seen.add(row["final"])
        if kind == "saved":
            saved = max(saved, int(str(row["id"]).split("-")[1]))
            per_host[host] = per_host.get(host, 0) + 1
        elif kind == "blocked" and host:
            blocked.add(host)
        elif kind == "robots" and host:
            robots_hosts.add(host)
    return saved, per_host, blocked, seen, robots_hosts


def main() -> None:
    HTML_DIR.mkdir(parents=True, exist_ok=True)
    saved, per_host, blocked_hosts, seen_urls, robots_done = _resume()
    robots: dict[str, str] = {host: "" for host in robots_done}
    last_host = ""
    last_at = 0.0
    queue: deque[tuple[str, str]] = deque((url, "seed") for url in SEEDS)

    while queue and saved < MAX_SAVED:
        url, kind = queue.popleft()
        host = _host(url)
        if not host or url in seen_urls or host in blocked_hosts or not _usable(url):
            continue
        if "/blocked" in urlparse(url).path:
            blocked_hosts.add(host)
            _append({"kind": "blocked", "url": url, "host": host, "status": 200, "why": "blocked path"})
            print(f"blocked {host}: blocked path", flush=True)
            continue
        if per_host.get(host, 0) >= MAX_PER_HOST and kind != "robots":
            continue
        seen_urls.add(url)
        wait = SAME_HOST_DELAY_S if host == last_host else DELAY_S
        elapsed = time.monotonic() - last_at
        if last_at and elapsed < wait:
            time.sleep(wait - elapsed)
        if host not in robots:
            robots_url = f"{urlparse(url).scheme}://{host}/robots.txt"
            status, body, _final = _fetch(robots_url)
            robots[host] = body if status == 200 else ""
            _append({"kind": "robots", "url": robots_url, "status": status, "host": host})
            last_host = host
            last_at = time.monotonic()
            time.sleep(DELAY_S)
        if not _robots_allows(robots.get(host, ""), url):
            _append({"kind": "robots-skip", "url": url, "host": host, "why": "disallowed"})
            continue
        try:
            status, body, final = _fetch(url)
        except Exception as exc:  # one bad URL must not stop the sweep
            _append({"kind": "miss", "url": url, "host": host, "status": 0, "why": type(exc).__name__})
            print(f"miss {type(exc).__name__} {url[:90]}", flush=True)
            last_host = host
            last_at = time.monotonic()
            continue
        last_host = host
        last_at = time.monotonic()
        why = _blocked(status, body)
        if why:
            blocked_hosts.add(host)
            _append({"kind": "blocked", "url": url, "final": final, "host": host, "status": status, "why": why})
            print(f"blocked {host}: {why}", flush=True)
            continue
        if status != 200 or body.startswith("not-html") or body.startswith("url-error"):
            _append({"kind": "miss", "url": url, "final": final, "host": host, "status": status})
            print(f"miss {status} {url[:90]}", flush=True)
            continue
        if _is_product(final, body):
            saved += 1
            per_host[host] = per_host.get(host, 0) + 1
            page_id = f"live-{saved:03d}"
            cleaned = _clean(body)
            (HTML_DIR / f"{page_id}.html").write_text(cleaned, encoding="utf-8")
            _append({
                "kind": "saved",
                "id": page_id,
                "url": url,
                "final": final,
                "host": host,
                "status": status,
                "bytes": len(cleaned),
            })
            print(f"saved {page_id} {host} {final[:100]}", flush=True)
            continue
        _append({"kind": "listing", "url": final, "host": host, "status": status})
        print(f"listing {host} {final[:100]}", flush=True)
        # Product pages from this listing go next, ahead of other seeds.
        for link in reversed(_links(final, body)):
            if link not in seen_urls:
                queue.appendleft((link, "product"))

    print(f"done saved={saved} blocked_hosts={len(blocked_hosts)}", flush=True)


if __name__ == "__main__":
    main()
