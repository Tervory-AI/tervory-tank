"""Decide public record from the source, and mask client work before it is shared.

The material type is never inferred from the words of the document. A court
source id is public record. A tenant matter is client work. Anything else is
unknown and is not shared.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.zenas.core.pii_detect import mask_client_text

log = logging.getLogger("zenas.material")

# Pool source ids whose documents are filed cases, judgments, gazettes, or law reports.
# A source that is not in this set is unknown. Unknown material is not shared.
COURT_SOURCES = frozenset({"saflii", "courtlistener", "cap", "govza-gazette"})

UNKNOWN = "material type is unknown"
MASK_FAILED = "masking failed"


def material_type_for_pool(source_id: str | None) -> str | None:
    """Public record only when the pool source is a court source."""
    if (source_id or "").strip().lower() in COURT_SOURCES:
        return "public_record"
    return None


def log_withheld(reason: str) -> None:
    """Log a fixed reason. The document text is never written here."""
    log.warning("not shared: %s", reason)


def _walk(value: Any, parties: Any) -> Any:
    if isinstance(value, str):
        masked = mask_client_text(value, parties)
        if not masked["ok"]:
            raise ValueError(MASK_FAILED)
        return masked["text"]
    if isinstance(value, list):
        return [_walk(item, parties) for item in value]
    if isinstance(value, dict):
        return {key: _walk(item, parties) for key, item in value.items()}
    return value


def mask_share(
    *,
    parties: Any = None,
    body: str = "",
    narrative: str = "",
    features: dict[str, Any] | None = None,
    findings: list[dict[str, Any]] | None = None,
    lawyer_edits: str = "",
    outcome: str = "",
    memo: str = "",
) -> dict[str, Any]:
    """Mask the three things a shared client worked matter may keep."""
    try:
        return {
            "ok": True,
            "body": _walk(body, parties),
            "narrative": _walk(narrative, parties),
            "features": _walk(features or {}, parties),
            "findings": _walk(findings or [], parties),
            "lawyer_edits": _walk(lawyer_edits, parties),
            "outcome": _walk(outcome, parties),
            "memo": _walk(memo, parties),
        }
    except Exception:
        return {"ok": False, "reason": MASK_FAILED}
