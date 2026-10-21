"""Base's careful public-web visitor, with persistent cookies and no bot bypass."""
from __future__ import annotations

import asyncio
import base64
import hmac
import uuid
from dataclasses import dataclass
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

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

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
    slot = {"retained": False}
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
        yield slot
    finally:
        if admitted and not slot["retained"]:
            concurrency.release()
        if locked:
            lock.release()
HUMAN_CHECKS = ("g-recaptcha", "hcaptcha", "cf-turnstile", "verify you are human", "confirm you are human",
                "checking your browser", "complete the security check", "prove you are human")
AGE_BUTTON = re.compile(r"^(?:yes[,! ]*)?(?:i am|i'm|i confirm i am) (?:over |at least )?(?:18|21)(?:\+| years old)?[.!]?$", re.I)


class Page(BaseModel):
    url: str = Field(max_length=2048)
    screenshot: bool = False
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
    return {"ok": True, "room": os.environ.get("ACCESS_ROOM", "base")}


@app.post("/render")
async def render(body: Page, x_tank_key: str = Header(default=""), x_tenant_id: str = Header(default=""),
                 x_home_region: str = Header(default=""), x_task_id: str = Header(default="")):
    authenticate(x_tank_key)
    tenant = scope(x_tenant_id, x_home_region)
    if x_task_id:
        try: x_task_id = str(uuid.UUID(x_task_id))
        except ValueError: raise HTTPException(422, "Invalid task identifier.") from None
    try:
        site = site_origin(body.url)
    except (ValueError, OSError):
        raise HTTPException(403, "Private or internal web address refused.") from None
    if os.environ.get("ACCESS_BROWSER_KEY"):
        async with access_locks.setdefault((tenant, site), asyncio.Lock()):
            task = asyncio.current_task()
            active_visits[(tenant, site)] = task
            try:
                return await visit(body, tenant, x_task_id, site)
            finally:
                if active_visits.get((tenant, site)) is task: active_visits.pop((tenant, site), None)
    return await visit(body, tenant, x_task_id, site)


