"""Bind verified tenant+user into the existing lifecycle HMAC for personal memory.

Reuses the Tank/Ghost lifecycle form (tank/ghost_routes.lifecycle_message,
agents/ghost/enforce_api.verify_lifecycle): timestamp\\nmethod\\npath\\n + optional
tenant\\nuser\\n + body, signed with the agent key already used as X-Tank-Key.

Agent key alone is not end-user proof. Personal Hermes operations require the
bound five-line form so body/query user_id cannot substitute a missing or
mismatched assertion. Declared tenant-wide kinds with no user keep the
historical three-line / unsigned agent-key path.
"""
from __future__ import annotations

import hashlib
import hmac
import time
import uuid

from fastapi import HTTPException


def lifecycle_message(
    timestamp: str,
    method: str,
    path: str,
    body: bytes,
    *,
    tenant: str = "",
    user: str = "",
) -> bytes:
    """Same dual-form contract as tank/ghost_routes.lifecycle_message."""
    if tenant and user:
        return f"{timestamp}\n{method}\n{path}\n{tenant}\n{user}\n".encode() + body
    return f"{timestamp}\n{method}\n{path}\n".encode() + body


def verify_personal_identity(
    *,
    key: str,
    method: str,
    path: str,
    timestamp: str,
    signature: str,
    tenant_header: str,
    user_header: str,
    body: bytes,
    body_tenant: str | None,
    body_user: str | None,
) -> tuple[str, str]:
    """Require lifecycle-bound tenant+user for personal memory; match body/query.

    Returns normalized (tenant, user). Raises 401 on missing/bad signature,
    403 on tenant/user mismatch with the request payload.
    """
    if not key or not (timestamp or "").strip() or not (signature or "").strip():
        raise HTTPException(401, "signed identity required")
    try:
        fresh = abs(time.time() - int(timestamp)) <= 60
    except (TypeError, ValueError):
        fresh = False
    if not fresh:
        raise HTTPException(401, "signed identity required")
    user = (user_header or "").strip()
    if not user or len(user) > 200:
        raise HTTPException(401, "signed identity required")
    try:
        tenant = str(uuid.UUID((tenant_header or "").strip()))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "signed identity required") from exc
    expected = hmac.new(
        key.encode(),
        lifecycle_message(
            timestamp, method.upper(), path, body, tenant=tenant, user=user
        ),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected.encode(), signature.encode()):
        raise HTTPException(401, "signed identity required")
    if body_tenant is not None and str(body_tenant) != tenant:
        raise HTTPException(403, "tenant does not match signed identity")
    if body_user is not None and str(body_user).strip() != user:
        raise HTTPException(403, "user does not match signed identity")
    return tenant, user
