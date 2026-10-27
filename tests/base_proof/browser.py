"""Exercise the actual Workspace controls against the actual fixture Tank routes."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

OUTPUT = Path(__file__).parent / "screenshots"


async def main():
    OUTPUT.mkdir(exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(executable_path="/usr/bin/chromium", args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto("http://localhost:3141/base", wait_until="networkidle", timeout=120000)
        await page.get_by_text("4 ATF licences", exact=True).wait_for()
        await page.screenshot(path=str(OUTPUT / "01-empty-1440.png"))
        await page.get_by_label("States", exact=True).select_option("TX")
        await page.get_by_label("Licence types", exact=True).select_option("01")
        await page.get_by_role("button", name="Start from reference", exact=True).click()
        await page.get_by_role("status").filter(has_text="2 licences received").wait_for()
        await page.locator('a[href*="metric=email_and_phone"]').filter(has_text="2").first.wait_for()
        await page.get_by_role("button", name="Start from reference", exact=True).wait_for(state="visible")
        await page.screenshot(path=str(OUTPUT / "02-reference-batch-1440.png"))
        await page.get_by_role("button", name="View verified fields and sources").click()
        await page.get_by_role("region", name="Reference licences and verified results").get_by_text("Website", exact=True).first.wait_for()
        detail = page.locator('[aria-label="Verified fields"]')
        await detail.scroll_into_view_if_needed()
        await page.screenshot(path=str(OUTPUT / "03-field-sources-1440.png"))
        assert await detail.get_by_text("Checked", exact=False).count() >= 4
        await page.get_by_role("button", name="excludes 1 unpriced call", exact=True).first.click()
        expenses = page.get_by_label("Cost receipts")
        await expenses.get_by_text("Showing 1 of 1 call.", exact=True).wait_for()
        visible = await expenses.inner_text()
        assert "Web search" in visible and "price not set" in visible
        assert "brave.search" not in visible and "Receipt " not in visible and "T10:" not in visible
        await expenses.scroll_into_view_if_needed()
        await page.screenshot(path=str(OUTPUT / "08-unpriced-calls-1440.png"))

        async with page.expect_download() as pending:
            await page.locator('a[href*="metric=email_and_phone"]').first.click()
        download = await pending.value
        await download.save_as(str(OUTPUT / "verified-records.csv"))
        csv = (OUTPUT / "verified-records.csv").read_text()
        assert "phone_source_url" in csv and "/contact" in csv and "2026-10-26" in csv
        import csv as csv_reader
        import io
        imported = list(csv_reader.DictReader(io.StringIO(csv.lstrip("\ufeff"))))
        assert all(row["phone"] == "+15125550101" for row in imported)
        assert "[" not in csv and "]" not in csv and "{" not in csv
        for row in imported:
            assert row["email"].startswith("info@") and row["other_emails"].startswith("sales@")
            assert row["other_emails_source_url"] == row["instagram_source_url"] == row["website"] + "team"
            assert row["email_checked_at"] == "2026-10-26T10:00:00+00:00"
            assert row["other_emails_checked_at"] == "2026-10-27T10:00:00+00:00"
            assert row["x"] == row["linkedin"] == row["youtube"] == ""
            assert all('"' not in row[key] for key in ("email", "other_emails", "facebook", "instagram", "x", "linkedin", "youtube"))
        await page.get_by_label("Business CSV").set_input_files({"name": "fixture-businesses.csv", "mimeType": "text/csv", "buffer": b"name,state,website\nFixture Upload,CA,https://upload.example/\n"})
        await page.get_by_role("button", name="Upload and verify", exact=True).first.click()
        await page.get_by_role("status").filter(has_text="Your list was received").wait_for()
        await page.locator('a[href*="types=unspecified"]').first.wait_for()
        await page.get_by_text("California, licence type not given", exact=True).wait_for()
        await page.get_by_role("button", name="View verified fields and sources").click()
        await page.get_by_text("This website does not allow automatic reads. We stopped checking it.", exact=False).first.wait_for()
        visible = await page.locator("body").inner_text()
        import re
        assert not re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", visible)
        assert "licence_key" not in visible and "brave.search" not in visible and "1 calls" not in visible
        assert "CA / unspecified" not in visible and "paid model" not in visible

        await page.screenshot(path=str(OUTPUT / "04-csv-upload-1440.png"))
        await page.get_by_label("Apollo CSV").set_input_files({"name": "apollo-fixture.csv", "mimeType": "text/csv", "buffer": b"licence_key,website,phone,email\n5-74-00001,https://business-5-74-00001.example/,2125550199,\n"})
        await page.get_by_role("button", name="Compare the same licences").click()
        await page.get_by_role("status").filter(has_text="Apollo comparison saved").wait_for()
        await page.get_by_role("heading", name="Compare with Apollo").scroll_into_view_if_needed()
        await page.screenshot(path=str(OUTPUT / "05-apollo-1440.png"))
        for width in (375, 1440):
            await page.set_viewport_size({"width": width, "height": 1000})
            await page.reload(wait_until="networkidle")
            await page.get_by_text("4 ATF licences", exact=True).wait_for()
            await page.locator('[data-scroll-root]').evaluate("element => element.scrollTop = 0")
            await page.wait_for_timeout(250)  # allow the existing mobile drawer transition to finish
            await page.screenshot(path=str(OUTPUT / f"06-complete-{width}.png"))
            assert await page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
        await page.get_by_role("button", name="Reference list · TX", exact=True).click()
        batch = page.get_by_role("region", name="Batch results")
        await batch.get_by_text("2 attempted records.", exact=False).wait_for()
        async with page.expect_download() as pending:
            await batch.get_by_role("link", name="Download batch fields and sources").click()
        saved = await pending.value
        path = await saved.path()
        assert "phone_source_url" in Path(path).read_text()
        import html
        await page.set_content('<h1>Downloaded CSV · local, fixture page</h1><pre style="white-space:pre-wrap;overflow-wrap:anywhere">' + html.escape(csv) + '</pre>')
        await page.screenshot(path=str(OUTPUT / "07-downloaded-csv-1440.png"))
        assert not errors, errors
        await browser.close()
    print("Local fixture browser proof passed: reference batch, per-field evidence, CSV upload/download, Apollo and both widths.")


if __name__ == "__main__":
    asyncio.run(main())