async def visit(body, tenant, task, origin):
    host, _ = public_url(body.url)
    directory = tenant_dir(Path(os.environ.get("BROWSER_DATA_DIR", "/browser-data")), tenant)
    storage = storage_for(tenant, origin)
    secure = bool(os.environ.get("ACCESS_BROWSER_KEY"))
    policy = await access_rpc(tenant, origin, "policy") if secure else {"state": "public"}
    private = policy["state"] != "public"
    if private: storage = storage_for(tenant, origin, authenticated=True)
    social = any(host == name or host.endswith("." + name) for name in ("facebook.com", "instagram.com", "fb.com", "fb.me"))
    if social: storage.unlink(missing_ok=True)
    if private and policy["state"] != "allowed":
        storage.unlink(missing_ok=True)
        for handle, item in list(held.items()):
            if item.tenant == tenant and item.site == origin: await dispose(handle, save=False)
        reason = policy["state"]
        queue = None
        if reason in {"terms_no", "terms_unknown", "rotation_due"}:
            queue = (await access_rpc(tenant, origin, "queue", reason=reason, task_id=task or None))["queue_id"]
        return {"ok": False, "challenge": True, "needs_person": "needs a person", "queue_id": queue,
                "html": "", "login_status": "login failed"}
    for handle, item in list(held.items()):
        if item.tenant == tenant and item.site == origin:
            if not item.ready:
                return {"ok": False, "challenge": True, "needs_person": "needs a person", "html": ""}
            # Consume the page the person handed back, in the same live context.
            html = "" if private else await item.page.content()
            result = {"ok": True, "challenge": False, "html": html[:600000], "url": origin,
                      "human_handled": True, "links": []}
            if private:
                result.update(await portal_result(item.page, policy))
            await dispose(handle)
            return result
    from playwright.async_api import async_playwright
    site = host.removeprefix("www.")
    async with render_slot(site) as slot:
        manager = async_playwright()
        playwright = await manager.__aenter__()
        browser = None
        context = None
        retained = False
        result = {"ok": False, "challenge": False}
        navigation = {"login": False, "human": False}
        try:
            proxy = os.environ.get("BROWSER_PROXY_URL", "http://base-browser-gateway:3128")
            browser = await playwright.chromium.launch(headless=True, executable_path="/usr/bin/chromium",
                proxy={"server": proxy},
                args=["--disable-quic", "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--proxy-bypass-list=<-loopback>"])
            context = await browser.new_context(storage_state=str(storage) if storage.exists() else None,
                proxy={"server": proxy}, viewport={"width": 1280, "height": 900},
                service_workers="block", accept_downloads=False)
            denied: set[str] = set()
            async def check(route):
                try:
                    public_url(route.request.url)
                    target = site_origin(route.request.url)
                    target_host = urlsplit(route.request.url).hostname or ""
                    target_social = any(target_host == name or target_host.endswith("." + name) for name in ("facebook.com", "instagram.com", "fb.com", "fb.me"))
                    if target_social and (navigation["human"] or route.request.method not in {"GET", "HEAD", "OPTIONS"}):
                        raise ValueError("Social pages are anonymous and read-only")
                    if private and target != origin:
                        raise ValueError("Authenticated requests stay on the owning site")
                    # The automated visitor cannot submit a form. Only this
                    # sealed login operation or an authenticated human may do so.
                    if (private or route.request.is_navigation_request()) and route.request.method not in {"GET", "HEAD", "OPTIONS"} and not (navigation["login"] or navigation["human"]):
                        raise ValueError("Forms are not allowed")
                    if navigation["login"] and urlsplit(route.request.url).query:
                        raise ValueError("Login query refused")
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
                    login_needed = private and (not storage.exists() or await page.locator('input[type="password"]').count() > 0 or bool(response and response.status == 401))
                    if login_needed and not human_check(html) and not bool(response and response.status in {403, 429}):
                        success = await login(page, context, tenant, origin, navigation)
                        await access_rpc(tenant, origin, "event", event="logged_in" if success else "login_failed")
                        if success:
                            if (await access_rpc(tenant, origin, "policy"))["state"] != "allowed":
                                raise HTTPException(403, "Connection is no longer available.")
                            result = {"ok": True, "challenge": False, "html": "", "login_status": "logged in", "links": []}
                            return result
                        challenge = True
                        html = await page.content()
                    clicked = False
                    if not challenge:
                        clicked = await confirm_age(page, html)
                        await page.evaluate("window.scrollBy(0, Math.min(document.body.scrollHeight, 900))")
                        await page.wait_for_timeout(body.settle_ms)
                        html = await page.content()
                        challenge = human_check(html) or bool(response and response.status in {401, 403, 429})
                    public_url(page.url)
                    links = []
                    if not challenge and not private:
                        for item in await page.locator("a[href]").evaluate_all(
                            "els => els.slice(0,100).map(e => ({text:e.innerText.slice(0,120),url:e.href}))"):
                            try: public_url(item["url"])
                            except ValueError: continue
                            links.append(item)
                    queue = None
                    if challenge and secure and social:
                        queue = (await access_rpc(tenant, origin, "queue", reason="human_login", task_id=task or None))["queue_id"]
                    if challenge and secure and not social:
                        queue = await retain(tenant, origin, page, context, browser, manager, storage, body.url, task,
                                             "captcha" if human_check(html) else "human_login", navigation, slot)
                        retained = True
                    result = {"ok": not challenge and bool(response and response.status < 400), "url": origin if private else page.url,
                        "status": response.status if response else None, "challenge": challenge,
                        "needs_person": "needs a person" if challenge else None, "queue_id": queue,
                        "html": "" if challenge or private else html[:600000],
                        "blocked_by_check": challenge, "denied_requests": len(denied), "links": links, "age_confirmation": clicked}
            if private and result.get("ok") and not urlsplit(body.url).path.lower().endswith(".pdf"):
                result.update(await portal_result(page, policy))
            if private and urlsplit(body.url).path.lower().endswith(".pdf"):
                result = {"ok": False, "html": "", "login_status": "logged in", "error": "Private documents need a configured data reader."}
            if private and (await access_rpc(tenant, origin, "policy"))["state"] != "allowed":
                storage.unlink(missing_ok=True)
                raise HTTPException(403, "Connection is no longer available.")
            if body.screenshot and not private and not result.get("challenge") and result.get("ok"):
                result["png_base64"] = base64.b64encode(await page.screenshot(type="png")).decode()
            return result
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(503, "The browser could not read this page; no result is claimed.") from None
        finally:
            if not retained:
                try:
                    if context and not social: await context.storage_state(path=str(storage))
                finally:
                    if browser: await browser.close()
                    await manager.__aexit__(None, None, None)
            with (directory / "history.jsonl").open("a") as history:
                history.write(json.dumps({"time": int(time.time()), "tenant_id": tenant,
                    "task_id": str(uuid.UUID(task)) if task else None,
                    "action": "browser", "host": host, "human_check": bool(result.get("challenge")),
                    "needs_person": "needs a person" if result.get("challenge") else None,
                    "age_confirmation": bool(result.get("age_confirmation")), "ok": result.get("ok", False)}) + "\n")
            last_visit[site] = time.monotonic()


