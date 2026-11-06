const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const http = require('node:http');
const {gzipSync}=require('node:zlib');
const {spawn} = require('node:child_process');
const {once} = require('node:events');
const {loader,bundle,realRequire,root} = require('./skala_gate5_support.cjs');
const React=realRequire('react');
const {renderToString}=realRequire('react-dom/server');
const sources=JSON.parse(fs.readFileSync(0,'utf8'));
const read=name=>sources[path.join(root,name)]??fs.readFileSync(path.join(root,name),'utf8');
const pause=ms=>new Promise(r=>setTimeout(r,ms));
let role=null, rows=[], failure=false, malformedEval=true, refreshFailures=0, seen=[], receipts=[], goldChecked=false, configured=true;
const tenant='00000000-0000-0000-0000-000000000099';
const example='00000000-0000-0000-0000-000000000088';
const seed=()=>({id:'base.offline',version:'1.0.0',agent:'base',rung:3,task_type:null,description:'',state:'candidate',last_eval_score:null,last_eval_at:null,present:true});
const result={skill:'base.offline@1.0.0',score:1,passed:5,total:5,threshold:1,cost_usd:0,state:'staging',gate:'passed',details:Array.from({length:5},(_,i)=>({case:i,name:'offline case '+i,passed:true,why:'ok',goal:{ok:true},result:{ok:true}}))};
const completedEvals=new Map();
const reply=(body,status=200)=>Response.json(body,{status});
async function provider(raw,init={}) {
  const url=new URL(raw); assert.equal(url.hostname,'tank.test');
  const headers=new Headers(init.headers); assert.equal(headers.get('x-tank-key'),'offline-placeholder');
  const body=init.body?JSON.parse(init.body):{};
  seen.push({path:url.pathname,body,key:headers.get('idempotency-key'),tenant:headers.get('x-tervory-tenant')});
  if(url.pathname.startsWith('/v1/tenants/'))return reply({tenant_id:tenant,home_region:'us-east'});
  if(url.pathname==='/v1/skala'){if(refreshFailures>0){refreshFailures--;return reply({},503);}return reply(rows);}
  if(url.pathname==='/v1/skala/approvals/status')return reply([]);
  if(url.pathname.endsWith('/evals')) {
    if(failure){failure=false;return reply({detail:'offline-private-placeholder'},502);}
    if(completedEvals.has(headers.get('idempotency-key')))return reply(completedEvals.get(headers.get('idempotency-key')));
    rows[0]={...rows[0],state:'staging',last_eval_score:1,last_eval_at:'2026-11-07T00:00:00Z'};
    receipts.push({action:'evals',key:headers.get('idempotency-key')});refreshFailures=2;completedEvals.set(headers.get('idempotency-key'),result);if(malformedEval){malformedEval=false;return reply({});} return reply(result);
  }
  if(url.pathname.endsWith('/approve')||url.pathname.endsWith('/rollback')) {
    rows[0]={...rows[0],state:'approved',approved_at:'2026-11-07T00:00:00Z'};
    receipts.push({action:'approve',by:body.by});return reply({ok:true});
  }
  if(url.pathname.endsWith('/retire')){rows[0].state='retired';receipts.push({action:'retire'});return reply({ok:true});}
  if(url.pathname==='/v1/skala/approvals/preview')return reply({token:'offline-preview',items:[{id:rows[0].id,version:rows[0].version,score:1,runs:1,model:false}]});
  if(url.pathname==='/v1/skala/approvals/confirm'){assert.equal(body.token,'offline-preview');rows[0].state='approved';receipts.push({action:'bulk'});return reply({approved:[rows[0]]});}
  if(url.pathname.endsWith('/source-review'))return reply({files:[{path:'run.py',source:'async def run(payload, ctx): return payload'}],review_token:'offline-review'});
  if(url.pathname==='/v1/gold/summary')return reply({region:'us-east',pairs:{zenas:goldChecked?1:0},skills:[{agent:'zenas',skill_id:'zenas.offline',checked:goldChecked?1:0,target:100,candidates:goldChecked?0:1,holdout:0,last_score:null,trend:null,ran_at:null}]});
  if(url.pathname==='/v1/gold/next')return reply(goldChecked?null:{id:example,input:{record:'offline'},expected:{ok:true},source:'package'});
  if(url.pathname.endsWith('/check')){assert.equal(headers.get('x-tervory-user'),'offline-user');goldChecked=true;receipts.push({action:body.action,tenant:headers.get('x-tervory-tenant')});return reply({ok:true});}
  throw new Error('Unexpected fake provider path '+url.pathname);
}
function appLoader() {
 return loader(sources,{
  '@/lib/trigger-signin-fetch':{signinFetch:provider}, '@/app/api/zenas/tank':{regionTank:()=>null},
  '@/lib/trigger-signin':{auth:async()=>({userId:role?'offline-user':null,orgRole:role})},
  '@/app/review/access':{rejectUnlessFounder:async()=>role==='founder'?null:{status:404,error:'Not found'},requireReviewer:async()=>{if(role!=='reviewer')throw new Error('Not found');}},
  '@/lib/tenant':{currentTenant:async()=>({userId:'offline-user',tenantId:tenant}),activeTenant:async()=>null},
  'next/navigation':{notFound(){throw new Error('Not found');}},
  'next/server':{NextResponse:{json:(body,init)=>Response.json(body,init)}},
 },{}, {TANK_API_KEY:configured?'offline-placeholder':'',TANK_URL:'http://tank.test'});
}
let currentBundle='';
const server=http.createServer(async(req,res)=>{
 try {
  const load=appLoader();
  if(req.url==='/bundle.js'){res.setHeader('Content-Type','text/javascript');res.setHeader('Content-Encoding','gzip');return res.end(gzipSync(currentBundle));}
  if(req.url.startsWith('/brand/')){
    res.setHeader('Content-Type','image/png');return res.end(fs.readFileSync(path.join(root,'workspace/public/brand/skala-on-dark.png')));
  }
  if(req.url.startsWith('/api/')) {
    const chunks=[];for await(const chunk of req)chunks.push(chunk);
    const url='http://'+req.headers.host+req.url;
    const request=new Request(url,{method:req.method,headers:req.headers,...(req.method==='GET'?{}:{body:Buffer.concat(chunks)})});
    const api=load(req.url.startsWith('/api/skala/gold')?'workspace/app/api/skala/gold/route.ts':'workspace/app/api/skala/route.ts');
    const response=await api[req.method](request);res.statusCode=response.status;
    res.setHeader('Content-Type','application/json');return res.end(Buffer.from(await response.arrayBuffer()));
  }
  async function servePage(page, entry, stylesheet) {
    const element=await load(page).default();
    currentBundle=bundle(sources,entry,element.props);
    const css=read(stylesheet);
    res.setHeader('Content-Type','text/html');return res.end('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Skala</title><style>body{margin:0}'+css+'</style></head><body><main id="root">'+renderToString(element)+'</main><script src="/bundle.js"></script></body></html>');
  }
  if(req.url==='/skala')return await servePage('workspace/app/skala/page.tsx','view.tsx','workspace/app/skala/skala.css');
  if(req.url==='/skala/gold')return await servePage('workspace/app/skala/gold/page.tsx','gold/view.tsx','workspace/app/skala/gold/gold.css');
  res.statusCode=404;res.end('Not found');
 } catch(error){res.statusCode=error.message==='Not found'?404:500;res.end(error.message==='Not found'?'Not found':'Offline app failed');}
});
class CDP {
 constructor(ws){this.ws=ws;this.id=0;this.waiting=new Map();this.events=[];ws.addEventListener('message',event=>{const m=JSON.parse(event.data);if(m.id){const p=this.waiting.get(m.id);this.waiting.delete(m.id);m.error?p.reject(new Error(JSON.stringify(m.error))):p.resolve(m.result);}else{this.events.push(m);}});}
 call(method,params={}){const id=++this.id;return new Promise((resolve,reject)=>{this.waiting.set(id,{resolve,reject});this.ws.send(JSON.stringify({id,method,params}));});}
 async evaluate(expression){const r=await this.call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw new Error(JSON.stringify(r.exceptionDetails));return r.result.value;}
 async until(expression){for(let i=0;i<160;i++){if(await this.evaluate('Boolean('+expression+')'))return;await pause(50);}throw new Error('Browser condition timed out: '+expression+'\n'+await this.evaluate('document.body.innerText'));}
 async click(text,selector='button'){await this.until(`Array.from(document.querySelectorAll(${JSON.stringify(selector)})).some(e=>e.textContent.trim()===${JSON.stringify(text)}&&!e.disabled)`);const point=await this.evaluate(`(()=>{const e=Array.from(document.querySelectorAll(${JSON.stringify(selector)})).find(e=>e.textContent.trim()===${JSON.stringify(text)}&&!e.disabled);e.scrollIntoView({block:'center'});const r=e.getBoundingClientRect();return {x:r.x+r.width/2,y:r.y+r.height/2};})()`);await this.call('Input.dispatchMouseEvent',{type:'mousePressed',button:'left',clickCount:1,...point});await this.call('Input.dispatchMouseEvent',{type:'mouseReleased',button:'left',clickCount:1,...point});}
}
async function contrastCheck(cdp) {
  const contrast=await cdp.evaluate(`(()=>{const rgb=s=>(s.match(/[\\d.]+/g)||[]).slice(0,3).map(Number);const lum=c=>c.map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4}).reduce((n,v,i)=>n+v*[.2126,.7152,.0722][i],0);const low=[];for(const e of document.querySelectorAll('button,a,p,h1,h2,h3,label,dt,dd,span,summary')){if(!e.getBoundingClientRect().width||!e.innerText?.trim()||e.disabled||getComputedStyle(e).visibility==='hidden')continue;const s=getComputedStyle(e);let b=e,bg='rgb(255,255,255)';while(b){const c=getComputedStyle(b).backgroundColor;if(c!=='rgba(0, 0, 0, 0)'&&c!=='transparent'){bg=c;break;}b=b.parentElement;}const x=lum(rgb(s.color)),y=lum(rgb(bg));const ratio=(Math.max(x,y)+.05)/(Math.min(x,y)+.05);const large=parseFloat(s.fontSize)>=24||(parseFloat(s.fontSize)>=18.66&&parseInt(s.fontWeight)>=700);if(ratio<(large?3:4.5))low.push({text:e.innerText.slice(0,35),ratio});}return low;})()`);
  assert.deepEqual(contrast,[]);
}
(async()=>{
 const profile=fs.mkdtempSync(path.join(os.tmpdir(),'skala-browser-'));
 let browser,cdp;
 server.listen(0,'127.0.0.1');await once(server,'listening');
 const origin='http://127.0.0.1:'+server.address().port;
 try {
  browser=spawn('/usr/bin/chromium',['--headless','--no-sandbox','--disable-dev-shm-usage','--disable-background-networking','--disable-component-update','--disable-sync','--no-first-run','--no-proxy-server','--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1','--remote-debugging-port=0','--remote-debugging-address=127.0.0.1','--user-data-dir='+profile,'about:blank'],{stdio:['ignore','ignore','pipe'],detached:true});
  let diagnostics='';browser.stderr.on('data',chunk=>{diagnostics+=chunk;});
  const active=path.join(profile,'DevToolsActivePort');
  // Cold hosted runners can take over five seconds before DevTools is ready.
  const startupDeadline=Date.now()+30000;
  while(!fs.existsSync(active)&&browser.exitCode===null&&browser.signalCode===null&&Date.now()<startupDeadline)await pause(50);
  assert.ok(fs.existsSync(active),'Chromium did not become ready within 30s: '+diagnostics.slice(-1000));
  const port=fs.readFileSync(active,'utf8').split('\n')[0];
  const targets=await(await fetch('http://127.0.0.1:'+port+'/json/list')).json();
  const ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);await once(ws,'open');cdp=new CDP(ws);
  await cdp.call('Page.enable');await cdp.call('Runtime.enable');await cdp.call('Network.enable');
  await cdp.call('Page.addScriptToEvaluateOnNewDocument',{source:'window.layoutShift=0;window.layoutEvents=[];new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput){window.layoutShift+=entry.value;window.layoutEvents.push({value:entry.value,sources:entry.sources.map(s=>({tag:s.node?.tagName,cls:s.node?.className,from:s.previousRect.y,to:s.currentRect.y,height:s.currentRect.height}))});}}).observe({type:"layout-shift",buffered:true});'});
  await cdp.call('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:true});
  await cdp.call('Emulation.setFocusEmulationEnabled',{enabled:true});
  await cdp.call('Emulation.setCPUThrottlingRate',{rate:4});
  await cdp.call('Network.emulateNetworkConditions',{offline:false,latency:100,downloadThroughput:100000,uploadThroughput:50000});
  async function navigate(page){cdp.events=[];await cdp.call('Page.navigate',{url:origin+page});await cdp.until('document.readyState==="complete"');}
  await navigate('/skala');assert.equal(await cdp.evaluate('document.body.innerText'),'Not found');assert.equal(seen.length,0);
  role='member';await navigate('/skala');assert.equal(await cdp.evaluate('document.body.innerText'),'Not found');assert.equal(seen.length,0);
  role='founder';await navigate('/skala');await cdp.until('document.body.innerText.includes("No skills yet.")');
  assert.ok(await cdp.evaluate('Array.from(document.querySelectorAll("button")).find(e=>e.textContent==="Approve all ready").disabled'));
  await contrastCheck(cdp);
  assert.equal(await cdp.evaluate('document.documentElement.scrollWidth>innerWidth'),false);
  assert.ok(await cdp.evaluate('window.layoutShift')<0.1);
  // Narrow navigation is unreachable while closed and returns focus on Escape.
  assert.equal(await cdp.evaluate('getComputedStyle(document.querySelector(".sk-panel")).visibility'),'hidden');
  await cdp.click('Menu');await cdp.until('document.activeElement.classList.contains("sk-close")');
  await cdp.call('Input.dispatchKeyEvent',{type:'keyDown',key:'Escape',code:'Escape'});
  await cdp.until('document.activeElement.classList.contains("sk-menu")');
  rows=[seed()];failure=true;await navigate('/skala');
  await cdp.evaluate('const run=Array.from(document.querySelectorAll("button")).find(e=>e.textContent==="Run evals");run.click();run.click()');await cdp.until('document.querySelector("[role=alert]")');
  assert.doesNotMatch(await cdp.evaluate('document.body.innerText'),/offline-private-placeholder/);
  await cdp.click('Run evals');await cdp.until('document.body.innerText.includes("Evals could not be run")');
  await cdp.click('Run evals');await cdp.until('document.querySelectorAll(".sk-cases article").length===5');
  const evals=seen.filter(r=>r.path.endsWith('/evals'));assert.equal(evals.length,3);assert.equal(evals[0].key,evals[1].key);assert.equal(evals[1].key,evals[2].key);assert.ok(evals[0].key);
  assert.equal(receipts.filter(r=>r.action==='evals').length,1);
  await cdp.until('document.querySelector("[role=alert]")?.textContent.includes("could not be reached")');
  assert.equal(refreshFailures,0);
  await navigate('/skala');
  await cdp.click('Approve');await cdp.until('document.querySelector("dialog[open]")');
  await cdp.click('Approve','dialog[open] button');await cdp.until('!document.querySelector("dialog[open]")&&document.querySelector(".sk-state.approved")');
  assert.equal(receipts.filter(r=>r.action==='approve').length,1);assert.equal(receipts.find(r=>r.action==='approve').by,'offline-user');
  rows=[{...seed(),state:'staging',last_eval_score:1}];await navigate('/skala');
  await cdp.click('Approve all ready');await cdp.until('document.querySelector("dialog[open]")');
  await cdp.click('Confirm listed approvals');await cdp.until('document.body.innerText.includes("1 versions approved")');assert.equal(receipts.filter(r=>r.action==='bulk').length,1);
  rows=[seed()];await navigate('/skala');await cdp.click('Retire');await cdp.until('document.body.innerText.includes("is retired")');assert.equal(receipts.filter(r=>r.action==='retire').length,1);
  rows=[{...seed(),state:'staging',approved_at:'2026-11-01T00:00:00Z'}];await navigate('/skala');await cdp.click('Roll back to 1.0.0');await cdp.click('Confirm rollback');await cdp.until('!document.querySelector("dialog[open]")&&document.querySelector(".sk-state.approved")');
  rows=[{...seed(),id:'base.learned.offline',state:'staging'}];await navigate('/skala');await cdp.click('Approve');await cdp.until('document.querySelector(".sk-source")');await cdp.click('Cancel','dialog[open] button');
  configured=false;const prior=seen.length;await navigate('/skala');await cdp.until('document.body.innerText.includes("Missing setting: TANK_API_KEY.")');assert.equal(seen.length,prior);
  await navigate('/skala/gold');await cdp.until('document.body.innerText.includes("Missing setting: TANK_API_KEY.")');assert.equal(seen.length,prior);
  configured=true;role='reviewer';await navigate('/skala/gold');await cdp.until('document.querySelector(".gold-example")');
  // Real keyboard activation, no pointer: check the first example once.
  await cdp.until('Array.from(document.querySelectorAll("button")).some(e=>e.textContent.startsWith("Right")&&!e.disabled)');
  await cdp.evaluate('Array.from(document.querySelectorAll("button")).find(e=>e.textContent.startsWith("Right")).focus()');
  await cdp.until('document.activeElement.textContent.startsWith("Right")');
  await cdp.call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r',unmodifiedText:'\r'});
  await cdp.call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await cdp.until('document.body.innerText.includes("Checked. Thank you.")');assert.equal(receipts.filter(r=>r.action==='right').length,1);
  goldChecked=false;
  await cdp.evaluate('document.querySelector(".gold-scope select").focus()');
  await cdp.call('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
  await cdp.call('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});
  await cdp.call('Input.dispatchKeyEvent',{type:'keyDown',key:'Enter',code:'Enter',windowsVirtualKeyCode:13,text:'\r'});
  await cdp.call('Input.dispatchKeyEvent',{type:'keyUp',key:'Enter',code:'Enter',windowsVirtualKeyCode:13});
  await cdp.until('document.querySelector(".gold-scope select").value==="tenant"');
  await cdp.until('document.querySelector(".gold-example")');
  await cdp.click('Wrong W');
  await cdp.until('document.querySelector(".gold-correction textarea")');
  await cdp.evaluate('(()=>{const box=document.querySelector(".gold-correction textarea");Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set.call(box,"not json");box.dispatchEvent(new Event("input",{bubbles:true}));})()');
  await cdp.click('Save correction');await cdp.until('document.body.innerText.includes("Enter the corrected answer")');
  await cdp.evaluate('(()=>{const box=document.querySelector(".gold-correction textarea");Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set.call(box,JSON.stringify({ok:false}));box.dispatchEvent(new Event("input",{bubbles:true}));})()');
  await cdp.click('Save correction');await cdp.until('document.body.innerText.includes("Wrong answer rejected")');
  assert.equal(receipts.find(r=>r.action==='wrong').tenant,tenant);
  const metrics=await cdp.evaluate(`(()=>{const controls=[...document.querySelectorAll('button,input,select,textarea')].filter(e=>e.getBoundingClientRect().width&&!e.disabled);return {overflow:document.documentElement.scrollWidth>innerWidth,unlabelled:controls.filter(e=>!e.textContent.trim()&&!e.getAttribute('aria-label')&&!e.labels?.length).length,targets:controls.every(e=>e.getBoundingClientRect().height>=44),load:performance.getEntriesByType('navigation')[0].loadEventEnd,cls:window.layoutShift,shifts:window.layoutEvents};})()`);
  assert.equal(metrics.overflow,false);assert.equal(metrics.unlabelled,0);assert.equal(metrics.targets,true);assert.ok(metrics.load<10000,JSON.stringify(metrics));assert.ok(metrics.cls<0.1,JSON.stringify(metrics));
  assert.ok(gzipSync(currentBundle).length<200000,'Compressed production browser bundle budget: '+gzipSync(currentBundle).length);
  await contrastCheck(cdp);
  const crashes=cdp.events.filter(e=>e.method==='Runtime.exceptionThrown');assert.deepEqual(crashes,[]);
  console.log('Skala browser journeys passed: identity, day zero, eval result, receipts, approval, rollback, retirement, bulk, source review, retry, missing settings, reviewer, keyboard, phone layout and slow load.');
 } finally {
  cdp?.ws.close();
  if(browser && browser.exitCode===null && browser.signalCode===null) {
    const closed = once(browser,'close');
    const stop = signal => {try {process.kill(-browser.pid,signal);} catch(error) {if(error.code!=='ESRCH')throw error;}};
    stop('SIGTERM');
    const settled = await Promise.race([closed.then(()=>true),pause(3000).then(()=>false)]);
    if(!settled){stop('SIGKILL');await closed;}
  }
  server.closeAllConnections();await new Promise(resolve=>server.close(resolve));await fs.promises.rm(profile,{recursive:true,force:true,maxRetries:5,retryDelay:100});
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
