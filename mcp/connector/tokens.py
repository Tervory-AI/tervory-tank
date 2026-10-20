"""Signed access tokens and PKCE. The signing key stays in the environment."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


class TokenError(Exception):
    """The presented token is not one this server issued."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64_json(value: dict[str, Any]) -> str:
    return _b64(json.dumps(value, separators=(",", ":")).encode("utf-8"))


def _unb64(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def code_verifier() -> str:
    return secrets.token_urlsafe(48)


def code_challenge(verifier: str) -> str:
    return _b64(hashlib.sha256(verifier.encode("ascii")).digest())


def challenge_matches(verifier: str, challenge: str) -> bool:
    if not verifier or not challenge:
        return False
    return hmac.compare_digest(code_challenge(verifier), challenge)


def sign_access(
    *,
    secret: str,
    issuer: str,
    audience: str,
    user_id: str,
    org_id: str,
    tenant_id: str,
    ttl_s: int = 3600,
    now: int | None = None,
) -> str:
    issued = int(time.time() if now is None else now)
    header = _b64_json({"alg": "HS256", "typ": "JWT"})
    body = _b64_json(
        {
            "iss": issuer,
            "aud": audience,
            "sub": user_id,
            "org_id": org_id,
            "tenant_id": tenant_id,
            "typ": "access",
            "iat": issued,
            "exp": issued + ttl_s,
        }
    )
    mac = hmac.new(secret.encode("utf-8"), f"{header}.{body}".encode("ascii"), hashlib.sha256).digest()
    return f"{header}.{body}.{_b64(mac)}"


def read_access(
    token: str,
    *,
    secret: str,
    issuer: str,
    audience: str,
    now: int | None = None,
    skew_s: int = 60,
) -> dict[str, Any]:
    parts = (token or "").split(".")
    if len(parts) != 3 or not secret:
        raise TokenError("rejected")
    try:
        header = json.loads(_unb64(parts[0]))
        payload = json.loads(_unb64(parts[1]))
        signature = _unb64(parts[2])
    except (ValueError, json.JSONDecodeError, UnicodeError):
        raise TokenError("rejected") from None
    if not isinstance(header, dict) or header.get("alg") != "HS256":
        raise TokenError("rejected")
    if not isinstance(payload, dict) or payload.get("typ") != "access":
        raise TokenError("rejected")
    expected = hmac.new(secret.encode("utf-8"), f"{parts[0]}.{parts[1]}".encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(signature, expected):
        raise TokenError("rejected")
    moment = int(time.time() if now is None else now)
    try:
        expires = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        raise TokenError("rejected") from None
    if expires + skew_s < moment:
        raise TokenError("rejected")
    if payload.get("iss") != issuer or payload.get("aud") != audience:
        raise TokenError("rejected")
    if not str(payload.get("sub") or "").strip() or not str(payload.get("org_id") or "").startswith("org_"):
        raise TokenError("rejected")
    return payload
