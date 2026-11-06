const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '../..');
const proposed = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const width = Number(process.argv[3]);
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const {chromium} = require(path.join(process.env.TIGER_TEST_TOOLS, 'playwright'));
const template = path.join(root, 'workspace');
const modules = new Map();
function read(file) {return proposed[path.relative(root, file)] ?? fs.readFileSync(file, 'utf8');}
const boundaries = ['next/navigation', 'next/cache', '@/lib/tenant', '@/lib/tank', '../squad-links'];
function bundle(file) {
  file = path.resolve(file);
  if (modules.has(file)) return file;
  modules.set(file, '');
  let code = read(file);
  if (/\.tsx?$/.test(file)) code = ts.transpileModule(code, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020,
  }}).outputText;
  const deps = {};
  for (const match of code.matchAll(/require\(["']([^"']+)["']\)/g)) {
    const name = match[1];
    if (boundaries.includes(name)) {deps[name] = name; continue;}
    const base = path.resolve(path.dirname(file), name);
    const target = name.startsWith('.') ? ['', '.ts', '.tsx', '.js', '/index.js'].map(s => base+s).find(p => fs.existsSync(p))
      : createRequire(path.join(template, 'package.json')).resolve(name);
    assert(target, name); deps[name] = bundle(target);
  }
  modules.set(file, `function(module,exports,load){const require=n=>load(${JSON.stringify(deps)}[n]);\n${code}\n}`);
  return file;
}
const entries = {};
for (const [name, file] of Object.entries({view:'app/tiger/view.tsx', loader:'app/tiger/load.ts', chart:'app/prices/chart.tsx', prices:'app/prices/page.tsx'})) entries[name] = bundle(path.join(template,file));
const req = createRequire(path.join(template,'package.json'));
entries.react = bundle(req.resolve('react')); entries.dom = bundle(req.resolve('react-dom/client'));
const script = `(()=>{const process={env:{NODE_ENV:'development'}};
const table={${[...modules].map(([k,v])=>JSON.stringify(k)+':'+v).join(',')}};
const cached={}, entry=${JSON.stringify(entries)};
window.signedIn=false;window.failNext=false;window.failPlugin=false;window.failDecision=false;window.calls=[];
const actor={tenantId:${JSON.stringify(process.env.TIGER_JOURNEY_TENANT)},userId:'placeholder-new-user'};
const panel={enabled:true,message:null,secrets:[],files:[],links:[],connections:[]};
let comparison={positions:[],matches:[],sites:[],plugins:panel};
let route={tab:'overview',notice:''},version=0;
window.room=async(method,path,body)=>{
 const response=await fetch('https://placeholder.invalid/room'+path,{method,headers:{'Content-Type':'application/json','X-Tank-Key':'placeholder-room-key'},body:body===undefined?undefined:JSON.stringify(body)});
 if(!response.ok) throw Error('Tiger '+response.status+': '+await response.text());
 return response.status===204?null:response.json();
};
const q=tenant=>'?tenant_id='+encodeURIComponent(tenant);
const tank={
 VAULT_OFF_MESSAGE:'This vault is off. Turn it on in Tank.',
 listTigerWatches:tenant=>window.room('GET','/watchlist'+q(tenant)),
 listTigerAlerts:tenant=>window.room('GET','/alerts'+q(tenant)),
 listTigerObservations:(tenant,url)=>window.room('GET','/observations'+q(tenant)+'&url='+encodeURIComponent(url)),
 createTigerWatch:async(tenant,body)=>{window.calls.push('watch');if(window.failNext){window.failNext=false;throw Error('Tiger 503');}return window.room('POST','/watchlist',{...body,tenant_id:tenant});},
 deleteTigerWatch:(tenant,id)=>window.room('DELETE','/watchlist/'+id+q(tenant)),
 decideTigerMatch:async(actor,id,decision)=>{window.calls.push('decision');if(window.failDecision){window.failDecision=false;throw Error('placeholder outage');}const result={...comparison.matches[0],state:decision==='confirm'?'confirmed':'rejected'};comparison.matches=[];return result;},
};
for(const name of ['saveVaultSecret','removeVaultSecret','uploadVaultFiles','removeVaultFile','addVaultLink','removeVaultLink','addVaultConnection','removeVaultConnection']) tank[name]=async(...args)=>{
 window.calls.push(name);if(window.failPlugin){window.failPlugin=false;throw Error('placeholder private diagnostic');}
 await new Promise(r=>setTimeout(r,30));
 if(name==='saveVaultSecret')panel.secrets=[{name:args[4],purpose:args[5],mask:'••••••••'}];
 if(name==='removeVaultSecret')panel.secrets=[];
 if(name==='uploadVaultFiles')panel.files=[{id:'placeholder-file',name:'placeholder.csv',type:'CSV',status:'saved'}];
 if(name==='removeVaultFile')panel.files=[];
 if(name==='addVaultLink')panel.links=[{id:'placeholder-link',url:args[4],label:args[5],status:'saved'}];
 if(name==='removeVaultLink')panel.links=[];
 if(name==='addVaultConnection')panel.connections=[{id:'placeholder-connection',name:args[4],serverUrl:args[5],hasToken:true,status:'saved'}];
 if(name==='removeVaultConnection')panel.connections=[];
 return {};
};
const identity=async()=>window.signedIn?actor:null;
const stubs={'@/lib/tank':tank,'@/lib/tenant':{activeTenant:identity,currentTenant:async()=>{if(!window.signedIn)throw Error('Trigger sign-in required');return actor;}},
 '../squad-links':{SquadLinks:()=>null},'next/cache':{revalidatePath:()=>{}},
 'next/navigation':{useRouter:()=>({refresh:()=>window.render()}),redirect:url=>{throw {redirect:url};}}};
function load(id){if(stubs[id])return stubs[id];if(cached[id])return cached[id].exports;const m={exports:{}};cached[id]=m;table[id](m,m.exports,load);
 if(id.endsWith('/actions.ts'))for(const name of Object.keys(m.exports)){const fn=m.exports[name];m.exports[name]=async(...args)=>{try{return await fn(...args);}catch(error){if(error.redirect){await window.navigate(error.redirect);return;}throw error;}};}return m.exports;}
const React=load(entry.react),dom=load(entry.dom),app=dom.createRoot(document.getElementById('root'));
window.render=async()=>{const loaded=await load(entry.loader).loadTiger();app.render(React.createElement(load(entry.view).TigerApp,{key:version,data:loaded.data,notice:route.notice||loaded.notice||'',initialTab:route.tab,accountName:window.signedIn?'New organisation':null,comparison}));};
window.navigate=async(url)=>{if(url.startsWith('/prices'))return window.prices(url);const params=new URL(url,'https://placeholder.invalid').searchParams;route={tab:params.get('tab')||'overview',notice:params.get('notice')||''};version++;await window.render();};
window.unavailable=async()=>{comparison={...comparison,positions:null,matches:null,sites:null};await window.navigate('/tiger?tab=watch');};
window.withMatch=async()=>{comparison={positions:[],sites:[],plugins:panel,matches:[{id:'33333333-3333-4333-8333-333333333333',sku:'receipt-sku',state:'suggested',method:'brand_mpn',url:'https://store.example/item',seen_on:'https://store.example/item',product:{name:'Verified product'},identifiers:{own:{brand:'Verified',mpn:'P1'},seen:{brand:'Verified',mpn:'P1'}}}]};await window.navigate('/tiger?tab=watch');};
window.missing=async()=>{panel.enabled=false;panel.message=tank.VAULT_OFF_MESSAGE;await window.navigate('/tiger?tab=watch');};
window.prices=async(url='/prices')=>{const params=new URL(url,'https://placeholder.invalid').searchParams;app.render(await load(entry.prices).default({searchParams:Promise.resolve({notice:params.get('notice')||''})}));};
window.cls=0;new PerformanceObserver(list=>{for(const item of list.getEntries())if(!item.hadRecentInput)window.cls+=item.value;}).observe({type:'layout-shift',buffered:true});
window.render();})();`;
new (require('node:vm').Script)(script, {filename: 'offline-journey-bundle.js'});

