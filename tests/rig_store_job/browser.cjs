/* Real admin -> Tank -> Rig -> Postgres -> SMTP proof. Only Clerk's external
 * session boundary and public DNS are replaced with local fixture routing. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createServer } = require('node:http');
const { AsyncLocalStorage } = require('node:async_hooks');
const { randomBytes } = require('node:crypto');
const root = path.resolve(__dirname, '../..');
const proof = process.env.RIG_PROOF_DIR || '/tmp/rig-works';
const { build } = require(process.env.RIG_ESBUILD_PATH || 'esbuild');
const { chromium } = require(process.env.RIG_PLAYWRIGHT_PATH || 'playwright');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const config = Object.fromEntries(fs.readFileSync(path.join(proof,'common.env'),'utf8').trim().split('\n').map(line => [line.slice(0,line.indexOf('=')),line.slice(line.indexOf('=')+1)]));
const fixtures = JSON.parse(fs.readFileSync(path.join(proof,'fixture.json'),'utf8'));
const sessions = new Map();
const session = new AsyncLocalStorage();
const tankUrl = process.env.RIG_TANK_URL || 'http://127.0.0.1:18000';
const rigUrl = process.env.RIG_API_URL || 'http://127.0.0.1:18001';
function moduleFrom(relative, bindings) {
  const compiled = ts.transpileModule(fs.readFileSync(path.join(root,relative),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const exports = {};
  vm.runInNewContext(compiled,{exports,require:name=>{assert(name in bindings);return bindings[name];},process:{env:{...config,TANK_URL:tankUrl}},fetch,URL,URLSearchParams,Headers,Response,Request,Uint8Array,TextDecoder,Set,Error,AbortSignal});
  return exports;
}
const tank = moduleFrom('workspace/lib/tank.ts',{'@/app/api/zenas/tank':moduleFrom('workspace/app/api/zenas/tank.ts',{})});
const actions = moduleFrom('workspace/app/rig/admin/actions.ts',{
  '@clerk/nextjs/server':{auth:async()=>({userId:session.getStore()?.userId,orgRole:session.getStore()?'org:admin':null})},
  '@/lib/tenant':{activeTenant:async()=>session.getStore()},
  '../../review/founder':{isListedFounder:()=>false},
  '@/lib/tank':tank,
});
const route = moduleFrom('workspace/app/rig/admin/api/route.ts',{
  'next/server':{NextResponse:{json:(body,options)=>Response.json(body,options)}},'../actions':actions,
});
const csv = `sku,name,brand,category,price,image_url,quantity,fits_sku,fit_evidence
LAMP,Desk Light,Fixture Store,lighting,100,https://store-a.rig.test/light.svg,10,,
SHADE,Light Shade,Fixture Store,shade,20,https://store-a.rig.test/light.svg,10,LAMP,Supplier confirms this shade mounts on Desk Light.
STAND,Light Stand,Fixture Store,stand,30,https://store-a.rig.test/light.svg,10,LAMP,Supplier confirms this stand mounts on Desk Light.
`;
async function main() {
  const built = await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {RetailerAdmin} from './app/rig/admin/retailer-admin';createRoot(document.getElementById('root')).render(<RetailerAdmin initial={window.__panel}/>);`,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
  const css = fs.readFileSync(path.join(root,'workspace/app/rig/admin/retailer-admin.css'),'utf8');
  const server = createServer(async(req,res)=>{
    try {
      const url=new URL(req.url,'https://app.rig.test');
      if(url.pathname.startsWith('/fixture/sign-in/')) {
        const which=url.pathname.endsWith('/b')?'b':'a';const id=randomBytes(32).toString('hex');
        sessions.set(id,{tenantId:fixtures['store_'+which],userId:'fixture-owner-'+which});
        res.writeHead(302,{'location':'/rig/admin','set-cookie':`fixture_session=${id}; Path=/; HttpOnly; SameSite=Strict`});res.end();return;
      }
      const id=(req.headers.cookie||'').match(/fixture_session=([^;]+)/)?.[1];
      await session.run(sessions.get(id),async()=>{
        if(url.pathname==='/rig/admin/api') {
          const chunks=[];for await(const c of req)chunks.push(c);
          const response=await route.POST(new Request('https://app.rig.test/rig/admin/api',{method:'POST',headers:{...req.headers,host:'app.rig.test'},body:Buffer.concat(chunks)}));
          res.writeHead(response.status,Object.fromEntries(response.headers));res.end(await response.text());return;
        }
        if(url.pathname==='/rig/admin') {
          const actor=await actions.retailerIdentity();const panel=await tank.rigAdminPanel(actor);
          res.setHeader('content-type','text/html');res.end(`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head><body><div id="root"></div><script>window.__panel=${JSON.stringify(panel).replaceAll('<','\\u003c')}</script><script src="/admin.js"></script></body></html>`);return;
        }
        if(url.pathname==='/admin.js'){res.setHeader('content-type','text/javascript');res.end(built.outputFiles[0].text);return;}
        res.setHeader('content-type','text/html');res.end('<a href="/fixture/sign-in/a">Sign in to fixture store A</a><a href="/fixture/sign-in/b">Sign in to fixture store B</a>');
      });
    }catch{res.writeHead(500);res.end('Fixture request failed');}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const adminUrl=`http://127.0.0.1:${server.address().port}`;
  const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',args:['--no-sandbox']});
  const errors=[];
  const outputs={};
  try {
    async function context() {
      const ctx=await browser.newContext({viewport:{width:1440,height:1100}});
      await ctx.route('https://app.rig.test/**',async r=>r.fulfill({response:await r.fetch({url:adminUrl+new URL(r.request().url()).pathname,headers:r.request().headers()})}));
      await ctx.route('https://rig.tervory.com/**',async r=>r.fulfill({response:await r.fetch({url:rigUrl+new URL(r.request().url()).pathname+new URL(r.request().url()).search,headers:r.request().headers()})}));
      // Fixture product images; all catalogue/API responses come from real Rig.
      await ctx.route('https://store-a.rig.test/light.svg',r=>r.fulfill({contentType:'image/svg+xml',body:'<svg xmlns="http://www.w3.org/2000/svg" width="80" height="80"><path fill="#001840" d="M20 45 30 10h20l10 35H20m17 0h6v25H20v-5h17z"/></svg>'}));
      return ctx;
    }
    const a=await context();const page=await a.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.goto('https://app.rig.test/');await page.getByRole('link',{name:'Sign in to fixture store A',exact:true}).click();
    await page.getByRole('heading',{name:'Retailer settings',exact:true}).waitFor();
    await page.getByLabel('Store name',{exact:true}).fill('Fixture Store A');
    await page.getByLabel('Quote delivery email').fill('store-a@rig.test');
    await page.getByRole('button',{name:'Save delivery settings'}).click();await page.getByRole('status').filter({hasText:'Saved.'}).waitFor();
    await page.getByLabel('Feed name',{exact:true}).fill('own-catalogue');
    await page.getByLabel('Supplier or store website').fill('https://store-a.rig.test');
    await page.getByLabel('Feed currency',{exact:true}).fill('ZAR');await page.getByLabel('Country code',{exact:true}).fill('ZA');
    await page.getByRole('combobox',{name:/Prices are/}).selectOption('selling');
    await page.getByLabel('Catalogue file',{exact:true}).setInputFiles({name:'store-a.csv',mimeType:'text/csv',buffer:Buffer.from(csv)});
    await page.getByRole('button',{name:'Suggest field mapping'}).click();
    await page.getByLabel('I checked this mapping',{exact:false}).check();
    await page.getByRole('button',{name:'Publish catalogue',exact:true}).click();
    await page.getByRole('status').filter({hasText:'3 added, 0 updated, 0 rejected.'}).waitFor({timeout:30000});
    console.log('PASS store A fixture sign-in -> real admin CSV upload -> mapping confirmation -> publish: 3 products');
    const approve=page.getByRole('button',{name:'Approve',exact:true});
    while(await approve.count()) {await approve.first().click();await page.waitForFunction(()=>!document.querySelector('fieldset[disabled]'));}
    await page.getByLabel('Product category',{exact:true}).fill('lighting');await page.getByLabel('Included categories, separated by commas').fill('shade,stand');
    await page.getByRole('button',{name:'Save template'}).click();await page.getByText('shade · stand',{exact:true}).waitFor();
    await page.getByLabel('Website origin',{exact:true}).fill('https://store-a.rig.test');await page.getByRole('button',{name:'Create embed key'}).click();
    await page.getByLabel('Widget snippet',{exact:true}).waitFor().catch(async()=>{throw new Error('Embed handoff: '+await page.locator('.retailer-notice').innerText());});
    const snippet=await page.getByLabel('Widget snippet',{exact:true}).inputValue();const key=await page.getByLabel('Publishable embed key',{exact:true}).inputValue();
    assert(snippet.includes(key));outputs.key_a=key;
    fs.writeFileSync(path.join(proof,'store-a-snippet.html'),snippet,{mode:0o600});
    for(const width of [1440,390]) {await page.setViewportSize({width,height:1100});await page.screenshot({path:path.join(proof,`admin-${width}.png`),fullPage:true,mask:[page.getByLabel('Publishable embed key',{exact:true}),page.getByLabel('Widget snippet',{exact:true})]});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
    console.log('PASS own origin-bound embed key + exact shipped snippet; admin checked at 1440/390px');
    await a.route('https://store-a.rig.test/',r=>r.fulfill({contentType:'text/html',body:`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body>${snippet}</body></html>`}));
    await page.setViewportSize({width:1440,height:1000});await page.goto('https://store-a.rig.test/');
    await page.getByRole('searchbox').fill('Desk Light');await page.getByRole('button',{name:'Search',exact:true}).click();
    await page.locator('.card',{hasText:'Desk Light'}).getByRole('button',{name:'Complete my setup',exact:true}).click();
    await page.getByRole('button',{name:/Request a quote for this setup/}).first().waitFor({timeout:30000});
    assert(!/sample/i.test(await page.locator('tervory-rig').innerText()));
    for(const width of [1440,390]) {await page.setViewportSize({width,height:1100});await page.screenshot({path:path.join(proof,`widget-${width}.png`),fullPage:true});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));}
    await page.getByRole('button',{name:/Request a quote for this setup/}).first().click();
    await page.locator('#quote-name').fill('Fixture Shopper');await page.locator('#quote-email').fill('shopper@rig.test');
    const responsePromise=page.waitForResponse(r=>new URL(r.url()).pathname==='/v1/rig/quote');
    await page.getByRole('button',{name:'Send request',exact:true}).click();const response=await responsePromise;const ack=await response.json();
    assert.equal(response.status(),200);assert.equal(ack.delivery,'sent');outputs.quote=ack.request_id;
    console.log(`PASS installed snippet -> search -> approved setup -> quote ${ack.request_id}: email delivery sent`);
    const b=await context();const other=await b.newPage();await other.goto('https://app.rig.test/');await other.getByRole('link',{name:'Sign in to fixture store B',exact:true}).click();
    assert((await other.locator('.retailer-count').innerText()).startsWith('0 products'));
    assert.equal(await other.getByLabel('Store name',{exact:true}).inputValue(),'');assert.equal(await other.getByLabel('Quote delivery email').inputValue(),'');
    assert.equal(await other.getByLabel('Publishable embed key',{exact:true}).count(),0);assert(await other.getByRole('button',{name:'Create embed key'}).isDisabled());
    const hostile=await other.evaluate(async tenant=>{const r=await fetch('/rig/admin/api',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({operation:'settings',data:{tenant_id:tenant,name:'Fixture Store B',email:'store-b@rig.test'}})});return r.json();},fixtures.store_a);
    assert.equal(hostile.ok,true);assert.equal(hostile.panel.products,0);assert.equal(hostile.panel.settings.name,'Fixture Store B');
    const fresh=await session.run({tenantId:fixtures.store_a,userId:'fixture-owner-a'},()=>tank.rigAdminPanel({tenantId:fixtures.store_a,userId:'fixture-owner-a'}));assert.equal(fresh.settings.email,'store-a@rig.test');
    console.log('PASS store B admin sees no store A catalogue, key, delivery settings or receipts; injected tenant override ignored');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(proof,'browser-result.json'),JSON.stringify(outputs),{mode:0o600});
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
