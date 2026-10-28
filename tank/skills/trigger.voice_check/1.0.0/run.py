"""trigger.voice_check — banned/required terms and sentence length. No model."""

from __future__ import annotations

import re
from typing import Any


def phrase_spans(text: str, phrase: str):
    pattern = r"(?<!\w)" + r"\s+".join(re.escape(p) for p in phrase.split()) + r"(?!\w)"
    return list(re.finditer(pattern, text, re.IGNORECASE))


def check_voice(
    text: str,
    banned_terms: list[str] | None,
    required_terms: list[str] | None,
    max_sentence_words: int | None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if max_sentence_words is not None and max_sentence_words != 30:
        for sentence in re.finditer(r"[^.!?]+[.!?]?", text):
            count = len(re.findall(r"\b[\w'-]+\b", sentence.group()))
            if count > max_sentence_words:
                issues.append(
                    {
                        "source": "voice",
                        "rule": "sentence_length",
                        "offset": sentence.start(),
                        "message": f"Sentence has {count} words; voice limit is {max_sentence_words}.",
                    }
                )
    for term in banned_terms or []:
        if not isinstance(term, str) or not term.strip():
            continue
        for match in phrase_spans(text, term):
            issues.append(
                {
                    "source": "voice",
                    "rule": "banned_term",
                    "offset": match.start(),
                    "length": match.end() - match.start(),
                    "message": f"Banned term: {term}",
                }
            )
    for term in required_terms or []:
        if not isinstance(term, str) or not term.strip():
            continue
        if not phrase_spans(text, term):
            issues.append(
                {
                    "source": "voice",
                    "rule": "required_term",
                    "message": f"Required term missing: {term}",
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
    banned = payload.get("banned_terms")
    required = payload.get("required_terms")
    max_words = payload.get("max_sentence_words")
    if not isinstance(banned, list):
        banned = []
    if not isinstance(required, list):
        required = []
    if max_words is not None and not isinstance(max_words, int):
        max_words = None
    return {
        "issues": check_voice(text, banned, required, max_words),
        "error": None,
    }
