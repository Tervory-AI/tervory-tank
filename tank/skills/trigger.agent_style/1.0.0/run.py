"""trigger.agent_style — vendored deterministic detectors. No network, no model."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "vendor"))
from agent_style.review import detectors_mech, detectors_struct  # noqa: E402
from agent_style.review.loader import parse_rules  # noqa: E402

RULES = parse_rules((ROOT / "vendor" / "agent_style" / "RULES.md").read_text(encoding="utf-8"))
MECHANICAL = {"RULE-05", "RULE-06", "RULE-12", "RULE-B", "RULE-D"}
STRUCTURAL = {"RULE-A", "RULE-C", "RULE-E"}
SKIPPED = [r.id for r in RULES if r.id not in MECHANICAL | STRUCTURAL]


def review(text: str, max_sentence_words: int | None = None) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    for rule in RULES:
        if rule.id == "RULE-12" and max_sentence_words is not None and max_sentence_words != 30:
            continue
        module = detectors_mech if rule.id in MECHANICAL else detectors_struct if rule.id in STRUCTURAL else None
        if module is None:
            continue
        result = module.run(rule, text, "input.md")
        issues.extend(
            {
                "source": "agent-style",
                "rule": v.rule,
                "line": v.line,
                "column": v.column,
                "message": v.detail,
            }
            for v in result.violations
        )
    return {"issues": issues, "skipped_rules": list(SKIPPED), "error": None}


async def run(payload: dict, ctx) -> dict:
    del ctx
    if not isinstance(payload, dict):
        payload = {}
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return {"issues": [], "skipped_rules": list(SKIPPED), "error": "empty text"}
    max_words = payload.get("max_sentence_words")
    if max_words is not None and not isinstance(max_words, int):
        max_words = None
    return review(text, max_words)
