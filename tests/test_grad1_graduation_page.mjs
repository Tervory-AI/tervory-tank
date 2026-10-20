import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.TRAIN1_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.TRAIN1_PLAYWRIGHT_PATH || 'playwright');
const out=process.env.TRAIN1_SCREENSHOT_DIR || '/tmp/grad1-table-shots';
await fs.mkdir(out,{recursive:true});
const rows=[{task_type:'base.extract',model:'luna',gold_count:118,candidate:'skill:base.extract@2.0.0',heldout_score:.98,current_cost:.0012,candidate_cost:0,can_promote:false},{task_type:'reason.brief',model:'luna',gold_count:105,candidate:'flash-lite',heldout_score:.99,current_cost:.0012,candidate_cost:.0002,can_promote:true},{task_type:'zenas.retrieve',model:'luna',gold_count:23,candidate:null,heldout_score:null,current_cost:null,candidate_cost:null,can_promote:false}];
const bundle=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {GraduationPanel} from './app/tank/graduation-panel';createRoot(document.getElementById('root')).render(<GraduationPanel rows={${JSON.stringify(rows)}}/>);`,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'server-action-fixture',setup(b){b.onResolve({filter:/graduation-actions$/},()=>({path:'action',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export async function promoteTraining(){window.promoted=true}',loader:'js'}));}}]});
const css=await fs.readFile(path.join(root,'workspace/app/tank/tank.css'),'utf8');
const server=createServer((req,res)=>{if(req.url==='/bundle.js'){res.setHeader('content-type','text/javascript');res.end(bundle.outputFiles[0].text);return;}res.end(`<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font-family:Arial}${css}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>`)});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({headless:true});
try{const page=await browser.newPage();await page.goto(`http://127.0.0.1:${server.address().port}`);await page.getByRole('heading',{name:'Graduation'}).waitFor();assert.equal(await page.getByRole('button',{name:'Promote'}).count(),1);assert.equal(await page.getByText('Not tested',{exact:true}).count(),1);assert(!(await page.evaluate(()=>window.promoted)));for(const width of [1440,375]){await page.setViewportSize({width,height:900});await page.screenshot({path:path.join(out,`graduation-${width}.png`),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}await page.getByRole('button',{name:'Promote'}).click();assert(await page.evaluate(()=>window.promoted));console.log('Graduation fixtures: costs, missing evidence, founder click, desktop/mobile overflow passed');}finally{await browser.close();server.close();}
