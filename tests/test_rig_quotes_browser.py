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
    process_env = {**os.environ, "PYTHONPATH": os.pathsep.join(str(ROOT / "agents" / part) for part in ("rig", "_chassis")),
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
    # API, bundle and licensed fonts must all work on the local origin.
    await page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(widget_server + "/")
                     else route.abort())

    async def capture(name):
        await page.evaluate("document.fonts.ready")
        await page.locator("tervory-rig").screenshot(path=str(output / f"rig4b-{name}-{width}.png"))
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        assert await page.locator("tervory-rig").evaluate("el => el.shadowRoot.querySelector('.shell').scrollWidth <= el.clientWidth + 1")

    await page.goto(widget_server + "/widget/test")
    await expect(page.get_by_role("heading", name="Find it. We source it.")).to_be_visible()
    await capture("01-search")
    assert await page.evaluate("document.fonts.load('600 32px \"Barlow Condensed\"').then(fonts => fonts.length > 0)")
    assert await page.evaluate("document.fonts.check('600 32px \"Barlow Condensed\"')")
    await page.get_by_role("searchbox").fill("Core")
    await page.get_by_role("button", name="Search", exact=True).click()
    await expect(page.get_by_role("heading", name="Core One", exact=True)).to_be_visible()
    await expect(page.get_by_text("SAMPLE DATA", exact=True)).to_have_count(0)
    await expect(page.locator(".card")).to_have_count(3)
    await page.locator(".card").filter(has=page.get_by_role("heading", name="Core One", exact=True)).get_by_role("button", name="Complete my setup", exact=True).click()
    await expect(page.get_by_text("R 120", exact=True)).to_be_visible()
    await expect(page.locator(".setup")).to_have_count(3)
    await expect(page.get_by_text("Most chosen", exact=True)).to_be_visible()
    await expect(page.locator(".chosen-note")).to_contain_text("We matched")
    await expect(page.locator(".chosen button")).to_have_count(0)
    await expect(page.get_by_text("SAMPLE DATA", exact=True)).to_have_count(0)
    await capture("03-setup")
    essential = page.locator(".setup").first
    await essential.get_by_role("button", name="Swap ⇄", exact=True).click()
    await essential.get_by_role("button", name="Part Beta", exact=True).click()
    await expect(essential.get_by_text("R 130", exact=True)).to_be_visible()
    assert "Unapproved Part" not in await page.locator(".shell").text_content()
    await capture("03-swap")
    await page.get_by_role("searchbox").fill("Core")
    await page.get_by_role("button", name="Search", exact=True).click()
    await expect(page.get_by_role("button", name="Selected ✓", exact=True)).to_be_visible()
    await capture("02-results")
    await page.get_by_role("searchbox").fill("zzzzzzzzzzzzzz")
    await page.get_by_role("button", name="Search", exact=True).click()
    await expect(page.locator("#link-url")).to_be_visible()
    labels = await page.locator(".link-form label").evaluate_all("""labels => labels.map(label => {
        const style = getComputedStyle(label.querySelector('span') ?? label);
        return [style.fontSize, style.fontWeight, style.color].join('|');
    })""")
    assert len(labels) == 4 and len(set(labels)) == 1
    await capture("04-missing")
    await page.locator("#link-url").fill("https://example.com/item")
    await page.locator("#link-name").fill("Sample Shopper")
    await page.get_by_role("button", name="Request a quote", exact=True).click()
    await expect(page.locator("#link-email-error")).to_have_text("Enter your email address.")
    await expect(page.locator("#link-phone-error")).to_have_text("Enter your phone number.")
    await expect(page.locator("#link-email")).to_be_focused()
    await capture("04-missing-errors")
    await page.locator("#link-email").fill("not-an-email")
    await page.locator("#link-phone").fill("123")
    await page.get_by_role("button", name="Request a quote", exact=True).click()
    await expect(page.locator("#link-email-error")).to_contain_text("Enter a valid email address")
    await expect(page.locator("#link-phone-error")).to_contain_text("Enter a valid phone number")
    await capture("04-missing-invalid")
    await page.locator("#link-email").fill("sample@example.com")
    await page.locator("#link-phone").fill("+1 202-555-0123")
    await expect(page.locator(".field-error")).to_have_count(0)
    async with page.expect_request("**/v1/rig/link-quote") as submitted:
        await page.get_by_role("button", name="Request a quote", exact=True).click()
    assert (await submitted.value).post_data_json["contact"] == {
        "name": "Sample Shopper", "email": "sample@example.com", "phone": "+1 202-555-0123"}

    await expect(page.get_by_text("Request received. Reference", exact=False)).to_be_visible()
    request = page.get_by_role("button", name="Request a quote", exact=True)
    await expect(request).to_be_disabled()
    await expect(request).to_have_css("opacity", "0.5")
    await capture("04-missing-sent")
    await page.get_by_role("searchbox").fill("Core One")
    await page.get_by_role("button", name="Search", exact=True).click()
    await page.get_by_role("button", name="Selected ✓", exact=True).click()
    await page.get_by_role("button", name="Explore", exact=True).click()
    await expect(page.get_by_role("heading", name="Core One", exact=True)).to_be_visible()
    await expect(page.get_by_text("R 130", exact=True)).to_be_visible()
    await expect(page.get_by_role("button", name="2 parts", exact=True)).to_be_visible()
    await expect(page.get_by_role("button", name="+ 1 more fitted adapters", exact=True)).to_be_visible()
    await expect(page.locator(".connectors path")).to_have_count(9)
    await capture("05-explore")
    await page.get_by_role("button", name="+ 1 more fitted adapters", exact=True).click()
    await expect(page.locator(".g-chip")).to_have_count(7)
    await expect(page.get_by_role("button", name="+ 1 more fitted adapters", exact=True)).to_be_focused()
    await page.locator("#ask-q").fill("What fits this product?")
    await expect(page.locator("#ask-q")).to_have_css("resize", "none")
    await page.locator("#ask-q").press("Enter")
    await expect(page.locator(".answer")).to_contain_text("I don't know")
    await page.get_by_role("button", name="Find it. We source it. Back to setups", exact=True).click()
    await expect(page.locator(".setup")).to_have_count(3)
    await page.go_forward()
    await expect(page.locator(".answer")).to_contain_text("I don't know")
    await page.locator("#ask-q").press("Escape")
    await expect(page.locator(".setup")).to_have_count(3)
    await page.go_forward()
    await expect(page.locator(".graph-canvas")).to_be_visible()
    await page.get_by_role("button", name="Request a quote for this setup →", exact=True).click()
    await page.locator("#quote-name").fill("Sample Shopper")
    await page.locator("#quote-email").fill("sample@example.com")
    await page.get_by_role("button", name="Send request", exact=True).click()
    await expect(page.get_by_text("Request received. Reference", exact=False)).to_be_visible()
    await capture("quote")
    assert not failures
    await page.close()


@pytest.mark.asyncio
async def test_typeahead_only_counts_the_settled_search(real_chromium, widget_server):
    from playwright.async_api import expect

    page = await real_chromium.new_page()
    receipts = []
    searches = []
    page.on("request", lambda request: receipts.append(request.post_data_json)
            if request.url.endswith("/search-events") else searches.append(request.url)
            if "/v1/rig/search?" in request.url else None)
    await page.goto(widget_server + "/widget/test")
    box = page.get_by_role("searchbox")
    await expect(box).to_be_visible()
    # Slow enough for several typeahead fetches, faster than settlement.
    await box.press_sequentially("Core", delay=350)
    await expect(page.locator(".card")).to_have_count(3)
    for _ in range(30):
        if receipts:
            break
        await asyncio.sleep(0.1)
    assert len(searches) >= 3
    assert len(receipts) == 1 and receipts[0]["no_results"] is False
    assert set(receipts[0]) == {"event_id", "no_results"}
    await box.press("Enter")
    await expect(page.locator(".card")).to_have_count(3)
    await asyncio.sleep(0.2)
    assert len(receipts) == 1
    await page.close()
