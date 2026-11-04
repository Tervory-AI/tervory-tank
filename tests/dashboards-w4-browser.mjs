// Offline production-component renders from dashboards-w4-render.cjs.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
import {execFileSync} from 'node:child_process';
const root=process.cwd();
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const output=process.env.W4_SCREENSHOTS || path.join(root,'docs/screenshots/dashboards-w4');
const base=process.env.W4_FIXTURES || '/dev/shm/dashboards-w4';
const screen=process.env.W4_SCREEN || 'founder';
await fs.mkdir(output,{recursive:true});
const bundles={};
if(screen==='client'){
  const require=createRequire(import.meta.url);
  const {build}=require(process.env.ESBUILD_MODULE);
  for(const phase of ['main','current']){
    const entry=`import React from 'react';import{createRoot}from'react-dom/client';import{createPortal}from'react-dom';import{Shell}from'./app/shell';import{DashboardGreeting}from'./app/dashboard-greeting';function Snapshot(){const[slot,setSlot]=React.useState(null);React.useEffect(()=>{setSlot(document.querySelector('[data-w4-greeting]'))},[]);return <><div style={{display:'contents'}} dangerouslySetInnerHTML={{__html:window.w4Fragment}}/>{slot&&createPortal(<DashboardGreeting firstName="placeholder"/>,slot)}</>}createRoot(document.getElementById('root')).render(<Shell founder={false} reviewer={false} readAccess={async()=>({founder:false,reviewer:false})}><Snapshot/></Shell>);`;
    const bundle=await build({stdin:{contents:entry,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,format:'esm',jsx:'automatic',loader:{'.css':'empty'},define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'offline-shell',setup(b){
      b.onLoad({filter:/product-nav\.ts$/},async args=>({loader:'ts',contents:phase==='main'?execFileSync('git',['show','981ac096:workspace/app/product-nav.ts'],{cwd:root,encoding:'utf8'}):await fs.readFile(args.path,'utf8')}));
      b.onResolve({filter:/^(@clerk\/nextjs|next\/link|next\/navigation)$/},args=>({path:args.path,namespace:'offline'}));
      b.onLoad({filter:/.*/,namespace:'offline'},args=>({loader:'js',resolveDir:path.join(root,'workspace'),contents:args.path==='@clerk/nextjs'?`export const useAuth=()=>({isLoaded:true,isSignedIn:false,userId:null});export const OrganizationSwitcher=()=>null;export const UserButton=()=>null;`:args.path==='next/link'?`import React from 'react';export default function Link({prefetch,...p}){return React.createElement('a',p)}`:`export const usePathname=()=>'/';export const useSearchParams=()=>new URLSearchParams(location.search);export const useSelectedLayoutSegments=()=>[];`}));
    }}]});
    bundles[`/${phase}/client.js`]=bundle.outputFiles[0].text;
  }
}
const server=createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://offline').pathname;
  if(bundles[pathname]){res.setHeader('Content-Type','text/javascript');res.end(bundles[pathname]);return;}
  if(screen==='client'&&/^\/(main|current)\/client\.html$/.test(pathname)){
    const phase=pathname.split('/')[1];
    const css=await fs.readFile(path.join(base,phase,'styles.css'),'utf8');
    const fragment=(await fs.readFile(path.join(base,phase,'client-fragment.html'),'utf8')).replace(/<h1>.*?<\/h1>/,'<div data-w4-greeting></div>');
    res.setHeader('Content-Type','text/html');
    res.end(`<!doctype html><html lang="en"><meta charset="utf-8"><style>${css}</style><div id="root"></div><script>window.w4Fragment=${JSON.stringify(fragment).replaceAll('<','\\u003c')}</script><script type="module" src="/${phase}/client.js"></script></html>`);return;
  }
  let file;
  if(pathname.startsWith('/brand/') || pathname.startsWith('/dashboards/'))file=path.join(root,'workspace/public',pathname);
  else if(pathname.startsWith('/fonts/'))file=path.join(root,'workspace/app',pathname);
  else if(/^\/(main|current)\/(founder|client)\.html$/.test(pathname))file=path.join(base,pathname);
  else {res.writeHead(404);res.end();return;}
  try{res.setHeader('Content-Type',({'.html':'text/html','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2'})[path.extname(file)] || 'application/octet-stream');res.end(await fs.readFile(file));}
  catch{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,args:['--no-sandbox']});
