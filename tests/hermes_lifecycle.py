"""Test helper: same lifecycle HMAC MemoryClient attaches for personal Hermes calls."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from uuid import UUID


def personal_headers(
    key: str,
    method: str,
    path: str,
    *,
    tenant: str,
    user: str,
    body: dict | None = None,
    extra: dict | None = None,
) -> tuple[dict[str, str], bytes]:
    raw = b""
    if body is not None:
        raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    tenant = str(UUID(str(tenant)))
    user = str(user).strip()
    ts = str(int(time.time()))
    route = path.split("?", 1)[0]
    message = f"{ts}\n{method.upper()}\n{route}\n{tenant}\n{user}\n".encode() + raw
    headers = {
        "X-Tank-Key": key,
        "X-Lifecycle-Timestamp": ts,
        "X-Lifecycle-Signature": hmac.new(key.encode(), message, hashlib.sha256).hexdigest(),
        "X-Tervory-Tenant": tenant,
        "X-Tervory-User": user,
        **(extra or {}),
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    return headers, raw
