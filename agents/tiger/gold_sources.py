"""Public saved-page candidates. No crawling, client observations, or approvals.

Expected items contain price fields only: unknown metadata is not labelled.
The consumer must compare these labelled fields, not invent missing metadata.
"""
from __future__ import annotations

import base64
import json
import re
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zipfile import ZipFile
from urllib.parse import urlsplit

CORPUS = Path(__file__).with_name("gold") / "public-pages.zip"
MAX_CANDIDATES = 200


def amount(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", text):
        return None
    try:
        return format(Decimal(text).quantize(Decimal(".01")), "f")
    except InvalidOperation:
        return None


class Evidence(HTMLParser):
    """Conservative agreement: a single visible amount and structured amount."""
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.stack: list[tuple[str, bool]] = []
        self.visible: list[str] = []
        self.structured: set[str] = set()
        self.script: list[str] | None = None
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list) -> None:
        attr = dict(attrs)
        hide = tag in {"script", "style", "template", "noscript"} or "hidden" in attr or attr.get("aria-hidden") == "true" or bool(re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", attr.get("style", ""), re.I))
        if tag == "script" and attr.get("type", "").lower() == "application/ld+json":
            self.script = []
        if tag not in {"meta", "link", "img", "br", "input", "hr", "source", "wbr"}:
            self.stack.append((tag, hide))
            self.hidden += int(hide)
        if "price" in attr.get("itemprop", "").split():
            price = amount(attr.get("content", ""))
            if price:
                self.structured.add(price)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.script is not None:
            self.blocks.append("".join(self.script))
            self.script = None
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                self.hidden -= sum(int(hidden) for _, hidden in self.stack[i:])
                del self.stack[i:]
                break

    def handle_data(self, data: str) -> None:
        if self.script is not None:
            self.script.append(data)
        if not self.hidden:
            self.visible.append(data)


def agreement(html: str) -> str | None:
    evidence = Evidence()
    evidence.feed(html)
    def walk(node: Any, product: bool = False) -> None:
        if isinstance(node, list):
            for value in node:
                walk(value, product)
        elif isinstance(node, dict):
            types = node.get("@type", [])
            types = types if isinstance(types, list) else [types]
            product = product or any(str(t).rsplit("/", 1)[-1] == "Product" for t in types)
            if product and "price" in node:
                price = amount(node["price"])
                if price:
                    evidence.structured.add(price)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    walk(value, product)
    for block in evidence.blocks:
        try:
            walk(json.loads(block))
        except (ValueError, RecursionError):
            continue
    visible = {amount(m) for m in re.findall(r"(?:US\$|\$|£|€|USD|GBP|EUR)\s*(\d[\d,]*(?:\.\d{1,2})?)(?!\d)", " ".join(evidence.visible))}
    visible.discard(None)
    if len(visible) == 1 and visible == evidence.structured:
        return next(iter(visible))
    return None


def snapshot_candidates(rows: list[dict], *, region: str) -> list[dict]:
    """Additional public snapshots from an authorised collector, never client watches.

    Each snapshot must attest access permission and region. This module never
    fetches pages or bypasses robots, terms, authentication or challenges.
    """
    result = []
    if region not in {"us-east", "za"}:
        return result
    for row in rows:
        if not all(row.get(key) is True for key in ("public", "robots_allowed", "terms_allowed")):
            continue
        if row.get("challenge") is not False or row.get("authenticated") is not False or row.get("region") != region:
            continue
        url = str(row.get("url") or "")
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            continue
        html = row.get("html")
        if not isinstance(html, str) or len(html) > 2_000_000:
            continue
        price = agreement(html)
        if price is None:
            continue
        common = {"expected": {"items": [{"price": price}]},
                  "label_source": "auto:visible-structured-agreement", "region": region, "public": True}
        result.append({**common, "skill_id": "tiger.price_extract", "input": {"html": html, "url": url}})
        png = row.get("png_base64")
        if isinstance(png, str) and len(png) <= 2_000_000:
            try:
                valid = base64.b64decode(png, validate=True).startswith(b"\x89PNG\r\n\x1a\n")
            except ValueError:
                valid = False
            if valid:
                result.append({**common, "skill_id": "tiger.price_ocr", "input": {"png_base64": png, "url": url}})
    return result


def candidates(limit: int = 200, *, region: str = "us-east", corpus: Path = CORPUS, snapshots: Path | None = None) -> list[dict]:
    if region not in {"us-east", "za"} or limit <= 0:
        return []
    result: list[dict] = []
    if snapshots is not None and snapshots.is_file() and snapshots.stat().st_size <= 20_000_000:
        try:
            rows = json.loads(snapshots.read_text())
            if isinstance(rows, list) and all(isinstance(row, dict) for row in rows):
                result = snapshot_candidates(rows, region=region)[:min(limit, MAX_CANDIDATES)]
        except (ValueError, OSError):
            pass
    if len(result) >= min(limit, MAX_CANDIDATES) or region != "us-east":
        return result
    with ZipFile(corpus) as archive:
        rows = json.loads(archive.read("manifest.json"))
        for row in rows:
            if row["split"] != "build" or row["conflict"] or row["unreadable"]:
                continue
            price = amount(row["expected_price"])
            if price is None:
                continue
            html = archive.read(row["id"] + ".html").decode()
            source = "auto:price-gold-109:" + row["id"]
            if agreement(html) == price:
                source += ":visible-structured-agreement"
            expected = {"items": [{"price": price}]}
            if row.get("currency"):
                expected["items"][0]["currency"] = row["currency"]
            for skill, payload in (
                ("tiger.price_extract", {"html": html, "url": row["url"]}),
                ("tiger.price_ocr", {"png_base64": base64.b64encode(archive.read(row["id"] + ".png")).decode(), "url": row["url"]}),
            ):
                result.append({"skill_id": skill, "input": payload, "expected": expected,
                               "label_source": source, "region": region, "public": True})
                if len(result) >= min(limit, MAX_CANDIDATES):
                    return result
    return result
