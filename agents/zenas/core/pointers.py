"""Resolve model pointers against a stored public judgment."""

from __future__ import annotations

import re
from typing import Any

from agents.zenas.core.engine import fold_for_quote


class PointerError(ValueError):
    pass


def judgment_text(text: str) -> str:
    text = re.sub(r"(?is)<footnote\b[^>]*>.*?</footnote>", "", text)
    text = re.sub(r"(?is)<aside\b[^>]*>.*?</aside>", "", text)
    text = re.sub(r"(?m)^[ \t]*(?:Footnote\s+\d+[:.]?|\d+\s+See\b)[^\n]*(?:\n[ \t]+[^\n]+)*", "", text)
    return text


def resolve_pointer(pointer: Any, text: str) -> str:
    if not isinstance(pointer, dict):
        raise PointerError("pointer did not resolve")
    paragraphs = pointer.get("paragraphs")
    if paragraphs is not None:
        if not isinstance(paragraphs, list) or not 1 <= len(paragraphs) <= 8:
            raise PointerError("pointer did not resolve")
        matches = list(re.finditer(r"(?m)^[ \t]*(?:\[(\d+)\]|(\d+)\.)[ \t]+", text))
        found: dict[int, list[str]] = {}
        for index, match in enumerate(matches):
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            number = int(match.group(1) or match.group(2))
            found.setdefault(number, []).append(text[match.end():end].strip())
        if any(type(number) is not int or len(found.get(number, [])) != 1 for number in paragraphs):
            raise PointerError("pointer did not resolve")
        return " ... ".join(found[number][0] for number in paragraphs)
    first = pointer.get("first")
    last = pointer.get("last")
    if not isinstance(first, str) or not isinstance(last, str):
        raise PointerError("pointer did not resolve")
    first, last = fold_for_quote(first), fold_for_quote(last)
    source = fold_for_quote(text)
    if len(first.split()) != 8 or len(last.split()) != 8:
        raise PointerError("pointer did not resolve")
    starts = list(re.finditer(r"(?<!\w)" + re.escape(first) + r"(?!\w)", source))
    ends = list(re.finditer(r"(?<!\w)" + re.escape(last) + r"(?!\w)", source))
    if len(starts) != 1 or len(ends) != 1 or ends[0].end() < starts[0].end():
        raise PointerError("pointer did not resolve")
    return source[starts[0].start():ends[0].end()]


def resolve_answer(data: dict[str, Any], text: str) -> dict[str, Any]:
    if "facts_pointer" in data:
        data["facts"] = resolve_pointer(data["facts_pointer"], text)
    for field in ("elements", "element_findings", "citations"):
        for item in data.get(field) or []:
            if isinstance(item, dict) and "quote_pointer" in item:
                item["quote"] = resolve_pointer(item["quote_pointer"], text)
    return data
