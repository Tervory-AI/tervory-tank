"""Read the 'files you may change' section of a brief. Anything else is out of bounds."""

from __future__ import annotations

import re

_TICK = re.compile(r"`([^`\n]+)`")
_HEADING = re.compile(r"^#{1,3} ", re.M)


def files_section(markdown: str) -> str:
    lowered = markdown.lower()
    mark = lowered.find("files you may change")
    if mark < 0:
        return ""
    rest = markdown[mark:]
    heading = _HEADING.search(rest, 1)
    if heading:
        rest = rest[: heading.start()]
    return rest


def allowed_rules(markdown: str) -> list[str]:
    section = files_section(markdown)
    rules: list[str] = []
    for match in _TICK.finditer(section):
        raw = match.group(1).strip()
        if raw.startswith("./"):
            raw = raw[2:]
        if not raw or raw.startswith("http") or any(char.isspace() for char in raw):
            continue
        if ".." in raw.split("/"):
            continue
        if not re.fullmatch(r"[A-Za-z0-9._/-]+", raw):
            continue
        if raw not in rules:
            rules.append(raw)
    if re.search(r"\bnew tests\b", section, re.I) and "tests/" not in rules:
        rules.append("tests/")
    return rules


def path_allowed(path: str, rules: list[str]) -> bool:
    name = path.strip().replace("\\", "/")
    if not name or name.startswith("/") or name.startswith("~"):
        return False
    parts = name.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return False
    for rule in rules:
        if rule.endswith("/"):
            if name.startswith(rule):
                return True
        elif name == rule:
            return True
    return False


def outside_rules(paths: list[str], rules: list[str]) -> list[str]:
    return [path for path in paths if not path_allowed(path, rules)]
