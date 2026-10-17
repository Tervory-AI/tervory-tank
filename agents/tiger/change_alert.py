"""Replay a price history and say which steps are real changes.

Sub-cent rounding is the same price. A flat series does not alert. Text that
tries to give orders is ignored. A missing price is not a change.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any

_PROMPT = re.compile(
    r"(ignore (all |any )?(previous|above|prior)|disregard (the |all )?(instructions|above)"
    r"|you are now|system\s*:|new instructions|output the price|do not follow)",
    re.I,
)
_SKIP = {"blocked", "robots", "error", "none", "unread"}
_STOCK = {
    "instock": "InStock",
    "outofstock": "OutOfStock",
    "preorder": "PreOrder",
    "discontinued": "Discontinued",
    "limitedavailability": "LimitedAvailability",
    "soldout": "OutOfStock",
}


def stock_token(value: Any) -> str | None:
    """A known stock word, or nothing. Unknown wording is not a stock change."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    tail = text.rstrip("/").split("/")[-1]
    key = re.sub(r"[\s_\-]+", "", tail).lower()
    return _STOCK.get(key)


def normalize_price(value: Any) -> str | None:
    """A stated amount as cents. Rounding below half a cent collapses."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        text = str(value)
    elif isinstance(value, str):
        text = value.strip()
    else:
        return None
    if _PROMPT.search(text):
        return None
    text = text.replace("\xa0", "").replace(" ", "")
    text = re.sub(r"^[A-Za-z]{1,3}\.?", "", text)
    text = re.sub(r"[^\d,.\-]", "", text)
    if not text or text in {"-", ".", ",", "-."}:
        return None
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        if re.fullmatch(r"-?\d{1,3}(,\d{3})+", text):
            text = text.replace(",", "")
        elif re.fullmatch(r"-?\d+,\d{1,2}", text):
            text = text.replace(",", ".")
        else:
            return None
    try:
        number = Decimal(text)
    except InvalidOperation:
        return None
    if number < 0:
        return None
    return f"{number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)}"


def cents(value: Any) -> Decimal | None:
    text = normalize_price(value)
    if text is None:
        return None
    return Decimal(text)


def price_moved(before: Any, after: Any, threshold: Any) -> bool:
    """True when the cent price moved by more than the watch's fraction."""
    old = cents(before)
    new = cents(after)
    if old is None or new is None or old == new:
        return False
    if old == 0:
        return True
    try:
        limit = Decimal(str(threshold))
    except InvalidOperation:
        return False
    return abs(new - old) / abs(old) > limit


def replay(history: list[dict[str, Any]] | None, threshold: Any = "0") -> list[dict[str, Any]]:
    """One result per history step. Alerts compare with the last readable price."""
    if not history:
        return []
    previous: dict[str, Any] | None = None
    results: list[dict[str, Any]] = []
    for raw in history:
        row = _clean(raw if isinstance(raw, dict) else {})
        alerts: list[dict[str, str]] = []
        if previous is not None and row is not None:
            alerts = _alerts(previous, row, threshold)
        results.append({"alerts": alerts})
        if row is not None and row.get("price") is not None:
            previous = row
    return results


def _clean(point: dict[str, Any]) -> dict[str, Any] | None:
    method = str(point.get("method") or "")
    if method in _SKIP:
        return None
    price_raw = point.get("price")
    if isinstance(price_raw, str) and _PROMPT.search(price_raw):
        return None
    price = normalize_price(price_raw)
    if price is None:
        return None
    availability = point.get("availability")
    if isinstance(availability, str) and _PROMPT.search(availability):
        availability = None
    return {
        "price": price,
        "availability": stock_token(availability),
        "method": method or "read",
    }


def _alerts(previous: dict[str, Any], current: dict[str, Any], threshold: Any) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if price_moved(previous.get("price"), current.get("price"), threshold):
        found.append({
            "kind": "price",
            "before": str(previous.get("price")),
            "after": str(current.get("price")),
        })
    before_stock = previous.get("availability")
    after_stock = current.get("availability")
    if before_stock and after_stock and before_stock != after_stock:
        found.append({"kind": "stock", "before": str(before_stock), "after": str(after_stock)})
    return found
