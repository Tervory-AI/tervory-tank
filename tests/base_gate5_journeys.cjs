const jsLiteral = value => JSON.stringify(value).replace(/</g, '\\u003c').replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
/* Real Base React screens/actions. Authentication and HTTP boundaries are fake;
   the browser cannot contact any external service. */
const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const {createRequire}=require('node:module');
const {root,read}=require('./base_gate5_sources.cjs');
const req=createRequire(path.join(root,'workspace/package.json'));
const ts=req('typescript');
const {chromium}=require(process.env.BASE_TEST_PLAYWRIGHT || path.join(root,'.split-cache/browser/node_modules/playwright'));
const modules=new Map();
function bundle(file) {
 file=path.resolve(file); if(modules.has(file))return file; modules.set(file,'');
 let code=read(path.relative(root,file));
 if(/\.tsx?$/.test(file))code=ts.transpileModule(code,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText;
 const deps={};
 for(const [,name] of code.matchAll(/require\(["']([^"']+)["']\)/g)){
  if(['next/navigation','next/cache','@/lib/tenant','@/lib/tank'].includes(name)){deps[name]=name;continue;}
  const base=path.resolve(path.dirname(file),name);
  const target=name.startsWith('.')?['','.ts','.tsx','.js','/index.js'].map(e=>base+e).find(p=>fs.existsSync(p)&&fs.statSync(p).isFile()):req.resolve(name);
  assert(target,name);deps[name]=bundle(target);
 }
 modules.set(file,`function(module,exports,load){const require=n=>load(${jsLiteral(deps)}[n]);\n${code}\n}`);return file;
}
const view=bundle(path.join(root,'workspace/app/base/view.tsx'));
const react=bundle(req.resolve('react')),dom=bundle(req.resolve('react-dom/client'));
const search=bundle(path.join(root,'workspace/app/base/search.ts'));
const script=`(()=>{const process={env:{NODE_ENV:'production'}},table={${[...modules].map(([k,v])=>jsLiteral(k)+':'+v).join(',')}},cached={};
window.signedIn=false;window.tenant='placeholder-tenant-a';window.saved=false;window.calls=[];window.vaultFailure=false;
const panel={enabled:true,message:null,secrets:[],files:[],links:[],connections:[]};
const tank={baseRecords:async(tenant)=>{window.calls.push({name:'records',tenant});return window.saved&&tenant==='placeholder-tenant-a'?[{id:'record-1',batch:'First list',raw:{name:'Recorded Business',city:'Washington'},profile:{name:{value:'Recorded Business'},website:{value:'https://recorded.example',source_url:'https://recorded.example/contact',checked_at:'2026-11-05T12:00:00Z'}}}]:[];}};
for(const name of ['saveVaultSecret','removeVaultSecret','uploadVaultFiles','removeVaultFile','addVaultLink','removeVaultLink','addVaultConnection','removeVaultConnection'])tank[name]=async(...args)=>{window.calls.push({name,tenant:args[2]});if(window.vaultFailure)return new Promise(()=>{});return {};};
const stubs={'next/navigation':{usePathname:()=>'/base',useRouter:()=>({refresh(){}})},'next/cache':{revalidatePath(){}},'@/lib/tenant':{currentTenant:async()=>{if(!window.signedIn)throw Error('sign in');return {tenantId:window.tenant,userId:'placeholder-user'};},activeTenant:async()=>({tenantId:window.tenant,userId:'placeholder-user'})},'@/lib/tank':tank};
function load(id){if(stubs[id])return stubs[id];if(cached[id])return cached[id].exports;const m={exports:{}};cached[id]=m;table[id](m,m.exports,load);return m.exports;}
const React=load(${jsLiteral(react)}),app=load(${jsLiteral(dom)}).createRoot(document.getElementById('root')),BaseView=load(${jsLiteral(view)}).BaseView,actions=load(${jsLiteral(search)});
window.render=()=>app.render(React.createElement(BaseView,{key:window.tenant+window.signedIn,plugins:panel,accountName:null,model:{loadError:false,empty:true,totals:{records:0,withSite:0,withEmail:0,skipped:0},batches:[],skills:[],skillsError:false,refreshedLabel:''},refresh:async()=>{},search:actions.searchBase,ask:actions.askBase,signedIn:window.signedIn}));window.render();})();`;

async function serverRouteProofs(){
 const vm=require('node:vm'); const file='workspace/app/base/product/[...path]/route.ts';
 const code=ts.transpileModule(read(file),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 let signed=true,calls=[];const module={exports:{}};
 vm.runInNewContext(code,{exports:module.exports,require:name=>({
  '@/lib/tenant':{currentTenant:async()=>{if(!signed)throw Error();return {tenantId:'placeholder-tenant-a',userId:'placeholder-user'};}},
  '@/lib/workspace-origin':{isWorkspaceOrigin:r=>r.headers.get('origin')==='http://127.0.0.1'},
  '@/lib/tank':{baseProductRequest:async(...args)=>{calls.push(args);return Response.json({ok:true});}},
 }[name]),Request,Response,Headers,URL,URLSearchParams,Buffer,AbortSignal,Uint8Array,Promise});
 const route=module.exports.POST,ctx={params:Promise.resolve({path:['uploads']})};
 const request=(body,origin='http://127.0.0.1')=>new Request('http://127.0.0.1/base/product/uploads?tenant_id=placeholder-other',{method:'POST',headers:{origin},body});
 signed=false;assert.equal((await route(request('{}'),ctx)).status,401);signed=true;
 assert.equal((await route(request('{}','https://evil.invalid'),ctx)).status,403);
 assert.equal((await route(request('{'),ctx)).status,400);
 let cancelled=false,reads=0;
 const stream=new ReadableStream({pull(c){reads++;c.enqueue(new Uint8Array(750000));},cancel(){cancelled=true;}});
 assert.equal((await route(new Request('http://127.0.0.1/base/product/uploads',{method:'POST',headers:{origin:'http://127.0.0.1'},body:stream,duplex:'half'}),ctx)).status,413);
 assert(cancelled&&reads<=4,'Oversized upload must stop reading before buffering the full body');
 assert.equal((await route(request(JSON.stringify({tenant_id:'placeholder-other',created_by:'placeholder-other',records:[]})),ctx)).status,200);
 assert.equal(calls.length,1);assert.equal(calls[0][0],'placeholder-tenant-a');assert(!calls[0][2].has('tenant_id'));
 assert.equal(calls[0][3].tenant_id,undefined);assert.equal(calls[0][3].created_by,'placeholder-user');

 // Exercise the real shared HTTP helpers too: founder trials and engine
 // discovery intentionally have no client tenant; private reads always do.
 const tankCode=ts.transpileModule(read('workspace/lib/tank.ts'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
 const api={exports:{}};let stalled=false;const upstream=[];
 const transport=async(raw,init)=>{
   const url=new URL(String(raw));upstream.push({url,init});
   if(url.pathname.endsWith('/home'))return Response.json({tenant_id:'placeholder-tenant-a',home_region:'us-east'});
   if(stalled)return new Response(new ReadableStream({pull(){}}));
   return Response.json(url.pathname.endsWith('/trial')?{records_sent:0}:[]);
 };
 vm.runInNewContext(tankCode+'\nexports.__baseTank=tank;',{
  exports:api.exports,require:name=>name==='@/lib/trigger-signin-fetch'?{signinFetch:transport}:{regionTank:()=>null},
  process:{env:{TANK_API_KEY:'placeholder-workspace-key',TANK_URL:'http://fake',TANK_REGION:'us-east'}},
  Request,Response,Headers,URL,URLSearchParams,Buffer,AbortSignal,AbortController,ReadableStream,TextDecoder,TextEncoder,console,
  setTimeout:(fn,ms,...args)=>setTimeout(fn,ms>=5000?10:ms,...args),clearTimeout,
 });
 assert.equal((await api.exports.runContextTrial('placeholder-founder')).records_sent,0);
 assert.equal(upstream.length,1);assert.equal(upstream[0].init.headers.get('x-tervory-admin'),'placeholder-founder');
 assert.equal(upstream[0].init.headers.get('x-tank-key'),'placeholder-workspace-key');
 await api.exports.__baseTank('/v1/base/engines',{method:'GET'});
 assert.equal(upstream.length,2);
 await assert.rejects(api.exports.__baseTank('/v1/base/records',{method:'GET'}),/Sign in/);
 await api.exports.baseRecords('placeholder-tenant-a');
 assert.equal(upstream.length,4);
 assert.equal(upstream[3].url.searchParams.get('tenant_id'),'placeholder-tenant-a');
 await api.exports.listSkills(true);
 assert.equal(upstream.at(-1).url.pathname,'/v1/skala');
 stalled=true;
 await assert.rejects(api.exports.listSkills(true),/deadline/);
 assert(upstream.at(-1).init.signal.aborted,'A stalled response body must close its upstream connection');
}

(async()=>{
 await serverRouteProofs();
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  page.setDefaultTimeout(10000);
  const errors=[],external=[],writes=[],ids=new Set();let missing=false,lose=true,completed=false;
  page.on('pageerror',e=>errors.push(e.message));
  const empty={groups:[],costs:[],states:[],states_done:0,unattributed_calls:0,records_without_receipts:0};
  const ref={file:{published_on:'2026-11-01',source_url:'https://www.atf.gov/recorded.txt'},total_all:0,collectors:0,groups:[],history:[],changes:[]};
  const cost={state:'DC',month:'2026-11',rung:3,known_cost_usd:'0',cost_per_verified_record:'0',status:'priced',verified_records:1,unpriced:0};
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.hostname!=='127.0.0.1'){external.push(url.href);return route.abort();}
   if(url.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Base offline proof</title></head><body><main><div id="root"></div></main></body></html>'});
   if(!url.pathname.startsWith('/base/product/'))return route.abort();
   if(missing)return route.fulfill({status:503,json:{detail:'Missing setting: TANK_KEY_BASE'}});
   const name=url.pathname.slice('/base/product/'.length);
   if(route.request().method()==='POST'){
    const body=route.request().postDataJSON();writes.push({name,body});
    if(name==='uploads'){
     assert.equal(body.records[0].name,'Recorded Business');ids.add(body.request_id);completed=true;
     if(lose){lose=false;return route.abort('failed');}
    }
    return route.fulfill({json:{records:1,states:1}});
   }
   const field={value:'https://recorded.example',verified:true,source_url:'https://recorded.example/contact',checked_at:'2026-11-05T12:00:00Z',reason:null};
   const nil={value:null,verified:false,source_url:null,checked_at:null,reason:'unavailable'};
   const responses={reference:ref,numbers:completed?{...empty,costs:[cost],states_done:1,states:[{id:'state-1',state:'DC',name:'First list',records_count:1,status:'done'}]}:empty,
    comparison:{states:[],rows:[]},records:{total:1,rows:[{record_id:'record-1',name:'Recorded Business',state:'DC',licence_type:'01',fields:{website:field,phone:nil,email:nil,socials:nil}}]},
    ledger:{total:1,rows:[{id:'receipt-1',ts:'2026-11-05T12:00:00Z',cost_usd:'0',cost_status:'set',vendor:null,rung:3,units:'1'}]}};
   if(name==='records.csv')return route.fulfill({contentType:'text/csv',body:'name,source_url,checked_at\nRecorded Business,https://recorded.example/contact,2026-11-05\n'});
   assert(name in responses,name);return route.fulfill({json:responses[name]});
  });
  await page.goto('http://127.0.0.1/');
  await page.addStyleTag({content:read('workspace/app/base/base.css')});
  await page.addScriptTag({content:script});
  await page.getByText('Sign in to read the public reference and start your own list.',{exact:true}).waitFor();
  assert.equal(writes.length,0);
  // Complete the existing authentication boundary as a first-time client.
  await page.evaluate(()=>{window.signedIn=true;window.render();});
  await page.locator('[data-empty="costs"]').waitFor();
  assert((await page.locator('body').innerText()).includes('0 calls'));
  assert(!(await page.locator('body').innerText()).includes('Kauai'));
  const upload=page.getByLabel('Business CSV',{exact:true});
  await upload.setInputFiles({name:'first.csv',mimeType:'text/csv',buffer:Buffer.from('name,city,state\nRecorded Business,Washington,DC\n')});
  await page.getByRole('button',{name:'Upload and verify',exact:true}).click();
  await page.getByRole('alert').first().waitFor();
  await page.getByRole('button',{name:'Upload and verify',exact:true}).click();
  await page.getByText('Your list was received. Follow its states below.',{exact:true}).waitFor();
  assert.equal(ids.size,1,'Lost acknowledgements must not enqueue another job');
  assert.equal(writes.filter(w=>w.name==='uploads').length,2);
  await page.getByRole('button',{name:'View verified fields and sources',exact:true}).click();
  await page.getByRole('heading',{name:'Recorded Business · District of Columbia',exact:true}).waitFor();
  assert(await page.getByRole('link',{name:'https://recorded.example/contact',exact:true}).count());
  await page.getByRole('button',{name:'$0.000000',exact:true}).first().click();
  await page.getByLabel('Cost receipts',{exact:true}).waitFor();
  assert((await page.getByLabel('Cost receipts',{exact:true}).innerText()).includes('Showing 1 of 1 call'));
  await page.evaluate(()=>{window.saved=true;});
  await page.getByRole('link',{name:'Search',exact:true}).click();
  await page.getByLabel('Search Base records',{exact:true}).fill('Recorded Business');
  await page.getByRole('button',{name:'Search',exact:true}).click();
  await page.getByText('Recorded Business',{exact:true}).first().waitFor();
  await page.getByRole('link',{name:'Ask Base',exact:true}).click();
  await page.getByLabel('Type a request',{exact:true}).fill('start a batch');
  await page.getByRole('button',{name:'Send',exact:true}).click();
  await page.getByText("I can only read records here. I can't start, re-run, restore or change anything from this box.",{exact:true}).waitFor();
  assert.equal(writes.length,2);
  await page.getByRole('button',{name:'Plugins',exact:true}).click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();
  for(let i=0;i<24;i++){await page.keyboard.press('Tab');assert(await dialog.evaluate(el=>el.contains(document.activeElement)));}
  await page.keyboard.press('Shift+Tab');assert(await dialog.evaluate(el=>el.contains(document.activeElement)));
  await page.keyboard.press('Escape');assert.equal(await page.getByRole('dialog').count(),0);
  assert.equal(await page.evaluate(()=>document.activeElement.textContent.trim()),'Plugins');
  // A server action that never acknowledges cannot leave the dialog stuck.
  await page.evaluate(()=>{
    window.originalTimeout=window.setTimeout;
    window.setTimeout=(fn,ms,...args)=>window.originalTimeout(fn,ms===30000?20:ms,...args);
    window.vaultFailure=true;
  });
  await page.getByRole('button',{name:'Plugins',exact:true}).click();
  await page.getByRole('dialog').getByLabel('Name',{exact:true}).fill('placeholder-tool');
  await page.getByRole('dialog').getByLabel('Key',{exact:true}).fill('placeholder-private-value');
  await page.getByRole('button',{name:'Save key',exact:true}).click();
  await page.getByText('Plugins could not be loaded from Tank. No vault data is shown.',{exact:true}).waitFor();
  assert(await page.getByRole('button',{name:'Save key',exact:true}).isEnabled());
  assert(!(await page.locator('body').innerText()).includes('placeholder-private-value'));
  // Switching tabs preserves the trap and returns to the original opener.
  for(const tab of ['Files','Source links','MCP connections','API keys'])await page.getByRole('tab',{name:tab,exact:true}).click();
  await page.keyboard.press('Escape');
  assert.equal(await page.evaluate(()=>document.activeElement.textContent.trim()),'Plugins');
  await page.evaluate(()=>{window.setTimeout=window.originalTimeout;window.vaultFailure=false;});
  // Missing settings remain visible without a write or an unsafe retry.
  missing=true;
  await page.getByRole('button',{name:'View verified fields and sources',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Missing setting: TANK_KEY_BASE'}).waitFor();
  assert.equal(writes.length,2);missing=false;
  // A response body that never finishes is covered by the same total deadline.
  await page.evaluate(()=>{
    window.originalFetch=window.fetch;
    window.fetch=async()=>({ok:true,json:()=>new Promise(()=>{})});
    window.setTimeout=(fn,ms,...args)=>window.originalTimeout(fn,ms===30000?20:ms,...args);
  });
  await page.getByRole('button',{name:'View verified fields and sources',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Base is unavailable. Your existing work has not changed.'}).waitFor();
  await page.evaluate(()=>{window.fetch=window.originalFetch;window.setTimeout=window.originalTimeout;});
  // New client, no previous tenant's records; mobile/slow CPU and keyboard.
  completed=false;await page.setViewportSize({width:375,height:812});
  const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  const started=Date.now();
  await page.evaluate(()=>{window.tenant='placeholder-tenant-b';window.render();});
  await page.locator('[data-empty="costs"]').waitFor();assert(Date.now()-started<5000,'Day zero should render promptly on a slow phone');
  assert(!(await page.locator('body').innerText()).includes('Recorded Business'));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  // Every editable control has a programmatic label; all enabled controls can focus.
  const unlabeled=await page.locator('input,select,textarea').evaluateAll(nodes=>nodes.filter(el=>!el.getAttribute('aria-label')&&!el.labels?.length).map(el=>el.outerHTML));
  assert.deepEqual(unlabeled,[]);
  for(const button of await page.locator('button:visible:not([disabled])').all()){
   await button.focus();assert(await button.evaluate(el=>el===document.activeElement));
  }
  // Existing palette body text exceeds WCAG AA; focus outlines remain visible.
  const colors=await page.locator('.bcp').evaluate(el=>({fg:getComputedStyle(el).color,bg:getComputedStyle(el).backgroundColor}));
  function luminance(color){return color.match(/\d+/g).slice(0,3).map(Number).map(v=>{v/=255;return v<=.04045?v/12.92:((v+.055)/1.055)**2.4;}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);}
  assert((luminance(colors.bg)+.05)/(luminance(colors.fg)+.05)>=4.5);
  assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
  console.log('Anonymous/day-zero, first upload/result/receipt, lost acknowledgement/retry, missing setting, tenant switch, search/Ask, modal keyboard, labels, contrast and slow-phone journeys passed offline.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
