"""Fixed browser gateway plus exact-host CONNECT proxy.

Only this process has an outbound Docker network. Chromium lives on an internal
network with no default internet route; clearing proxy settings cannot bypass it.
DNS results are checked and the TCP connection uses the checked IP, preventing
DNS rebinding to metadata services, other rooms or the Docker host.
"""
from __future__ import annotations

import asyncio
import os
import socket
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException

from brain.security import allowed_hosts, authenticate, public_address, scope


async def tunnel(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    remote = None
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        if len(raw) > 8192:
            raise ValueError("header too large")
        method, target, _version = raw.split(b"\r\n", 1)[0].decode("ascii").split()
        host, port = target.rsplit(":", 1)
        if method != "CONNECT" or port != "443" or host.lower() not in allowed_hosts(os.environ.get("BASE_ALLOWED_HOSTS", "")):
            raise ValueError("host refused")
        answers = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = [a[4][0] for a in answers]
        if not addresses or not all(public_address(ip) for ip in addresses):
            raise ValueError("non-public address")
        upstream, remote = await asyncio.wait_for(asyncio.open_connection(addresses[0], 443), 10)
        writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        await writer.drain()

        async def copy(source, destination):
            while data := await asyncio.wait_for(source.read(65536), 45):
                destination.write(data)
                await destination.drain()

        tasks = [asyncio.create_task(copy(reader, remote)), asyncio.create_task(copy(upstream, writer))]
        try:
            await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
    except (ValueError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n")
    finally:
        writer.close()
        if remote:
            remote.close()


@asynccontextmanager
async def lifespan(app):
    server = await asyncio.start_server(tunnel, "0.0.0.0", 3128, limit=8192)
    async with server:
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/render")
async def render(body: dict, x_tank_key: str = Header(default=""), x_tenant_id: str = Header(default=""),
                 x_home_region: str = Header(default=""), x_task_id: str = Header(default="")):
    authenticate(x_tank_key)
    tenant = scope(x_tenant_id, x_home_region)
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post("http://base-browser:3000/render", json=body, headers={
                "X-Tank-Key": x_tank_key, "X-Tenant-ID": tenant, "X-Home-Region": x_home_region, "X-Task-ID": x_task_id})
        if response.status_code != 200:
            raise HTTPException(response.status_code, "Base browser refused the request.")
        return response.json()
    except httpx.HTTPError:
        raise HTTPException(503, "Base browser is unavailable.") from None
