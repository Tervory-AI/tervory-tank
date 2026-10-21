"""Base's careful public-web visitor, with persistent cookies and no bot bypass."""
from __future__ import annotations

import asyncio
import hashlib
import html as html_module
import io
import json
import os
import re
import socket
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from brain.security import public_url, scope, tenant_dir

app = FastAPI()
# The browser holds no Tank key (SEAL-1): it runs untrusted web pages. Its only
# caller is base-browser-gateway, which checks the room key before forwarding.
GATEWAY_HOST = "base-browser-gateway"


async def gateway_addresses() -> set[str]:
    answers = await asyncio.get_running_loop().getaddrinfo(GATEWAY_HOST, 3000, type=socket.SOCK_STREAM)
    return {answer[4][0] for answer in answers}


@app.middleware("http")
async def only_the_gateway(request: Request, call_next):
    # Everything but /health must come from the gateway's address on the internal
    # browser network. A page inside this container calls from 127.0.0.1, which is
    # refused. uvicorn runs with --no-proxy-headers, so the peer cannot be forged.
    if request.url.path != "/health":
        peer = request.client.host if request.client else ""
        try:
            allowed = await gateway_addresses()
        except OSError:
            return JSONResponse({"detail": "Base browser gateway cannot be found."}, status_code=503)
        if not peer or peer not in allowed:
            return JSONResponse({"detail": "Base browser accepts work only from its gateway."}, status_code=401)
    return await call_next(request)
concurrency = asyncio.Semaphore(4)
site_locks: dict[str, asyncio.Lock] = {}
last_visit: dict[str, float] = {}
QUEUE_TIMEOUT = 20


@asynccontextmanager
async def render_slot(site):
    lock = site_locks.setdefault(site, asyncio.Lock())
    locked = admitted = False
    try:
        try:
            async with asyncio.timeout(QUEUE_TIMEOUT):
                await lock.acquire()
                locked = True
                await asyncio.sleep(max(0, 3.0 - (time.monotonic() - last_visit.get(site, 0))))
                await concurrency.acquire()
                admitted = True
        except TimeoutError:
            raise HTTPException(503, "Base browser is busy; try again shortly.") from None
        yield
    finally:
        if admitted:
            concurrency.release()
        if locked:
            lock.release()
HUMAN_CHECKS = ("g-recaptcha", "hcaptcha", "cf-turnstile", "verify you are human", "confirm you are human",
                "checking your browser", "complete the security check", "prove you are human")
AGE_BUTTON = re.compile(r"^(?:yes[,! ]*)?(?:i am|i'm|i confirm i am) (?:over |at least )?(?:18|21)(?:\+| years old)?[.!]?$", re.I)


class Page(BaseModel):
    url: str = Field(max_length=2048)
    settle_ms: int = Field(default=2000, ge=0, le=10000)
    max_ms: int = Field(default=90000, ge=1000, le=150000)


def human_check(html: str) -> bool:
    return any(marker in html.lower() for marker in HUMAN_CHECKS)


async def confirm_age(page, html: str) -> bool:
    # One narrowly identified age button, never a form, login, consent to terms,
    # bot check or general-purpose click instruction from page text.
    if human_check(html) or not re.search(r"(?:age.{0,30}(?:18|21)|(?:over|at least)\s+(?:18|21)|age verification)", html, re.I):
        return False
    buttons = page.get_by_role("button", name=AGE_BUTTON)
    for index in range(min(await buttons.count(), 4)):
        button = buttons.nth(index)
        if await button.is_visible() and not await button.evaluate("el => !!el.closest('form')"):
            await button.click(timeout=10000)
            await page.wait_for_timeout(2000)
            return True
    return False


async def read_pdf(context, url: str, timeout: int) -> dict:
    from pypdf import PdfReader
    for _ in range(8):
        public_url(url)
        response = await context.request.get(url, timeout=timeout, max_redirects=0)
        if response.status in {301, 302, 303, 307, 308}:
            url = urljoin(url, response.headers.get("location", ""))
            continue
        if int(response.headers.get("content-length", "0")) > 10_000_000:
            raise ValueError("PDF too large")
        data = await response.body()
        if len(data) > 10_000_000 or not data.startswith(b"%PDF-"):
            raise ValueError("Unsupported document")
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((page.extract_text() or "") for page in reader.pages[:100])[:300000]
        return {"ok": True, "url": url, "status": response.status, "content_type": "application/pdf",
                "text": text, "html": "<pre>" + html_module.escape(text) + "</pre>", "challenge": False,
                "blocked_by_check": False, "links": []}
    raise ValueError("Too many document redirects")


