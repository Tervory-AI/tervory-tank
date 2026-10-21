"""Public-web proxy with checked, pinned DNS and a browser-only listening socket."""
from __future__ import annotations

import asyncio
import socket
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Header, HTTPException

from brain.security import authenticate, public_destination, public_url, scope


async def tunnel(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    remote = None
    try:
        raw = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), 10)
        if len(raw) > 16384:
            raise ValueError("header too large")
        first, *headers = raw[:-4].decode("latin1").split("\r\n")
        method, target, version = first.split()
        if method == "CONNECT":
            host, port = target.rsplit(":", 1)
            if port != "443":
                raise ValueError("unsupported port")
            url = "https://" + ("[" + host.strip("[]") + "]" if ":" in host else host)
        else:
            if method not in {"GET", "HEAD", "POST", "OPTIONS"}:
                raise ValueError("unsupported method")
            url = target
            if urlsplit(url).scheme != "http":
                raise ValueError("use CONNECT for HTTPS")
        _host, port, addresses = await public_destination(url)
        upstream, remote = await asyncio.wait_for(asyncio.open_connection(addresses[0], port), 20)
        if method == "CONNECT":
            writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await writer.drain()
        else:
            parsed = urlsplit(url)
            path = (parsed.path or "/") + ("?" + parsed.query if parsed.query else "")
            # One checked destination per HTTP connection. Strip proxy headers
            # and pipelining/keep-alive so another host cannot reuse this socket.
            cleaned = [h for h in headers if h.split(":", 1)[0].lower() not in {
                "proxy-authorization", "proxy-connection", "connection", "host"}]
            cleaned += ["Host: " + parsed.netloc, "Connection: close"]
            remote.write((method + " " + path + " " + version + "\r\n" + "\r\n".join(cleaned) + "\r\n\r\n").encode("latin1"))
            await remote.drain()

        async def copy(source, destination):
            while data := await asyncio.wait_for(source.read(65536), 120):
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


def browser_interface() -> str:
    # The UDP route lookup does not send a packet. It selects only the gateway's
    # interface on the browser network, never its Base corridor interface.
    address = socket.gethostbyname("base-browser")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((address, 3000))
        return sock.getsockname()[0]


@asynccontextmanager
async def lifespan(app):
    server = await asyncio.start_server(tunnel, browser_interface(), 3128, limit=16384)
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
        public_url(body.get("url", ""))
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post("http://base-browser:3000/render", json=body, headers={
                "X-Tank-Key": x_tank_key, "X-Tenant-ID": tenant, "X-Home-Region": x_home_region, "X-Task-ID": x_task_id})
        if response.status_code != 200:
            raise HTTPException(response.status_code, "Base browser refused the request.")
        return response.json()
    except ValueError:
        raise HTTPException(403, "Private or unsupported web address.") from None
    except httpx.HTTPError:
        raise HTTPException(503, "Base browser is unavailable.") from None
