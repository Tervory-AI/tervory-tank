"""The only way Radix code makes an HTTP call outside Tank and Hermes.

RADIX_ALLOWED_HOSTS is a comma-separated host list. Empty refuses every host.
Tank and Hermes are reached by the chassis, not by this client.
"""

from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

import httpx


class HostNotAllowed(PermissionError):
    """The host is not on RADIX_ALLOWED_HOSTS."""

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(f"host not allowed: {host or '(none)'}")


def allowed_hosts(raw: str | None = None) -> frozenset[str]:
    if raw is None:
        raw = os.environ.get("RADIX_ALLOWED_HOSTS", "")
    names = (part.strip().lower().rstrip(".") for part in raw.split(","))
    return frozenset(name for name in names if name)


def host_from_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    return parsed.hostname.lower().rstrip(".")


def require_allowed(url: str, allow: frozenset[str] | None = None) -> str:
    """Return the host, or refuse it. An empty list refuses every host."""
    host = host_from_url(url)
    listed = allowed_hosts() if allow is None else allow
    if host not in listed:
        raise HostNotAllowed(host)
    return host


class Client:
    """HTTP client. Refuses any host that is not on RADIX_ALLOWED_HOSTS."""

    def __init__(
        self,
        allow: frozenset[str] | None = None,
        http: httpx.Client | None = None,
    ) -> None:
        self._allow = allowed_hosts() if allow is None else allow
        self._http = http

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        require_allowed(url, self._allow)
        if self._http is None:
            with httpx.Client(timeout=30) as client:
                return client.request(method, url, **kwargs)
        return self._http.request(method, url, **kwargs)

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)
