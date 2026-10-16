"""Rank a shopper query against one catalogue.

The words before a relation (for, fits, pairs with, goes on, compatible with,
to go with, and the same kind of phrase) are the part the shopper wants. A
word counts as a whole token, or as the same token with a small spelling
change when it is at least four characters. A piece of a longer word does not
count. A word that is already a category outranks a shared name, so that part
comes ahead of the product it attaches to. Typos use character trigrams,
including the text with spaces and dashes removed.
"""

from __future__ import annotations

import re
from typing import Any

from rigbox.logic import _active, _haystack, _limit, _similarity, _sku, _tokens, public_product

_FILLER = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "to",
        "and",
        "or",
        "for",
        "with",
        "on",
        "in",
        "by",
        "at",
        "from",
        "is",
        "it",
        "be",
        "as",
        "per",
        "which",
        "what",
        "need",
        "that",
        "this",
        "these",
        "made",
        "called",
        "show",
        "find",
        "please",
        "my",
        "your",
        "use",
        "me",
        "do",
        "does",
        "can",
        "are",
    }
)
# Longer phrases first so "pairs with" wins over a shorter overlap at the same spot.
_RELATIONS = (
    "compatible with",
    "pairs with",
    "to go with",
    "goes with",
    "goes on",
    "to use on",
    "to mount on",
    "to replace on",
    "that suits",
    "fits",
    "fit",
    "for",
)
_COMPACT = re.compile(r"[^a-z0-9]+")
# A trigram-only match below this is a different product, not a typo.
_TYPO = 0.45
# A single token this close to a catalogue token is the same word misspelled
# or a short model code. Below this, "sig" is not "sight".
_FUZZY = 0.6
_CATEGORY = 4.0


def search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("q") or "").strip()
    limit = _limit(payload.get("limit"))
    tenant = payload.get("tenant_id")
    rows = list(payload.get("products") or [])
    if tenant is not None and str(tenant) != "":
        rows = [row for row in rows if str(row.get("tenant_id") or tenant) == str(tenant)]
    rows = [row for row in rows if _active(row)]
    if not query:
        return {"results": [], "ids": []}
    sought, host = _intent(query)
    ranked: list[tuple[float, str, dict[str, Any]]] = []
    for row in rows:
        score = _score(sought, host, row)
        if score <= 0:
            continue
        ranked.append((score, _sku(row), row))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    chosen = [row for _, _, row in ranked[:limit]]
    results = [public_product(row) for row in chosen]
    return {"results": results, "ids": [item["id"] for item in results]}


def _intent(query: str) -> tuple[str, str]:
    lowered = query.lower()
    found: tuple[tuple[int, int], re.Match[str]] | None = None
    for phrase in _RELATIONS:
        match = re.search(rf"\b{re.escape(phrase)}\b", lowered)
        if match is None:
            continue
        rank = (match.start(), -len(phrase))
        if found is None or rank < found[0]:
            found = (rank, match)
    if found is None:
        return query.strip(), ""
    match = found[1]
    left = query[: match.start()].strip()
    right = query[match.end() :].strip()
    if not left or not right:
        return query.strip(), ""
    return left, right


def _score(sought: str, host: str, row: dict[str, Any]) -> float:
    base = _match(sought, row)
    if host:
        if base <= 0:
            return 0.0
        return base * 5 + _match(host, row)
    return base


def _same_word(left: str, right: str) -> bool:
    if left == right:
        return True
    if len(left) >= 4 and left + "s" == right:
        return True
    if len(right) >= 4 and right + "s" == left:
        return True
    return False


def _token_hit(needle: str, have: set[str]) -> bool:
    if any(_same_word(needle, item) for item in have):
        return True
    # Three-letter pieces stay exact, so a fragment cannot pose as a longer word.
    if len(needle) < 4:
        return False
    return any(len(item) >= 4 and _similarity(needle, item) >= _FUZZY for item in have)


def _match(text: str, row: dict[str, Any]) -> float:
    needles = [token for token in _tokens(text) if token not in _FILLER and len(token) >= 2]
    if not needles:
        return 0.0
    have = set(_tokens(_text(row)))
    hits = sum(1 for token in needles if _token_hit(token, have))
    token_score = hits / len(needles)
    sim = _sim(text, row)
    # A short fragment such as "sig" or "cat" is not a typo of a longer word.
    if token_score <= 0 and (sim < _TYPO or max(len(token) for token in needles) < 4):
        return 0.0
    category = set(_tokens(str(row.get("category") or "")))
    bonus = _CATEGORY if any(any(_same_word(token, item) for item in category) for token in needles) else 0.0
    return token_score + sim + bonus


def _text(row: dict[str, Any]) -> str:
    return f"{_haystack(row)} {row.get('family') or ''}".lower()


def _fields(row: dict[str, Any]) -> list[str]:
    fields = [
        str(row.get("name") or ""),
        str(row.get("brand") or ""),
        _sku(row),
        str(row.get("category") or ""),
        str(row.get("family") or ""),
    ]
    attributes = row.get("attributes") or {}
    if isinstance(attributes, dict):
        for key, value in attributes.items():
            fields.append(str(key))
            fields.append(str(value))
    return fields


def _sim(text: str, row: dict[str, Any]) -> float:
    folded = _COMPACT.sub("", text.lower())
    best = 0.0
    for field in _fields(row):
        best = max(best, _similarity(text, field))
        compact = _COMPACT.sub("", field.lower())
        if folded and compact:
            best = max(best, _similarity(folded, compact))
    return best
