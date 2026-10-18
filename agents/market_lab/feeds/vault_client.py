"""Ask Tank whether lab.vault is on, and which feed key names it holds.

The feeds runner calls this once per pass. A secret is fetched only when a
live call needs that one name. Values are not logged. If Tank cannot be
reached, the vault is treated as off and env keys still work.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from feeds.keys import configure_vault

Opener = Callable[..., Any]


def refresh(opener: Opener | None = None) -> None:
    """Load lab.vault's feed-key names. No-op when TANK_URL is unset."""
    if not os.environ.get("TANK_URL", "").strip():
        return
    fetch = opener or urllib.request.urlopen
    try:
        enabled, names = _names(fetch)
    except Exception:
        configure_vault(enabled=False)
        return
    if not enabled:
        configure_vault(enabled=False)
        return
    configure_vault(enabled=True, names=names, resolver=lambda name: _one(fetch, name))


def _names(fetch: Opener) -> tuple[bool, list[str]]:
    tenant = os.environ.get("FEEDS_TENANT_ID", "").strip()
    if not tenant:
        return False, []
    url = _base() + "/v1/vaults/lab.vault/plugins?tenant_id=" + quote(tenant)
    body = _get(fetch, url)
    enabled = bool(body.get("enabled"))
    names = []
    for row in body.get("secrets") or []:
        if isinstance(row, dict) and isinstance(row.get("name"), str):
            names.append(row["name"])
    return enabled, names


def _one(fetch: Opener, name: str) -> str:
    tenant = os.environ.get("FEEDS_TENANT_ID", "").strip()
    if not tenant:
        return ""
    url = _base() + "/v1/vaults/lab.vault/secrets/resolve"
    payload = json.dumps({"tenant_id": tenant, "name": name}).encode()
    request = urllib.request.Request(url, data=payload, headers=_headers("application/json"), method="POST")
    try:
        with fetch(request, timeout=5) as response:
            raw = response.read()
    except Exception:
        return ""
    try:
        body = json.loads(raw.decode())
    except (UnicodeDecodeError, json.JSONDecodeError):
        return ""
    if not isinstance(body, dict) or not body.get("found"):
        return ""
    value = body.get("value")
    return value.strip() if isinstance(value, str) else ""


def _get(fetch: Opener, url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=_headers(None), method="GET")
    try:
        with fetch(request, timeout=5) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        raw = exc.read()
    body = json.loads(raw.decode())
    if not isinstance(body, dict):
        raise ValueError("vault list was not an object")
    return body


def _base() -> str:
    return os.environ.get("TANK_URL", "").strip().rstrip("/")


def _headers(content_type: str | None) -> dict[str, str]:
    headers = {"X-Tank-Key": os.environ.get("TANK_KEY", "").strip(), "Accept": "application/json"}
    if content_type:
        headers["Content-Type"] = content_type
    return headers
