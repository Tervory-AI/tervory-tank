"""ThreatPayload: the only shape that may cross from LLM triage into an execute path.

Ghost may read dirty logs and advisory text. Nothing from that side may raise a
shield, restart a room, or open a worker brief until it validates as ThreatPayload.
On any failure we burn: raise ThreatBurned with a fixed message and never echo the
rejected input (it may carry secrets or injection).

Founder tap is still required for Shields Up. This schema is the air-gap spike
(Phase 4), not auto-execute.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from .inventory import WATCHED_SITES
from .shields import KINDS, ShieldRequest

SCHEMA_VERSION = "ghost.threat.v1"
BURN_DETAIL = "Threat payload burned. No action was taken."
# Site keys and hosts Ghost is allowed to name.
ALLOWED_SITES = frozenset({*WATCHED_SITES.keys(), *WATCHED_SITES.values()})
CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$")
# Patterns that mean "this is not a structured threat fact" — burn without parsing further.
INJECTION_MARKERS = (
    "ignore previous",
    "ignore all previous",
    "disregard previous",
    "system prompt",
    "you are now",
    "</",
    "<script",
    "```",
    "rm -rf",
    "/bin/sh",
    "powershell",
    "curl |",
    "wget |",
    "base64 -d",
    "os.system",
    "subprocess",
    "__import__",
)


class ThreatBurned(ValueError):
    """Raised when triage output is refused. Message is always BURN_DETAIL."""

    def __init__(self) -> None:
        super().__init__(BURN_DETAIL)


class ThreatAction(str, Enum):
    propose_shield = "propose_shield"
    open_match = "open_match"
    write_brief = "write_brief"


class ThreatSeverity(str, Enum):
    known_exploited = "known_exploited"
    critical = "critical"
    high = "high"
    medium = "medium"
    low = "low"
    unknown = "unknown"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ThreatPayload(Strict):
    """Bounded facts only. No free-form commands, patches, or shell."""

    schema_version: Literal["ghost.threat.v1"] = SCHEMA_VERSION
    action: ThreatAction
    site: str = Field(min_length=1, max_length=80)
    kind: Literal["waf_managed", "rate_limit", "block_multipart_post", "challenge_bots"] | None = None
    path: str | None = Field(default=None, max_length=120, pattern=r"^/[A-Za-z0-9._~/-]*$")
    match_id: str | None = Field(default=None, max_length=200)
    cve_ids: list[str] = Field(default_factory=list, max_length=20)
    severity: ThreatSeverity = ThreatSeverity.unknown
    reason: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("site")
    @classmethod
    def site_must_be_ours(cls, value: str) -> str:
        site = value.strip().lower()
        if site not in {s.lower() for s in ALLOWED_SITES}:
            raise ValueError("site not allowlisted")
        return site

    @field_validator("cve_ids")
    @classmethod
    def cves_must_be_shaped(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for item in values:
            if not isinstance(item, str) or not CVE_RE.fullmatch(item):
                raise ValueError("invalid cve")
            cleaned.append(item)
        return cleaned

    @field_validator("reason")
    @classmethod
    def reason_must_be_plain(cls, value: str) -> str:
        text = value.strip()
        if any(ord(ch) < 32 for ch in text):
            raise ValueError("control characters")
        lowered = text.lower()
        if any(marker in lowered for marker in INJECTION_MARKERS):
            raise ValueError("injection marker")
        return text


def _preflight_raw(raw: bytes | str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        if len(raw) > 8_000:
            raise ThreatBurned()
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ThreatBurned() from exc
    elif isinstance(raw, str):
        if len(raw) > 8_000:
            raise ThreatBurned()
        text = raw
    else:
        raise ThreatBurned()
    lowered = text.lower()
    if any(marker in lowered for marker in INJECTION_MARKERS):
        raise ThreatBurned()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise ThreatBurned() from exc
    if not isinstance(data, dict):
        raise ThreatBurned()
    return data


def accept_threat_payload(raw: bytes | str | dict[str, Any]) -> ThreatPayload:
    """Parse and validate triage output. Burns on any failure — never echoes input."""
    try:
        data = _preflight_raw(raw)
        payload = ThreatPayload.model_validate(data)
    except ThreatBurned:
        raise
    except (ValidationError, ValueError, TypeError) as exc:
        raise ThreatBurned() from None
    if payload.action == ThreatAction.propose_shield:
        if payload.kind is None or payload.kind not in KINDS:
            raise ThreatBurned()
    return payload


def threat_to_shield_request(payload: ThreatPayload) -> ShieldRequest:
    """Map a validated ThreatPayload onto the existing shield propose shape.

    Caller must still go through Shields.propose → founder Shield tap. This does
    not apply anything.
    """
    if payload.action != ThreatAction.propose_shield or payload.kind is None:
        raise ThreatBurned()
    # Prefer host form when the triage named an app key.
    site = WATCHED_SITES.get(payload.site, payload.site)
    return ShieldRequest(
        site=site,
        kind=payload.kind,
        path=payload.path,
        match_id=payload.match_id,
        reason=payload.reason or f"triage:{payload.severity.value}",
    )
