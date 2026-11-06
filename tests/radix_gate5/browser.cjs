const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const zlib = require('node:zlib');
const root = process.argv[2];
const tools = process.env.RADIX_BROWSER_MODULES || path.resolve('tests/browser/node_modules');
const {build} = require(path.join(tools,'esbuild'));
const {chromium} = require(path.join(tools,'playwright'));
process.env.COMMAND_TEST_TOOLS = path.resolve('workspace/node_modules');
const {workspace} = require(path.join(root,'tests/command_acceptance_20261031/workspace_loader.cjs'));
const tenant='00000000-0000-0000-0000-000000000011';
let signed=false,failWrite=false,attempts=0,created=0,failRead=false;
const records=[];
const store={
  list:async owner=>{assert.equal(owner,tenant);if(failRead)throw Error('placeholder-private-error');return records;},
  get:async(owner,id)=>{assert.equal(owner,tenant);const item=records.find(item=>item.id===id);assert(item);item.status='done';return item;},
  create:async(owner,user,title,type,messages,agent)=>{
    assert.equal(owner,tenant);assert.equal(user,'placeholder-new-user');assert.equal(agent,'radix');attempts++;
    if(failWrite)throw Error('placeholder-private-error');
    const item={id:'33333333-3333-4333-8333-'+String(++created).padStart(12,'0'),tenant_id:tenant,agent,title,status:'queued',result:'Your supplied code review is ready.',created_at:new Date().toISOString()};records.push(item);return item;
  },
};
const load=workspace({env:{},fetch:()=>{throw Error('unexpected server network');},mocks:{
  '@/lib/tank':{radixTaskStore:store},'@/lib/tenant':{currentTenant:async()=>{if(!signed)throw Error('placeholder-signed-out');return {tenantId:tenant,userId:'placeholder-new-user'};}},
  'next/server':{NextResponse:{json:Response.json}},
}});
const routes=load('app/radix/requests/route.ts');
const actions=['readRadixPlugins','saveRadixKey','removeRadixSecret','removeRadixFile','addRadixLink','removeRadixLink','addRadixConnection','removeRadixConnection'];
const plugins={enabled:true,message:'',secrets:[],files:[],links:[],connections:[]};
(async()=>{
  const bundle=await build({stdin:{contents:'import React from "react";import{createRoot}from"react-dom/client";import{RadixPage}from"./app/radix/view";createRoot(document.getElementById("root")).render(<RadixPage accountName="New workspace" settings={<button>Settings</button>}/>);',resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',minify:true,plugins:[{name:'offline-boundaries',setup(b){
    b.onResolve({filter:/plugin-actions$/},()=>({path:'actions',namespace:'fake'}));
    b.onResolve({filter:/squad-links$/},()=>({path:'squads',namespace:'fake'}));
    b.onLoad({filter:/.*/,namespace:'fake'},({path:name})=>({loader:'js',contents:name==='squads'?'export function SquadLinks(){return null;}':actions.map(name=>`export async function ${name}(...args){return (await fetch('/test-action/${name}',{method:'POST',body:JSON.stringify(args)})).json();}`).join('\n')}));
  }}]});
  const script=zlib.gzipSync(bundle.outputFiles[0].contents);
  const css=fs.readFileSync(path.join(root,'workspace/app/radix/radix.css'),'utf8');
  const html='<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0;font-family:Arial}button,input,textarea{font:inherit}'+css+'</style></head><body><main><div id="root"></div></main><script src="/page.js"></script></body></html>';
  const severities=['critical','high','medium','low','info','unknown'];
  const figure=(id,value)=>({id,value,status:'available'});
  const server=http.createServer(async(req,res)=>{
    try{
      const url=new URL(req.url,'http://'+req.headers.host);
      if(url.pathname==='/sign-in'){res.setHeader('content-type','text/html');res.end('<!doctype html><html lang="en"><body><form method="post" action="/test-signup"><button>Continue</button></form></body></html>');return;}
      if(url.pathname==='/test-signup'){signed=true;res.writeHead(303,{location:'/radix'});res.end();return;}
      if(url.pathname==='/page.js'){res.writeHead(200,{'content-type':'text/javascript','content-encoding':'gzip'});res.end(script);return;}
      if(url.pathname.startsWith('/brand/')){res.setHeader('content-type','image/png');res.end(fs.readFileSync(path.join(root,'workspace/public',url.pathname)));return;}
      if(url.pathname==='/radix/requests'){
        const chunks=[];for await(const chunk of req)chunks.push(chunk);
        const incoming=new Request(url,{method:req.method,headers:req.headers,...(req.method==='GET'?{}:{body:Buffer.concat(chunks)})});
        const result=await routes[req.method](incoming);res.writeHead(result.status,Object.fromEntries(result.headers));res.end(await result.text());return;
      }
      if(url.pathname==='/api/case-studies/radix'){
        res.setHeader('content-type','application/json');res.end(JSON.stringify({product:'radix',figures:[figure('radix.scans',0),figure('radix.findings_by_severity',severities.map(id=>({id,value:0})))],tank:[figure('tank.work_by_execution',[{id:'code',value:created},{id:'cache',value:0},{id:'model',value:0}]),figure('tank.spend',0)]}));return;
      }
      if(url.pathname.startsWith('/test-action/')){
        const chunks=[];for await(const chunk of req)chunks.push(chunk);const args=JSON.parse(Buffer.concat(chunks));
        const name=url.pathname.split('/').pop();assert(actions.includes(name));
        if(name==='saveRadixKey')plugins.secrets=[{name:args[0],purpose:args[2],mask:'••••••••',saved_at:'2026-11-05'}];
        if(name==='removeRadixSecret')plugins.secrets=[];
        res.setHeader('content-type','application/json');res.end(JSON.stringify(name==='readRadixPlugins'?plugins:{ok:true,message:'Saved.'}));return;
      }
      if(!signed){res.writeHead(302,{location:'/sign-in'});res.end();return;}
      res.setHeader('content-type','text/html');res.end(html);
    }catch(error){res.writeHead(500);res.end('placeholder-test-failed');console.error(error);}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port;
  let browser;
  try{
    browser=await chromium.launch({headless:true,args:['--no-sandbox']});
    const page=await browser.newPage({viewport:{width:375,height:812},isMobile:true,deviceScaleFactor:1});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>route.request().url().startsWith(base)?route.continue():route.abort());
    const cdp=await page.context().newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
    await cdp.send('Network.enable');await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:50000,uploadThroughput:25000});
    await page.goto(base+'/radix');await page.getByRole('button',{name:'Continue',exact:true}).click();
    const started=Date.now();
    await page.getByText('No recent Radix requests. Send one below to start.',{exact:true}).waitFor();
    assert(Date.now()-started<12000,'day-zero page must become usable on the throttled phone');
    assert.equal(await page.locator('svg[aria-label="Findings by severity"] rect').count(),0);
    assert.equal(await page.locator('svg[aria-label="Findings by severity"] line').count(),5);
    await page.getByText('$0.00',{exact:true}).waitFor();
    assert.equal(await page.getByRole('button',{name:'View example report'}).count(),0);
    await page.locator('.rx-logo').first().evaluate(image=>image.decode());
    assert(await page.locator('.rx-logo').first().evaluate(image=>image.naturalWidth>0));
    await page.screenshot({path:'/tmp/radix-gate5-mobile.png'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    const menu=page.getByRole('button',{name:'Menu',exact:true});await menu.focus();await page.keyboard.press('Enter');
    for(let i=0;i<18;i++){await page.keyboard.press('Tab');assert(await page.evaluate(()=>!!document.activeElement.closest('dialog[open]')));}
    await page.keyboard.press('Escape');assert(await menu.evaluate(el=>el===document.activeElement));
    const box=page.getByLabel('Your request',{exact:true});await box.fill('Review my supplied code');
    failWrite=true;await box.press('Enter');await page.getByRole('alert').waitFor();
    assert.equal(await box.inputValue(),'Review my supplied code');assert.equal(attempts,1);assert.equal(created,0);
    assert(!(await page.content()).includes('placeholder-private-error'));
    failWrite=false;await box.press('Enter');await page.getByText('Your supplied code review is ready.',{exact:true}).waitFor();
    assert.equal(created,1);assert.equal(attempts,2);
    const receipt=page.locator('article').filter({has:page.getByRole('heading',{name:'Receipts',exact:true})});
    await page.waitForFunction(()=>[...document.querySelectorAll('article')].some(el=>el.querySelector('h2')?.textContent==='Receipts'&&el.querySelector('p')?.textContent==='1'));
    assert((await receipt.textContent()).includes('$0.00'));
    failRead=true;await page.getByRole('button',{name:'Refresh records',exact:true}).click();
    await page.getByText('Your Radix records could not load. Try again.',{exact:true}).waitFor();
    failRead=false;await page.getByRole('button',{name:'Refresh records',exact:true}).click();
    await page.getByRole('button',{name:'Review my supplied code done'}).waitFor();
    await page.clock.install();let held;
    await page.route('**/radix/requests?id=*',route=>{held=route;});
    const outgoing=page.waitForRequest(req=>req.url().includes('/radix/requests?id='));
    await page.getByRole('button',{name:'Review my supplied code done'}).click();await outgoing;
    await page.clock.fastForward(30010);await page.getByText('That Radix record could not load. Try again.',{exact:true}).waitFor();
    await held.abort().catch(()=>{});await page.unroute('**/radix/requests?id=*');
    await page.getByRole('button',{name:'Review my supplied code done'}).click();await page.getByRole('button',{name:'Use in request'}).waitFor();
    await page.setViewportSize({width:320,height:568});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    await box.focus();assert.equal(await box.evaluate(el=>getComputedStyle(el).outlineWidth),'2px');
    const ratio=await page.getByRole('button',{name:'Send',exact:true}).evaluate(el=>{
      const light=value=>{const rgb=value.match(/[\d.]+/g).slice(0,3).map(Number).map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4;});return rgb[0]*.2126+rgb[1]*.7152+rgb[2]*.0722;};
      const style=getComputedStyle(el),a=light(style.color),b=light(style.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
    });assert(ratio>=4.5);
    await page.setViewportSize({width:1440,height:900});
    await page.locator('.rx-panel').getByRole('button',{name:'Plugins',exact:true}).click();
    const dialog=page.getByRole('dialog',{name:'Plugins',exact:true});await dialog.getByRole('tab',{name:'API keys',exact:true}).focus();
    await page.keyboard.press('End');assert.equal(await dialog.getByRole('tab',{name:'MCP connections',selected:true}).count(),1);
    await dialog.getByText('No connections saved.',{exact:true}).first().waitFor();
    assert(await dialog.locator('input').evaluateAll(inputs=>inputs.every(input=>input.labels.length>0)));
    await page.keyboard.press('Escape');assert(await page.locator('.rx-panel').getByRole('button',{name:'Plugins',exact:true}).evaluate(el=>el===document.activeElement));
    assert.deepEqual(errors,[]);
    console.log('PASS: fake sign-up return, day zero, first action/result/receipt, error/retry, timeout, narrow phone, contrast, labels and keyboard focus.');
  }finally{await browser?.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
