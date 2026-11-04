/* Offline browser fixtures for the actual Base TSX and server actions.
   Only Clerk, Next navigation/cache and Tank HTTP boundaries are replaced. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../..');
const template = path.join(root, 'workspace');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const { chromium } = require(process.env.BASE_TEST_PLAYWRIGHT || path.join(root, 'agents/tisan/templates/next-site/node_modules/playwright'));
const row = process.env.BASE_ACCEPTANCE_ROW;
const modules = new Map();
function bundle(file) {
  file = path.resolve(file);
  if (modules.has(file)) return file;
  modules.set(file, '');
  let code = fs.readFileSync(file, 'utf8');
  if (/\.tsx?$/.test(file)) code = ts.transpileModule(code, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020,
  }}).outputText;
  const deps = {};
  for (const match of code.matchAll(/require\(["']([^"']+)["']\)/g)) {
    const name = match[1];
    if (['next/navigation', 'next/cache', '@/lib/tenant', '@/lib/tank'].includes(name)) { deps[name] = name; continue; }
    let target;
    if (name.startsWith('.')) {
      const base = path.resolve(path.dirname(file), name);
      target = ['', '.ts', '.tsx', '.js', '/index.js'].map(x=>base+x).find(x=>fs.existsSync(x)&&fs.statSync(x).isFile());
    } else target = createRequire(path.join(template, 'package.json')).resolve(name);
    assert(target, `Cannot resolve ${name}`);
    deps[name] = bundle(target);
  }
  modules.set(file, `function(module,exports,load){const require=n=>load(${JSON.stringify(deps)}[n]);\n${code}\n}`);
  return file;
}
const entry = bundle(path.join(root, 'workspace/app/base/view.tsx'));
const react = bundle(createRequire(path.join(template, 'package.json')).resolve('react'));
const client = bundle(createRequire(path.join(template, 'package.json')).resolve('react-dom/client'));
const searchActions = bundle(path.join(root, 'workspace/app/base/search.ts'));
const panelModel = bundle(path.join(root, 'workspace/app/base/plugin-panel.ts'));
const script = `(()=>{const process={env:{NODE_ENV:'development'}};const table={${[...modules].map(([k,v])=>JSON.stringify(k)+':'+v).join(',')}};
const cached={};window.calls=[];const panel={enabled:${!['B00','B41'].includes(row)},message:null,secrets:[],files:[],links:[],connections:[]};
const tank={baseRecords:async(tenant,options)=>{
 window.calls.push({name:'baseRecords',tenant,options});
 if(tenant!=='placeholder-tenant') throw Error('wrong tenant');
 return [{id:'placeholder-record',batch:'Founder acceptance',raw:{name:'Founder Store',city:'Washington'},profile:{name:{value:'Founder Store'},website:{value:'https://placeholder.invalid/',source:'site:code'}},passes:{'2b':{gold_observation:{source_url:'https://placeholder.invalid/contact',observed_on:'2026-11-03',status:200,blocked:false}}}}];
}}; for(const name of ['saveVaultSecret','removeVaultSecret','uploadVaultFiles','removeVaultFile','addVaultLink','removeVaultLink','addVaultConnection','removeVaultConnection']) tank[name]=async(...args)=>{
 window.calls.push({name,args:args.map(v=>v instanceof FormData?'placeholder-form':v)});
 if(name==='saveVaultSecret') panel.secrets=[{name:args[4],purpose:args[5],mask:'••••••••',savedAt:null}];
 if(name==='removeVaultSecret') panel.secrets=[];
 if(name==='uploadVaultFiles') panel.files=[{id:'placeholder-file',name:'placeholder.csv',type:'CSV',size:24,rows:1,pages:null,uploadedAt:'',status:'saved'}];
 if(name==='removeVaultFile') panel.files=[];
 if(name==='addVaultLink') panel.links=[{id:'placeholder-link',url:args[4],label:args[5],frequency:args[6],lastChecked:null,status:'saved'}];
 if(name==='removeVaultLink') panel.links=[];
 if(name==='addVaultConnection') panel.connections=[{id:'placeholder-connection',name:args[4],serverUrl:args[5],authType:args[6],hasToken:true,status:'saved',lastUsed:null}];
 if(name==='removeVaultConnection') panel.connections=[];
 return {}; };
const stubs={'next/navigation':{usePathname:()=>'/base',useRouter:()=>({refresh:()=>window.render()})},'next/cache':{revalidatePath:()=>{}},'@/lib/tenant':{activeTenant:async()=>({tenantId:'placeholder-tenant',userId:'placeholder-founder'}),currentTenant:async()=>({tenantId:'placeholder-tenant',userId:'placeholder-founder'})},'@/lib/tank':tank};
function load(id){if(stubs[id])return stubs[id];if(cached[id])return cached[id].exports;const m={exports:{}};cached[id]=m;table[id](m,m.exports,load);return m.exports;}
const React=load(${JSON.stringify(react)}), dom=load(${JSON.stringify(client)}),{BaseView}=load(${JSON.stringify(entry)});
const off=load(${JSON.stringify(panelModel)}).offPanel();const app=dom.createRoot(document.getElementById('root'));
window.render=()=>app.render(React.createElement(BaseView,{plugins:panel.enabled?{...panel}:off,accountName:'placeholder founder workspace',model:{loadError:false,empty:true,totals:{records:0,withSite:0,withEmail:0,skipped:0},batches:[],skills:[],skillsError:false,refreshedLabel:""},refresh:async()=>{},search:load(${JSON.stringify(searchActions)}).searchBase,ask:load(${JSON.stringify(searchActions)}).askBase,signedIn:true}));window.render();})();`;
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.setDefaultTimeout(10000);
  const requests=[];await page.route('**/*',route=>{requests.push(route.request().url());return route.abort();});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div id="root"></div>');
  await page.addStyleTag({content:fs.readFileSync(path.join(root,'workspace/app/base/base.css'),'utf8')});
  await page.addScriptTag({content:script});
  await page.getByRole('link',{name:'Overview',exact:true}).waitFor();
  if(row==='B46') {
    await page.getByRole('link',{name:'Search',exact:true}).click();
    await page.getByLabel('Search Base records',{exact:true}).fill('Founder Store');
    await page.getByRole('button',{name:'Search',exact:true}).click();
    await page.getByText('Founder Store',{exact:true}).waitFor();
    assert(await page.getByRole('link',{name:'Source link',exact:true}).count()>=1);
    assert.equal((await page.evaluate(()=>window.calls))[0].tenant,'placeholder-tenant');
  } else if(row==='B47') {
    await page.getByRole('link',{name:'Ask Base',exact:true}).click();
    await page.getByLabel('Type a request',{exact:true}).fill('Founder Store');
    await page.getByRole('button',{name:'Send',exact:true}).click();
    await page.getByText('Sources',{exact:true}).waitFor();
    assert((await page.locator('.bcp-msg-text').last().innerText()).includes('I found 1 record that matches'));
    await page.getByLabel('Type a request',{exact:true}).fill('start a batch');
    await page.getByRole('button',{name:'Send',exact:true}).click();
    await page.getByText("I can only read records here. I can't start, re-run, restore or change anything from this box.",{exact:true}).waitFor();
    assert((await page.evaluate(()=>window.calls)).every(call=>call.name==='baseRecords'));
  } else {
   await page.getByRole('button',{name:'Plugins',exact:true}).click();
   const popup=page.getByRole('dialog');
   if(row==='B41') {
    assert(await page.getByText('This vault is off. Turn it on in Tank.',{exact:true}).first().isVisible());
    assert.deepEqual(await page.evaluate(()=>window.calls),[]);
   } else {
    const tabs={B42:'API keys',B43:'Files',B44:'Source links',B45:'MCP connections'};
    await popup.getByRole('tab',{name:tabs[row],exact:true}).click();
    if(row==='B42') {
     await popup.getByLabel('Name',{exact:true}).fill('placeholder-tool');
     await popup.getByLabel('Key',{exact:true}).fill('placeholder-key');
     await popup.getByRole('button',{name:'Save key',exact:true}).click();
     await popup.getByText('Saved. The key is hidden and will not be shown again.',{exact:true}).waitFor();
     assert(!(await page.locator('body').innerText()).includes('placeholder-key'));
    } else if(row==='B43') {
     await popup.locator('input[type=file]').setInputFiles({name:'placeholder.csv',mimeType:'text/csv',buffer:Buffer.from('name\nplaceholder\n')});
     await popup.getByText('Saved.',{exact:true}).waitFor();
     await popup.getByText('placeholder.csv',{exact:true}).waitFor();
    } else if(row==='B44') {
     await popup.getByLabel('Link',{exact:true}).fill('https://placeholder.invalid/');
     await popup.getByLabel('Label (optional)',{exact:true}).fill('placeholder source');
     await popup.getByRole('button',{name:'Add link',exact:true}).click();
     await popup.getByText('Saved.',{exact:true}).waitFor();
    } else {
     await popup.getByLabel('Name',{exact:true}).fill('placeholder MCP');
     await popup.getByLabel('Server URL',{exact:true}).fill('https://placeholder.invalid/mcp');
     await popup.locator('input[type=password]').fill('placeholder-token');
     await popup.getByRole('button',{name:'Add connection',exact:true}).click();
     await popup.getByText('Saved. A token is hidden and will not be shown again.',{exact:true}).waitFor();
     assert(!(await page.locator('body').innerText()).includes('placeholder-token'));
    }
    await popup.getByRole('button',{name:'Remove',exact:true}).click();
    await popup.getByText('Removed.',{exact:true}).waitFor();
    const calls=await page.evaluate(()=>window.calls);
    assert.equal(calls.length,2);
    assert.deepEqual(calls.map(c=>c.name),{B42:['saveVaultSecret','removeVaultSecret'],B43:['uploadVaultFiles','removeVaultFile'],B44:['addVaultLink','removeVaultLink'],B45:['addVaultConnection','removeVaultConnection']}[row]);
    assert(calls.every(c=>JSON.stringify(c.args.slice(0,4))===JSON.stringify(['base.vault','base','placeholder-tenant','placeholder-founder'])));
   }
  }
  assert.deepEqual(errors,[]);assert(requests.every(url=>!/^https?:/.test(url)));
  console.log(row+' passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
