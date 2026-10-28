"""Calls Tank with this agent's own key. No model or provider keys live here."""

from __future__ import annotations

from typing import Any

import httpx


class TankClient:
    def __init__(self, base_url: str, api_key: str, agent: str, http: httpx.AsyncClient) -> None:
        self._base = base_url.rstrip("/")
        self._api_key = api_key
        self.agent = agent
        self._http = http

    def __repr__(self) -> str:
        return f"TankClient(agent={self.agent!r})"

    async def route(self, tenant_id: str, task_type: str, messages: list[dict[str, str]]) -> dict[str, Any]:
        return await self._post(
            "/v1/route",
            {
                "tenant_id": str(tenant_id),
                "agent": self.agent,
                "task_type": task_type,
                "messages": messages,
            },
        )

    async def run_skill(self, tenant_id: str, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._post(
            f"/v1/skala/{skill_id}/run",
            {"tenant_id": str(tenant_id), "input": payload},
        )

    async def approved_skill(self, tenant_id: str, skill_id: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        """Only an explicit absence of approval permits the legacy implementation.

        Do not cache the version: approval and rollback take effect on the next
        call. Run without a version pin so Skala rechecks approval at execution.
        Failures after approval never silently fall back to room code.
        """
        if not self._api_key:
            raise RuntimeError("tank key is not set")
        response = await self._http.get(
            self._base + f"/v1/skala/{skill_id}/run",
            headers={"X-Tank-Key": self._api_key},
        )
        if (response.status_code == 409 and response.json().get("detail")
                == f"{skill_id} has no approved version"):
            return None
        response.raise_for_status()
        return await self.run_skill(tenant_id, skill_id, payload)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("tank key is not set")
        response = await self._http.post(
            self._base + path,
            json=body,
            headers={"X-Tank-Key": self._api_key},
        )
        if response.status_code >= 400:
            raise RuntimeError(f"tank answered {response.status_code}")
        data = response.json()
        if not isinstance(data, dict):
            raise RuntimeError("tank answer was not an object")
        return data
