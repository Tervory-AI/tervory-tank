// Real access components, rendered with same-machine fixtures in the cloud.
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),base=path.join(root,'workspace');
const {build}=require('/tmp/access-1-tools/node_modules/esbuild');
const {chromium}=require('/tmp/access-1-tools/node_modules/playwright');
const output=path.join(root,'tests/artifacts/access-1');
(async()=>{
 fs.mkdirSync(output,{recursive:true});
 const panel={connections:[{room:'tiger',site:'https://dealer.example',terms:'yes',revoked:false,clear_pending:false,overdue:false,rotate_by:'2026-11-20T12:00:00Z',rotation_days:30}],policies:[{site:'https://dealer.example',terms:'yes',rotation_days:30}],feeds:[{distributor:'rsr',site:'https://dealer.example',source:'ftp_export',fetched_at:'2026-10-21T12:00:00Z',row_count:1240}],meta_enabled:false};
 const queue=[{id:'00000000-0000-4000-8000-000000000010',tenant_id:'00000000-0000-4000-8000-000000000011',room:'base',site:'https://dealer.example',reason:'captcha',status:'waiting',created_at:'2026-10-21T12:00:00Z',live_available:true}];
 const bundle=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {AccessView} from './app/access/view';import {AccessQueueNotice} from './app/access/queue-notice';const founder=new URL(location.href).searchParams.get('role')==='founder';createRoot(document.getElementById('root')).render(<><AccessQueueNotice/><AccessView initialSection={new URL(location.href).searchParams.get('section')==='checks'?'checks':'connections'} founder={founder} account="00000000-0000-4000-8000-000000000011" selected="" name="Your workspace" panel={${JSON.stringify(panel)}} queue={${JSON.stringify(queue)}} error=""/></>);`,resolveDir:base,loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'router-fixture',setup(b){b.onResolve({filter:/^next\/navigation$/},()=>({path:'router',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export function useRouter(){return {refresh(){}}}',loader:'js'}));}}]});
 const css=fs.readFileSync(path.join(base,'app/access/access.css'),'utf8');
 const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:'JetBrains Mono';src:url('/fonts/JetBrainsMono-latin.woff2')}*{box-sizing:border-box}body{margin:0}${css}</style></head><body><div id="root"></div><script src="/bundle.js"></script></body></html>`;
 const calls=[];let fail=false;
 const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,'http://local');
  if(url.pathname==='/bundle.js'){res.setHeader('Content-Type','text/javascript');return res.end(bundle.outputFiles[0].contents);}
  if(url.pathname.startsWith('/fonts/'))return res.end(fs.readFileSync(path.join(base,'app',url.pathname)));
  if(url.pathname==='/access/api/queue'){res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(queue));}
  if(url.pathname.startsWith('/access/api/')){const chunks=[];for await(const c of req)chunks.push(c);calls.push({path:url.pathname,body:JSON.parse(Buffer.concat(chunks).toString())});res.statusCode=fail?503:200;res.setHeader('Content-Type','application/json');return res.end(JSON.stringify(fail?{error:'Unavailable'}:{ok:true}));}
  res.setHeader('Content-Type','text/html');res.end(html);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 try{
  for(const role of ['client','founder'])for(const width of [1440,375]){
   const page=await browser.newPage({viewport:{width,height:960}});
   await page.goto(`http://127.0.0.1:${server.address().port}/?role=${role}`);await page.getByRole('heading',{name:'Your connections'}).waitFor();await page.evaluate(()=>document.fonts.ready);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'horizontal overflow');
   await page.getByRole('link',{name:'Needs a person · 1',exact:true}).waitFor();
   assert.equal(await page.getByRole('button',{name:'Site settings',exact:true}).count(),role==='founder'?1:0);
   await page.screenshot({path:path.join(output,`${role}-${width}.png`),fullPage:true});
   await page.getByRole('button',{name:/Needs a person/}).click();await page.screenshot({path:path.join(output,`checks-${role}-${width}.png`),fullPage:true});
   assert.equal(await page.getByRole('link',{name:'Open live view'}).count(),role==='founder'?1:0);
   if(role==='client'&&width===375){
    await page.getByRole('button',{name:'Connections',exact:true}).click();
    const generated=require('node:crypto').randomUUID();
    await page.getByLabel('Site address',{exact:true}).fill('https://dealer.example');await page.getByLabel('Dedicated username').fill(generated);await page.getByLabel('Password',{exact:true}).fill(generated);
    await page.getByLabel('The owner created this read-only user for this client.').check();
    await page.getByRole('button',{name:/Save connection/}).click();await page.getByRole('status').waitFor();
    assert.equal(await page.getByLabel('Password',{exact:true}).inputValue(),'');
    assert(!page.url().includes(generated));assert(!(await page.locator('body').innerText()).includes(generated));
    assert.equal(await page.evaluate(()=>localStorage.length),0);
    assert(calls.some(c=>c.path.endsWith('/credentials')&&c.body.dedicated_read_only));
    fail=true;await page.getByRole('button',{name:'Revoke now'}).click();await page.getByRole('status').filter({hasText:'Could not complete'}).waitFor();fail=false;
   }
   await page.getByRole('link',{name:'Needs a person · 1',exact:true}).click();await page.getByRole('heading',{name:'Needs a person',exact:true}).waitFor();
   await page.close();
  }
  console.log('Access UI: client/founder at 375px and 1440px; no overflow; credential fields clear; errors remain visible.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1});