@app.get("/health")
async def health():
    return {"ok": True, "room": "base"}


@app.post("/render")
async def render(body: Page, x_tank_key: str = Header(default=""), x_tenant_id: str = Header(default=""),
                 x_home_region: str = Header(default=""), x_task_id: str = Header(default="")):
    # x_tank_key is ignored and kept only so existing callers keep their argument
    # order. The gateway no longer sends it; only_the_gateway admits the caller.
    tenant = scope(x_tenant_id, x_home_region)
    try:
        host, _port = public_url(body.url)
    except (ValueError, OSError):
        raise HTTPException(403, "Private or internal web address refused.") from None
    directory = tenant_dir(Path(os.environ.get("BROWSER_DATA_DIR", "/browser-data")), tenant)
    sites = directory / "sites"
    sites.mkdir(exist_ok=True)
    storage = sites / (hashlib.sha256(host.encode()).hexdigest() + ".json")
    from playwright.async_api import async_playwright

    site = host.removeprefix("www.")
    async with render_slot(site):
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                proxy={"server": "http://base-browser-gateway:3128"},
                args=["--disable-quic", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--proxy-bypass-list=<-loopback>"])
            context = None
            result = {"ok": False, "challenge": False}
            try:
                context = await browser.new_context(storage_state=str(storage) if storage.exists() else None,
                    proxy={"server": "http://base-browser-gateway:3128"},
                    service_workers="block", accept_downloads=False)
                denied: set[str] = set()

                async def check(route):
                    try:
                        public_url(route.request.url)
                        if route.request.is_navigation_request() and route.request.method not in {"GET", "HEAD"}:
                            raise ValueError("Forms are not allowed")
                    except (ValueError, OSError):
                        denied.add("private or unsupported request")
                        await route.abort()
                        return
                    await route.continue_()
                await context.route("**/*", check)
                if urlsplit(body.url).path.lower().endswith(".pdf"):
                    result = await read_pdf(context, body.url, body.max_ms)
                else:
                    page = await context.new_page()
                    pdfs = []
                    page.on("response", lambda response: pdfs.append(response.url) if
                        "application/pdf" in response.headers.get("content-type", "") and
                        response.request.resource_type == "document" else None)
                    try:
                        response = await page.goto(body.url, wait_until="domcontentloaded", timeout=body.max_ms)
                    except Exception:
                        if pdfs:
                            result = await read_pdf(context, pdfs[-1], body.max_ms)
                        else:
                            raise
                    else:
                        html = await page.content()
                        challenge = human_check(html) or bool(response and response.status in {401, 403, 429})
                        clicked = False
                        if not challenge:
                            clicked = await confirm_age(page, html)
                            await page.evaluate("window.scrollBy(0, Math.min(document.body.scrollHeight, 900))")
                            await page.wait_for_timeout(body.settle_ms)
                            html = await page.content()
                            challenge = human_check(html) or bool(response and response.status in {401, 403, 429})
                        # Re-check the final location, including client-side redirects.
                        public_url(page.url)
                        links = []
                        if not challenge:
                            for item in await page.locator("a[href]").evaluate_all(
                                "els => els.slice(0,100).map(e => ({text:e.innerText.slice(0,120),url:e.href}))"):
                                try:
                                    public_url(item["url"])
                                except ValueError:
                                    continue
                                links.append(item)
                        result = {"ok": not challenge and bool(response and response.status < 400), "url": page.url, "status": response.status if response else None,
                            "challenge": challenge, "needs_person": "needs a person" if challenge else None,
                            "html": "" if challenge else html[:600000], "blocked_by_check": challenge,
                            "denied_requests": len(denied), "links": links, "age_confirmation": clicked}
                return result
            except Exception:
                raise HTTPException(503, "Base browser could not read this page; no result is claimed.") from None
            finally:
                if context:
                    # Preserve the same identity even when a site asks for a human.
                    await context.storage_state(path=str(storage))
                with (directory / "history.jsonl").open("a") as history:
                    history.write(json.dumps({"time": int(time.time()), "tenant_id": tenant, "task_id": x_task_id,
                        "action": "browser", "host": host, "human_check": bool(result.get("challenge")),
                        "needs_person": "needs a person" if result.get("challenge") else None,
                        "age_confirmation": bool(result.get("age_confirmation")), "ok": result.get("ok", False)}) + "\n")
                last_visit[site] = time.monotonic()
                await browser.close()
