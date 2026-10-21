"""Shared room boundary checks, with no provider credentials or outbound calls."""
from __future__ import annotations

import hmac
import ipaddress
import os
import re
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import HTTPException


def authenticate(key: str) -> None:
    expected = os.environ.get("TANK_KEY", "")
    if not expected or not key or not hmac.compare_digest(key.encode(), expected.encode()):
        raise HTTPException(401, "Base room key required.")


def scope(tenant: str, region: str) -> str:
    if region != "us-east" or os.environ.get("TANK_REGION", "us-east") != region:
        raise HTTPException(403, "This task belongs to another region.")
    try:
        return str(uuid.UUID(tenant))
    except ValueError:
        raise HTTPException(422, "A tenant id is required.") from None


def tenant_dir(root: Path, tenant: str) -> Path:
    directory = root / "tenants" / str(uuid.UUID(tenant))
    if directory.is_symlink():
        raise RuntimeError("Tenant directory must not be a symlink")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    return directory


def allowed_hosts(raw: str) -> frozenset[str]:
    hosts = frozenset(part.strip().lower() for part in raw.split(",") if part.strip())
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host) for host in hosts):
        raise ValueError("Allowed hosts must be exact DNS names")
    return hosts


def allowed_url(url: str, hosts: frozenset[str]) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("Only public HTTPS pages are allowed")
    host = (parsed.hostname or "").lower()
    if host not in hosts:
        raise ValueError("Host is not in Base's allowlist")
    return host


def public_address(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast and not ip.is_unspecified
