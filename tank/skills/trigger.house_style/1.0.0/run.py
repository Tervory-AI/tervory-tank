"""trigger.house_style — vendored stylebook Avoid candidates. No model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
BOOK_TERMS = json.loads((ROOT / "data" / "book_terms.json").read_text(encoding="utf-8"))
BOOKS = frozenset(
    p.name for p in (ROOT / "data" / "stylebooks").iterdir() if p.is_dir()
)


def phrase_spans(text: str, phrase: str):
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(p) for p in phrase.split()) + r"(?!\w)"
    return list(re.finditer(pattern, text, re.IGNORECASE))


def check_stylebook(text: str, stylebook: str | None) -> list[dict[str, Any]]:
    if not stylebook or stylebook not in BOOKS:
        return []
    issues: list[dict[str, Any]] = []
    guide_path = ROOT / "data" / "stylebooks" / stylebook / "SKILL.md"
    guide = guide_path.read_text(encoding="utf-8") if guide_path.is_file() else ""
    for term in BOOK_TERMS.get(stylebook, []):
        for match in phrase_spans(text, term):
            issues.append(
                {
                    "source": "stylebook",
                    "rule": "avoid_candidate",
                    "offset": match.start(),
                    "message": f"{stylebook}: review '{term}' against the guide's Avoid section.",
                }
            )
    if "descriptive link" in guide.lower():
        for match in re.finditer(r"\[(?:click here|here|read more)\]\([^)]*\)", text, re.IGNORECASE):
            issues.append(
                {
                    "source": "stylebook",
                    "rule": "link_text",
                    "offset": match.start(),
                    "message": "Use descriptive link text.",
                }
            )
    return issues


async def run(payload: dict, ctx) -> dict:
    del ctx
    if not isinstance(payload, dict):
        payload = {}
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return {"issues": [], "error": "empty text"}
    stylebook = payload.get("stylebook")
    if stylebook is not None and not isinstance(stylebook, str):
        stylebook = None
    return {"issues": check_stylebook(text, stylebook), "error": None}