const errors=[];
try{
  for(const phase of ['main','current'])for(const width of [1440,375]){
    const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1,timezoneId:'America/Los_Angeles'});
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
    if(screen==='client')await page.clock.setFixedTime(new Date('2026-11-03T20:00:00Z'));
    await page.goto(`http://127.0.0.1:${server.address().port}/${phase}/${screen}.html`);
    if(screen==='client')await page.getByRole('heading',{name:'Good afternoon, placeholder',exact:true}).waitFor();
    await page.evaluate(()=>document.fonts.ready);
    await page.locator('img').evaluateAll(images=>Promise.all(images.map(image=>image.decode())));
    if(phase==='current'){
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${screen} ${width}: overflow`);
      const assets=await page.locator('img').evaluateAll(images=>images.map(image=>({src:image.getAttribute('src'),loaded:image.complete&&image.naturalWidth>0,width:image.width,height:image.height})));
      assert(assets.every(image=>image.loaded&&image.width>0&&image.height>0));
      if(screen==='founder'){
        assert.equal((await page.locator('.control-panel').boundingBox()).width,width,'Panel fills the viewport, not the old shared-shell cap');
        const metrics=await page.locator('.control-value').allTextContents();
        assert.deepEqual(metrics,['2','2','83','$12.75']);
        assert.deepEqual(await page.locator('.control-label').allTextContents(),['Sign-ups','Paying clients','Work done today','Spent this month']);
        assert.deepEqual(await page.locator('.control-metric-sub').allTextContents(),['+2 this week','+2 this week','37% by code, no model','']);
        assert.deepEqual(await page.locator('.control-age').allTextContents(),['1h ago','2h ago']);
        for(const name of ['Pause all paid work','Pause workers','Approve all','Switch','Later'])assert(await page.getByRole('button',{name,exact:true}).isEnabled());
        assert.equal(await page.locator('.control-needs-count').textContent(),'3');
        assert.equal(await page.locator('.control-decision-copy').nth(0).textContent(),'2 skills passed their tests');
        assert.equal(await page.locator('.control-decision-copy').nth(1).textContent(),'Cheaper model proven for placeholder market research · saves $50/mo');
        assert.equal(await page.locator('.control-decision-copy').nth(2).textContent(),'Daily check: 7 examples');
        assert.deepEqual(await page.locator('.control-squad-count').allTextContents(),['3 running','4 queued',...Array(5).fill('0 running')]);
        assert.equal(await page.locator('.control-signup-who').first().textContent(),'placeholder signup 0placeholder company 0 · placeholder country');
        assert.equal(await page.getByRole('button',{name:'Approve all',exact:true}).isEnabled(),true);
        assert.equal(await page.locator('[data-tile="workers"]').count(),0);
        assert.equal(await page.locator('.control-top>img').getAttribute('width'),'180');
        assert(!/—|Recorded spend|Approve all ready/.test(await page.locator('body').innerText()));
      }else{
        assert.equal(await page.locator('.shell-side').count(),0,'No unframed shared menu');
        assert.deepEqual(await page.locator('.dash-nav a').allTextContents(),['Home','Chats','Files','Billing','Settings']);
        assert.deepEqual(await page.locator('.dash-value').allTextContents(),['1,235','$11,765']);
        assert.equal(await page.locator('.dash-client-top>.dash-note').textContent(),'placeholder organisation');
        assert.deepEqual(await page.locator('.dash-status').allTextContents(),['Queued','In progress','Ready','Failed']);
        assert.deepEqual(await page.locator('.dash-row>a').allTextContents(),[0,1,2,3].map(i=>`placeholder requested work ${i}`));
        assert.deepEqual(await page.locator('.dash-member strong').allTextContents(),['Base','Tiger','Market Lab','Zenas']);
        assert.deepEqual(await page.locator('.dash-member .dash-note').allTextContents(),['Business lists','Prices','Market research','Legal']);
        assert.equal(await page.locator('.dash-input').getAttribute('placeholder'),'What do you need today?');
        assert.equal(await page.locator('.dash-logo img').getAttribute('width'),'180');
        assert.equal(await page.locator('#your-savings').isVisible(),false,'Report is a separate drilldown');
        const require=createRequire(import.meta.url);
        require('./client-copy.cjs')(await page.locator('body').innerText());
        assert(!/[—]/.test(await page.locator('body').innerText()));
        const found=await page.locator('.dash-client-root').boundingBox();
        assert.equal(found.width,width);
        if(width===1440)assert.equal((await page.locator('.dash-sidebar').boundingBox()).width,220);
      }
      const overflow=await page.evaluate(()=>{
        const bad=[];const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        while(walker.nextNode()){const n=walker.currentNode,e=n.parentElement;if(!n.textContent.trim()||e.closest('script,style,dialog')||!e.checkVisibility())continue;const r=document.createRange();r.selectNodeContents(n);for(const box of r.getClientRects())if(box.width&&(box.right>innerWidth+.5||box.left<-.5))bad.push(n.textContent);}
        return bad;
      });
      assert.deepEqual(overflow,[],`Text outside ${screen} ${width}`);
    }
    await page.screenshot({path:path.join(output,`${phase}-${screen}-${width}.png`),fullPage:true});
    await page.close();
  }
  assert.deepEqual(errors,[]);
  console.log(`PASS: ${screen} route-to-screen placeholder fixtures, main comparison, assets and text bounds at 1440/375. No live data or founder credentials.`);
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
