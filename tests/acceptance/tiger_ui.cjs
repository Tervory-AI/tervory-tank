/* Offline browser fixtures for the actual Tiger TSX and server actions.
   Only Clerk, Next navigation/cache and Tank HTTP boundaries are replaced. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '../..');
const template = path.join(root, 'workspace');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const { chromium } = require(path.join(process.env.TIGER_TEST_TOOLS || path.join(root, '.tmp/browser/node_modules'), 'playwright'));
const id = process.env.TIGER_ACCEPTANCE_ROW;
const row = {TG33:'T02', TG34:'T03', TG35:'T04', TG36:'T05', TG37:'T06'}[id];
assert(row, 'Unknown Tiger plugin acceptance row');
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
const entry = bundle(path.join(root, 'workspace/app/tiger/plugins.tsx'));
const react = bundle(createRequire(path.join(template, 'package.json')).resolve('react'));
const client = bundle(createRequire(path.join(template, 'package.json')).resolve('react-dom/client'));
const panelModel = bundle(path.join(root, 'workspace/app/tiger/plugins-data.ts'));
const script = `(()=>{const process={env:{NODE_ENV:'development'}};const table={${[...modules].map(([k,v])=>JSON.stringify(k)+':'+v).join(',')}};
const cached={};window.calls=[];const panel={enabled:${!['T01','T02'].includes(row)},message:null,secrets:[],files:[],links:[],connections:[]};
const tank={}; for(const name of ['saveVaultSecret','removeVaultSecret','uploadVaultFiles','removeVaultFile','addVaultLink','removeVaultLink','addVaultConnection','removeVaultConnection']) tank[name]=async(...args)=>{
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
const stubs={'next/navigation':{usePathname:()=>'/tiger',useRouter:()=>({refresh:()=>window.render()})},'next/cache':{revalidatePath:()=>window.render()},'@/lib/tenant':{activeTenant:async()=>({tenantId:'placeholder-tenant',userId:'placeholder-founder'})},'@/lib/tank':tank};
function load(id){if(stubs[id])return stubs[id];if(cached[id])return cached[id].exports;const m={exports:{}};cached[id]=m;table[id](m,m.exports,load);return m.exports;}
const React=load(${JSON.stringify(react)}), dom=load(${JSON.stringify(client)}),{Plugins}=load(${JSON.stringify(entry)});
const off=load(${JSON.stringify(panelModel)}).offPanel();const app=dom.createRoot(document.getElementById('root'));
window.render=()=>app.render(React.createElement(Plugins,{plugins:panel.enabled?{...panel}:off,onClose:()=>{}}));window.render();})();`;
(async()=>{
 const browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 try {
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  page.setDefaultTimeout(10000);
  const requests=[];await page.route('**/*',route=>{requests.push(route.request().url());return route.abort();});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.setContent('<div id="root"></div>');
  await page.addStyleTag({content:fs.readFileSync(path.join(root,'workspace/app/tiger/tiger.css'),'utf8')});
  await page.addScriptTag({content:script});
  {
   const popup=page.locator('.popup').first();
   if(row==='T02') {
    assert(await page.getByText('This vault is off. Turn it on in Tank.',{exact:true}).first().isVisible());
    assert.deepEqual(await page.evaluate(()=>window.calls),[]);
   } else {
    const tabs={T03:'API keys',T04:'Files',T05:'Source links',T06:'MCP connections'};
    await popup.getByRole('tab',{name:tabs[row],exact:true}).click();
    if(row==='T03') {
     await popup.getByLabel('Name',{exact:true}).fill('placeholder-tool');
     await popup.getByLabel('Key',{exact:true}).fill('placeholder-key');
     await popup.getByRole('button',{name:'Save key',exact:true}).click();
     await popup.getByText('Saved. The key is hidden and will not be shown again.',{exact:true}).waitFor();
     assert(!(await page.locator('body').innerText()).includes('placeholder-key'));
    } else if(row==='T04') {
     await popup.locator('input[type=file]').setInputFiles({name:'placeholder.csv',mimeType:'text/csv',buffer:Buffer.from('name\nplaceholder\n')});
     await popup.getByText('Saved.',{exact:true}).waitFor();
     await popup.getByText('placeholder.csv',{exact:true}).waitFor();
    } else if(row==='T05') {
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
    await popup.getByRole('button',{name:row==='T06'?'Disconnect':'Remove',exact:true}).click();
    await popup.getByText('Removed.',{exact:true}).waitFor();
    const calls=await page.evaluate(()=>window.calls);
    assert.equal(calls.length,2);
    assert.deepEqual(calls.map(c=>c.name),{T03:['saveVaultSecret','removeVaultSecret'],T04:['uploadVaultFiles','removeVaultFile'],T05:['addVaultLink','removeVaultLink'],T06:['addVaultConnection','removeVaultConnection']}[row]);
    assert(calls.every(c=>JSON.stringify(c.args.slice(0,4))===JSON.stringify(['tiger.vault','tiger','placeholder-tenant','placeholder-founder'])));
   }
  }
  assert.deepEqual(errors,[]);assert(requests.every(url=>!/^https?:/.test(url)));
  console.log(id+' passed');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
