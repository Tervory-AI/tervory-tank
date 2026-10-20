"""The only path from this service to a model or a record: Tank."""

from __future__ import annotations

from typing import Any, Protocol

import httpx


class TankError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(detail)


class Tank(Protocol):
    async def call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any: ...


def public_detail(status: int, payload: Any) -> str:
    """A short reason safe to show. Nothing that looks like a credential."""
    detail = ""
    if isinstance(payload, dict):
        raw = payload.get("detail")
        if isinstance(raw, str):
            detail = raw
        elif isinstance(raw, dict):
            inner = raw.get("detail") or raw.get("message")
            detail = inner if isinstance(inner, str) else ""
    elif isinstance(payload, str):
        detail = payload
    text = " ".join(detail.split())[:300]
    lowered = text.lower()
    if any(word in lowered for word in ("key", "token", "secret", "password", "authorization")):
        return "Tank refused the call."
    if text:
        return text
    if status == 503:
        return "Tank is unreachable."
    if status == 404:
        return "Tank has no such call."
    if status == 409:
        return "Tank could not run that yet."
    return "Tank refused the call."


class HttpTank:
    def __init__(self, base_url: str, api_key: str, http: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self._http = http

    async def call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> Any:
        if not self._api_key.strip():
            raise TankError(503, "Tank is not configured.")
        headers = {"Accept": "application/json", "X-Tank-Key": self._api_key}
        try:
            response = await self._http.request(
                method,
                self._base + path,
                headers=headers,
                json=body,
                params=params,
            )
        except httpx.HTTPError:
            raise TankError(503, "Tank is unreachable.") from None
        raw: Any = None
        if response.content:
            try:
                raw = response.json()
            except ValueError:
                raw = None
        if response.status_code >= 400:
            raise TankError(response.status_code, public_detail(response.status_code, raw))
        return raw
