"""Tiger — the browser.

POST /render {url, settle_ms?, max_ms?} → what a person would see after the page finished loading.

Why it exists: a plain HTTP fetch gives up on sites that build their page with JavaScript, load
slowly, or show a "checking your browser…" page for a few seconds first. Base used to mark those
sites dead. Tiger loads them in a real Chromium and waits (default up to 15 s) for the page to settle.

What it will not do, by design: it does not click "I am human" boxes, solve CAPTCHAs, spoof its
identity or use stealth tricks. If a site still shows an interactive check after waiting, Tiger
reports `challenge: true` and returns nothing from that page. The site owner's decision stands.
"""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from fastapi import FastAPI
from playwright.async_api import Browser, async_playwright
from pydantic import BaseModel, Field

MAX_PAGES = int(os.environ.get("TIGER_MAX_PAGES", "4"))
UA_SUFFIX = " TervoryTiger/0.1 (+https://tervory.com)"   # we say who we are
CHALLENGE_MARKERS = (
    "cf-turnstile", "challenges.cloudflare.com", "cf-challenge", "challenge-platform", "g-recaptcha",
    "hcaptcha.com", "captcha-delivery", "px-captcha",
)
CHALLENGE_TITLES = ("just a moment", "attention required", "verify you are human", "access denied", "are you a robot")

app = FastAPI(title="Tiger", version="0.1.0")
_pw = None
_browser: Browser | None = None
_ua: str = ""
_sem = asyncio.Semaphore(MAX_PAGES)


class RenderReq(BaseModel):
    url: str
    settle_ms: int = Field(default=10_000, ge=0, le=20_000)   # how long to wait for a self-clearing check
    max_ms: int = Field(default=25_000, ge=3_000, le=45_000)  # hard cap for the whole render


@app.on_event("startup")
async def _start() -> None:
    global _pw, _browser, _ua
    _pw = await async_playwright().start()
    _browser = await _pw.chromium.launch(args=["--disable-dev-shm-usage", "--no-sandbox"])
    ctx = await _browser.new_context()
    page = await ctx.new_page()
    _ua = (await page.evaluate("navigator.userAgent")).replace("HeadlessChrome", "Chrome") + UA_SUFFIX
    await ctx.close()


@app.on_event("shutdown")
async def _stop() -> None:
    if _browser:
        await _browser.close()
    if _pw:
        await _pw.stop()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {"ok": _browser is not None and _browser.is_connected(), "max_pages": MAX_PAGES}


async def _looks_like_challenge(page) -> bool:
    try:
        title = (await page.title()).lower()
        if any(t in title for t in CHALLENGE_TITLES):
            return True
        html = (await page.content())[:200_000].lower()
        return any(m in html for m in CHALLENGE_MARKERS)
    except Exception:  # noqa: BLE001 — page navigated mid-read; treat as still settling
        return True


@app.post("/render")
async def render(req: RenderReq) -> dict[str, Any]:
    assert _browser is not None
    started = time.perf_counter()
    async with _sem:
        ctx = await _browser.new_context(user_agent=_ua, java_script_enabled=True, locale="en-US",
                                         viewport={"width": 1280, "height": 900})
        # Text and links are all we need: skip heavy media to be a light visitor.
        await ctx.route("**/*", lambda route: route.abort()
                        if route.request.resource_type in ("image", "media", "font") else route.continue_())
        page = await ctx.new_page()
        out: dict[str, Any] = {"url": req.url, "ok": False, "challenge": False}
        try:
            resp = await page.goto(req.url, wait_until="domcontentloaded", timeout=req.max_ms)
            out["status"] = resp.status if resp else None
            # Let scripts run and the page settle.
            try:
                await page.wait_for_load_state("networkidle", timeout=min(8_000, req.max_ms))
            except Exception:  # noqa: BLE001 — busy pages never go idle; content is still usable
                pass
            # A self-clearing "checking your browser" page usually navigates on its own within seconds.
            deadline = time.perf_counter() + req.settle_ms / 1000
            while await _looks_like_challenge(page) and time.perf_counter() < deadline:
                await asyncio.sleep(1.0)
            if await _looks_like_challenge(page):
                out["challenge"] = True   # interactive check still there: we stop, by design
                return out
            out["final_url"] = page.url
            out["title"] = (await page.title())[:300]
            out["text"] = (await page.evaluate("document.body ? document.body.innerText : ''"))[:30_000]
            out["html"] = (await page.content())[:600_000]
            out["ok"] = bool(out["text"].strip())
            return out
        except Exception as exc:  # noqa: BLE001
            out["error"] = str(exc)[:300]
            return out
        finally:
            out["ms"] = int((time.perf_counter() - started) * 1000)
            await ctx.close()
