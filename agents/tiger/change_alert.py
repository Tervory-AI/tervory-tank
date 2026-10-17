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


CANT_READ = "can't read"

_AVAIL_JSON = re.compile(r'"availability"\s*:\s*"([^"]*)"', re.I)
_AVAIL_FIELD = re.compile(
    r"""<(?:meta|link)\b[^>]*?(?:itemprop|property|name)\s*=\s*['"]"""
    r"""(?:availability|product:availability|og:availability)['"][^>]*?"""
    r"""(?:content|href)\s*=\s*['"]([^'"]*)['"]""",
    re.I,
)
_AVAIL_FIELD_REV = re.compile(
    r"""<(?:meta|link)\b[^>]*?(?:content|href)\s*=\s*['"]([^'"]*)['"][^>]*?"""
    r"""(?:itemprop|property|name)\s*=\s*['"]"""
    r"""(?:availability|product:availability|og:availability)['"]""",
    re.I,
)


# A negator within a few words before a stock phrase flips it.
# This is a class of words, not a list of sentences. A contraction ending in
# n't counts, as do not/no/never/none/nothing/without, the word zero, and 0.
# "not out of stock" is one negation of an out-of-stock phrase, so it is in stock.
_APOS = "['\u2019]"
_NEGATOR = (
    r"(?:"
    r"\b[a-z]+n" + _APOS + r"t\b"
    r"|\bwithout\b|\bnothing\b|\bnever\b|\bnone\b|\bnot\b|\bno\b"
    r"|\bzero\b|\b0\b"
    r")"
)
_GAP = r"(?:\s+[a-z0-9]+){0,4}"
_NEG_TAIL = re.compile(_NEGATOR + _GAP + r"\s*$", re.I)
# Keeping, holding, or staying in stock is about demand or past difficulty, not
# a statement that the product is unavailable now. The signal is the verb in
# that role, not a list of difficulty words. keep/hold/stay in any form counts,
# and so does any other verb in the same spot: an infinitive ("to carry"), a
# participle ("maintaining"), or the word a negator actually scopes to
# ("couldn't remain"). Auxiliaries such as be/have/come are not that verb, so
# negation still flips the stock phrase. A later plain "out of stock" or
# "in stock" is a new sentence and still counts.
_RETAIN = {
    "keep", "keeps", "keeping", "kept",
    "hold", "holds", "holding", "held",
    "stay", "stays", "staying", "stayed",
}
# Closed class. Negation is allowed to pass through these. They are not the
# demand verb.
_AUX = {
    "be", "been", "being", "am", "is", "are", "was", "were",
    "have", "has", "had", "having",
    "do", "does", "did", "doing",
    "come", "comes", "coming", "came",
    "get", "gets", "got", "getting",
    "go", "goes", "going", "gone", "went",
}
_FUNCTION = _AUX | {
    "i", "we", "you", "he", "she", "it", "they", "me", "us", "him", "her", "them",
    "my", "our", "your", "his", "its", "their",
    "a", "an", "the", "this", "that", "these", "those",
    "any", "some", "all", "each", "every",
    "of", "to", "for", "from", "in", "on", "at", "by", "with", "as", "and", "or", "but",
    "still", "now", "just", "back", "again", "here", "there", "even", "yet", "once", "then",
    "also", "only", "already", "longer", "left", "unit", "units", "more", "most", "very",
    "too", "so", "one", "up",
}
_NOT_A_PARTICIPLE = _AUX | {"nothing", "something", "anything", "everything"}
_WORD = re.compile(r"[A-Za-z0-9]+(?:['\u2019]t)?")
_WORD_NEG = re.compile(r"(?:" + _NEGATOR + r")\Z", re.I)
# "no stock" and "without stock" name stock without "in" or "out of".
_NO_STOCK = re.compile(_NEGATOR + _GAP + r"\s+stock\b", re.I)
_PHRASE = (
    ("OutOfStock", re.compile(
        r"(?:schema\.org[/\\]+outofstock|\bout[\s\-]*of[\s\-]*stock\b|\bsold[\s\-]*out\b"
        r"|\boutofstock\b|\bunavailable\b)",
        re.I,
    )),
    ("LimitedAvailability", re.compile(
        r"(?:schema\.org[/\\]+limitedavailability|\blimited[\s\-]*availability\b|\blimitedavailability\b)",
        re.I,
    )),
    ("PreOrder", re.compile(
        r"(?:schema\.org[/\\]+preorder|\bpre[\s\-]*order\b|\bpreorder\b)",
        re.I,
    )),
    ("Discontinued", re.compile(
        r"(?:schema\.org[/\\]+discontinued|\bdiscontinued\b)",
        re.I,
    )),
    ("InStock", re.compile(
        r"(?:schema\.org[/\\]+instock|\bin[\s\-]*stock\b|\binstock\b)",
        re.I,
    )),
)


def _negated(prefix: str) -> bool:
    return _NEG_TAIL.search(prefix) is not None


def _clause_words(prefix: str) -> list[str]:
    """Words before a stock phrase, in the same sentence."""
    clause = re.split(r"[.!;?]+", prefix)[-1]
    return [word.lower().replace("\u2019", "'") for word in _WORD.findall(clause)]


