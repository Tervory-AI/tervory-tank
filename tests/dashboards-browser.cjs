/* Run after dashboards-ui.cjs in a managed cloud environment with Playwright/Chromium. */
const { chromium } = require('playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
(async () => {
  const server = http.createServer((req, res) => {
    const name = new URL(req.url, 'http://localhost').pathname;
    const base = name.startsWith('/brand/') ? 'workspace/public' : name.startsWith('/fonts/') ? 'workspace/app' : 'tests/artifacts/dash-1';
    const file = path.join(root, base, name);
    if (!fs.existsSync(file)) {res.writeHead(404); res.end(); return;}
    res.setHeader('Content-Type', ({'.html':'text/html','.woff2':'font/woff2','.png':'image/png'})[path.extname(file)] || 'application/octet-stream');
    res.end(fs.readFileSync(file));
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({executablePath:process.env.DASH_CHROMIUM || '/usr/bin/chromium', headless:true,args:['--no-sandbox']});
  try {
    for (const screen of ['client','founder']) for (const width of [1440,375]) {
      const page = await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1});
      await page.goto(`http://127.0.0.1:${server.address().port}/${screen}.html`);
      await page.evaluate(() => document.fonts.ready);
      const rendered = await page.evaluate(() => ({
        documentWidth:document.documentElement.scrollWidth,
        images:[...document.images].map(i=>({loaded:i.complete&&i.naturalWidth>0,width:i.width,height:i.height,naturalWidth:i.naturalWidth,naturalHeight:i.naturalHeight})),
        sharedShellVisible:getComputedStyle(document.querySelector('.shell-side')).display !== 'none',
      }));
      assert(rendered.documentWidth <= width, 'horizontal overflow');
      assert.equal(rendered.sharedShellVisible, screen === 'client', 'client uses shared shell; founder retains its own navigation');
      assert(rendered.images.every(i=>i.loaded), 'asset did not load');
      assert(rendered.images.every(i=>Math.abs(i.width/i.height-i.naturalWidth/i.naturalHeight)<.25), 'logo distorted');
      await page.screenshot({path:path.join(root,`tests/artifacts/dash-1/${screen}-${width}.png`),fullPage:true});
      await page.close();
      console.log(`${screen} ${width}px: no overflow, shell or asset mismatch`);
    }
  } finally {await browser.close();server.close();}
})().catch(err=>{console.error(err);process.exitCode=1});
