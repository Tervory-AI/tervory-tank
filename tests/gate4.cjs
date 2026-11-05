const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require('../workspace/node_modules/typescript');
const React = require('../workspace/node_modules/react');
const {renderToStaticMarkup: render} = require('../workspace/node_modules/react-dom/server');
const totals = {spent:'0',would_have_cost:'0',saved:'0',work_count:0,jobs_count:0,free_count:0,top_cost:'0',top_spent:'0',top_saved:'0',top_count:0,quality_pending:false};
const savings = {as_of:'2026-11-05T00:00:00Z',revision:'empty',total:totals,month:totals,daily:[],members:[]};
let authCalls = 0;
const tank = {
  readClientDashboard: async () => ({jobs_done:0,recent:[],granted_squads:[]}),
  ledgerSummary: async () => ({days:30,calls:0,delivered:0,accepted:0,rejected:0,acceptance_rate:null,unpriced:0,cost_usd:0,cost_per_delivered_usd:null,cost_per_accepted_usd:null,by_model:[]}),
};
const mock = {
  'react': React,
  'server-only': {},
  '@/lib/trigger-signin': {currentUser:async()=>({firstName:null}),auth:async()=>{authCalls++;throw Error('must not authenticate without settings');}},
  '@/lib/tenant': {activeTenant:async()=>({tenantId:'empty-tenant',orgName:'New organisation'}),currentTenant:async()=>({tenantId:'empty-tenant',orgName:'New organisation'})},
  '@/lib/tank':tank,
  './tank/proof/savings-actions': {readClientSavings:async()=>savings},
  '@/lib/mobile':{mobileIdentity:async()=>{authCalls++;throw Error('must not resolve mobile sessions without settings');}},
  './fonts':{inter:{variable:''},jost:{variable:''},mono:{variable:''}},
  'next/navigation':{redirect:()=>{throw Error('unexpected redirect');},usePathname:()=>'/tasks'},
};
const originalLoad=Module._load, originalResolve=Module._resolveFilename;
Module._load=function(name,parent,main){if(Object.hasOwn(mock,name))return mock[name];return originalLoad.call(this,name,parent,main);};
Module._resolveFilename=function(name,parent,...args){if(name.startsWith('@/'))name=path.join(root,'workspace',name.slice(2));return originalResolve.call(this,name,parent,...args);};
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(m,file)=>m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,file);
require.extensions['.css']=()=>{};
const env = {...process.env};
globalThis.fetch=async()=>{throw Error('Gate 4 permits no external requests');};
async function main(){
  const {workspaceSettings,workspaceSetupMessage}=require('../workspace/lib/workspace-setup.ts');
  const configured={TANK_URL:'http://127.0.0.1:1',TANK_API_KEY:'offline-placeholder',TRIGGER_SIGNIN_WORKSPACE_SECRET:'offline-session-placeholder'};
  assert.equal(workspaceSetupMessage(configured),null);
  const Layout=require('../workspace/app/layout.tsx').default;
  const authRoute=require('../workspace/app/api/auth/[...nextauth]/route.ts');
  for(const name of workspaceSettings){
    for(const key of workspaceSettings)process.env[key]=configured[key];
    delete process.env[name];
    const html=render(await Layout({children:React.createElement('div',null,'private-data-must-stay-hidden')}));
    assert(html.includes(name),name);assert(html.includes('Workspace setup'));assert(!html.includes('private-data-must-stay-hidden'));
    const response=await authRoute.GET(new Request('http://127.0.0.1/api/auth/session'),{params:Promise.resolve({nextauth:['session']})});
    assert.equal(response.status,503);assert((await response.json()).error.includes(name));
  }
  assert.equal(authCalls,0);
  for(const url of ['file:///tmp/private','https://user:password@invalid.example','invalid'])assert(workspaceSetupMessage({...configured,TANK_URL:url}).includes('TANK_URL'));
  // Fresh-client read responses exercise the actual pages and chart components.
  const Dashboard=require('../workspace/app/page.tsx').default;
  let html=render(await Dashboard());
  assert(html.includes('Ask for work above'));assert(html.includes('Ask your organisation admin'));assert(html.includes('No work yet.'));assert(!html.includes('Alex'));assert(!html.includes('href="/base"'));
  const Ledger=require('../workspace/app/ledger/page.tsx').default;
  html=render(await Ledger());assert(html.includes('No calls yet. Ask something in Chat.'));assert(html.includes('$0.00000000'));assert(!html.includes('NaN'));
  for(const [file,action] of [['tasks/page.tsx','Add a task'],['data/page.tsx','Upload a CSV']]){
    html=render(React.createElement(require('../workspace/app/'+file).default));assert(html.includes(action));assert(!html.includes('NaN'));assert(!html.includes('Own job'));
  }
  const {SavingsSet}=require('../workspace/app/tank/proof/savings-set.tsx');
  html=render(React.createElement(SavingsSet,{data:savings,title:'What you saved',loadRows:async()=>{throw Error('not requested');},client:true}));
  assert(html.includes('Ask for work in Chats'));assert(html.includes('12,150 588,150'));assert.equal((html.match(/<svg /g)||[]).length,2);assert(!html.includes('NaN'));assert(!html.includes('Infinity'));assert(html.includes('$0.00'));
  const {ReceiptExample}=require('../site/app/home-interactions.tsx');
  html=render(React.createElement(ReceiptExample));assert(html.includes('Sign in and ask for work'));assert(html.includes('$0.00'));
  for(const demo of ['1,284','312.40','led_7f3a','Ana','Sam','0.9728'])assert(!html.includes(demo),demo);
  const {RigProductDemo}=require('../site/app/rig/rig-product-demo.tsx');
  html=render(React.createElement(RigProductDemo));assert(html.includes('Connect your store'));assert(html.includes('Start a store search'));assert(!html.includes('690'));
  const {BillingScreen}=require('../workspace/app/billing/screen.tsx');
  const {emptyBilling}=require('../workspace/app/billing/billing.ts');
  for(const tab of ['plans','usage','invoices']){
    html=render(React.createElement(BillingScreen,{tab,view:emptyBilling(true),notice:null}));
    assert(!html.includes('NaN'));assert(!html.includes('$19'));assert(!html.includes('offline-placeholder'));
    assert(html.includes(tab==='usage'?'Choose a plan':tab==='invoices'?'Receipts appear here':'Nothing is charged'));
  }
  console.log('Gate 4: empty dashboard, ledger, tasks, files, billing, savings charts and public receipts passed; each missing Workspace setting refuses auth without a request.');
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{
  Module._load=originalLoad;Module._resolveFilename=originalResolve;
  for(const key of Object.keys(process.env))if(!(key in env))delete process.env[key];Object.assign(process.env,env);
});
