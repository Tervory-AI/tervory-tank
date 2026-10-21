/* Offline checks of the actual founder actions and Client squads tile. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const React = require(path.join(root, 'workspace/node_modules/react'));
const { renderToStaticMarkup } = require(path.join(root, 'workspace/node_modules/react-dom/server'));
const original = Module._load;
let founder = true, failRead = false, calls = [], organisationReads = 0;
const tenant = '00000000-0000-0000-0000-000000000011';
const agents = ['base','tiger','market_lab','rig','tisan','radix','zenas'];
const grants = agents.map(agent => ({agent,enabled:agent === 'base',enabled_by:agent==='base'?'founder-fixture':null,enabled_at:null}));
const log = [{id:1,agent:'base',enabled:true,changed_by:'founder-fixture',changed_at:'2026-10-21T12:00:00Z'}];
process.env.TANK_API_KEY = 'dummy-workspace-key';
Module._load = function(name,parent,isMain) {
  if (name === '@clerk/nextjs/server') return {
    auth:async()=>({userId:founder?'founder-fixture':'client-fixture'}),
    clerkClient:async()=>({organizations:{
      getOrganizationList:async options=>{organisationReads++;assert.equal(options.limit,25);return {data:[{id:'org-fixture',name:'Example Company'}],totalCount:26}},
      getOrganization:async ({organizationId})=>{organisationReads++;assert.equal(organizationId,'org-fixture');return {id:organizationId,name:'Example Company'}}
    }})
  };
  if(name==='@/lib/admin')return {isFounder:id=>id==='founder-fixture'};
  if(name==='@/lib/tenant')return {tenantIdFor:id=>{assert.equal(id,'org-fixture');return tenant}};
  if(name==='@/lib/tank')return require('../workspace/lib/tank.ts');
  if(name==='next/navigation')return {notFound:()=>{throw Error('404')}};
  return original.call(this,name,parent,isMain);
};
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,filename);
global.fetch = async(url,options)=>{
  calls.push({url,options});
  assert.equal(options.headers['X-Tervory-Tenant'],tenant);
  assert.equal(options.headers['X-Tervory-User'],'founder-fixture');
  assert.equal(options.headers['x-tank-key'],'dummy-workspace-key');
  if(options.method==='PUT')return {ok:true,json:async()=>({changed:true})};
  if(failRead)throw Error('private upstream failure');
  return {ok:true,json:async()=>url.endsWith('/log')?log:grants};
};
(async()=>{
  const actions=require('../workspace/app/control/squad-actions.ts');
  founder=false;
  for(const call of [()=>actions.squadClients(0),()=>actions.squadState('org-fixture'),()=>actions.changeSquad('org-fixture','tiger',true)])await assert.rejects(call,/404/);
  assert.equal(organisationReads,0);assert.equal(calls.length,0);
  founder=true;
  const clients=await actions.squadClients(0);assert.equal(clients.more,true);
  assert((await actions.squadClients(-1)).error);
  const state=await actions.squadState('org-fixture');assert.equal(state.grants.length,7);
  calls=[];
  await actions.changeSquad('org-fixture','tiger',true);
  assert.equal(calls.filter(c=>c.options.method==='PUT').length,1);
  assert.deepEqual(JSON.parse(calls[0].options.body),{enabled:true});
  assert(calls[0].url.endsWith('/v1/command/squads/tiger'));
  failRead=true;
  const failed=await actions.changeSquad('org-fixture','tiger',false);
  assert(failed.error.includes('could not be confirmed'));assert.deepEqual(failed.grants,[]);
  assert(!JSON.stringify(failed).includes('private upstream'));
  const {ClientSquads}=require('../workspace/app/control/client-squads.tsx');
  const tile=renderToStaticMarkup(React.createElement(ClientSquads,{initial:clients,selectedClient:'org-fixture',initialState:state}));
  assert.equal((tile.match(/role="switch"/g)||[]).length,7);
  assert(tile.includes('aria-checked="true"') && tile.includes('aria-checked="false"'));
  assert(tile.includes('Recent access changes') && tile.includes('Example Company'));
  assert(!tile.includes(tenant) && !tile.includes('dummy-workspace-key'));
  const unavailable=renderToStaticMarkup(React.createElement(ClientSquads,{initial:clients,selectedClient:'org-fixture',initialState:failed}));
  assert(unavailable.includes('role="alert"') && !unavailable.includes('role="switch"'));
  const empty=renderToStaticMarkup(React.createElement(ClientSquads,{initial:{clients:[],page:0,more:false}}));
  assert(empty.includes('No clients on this page.'));
  const {FounderDashboard}=require('../workspace/app/control/view.tsx');
  const view={data:null,signups:null,paying:null,paused:null,errors:[],models:[],refused:[]};
  const html=renderToStaticMarkup(React.createElement(FounderDashboard,{view,squads:React.createElement(ClientSquads,{initial:clients,selectedClient:'org-fixture',initialState:state})}));
  const css=fs.readFileSync(path.join(root,'workspace/app/control/dashboard.css'),'utf8')+fs.readFileSync(path.join(root,'workspace/app/control/client-squads.css'),'utf8');
  const fonts="@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2')}@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}html,body{margin:0}:root{--font-jost:Jost;--font-inter:Inter;--font-mono:Mono}";
  const out=path.join(require('node:os').tmpdir(),'command1a-ui');fs.mkdirSync(out,{recursive:true});
  fs.writeFileSync(path.join(out,'client-squads.html'),`<!doctype html><html lang="en"><meta charset="utf-8"><title>Client squads · offline fixture</title><style>${fonts}${css}</style><body>${html}</body></html>`);
  console.log('Founder authorization, tenant mapping, mutation/read-back, failure state, and tile rendering passed.');
})().catch(err=>{console.error(err);process.exitCode=1});