# ACCESS-1. The gateway transports ciphertext; it has no copy of this key.
# Credentials never pass through /render, a model, the history file or a URL.
def access_room():
    room = os.environ.get("ACCESS_ROOM", "base")
    if room not in {"base", "tiger"}:
        raise HTTPException(503, "Browser room is not configured.")
    return room


def access_key():
    try:
        raw = base64.urlsafe_b64decode(os.environ.get("ACCESS_BROWSER_KEY", ""))
        if len(raw) != 32: raise ValueError()
        return raw
    except ValueError:
        raise HTTPException(503, "Secure connections are not configured.") from None


def pack(direction, value):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    value = {**value, "at": int(time.time()), "nonce": str(uuid.uuid4())}
    data = AESGCM(access_key()).encrypt(nonce, json.dumps(value).encode(), f"access:browser:{access_room()}:{direction}".encode())
    return {"sealed": base64.urlsafe_b64encode(nonce + data).decode()}


def unpack(direction, value):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        data = base64.urlsafe_b64decode(value["sealed"])
        result = json.loads(AESGCM(access_key()).decrypt(data[:12], data[12:], f"access:browser:{access_room()}:{direction}".encode()))
        uuid.UUID(result["nonce"])
        if abs(time.time() - result["at"]) > 60: raise ValueError()
        return result
    except Exception:
        raise HTTPException(403, "Secure browser request refused.") from None


def site_origin(url):
    host, port = public_url(url)
    scheme = urlsplit(url).scheme
    return scheme + "://" + ("[" + host + "]" if ":" in host else host)


async def access_rpc(tenant, site, action, **values):
    payload = pack("request", {"tenant_id": tenant, "site": site, "action": action, **values})
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(os.environ.get("ACCESS_GATEWAY_URL", "http://base-browser-gateway:3000") + "/access/browser", json=payload)
        if response.status_code != 200: raise ValueError()
        result = unpack("response", response.json())
        if result.get("request_nonce") != unpack("request", payload)["nonce"]: raise ValueError()
        return result
    except Exception:
        raise HTTPException(503, "Secure connections are unavailable.") from None


def storage_for(tenant, site, *, authenticated=False):
    host, _ = public_url(site)
    directory = tenant_dir(Path(os.environ.get("BROWSER_DATA_DIR", "/browser-data")), tenant) / "sites"
    directory.mkdir(exist_ok=True)
    return directory / (hashlib.sha256(site.encode()).hexdigest() + (".auth.json" if authenticated else ".json"))