(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width,height:900}});
  page.setDefaultTimeout(10000);
  const cdp=await page.context().newCDPSession(page);
  await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  const errors=[],remote=[];page.on('pageerror',e=>{errors.push(e.message);console.error('browser:',e.stack);});
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());
   if(url.origin==='https://placeholder.invalid'&&url.pathname.startsWith('/room/')) {
    const response=await fetch(process.env.TIGER_JOURNEY_API+url.pathname.slice(5)+url.search,{method:route.request().method(),headers:route.request().headers(),body:route.request().postData()||undefined});
    const body=await response.text();
    await new Promise(resolve=>setTimeout(resolve,150+Buffer.byteLength(body)/64));
    return route.fulfill({status:response.status,body,headers:{'content-type':'application/json','access-control-allow-origin':'*'}});
   }
   if(url.origin==='https://placeholder.invalid'&&url.pathname.startsWith('/brand/')) {
    const file=path.join(template,'public',url.pathname);
    if(fs.existsSync(file))return route.fulfill({path:file});
   }
   remote.push(url.href);return route.abort();
  });
  await page.setContent('<html><head><base href="https://placeholder.invalid/"></head><body style="margin:0"><main id="root"></main></body></html>');
  await page.addStyleTag({content:fs.readFileSync(path.join(template,'app/globals.css'),'utf8')+read(path.join(template,'app/tiger/tiger.css'))+read(path.join(template,'app/prices/prices.css'))});
  const started=Date.now();await page.addScriptTag({content:script});
  await page.getByRole('heading',{name:'Tiger',exact:true}).waitFor();
  assert(Date.now()-started<10000,'slow-phone first render exceeded the existing 10s read deadline');
  async function audit(){
   const failures=await page.evaluate(()=>{
    const shown=el=>el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden';
    const issues=[];
    for(const el of document.querySelectorAll('input:not([type=hidden]),select,textarea,button,a[href]')) {
     if(!shown(el)||el.disabled)continue;
     const labelled=el.getAttribute('aria-label')||el.textContent?.trim()||Array.from(el.labels||[]).some(label=>label.textContent.trim())||el.querySelector('img[alt]');
     if(!labelled)issues.push('unlabelled '+el.outerHTML.slice(0,160));
     if(el.tabIndex<0)issues.push('unreachable '+el.outerHTML.slice(0,160));
    }
    const rgb=value=>(value.match(/[\d.]+/g)||[]).map(Number);
    const over=(top,bottom)=>top.slice(0,3).map((v,i)=>v*(top[3]??1)+bottom[i]*(1-(top[3]??1)));
    const light=c=>c.map(v=>v/255).map(v=>v<=.04045?v/12.92:((v+.055)/1.055)**2.4).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
    for(const el of document.querySelectorAll('p,span,b,a,button,label,th,td,dt,dd,h1,h2,h3,legend')) {
     if(!shown(el)||el.closest('button:disabled')||![...el.childNodes].some(n=>n.nodeType===3&&n.textContent.trim()))continue;
     const style=getComputedStyle(el),parents=[];
     for(let p=el;p;p=p.parentElement)parents.push(p);
     let background=[255,255,255];for(const p of parents.reverse())background=over(rgb(getComputedStyle(p).backgroundColor),background);
     const foreground=over(rgb(style.color),background),a=light(foreground),b=light(background),contrast=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);
     const large=parseFloat(style.fontSize)>=24||(parseFloat(style.fontSize)>=18.66&&Number(style.fontWeight)>=700);
     if(contrast<(large?3:4.5))issues.push('contrast '+contrast.toFixed(2)+' '+el.tagName+'.'+el.className+' '+el.textContent.trim().slice(0,60));
    }
    return issues;
   });assert.deepEqual(failures,[]);
  }
  await audit();
  async function section(name){if(width<761)await page.getByRole('button',{name:'Menu',exact:true}).click();await page.getByRole('button',{name,exact:true}).click();}
  async function add(){await page.getByRole('button',{name:'Add a product',exact:true}).click();assert(await page.getByRole('button',{name:'Close',exact:true}).evaluate(el=>el===document.activeElement));await page.getByLabel(/^Product page link/).fill('https://placeholder.example/item');}
  await add();await page.getByRole('button',{name:'Start watching',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Sign in to add a product.'}).waitFor();
  assert.equal(await page.evaluate(()=>window.calls.length),0);
  // Trigger owns sign-up. Its verified new-tenant result is the only fake
  // identity boundary; every following product route is the real ASGI room.
  await page.evaluate(async()=>{window.signedIn=true;await window.navigate('/tiger');});
  await page.locator('.count b').first().waitFor();
  assert.deepEqual(await page.locator('.count b').allTextContents(),['0','0']);
  await add();await page.getByRole('button',{name:'Close',exact:true}).focus();
  await page.keyboard.press('Shift+Tab');assert(await page.getByRole('button',{name:'Start watching',exact:true}).evaluate(el=>el===document.activeElement));
  await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'hidden'});
  assert(await page.getByRole('button',{name:'Add a product',exact:true}).evaluate(el=>el===document.activeElement));
  await page.evaluate(()=>window.failNext=true);await add();await page.getByRole('button',{name:'Start watching',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Tiger is not reachable right now.'}).waitFor();
  await section('Overview');await add();await page.getByRole('button',{name:'Start watching',exact:true}).click();
  await page.getByRole('dialog').waitFor({state:'hidden'});
  await page.evaluate(()=>window.room('POST','/fixture/settle',{}));
  await page.evaluate(()=>window.navigate('/tiger'));
  await page.getByText('$120.00',{exact:false}).filter({visible:true}).first().waitFor();
  await section('History');assert(await page.getByText('$120.00',{exact:true}).filter({visible:true}).first().isVisible());await audit();
  await page.evaluate(()=>window.room('POST','/fixture/settle',{failure:true}));
  await page.evaluate(()=>window.navigate('/tiger?tab=history'));
  await page.getByText(/Not checked —/).filter({visible:true}).first().waitFor();
  await page.evaluate(()=>window.room('POST','/fixture/settle',{price:115}));
  await page.evaluate(()=>window.navigate('/tiger?tab=alerts'));
  await page.getByText('$115.00',{exact:true}).filter({visible:true}).first().waitFor();
  await audit();
  await page.evaluate(()=>window.unavailable());
  await page.getByRole('alert').filter({hasText:'Tiger is not reachable right now.'}).waitFor();
  await page.getByRole('button',{name:'Try again',exact:true}).click();
  await page.evaluate(()=>window.withMatch());
  await page.getByRole('tab',{name:'Matches to review',exact:true}).click();
  await page.evaluate(()=>window.failDecision=true);
  await page.getByRole('button',{name:'Confirm',exact:true}).filter({visible:true}).first().click();
  await page.getByRole('button',{name:'Try again',exact:true}).filter({visible:true}).first().click();
  await page.getByRole('button',{name:'Confirm',exact:true}).filter({visible:true}).first().click();
  await page.getByText('No matches to review.',{exact:true}).waitFor();
  await audit();
  await page.getByRole('tab',{name:'Competitor sites',exact:true}).click();
  await page.getByRole('button',{name:'Tiger Plugins → Source links',exact:true}).click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();
  for(const name of ['API keys','Files','Source links','MCP connections']) {
   await dialog.getByRole('tab',{name,exact:true}).click();
   await audit();
   const unnamed=await dialog.locator('input:not([type=hidden]), select, button').evaluateAll(items=>items.filter(el=>el.getClientRects().length&&!((el.getAttribute('aria-label')||el.textContent||'').trim()||Array.from(el.labels||[]).some(label=>label.textContent.trim()))).map(el=>el.outerHTML));
   assert.deepEqual(unnamed,[]);
  }
  await dialog.getByRole('tab',{name:'API keys',exact:true}).click();
  await dialog.getByLabel('Name',{exact:true}).fill('placeholder-key-name');await dialog.getByLabel('Key',{exact:true}).fill('placeholder-private-value');
  await page.evaluate(()=>window.failPlugin=true);await dialog.getByRole('button',{name:'Save key',exact:true}).click();
  await dialog.getByRole('status').filter({hasText:'The key was not saved.'}).waitFor();
  assert(!(await page.locator('body').innerText()).includes('placeholder-private-value'));
  await dialog.getByLabel('Name',{exact:true}).fill('placeholder-key-name');await dialog.getByLabel('Key',{exact:true}).fill('placeholder-private-value');
  await dialog.getByRole('button',{name:'Save key',exact:true}).dblclick();
  await dialog.getByRole('status').filter({hasText:'Saved. The key is hidden'}).waitFor();
  assert.equal(await page.evaluate(()=>window.calls.filter(name=>name==='saveVaultSecret').length),2);
  await dialog.getByRole('button',{name:'Remove',exact:true}).click();
  await dialog.getByRole('status').filter({hasText:'Removed.'}).waitFor();
  await dialog.getByRole('tab',{name:'Files',exact:true}).click();
  await dialog.locator('input[type=file]').setInputFiles({name:'placeholder.csv',mimeType:'text/csv',buffer:Buffer.from('id\nplaceholder\n')});
  await dialog.getByRole('cell',{name:'placeholder.csv',exact:true}).waitFor();await audit();
  await dialog.getByRole('button',{name:'Remove',exact:true}).click();await dialog.getByText('No files stored.',{exact:true}).waitFor();
  await dialog.getByRole('tab',{name:'Source links',exact:true}).click();
  await dialog.getByLabel('Link',{exact:true}).fill('https://store.example/item');await dialog.getByLabel('Label (optional)',{exact:true}).fill('Source');
  await dialog.getByRole('button',{name:'Weekly',exact:true}).click();await dialog.getByRole('button',{name:'Add link',exact:true}).click();
  await dialog.getByText('https://store.example/item',{exact:true}).waitFor();await audit();
  await dialog.getByRole('button',{name:'Remove',exact:true}).click();await dialog.getByText('No links stored.',{exact:true}).waitFor();
  await dialog.getByRole('tab',{name:'MCP connections',exact:true}).click();
  await dialog.getByLabel('Name',{exact:true}).fill('Source');await dialog.getByLabel('Server URL',{exact:true}).fill('https://store.example');
  await dialog.getByLabel('Token',{exact:true}).fill('placeholder-private-token');await dialog.getByRole('button',{name:'Add connection',exact:true}).click();
  await dialog.getByRole('button',{name:'Disconnect',exact:true}).waitFor();await audit();
  assert(!(await page.locator('body').innerText()).includes('placeholder-private-token'));
  await dialog.getByRole('button',{name:'Disconnect',exact:true}).click();await dialog.getByRole('status').filter({hasText:'Removed.'}).waitFor();
  await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
  await page.evaluate(()=>window.prices());await page.getByRole('img',{name:'Price history',exact:true}).waitFor();
  await audit();
  assert(await page.getByRole('button',{name:'Stop watching',exact:true}).isVisible());
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth+1);assert(!overflow,'phone page overflow');
  await page.getByRole('button',{name:'Stop watching',exact:true}).click();
  await page.getByText('Nothing is being watched yet. Add a page above.',{exact:true}).waitFor();
  await page.getByLabel('Page address',{exact:true}).fill('https://placeholder.example/item');
  await page.getByRole('button',{name:'Watch this page',exact:true}).click();
  await page.getByRole('button',{name:'Stop watching',exact:true}).waitFor();
  await page.evaluate(()=>window.missing());
  await page.getByRole('tab',{name:'Competitor sites',exact:true}).click();
  await page.getByRole('button',{name:'Tiger Plugins → Source links',exact:true}).click();
  await page.getByText('This vault is off. Turn it on in Tank.',{exact:true}).waitFor();
  assert.equal(await page.getByRole('dialog').locator('input').count(),0);await audit();
  assert((await page.evaluate(()=>window.cls))<0.1,'layout shifted after rendering');
  assert.deepEqual(errors,[]);assert(remote.every(url=>url.startsWith('https://placeholder.invalid/')));
  console.log('journeys passed at '+width);
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
