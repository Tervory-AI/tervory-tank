"""trigger.languagetool — map LanguageTool v2/check JSON. No model."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_FIXTURE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def _load_fixture(name: str) -> dict[str, Any] | None:
    if not _FIXTURE.fullmatch(name):
        return None
    path = Path(__file__).resolve().parent / "evals" / "fixtures" / name
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def map_response(payload: dict[str, Any] | None, *, available: bool) -> dict[str, Any]:
    """Map LanguageTool JSON, or mark the checker unavailable."""
    if not available or payload is None:
        return {
            "issues": [],
            "complete": False,
            "checker_errors": ["LanguageTool is unavailable; its checks have not completed."],
            "error": None,
        }
    try:
        matches = payload["matches"]
        if not isinstance(matches, list):
            raise TypeError("Invalid matches")
        issues = []
        for match in matches:
            issues.append(
                {
                    "source": "languagetool",
                    "rule": match["rule"]["id"],
                    "message": match["message"],
                    "offset": match["offset"],
                    "length": match["length"],
                }
            )
        warnings = payload.get("warnings", {})
        if not isinstance(warnings, dict):
            raise TypeError("Invalid warnings")
        complete = not warnings.get("incompleteResults", False)
        return {
            "issues": issues,
            "complete": complete,
            "checker_errors": [] if complete else ["LanguageTool returned incomplete results."],
            "error": None,
        }
    except (ValueError, KeyError, TypeError):
        return {
            "issues": [],
            "complete": False,
            "checker_errors": ["LanguageTool is unavailable; its checks have not completed."],
            "error": None,
        }


async def run(payload: dict, ctx) -> dict:
    del ctx
    if not isinstance(payload, dict):
        payload = {}
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return {
            "issues": [],
            "complete": False,
            "checker_errors": [],
            "error": "empty text",
        }
    if "lt_response" in payload:
        raw = payload.get("lt_response")
        if raw is None:
            return map_response(None, available=False)
        if not isinstance(raw, dict):
            return map_response({}, available=True)
        return map_response(raw, available=True)
    fixture = payload.get("lt_fixture")
    if isinstance(fixture, str):
        data = _load_fixture(fixture)
        if data is None:
            return map_response(None, available=False)
        return map_response(data, available=True)
    # Production room supplies lt_response after its private LanguageTool call.
    return map_response(None, available=False)
