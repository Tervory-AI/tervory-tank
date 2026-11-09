"""Signed-in page content checks (ops/page_content_check.js) on saved HTML fixtures.

The same browser function the live check runs every 15 minutes. Each bad fixture is a
problem seen live on 8 Nov 2026 and must fail; the good page must pass. Fixtures are
served through Playwright routing with their HTTP status, so no network is used.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "signed_in_fixtures"
CHECK = (ROOT / "ops" / "page_content_check.js").read_text(encoding="utf-8").strip()
RIG = {"expect": ["What's built", "Next step"],
       "required": [{"name": "Ask Rig answers", "selector": '[aria-label="Ask Rig"] .thread'}]}


async def reasons_for(browser, fixture: str, status: int = 200, html: str | None = None,
                      **config) -> list[str]:
    context = await browser.new_context()
    try:
        page = await context.new_page()
        body = html if html is not None else (FIXTURES / fixture).read_text(encoding="utf-8")

        async def serve(route):
            await route.fulfill(status=status, content_type="text/html", body=body)

        await page.route("https://fixture.test/**", serve)
        response = await page.goto("https://fixture.test/page")
        return await page.evaluate(CHECK, {"status": response.status, **config})
    finally:
        await context.close()


@pytest.mark.asyncio
async def test_good_page_passes(real_chromium) -> None:
    assert await reasons_for(real_chromium, "good-rig-overview.html", **RIG) == []


@pytest.mark.asyncio
async def test_blank_next_step_support_placeholder_and_empty_ask_box_fail(real_chromium) -> None:
    reasons = await reasons_for(real_chromium, "blank-next-step.html", **RIG)
    assert "Empty section: Next step" in reasons
    assert "Section shows a placeholder: What's built (— Support)" in reasons
    assert "Empty: Ask Rig answers" in reasons
    assert len(reasons) == 3


@pytest.mark.asyncio
async def test_provider_name_on_sign_in_page_fails(real_chromium) -> None:
    reasons = await reasons_for(real_chromium, "zitadel-sign-in.html", signIn=True)
    assert "Sign-in text names the provider: ZITADEL" in reasons
    assert "Sign-in text shows an admin greeting: Welcome ZITADEL Admin" in reasons


@pytest.mark.asyncio
async def test_provider_name_in_signed_in_header_fails(real_chromium) -> None:
    good = (FIXTURES / "good-rig-overview.html").read_text(encoding="utf-8")
    assert "Sign out of Trigger sign-in" in good
    leaked = good.replace("Sign out of Trigger sign-in", "Sign out of Clerk")
    reasons = await reasons_for(real_chromium, "", html=leaked, **RIG)
    assert reasons == ["Sign-in text names the provider: Clerk"]


@pytest.mark.asyncio
async def test_503_page_fails(real_chromium) -> None:
    reasons = await reasons_for(real_chromium, "service-unavailable.html", status=503)
    assert reasons[0] == "HTTP 503"
    assert "Server error shown: 503 Service Unavailable" in reasons
    assert "No main content on the page" in reasons


@pytest.mark.asyncio
async def test_503_text_fails_even_when_the_proxy_says_200(real_chromium) -> None:
    reasons = await reasons_for(real_chromium, "service-unavailable.html", status=200)
    assert "HTTP 503" not in reasons
    assert "Server error shown: 503 Service Unavailable" in reasons


@pytest.mark.asyncio
async def test_failed_request_and_missing_expected_text_fail(real_chromium) -> None:
    reasons = await reasons_for(real_chromium, "good-rig-overview.html", failedRequests=[502],
                                expect=["Client savings"])
    assert reasons == ["A request on the page returned HTTP 502", "Missing expected text: Client savings"]


def test_every_page_the_founder_named_is_checked() -> None:
    config = json.loads((ROOT / "ops" / "signed_in_pages.json").read_text(encoding="utf-8"))
    ids = [page["id"] for page in config["pages"]]
    assert len(ids) == len(set(ids))
    for needed in ("workspace-chats", "tank-chats", "base", "rig-overview", "rig-search", "trigger",
                   "tiger", "skala", "autumbra", "radix", "tisan", "zenas", "opli", "market-lab", "savings"):
        assert needed in ids
    for page in config["pages"]:
        assert page["url"].startswith("https://") and page["url"].split("/")[2].endswith("tervory.com")