# Bound to a tenant/site and one actual Playwright page, never a debug socket.
@dataclass
class LivePage:
    tenant: str
    site: str
    page: object
    context: object
    browser: object
    manager: object
    storage: Path
    url: str
    task: str
    navigation: dict
    reserved: bool = False
    ready: bool = False
    timer: object = None


held: dict[str, LivePage] = {}
active_visits: dict[tuple[str, str], asyncio.Task] = {}
access_locks: dict[tuple[str, str], asyncio.Lock] = {}
control_nonces: dict[str, float] = {}


async def dispose(handle, *, save=True):
    item = held.pop(handle, None)
    if not item: return
    if item.timer and item.timer is not asyncio.current_task(): item.timer.cancel()
    try:
        if save: await item.context.storage_state(path=str(item.storage))
    finally:
        try:
            await item.browser.close()
        finally:
            await item.manager.__aexit__(None, None, None)
            if item.reserved: concurrency.release()


async def expire_live(handle):
    await asyncio.sleep(900)
    item = held.get(handle)
    if item:
        async with access_locks.setdefault((item.tenant, item.site), asyncio.Lock()):
            await dispose(handle)
        try:
            await access_rpc(item.tenant, item.site, "event", event="live_expired")
        except HTTPException:
            pass  # Expiry still closes the browser; no credential was used.


async def retain(tenant, site, page, context, browser, manager, storage, url, task, reason, navigation, slot):
    if len(held) >= 4:
        raise HTTPException(503, "All live views are in use; try again shortly.")
    handle = str(uuid.uuid4())
    result = await access_rpc(tenant, site, "queue", reason=reason, handle=handle, task_id=task or None)
    item = LivePage(tenant, site, page, context, browser, manager, storage, url, task, navigation, reserved=True)
    slot["retained"] = True
    held[handle] = item
    item.timer = asyncio.create_task(expire_live(handle))
    return result["queue_id"]


