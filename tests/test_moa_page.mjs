// Offline founder-view fixture. No Clerk, Tank, model keys or production calls.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
const root=process.cwd();
const require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.MOA_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.MOA_PLAYWRIGHT_PATH || 'playwright');
const chromiumPack=process.env.MOA_CHROMIUM_PACKAGE ? (await import(process.env.MOA_CHROMIUM_PACKAGE)).default : null;
const out=process.env.MOA_SCREENSHOT_DIR || '/tmp/moa-shots';
await fs.mkdir(out,{recursive:true});
const shapes=[{shape:'single',mode:'select',score:.97,cost_per_call:.04,samples:100,status:'complete'},
 ...['self','diverse','optimised'].flatMap((shape,i)=>['select','synthesize'].map((mode,j)=>({shape,mode,score:.98-j*.01,cost_per_call:.08-i*.025+j*.003,samples:100,status:'complete'})))];
const data={tenant_id:'00000000-0000-0000-0000-000000000001',region:'us-east',tasks:[{task_type:'base.extract',enabled:false,config_hash:'fixture',config:{shape:'optimised',mode:'select',min_samples:100,bench_enabled:true,cheap_aggregator:'small-model',frontier_aggregator:'top-model',cheap_candidate:null,frontier_candidate:'candidate-model',seats:['logic','context','research','data'].map((name,i)=>({name,model:'current-'+i,candidate:i===0?'candidate-model':null,critical:name==='research',timeout_s:15}))},shapes,proposals:[]}],
 runs:[{id:'fixture-run',task_type:'base.extract',kind:'bench',status:'complete',created_at:'2026-10-21T00:00:00Z',receipt:{baseline_model:'top-model',cost_usd:.03,all_frontier_usd:.12,single_top_usd:.04,saved_vs_frontier_usd:.09,saved_vs_single_usd:.01,seats:[{name:'logic',model:'current-0',status:'COMPLETE',attempts:[{model:'current-0',tokens_in:100,tokens_out:40,cost_usd:.005,ledger_id:'fixture-ledger'}]},{name:'research',model:'current-2',status:'FAILED',error:'Seat timed out',attempts:[]}]}}],shadows:[]};
const bundle=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {MoaView} from './app/tank/moa/view';createRoot(document.getElementById('root')).render(<MoaView data={${JSON.stringify(data)}}/>);`,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'offline-actions',setup(b){b.onResolve({filter:/\.\/actions$/},()=>({path:'actions',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export async function actOnMixture(){}',loader:'js'}));}}]});
const css=await fs.readFile(path.join(root,'workspace/app/tank/moa/moa.css'),'utf8');
const server=createServer((req,res)=>{if(req.url==='/bundle.js'){res.setHeader('content-type','text/javascript');res.end(bundle.outputFiles[0].text);return;}res.end(`<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font-family:Arial}${css}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>`)});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({headless:true,...(chromiumPack?{executablePath:await chromiumPack.executablePath(),args:chromiumPack.args}:{})});
try {
 const page=await browser.newPage();
 await page.goto(`http://127.0.0.1:${server.address().port}`);
 await page.getByRole('heading',{name:'Mixtures, measured'}).waitFor();
 assert.equal(await page.getByText('Off',{exact:true}).count(),1);
 assert.equal(await page.getByRole('img').count(),1);
 assert.equal(await page.getByRole('button',{name:'Promote measured winner'}).count(),1);
 assert.equal(await page.getByRole('button',{name:'Promote logic'}).count(),0);
 await page.locator('summary').click();
 await page.getByText('Seat timed out',{exact:true}).waitFor();
 for(const width of [1440,375]){
   await page.setViewportSize({width,height:900});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   await page.screenshot({path:path.join(out,`moa-${width}.png`),fullPage:true});
 }
 console.log('MoA fixture: chart, disabled policy, explicit promotion, failure receipt and 375px/1440px overflow checks passed.');
} finally {await browser.close();server.close();}
