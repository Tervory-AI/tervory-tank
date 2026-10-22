// Run from the repo root with esbuild and Playwright available (or set the paths below).
// Renders the production /rig/admin component with synthetic tenant responses.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';

const root = process.cwd();
const require = createRequire(path.join(root, 'workspace/package.json'));
const { build } = require(process.env.RIG_ESBUILD_PATH || 'esbuild');
const { chromium } = require(process.env.RIG_PLAYWRIGHT_PATH || 'playwright');
const out = process.env.RIG_SCREENSHOT_DIR || path.join(os.tmpdir(), 'rig-admin-review');
await fs.mkdir(out, { recursive: true });
const initial = {
  price_configured: true, currency: 'ZAR', products: 24, can_set_exchange_rate: false,
  feeds: [{ provider: 'shopify', site: 'https://sample-shop.example', next_refresh: null }],
  templates: { lighting: { shade: 'shade', stand: 'stand' } },
  fits: [{ part_sku: 'SAMPLE-SHADE', part_name: 'Sample Lamp Shade', fits_sku: 'SAMPLE-LAMP', fits_family: null, fits_with: 'Sample Desk Lamp', note: 'Supplier sample catalogue lists this shade for the sample desk lamp. Review before showing it to shoppers.', confidence: null }],
  missed_searches: [{ query: 'blue desk lamp', count: 12 }, { query: 'compact reading light', count: 7 }, { query: 'replacement shade', count: 4 }],
  receipts: [{ id: 'sample-import', provider: 'shopify', site: 'https://sample-shop.example', added: 24, updated: 0, rejected: 0, created_at: '2026-10-22T03:00:00Z' }],
};
const entry = `import React from 'react'; import {createRoot} from 'react-dom/client';
import {RetailerAdmin} from './app/rig/admin/retailer-admin';
let panel=${JSON.stringify(initial)}; window.__calls=[];
const act=async(operation,data)=>{window.__calls.push({operation,data});
if(operation==='approve'||operation==='reject')panel={...panel,fits:[]};
if(operation==='templates')panel={...panel,templates:{...panel.templates,...data}};
return {ok:true,message:operation==='refresh'?'0 added, 24 updated, 0 rejected.':'Saved.',panel};};
createRoot(document.getElementById('root')).render(<RetailerAdmin initial={panel} act={act}/>);`;
const built = await build({ stdin: { contents: entry, resolveDir: path.join(root, 'workspace'), loader: 'tsx' }, bundle: true, write: false, jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' } });
const script = built.outputFiles[0].text;
const css = await fs.readFile(path.join(root, 'workspace/app/rig/admin/retailer-admin.css'), 'utf8');
const html = `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
@font-face{font-family:Inter;src:url(/fonts/Inter-latin.woff2)}@font-face{font-family:Jost;src:url(/fonts/Jost-300-latin.woff2);font-weight:300}
@font-face{font-family:Mono;src:url(/fonts/JetBrainsMono-latin.woff2)}:root{--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}body{margin:0;background:#fafbfd}
${css}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>`;
const server = createServer(async(req,res)=>{
  if(req.url==='/app.js'){res.setHeader('content-type','text/javascript');res.end(script);return;}
  if(req.url?.startsWith('/fonts/')){res.setHeader('content-type','font/woff2');res.end(await fs.readFile(path.join(root,'workspace/app/fonts',path.basename(req.url))));return;}
  res.setHeader('content-type','text/html');res.end(html);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser = await chromium.launch({ executablePath: process.env.READ1_CHROMIUM_EXECUTABLE, args: ['--no-sandbox'] });
try {
  const page=await browser.newPage();
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/rig/admin`);
  await page.getByRole('heading',{name:'Retailer settings',exact:true}).waitFor();
  await page.evaluate(()=>document.fonts.ready);
  for(const width of [375,1440]){
    await page.setViewportSize({width,height:1000});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow at ${width}`);
    await page.screenshot({path:path.join(out,`rig-admin-${width}.png`),fullPage:true});
  }
  assert.equal(await page.getByText('shade: shade', {exact:true}).count(), 0);
  assert.equal(await page.getByLabel('Column names', {exact:true}).count(), 1);
  assert.equal(await page.getByLabel('Freight per item, in supplier currency').inputValue(),'');
  assert.equal(await page.getByLabel('Duty (%)',{exact:true}).inputValue(),'');
  assert.equal(await page.getByLabel('Gross margin (%)',{exact:true}).inputValue(),'');
  await page.getByRole('button',{name:'Refresh now',exact:true}).click();
  await page.getByRole('status').filter({hasText:'24 updated'}).waitFor();
  await page.getByRole('button',{name:'Approve',exact:true}).click();
  await page.getByText('Nothing waiting for review.',{exact:true}).waitFor();
  await page.getByLabel('Product category',{exact:true}).fill('tableware');
  await page.getByLabel('Included categories, separated by commas').fill('saucer, coaster');
  await page.getByRole('button',{name:'Save template',exact:true}).click();
  await page.getByText('saucer · coaster',{exact:true}).waitFor();
  await page.getByLabel('Freight per item, in supplier currency').fill('2');
  await page.getByLabel('Duty (%)',{exact:true}).fill('10');
  await page.getByLabel('Gross margin (%)',{exact:true}).fill('20');
  await page.getByRole('button',{name:'Save price rule',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('input[name=freight]').value==='');
  const calls=await page.evaluate(()=>window.__calls);
  assert.deepEqual(calls.map(call=>call.operation),['refresh','approve','templates','price-rule']);
  assert(calls.every(call=>!('tenant_id' in call.data)));
  assert.deepEqual(errors,[]);
  console.log('Retailer admin: 375px/1440px screenshots, no overflow, refresh, approval, template and private-rule form checks passed.');
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
