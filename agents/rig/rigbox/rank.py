"""Rank a shopper query against one catalogue.

The words before a relation (for, fits, pairs with, goes on, compatible with,
to go with, and the same kind of phrase) are the part the shopper wants. A
word counts as a whole token, or as the same token with a small spelling
change when it is at least four characters. A piece of a longer word does not
count. A model code that is one edit from a real code, or a short prefix of
one, can surface that row only as a closest match. It is never an exact hit.
A digit in a model name, including a single digit joined to or following
a model word, has to sit on that same row. An ordinary word is not a model
code. A misspelling of a catalogue word is that word. An unknown name next
to a known brand is a closest match.
A word that is already a category outranks a shared name, so that part comes
ahead of the product it attaches to. Typos use character trigrams, including
the text with spaces and dashes removed.
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
_WORD = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
# Ordinary words. A short English word is not a model code.
_COMMON = frozenset(
    {
        "buy",
        "gun",
        "oh",
        "set",
        "up",
        "rig",
        "iwb",
        "typ",
        "new",
        "old",
        "big",
        "low",
        "hot",
        "own",
        "out",
        "our",
        "too",
        "now",
        "how",
        "who",
        "why",
        "all",
        "any",
        "not",
        "but",
        "you",
        "was",
        "has",
        "had",
        "did",
        "get",
        "got",
        "let",
        "may",
        "say",
        "see",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "hundred",
        "thousand",
        "zero",
        "its",
        "off",
        "yes",
        "yet",
        "nor",
        "via",
        "ask",
        "try",
        "put",
        "full",
        "size",
        "carry",
        "race",
        "model",
        "ultra",
        "best",
        "good",
        "free",
        "next",
        "last",
        "more",
        "most",
        "some",
        "such",
        "than",
        "then",
        "them",
        "they",
        "also",
        "very",
        "just",
        "only",
        "into",
        "over",
        "here",
        "back",
        "down",
        "same",
        "both",
        "each",
        "few",
        "many",
        "much",
        "like",
        "want",
        "make",
        "made",
        "looking",
        "called",
        "please",
        "show",
        "find",
        "need",
        "about",
        "your",
        "have",
        "will",
        "from",
        "shoe",
        "post",
        "round",
        "hold",
        "front",
        "rear",
        "left",
        "side",
        "high",
        "long",
        "wide",
        "open",
        "real",
        "true",
        "able",
        "away",
        "come",
        "came",
        "keep",
        "know",
        "take",
        "tell",
        "well",
        "work",
        "year",
        "name",
        "item",
        "list",
        "listed",
        "catalogue",
        "catalog",
        "price",
        "cost",
        "brand",
        "appendix",
        "aluminum",
        "module",
        "weapon",
        "circle",
        "adjustable",
        "competition",
        "precision",
        "performance",
        "replacement",
        "reading",
        "table",
        "fabric",
        "desk",
        "level",
        "retention",
        "fiber",
        "duty",
        "flat",
        "faced",
        "shaped",
        "holding",
    }
)
# Relation words are not model codes. "go" would otherwise look like a short code.
_SKIP = frozenset(
    {
        "go",
        "goes",
        "going",
        "pair",
        "pairs",
        "paired",
        "fit",
        "fits",
        "fitting",
        "compatible",
        "suit",
        "suits",
        "mount",
        "replace",
        "use",
        "using",
    }
)
# A trigram-only match below this is a different product, not a typo.
_TYPO = 0.45
# A single token this close to a catalogue token is the same word misspelled.
# Below this, "sig" is not "sight". A different model code is handled apart from this.
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
    body: dict[str, Any] = {"results": results, "ids": [item["id"] for item in results]}
    if not results:
        return body
    missing = _unmatched_models(query, rows)
    if missing:
        body["exact_match"] = False
        body["message"] = _no_exact(missing)
    else:
        body["exact_match"] = True
    return body


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
    if any(_code_close(needle, item) for item in have):
        return True
    # Three-letter pieces stay exact, so a fragment cannot pose as a longer word.
    if len(needle) < 4:
        return False
    return any(len(item) >= 4 and _similarity(needle, item) >= _FUZZY for item in have)


def _code_close(left: str, right: str) -> bool:
    """One edit between two model codes. A different code is not the same model."""
    if left == right or len(left) < 4 or len(right) < 4:
        return False
    if not any(char.isdigit() for char in left) or not any(char.isdigit() for char in right):
        return False
    return _one_edit(left, right)


def _one_edit(left: str, right: str) -> bool:
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) > len(right):
        left, right = right, left
    i = 0
    j = 0
    edits = 0
    while i < len(left) and j < len(right):
        if left[i] == right[j]:
            i += 1
            j += 1
            continue
        edits += 1
        if edits > 1:
            return False
        if len(left) == len(right):
            i += 1
        j += 1
    edits += (len(right) - j) + (len(left) - i)
    return edits == 1


def _catalogue_tokens(rows: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        found.update(_tokens(_text(row)))
    return found


def _brand_tokens(rows: list[dict[str, Any]]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        found.update(_tokens(str(row.get("brand") or "")))
    return found


def _covered(token: str, have: set[str]) -> bool:
    return any(_same_word(token, item) for item in have)


def _ordinary(token: str) -> bool:
    return token in _FILLER or token in _SKIP or token in _COMMON


def _row_has_all(parts: list[str], rows: list[dict[str, Any]]) -> bool:
    if not parts:
        return True
    for row in rows:
        have = set(_tokens(_text(row)))
        if all(_covered(part, have) for part in parts):
            return True
    return False


def _model_parts(parts: list[str]) -> list[str]:
    kept: list[str] = []
    for part in parts:
        if any(char.isdigit() for char in part):
            kept.append(part)
        elif _ordinary(part) or len(part) < 2:
            continue
        else:
            kept.append(part)
    return kept


def _fuzzy_word(token: str, vocab: set[str]) -> bool:
    """A misspelling of a catalogue word, not a different model code."""
    if len(token) < 3 or not token.isalpha():
        return False
    return any(item.isalpha() and _similarity(token, item) >= _FUZZY for item in vocab)


def _unmatched_models(query: str, rows: list[dict[str, Any]]) -> list[str]:
    """Model codes that no single row carries exactly.

    A digit, including a single digit joined to a model word, has to be on
    that same row. An ordinary short word is not a model. A typo of a real
    catalogue word is that word. An unknown name next to a known brand is not
    an exact hit.
    """
    vocab = _catalogue_tokens(rows)
    brands = _brand_tokens(rows)
    parsed = [(word, _tokens(word)) for word in _WORD.findall(query)]
    query_tokens = [part for _, parts in parsed for part in parts]
    has_brand = any(_covered(token, brands) for token in query_tokens)
    missing: list[str] = []
    seen: set[str] = set()

    def add(phrase: str) -> None:
        if phrase and phrase not in seen:
            seen.add(phrase)
            missing.append(phrase)

    for index, (word, parts) in enumerate(parsed):
        if not any(any(char.isdigit() for char in part) for part in parts):
            continue
        # "Type 3": the digit is its own word and belongs to the word before it.
        if len(parts) == 1 and parts[0].isdigit() and index > 0:
            continue
        needed = _model_parts(parts)
        if needed and not _row_has_all(needed, rows):
            add(word)
    for index, (word, parts) in enumerate(parsed):
        if index == 0 or not (len(parts) == 1 and parts[0].isdigit()):
            continue
        prev_word, prev_parts = parsed[index - 1]
        needed = _model_parts(prev_parts) + parts
        if not _row_has_all(needed, rows):
            add(f"{prev_word} {word}")
    if has_brand:
        for word, parts in parsed:
            for part in parts:
                if any(char.isdigit() for char in part) or _ordinary(part):
                    continue
                if len(part) < 2 or _covered(part, vocab) or _fuzzy_word(part, vocab):
                    continue
                add(word)
    return missing


def _no_exact(words: list[str]) -> str:
    if len(words) == 1:
        return f"No exact match for {words[0]}."
    return "No exact match for " + ", ".join(words) + "."


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
