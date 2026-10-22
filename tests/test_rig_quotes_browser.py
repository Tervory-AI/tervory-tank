"""Built UMD -> real Rig API -> neutral catalogue and recording quote sender."""

import asyncio
import os
from pathlib import Path
import socket
import subprocess
import sys

import httpx
import pytest
import pytest_asyncio

ROOT = Path(__file__).resolve().parents[1]


@pytest_asyncio.fixture
async def widget_server(tmp_path):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    process_env = {**os.environ, "PYTHONPATH": str(ROOT / "agents" / "rig"),
                   "RIG_SAMPLE_ORIGIN": base, "RIG_WIDGET_PUBLISHABLE_KEY": "rk_pub_neutral_sample"}
    process_env.pop("RIG_WIDGET_DIR", None)
    with (tmp_path / "server.log").open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "rigbox.quotes.sample:app",
            "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
            cwd=ROOT, env=process_env, stdout=log, stderr=log)
        try:
            async with httpx.AsyncClient(trust_env=False) as client:
                for _ in range(100):
                    if process.poll() is not None:
                        pytest.fail("Sample API exited during startup")
                    try:
                        if (await client.get(base + "/health")).status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    await asyncio.sleep(0.1)
                else:
                    pytest.fail("Sample API did not become ready")
            yield base
        finally:
            process.terminate()
            process.wait(timeout=10)


@pytest.mark.asyncio
@pytest.mark.parametrize("width", [390, 1440])
async def test_built_widget_live_api_journey(real_chromium, widget_server, tmp_path, width):
    from playwright.async_api import expect

    output = Path(os.environ.get("RIG_SCREENSHOT_DIR", str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    page = await real_chromium.new_page(viewport={"width": width, "height": 900})
    failures = []
    page.on("pageerror", lambda error: failures.append(str(error)))
    # Only local API and static bundle traffic. Samples have no remote images/fonts.
    await page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(widget_server + "/")
                     else route.abort())

    async def capture(name):
        await page.locator("tervory-rig").screenshot(path=str(output / f"rig4-{name}-{width}.png"))
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")

    await page.goto(widget_server + "/widget/test")
    await expect(page.get_by_role("heading", name="Find it. We source it.")).to_be_visible()
    await capture("01-search")
    await page.get_by_role("searchbox").fill("Core One")
    await page.get_by_role("button", name="Search", exact=True).click()
    await expect(page.get_by_role("heading", name="Core One", exact=True)).to_be_visible()
    await expect(page.get_by_text("SAMPLE DATA").first).to_be_visible()
    await capture("02-results")
    await page.get_by_role("button", name="Complete my setup", exact=True).click()
    await expect(page.get_by_text("R 120", exact=True)).to_be_visible()
    await capture("03-setup")
    await page.get_by_role("button", name="Swap ⇄", exact=True).click()
    await page.get_by_role("button", name="Part Beta", exact=True).click()
    await expect(page.get_by_text("R 130", exact=True)).to_be_visible()
    assert "Unapproved Part" not in await page.locator("tervory-rig").inner_text()
    await capture("03-swap")
    await page.get_by_role("searchbox").fill("zzzzzzzzzzzzzz")
    await page.get_by_role("button", name="Search", exact=True).click()
    await expect(page.locator("#link-url")).to_be_visible()
    await capture("04-missing")
    await page.locator("#link-url").fill("https://example.com/item")
    await page.locator("#link-name").fill("Sample Shopper")
    await page.locator("#link-email").fill("sample@example.com")
    await page.get_by_role("button", name="Request a quote", exact=True).click()
    await expect(page.get_by_text("Request received. Reference", exact=False)).to_be_visible()
    await page.get_by_role("searchbox").fill("Core One")
    await page.get_by_role("button", name="Search", exact=True).click()
    await page.get_by_role("button", name="Explore", exact=True).click()
    await expect(page.get_by_role("heading", name="Core One", exact=True)).to_be_visible()
    await expect(page.get_by_text("R 120", exact=True)).to_be_visible()
    await capture("05-explore")
    await page.locator("#ask-q").fill("What fits this product?")
    await page.get_by_role("button", name="Ask", exact=True).click()
    await expect(page.locator(".answer")).to_contain_text("I don't know")
    await page.get_by_role("button", name="Request a quote for this setup →", exact=True).click()
    await page.locator("#quote-name").fill("Sample Shopper")
    await page.locator("#quote-email").fill("sample@example.com")
    await page.get_by_role("button", name="Send request", exact=True).click()
    await expect(page.get_by_text("Request received. Reference", exact=False)).to_be_visible()
    await capture("quote")
    assert not failures
    await page.close()
