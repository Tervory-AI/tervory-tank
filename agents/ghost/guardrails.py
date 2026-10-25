"""Tank-only NeMo-shaped inbound guardrails (GHOST-6 Dual-LLM air gap).

Scans untrusted inbound text (logs / triage strings) for prompt-injection
signatures before Ghost LLM or ThreatPayload triage use. This is the front
door the Gemini brief calls NeMo Guardrails — implemented here without the
NVIDIA NeMo / GPU / vLLM packages. Keep using Tank.

When a GPU bunker exists, replace the body of `guard_inbound` with a call into
`nemoguardrails` (or LLM Guard) and keep this public API stable.

Injection markers are imported from threat_payload — one shared source of truth.
On deny we raise GuardBurned with a fixed detail string and never echo input.
"""
from __future__ import annotations

from .threat_payload import INJECTION_MARKERS

GUARD_BURN_DETAIL = "Inbound text burned by guardrails. No action was taken."
# Same size bar as ThreatPayload preflight — drop oversized dirty text early.
MAX_INBOUND = 8_000


class GuardBurned(ValueError):
    """Raised when inbound text is refused. Message is always GUARD_BURN_DETAIL."""

    def __init__(self) -> None:
        super().__init__(GUARD_BURN_DETAIL)


def guard_inbound(text: str | bytes) -> str:
    """Pass through clean inbound text, or burn on injection / decode / size.

    Never echoes the rejected input. Callers should map GuardBurned → 422 with
    GUARD_BURN_DETAIL only.
    """
    if isinstance(text, (bytes, bytearray)):
        if len(text) > MAX_INBOUND:
            raise GuardBurned()
        try:
            decoded = text.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise GuardBurned() from exc
    elif isinstance(text, str):
        if len(text) > MAX_INBOUND:
            raise GuardBurned()
        decoded = text
    else:
        raise GuardBurned()
    lowered = decoded.lower()
    # Shared markers with ThreatPayload (ignore previous, system prompt, ```, shell…).
    if any(marker in lowered for marker in INJECTION_MARKERS):
        raise GuardBurned()
    return decoded
