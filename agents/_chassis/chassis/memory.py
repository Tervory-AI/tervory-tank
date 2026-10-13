"""Memory client. Calls Hermes with this agent's own key.

Memory is private to one agent and one tenant. Hermes chooses the collection
from the key. This client never names a collection, and it never logs the key.
"""

from __future__ import annotations

import os
from typing import Any

import httpx


class MemoryClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        agent: str | None = None,
        http: httpx.AsyncClient | None = None,
    ) -> None:
        configured = base_url if base_url is not None else os.environ.get("HERMES_URL", "")
        self._base = (configured or "http://hermes:8000").rstrip("/")
        self._api_key = api_key if api_key is not None else os.environ.get("TANK_KEY", "")
        self._agent = agent if agent is not None else os.environ.get("AGENT_NAME", "")
        self._http = http

    def __repr__(self) -> str:
        return f"MemoryClient(agent={self._agent!r})"

    async def remember(self, tenant_id: str, text: str, kind: str, source: str) -> dict[str, Any]:
        data = await self._send(
            "POST",
            "/memories",
            {
                "tenant_id": str(tenant_id),
                "text": text,
                "kind": kind,
                "source": source,
            },
        )
        if not isinstance(data, dict):
            raise RuntimeError("hermes answer was not an object")
        return data

    async def recall(
        self,
        tenant_id: str,
        query: str,
        *,
        kind: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        body: dict[str, Any] = {"tenant_id": str(tenant_id), "query": query}
        if kind:
            body["kind"] = kind
        if limit is not None:
            body["limit"] = limit
        data = await self._send("POST", "/recall", body)
        if not isinstance(data, dict) or not isinstance(data.get("memories"), list):
            raise RuntimeError("hermes answer was not an object")
        memories: list[dict[str, Any]] = []
        for item in data["memories"]:
            if not isinstance(item, dict):
                raise RuntimeError("hermes answer was not an object")
            memories.append(item)
        return memories

    async def forget(self, memory_id: str) -> None:
        await self._send("DELETE", "/memories/" + memory_id)

    async def _send(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        if not self._api_key:
            raise RuntimeError("tank key is not set")
        headers = {"X-Tank-Key": self._api_key}
        try:
            if self._http is not None:
                response = await self._http.request(method, self._base + path, json=body, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=30) as http:
                    response = await http.request(method, self._base + path, json=body, headers=headers)
        except httpx.HTTPError:
            raise RuntimeError("hermes unreachable") from None
        if response.status_code >= 400:
            raise RuntimeError(f"hermes answered {response.status_code}")
        if not response.content:
            return {}
        data = response.json()
        return data
