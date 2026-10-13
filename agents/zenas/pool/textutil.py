"""Citation keys, hashes, and version planning. No I/O."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from agents.zenas.pool.model import VersionHead

_TOKEN = re.compile(r"[^a-z0-9.()]+")


def citation_key(citation: str) -> str:
    """Fold a citation so '49 U.S.C. § 14706(a)' and '49 USC 14706(a)' match."""
    text = citation.lower().replace("§", " ")
    for src, dst in (
        ("fed. r. civ. p.", "frcp"),
        ("fed. r. evid.", "fre"),
        ("u.s.c.", "usc"),
        ("c.f.r.", "cfr"),
        ("del. c.", "delc"),
        ("f.3d", "f3d"),
        ("f.2d", "f2d"),
        ("f.4th", "f4th"),
        ("u.s.", "us"),
    ):
        text = text.replace(src, dst)
    text = text.replace("(", " ").replace(")", " ")
    text = _TOKEN.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    folded = re.sub(r"\s+", " ", text).strip()
    return hashlib.sha256(folded.encode("utf-8")).hexdigest()


def version_id_for(document_id: str, digest: str) -> str:
    return f"{document_id}:{digest[:16]}"


def document_id_for(source_id: str, citation: str) -> str:
    return f"{source_id}:{citation_key(citation)}"


@dataclass(frozen=True)
class VersionPlan:
    action: str  # skip | insert
    close_ids: tuple[str, ...]
    close_on: date | None


def plan_version(
    existing: list[VersionHead],
    *,
    content_hash: str,
    effective_from: date | None,
    on: date,
) -> VersionPlan:
    """Same hash is a no-op. A new hash closes older open versions.

    An open version is closed only when the new wording is known from a
    date on or after that version's start. A later re-run of the same
    text does not insert a second row.
    """
    if any(row.content_hash == content_hash for row in existing):
        return VersionPlan("skip", (), None)
    close_on = effective_from or on
    close_ids: list[str] = []
    for row in existing:
        if row.effective_to is not None:
            continue
        if row.effective_from is not None and close_on < row.effective_from:
            continue
        close_ids.append(row.version_id)
    return VersionPlan("insert", tuple(close_ids), close_on if close_ids else None)


def applies(effective_from: date | None, effective_to: date | None, as_at: date | None) -> bool:
    """`as_at` None means the open version. A dated query needs a known start.

    Unknown effective_from is not treated as 'in force forever'. That would
    present a current edition as the law on an earlier date.
    """
    if as_at is None:
        return effective_to is None
    if effective_from is None or as_at < effective_from:
        return False
    if effective_to is not None and as_at >= effective_to:
        return False
    return True


def flatten_text(sections: list) -> str:
    parts: list[str] = []

    def walk(nodes: list) -> None:
        for node in nodes:
            if node.heading:
                parts.append(node.heading)
            if node.text:
                parts.append(node.text)
            walk(node.children)

    walk(sections)
    return "\n".join(part.strip() for part in parts if part and part.strip())
