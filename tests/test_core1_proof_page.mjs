import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.CORE1_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.CORE1_PLAYWRIGHT_PATH || 'playwright');
const out=process.env.CORE1_SCREENSHOT_DIR || '/tmp/core1-proof-shots';
await fs.mkdir(out,{recursive:true});
const data={tenant_id:'all',tenant_names:{'00000000-0000-0000-0000-000000000001':'Tervory','22222222-2222-2222-2222-222222222222':'AmmoSync'},tenant_names_note:null,tenants:['00000000-0000-0000-0000-000000000001','22222222-2222-2222-2222-222222222222'],all_tenant_total:{saved_usd:.56,calls:40,priced_calls:39,unpriced_calls:1},window:{start:null,end:'2026-10-21T12:00:00+00:00'},page:0,page_size:100,has_more:{ledger:true},receipt_page_total:{calls:1,saved_usd:.0038},region:'us-east',tasks:[
  {task_type:'base.extract',calls:40,priced_calls:39,actual_usd:.08,compared_actual_usd:.08,unknown_cost_calls:0,baseline_usd:.64,saved_usd:.56,backfilled_calls:12,unpriced_calls:1,code_calls:10,code_share:.25,shadow_pairs:[{primary_model:'astra',candidate_model:'luna',samples:30,agreement:.98,primary_cost_usd:.12,could_have_cost_usd:.02}]},
  {task_type:'tiger.price_read',calls:0,priced_calls:0,actual_usd:0,compared_actual_usd:0,unknown_cost_calls:0,baseline_usd:0,saved_usd:0,backfilled_calls:0,unpriced_calls:0,code_calls:0,code_share:null,shadow_pairs:[]}],
  state:[{task_type:'base.extract',bench_at:'2026-10-21T00:00:00Z',bench_status:'complete',bench_error:null}],
  policies:[{task_type:'base.extract',model:'astra',candidate_model:'luna',baseline_model:'astra',auto_promote:false}],
  runs:[{id:'run-fixture',task_type:'base.extract',model:'luna',comparison_model:'astra',expected_n:100,score:.98,cost_per_call:.0002,status:'complete'}],
  cases:[{id:'case-fixture',run_id:'run-fixture',task_type:'base.extract',case_ref:'eval-fixture',case_kind:'eval',ledger_id:'receipt-fixture',score:1,charged_usd:.0002,status:'complete'}],
  shadows:[{id:'shadow-fixture',task_type:'base.extract',primary_model:'astra',candidate_model:'luna',primary_cost_usd:.004,candidate_cost_usd:.0002,agreement:1}],
  promotions:[{id:'promotion-fixture',task_type:'base.extract',action:'promote',from_model:'astra',to_model:'luna',created_at:'2026-10-20T00:00:00Z'}],
  ledger:[{id:'receipt-fixture',task_type:'base.extract',model:'luna',cost_usd:.0002,baseline_model:'astra',baseline_cost_usd:.004,saved_usd:.0038,baseline_status:'backfilled'}]};
const bundle=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {ProofView} from './app/tank/proof/view';createRoot(document.getElementById('root')).render(<ProofView data={${JSON.stringify(data)}}/>);`,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
const css=await fs.readFile(path.join(root,'workspace/app/tank/proof/proof.css'),'utf8');
const server=createServer((req,res)=>{if(req.url==='/bundle.js'){res.setHeader('content-type','text/javascript');res.end(bundle.outputFiles[0].text);return;}res.end(`<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font-family:Arial}${css}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>`)});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({headless:true,...(process.env.CORE1_CHROMIUM ? {executablePath:process.env.CORE1_CHROMIUM} : {})});
try { const page=await browser.newPage(); await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.getByRole('heading',{name:'Tank proof',exact:true}).waitFor();
  const saved=page.locator('.proof-task').first().getByRole('link',{name:'$0.560000',exact:true});
  const href=new URL(await saved.getAttribute('href'),'http://fixture');
  assert.equal(href.searchParams.get('task'),'base.extract'); assert.equal(href.searchParams.get('tenant_id'),'all'); assert.equal(href.hash,'#receipts');
  assert.equal(await page.getByLabel('Tenant',{exact:true}).inputValue(),'all');
  assert.equal(await page.getByLabel('Tenant',{exact:true}).textContent(),'All tenantsTervoryAmmoSync');
  for(const name of ['Export PDF','Export CSV']) {
    const exported=new URL(await page.getByRole('link',{name}).getAttribute('href'),'http://fixture');
    assert.equal(exported.searchParams.get('tenant_id'),'all'); assert.equal(exported.searchParams.get('end'),data.window.end);
    assert.equal(exported.searchParams.get('page'),'0');
  }
  const next=new URL(await page.getByRole('link',{name:'Next page',exact:true}).first().getAttribute('href'),'http://fixture');
  assert.equal(next.searchParams.get('page'),'1'); assert.equal(next.searchParams.get('end'),data.window.end);
  assert.equal(await page.getByText('No shadow pairs recorded yet.').count(),1);
  for(const width of [1440,375]) { await page.setViewportSize({width,height:900}); await page.screenshot({path:path.join(out,`proof-${width}.png`),fullPage:true}); assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)); }
  await saved.click(); assert.equal(await page.locator(':target').getAttribute('id'),'receipts');
  await page.getByLabel('Tenant',{exact:true}).selectOption(data.tenants[1]);
  await page.getByLabel('Task',{exact:true}).fill('base.extract');
  await page.getByLabel('From (UTC)',{exact:true}).fill('2026-10-01T00:00');
  await page.getByRole('button',{name:'Apply filters'}).click();
  const selected=new URL(page.url()); assert.equal(selected.searchParams.get('tenant_id'),data.tenants[1]);
  assert.equal(selected.searchParams.get('task'),'base.extract'); assert.equal(selected.searchParams.get('start'),'2026-10-01T00:00');
  console.log('Proof fixtures: desktop/mobile, exports, empty evidence and receipt links passed.');
} finally { await browser.close(); server.close(); }
