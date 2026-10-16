"""Rank a shopper query against one catalogue.

Words before "for" are the part the shopper wants. A word that is already a
category outranks a shared name, so that part comes ahead of the product it
attaches to. Typos use character trigrams, including the text with spaces and
dashes removed.
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
    }
)
_FOR = re.compile(r"\s+for\s+", re.IGNORECASE)
_COMPACT = re.compile(r"[^a-z0-9]+")
# A trigram-only match below this is a different product, not a typo.
_TYPO = 0.45
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
    parts = _FOR.split(query, maxsplit=1)
    if len(parts) == 2 and parts[0].strip() and parts[1].strip():
        return parts[0].strip(), parts[1].strip()
    return query.strip(), ""


def _score(sought: str, host: str, row: dict[str, Any]) -> float:
    base = _match(sought, row)
    if host:
        if base <= 0:
            return 0.0
        return base * 5 + _match(host, row)
    return base


def _match(text: str, row: dict[str, Any]) -> float:
    needles = [token for token in _tokens(text) if token not in _FILLER and len(token) >= 2]
    if not needles:
        return 0.0
    hay = _text(row)
    hits = sum(1 for token in needles if token in hay)
    token_score = hits / len(needles)
    sim = _sim(text, row)
    if token_score <= 0 and sim < _TYPO:
        return 0.0
    category = str(row.get("category") or "").lower()
    bonus = _CATEGORY if any(len(token) >= 4 and token in category for token in needles) else 0.0
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
