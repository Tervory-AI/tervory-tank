// Actual Workspace pages + actual Tank loaders over production-route JSON.
// Only identity/provider transports and network IO are doubled. No live credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname,'..');
const ts = require('../workspace/node_modules/typescript');
const React = require('../workspace/node_modules/react');
const {renderToStaticMarkup} = require('../workspace/node_modules/react-dom/server');
const routes = JSON.parse(fs.readFileSync(process.env.W4_ROUTES || '/dev/shm/dashboards-w4/routes.json','utf8'));
const out = process.env.W4_OUTPUT || '/dev/shm/dashboards-w4/current';
const baseline = process.env.W4_BASELINE === '1';
const screen = process.env.W4_SCREEN || 'founder';
const now = Date.UTC(2026,10,3,20);
Date.now = ()=>now;
process.env.TANK_URL='http://offline.invalid';
process.env.TANK_API_KEY='placeholder-w4-key';
process.env.TERVORY_ADMIN_USER_IDS='placeholder-founder';
const calls=[];
global.fetch=async(url,init={})=>{
  const target=new URL(url);assert.equal(target.hostname,'offline.invalid','No live network');
  const key=target.pathname+target.search;calls.push(key);
  assert.equal(new Headers(init.headers).get('x-tank-key'),'placeholder-w4-key');
  assert(routes[key],`No production-route response for ${key}`);
  return Response.json(routes[key]);
};
const users=[0,1].map(i=>({id:`placeholder-user-${i}`,firstName:'placeholder',lastName:`signup ${i}`,createdAt:now-(i+1)*3600000,publicMetadata:{company:`placeholder company ${i}`,country:'placeholder country',plan:'placeholder plan'}}));
class StripeRows {
  constructor(){
    this.balance={retrieve:async()=>({livemode:true})};
    this.subscriptions={list:async function*(){for(const i of [0,1])yield {id:`placeholder-sub-${i}`,customer:`placeholder-customer-${i}`,livemode:true,status:'active',start_date:Math.floor((now-86400000)/1000),items:{data:[{quantity:1,price:{unit_amount:1200}}]},latest_invoice:{id:`placeholder-invoice-${i}`,livemode:true,status:'paid',amount_paid:1200,currency:'usd'}}}};
  }
}
process.env.STRIPE_SECRET_KEY='placeholder-provider-double';
const load=Module._load;
Module._load=function(name,parent,main){
  if(name==='server-only')return {};
  if(name==='stripe')return StripeRows;
  if(name==='@clerk/nextjs/server')return {auth:async()=>({userId:'placeholder-founder'}),currentUser:async()=>({firstName:'placeholder'}),clerkClient:async()=>({users:{getCount:async()=>users.length,getUserList:async()=>({totalCount:users.length,data:users})}})};
  if(name==='@/lib/tenant')return {activeTenant:async()=>({tenantId:'00000000-0000-0000-0000-0000000000aa',orgName:'placeholder organisation',userId:'placeholder-client'})};
  if(name==='@/app/api/zenas/tank')return {regionTank:()=>null};
  if(name==='next/navigation')return {useRouter:()=>({refresh(){}}),redirect:()=>{throw Error('redirect')},notFound:()=>{throw Error('404')}};
  if(name==='next/cache')return {revalidatePath:()=>{}};
  if(name.startsWith('@/'))return load.call(this,path.join(root,'workspace',name.slice(2)),parent,main);
  return load.call(this,name,parent,main);
};
const read=file=>baseline?execFileSync('git',['show',`981ac096:${path.relative(root,file)}`],{cwd:root,encoding:'utf8'}):fs.readFileSync(file,'utf8');
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(module,file)=>module._compile(ts.transpileModule(read(file),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,file);
require.extensions['.css']=()=>{};
const text=html=>html.replace(/<script[\s\S]*?<\/script>/g,'').replace(/<dialog[\s\S]*?<\/dialog>/g,'').replace(/<[^>]+>/g,' ').replace(/\s+/g,' ').trim();
const cssFiles=['globals.css','control/dashboard.css','control/control.css','dashboard.css','tank/proof/savings.css'];
const css=cssFiles.map(file=>read(path.join(root,'workspace/app',file))).join('\n');
const fonts=`@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2');font-weight:100 900}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}:root{--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}html,body{margin:0}`;
(async()=>{
  fs.mkdirSync(out,{recursive:true});
  const Page=require(screen==='founder'?'../workspace/app/control/page.tsx':'../workspace/app/page.tsx').default;
  const html=renderToStaticMarkup(await Page({searchParams:Promise.resolve({})}));
  const visible=text(html);
  if(!baseline && screen==='founder'){
    for(const line of ['Spent this month','83','37','% by code, no model','$12.75','2 skills passed their tests','Approve all','Cheaper model proven for placeholder market research','Daily check: 7 examples','3 running','4 queued','0 running','placeholder signup 0','placeholder company 0','placeholder country','placeholder plan'])assert(visible.includes(line),`Missing route/provider value: ${line}`);
    for(const line of ['Recorded spend','price not set','Approve all ready','WORKERS-2','Workers status unavailable','—'])assert(!visible.includes(line),`Unapproved/placeholder output: ${line}`);
    assert(!html.includes('data-tile="workers"'),'Unframed card removed');
    const {activity}=require('../workspace/app/control/values.ts');
    const source=routes['/v1/dashboards/founder'];
    assert.throws(()=>activity({...source,daily:[{...source.daily[0],unpriced:1}]},now),/unpriced/);
    assert.throws(()=>activity({...source,daily:[{...source.daily[0],spent:null}]},now),/invalid measurement/);
    assert.equal(activity({...source,daily:[]},now).spent,0,'An empty ledger count really is zero');
  }
  if(!baseline && screen==='client'){
    const surface=text(html.split('<div id="your-savings"')[0]);
    for(const line of ['placeholder organisation','1,235','$11,765','placeholder requested work 0','Queued','In progress','Ready','Failed','Your team','Business lists','Market research','Legal'])assert(surface.includes(line),`Missing client route/identity value: ${line}`);
    require('./client-copy.cjs')(surface);
    const {clientMeasurements}=require('../workspace/app/dashboard-values.ts');
    const data=routes['/v1/dashboards/client?tenant_id=00000000-0000-0000-0000-0000000000aa'];
    const savings=routes['/v1/client-savings?tenant_id=00000000-0000-0000-0000-0000000000aa'];
    assert.throws(()=>clientMeasurements({...data,jobs_done:null},savings),/incomplete/);
    assert.throws(()=>clientMeasurements(data,{...savings,month:{saved:null}}),/incomplete/);
    assert.throws(()=>clientMeasurements({...data,recent:[{id:'placeholder-job',title:'placeholder work',status:'retired'}]},savings),/approved display state/);
    assert.equal(clientMeasurements({...data,jobs_done:0},{...savings,month:{saved:'0'}}).saved,0);
  }
  fs.writeFileSync(path.join(out,`${screen}.html`),`<!doctype html><html lang="en"><meta charset="utf-8"><title>Offline route fixtures · ${screen}</title><style>${fonts}${css}</style><body><div class="app-shell"><aside class="shell-side">Shared shell</aside><div class="shell-main"><main>${html}</main></div></div></body></html>`);
  fs.writeFileSync(path.join(out,`${screen}-values.json`),JSON.stringify({fixture:true,source:'production Tank routes and Clerk/Stripe transport doubles',visible,calls},null,2));
  fs.writeFileSync(path.join(out,'styles.css'),fonts+css);
  fs.writeFileSync(path.join(out,`${screen}-fragment.html`),html);
  console.log(`PASS: ${baseline?'main baseline':`current ${screen}`} route/provider values rendered; ${calls.length} actual loader reads; no production IO.`);
})().catch(error=>{console.error(error);process.exitCode=1});
