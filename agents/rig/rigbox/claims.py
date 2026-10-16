"""Keep a shopper answer only when the catalogue itself says it.

A question is in the catalogue when every subject word is already written on a
product or a fit. A model answer is kept only when every remaining word and
every number sits on a row it cites. One real id cannot carry an invented
name, price, or claim.
"""

from __future__ import annotations

import re
from typing import Any

from rigbox.ground import _object

_UNKNOWN = "I don't know"
_TOKEN = re.compile(r"[a-z0-9]+")
_NUMBER = re.compile(r"\d+")
# Question words and sentence glue. None of these is a product fact.
_GLUE = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "this",
        "that",
        "what",
        "which",
        "when",
        "where",
        "will",
        "does",
        "have",
        "from",
        "your",
        "about",
        "into",
        "them",
        "they",
        "also",
        "please",
        "would",
        "could",
        "should",
        "there",
        "their",
        "only",
        "just",
        "how",
        "much",
        "many",
        "can",
        "you",
        "are",
        "was",
        "were",
        "has",
        "had",
        "did",
        "not",
        "but",
        "who",
        "why",
        "tell",
        "any",
        "some",
        "over",
        "under",
        "than",
        "then",
        "these",
        "those",
        "come",
        "comes",
        "take",
        "takes",
        "very",
        "buy",
        "get",
        "got",
        "make",
        "want",
        "need",
        "show",
        "find",
        "list",
        "listed",
        "looking",
        "catalogue",
        "catalog",
        "item",
        "items",
        "product",
        "products",
        "one",
        "all",
        "each",
        "our",
        "off",
        "too",
        "hello",
        "thanks",
        "thank",
        "is",
        "a",
        "an",
        "of",
        "in",
        "on",
        "to",
        "it",
        "be",
        "or",
        "if",
        "my",
        "me",
        "we",
        "do",
        "so",
        "at",
        "by",
        "up",
        "no",
        "yes",
        "am",
        "its",
        "out",
        "per",
        "via",
        "onto",
        "upon",
        "within",
        "without",
        "between",
        "across",
        "after",
        "before",
        "again",
        "here",
        "now",
        "today",
        "tomorrow",
        "price",
        "prices",
        "cost",
        "costs",
        "priced",
        "fit",
        "fits",
        "fitting",
    }
)


def answerable(question: str, products: list[dict[str, Any]], fits: list[dict[str, Any]]) -> bool:
    tokens = _subject(question)
    if not tokens:
        return False
    hay = _catalogue_blob(products, fits)
    return all(token in hay for token in tokens)


def grounded_answer(payload: dict[str, Any], model_text: str) -> dict[str, Any]:
    products = list(payload.get("products") or [])
    fits = list(payload.get("fits") or [])
    if not answerable(str(payload.get("question") or ""), products, fits):
        return {"answer": _UNKNOWN, "cites": []}
    parsed = _object(model_text)
    by_id: dict[str, dict[str, Any]] = {}
    for row in products:
        ident = str(row.get("id") or row.get("sku") or "")
        if ident:
            by_id[ident] = row
    cites: list[str] = []
    for item in parsed.get("cites") or []:
        ident = str(item)
        if ident in by_id and ident not in cites:
            cites.append(ident)
    answer = str(parsed.get("answer") or "").strip()
    if not cites or not answer or answer.lower() == _UNKNOWN.lower():
        return {"answer": _UNKNOWN, "cites": []}
    if not _supported(answer, [by_id[ident] for ident in cites]):
        return {"answer": _UNKNOWN, "cites": []}
    return {"answer": answer, "cites": cites}


def _subject(text: str) -> list[str]:
    return [token for token in _TOKEN.findall(text.lower()) if len(token) >= 3 and token not in _GLUE]


def _supported(answer: str, rows: list[dict[str, Any]]) -> bool:
    blob = _row_blob(rows)
    allowed = _numbers(rows)
    if any(number not in allowed for number in _NUMBER.findall(answer)):
        return False
    for token in _TOKEN.findall(answer.lower()):
        if token in _GLUE or len(token) < 2 or token.isdigit():
            continue
        if token not in blob:
            return False
    return True


def _catalogue_blob(products: list[dict[str, Any]], fits: list[dict[str, Any]]) -> str:
    parts = [_row_blob(products)]
    for fit in fits:
        parts.append(str(fit.get("part_sku") or ""))
        parts.append(str(fit.get("fits_sku") or ""))
        parts.append(str(fit.get("fits_family") or ""))
        parts.append(str(fit.get("note") or ""))
    return " ".join(parts).lower()


def _row_blob(rows: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for row in rows:
        for key in ("id", "sku", "name", "brand", "category"):
            parts.append(str(row.get(key) or ""))
        price = row.get("price")
        if isinstance(price, dict):
            parts.append(str(price.get("currency") or ""))
        else:
            parts.append(str(row.get("currency") or ""))
        attributes = row.get("attributes") or {}
        if isinstance(attributes, dict):
            for key, value in attributes.items():
                parts.append(str(key))
                parts.append(str(value))
    return " ".join(parts).lower()


def _numbers(rows: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        chunks = [str(row.get("id") or ""), str(row.get("sku") or ""), str(row.get("name") or "")]
        chunks.append(str(row.get("brand") or ""))
        chunks.append(str(row.get("category") or ""))
        attributes = row.get("attributes") or {}
        if isinstance(attributes, dict):
            for key, value in attributes.items():
                chunks.append(str(key))
                chunks.append(str(value))
        price = row.get("price")
        amount = price.get("amount") if isinstance(price, dict) else price
        if amount is not None:
            chunks.append(str(amount))
        for chunk in chunks:
            found.update(_NUMBER.findall(chunk))
            if "." in chunk:
                whole, frac = chunk.split(".", 1)
                if frac.strip("0") == "" and whole.isdigit():
                    found.add(whole)
    found.discard("")
    return found
