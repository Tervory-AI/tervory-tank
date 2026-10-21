"""Base's careful public-web visitor, with persistent cookies and no bot bypass."""
from __future__ import annotations

import asyncio
import hashlib
import html as html_module
import io
import json
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from brain.evidence import stage
from brain.robots import RobotsDenied, require_allowed
from brain.reader import read_page
from brain.security import authenticate, public_url, scope, tenant_dir

app = FastAPI()
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
    started = time.perf_counter()
    for _ in range(8):
        public_url(url)
        await require_allowed(context, url, min(timeout, 10000))
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
                "title": str((reader.metadata or {}).get("/Title", "")), "pdf_extraction_ms": (time.perf_counter() - started) * 1000,
                "text": text, "html": "<pre>" + html_module.escape(text) + "</pre>", "challenge": False,
                "blocked_by_check": False, "links": [
                    {"text": "PDF link", "url": str(annotation.get_object().get("/A", {}).get("/URI", ""))}
                    for page in reader.pages[:100] for annotation in page.get("/Annots", [])
                    if annotation.get_object().get("/A", {}).get("/URI")], "pdf_data": data}
    raise ValueError("Too many document redirects")


async def rendered_source(page) -> str:
    """Mark computed CSS invisibility while keeping structured data available."""
    return await page.evaluate(r"""() => {
        const copy = document.documentElement.cloneNode(true);
        const rawTextTags = new Set(['NOSCRIPT', 'TEMPLATE', 'IFRAME', 'NOEMBED', 'NOFRAMES', 'XMP']);
        const originals = [document.documentElement, ...document.documentElement.querySelectorAll('*')];
        const clones = [copy, ...copy.querySelectorAll('*')];
        const pageWidth = Math.max(document.documentElement.clientWidth, document.body.clientWidth, innerWidth);
        const pageHeight = Math.max(document.documentElement.clientHeight, document.body.clientHeight, innerHeight);
        const color = text => {
            const match = text.match(/rgba?\(([^)]+)\)/);
            if (!match) return null;
            const parts = match[1].split(',').map(Number);
            return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
        };
        const background = el => {
            let result = [0, 0, 0, 0];
            for (let node = el; node; node = node.parentElement) {
                if (getComputedStyle(node).backgroundImage !== 'none') return null;
                const c = color(getComputedStyle(node).backgroundColor);
                if (!c) continue;
                const alpha = result[3] + c[3] * (1 - result[3]);
                if (alpha) result = [0, 1, 2].map(i => (result[i]*result[3] + c[i]*c[3]*(1-result[3]))/alpha).concat(alpha);
                if (alpha >= 1) break;
            }
            return [0, 1, 2].map(i => result[i]*result[3] + 255*(1-result[3]));
        };

        // WCAG relative luminance, with translucent ink composited over its
        // effective background before measuring contrast.
        const luminance = rgb => {
            const linear = rgb.map(value => {
                const channel = value / 255;
                return channel <= 0.04045 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
            });
            return linear[0]*0.2126 + linear[1]*0.7152 + linear[2]*0.0722;
        };
        const contrast = (ink, bg) => {
            const rendered = ink.slice(0,3).map((value, j) => value*ink[3] + bg[j]*(1-ink[3]));
            const a = luminance(rendered), b = luminance(bg);
            return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        };
        const visibleText = node => {
            const range = document.createRange();
            range.selectNodeContents(node);
            return [...range.getClientRects()].some(rect => {
                let left = Math.max(rect.left, -scrollX), top = Math.max(rect.top, -scrollY);
                let right = Math.min(rect.right, pageWidth-scrollX), bottom = Math.min(rect.bottom, pageHeight-scrollY);
                for (let parent = node.parentElement; parent; parent = parent.parentElement) {
                    const css = getComputedStyle(parent), box = parent.getBoundingClientRect();
                    if (['hidden', 'clip'].includes(css.overflowX)) {
                        left = Math.max(left, box.left + parent.clientLeft);
                        right = Math.min(right, box.left + parent.clientLeft + parent.clientWidth);
                    }
                    if (['hidden', 'clip'].includes(css.overflowY)) {
                        top = Math.max(top, box.top + parent.clientTop);
                        bottom = Math.min(bottom, box.top + parent.clientTop + parent.clientHeight);
                    }
                }
                return right > left && bottom > top;
            });
        };
        originals.forEach((el, i) => {
            // Remove raw-text elements before serialization so embedded closing
            // tags cannot escape a hidden subtree in the downstream parser.
            if (rawTextTags.has(el.tagName)) { clones[i].remove(); return; }
            if (el.closest('head') || el.tagName === 'SCRIPT') return;
            const css = getComputedStyle(el);
            // Contents wrappers have no box; their visible children still do.
            const contents = css.display === 'contents';
            const r = el.getBoundingClientRect();
            const x = r.left + scrollX, y = r.top + scrollY;
            const clipped = (css.clip !== 'auto' || css.clipPath !== 'none');
            const tinyBox = r.width <= 1 && r.height <= 1;
            const hiddenBox = !contents && (r.width <= 0 || r.height <= 0 || x+r.width <= 0 || y+r.height <= 0 || x >= pageWidth || y >= pageHeight || tinyBox);
            const ink = color(css.webkitTextFillColor || css.color), bg = background(el);
            const invisibleInk = ink && (ink[3] === 0 || (bg && contrast(ink, bg) < 1.2));
            // Mark the element's own text without hiding contrasting children.
            // Geometric/CSS invisibility applies to the whole subtree.
            if ((!el.checkVisibility({checkOpacity:true,checkVisibilityCSS:true}) && !contents) || hiddenBox || clipped || el.getAttribute('aria-hidden') === 'true') {
                clones[i].remove();
                return;
            }
            const originalChildren = [...el.childNodes], copiedChildren = [...clones[i].childNodes];
            originalChildren.forEach((node, j) => {
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() &&
                    (parseFloat(css.fontSize) < 4 || invisibleInk || !visibleText(node))) copiedChildren[j].remove();
            });
            if (parseFloat(css.fontSize) < 4 || invisibleInk) {
                clones[i].removeAttribute('itemprop');
                if (clones[i].tagName === 'A') clones[i].removeAttribute('href');
            }
            if (clones[i].tagName === 'A' && clones[i].hasAttribute('href')) clones[i].setAttribute('href', el.href);
        });
        return copy.outerHTML;
    }""")



