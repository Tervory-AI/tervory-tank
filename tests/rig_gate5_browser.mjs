import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
import {gzipSync} from 'node:zlib';

const root=process.cwd(), require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.RIG_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.RIG_PLAYWRIGHT_PATH || 'playwright');
const initial={products:0,product_rows:[],currency:'USD',settings:{},price_configured:false,templates:{},fits:[],missed_searches:[],receipts:[],feeds:[]};
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';
import {Lab} from './app/rig/lab';import {RetailerAdmin} from './app/rig/admin/retailer-admin';
import {CommerceAdmin} from './app/rig/admin/commerce-admin';import {ThreeDAdminScreen} from './app/rig/admin/three-d/screen';
import {ProductPreview} from './app/rig/admin/three-d/preview';
import {request} from './app/rig/request'; window.rigRequest=request;
const mode=new URLSearchParams(location.search).get('view');
const plugins={enabled:true,secrets:[],files:[],links:[],connections:[]};
createRoot(document.getElementById('root')).render(mode==='admin'?<RetailerAdmin initial={${JSON.stringify(initial)}}/>:
['connection','delivery','orders'].includes(mode)?<CommerceAdmin section={mode}/>:
mode==='preview'?<main className="three-admin"><ProductPreview id="placeholder" anchors={{}}/></main>:
mode==='three-d'?<ThreeDAdminScreen enabled jobs={[]} jobId="placeholder" action={async()=>{}}/>:
<Lab accountName="Your account" products={mode==='empty'?0:1} fits={0} plugins={plugins}/>);`;
const built=await build({stdin:{contents:entry,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,minify:true,
  write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'external-boundaries',setup(p){
    p.onResolve({filter:/^\.\/plugin-actions$|^\.\.\/squad-links$/},a=>({path:a.path,namespace:'fake'}));
    p.onLoad({filter:/.*/,namespace:'fake'},a=>({contents:a.path.includes('squad')?'export const SquadLinks=()=>null;':
      ['addRigConnectionAction','addRigLinkAction','removeRigConnectionAction','removeRigFileAction','removeRigKey','removeRigLinkAction','saveRigKey','uploadRigFileForm'].map(n=>`export async function ${n}(){if(window.pluginStall)return new Promise(()=>{});throw Error('placeholder-private');}`).join('\n')}));
  }}]});
const js=built.outputFiles[0].text;
assert(gzipSync(js).length<140000,'Rig first screen must not eagerly bundle the 3D renderer');
const css=(await Promise.all(['rig.css','admin/retailer-admin.css','admin/three-d/three-d.css'].map(n=>fs.readFile(path.join(root,'workspace/app/rig',n),'utf8')))).join('\n');
const html=`<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Rig</title><style>body{margin:0}${css}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>`;
const server=createServer((req,res)=>{res.setHeader('content-type',req.url==='/app.js'?'text/javascript':req.url.startsWith('/brand/')?'image/svg+xml':'text/html');res.end(req.url==='/app.js'?js:req.url.startsWith('/brand/')?'<svg xmlns="http://www.w3.org/2000/svg" width="186" height="34"/>':html);});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:process.env.READ1_CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});
try {
  const page=await browser.newPage(), errors=[], calls=[];
  page.setDefaultTimeout(5000);page.on('pageerror',e=>errors.push(e.message));
  let fail=false, panel=structuredClone(initial), orderDelay=0, activeOrders=0, maximumOrders=0, previewFail=true;
  await page.route('**/*',async route=>{
    const req=route.request();
    if(!req.url().startsWith(base)) return route.abort();
    if(req.url().includes('/three-d/file/draft/'))return route.fulfill({status:previewFail?503:200,body:'placeholder-model'});
    if(req.url().endsWith('/three-d/file/runtime.js'))return route.fulfill({contentType:'text/javascript',body:'export async function createStage(){return {rotate(){window.rotations=(window.rotations||0)+1},zoom(){},dispose(){}}}'});
    if(req.method()!=='POST') return route.continue();
    const body=req.postDataJSON();calls.push(body);
    if(body.operation==='commerce-orders' && orderDelay) { activeOrders++; maximumOrders=Math.max(maximumOrders,activeOrders); await new Promise(r=>setTimeout(r,orderDelay)); activeOrders--; }
    if(fail) return route.fulfill({status:503,json:{error:'placeholder-private'}});
    if(body.op==='search') {
      await new Promise(r=>setTimeout(r,body.q==='Old'?250:10));
      return route.fulfill({json:{results:[{id:body.q,name:body.q,category:'Products',price:{amount:12,currency:'USD'}}],exact_match:true}});
    }
    if(body.op==='graph') return route.fulfill({json:{branches:[]}});
    if(body.op==='ask') return route.fulfill({json:{answer:'Placeholder recorded answer',sources:[{title:'Catalogue',detail:'Recorded source'}]}});
    if(body.operation==='commerce-orders') return route.fulfill({json:{ok:true,commerce:{orders:[]}}});
    if(body.operation==='commerce-connect') return route.fulfill({json:{ok:true,commerce:{}}});
    if(body.operation==='settings') panel.settings=body.data;
    if(body.operation==='mapping') return route.fulfill({json:{ok:true,message:'',mapping:{fields:['sku','name','brand','category','price','image_url'],columns:Object.fromEntries(['sku','name','brand','category','price','image_url'].map(k=>[k,k])),required:['sku','name','brand','category','price','image_url']}}});
    if(body.operation==='import') {panel.products=1;panel.receipts=[{id:'placeholder-receipt',provider:'catalogue',site:'https://placeholder.example',added:1,updated:0,rejected:0,created_at:'2026-11-06T00:00:00Z'}];}
    return route.fulfill({json:{ok:true,message:'Saved.',panel}});
  });
  const search=async text=>{await page.getByRole('textbox',{name:'Search a brand, model or part',exact:true}).first().fill(text);await page.getByRole('textbox',{name:'Search a brand, model or part',exact:true}).first().press('Enter');};
  for(const width of [375,1440]) {
    await page.setViewportSize({width,height:1000});
    for(const view of ['empty','Overview','Catalogues','Fits to review','Skins','Progress','Plugins','Files','Source links','MCP connections','admin','connection','delivery','orders','three-d']) {
      await page.goto(base+'/?view='+encodeURIComponent(view));await page.locator('h1,.search-view').first().waitFor();
      if(['Overview','Catalogues','Fits to review','Skins','Progress','Plugins','Files','Source links','MCP connections'].includes(view)) {
        if(width===375)await page.getByRole('button',{name:'Menu',exact:true}).click();
        const plugin=['Plugins','Files','Source links','MCP connections'].includes(view);
        await page.getByRole('button',{name:plugin?'Plugins':view,exact:true}).click();
        if(plugin&&view!=='Plugins')await page.getByRole('tab',{name:view,exact:true}).click();
      }
      const problems=await page.evaluate(()=>{
        const visible=n=>n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden';
        return [...document.querySelectorAll('input:not([type=hidden]),select,textarea,button,a[href],canvas')].filter(visible).filter(n=>
          !n.disabled&&!n.getAttribute('aria-label')&&!n.getAttribute('aria-labelledby')&&!n.labels?.length&&!n.textContent.trim()&&!n.querySelector('img[alt]'))
          .map(n=>n.outerHTML.slice(0,140));
      });
      assert.deepEqual(problems,[],view+' accessible names');
      const contrast = await page.evaluate(() => {
        const rgb = text => (text.match(/[\d.]+/g)||[]).map(Number);
        const luminance = c => c.slice(0,3).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;}).reduce((v,n,i)=>v+n*[.2126,.7152,.0722][i],0);
        const failures=[];
        for(const node of document.querySelectorAll('p,label,h1,h2,h3,h4,button,a,small,span,th,td')) {
          if(!node.getClientRects().length||!node.textContent.trim()||node.children.length||node.disabled) continue;
          const style=getComputedStyle(node);if(style.visibility==='hidden')continue;
          const layers=[];for(let n=node;n;n=n.parentElement) layers.unshift(rgb(getComputedStyle(n).backgroundColor));
          let bg=[255,255,255];for(const layer of layers){const a=layer[3]??1;bg=bg.map((n,i)=>layer[i]*a+n*(1-a));}
          const fg=rgb(style.color);const a=fg[3]??1;const color=fg.map((n,i)=>n*a+bg[i]*(1-a));
          const l1=luminance(bg),l2=luminance(color),ratio=(Math.max(l1,l2)+.05)/(Math.min(l1,l2)+.05);
          const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&parseInt(style.fontWeight)>=700);
          if(ratio<(large?3:4.5)-.01) failures.push({text:node.textContent.trim().slice(0,35),color:style.color,ratio:ratio.toFixed(2)});
        }return failures;
      });
      assert.deepEqual(contrast,[],view+' text contrast');

      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),view+' overflow');
    }
    await page.goto(base);fail=true;await search('Camera');
    await page.getByRole('status').filter({hasText:'Rig did not answer. Try again.'}).waitFor();
    assert(!(await page.locator('body').innerText()).includes('placeholder-private'));
    fail=false;await search('Camera');await page.getByRole('heading',{name:'Camera',exact:true}).waitFor();
    await search('Old');await search('New');await page.getByRole('heading',{name:'New',exact:true}).waitFor();
    await page.waitForTimeout(300);assert.equal(await page.getByRole('heading',{name:'Old',exact:true}).count(),0);
    if(width===375) await page.getByRole('button',{name:'Menu',exact:true}).click();
    const opener=page.getByRole('button',{name:'Plugins',exact:true});await opener.click();
    const dialog=page.getByRole('dialog');await dialog.waitFor();
    assert(await dialog.evaluate(n=>n.contains(document.activeElement)));
    await page.keyboard.press('Shift+Tab');assert(await dialog.evaluate(n=>n.contains(document.activeElement)));
    await page.getByLabel('Key name',{exact:true}).fill('placeholder');
    await page.getByLabel('Key',{exact:true}).fill('placeholder-private');
    await page.evaluate(()=>{window.pluginStall=true;const original=window.setTimeout;window.setTimeout=(call,ms,...args)=>original(call,ms===35000?20:ms,...args);});
    await page.getByRole('button',{name:'Save key',exact:true}).click();
    await page.getByRole('status').filter({hasText:'Rig did not answer. Try again.'}).waitFor();
    assert(await page.getByRole('button',{name:'Save key',exact:true}).isEnabled());
    assert(!(await dialog.innerText()).includes('placeholder-private'));
    await page.getByRole('tab',{name:'API keys',exact:true}).focus();await page.keyboard.press('ArrowRight');
    assert.equal(await page.getByRole('tab',{name:'Files',exact:true}).getAttribute('aria-selected'),'true');
    await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
    // Mobile hides its nav when opening a dialog; focus must still return to a visible control.
    assert(await (width===1440?opener:page.getByRole("button",{name:"Menu",exact:true})).evaluate(n=>n===document.activeElement));
  }
  await page.goto(base+'/?view=preview');await page.getByRole('button',{name:'Open product preview',exact:true}).click();
  await page.getByRole('status').filter({hasText:'The preview could not be opened. Try again before approving.'}).waitFor();
  previewFail=false;await page.getByRole('button',{name:'Open product preview',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Check the product from every side.'}).waitFor();
  await page.locator('canvas').focus();await page.keyboard.press('ArrowRight');assert.equal(await page.evaluate(()=>window.rotations),1);
  await page.goto(base+'/?view=admin');
  await page.getByLabel('Store name',{exact:true}).fill('Placeholder shop');
  await page.getByLabel('Quote delivery email',{exact:true}).fill('placeholder@example.com');
  fail=true;await page.getByRole('button',{name:'Save delivery settings'}).click();
  await page.getByText('The operation was not confirmed. Check the import history before retrying.',{exact:true}).waitFor();
  fail=false;await page.getByRole('button',{name:'Save delivery settings'}).click();await page.getByText('Saved.',{exact:true}).waitFor();
  await page.getByLabel('Feed name',{exact:true}).fill('placeholder');
  await page.getByLabel('Supplier or store website',{exact:true}).fill('https://placeholder.example');
  await page.getByLabel('Feed currency',{exact:true}).fill('USD');await page.getByLabel('Country code',{exact:true}).fill('US');
  await page.getByLabel('Catalogue file',{exact:true}).setInputFiles({name:'placeholder.csv',mimeType:'text/csv',buffer:Buffer.from('sku,name,brand,category,price,image_url\nplaceholder,Placeholder,Placeholder,Parts,12,https://placeholder.example/photo.jpg\n')});
  await page.getByRole('button',{name:'Suggest field mapping',exact:true}).click();
  await page.getByLabel("I checked this mapping and the feed's currency, country and price type.",{exact:true}).check();
  await page.getByRole('button',{name:'Publish catalogue',exact:true}).click();
  await page.locator('.retailer-history article').waitFor();assert.equal(calls.filter(c=>c.operation==='import').length,1);
  // A stalled response body must abort too, with exactly one attempt.
  const deadline=await page.evaluate(async()=>{
    const original=window.fetch;let count=0,aborted=false;
    window.fetch=async(_url,init)=>{count++;init.signal.addEventListener('abort',()=>aborted=true);return {json:()=>new Promise(()=>{})};};
    try {await window.rigRequest('/placeholder',{},r=>r.json(),20);return null;}
    catch(e){return {count,aborted,message:e.message};}finally{window.fetch=original;}
  });
  assert.deepEqual(deadline,{count:1,aborted:true,message:'Rig did not answer. Try again.'});
  await page.addInitScript(()=>{const original=window.setInterval;window.setInterval=(call,ms,...args)=>original(call,ms===5000?20:ms,...args);});
  const before=calls.filter(c=>c.operation==='commerce-orders').length;
  orderDelay=40;fail=true;await page.goto(base+'/?view=orders');
  await page.getByRole('alert').filter({hasText:'Rig did not answer. Try again.'}).waitFor();
  await page.waitForTimeout(420);
  assert.equal(calls.filter(c=>c.operation==='commerce-orders').length-before,6);
  assert.equal(maximumOrders,1,'order polls must not overlap');
  fail=false;orderDelay=0;await page.reload();await page.getByRole('link',{name:'Shop connection',exact:true}).waitFor();
  assert.equal(await page.getByRole('alert').count(),0);
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  await cdp.send('Network.enable');await cdp.send('Network.emulateNetworkConditions',{offline:false,latency:150,downloadThroughput:750000/8,uploadThroughput:250000/8});
  const started=Date.now();await page.goto(base+'/?view=empty');await page.locator('.results-line a').waitFor();
  assert(Date.now()-started<8000,'day zero usable on a throttled phone');
  assert.deepEqual(errors,[]);
  console.log('PASS: zero-data, search/error/retry/races, retailer import/receipt, keyboard dialogs, screen labels/overflow, bounded body, slow phone.');
} finally {await browser.close();await new Promise(r=>server.close(r));}
