"""Signed inbound webhooks only (Cloudflare and Google). Unsigned dropped and counted, never stored."""
from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any


class WebhookRejected(ValueError):
    """Unsigned or badly signed — drop, count, never store the body."""


# Coolify secret names only — values never appear in code.
CF_SECRET_ENV = "AUTUMBRA_CF_WEBHOOK_SECRET"
GOOGLE_SECRET_ENV = "AUTUMBRA_GOOGLE_WEBHOOK_SECRET"

_drops: dict[str, int] = {"cloudflare": 0, "google": 0, "unknown": 0}


def drop_counts() -> dict[str, int]:
    return dict(_drops)


def reset_drop_counts() -> None:
    for key in _drops:
        _drops[key] = 0


def _secret(env_name: str) -> str:
    return os.environ.get(env_name, "").strip()


def verify_cloudflare(
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None = None,
    max_skew_seconds: int = 300,
) -> None:
    """HMAC-SHA256 over body with the named Coolify secret. No parse before verify."""
    secret = _secret(CF_SECRET_ENV)
    if not secret:
        _drops["cloudflare"] += 1
        raise WebhookRejected("Cloudflare webhook secret is not configured.")
    if not signature:
        _drops["cloudflare"] += 1
        raise WebhookRejected("missing signature")
    if timestamp is not None:
        try:
            ts = int(timestamp)
        except (TypeError, ValueError) as exc:
            _drops["cloudflare"] += 1
            raise WebhookRejected("bad timestamp") from exc
        if abs(int(time.time()) - ts) > max_skew_seconds:
            _drops["cloudflare"] += 1
            raise WebhookRejected("stale timestamp")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, provided):
        _drops["cloudflare"] += 1
        raise WebhookRejected("bad signature")


def verify_google_workspace(
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None = None,
    max_skew_seconds: int = 300,
) -> None:
    """Same shape for Google Workspace alert webhooks (channel token HMAC)."""
    secret = _secret(GOOGLE_SECRET_ENV)
    if not secret:
        _drops["google"] += 1
        raise WebhookRejected("Google webhook secret is not configured.")
    if not signature:
        _drops["google"] += 1
        raise WebhookRejected("missing signature")
    if timestamp is not None:
        try:
            ts = int(timestamp)
        except (TypeError, ValueError) as exc:
            _drops["google"] += 1
            raise WebhookRejected("bad timestamp") from exc
        if abs(int(time.time()) - ts) > max_skew_seconds:
            _drops["google"] += 1
            raise WebhookRejected("stale timestamp")
    expected = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(expected, provided):
        _drops["google"] += 1
        raise WebhookRejected("bad signature")


def accept_signed(
    provider: str,
    body: bytes,
    *,
    signature: str | None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Verify then return a tiny envelope. Body is not persisted by this helper."""
    if provider == "cloudflare":
        verify_cloudflare(body, signature=signature, timestamp=timestamp)
    elif provider == "google":
        verify_google_workspace(body, signature=signature, timestamp=timestamp)
    else:
        _drops["unknown"] += 1
        raise WebhookRejected("unknown provider")
    return {
        "provider": provider,
        "bytes": len(body),
        "accepted": True,
        "stored": False,
        "note": "Verified at the Watch edge. Body stays in working memory only.",
    }