@app.get("/health")
async def health():
    return {"ok": True, "room": "base"}


@app.post("/render")
async def render(body: Page, x_tank_key: str = Header(default=""), x_tenant_id: str = Header(default=""),
                 x_home_region: str = Header(default=""), x_task_id: str = Header(default="")):
    authenticate(x_tank_key)
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
                    service_workers="block", accept_downloads=False, user_agent="TervoryBase/1.0 (+https://tervory.com)")
                denied: set[str] = set()
                await require_allowed(context, body.url, min(body.max_ms, 10000))

                async def check(route):
                    try:
                        public_url(route.request.url)
                        if route.request.is_navigation_request() and route.request.method not in {"GET", "HEAD"}:
                            raise ValueError("Forms are not allowed")
                    except (ValueError, OSError):
                        denied.add("private or unsupported request")
                        await route.abort()
                        return
                    if route.request.is_navigation_request():
                        try:
                            await require_allowed(context, route.request.url)
                        except RobotsDenied:
                            denied.add('robots.txt')
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
                        result = {"ok": not challenge and bool(response and response.status < 400), "url": page.url, "status": response.status if response else None,
                            "challenge": challenge, "needs_person": "needs a person" if challenge else None,
                            "html": "" if challenge else html[:600000], "blocked_by_check": challenge,
                            "denied_requests": len(denied), "age_confirmation": clicked}
                result['evidence'] = await stage(directory.parent.parent, directory, x_task_id,
                    html=html if result.get('content_type') != 'application/pdf' else '',
                    pdf=result.pop('pdf_data', None), page=page if result.get('content_type') != 'application/pdf' else None)
                # The rendered DOM removes CSS-hidden content before parsing; raw
                # HTML is staged as evidence only, never included in the report.
                extraction_started = time.perf_counter()
                source = result.get("html", "")
                if result.get("content_type") != "application/pdf":
                    source = await rendered_source(page)
                result["page"] = read_page(result.get("url", body.url), source,
                    text=result.get("text"), title=result.get("title", ""), links=result.get("links"), status=result.get("status"),
                    challenge=bool(result.get("challenge")))
                result["page"]["facts"]["age_gate"] |= bool(result.get("age_confirmation"))
                result["page"]["extraction_ms"] = round((time.perf_counter() - extraction_started) * 1000 + result.pop("pdf_extraction_ms", 0), 3)
                result.pop("html", None)
                result.pop("text", None)
                result.pop("links", None)
                return result
            except Exception as exc:
                if isinstance(exc, RobotsDenied) or 'robots.txt' in locals().get('denied', set()):
                    report = read_page(body.url)
                    report['facts']['skip_reason'] = 'robots.txt'
                    result = {'ok': False, 'skipped': True, 'reason': 'robots.txt', 'page': report}
                    return result
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
