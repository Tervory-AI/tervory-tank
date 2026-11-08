import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
const root=process.cwd(), require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.RIG_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.RIG_PLAYWRIGHT_PATH || 'playwright');
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import {SavingsReceipts} from './app/rig/admin/savings-receipts';
const root=createRoot(document.getElementById('root'));window.show=receipts=>root.render(<main className="retailer-admin"><SavingsReceipts receipts={receipts}/></main>);window.show([]);`;
const built=await build({stdin:{contents:entry,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,minify:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
const js=built.outputFiles[0].text, css=await fs.readFile(path.join(root,'workspace/app/rig/admin/retailer-admin.css'),'utf8');
const server=createServer((req,res)=>{res.setHeader('content-type',req.url==='/app.js'?'text/javascript':'text/html');res.end(req.url==='/app.js'?js:`<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>`);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:process.env.READ1_CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});
try {
 const page=await browser.newPage();page.setDefaultTimeout(5000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',r=>r.request().url().startsWith(base)?r.continue():r.abort());
 for(const width of [375,1440]) {
  await page.setViewportSize({width,height:1000});await page.goto(base);
  const section=page.getByRole('region',{name:'Receipts'});
  await section.getByText('Run a search to see receipts here.',{exact:true}).waitFor();
  assert.equal(await section.locator('article').count(),0);assert.deepEqual(await section.locator('dd').allTextContents(),['—','—']);
  await page.keyboard.press('Tab');assert(await section.getByRole('link',{name:'Search'}).evaluate(n=>n===document.activeElement));
  await page.evaluate(()=>window.show([{id:'placeholder-code',action:'rig.ask',created_at:'2026-11-06T00:00:00Z',outcome:'delivered',cost:'0',cost_status:'recorded',would_have_cost:'0.0028',baseline_status:'bpe_reference'},
   {id:'placeholder-gpu',action:'rig.forge.trellis2',created_at:'2026-11-06T00:00:00Z',outcome:'unverified',cost:'0.166667',cost_status:'upper_bound',would_have_cost:null,baseline_status:'unpriced'}]));
  await section.getByText('Reserved cost',{exact:true}).waitFor();
  assert.deepEqual(await section.locator('dd').allTextContents(),['$0.00','$0.0028','$0.166667','—']);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 assert.deepEqual(errors,[]);console.log('PASS: empty receipt shape, first action, keyboard, real zero, fractional cost, GPU reserve, unknown baseline, phone layout.');
} finally {await browser.close();await new Promise(r=>server.close(r));}
