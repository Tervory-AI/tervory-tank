"""zenas.scope — rules first, cheap model only when no rule hits."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


def _rules() -> Any:
    path = Path(__file__).with_name("rules.py")
    spec = importlib.util.spec_from_file_location("zenas_scope_rules", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("zenas.scope rules are missing")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_PROMPT = """Classify this request for Zenas. Reply with JSON only:
{"area":"<id>","jurisdiction":"us|za|both"}
Allowed area ids: __ALLOWED__
If it is not one of those, use "none". Do not give legal advice. Do not help with criminal law.

Request:
__TEXT__
"""


async def run(payload: dict, ctx: Any) -> dict:
    rules = _rules()
    text = str((payload or {}).get("text") or "")
    given = (payload or {}).get("jurisdiction")
    jurisdiction = given if given in ("us", "za", "both") else None
    if rules.ruled(text) is not None or not text.strip():
        return rules.public_result(rules.classify(text, jurisdiction))
    allowed = ", ".join(rules.allowed_ids())
    prompt = _PROMPT.replace("__ALLOWED__", allowed).replace("__TEXT__", text)
    raw = await ctx.model(
        [{"role": "user", "content": prompt}],
        task_type="zenas.scope",
        max_tokens=200,
    )
    return rules.public_result(rules.classify_with_hint(text, str(raw or ""), jurisdiction))
