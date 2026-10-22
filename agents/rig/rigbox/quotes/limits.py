"""Short-lived abuse counters, separate from anonymous usage analytics.

Production uses Postgres; the memory implementation is for the sample app/tests.
Raw addresses never enter storage. A fresh per-tenant/minute secret salts their
HMACs, so counters cannot be joined across windows, tenants or analytics.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import os
import secrets
import time
from typing import Any
from uuid import UUID

QUOTE_ROUTES = frozenset({"/v1/rig/quote", "/v1/rig/link-quote"})


def client_address(request: Any) -> str:
    peer = request.client.host if request.client else "unknown"
    networks = []
    for value in os.environ.get("RIG_TRUSTED_PROXY_CIDRS", "").split(","):
        if value.strip():
            network = ipaddress.ip_network(value.strip(), strict=False)
            if network.prefixlen == 0:
                raise ValueError("A specific trusted proxy network is required")
            networks.append(network)

    def trusted(value: str) -> bool:
        try:
            address = ipaddress.ip_address(value)
            return any(address in network for network in networks)
        except ValueError:
            return False

    if not trusted(peer):
        return peer
    forwarded = request.headers.get("x-forwarded-for", "")
    try:
        chain = [str(ipaddress.ip_address(value.strip())) for value in forwarded.split(",")]
    except ValueError:
        return peer
    if len(chain) > 16:
        return peer
    # Walk from the known peer, never trust the leftmost header blindly.
    for address in reversed(chain):
        peer = address
        if not trusted(address):
            break
    return peer


def budgets(route: str, read_limit: int = 60) -> tuple[str, int, str, int]:
    if route in QUOTE_ROUTES:
        return "quotes", 5, "quotes", 600
    limit = 10 if route == "/v1/rig/ask" else read_limit
    return route, limit, "browse", 6000


def fingerprint(salt: bytes, address: str) -> bytes:
    return hmac.new(salt, address.encode(), hashlib.sha256).digest()


class MemoryRateLimits:
    def __init__(self, read_limit: int = 60, clock=time.time):
        self.read_limit, self.clock = read_limit, clock
        self.windows: dict[tuple[str, int], tuple[bytes, dict]] = {}
        self.lock = asyncio.Lock()

    async def consume(self, tenant: str, address: str, route: str) -> int:
        now = int(self.clock())
        window = now // 60
        async with self.lock:
            self.windows = {key: value for key, value in self.windows.items() if key[1] >= window - 1}
            salt, counts = self.windows.setdefault((tenant, window), (secrets.token_bytes(32), {}))
            client_route, limit, group, ceiling = budgets(route, self.read_limit)
            keys = [(group, b""), (client_route, fingerprint(salt, address))]
            if any(counts.get(key, 0) >= cap for key, cap in zip(keys, (ceiling, limit))):
                return 60 - now % 60
            for key in keys:
                counts[key] = counts.get(key, 0) + 1
        return 0


class _Full(Exception):
    pass


class PgRateLimits:
    def __init__(self, pool: Any, read_limit: int = 60):
        self.pool, self.read_limit = pool, read_limit

    async def consume(self, tenant: str, address: str, route: str) -> int:
        retry_after = 60
        try:
            async with self.pool.acquire() as conn, conn.transaction():
                now = int(await conn.fetchval("SELECT extract(epoch FROM clock_timestamp())::bigint"))
                window = now // 60
                retry_after = 60 - now % 60
                await conn.execute("""DELETE FROM agent_rig.rate_windows
                    WHERE tenant_id=$1 AND window_id < $2""", UUID(tenant), window - 1)
                await conn.execute("""INSERT INTO agent_rig.rate_windows (tenant_id, window_id, salt)
                    VALUES ($1,$2,$3) ON CONFLICT DO NOTHING""", UUID(tenant), window, secrets.token_bytes(32))
                salt = bytes(await conn.fetchval("""SELECT salt FROM agent_rig.rate_windows
                    WHERE tenant_id=$1 AND window_id=$2""", UUID(tenant), window))
                client_route, limit, group, ceiling = budgets(route, self.read_limit)
                for bucket, identity, cap in [(group, b"", ceiling),
                                              (client_route, fingerprint(salt, address), limit)]:
                    accepted = await conn.fetchval("""INSERT INTO agent_rig.rate_counts
                        (tenant_id, window_id, route, client_hash, hits) VALUES ($1,$2,$3,$4,1)
                        ON CONFLICT (tenant_id, window_id, route, client_hash) DO UPDATE
                        SET hits=agent_rig.rate_counts.hits + 1 WHERE agent_rig.rate_counts.hits < $5
                        RETURNING hits""", UUID(tenant), window, bucket, identity, cap)
                    if accepted is None:
                        raise _Full  # Roll back BOTH counters; rejected clients cannot drain the tenant.
        except _Full:
            return retry_after
        return 0
