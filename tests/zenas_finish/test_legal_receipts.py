"""Browser acceptance of the shipped receipts view; data stays an offline fixture."""
import pytest
from zenas_finish.test_gate5_journeys import client_bundle as _client_bundle

client_bundle = _client_bundle

@pytest.mark.asyncio
async def test_receipt_view_is_empty_at_day_zero_and_shows_measured_costs(client_bundle):
    from playwright.async_api import async_playwright,expect
    from zenas_finish.test_gate5_journeys import screen
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True, args=['--no-sandbox'])
        context,page,errors=await screen(browser,client_bundle,'receipts')
        await expect(page.get_by_role('columnheader',name='Cost',exact=True)).to_be_visible()
        await expect(page.get_by_role('columnheader',name='Would have cost',exact=True)).to_be_visible()
        await expect(page.get_by_text('Ask Zenas',exact=True)).to_be_visible()
        assert '$' not in await page.locator('body').inner_text()
        await page.evaluate('window.renderScreen("receipts",{receipts:[{id:"one",action:"/answers",cost:0.001,"would have cost":0.02,baseline_model:"paid-default"}]})')
        await expect(page.get_by_text('$0.00100000',exact=True)).to_be_visible()
        await expect(page.get_by_text('$0.02000000 · paid-default',exact=True)).to_be_visible()
        await page.evaluate('window.renderScreen("receipts",{receipts:[{id:"other-product",action:"/moot/hearings/one/ai",cost:77,"would have cost":88,baseline_model:"paid-default"}]})')
        await expect(page.get_by_text('Ask Zenas',exact=True)).to_be_visible()
        assert '$' not in await page.locator('body').inner_text()
        assert 'Moot Court' not in await page.locator('body').inner_text()
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.evaluate('window.renderScreen("receipts",{receipts:Array.from({length:100},(_,i)=>({id:String(i),action:"/answers",cost:i+.001,"would have cost":i+.02,baseline_model:"paid-default"}))})')
        panel=page.get_by_role('region',name='Receipts',exact=True)
        await panel.focus();await page.keyboard.press('End')
        await expect(panel.get_by_role('row').last).to_be_in_viewport()
        assert not errors
        await context.close();await browser.close()
