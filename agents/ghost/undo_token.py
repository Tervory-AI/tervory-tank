"""Signed, expiring Autumbra undo tokens for owner email links.

Token names tenant_id + shield (rule_id) + receipt_id. The owner can undo from
the email without workspace sign-in; /api/autumbra/undo verifies this token only.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


DEFAULT_TTL_SEC = 7 * 24 * 3600


def _secret() -> bytes:
    raw = (os.environ.get("AUTUMBRA_UNDO_TOKEN_SECRET") or "").strip()
    if not raw:
        # Fall back to webhook secret so dogfood hosts with one secret still work.
        raw = (os.environ.get("AUTUMBRA_EDGE_WEBHOOK_SECRET") or "").strip()
    if not raw:
        raise RuntimeError("AUTUMBRA_UNDO_TOKEN_SECRET is not configured.")
    return raw.encode("utf-8")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign_undo_token(
    *,
    tenant_id: str,
    receipt_id: str,
    rule_id: str = "",
    site: str = "",
    ttl_sec: int = DEFAULT_TTL_SEC,
    now: float | None = None,
) -> str:
    """Return a compact signed token naming tenant + shield (+ receipt)."""
    tid = (tenant_id or "").strip()
    rid = (receipt_id or "").strip()
    if not tid or not rid:
        raise ValueError("undo token requires tenant_id and receipt_id")
    payload = {
        "tenant_id": tid,
        "receipt_id": rid,
        "rule_id": (rule_id or "").strip(),
        "site": (site or "").strip(),
        "exp": int((now if now is not None else time.time()) + max(60, int(ttl_sec))),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = _b64url(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{sig}"


def verify_undo_token(token: str, *, now: float | None = None) -> dict[str, Any]:
    """Verify signature + expiry. Returns payload or raises ValueError."""
    raw = (token or "").strip()
    if not raw or "." not in raw:
        raise ValueError("undo token missing")
    body, _, sig = raw.partition(".")
    if not body or not sig:
        raise ValueError("undo token malformed")
    expected = _b64url(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    if not hmac.compare_digest(expected, sig):
        raise ValueError("undo token signature invalid")
    try:
        payload = json.loads(_b64url_decode(body).decode("utf-8"))
    except Exception as exc:
        raise ValueError("undo token payload invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("undo token payload invalid")
    exp = int(payload.get("exp") or 0)
    if exp < int(now if now is not None else time.time()):
        raise ValueError("undo token expired")
    tenant_id = str(payload.get("tenant_id") or "").strip()
    receipt_id = str(payload.get("receipt_id") or "").strip()
    if not tenant_id or not receipt_id:
        raise ValueError("undo token missing tenant or receipt")
    return {
        "tenant_id": tenant_id,
        "receipt_id": receipt_id,
        "rule_id": str(payload.get("rule_id") or "").strip(),
        "site": str(payload.get("site") or "").strip(),
        "exp": exp,
    }
