"""trigger.proselint — proselint findings only. Pure code. No network, no model."""

from __future__ import annotations

from typing import Any

from proselint.checks import __register__
from proselint.registry import CheckRegistry
from proselint.tools import LintFile

_REGISTRY_READY = False


def _ensure_registry() -> None:
    global _REGISTRY_READY
    if _REGISTRY_READY:
        return
    registry = CheckRegistry()
    # register_many is additive; only load once per process so findings are not doubled
    # when the Trigger room (or another import) already registered the same checks.
    if not getattr(registry, "_tervory_proselint_loaded", False):
        registry.register_many(__register__)
        registry._tervory_proselint_loaded = True
    _REGISTRY_READY = True


def lint_text(text: str) -> list[dict[str, Any]]:
    _ensure_registry()
    issues: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for found in LintFile("input", text).lint():
        item = found.into_dict()
        row = {
            "source": "proselint",
            "rule": item["check_path"],
            "message": item["message"],
            "line": found.pos[0],
            "column": found.pos[1],
        }
        key = (row["rule"], row["line"], row["column"], row["message"])
        if key in seen:
            continue
        seen.add(key)
        issues.append(row)
    return issues


async def run(payload: dict, ctx) -> dict:
    del ctx
    if not isinstance(payload, dict):
        payload = {}
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return {"issues": [], "error": "empty text"}
    return {"issues": lint_text(text), "error": None}