def authenticator(secret):
    # RFC 6238; enrollment was explicitly confirmed by the account owner.
    import struct
    key_bytes = base64.b32decode(secret.upper(), casefold=True)
    digest = hmac.new(key_bytes, struct.pack(">Q", int(time.time()) // 30), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return str((int.from_bytes(digest[offset:offset+4], "big") & 0x7fffffff) % 1000000).zfill(6)


async def login(page, context, tenant, site, navigation):
    grant = await access_rpc(tenant, site, "release")
    if grant["state"] != "allowed": return False
    values = grant.pop("credential")
    config = grant["config"]
    try:
        await page.goto(site + config["login_path"], wait_until="domcontentloaded", timeout=30000)
        if site_origin(page.url) != site or human_check(await page.content()): return False
        # No GET form or cross-origin submit, even when the page asks for one.
        button = page.locator(config["submit_selector"])
        safe_form = await button.evaluate("""el => {const f=el.form || el.closest('form');
            return !!f && f.method.toLowerCase()==='post' && new URL(f.action,location.href).origin===location.origin;}""")
        if not safe_form: return False
        navigation["login"] = True
        await page.locator(config["username_selector"]).fill(values["username"])
        await page.locator(config["password_selector"]).fill(values["password"])
        await button.click(timeout=10000)
        await page.wait_for_timeout(1200)
        if human_check(await page.content()): return False
        code = page.locator(config["totp_selector"])
        if await code.count() and await code.first.is_visible():
            if not values.get("totp"): return False
            await code.first.fill(authenticator(values["totp"]))
            await page.locator(config["submit_selector"]).click(timeout=10000)
            await page.wait_for_timeout(1200)
        return site_origin(page.url) == site and not human_check(await page.content()) and await page.locator(config["success_selector"]).count() > 0
    except Exception:
        return False
    finally:
        navigation["login"] = False
        # Remove credential fields before any human screenshot or content output.
        try:
            for name in ("username_selector", "password_selector", "totp_selector"):
                await page.locator(config[name]).evaluate_all("els=>els.forEach(e=>e.value='')")
        except Exception:
            pass
        values.clear()


async def portal_result(page, policy):
    # Models receive only login status. Tiger may read configured numeric fields
    # with plain code; account details and page HTML never reach a model or gold.
    result = {"html": "", "login_status": "logged in"}
    if access_room() != "tiger": return result
    from decimal import Decimal, InvalidOperation
    config = policy.get("config") or {}
    item = {"currency": "USD", "price": None, "quantity": None}
    try:
        for name in ("price", "quantity"):
            selector = config.get(name + "_selector")
            if selector:
                text = (await page.locator(selector).inner_text()).strip().replace("$", "").replace(",", "")
                amount = Decimal(text)
                if not amount.is_finite() or amount < 0: raise ValueError()
                item[name] = str(amount)
        if item["price"] is not None: result["portal_item"] = item
    except (ValueError, InvalidOperation):
        pass
    return result


@app.post("/access/control")
async def access_control(request: Request):
    raw = await request.body()
    if len(raw) > 20000: raise HTTPException(413, "Request too large.")
    try:
        body = unpack("control", json.loads(raw))
        tenant = str(uuid.UUID(body["tenant_id"]))
        site = site_origin(body["site"])
    except (ValueError, KeyError):
        raise HTTPException(403, "Secure browser request refused.") from None
    now = time.time()
    for nonce, at in list(control_nonces.items()):
        if at < now-120: control_nonces.pop(nonce, None)
    if body["nonce"] in control_nonces: raise HTTPException(409, "Request already used.")
    control_nonces[body["nonce"]] = now
    if body["action"] == "revoke":
        visiting = active_visits.get((tenant, site))
        if visiting and visiting is not asyncio.current_task():
            visiting.cancel()
            await asyncio.gather(visiting, return_exceptions=True)
    async with access_locks.setdefault((tenant, site), asyncio.Lock()):
        result = {}
        if body["action"] == "revoke":
            for handle, item in list(held.items()):
                if item.tenant == tenant and item.site == site: await dispose(handle, save=False)
            storage_for(tenant, site).unlink(missing_ok=True)
            storage_for(tenant, site, authenticated=True).unlink(missing_ok=True)
            result = {"cleared": True}
        elif body["action"] == "live":
            item = held.get(body["handle"])
            if not item or item.tenant != tenant or item.site != site:
                result = {"error": "expired"}
            else:
                value = body["input"]
                action = value["action"]
                item.navigation["human"] = action != "hand_back"
                if action == "click": await item.page.mouse.click(value["x"], value["y"])
                elif action == "key": await item.page.keyboard.press(value["key"])
                elif action == "text": await item.page.keyboard.insert_text(value["text"])
                elif action == "scroll": await item.page.mouse.wheel(0, value["delta"])
                elif action == "hand_back":
                    policy = await access_rpc(tenant, site, "policy")
                    item.ready = not human_check(await item.page.content())
                    if policy["state"] not in {"public", "allowed"}: item.ready = False
                    if policy["state"] == "allowed":
                        marker = (policy.get("config") or {}).get("success_selector", "")
                        item.ready = item.ready and bool(marker) and await item.page.locator(marker).count() > 0
                    if item.ready: await item.context.storage_state(path=str(item.storage))
                    result = {"ready": item.ready}
                elif action not in {"open", "frame"}: raise HTTPException(422, "Unsupported action.")
                if action != "hand_back":
                    result = {"png": base64.b64encode(await item.page.screenshot(type="png")).decode()}
        else:
            raise HTTPException(422, "Unsupported action.")
    return pack("result", {**result, "request_nonce": body["nonce"]})
