"""Base's browser: read public pages; never click or solve a human check."""
from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from brain.security import allowed_hosts, allowed_url, authenticate, scope, tenant_dir

app = FastAPI()
locks: dict[str, asyncio.Lock] = {}
HUMAN_CHECKS = ("g-recaptcha", "hcaptcha", "cf-turnstile", "verify you are human", "confirm you are human", "captcha")


class Page(BaseModel):
    url: str = Field(max_length=2048)
    settle_ms: int = Field(default=1000, ge=0, le=10000)
    max_ms: int = Field(default=25000, ge=1000, le=45000)


def human_check(html: str) -> bool:
    return any(marker in html.lower() for marker in HUMAN_CHECKS)


@app.get("/health")
async def health():
    return {"ok": True, "room": "base"}


@app.post("/render")
async def render(body: Page, x_tank_key: str = Header(default=""), x_tenant_id: str = Header(default=""),
                 x_home_region: str = Header(default=""), x_task_id: str = Header(default="")):
    authenticate(x_tank_key)
    tenant = scope(x_tenant_id, x_home_region)
    hosts = allowed_hosts(os.environ.get("BASE_ALLOWED_HOSTS", ""))
    try:
        allowed_url(body.url, hosts)
    except ValueError:
        raise HTTPException(403, "This host is outside Base's browser allowlist.") from None
    directory = tenant_dir(Path(os.environ.get("BROWSER_DATA_DIR", "/browser-data")), tenant)
    from playwright.async_api import async_playwright

    async with locks.setdefault(tenant, asyncio.Lock()):
        storage = directory / "storage.json"
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True, executable_path="/usr/bin/chromium", proxy={"server": "http://base-browser-gateway:3128"},
                args=["--disable-quic", "--proxy-bypass-list=<-loopback>"])
            try:
                context = await browser.new_context(storage_state=str(storage) if storage.exists() else None,
                                                    service_workers="block", accept_downloads=False)
                denied: set[str] = set()

                async def check(route):
                    try:
                        allowed_url(route.request.url, hosts)
                    except ValueError:
                        denied.add("request outside allowlist")
                        await route.abort()
                        return
                    await route.continue_()

                await context.route("**/*", check)
                page = await context.new_page()
                response = await page.goto(body.url, wait_until="domcontentloaded", timeout=body.max_ms)
                html = await page.content()
                challenge = human_check(html)
                if not challenge:
                    await page.wait_for_timeout(body.settle_ms)
                    html = await page.content()
                    challenge = human_check(html)
                result = {"ok": not challenge, "url": page.url, "status": response.status if response else None,
                          "challenge": challenge, "html": "" if challenge else html[:600000],
                          "blocked_by_check": challenge, "denied_requests": len(denied)}
                if not challenge:
                    await context.storage_state(path=str(storage))
                with (directory / "history.jsonl").open("a") as history:
                    # No query strings, page bodies, cookies or credentials in history.
                    history.write(json.dumps({"time": int(time.time()), "tenant_id": tenant, "task_id": x_task_id,
                        "action": "browser", "host": allowed_url(body.url, hosts), "human_check": challenge}) + "\n")
                return result
            except Exception:
                raise HTTPException(503, "Base browser could not read this page.") from None
            finally:
                await browser.close()
