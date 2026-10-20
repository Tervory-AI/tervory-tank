// Browser test of the real client component, with a fixture API and no Clerk secrets.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import { createServer } from 'node:http';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(path.join(root, 'workspace/package.json'));
const { build } = require(process.env.TRAIN1_ESBUILD_PATH || 'esbuild');
const { chromium } = require(process.env.TRAIN1_PLAYWRIGHT_PATH || 'playwright');
const output = process.env.TRAIN1_SCREENSHOT_DIR || '/tmp/tervory-train1-screenshots';
await fs.mkdir(output, { recursive: true });
const fixture = await build({ stdin: { contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import {GoldView} from './app/skala/gold/view'; createRoot(document.getElementById('root')).render(<GoldView founder={true}/>);`, resolveDir: path.join(root, 'workspace'), loader: 'tsx' }, bundle: true, write: false, jsx: 'automatic', define: { 'process.env.NODE_ENV': '"production"' } });
const css = await fs.readFile(path.join(root, 'workspace/app/skala/gold/gold.css'), 'utf8');
const calls = [];
const examples = [{id:'00000000-0000-0000-0000-000000000011',input:{name:'Example company',website:'https://example.invalid'},expected:{match:true},source:'package'}, {id:'00000000-0000-0000-0000-000000000012',input:{name:'Second example'},expected:{match:false},source:'package'}];
const summary = {region:'us-east',pairs:{base:34,tiger:18,zenas:22},skills:[{agent:'base',skill_id:'base.find_site',checked:82,target:100,holdout:16,candidates:2,last_score:.95,trend:-.03,ran_at:'2026-01-01'},{agent:'tiger',skill_id:'tiger.price_extract',checked:46,target:100,holdout:9,candidates:2,last_score:.96,trend:-.01,ran_at:'2026-01-01'}]};
const server = createServer(async (request,response) => {
  const url = new URL(request.url, 'http://localhost');
  if (url.pathname === '/bundle.js') {response.setHeader('content-type','text/javascript'); response.end(fixture.outputFiles[0].text);return;}
  if (url.pathname === '/api/skala/gold') {
    response.setHeader('content-type','application/json');
    if (request.method === 'POST') {let body='';for await(const part of request) body+=part;calls.push(JSON.parse(body)); examples.shift(); response.end('{"ok":true}');return;}
    response.end(JSON.stringify(url.searchParams.get('view') === 'next' ? examples.find(e => e.id > (url.searchParams.get('after')||'')) ?? null : summary));return;
  }
  response.end(`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{margin:0}${css}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>`);
});
await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
const browser = await chromium.launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:1440,height:1100}});
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}/skala/gold`);
  await page.getByText('Example company', {exact:false}).waitFor();
  await page.getByText('Ten machine-labelled examples per source for each skill', {exact:false}).waitFor();
  await page.getByText('-3.0 points', {exact:true}).waitFor();
  await page.getByText('95.0%', {exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'gold-desktop.png'),fullPage:true});
  await page.setViewportSize({width:375,height:844});
  await page.screenshot({path:path.join(output,'gold-mobile.png'),fullPage:true});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth));
  await page.keyboard.press('r');
  await page.getByText('Second example', {exact:false}).waitFor();
  assert.equal(calls[0].action,'right');
  await page.keyboard.press('w');
  const box=page.getByRole('textbox');
  await box.waitFor();
  await box.fill('{"match":true}');
  await box.press('r'); // Typing in correction must not invoke Right.
  assert.equal(calls.length,1);
  await box.fill('{"match":true}');
  await page.getByRole('button',{name:'Save correction'}).click();
  await page.getByRole('heading',{name:'No examples waiting for this skill.'}).waitFor();
  assert.equal(calls[1].action,'wrong');
  assert.deepEqual(calls[1].correction,{match:true});
  assert.deepEqual(errors,[]);
  console.log('TRAIN-1 browser checks passed: desktop, mobile, no overflow, shortcuts, correction focus, save.');
} finally {await browser.close();server.close();}
