"""Autumbra Watch OSS intake adapters (Vector / Fluent Bit / Steampipe / OpenCTI).

Thin adapters over the staging vault at /workspace/autumbra-oss-vault — we do not
vendor multi-GB upstream trees. Stronger-than-stock defaults:

- anomaly-only forward (raw client payloads never leave the onsite bus)
- telemetry / phone-home off
- ThreatPayload burn before any Watch→Enforce handoff
- Steampipe read-only; OpenCTI CE + feed allowlist

Product copy: Autumbra Watch / Autumbra Enforce only.
Flag: WATCH_OSS_ENABLED / GHOST_WATCH_OSS_ENABLED (default OFF).
"""
from __future__ import annotations

import os

from .common import (
    DEFAULT_ANOMALY_THRESHOLD,
    AnomalyEvent,
    anomaly_only,
    enabled,
    handoff_threat,
)
from . import fluentbit, opencti, steampipe, vector

__all__ = [
    "DEFAULT_ANOMALY_THRESHOLD",
    "AnomalyEvent",
    "anomaly_only",
    "enabled",
    "fluentbit",
    "handoff_threat",
    "opencti",
    "steampipe",
    "vector",
]


def status() -> dict:
    """Operator-facing status (Autumbra Watch copy). Never claims upstream is live."""
    return {
        "product": "Autumbra Watch",
        "enabled": enabled(),
        "adapters": {
            "vector": vector.adapter_meta(),
            "fluent_bit": fluentbit.adapter_meta(),
            "steampipe": steampipe.adapter_meta(),
            "opencti": opencti.adapter_meta(),
        },
        "note": (
            "Adapters and presets only. Upstream daemons are not started by this "
            "module. Dual-LLM / Wazuh triage are not live here."
        ),
        "vault_hint": os.environ.get(
            "AUTUMBRA_OSS_VAULT", "/workspace/autumbra-oss-vault"
        ),
    }
