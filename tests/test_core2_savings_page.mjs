import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
const root=process.cwd(), require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.CORE2_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.CORE2_PLAYWRIGHT_PATH || 'playwright');
const out=process.env.CORE2_SCREENSHOT_DIR || '/tmp/core2-shots';
await fs.mkdir(out,{recursive:true});
const total={standards:['sol'],tops:['astra'],top_cost:'21',top_spent:'2.1',top_saved:'18.9',top_count:21,quality_pending:true,spent:'2.10000000',would_have_cost:'8.40000000',saved:'6.30000000',work_count:21,jobs_count:7,free_count:7};
const data={revision:'0',as_of:'2026-10-21T12:00:00Z',total,month:total,daily:Array.from({length:21},(_,i)=>({...total,day:`2026-10-${String(i+1).padStart(2,'0')}`,spent:'.1',would_have_cost:'.4',saved:'.3',cumulative:String((i+1)*.3),work_count:1,jobs_count:1,free_count:i%3===0?1:0})),members:[{...total,member:'Base',saved:'3.3'},{...total,member:'Tiger',saved:'2.1'},{...total,member:'Market Lab',saved:'.9'}],tenant_id:'all',tenants:['00000000-0000-0000-0000-000000000001','client-fixture'],region:'us-east',excluded:[{excluded_reason:'Unknown baseline',count:2}],margin:{status:'no billing data yet',paid:null,margin:null,margin_percent:null,total:{standards:['sol'],actual:'2.2',baseline:'8.4',unknown_costs:1,unknown_baselines:2},daily:[{day:'2026-10-20',standards:['sol'],actual:'2.2',baseline:'8.4',unknown_costs:1,unknown_baselines:2}]}};
// Synthetic fixtures; production components, no network or model/provider calls.
const fixtures=`export const data=${JSON.stringify(data)};
if(location.search.includes('tiny')){data.daily=data.daily.map(p=>({...p,spent:'0.00000000',would_have_cost:'0.00000001',saved:'0.00000001',cumulative:'0.00000001'}));}
export function rows(f={}){window.__filters=f;return {as_of:data.as_of,page:Number(f.page??0),has_more:!Number(f.page),total:data.total,rows:[{job_id:'fixture-job',job_title:'Business list',member:'Base',day:'2026-10-20',spent:'.1',would_have_cost:'.4',saved:'.3',free_work:false,standard_name:'sol',top_name:'astra',top_saved:'.9',selected_name:'astra',selected_cost:'1',quality_compared:false,comparison_status:'re-priced',compared_at:'2026-10-21T12:00:00Z',...(f.population==='excluded'?{id:'receipt-fixture',model:'founder-model',excluded_reason:'Unknown baseline'}:{})}]};}`;
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import Dashboard from './app/page';import {FounderSavingsPanel} from './app/tank/proof/savings-founder';
const content=location.pathname==='/client' ? await Dashboard({searchParams:Promise.resolve({})}) : await FounderSavingsPanel({tenant:location.search.includes('selected')?'client-fixture':undefined});
createRoot(document.getElementById('root')).render(content);`;
const bundle=await build({stdin:{contents:entry,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,format:'esm',jsx:'automatic',outdir:'/tmp/unused-core2',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'offline-identity',setup(b){
 b.onResolve({filter:/^fixture$/},()=>({path:'fixture',namespace:'mock'}));
 b.onResolve({filter:/^(server-only|@clerk\/nextjs\/server|@\/lib\/tenant|@\/lib\/tank|next\/navigation)$/},args=>({path:args.path,namespace:'mock'}));
 b.onResolve({filter:/^\.\/server$/},args=>args.importer.endsWith('savings-founder.tsx')?{path:'proof-server',namespace:'mock'}:undefined);
 b.onResolve({filter:/savings-founder-actions$/},()=>({path:'founder-actions',namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},args=>({loader:'js',contents:args.path==='fixture'?fixtures:args.path==='server-only'?'':args.path==='@/lib/tenant'?`export async function activeTenant(){return {tenantId:'client-fixture',orgName:'Example client',userId:'fixture'};}export const tenantIdFor=()=> 'client-fixture';export const uuidFrom=tenantIdFor;`:args.path==='@clerk/nextjs/server'?`export async function currentUser(){return {firstName:'Alex'};}export async function clerkClient(){return {organizations:{getOrganizationList:async()=>({data:[{id:'fixture-org',name:'Example client'}],totalCount:1})}};}`:args.path==='next/navigation'?`export function redirect(){throw Error('unexpected redirect');}export function useRouter(){return {refresh(){window.__refreshed=true;}};}`:args.path==='proof-server'?`import {data} from 'fixture';export async function proofResponse(filters={}){return {json:async()=>({...data,tenant_id:filters.tenant_id??'all'})};}`:args.path==='founder-actions'?`import {rows} from 'fixture';export async function readFounderSavingsRows(tenant,f){window.__tenant=tenant;return rows(f);}export async function readBaselineSettings(){return {tasks:[{task_type:'Find a business',standard:'sol',top:'astra',override_model:window.__baseline??null,choices:['luna','sol','astra'],quality_compared:false}],changes:window.__baseline?[{id:'change-1',task_type:'Find a business',old_model:'sol',new_model:window.__baseline,by_user:'Founder',created_at:'2026-10-21T12:00:00Z',status:'complete',rows_updated:21}]:[]};}export async function saveBaseline(task,model){window.__baseline=model;}`:`import {data,rows} from 'fixture';export async function createTask(){};export async function readClientDashboard(){return {jobs_done:7,recent:[{id:'fixture-job',title:'Business list',status:'done'}]};}export async function rigProxy(path,tenant,init){if(path.endsWith('/revision'))return {revision:String(window.__revision??0)};if(path.endsWith('/rows'))return rows(init.query);window.__reportReads=(window.__reportReads??0)+1;const {margin,excluded,tenant_id,tenants,region,...client}=data;return client;}`}));
}}]});
const js=bundle.outputFiles.find(f=>f.path.endsWith('.js')).text, css=bundle.outputFiles.find(f=>f.path.endsWith('.css')).text;
const server=createServer(async(req,res)=>{if(req.url==='/bundle.js'){res.setHeader('content-type','text/javascript');res.end(js);return;}if(req.url.startsWith('/brand/')){try{res.setHeader('content-type','image/png');res.end(await fs.readFile(path.join(root,'workspace/public',req.url)));}catch{res.writeHead(404);res.end();}return;}
res.end(`<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font-family:Arial}*{box-sizing:border-box}${css}</style></head><body><div id="root"></div><script type="module" src="/bundle.js"></script></body></html>`);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const browser=await chromium.launch({executablePath:process.env.CORE2_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
try {
 const page=await browser.newPage();page.setDefaultTimeout(10000);const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install();await page.goto(`http://127.0.0.1:${server.address().port}/client`);
 await page.getByRole('heading',{name:'What you saved',exact:true}).waitFor();
 assert.equal(await page.locator('.savings-set').count(),1);
 for(const name of ['Spent and would have cost','Saved to date','Saved this month','Done at no AI cost','Saved by team member'])assert.equal(await page.getByRole('heading',{name,exact:true}).count(),1);
 assert(!/\b(Tank|ledger|rung|margin|Skala|eval|gold|retire)\b/i.test(await page.locator('.savings-live').innerText()));
 await page.getByLabel('Show',{exact:true}).selectOption('3');assert.equal(await page.locator('.savings-daily>div').count(),82);
 await page.getByLabel('Show',{exact:true}).selectOption('12');assert.equal(await page.locator('.savings-daily>div').count(),355);
 await page.getByLabel('Show',{exact:true}).selectOption('1');
 for(const width of [1440,375]){await page.setViewportSize({width,height:900});await page.screenshot({path:path.join(out,`client-${width}.png`),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 await page.getByRole('button',{name:'$6.30 vs standard (sol)',exact:true}).first().click();
 const drawer=page.getByRole('dialog');await drawer.getByRole('heading',{name:'Business list'}).waitFor();
 assert(!/receipt-fixture|founder-model|margin/.test(await drawer.innerText()));
 await drawer.getByRole('button',{name:'Next',exact:true}).click();await page.waitForFunction(()=>window.__filters.page==='1');
 await page.screenshot({path:path.join(out,'client-drawer-375.png'),fullPage:true});
 await page.keyboard.press('Escape');assert.equal(await drawer.isVisible(),false);
 const before=await page.evaluate(()=>window.__reportReads);await page.clock.runFor(60010);assert((await page.evaluate(()=>window.__reportReads))>before);
 const after=await page.evaluate(()=>window.__reportReads);await page.evaluate(()=>window.__revision=1);await page.clock.runFor(5010);assert((await page.evaluate(()=>window.__reportReads))>after);
 await page.goto(`http://127.0.0.1:${server.address().port}/founder?selected`);
 await page.getByRole('heading',{name:'Client savings',exact:true}).waitFor();assert.equal(await page.locator('.savings-set').count(),2);
 assert.equal(await page.getByLabel('Client',{exact:true}).inputValue(),'client-fixture');
 await page.getByText('Baseline settings · founder only',{exact:true}).click();
 await page.getByLabel('Baseline for Find a business',{exact:true}).selectOption('astra');await page.getByRole('button',{name:'Save baseline and re-price',exact:true}).click();
 await page.getByText(/21 rows re-priced/).waitFor();
 assert((await page.locator('.savings-headline').first().innerText()).includes('75.0% cheaper (4.00× cheaper) than the standard model (sol)'));
 assert.equal(await page.getByLabel('Baseline for Find a business',{exact:true}).inputValue(),'astra');
 for(const width of [1440,375]){await page.setViewportSize({width,height:900});await page.screenshot({path:path.join(out,`founder-${width}.png`),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
 await page.getByRole('button',{name:'Inspect excluded rows',exact:true}).last().click();await page.getByRole('dialog').getByText(/receipt-fixture/).waitFor();assert.equal(await page.evaluate(()=>window.__tenant),'client-fixture');await page.keyboard.press('Escape');
 await page.getByRole('button',{name:'Browse evidence and export pages',exact:true}).last().click();await page.getByRole('dialog').getByRole('button',{name:'Next',exact:true}).click();
 const link=page.getByRole('dialog').getByRole('link',{name:'Export this page as CSV'});await page.waitForFunction(()=>window.__filters.page===1);const query=new URL(await link.getAttribute('href'),'http://fixture');assert.equal(query.searchParams.get('page'),'1');assert.equal(query.searchParams.get('tenant_id'),'client-fixture');
 await page.goto(`http://127.0.0.1:${server.address().port}/founder`);await page.getByRole('heading',{name:'Client savings',exact:true}).waitFor();assert.equal(await page.getByLabel('Client',{exact:true}).inputValue(),'all');
 await page.goto(`http://127.0.0.1:${server.address().port}/client?tiny`);
 await page.getByRole('heading',{name:'What you saved',exact:true}).waitFor();
 assert((await page.locator('.savings-axis').first().innerText()).includes('$0.00000001'));
 assert(!/NaN|Infinity/.test(await page.locator('.savings-chart').first().innerHTML()));
 assert.deepEqual(errors,[]);console.log('Client/founder 375px/1440px: graphs, ranges, private drawer, pagination, billing state, tenant picker, exports, 60-second refresh and job-finish refresh passed.');
} finally {await browser.close();server.close();}
