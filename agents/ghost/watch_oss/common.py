"""Shared Autumbra Watch intake helpers: anomaly gate + ThreatPayload burn."""
from __future__ import annotations

import os
import re
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..threat_payload import (
    ThreatAction,
    ThreatBurned,
    ThreatPayload,
    ThreatSeverity,
    accept_threat_payload,
)

DEFAULT_ANOMALY_THRESHOLD = 0.8
# Bounded keys only — never free-form log bodies.
_SITE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,79}$")
_SIGNAL_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


def enabled() -> bool:
    for name in ("WATCH_OSS_ENABLED", "GHOST_WATCH_OSS_ENABLED"):
        if os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}:
            return True
    return False


class AnomalyEvent(BaseModel):
    """Bounded Watch intake fact. No raw payload, headers, or shell."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(pattern=r"^(vector|fluent_bit|steampipe|opencti)$")
    site: str = Field(min_length=1, max_length=80)
    signal: str = Field(min_length=1, max_length=64)
    score: float = Field(ge=0.0, le=1.0)
    cve_ids: list[str] = Field(default_factory=list, max_length=20)
    reason: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("site")
    @classmethod
    def site_shaped(cls, value: str) -> str:
        site = value.strip().lower()
        if not _SITE_RE.fullmatch(site) and "." not in site:
            # allow hostnames like coolify.tervory.com
            if not re.fullmatch(r"^[a-z0-9][a-z0-9.-]{0,79}$", site):
                raise ValueError("bad site")
        return site

    @field_validator("signal")
    @classmethod
    def signal_shaped(cls, value: str) -> str:
        signal = value.strip().lower()
        if not _SIGNAL_RE.fullmatch(signal):
            raise ValueError("bad signal")
        return signal

    @field_validator("reason")
    @classmethod
    def reason_plain(cls, value: str) -> str:
        text = value.strip()
        if any(ord(ch) < 32 for ch in text):
            raise ValueError("control characters")
        return text


def anomaly_only(
    events: Iterable[AnomalyEvent | dict[str, Any]],
    *,
    threshold: float = DEFAULT_ANOMALY_THRESHOLD,
) -> list[AnomalyEvent]:
    """Keep only events at/above the anomaly threshold. Drops the rest silently."""
    kept: list[AnomalyEvent] = []
    for item in events:
        try:
            event = item if isinstance(item, AnomalyEvent) else AnomalyEvent.model_validate(item)
        except (ValueError, TypeError):
            continue
        if event.score >= threshold:
            kept.append(event)
    return kept


def handoff_threat(event: AnomalyEvent | dict[str, Any]) -> ThreatPayload:
    """Normalize an anomaly into ThreatPayload. Burns on any failure; never echoes."""
    try:
        if not isinstance(event, AnomalyEvent):
            event = AnomalyEvent.model_validate(event)
    except (ValueError, TypeError) as exc:
        raise ThreatBurned() from None

    if event.score < DEFAULT_ANOMALY_THRESHOLD:
        raise ThreatBurned()

    severity = ThreatSeverity.unknown
    if event.score >= 0.95:
        severity = ThreatSeverity.critical
    elif event.score >= 0.9:
        severity = ThreatSeverity.high
    elif event.score >= DEFAULT_ANOMALY_THRESHOLD:
        severity = ThreatSeverity.medium

    candidate = {
        "schema_version": "ghost.threat.v1",
        "action": ThreatAction.open_match.value,
        "site": event.site,
        "kind": None,
        "path": None,
        "match_id": f"watch-oss:{event.source}:{event.signal}"[:200],
        "cve_ids": list(event.cve_ids),
        "severity": severity.value,
        "reason": (event.reason or f"Autumbra Watch anomaly via {event.source}")[:300],
        "confidence": max(event.confidence, event.score),
    }
    return accept_threat_payload(candidate)
