"""Code-only evidence selection and refusal rules for Trigger B1.

No network, model, client defaults or visitor-facing fallback wording lives here.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

from semantic_cache import NUMBER

PASSAGE_THRESHOLD = 0.35
FAQ_THRESHOLD = 0.92
MAX_PASSAGES = 6
PRICE_OR_STOCK = re.compile(r"\b(price|prices|cost|costs|stock|available|availability|inventory)\b|how much|[$£€]", re.I)


@dataclass(frozen=True)
class Passage:
    id: UUID
    tenant_id: UUID
    source_id: UUID
    text: str
    url: str | None
    title: str
    kind: str
    score: float
    sku: str | None = None
    approved_answer: str | None = None

    def public_source(self) -> dict:
        return {"id": str(self.id), "title": self.title, "url": self.url,
                "document_id": str(self.source_id), "sku": self.sku}


def chunks(text: str, words: int = 160) -> list[str]:
    """Bound below the pinned encoder's 512-token limit; validation stays authoritative."""
    tokens = text.split()
    if not tokens:
        return []
    return [" ".join(tokens[start:start + words]) for start in range(0, len(tokens), words - 25)]


def eligible(tenant: UUID, candidates: list[Passage]) -> list[Passage]:
    # Recheck identity after both stores: a vector-filter bug must never leak a row.
    return [p for p in candidates if p.tenant_id == tenant and p.score >= PASSAGE_THRESHOLD][:MAX_PASSAGES]


def exact_origin(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        return bool(parsed.scheme == "https" and parsed.hostname and not parsed.path
                    and not parsed.username and not parsed.password and not parsed.query
                    and not parsed.fragment and "*" not in value and not any(c.isspace() for c in value)
                    and parsed.port != 0)
    except (ValueError, TypeError):
        return False


def grounded(output: Any, passages: list[Passage]) -> tuple[str, list[Passage]] | None:
    """Validate structured output in code; unknown citations or novel numbers refuse."""
    try:
        data = json.loads(output) if isinstance(output, str) else output
        if not isinstance(data, dict) or set(data) != {"answer", "passage_ids"}:
            return None
        answer, ids = data["answer"], data["passage_ids"]
        if not isinstance(answer, str) or not answer.strip() or len(answer) > 8000:
            return None
        if not isinstance(ids, list) or not ids or len(ids) > MAX_PASSAGES:
            return None
        by_id = {str(p.id): p for p in passages}
        cited = [by_id[value] for value in dict.fromkeys(ids)]
        supported = {v.casefold() for v in NUMBER.findall(" ".join(p.text for p in cited))}
        if any(v.casefold() not in supported for v in NUMBER.findall(answer)):
            return None
        dates = re.compile(r"\b(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|today|tomorrow|yesterday|January|February|March|April|May|June|July|August|September|October|November|December)\b", re.I)
        source_text = ' '.join(p.text for p in cited).casefold()
        if any(token.casefold() not in source_text for token in dates.findall(answer)):
            return None
        currencies = re.compile(r"[$£€]|\b(?:USD|GBP|EUR|ZAR)\b")
        if any(token not in ' '.join(p.text for p in cited) for token in currencies.findall(answer)):
            return None
        # The engine owns links. A model cannot introduce a destination or a raw citation URL.
        if re.search(r"https?://|\]\(", answer, re.I):
            return None
        return answer.strip(), cited
    except (ValueError, TypeError, KeyError):
        return None


def fuse(tenant: UUID, lexical: list[dict], vectors: list[dict]) -> list[dict]:
    """Reciprocal-rank fusion, using only authoritative tenant-scoped DB rows."""
    results: dict[str, dict] = {}
    for rows in (lexical, vectors):
        for rank, row in enumerate(rows):
            if str(row.get("tenant_id")) != str(tenant):
                continue
            key = str(row["id"])
            item = results.setdefault(key, {**row, "fusion": 0.0})
            item["fusion"] += 1 / (20 + rank)
            item["score"] = max(item.get("score", 0), row.get("score", 0))
    return sorted(results.values(), key=lambda row: (-row["fusion"], str(row["id"])))
