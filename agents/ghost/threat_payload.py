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
    undo_shield = "undo_shield"
    approve_shield = "approve_shield"


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
    kind: Literal["waf_managed", "rate_limit", "block_multipart_post", "challenge_bots", "block_ip", "revoke_sessions"] | None = None
    path: str | None = Field(default=None, max_length=120, pattern=r"^/[A-Za-z0-9._~/-]*$")
    address: str | None = Field(default=None, max_length=64, pattern=r"^[0-9A-Fa-f:.]*$")
    match_id: str | None = Field(default=None, max_length=200)
    cve_ids: list[str] = Field(default_factory=list, max_length=20)
    severity: ThreatSeverity = ThreatSeverity.unknown
    reason: str = Field(default="", max_length=300)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    # Undo / approve door fields (ThreatPayload-only; never raw HTTP bytes).
    rule_id: str | None = Field(default=None, max_length=64, pattern=r"^[0-9A-Fa-f]*$")
    prior_receipt_id: str | None = Field(default=None, max_length=80)
    tenant_id: str | None = Field(default=None, max_length=80)
    advisory_url: str | None = Field(default=None, max_length=500)
    queued_at: str | None = Field(default=None, max_length=40)

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
    except (ValidationError, ValueError, TypeError):
        raise ThreatBurned() from None
    if payload.action == ThreatAction.propose_shield:
        if payload.kind is None or payload.kind not in KINDS:
            raise ThreatBurned()
    if payload.action == ThreatAction.undo_shield:
        if not (payload.rule_id or payload.prior_receipt_id):
            raise ThreatBurned()
    if payload.action == ThreatAction.approve_shield:
        if not payload.prior_receipt_id:
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
        address=payload.address,
        match_id=payload.match_id,
        reason=payload.reason or f"triage:{payload.severity.value}",
    )


def match_to_threat_payload(match: dict, kind: str, path: str | None = None) -> ThreatPayload:
    """Convert an open advisory match into a ThreatPayload for propose_shield.

    Burns when the match is not allowlisted / not shield-worthy. Never applies
    anything — caller must still propose → founder Shield tap.
    """
    if not isinstance(match, dict) or kind not in KINDS:
        raise ThreatBurned()
    affected = match.get("affected") or {}
    app = affected.get("app") if isinstance(affected, dict) else None
    if not isinstance(app, str) or not app:
        raise ThreatBurned()
    site = WATCHED_SITES.get(app)
    if site is None:
        raise ThreatBurned()
    severity = match.get("severity") if isinstance(match.get("severity"), dict) else {}
    if severity.get("known_exploited"):
        sev = ThreatSeverity.known_exploited
    else:
        label = str(severity.get("label") or "unknown")
        try:
            sev = ThreatSeverity(label)
        except ValueError:
            sev = ThreatSeverity.unknown
    # Serious matches only — same bar as proposals_for_match.
    if sev not in {ThreatSeverity.known_exploited, ThreatSeverity.critical, ThreatSeverity.high}:
        raise ThreatBurned()
    source_ids = match.get("source_ids") if isinstance(match.get("source_ids"), list) else []
    cves: list[str] = []
    for item in source_ids:
        if isinstance(item, str) and CVE_RE.fullmatch(item) and item not in cves:
            cves.append(item)
    advisory_id = match.get("advisory_id")
    if isinstance(advisory_id, str) and CVE_RE.fullmatch(advisory_id) and advisory_id not in cves:
        cves.insert(0, advisory_id)
    match_id = match.get("id")
    if match_id is not None and not isinstance(match_id, str):
        raise ThreatBurned()
    # Fixed plain reason — never copy free-form advisory summary (injection surface).
    reason = f"{advisory_id or 'advisory'} on {app}"
    raw = {
        "schema_version": SCHEMA_VERSION,
        "action": ThreatAction.propose_shield.value,
        "site": site,
        "kind": kind,
        "path": path,
        "match_id": match_id,
        "cve_ids": cves[:20],
        "severity": sev.value,
        "reason": reason[:300],
        "confidence": 1.0 if sev is ThreatSeverity.known_exploited else 0.85,
    }
    return accept_threat_payload(raw)
