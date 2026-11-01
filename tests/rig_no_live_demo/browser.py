"""Local browser proof of the actual v5 routes and Rig Workspace components.

Offline data only. Not founder-session or deployed-site proof. No sign-in,
production settings, model calls, widget changes or live data writes.
"""

from __future__ import annotations

async def load_catalogue(service, folder):
    from rig_fixture_loader import load_catalogue as load
    return await load(service, folder)


import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from playwright.async_api import async_playwright, expect
import uvicorn

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "agents/rig"), str(ROOT / "agents/_chassis")]
from rigbox.api import mount  # noqa: E402
from rigbox.page_route import mount_page  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402


async def main():
    output = Path(
        os.environ.get("RIG_SCREENSHOT_DIR", Path(__file__).parent / "evidence")
    )
    output.mkdir(parents=True, exist_ok=True)
    service = Service(MemoryStore())
    # Existing saved catalogue, explicitly loaded only by this offline harness.
    await load_catalogue(service, ROOT / "tests/fixtures/rig_catalogues/customnation")
    config = json.loads(
        (ROOT / "tests/fixtures/rig_catalogues/customnation/publish.json").read_text()
    )
    tenant = config["tenant_id"]
    app = FastAPI()
    app.state.rig = service
    mount(app)
    mount_page(app)
    requests = []
    errors = []
    with tempfile.TemporaryDirectory(prefix="rig-empty-proof-") as temp:
        bundle = Path(temp) / "workspace.js"
        subprocess.run(
            ["node", str(Path(__file__).with_name("bundle.cjs")), str(bundle)],
            check=True,
            cwd=ROOT,
        )

        @app.get("/local-workspace")
        async def workspace():
            return HTMLResponse(
                '<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">'
                '<link rel="stylesheet" href="/local-globals.css"><link rel="stylesheet" href="/local-fonts.css">'
                '<link rel="stylesheet" href="/local-rig.css"></head><body style="margin:0">'
                '<main><div id="root"></div></main><script src="/local-workspace.js"></script></body></html>'
            )

        @app.get("/local-workspace.js")
        async def script():
            return FileResponse(bundle, media_type="text/javascript")

        @app.get("/local-rig.css")
        async def css():
            return FileResponse(
                ROOT / "workspace/app/rig/rig.css", media_type="text/css"
            )

        @app.get("/local-globals.css")
        async def globals_css():
            return FileResponse(
                ROOT / "workspace/app/globals.css", media_type="text/css"
            )

        @app.get("/local-fonts.css")
        async def fonts_css():
            return Response(
                "@font-face{font-family:Inter;src:url(/local-fonts/Inter-latin.woff2);font-weight:100 900}"
                "@font-face{font-family:Jost;src:url(/local-fonts/Jost-300-latin.woff2);font-weight:300}"
                ":root{--font-inter:Inter;--font-jost:Jost;--font-mono:monospace}",
                media_type="text/css",
            )

        @app.get("/local-fonts/{name}")
        async def font(name: str):
            assert name in {"Inter-latin.woff2", "Jost-300-latin.woff2"}
            return FileResponse(ROOT / "workspace/app/fonts" / name)

        @app.get("/brand/{name}")
        async def brand(name: str):
            path = ROOT / "workspace/public/brand" / name
            assert path.parent == ROOT / "workspace/public/brand"
            return FileResponse(path)

        @app.post("/rig/api/rig")
        async def rig_call(request: Request):
            data = await request.json()
            requests.append(data)
            if data["op"] == "search":
                return await service.search(tenant, data["q"], 12)
            if data["op"] == "graph":
                return await service.graph(tenant, data["id"])
            raise AssertionError(data)

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )
        task = asyncio.create_task(server.serve())
        while not server.started:
            await asyncio.sleep(0.05)
        origin = f"http://127.0.0.1:{port}"
        # The empty host must not borrow even the explicitly loaded offline tenant.
        old_key = os.environ.pop("RIG_WIDGET_PUBLISHABLE_KEY", None)
        try:
            async with async_playwright() as pw:
                chrome = await pw.chromium.launch(
                    executable_path=os.environ.get(
                        "READ1_CHROMIUM_EXECUTABLE", "/usr/bin/chromium"
                    ),
                    args=["--no-sandbox"],
                )
                context = await chrome.new_context()
                await context.route(
                    "**/*",
                    lambda route: route.continue_()
                    if route.request.url.startswith(origin)
                    else route.abort(),
                )
                page = await context.new_page()
                page.on("pageerror", lambda error: errors.append(str(error)))
                network = []
                page.on("request", lambda request: network.append(request.url))
                for path in ["/", "/v5", "/v5/cn", "/?q=Archon%20Type%20B"]:
                    await page.goto(origin + path, wait_until="networkidle")
                    text = await page.locator("body").inner_text()
                    assert not any(
                        word in text.lower() for word in ["archon", "demo", "sample"]
                    )
                    assert not await page.locator("#stage").is_visible()
                    assert not await page.locator("#idk").is_visible()
                    assert await page.locator("#footCount").inner_text() == ""
                    assert await page.locator(".chip:visible").count() == 0
                assert not any(
                    "/v1/rig/" in url or "sample-suppliers" in url for url in network
                )
                await page.goto(origin + "/", wait_until="networkidle")
                for width in [1440, 390]:
                    await page.set_viewport_size({"width": width, "height": 1000})
                    await page.screenshot(
                        path=str(output / f"local-rig-empty-{width}.png"),
                        full_page=True,
                    )
                print(
                    "PASS v5 root and both skins: no fixture requests, no demo text, no results, counts or chips without a published store",
                    flush=True,
                )
                await page.set_viewport_size({"width": 1440, "height": 1000})
                await page.goto(origin + "/local-workspace", wait_until="networkidle")
                await page.locator(".search-view").wait_for()
                await page.evaluate("document.fonts.ready")
                assert requests == []
                assert await page.locator(".search-main").inner_text() == ""
                assert await page.locator(".results-line").inner_text() == ""
                assert await page.locator(".thread").inner_text() == ""
                assert await page.locator(".build-wrap").count() == 0
                await expect(
                    page.get_by_placeholder(
                        "Search a brand, model or part, like LumaWorks"
                    )
                ).to_have_value("")
                for width in [1440, 390]:
                    await page.set_viewport_size({"width": width, "height": 1000})
                    await page.screenshot(
                        path=str(output / f"local-workspace-empty-{width}.png"),
                        full_page=True,
                    )
                await page.set_viewport_size({"width": 1440, "height": 1000})
                for tab in [
                    "Overview",
                    "Catalogues",
                    "Fits to review",
                    "Skins",
                    "Progress",
                ]:
                    await (
                        page.locator('nav[aria-label="Rig"]')
                        .get_by_role("button", name=tab, exact=True)
                        .click()
                    )
                    text = await page.locator(".body").inner_text()
                    assert not any(
                        word in text.lower()
                        for word in [
                            "archon",
                            "demo",
                            "stand-in",
                            "sample",
                            "saved 17 oct",
                            "lumaworks",
                            "holosun",
                        ]
                    )
                    assert not await page.locator(
                        ".counts b"
                    ).all_text_contents() or not any(
                        await page.locator(".counts b").all_text_contents()
                    )
                    assert await page.locator(".pill:visible").count() == 0
                print(
                    "PASS Workspace starts empty: no startup search, products, parts, added items, opening conversation, demo decisions or invented counts on any tab",
                    flush=True,
                )
                await (
                    page.locator('nav[aria-label="Rig"]')
                    .get_by_role("button", name="Search", exact=True)
                    .click()
                )
                await page.evaluate("window.renderRig(18, 9)")
                assert requests == []
                await page.get_by_placeholder(
                    "Search a brand, model or part, like LumaWorks"
                ).fill("LumaWorks")
                await page.locator("form.search-bar button").click()
                await expect(page.locator(".pistols")).to_contain_text("LumaWorks C2")
                await expect(page.locator(".upgrades")).to_be_visible()
                assert await page.locator(".pill-btn").count() == 0
                assert [row["op"] for row in requests] == ["search", "graph"]
                # The recorded graph must have been fetched, not filled from C2_PARTS.
                assert requests[1]["id"] == "STI-C2-9"
                await page.get_by_placeholder(
                    "Search a brand, model or part, like LumaWorks"
                ).fill("nothing matches zzz")
                await page.locator("form.search-bar button").click()
                await expect(page.locator(".pistols")).to_have_count(0)
                assert await page.locator(".results-line").inner_text() == ""
                print(
                    "PASS submitted Workspace search uses the stored catalogue and graph; nothing is pre-added; a no-result search stays empty",
                    flush=True,
                )
                assert errors == [], errors
                await chrome.close()
        finally:
            if old_key is not None:
                os.environ["RIG_WIDGET_PUBLISHABLE_KEY"] = old_key
            server.should_exit = True
            await task


if __name__ == "__main__":
    asyncio.run(main())
