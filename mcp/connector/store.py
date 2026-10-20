"""Short-lived sign-in state. Redis when configured, otherwise this process."""

from __future__ import annotations

import json
import time
from typing import Any, Protocol


class Store(Protocol):
    async def put(self, key: str, value: dict[str, Any], ttl_s: int) -> None: ...

    async def get(self, key: str) -> dict[str, Any] | None: ...

    async def pop(self, key: str) -> dict[str, Any] | None: ...


class MemoryStore:
    def __init__(self) -> None:
        self._rows: dict[str, tuple[float, dict[str, Any]]] = {}

    def _live(self, key: str) -> dict[str, Any] | None:
        row = self._rows.get(key)
        if row is None:
            return None
        expires, value = row
        if expires < time.time():
            self._rows.pop(key, None)
            return None
        return value

    async def put(self, key: str, value: dict[str, Any], ttl_s: int) -> None:
        self._rows[key] = (time.time() + ttl_s, value)

    async def get(self, key: str) -> dict[str, Any] | None:
        return self._live(key)

    async def pop(self, key: str) -> dict[str, Any] | None:
        value = self._live(key)
        self._rows.pop(key, None)
        return value


class RedisStore:
    def __init__(self, url: str) -> None:
        self._url = url
        self._client: Any = None

    async def _redis(self) -> Any:
        if self._client is None:
            from redis.asyncio import from_url

            self._client = from_url(self._url, decode_responses=True)
        return self._client

    async def put(self, key: str, value: dict[str, Any], ttl_s: int) -> None:
        client = await self._redis()
        await client.set(key, json.dumps(value), ex=ttl_s)

    async def get(self, key: str) -> dict[str, Any] | None:
        client = await self._redis()
        raw = await client.get(key)
        if not raw:
            return None
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else None

    async def pop(self, key: str) -> dict[str, Any] | None:
        client = await self._redis()
        raw = await client.getdel(key)
        if not raw:
            return None
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, dict) else None