def _negator_word(word: str) -> bool:
    return _WORD_NEG.search(word) is not None


def _participle(word: str) -> bool:
    """A verb form such as maintaining or carried. Not 'nothing' or 'been'."""
    if word in _NOT_A_PARTICIPLE:
        return False
    if len(word) >= 6 and word.endswith("ing"):
        return True
    return len(word) >= 5 and word.endswith("ed")


def _demand_clause(prefix: str) -> bool:
    """True when this sentence is about keeping, holding, or staying in stock."""
    words = _clause_words(prefix)
    for index, word in enumerate(words):
        if word.isdigit() or (len(word) > 3 and word.endswith("ly")):
            continue
        if word in _RETAIN or _participle(word):
            return True
        nxt = words[index + 1] if index + 1 < len(words) else ""
        if not nxt or nxt.isdigit() or (len(nxt) > 3 and nxt.endswith("ly")):
            continue
        if nxt in _AUX or nxt in _FUNCTION or _negator_word(nxt):
            continue
        # "to remain" is an infinitive. "couldn't hold" scopes the negator to hold.
        if word == "to" or _negator_word(word):
            return True
    return False


def _flip_stock(token: str) -> str | None:
    """Negation swaps in stock and out of stock. Other phrases then cannot be told."""
    if token == "InStock":
        return "OutOfStock"
    if token == "OutOfStock":
        return "InStock"
    return None


def phrases_in(value: Any) -> list[str]:
    """Known stock phrases in this wording. A negator before the phrase wins."""
    if value is None:
        return []
    text = str(value).strip()
    if not text or text == CANT_READ:
        return []
    found: list[str] = []
    demand = False
    for token, pattern in _PHRASE:
        for match in pattern.finditer(text):
            if _demand_clause(text[:match.start()]):
                demand = True
                continue
            if _negated(text[:match.start()]):
                flipped = _flip_stock(token)
                if flipped and flipped not in found:
                    found.append(flipped)
                continue
            if token not in found:
                found.append(token)
    if found:
        return found
    if demand:
        return []
    if _NO_STOCK.search(text):
        return ["OutOfStock"]
    tail = text.rstrip("/").split("/")[-1]
    key = re.sub(r"[\s_\-]+", "", tail).lower()
    token = _STOCK.get(key)
    return [token] if token else []


def stock_token(value: Any) -> str | None:
    """A known stock phrase, including the same phrase with extra words."""
    found = phrases_in(value)
    if len(found) == 1:
        return found[0]
    return None


def stock_reading(value: Any) -> str | None:
    """A known stock phrase, nothing when stock was not stated, or "can't read".

    Clear out-of-stock wording is out of stock. "Can't read" is only when
    the stock cannot be told. A known in-stock phrase with extra words stays
    in stock.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text == CANT_READ:
        return CANT_READ
    return stock_token(text) or CANT_READ


# Stock lines only. A wrapper div whose class says "instock" is not a stock phrase.
_STOCK_LINE = re.compile(
    r"""<(?:p|span|a|li|dd|td|h2|h3)\b[^>]*"""
    r"""(?:itemprop\s*=\s*['"]availability['"]|class\s*=\s*['"][^'"]*"""
    r"""(?:availability|\bstock\b|in-stock|out-of-stock)[^'"]*['"])[^>]*>"""
    r"""(.*?)</(?:p|span|a|li|dd|td|h2|h3)>""",
    re.I | re.S,
)
_TAG = re.compile(r"<[^>]+>")


def stock_statements(html: str) -> list[str]:
    """Stock wording on the page, before it is renamed to a token."""
    if not html:
        return []
    found: list[str] = []
    for pattern in (_AVAIL_JSON, _AVAIL_FIELD, _AVAIL_FIELD_REV):
        for match in pattern.finditer(html):
            text = match.group(1).strip()
            if text:
                found.append(text)
    for match in _STOCK_LINE.finditer(html):
        text = " ".join(_TAG.sub(" ", match.group(1)).split())
        if text and len(text) <= 80:
            found.append(text)
    return found


def record_stock(statements: list[str]) -> str | None:
    """Record the stock the page states. Out of stock wins over in stock.

    "Not in stock" is out of stock, not in stock. One unclear line does not
    veto a known phrase. "Can't read" is only when no clear stock phrase is
    there, or two different phrases still disagree and neither is out of stock.
    """
    if not statements:
        return None
    tokens: list[str] = []
    other = False
    for text in statements:
        found = phrases_in(text)
        if not found:
            if str(text).strip():
                other = True
            continue
        for token in found:
            if token not in tokens:
                tokens.append(token)
    if "OutOfStock" in tokens:
        return "OutOfStock"
    if len(tokens) == 1:
        return tokens[0]
    if len(tokens) > 1:
        return CANT_READ
    if other:
        return CANT_READ
    return None


def stated_availability(html: str) -> str | None:
    """Availability words written in a stock field, before they are renamed."""
    found = stock_statements(html)
    return found[0] if found else None


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
    """Older helper. A watch check does not call this."""
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
