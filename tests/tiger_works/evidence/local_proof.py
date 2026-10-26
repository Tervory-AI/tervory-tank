"""Local fixture proof, never a production auth bypass.

Run from the repository: PYTHONPATH=tank:tests python tests/tiger_works/evidence/local_proof.py
Requires Workspace npm dependencies, Node 22 and Playwright Chromium.
Only a temporary Workspace copy replaces Clerk with a local identity. Actual
server actions, tenant derivation, Tank proxy routes and Tiger handlers run.
MemoryStore replaces Postgres; fixture checks replace the scheduled job trigger.
The rendered DOM, price extraction, history and alerts use production code.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import socket
import tempfile
import uuid

import httpx
from playwright.async_api import async_playwright
import uvicorn

from test_tg2_tiger_watchlist import ROOT  # sets offline Tank configuration
from test_agent1_isolation import browser
from test_tiger import _load
from tiger_works.fixture import LABEL, URL, extract, no_paid_call, robots_fixture, saved_page
from watch import DomainLimiter, MemoryStore, run_check
import main as tank


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


CLIENT = '''"use client";
export function ClerkProvider({ children }) { return children; }
export function SignedIn({ children }) { return children; }
export function SignedOut() { return null; }
export function UserButton() { return null; }
export function OrganizationSwitcher() { return null; }
export function useAuth() { return { isLoaded: true, userId: "local_fixture_user" }; }
'''
SERVER = '''export async function auth() {
  return { userId: "local_fixture_user", orgId: "org_tiger_local_fixture", orgRole: "org:member" };
}
export async function clerkClient() {
  return { organizations: { getOrganization: async () => ({ name: "local, fixture page" }) } };
}
export async function currentUser() { return null; }
export function clerkMiddleware(callback) { return request => callback(auth, request); }
export function createRouteMatcher() { return () => false; }
'''


async def ready(url: str, process=None) -> None:
    async with httpx.AsyncClient(trust_env=False) as client:
        for _ in range(180):
            if process and process.returncode is not None:
                raise RuntimeError("Local Workspace exited; see workspace.log")
            try:
                response = await client.get(url, timeout=2)
                if response.status_code < 500:
                    return
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    raise RuntimeError("Local proof server did not start")


async def main() -> None:
    output = Path(os.environ.get("TIGER_PROOF_DIR", ROOT / "tests/tiger_works/evidence/proof")).resolve()
    output.mkdir(parents=True, exist_ok=True)
    store = MemoryStore()
    tiger = _load("tiger_local_proof", ROOT / "agents/tiger/app.py")
    tiger._store = lambda: store
    room_client = httpx.AsyncClient(transport=httpx.ASGITransport(app=tiger.app))
    tank._http = room_client
    tank_port, workspace_port = free_port(), free_port()
    # Serve the actual Tank app. Only infrastructure startup is omitted because
    # this fixture harness provides the room HTTP transport and MemoryStore.
    service = uvicorn.Server(uvicorn.Config(tank.app, host="127.0.0.1", port=tank_port,
                                          log_level="warning", lifespan="off"))
    server_task = asyncio.create_task(service.serve())
    origin = f"http://localhost:{workspace_port}"
    process = None
    os.environ["ACCESS_ROOM"] = "tiger"
    try:
        with tempfile.TemporaryDirectory(prefix="tiger-local-", dir="/tmp") as temp:
            local = Path(temp) / "workspace"
            shutil.copytree(ROOT / "workspace", local, ignore=shutil.ignore_patterns("node_modules", ".next", ".env*", "*.tsbuildinfo"))
            (local / "node_modules").symlink_to(ROOT / "workspace/node_modules", target_is_directory=True)
            (local / "fixture-clerk-client.js").write_text(CLIENT)
            (local / "fixture-clerk-server.js").write_text(SERVER)
            (local / "next.config.ts").write_text('''import path from "node:path";
export default { devIndicators: false, webpack(config) {
  config.resolve.alias["@clerk/nextjs$"] = path.resolve("fixture-clerk-client.js");
  config.resolve.alias["@clerk/nextjs/server$"] = path.resolve("fixture-clerk-server.js");
  return config;
} };
''')
            env = {**os.environ, "TANK_URL": f"http://127.0.0.1:{tank_port}", "TANK_API_KEY": tank.TANK_API_KEY,
                   "NEXT_TELEMETRY_DISABLED": "1", "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY": "pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA==",
                   "CLERK_SECRET_KEY": "sk_test_dummy"}
            with (output / "workspace.log").open("w") as log:
                process = await asyncio.create_subprocess_exec("node", str(local / "node_modules/next/dist/bin/next"), "dev",
                    "--hostname", "localhost", "--port", str(workspace_port), cwd=local, env=env,
                    stdout=log, stderr=asyncio.subprocess.STDOUT)
                await ready(origin + "/tiger", process)
                async with async_playwright() as playwright:
                    chromium = await playwright.chromium.launch(executable_path=os.environ.get("READ1_CHROMIUM_EXECUTABLE", "/usr/bin/chromium"), args=["--no-sandbox"])
                    context = await chromium.new_context(viewport={"width": 1440, "height": 1050})
                    async def local_only(route):
                        if route.request.url.startswith(origin):
                            await route.continue_()
                        else:
                            await route.abort()
                    await context.route("**/*", local_only)
                    page = await context.new_page()
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    async def shot(name):
                        # Every image explicitly identifies the proof's scope.
                        await page.evaluate('''() => {
                          document.getElementById('fixture-proof-label')?.remove();
                          const label = document.createElement('div'); label.id = 'fixture-proof-label';
                          label.textContent = 'local, fixture page';
                          label.style.cssText = 'position:fixed;bottom:12px;right:12px;z-index:99999;background:#001840;color:white;padding:10px 16px;font:16px sans-serif';
                          document.body.append(label);
                        }''')
                        await page.screenshot(path=str(output / name), full_page=True)
                    async def search_count(query, expected):
                        field = page.get_by_role("textbox", name="Search watched products, reads and alerts")
                        await field.fill(query)
                        await field.press("Enter")
                        await page.get_by_text(expected + " in your watched products, reads and alerts.", exact=True).wait_for()
                        await page.get_by_role("button", name="Clear", exact=True).click()
                    await page.goto(origin + "/tiger?tab=watch")
                    await page.get_by_text("No products watched yet.").wait_for()
                    assert await page.get_by_role("button", name="Ask Tiger", exact=True).count() == 0
                    assert await page.get_by_text("Next page →", exact=True).count() == 0
                    await shot("01-empty.png")
                    await search_count("no matching fixture", "0 matches")
                    await page.get_by_role("button", name="Alerts", exact=True).click()
                    await page.get_by_text("0 alerts", exact=True).wait_for()
                    assert await page.get_by_role("button", name="Last 7 days ▾", exact=True).count() == 0
                    assert await page.get_by_role("button", name="Load older alerts", exact=True).count() == 0
                    await page.get_by_role("button", name="Watch list", exact=True).click()
                    await page.get_by_role("button", name="Add a product", exact=True).click()
                    await page.locator('input[name="url"]').fill(URL)
                    await page.locator('input[name="label"]').fill(LABEL)
                    await page.locator('select[name="every"]').select_option("1h")
                    await page.locator('input[name="price"]').check()
                    await page.locator('input[name="stock"]').uncheck()
                    await page.get_by_role("button", name="Start watching", exact=True).click()
                    await page.get_by_text("Not checked", exact=True).wait_for()
                    assert len(store.watches) == 1
                    watch = store.watches[0]
                    assert watch["alert_price"] and not watch["alert_stock"]
                    await shot("02-watch-added.png")
                    await search_count("Not checked", "1 match")
                    # Old Ask links must land on a usable tab, without a question
                    # box or a promise of answers that the page cannot provide.
                    await page.goto(origin + "/tiger?tab=ask")
                    await page.get_by_role("heading", name="Latest reads", exact=True).wait_for()
                    assert await page.get_by_role("textbox", name="Ask Tiger", exact=True).count() == 0
                    assert "Every answer lists its sources" not in await page.locator("body").inner_text()
                    assert "Checked Not yet" not in await page.locator("body").text_content()
                    await page.set_viewport_size({"width": 390, "height": 844})
                    await page.get_by_text("Not checked yet", exact=True).wait_for()
                    await shot("08-not-checked.png")
                    await page.set_viewport_size({"width": 1440, "height": 1050})
                    reader_context = await chromium.new_context(java_script_enabled=False)
                    await reader_context.route("**/*", lambda route: route.abort())
                    reader_page = await reader_context.new_page()
                    async def check(price):
                        html = saved_page(price)
                        await reader_page.set_content(html)
                        result = await browser.public_result(reader_page, {"ok": True, "url": URL}, html,
                            Path(temp), str(uuid.uuid4()), price_reader=True)
                        async def render(*args):
                            return result
                        observed = await run_check(store, watch["tenant_id"], watch, "tiger", render,
                            extract, no_paid_call, robots_fixture, DomainLimiter(0))
                        assert observed["price"] == price + ".00"
                    await check("120")
                    await page.goto(origin + "/tiger")
                    await page.get_by_text("$120.00", exact=True).first.wait_for()
                    await page.get_by_text("Watched product", exact=True).wait_for()
                    await search_count("$120.00", "2 matches")
                    await shot("03-first-reading.png")
                    await check("115")
                    await check("115")
                    assert len(store.observations) == 3 and len(store.alerts) == 1
                    await page.goto(origin + "/tiger?tab=history")
                    await page.get_by_text("$115.00", exact=True).first.wait_for()
                    assert await page.locator("tbody tr").count() == 3
                    assert await page.get_by_text("$120.00", exact=True).count() == 1
                    await shot("04-history.png")
                    await page.goto(origin + "/tiger?tab=alerts")
                    await page.get_by_text("1 alert", exact=True).wait_for()
                    assert await page.get_by_role("button", name="Last 7 days ▾", exact=True).count() == 0
                    assert await page.get_by_role("button", name="Load older alerts", exact=True).count() == 0
                    await page.get_by_role("button", name="Stock", exact=True).click()
                    await page.get_by_text("0 alerts", exact=True).wait_for()
                    assert await page.locator("tbody tr").count() == 0
                    await page.get_by_role("button", name="Price", exact=True).click()
                    await page.get_by_text("1 alert", exact=True).wait_for()
                    await page.get_by_role("button", name="All", exact=True).click()
                    await shot("05-alert.png")
                    (output / "observations.json").write_text(json.dumps({"scope": "local, fixture page", "watch": watch,
                        "observations": store.observations, "alerts": store.alerts}, indent=2, default=str) + "\n")
                    await page.goto(origin + "/tiger")
                    await page.get_by_text("Change today", exact=True).wait_for()
                    await check("110")
                    await page.goto(origin + "/tiger?tab=alerts")
                    await page.get_by_text("2 alerts", exact=True).wait_for()
                    await shot("06-two-alerts.png")
                    await page.goto(origin + "/tiger")
                    await page.get_by_text("Changes today", exact=True).wait_for()

                    # A saved refusal page produces an actual blocked observation,
                    # then Tank/Tiger's read routes supply the Can't-read row.
                    blocked_html = (ROOT / "tests/fixtures/uncitral/cloudfront-blocked.html").read_text()
                    await reader_page.set_content(blocked_html)
                    blocked = await browser.public_result(reader_page,
                        {**browser.blocked_result(URL), "status": 403}, blocked_html,
                        Path(temp), str(uuid.uuid4()), price_reader=True)
                    async def blocked_render(*args): return blocked
                    observed = await run_check(store, watch["tenant_id"], watch, "tiger", blocked_render,
                        no_paid_call, no_paid_call, no_paid_call, DomainLimiter(0))
                    assert observed["status"] == "blocked" and observed["alerts"] == []
                    await page.goto(origin + "/tiger?tab=unread")
                    try:
                        await page.get_by_role("columnheader", name="Page", exact=True).wait_for(timeout=10000)
                    except Exception:
                        await shot("failed.png")
                        (output / "failed.html").write_text(await page.content())
                        raise
                    link = page.get_by_role("link", name="www.adafruit.com", exact=True)
                    assert await link.get_attribute("href") == URL
                    assert await link.get_attribute("title") == URL
                    assert await page.get_by_role("button", name="Check again", exact=True).count() == 0
                    await shot("07-cant-read.png")
                    (output / "review2-observations.json").write_text(json.dumps({"scope": "local, fixture page", "watch": watch,
                        "observations": store.observations, "alerts": store.alerts}, indent=2, default=str) + "\n")
                    assert not errors, errors
                    await chromium.close()
            print(f"PASS: form → Tank → Tiger → 3 saved-page readings → 1 alert; screenshots: {output}")
            print("PASS: 0/1/2 alert and search counts, overview grammar, blocked row Page link, no inactive retry button")
            print("PASS: actual Tank app; inactive date/load/paging/Ask controls removed; legacy Ask link and Not checked yet card")
    finally:
        if process and process.returncode is None:
            process.terminate()
            await process.wait()
        service.should_exit = True
        await server_task
        await room_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
