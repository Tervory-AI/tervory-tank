/* Run with PLAYWRIGHT_MODULE pointing at an installed Playwright package. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async () => {
  const browser = await chromium.launch({headless: true, ...(process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {})});
  try {
    for (const width of [375, 1440]) {
      const page = await browser.newPage({viewport: {width, height: 900}});
      let adds = 0;
      await page.route('https://store.example/**', route => route.fulfill({contentType: 'text/html', body: '<div id="shop"></div>'}));
      await page.route('https://rig.example/**', async route => {
        const url = new URL(route.request().url());
        const headers = {'Access-Control-Allow-Origin': 'https://store.example', 'Access-Control-Allow-Headers': 'X-Rig-Key,Content-Type'};
        if (route.request().method() === 'OPTIONS') return route.fulfill({status: 204, headers});
        assert.equal(route.request().headers()['x-rig-key'], 'rk_pub_browser_fixture');
        if (url.pathname.endsWith('/media')) return route.fulfill({headers, contentType: 'video/mp4', body: fs.readFileSync(path.join(__dirname, 'fixtures/video_shop/sample.mp4'))});
        let result;
        if (url.pathname.endsWith('/videos/sample')) result = {moments: [{start: 1, end: 5, product_id: 'stock'}], products: {stock: {id: 'stock', name: '<Red cup>', price: {amount: '10.00', currency: 'USD'}, image: ''}}};
        else if (url.pathname.endsWith('/products/stock')) result = {name: '<Red cup>', attributes: {colour: 'red'}};
        else if (url.pathname.endsWith('/cart/session')) result = {session: 's'.repeat(43)};
        else if (url.pathname.endsWith('/cart/add')) {
          assert.deepEqual(route.request().postDataJSON(), {session: 's'.repeat(43), product_id: 'stock', quantity: 1});
          adds += 1; result = {lines: [{product_id: 'stock', quantity: 1}]};
        } else throw new Error(url.pathname);
        await route.fulfill({headers, contentType: 'application/json', body: JSON.stringify(result)});
      });
      await page.goto('https://store.example/');
      await page.addScriptTag({path: path.join(__dirname, '../agents/video_shop/widget.js')});
      await page.evaluate(async () => { window.player = await VideoShop.mount(document.querySelector('#shop'), {rigBase: 'https://rig.example', key: 'rk_pub_browser_fixture', videoId: 'sample'}); });
      const video = page.locator('video');
      await video.evaluate(node => new Promise(resolve => { if (node.readyState >= 1) resolve(); else node.onloadedmetadata = resolve; }));
      await video.evaluate(node => { node.currentTime = 2; });
      await page.getByRole('button', {name: 'View product: <Red cup>', exact: true}).click();
      await page.getByRole('button', {name: 'Add to cart', exact: true}).click();
      await page.getByRole('status').filter({hasText: 'Added to your store’s cart.'}).waitFor();
      assert.equal(adds, 1);
      assert.equal(await page.getByRole('button', {name: 'Open store cart', exact: true}).isDisabled(), true);
      await page.getByRole('button', {name: 'Products in this video', exact: true}).click();
      await page.getByRole('button', {name: 'Watch at 00:01', exact: true}).click();
      await video.evaluate(node => { node.pause(); });
      await page.getByRole('button', {name: 'View product: <Red cup>', exact: true}).waitFor();
      assert.equal(await page.locator('script').count(), 1); // Product text did not become markup.
      await video.evaluate(node => { node.currentTime = 7; });
      await page.getByRole('button', {name: 'View product: <Red cup>', exact: true}).waitFor({state: 'detached'});
      await page.evaluate(() => player.destroy());
      assert.equal(await page.locator('video').count(), 0);
      await page.close();
    }
    console.log('video-shop browser: mobile and desktop passed');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
