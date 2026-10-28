"""trigger.readability — passive-voice candidates and fence balance. No model."""

from __future__ import annotations

import re
from typing import Any

_PASSIVE = re.compile(
    r"\b(?:am|is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?"
    r"(?:\w+ed|written|given|made|seen|known|taken|built|sent|shown|found|done)\b",
    re.IGNORECASE,
)


def check_readability(text: str) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for match in _PASSIVE.finditer(text):
        issues.append(
            {
                "source": "readability",
                "rule": "passive_voice",
                "offset": match.start(),
                "length": match.end() - match.start(),
                "message": "Possible passive voice; review the actor and verb.",
            }
        )
    fences = re.findall(r"^\s*(`{3,}|~{3,})", text, re.MULTILINE)
    if len(fences) % 2:
        issues.append(
            {
                "source": "practical-prose",
                "rule": "F3",
                "message": "Unclosed fenced code block.",
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
    return {"issues": check_readability(text), "error": None}
