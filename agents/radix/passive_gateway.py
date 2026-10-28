"""DNS proof and one short-lived scan tunnel on the sealed room's egress peer.

The API accepts only persisted pending run IDs. Domains and proof values come
from the tenant-scoped database join, never the HTTP caller. No scan CLI or
browser runs on this internet-connected peer.
"""
from __future__ import annotations

import asyncio
import hmac
import os
import time
from contextlib import asynccontextmanager
from uuid import UUID

import asyncpg
import dns.asyncresolver
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict

from egress import Proxy, Server, env_revoked, system_resolve
from passive_store import Store


async def proof(domain: str, challenge: str) -> bool:
    try:
        answer = await dns.asyncresolver.resolve('_tervory-verify.' + domain, 'TXT', lifetime=5)
        return any(hmac.compare_digest(b''.join(row.strings).decode('ascii'), challenge) for row in answer)
    except (dns.exception.DNSException, UnicodeError, OSError):
        return False


class Lease:
    def __init__(self, store, *, check=proof, server=Server, now=time.monotonic):
        self.store, self.check, self.server, self.now = store, check, server, now
        self.lock = asyncio.Lock()
        self.run = None
        self.until = 0.0
        self.proxy_server = None

    def close(self):
        self.until = 0
        self.run = None
        if self.proxy_server:
            self.proxy_server.close()
            self.proxy_server = None

    async def start(self, tenant: UUID, ident: UUID):
        async with self.lock:
            if self.run is not None and self.now() < self.until:
                raise HTTPException(409, 'scan busy')
            self.close()
            row = await self.store.pending(tenant, ident)
            if row is None or not await self.check(row['domain'], row['challenge']):
                raise HTTPException(403, 'domain proof required')
            if env_revoked():
                raise HTTPException(403, 'egress revoked')
            try:
                started = await self.store.running(tenant, ident)
            except asyncpg.UniqueViolationError:
                raise HTTPException(409, 'scan busy') from None
            if not started:
                raise HTTPException(409, 'scan unavailable')
            self.run, self.until = (tenant, ident), self.now() + 420
            domain = row['domain']
            # Capture this lease's deadline, so a later tenant cannot revive an old tunnel.
            until = self.until
            proxy = Proxy(verified_host=domain, allow_storage=False,
                resolve=lambda host: system_resolve(host, verified_host=domain),
                active=lambda: self.run == (tenant, ident) and self.now() < until and not env_revoked())
            try:
                self.proxy_server = self.server(proxy, host='0.0.0.0', port=8082).start()
            except Exception:
                self.close()
                await self.store.fail(tenant, ident)
                raise HTTPException(503, 'scan egress unavailable') from None
            return {'ready': True}

    async def release(self, tenant: UUID, ident: UUID):
        async with self.lock:
            if self.run == (tenant, ident):
                self.close()


class Run(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    scan_id: UUID


@asynccontextmanager
async def lifespan(app):
    app.state.pool = await asyncpg.create_pool(os.environ['DATABASE_URL'], min_size=1, max_size=2)
    app.state.lease = Lease(Store(app.state.pool))
    try:
        yield
    finally:
        app.state.lease.close()
        await app.state.pool.close()


app = FastAPI(lifespan=lifespan)


@app.post('/lease')
async def lease(body: Run):
    return await app.state.lease.start(body.tenant_id, body.scan_id)


@app.post('/release')
async def release(body: Run):
    await app.state.lease.release(body.tenant_id, body.scan_id)
    return {'released': True}


@app.get('/health')
async def health():
    return {'ok': True}
