"""Memory client. C7 (Hermes) fills these in. Private to one agent and one tenant."""

from __future__ import annotations

from typing import Any


class MemoryClient:
    async def remember(self, tenant_id: str, text: str, kind: str, source: str) -> None:
        raise NotImplementedError("memory arrives in C7 (Hermes)")

    async def recall(self, tenant_id: str, query: str) -> list[dict[str, Any]]:
        raise NotImplementedError("memory arrives in C7 (Hermes)")

    async def forget(self, memory_id: str) -> None:
        raise NotImplementedError("memory arrives in C7 (Hermes)")
