"""Signed inbound webhooks only. Unsigned dropped and counted, never stored.

Founder correction: no Cloudflare-named secrets yet. Env names are agnostic
(edge / mailbox). Values never appear in code.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any


class WebhookRejected(ValueError):
    """Unsigned or badly signed — drop, count, never store the body."""


# Coolify secret names only — agnostic; no Cloudflare-named secrets until a real CF client.
EDGE_WEBHOOK_SECRET_ENV = "AUTUMBRA_EDGE_WEBHOOK_SECRET"
MAILBOX_WEBHOOK_SECRET_ENV = "AUTUMBRA_MAILBOX_WEBHOOK_SECRET"
CF_SECRET_ENV = EDGE_WEBHOOK_SECRET_ENV  # alias name only; value from EDGE env
GOOGLE_SECRET_ENV = MAILBOX_WEBHOOK_SECRET_ENV

_drops: dict[str, int] = {"edge": 0, "mailbox": 0, "cloudflare": 0, "google": 0, "unknown": 0}


def drop_counts() -> dict[str, int]:
    return dict(_drops)


def reset_drop_counts() -> None:
    for key in _drops:
        _drops[key] = 0


def _secret(*env_names: str) -> str:
    for name in env_names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _verify(
    body: bytes,
    *,
    secret: str,
    signature: str | None,
    timestamp: str | None,
    bucket: str,
    max_skew_seconds: int = 300,
) -> None:
    if not secret:
        _drops[bucket] += 1
        raise WebhookRejected(f"{bucket} webhook secret is not configured.")
    if not signature:
        _drops[bucket] += 1
        raise WebhookRejected("missing signature")
    if timestamp is not None:
        try:
            ts = int(timestamp)
        except (TypeError, ValueError) as exc:
            _drops[bucket] += 1
            raise WebhookRejected("bad timestamp") from exc
        if abs(int(time.time()) - ts) > max_skew_seconds:
            _drops[bucket] += 1
            raise WebhookRejected("stale timestamp")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, provided):
        _drops[bucket] += 1
        raise WebhookRejected("bad signature")


def verify_edge(
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None = None,
    max_skew_seconds: int = 300,
) -> None:
    """HMAC-SHA256 over body with the agnostic edge webhook secret."""
    secret = _secret(EDGE_WEBHOOK_SECRET_ENV)
    try:
        _verify(
            body,
            secret=secret,
            signature=signature,
            timestamp=timestamp,
            bucket="edge",
            max_skew_seconds=max_skew_seconds,
        )
    finally:
        # Keep legacy counter in sync for older dashboards/tests.
        _drops["cloudflare"] = _drops["edge"]


def verify_mailbox(
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None = None,
    max_skew_seconds: int = 300,
) -> None:
    """HMAC-SHA256 for mailbox / Workspace-style alert webhooks."""
    secret = _secret(MAILBOX_WEBHOOK_SECRET_ENV)
    try:
        _verify(
            body,
            secret=secret,
            signature=signature,
            timestamp=timestamp,
            bucket="mailbox",
            max_skew_seconds=max_skew_seconds,
        )
    finally:
        _drops["google"] = _drops["mailbox"]


# Back-compat names.
verify_cloudflare = verify_edge
verify_google_workspace = verify_mailbox


def accept_signed(
    provider: str,
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Verify then return a tiny envelope. Body is not persisted by this helper."""
    key = str(provider or "").strip().lower()
    if key in {"cloudflare", "edge", "host_firewall"}:
        verify_edge(body, signature=signature, timestamp=timestamp)
        named = "edge"
    elif key in {"google", "google_workspace", "mailbox"}:
        verify_mailbox(body, signature=signature, timestamp=timestamp)
        named = "mailbox"
    else:
        _drops["unknown"] += 1
        raise WebhookRejected("unknown provider")
    return {
        "provider": named,
        "requested_provider": key,
        "bytes": len(body),
        "accepted": True,
        "stored": False,
        "note": "Verified at the Watch edge. Body stays in working memory only.",
    }
