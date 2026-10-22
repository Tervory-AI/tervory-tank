// Page-boundary checks without network, and without replacing DASH-1's tests.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const Module=require('node:module');
const root=path.resolve(__dirname,'..');
const ts=require(path.join(root,'workspace/node_modules/typescript'));
const original=Module._load;
let founder=false,tools=['tiger.watch'],toolsFail=false,rosterReads=0,tasks=0;
const identity={tenantId:'owned',userId:'owned-user',orgName:'Example'};
Module._load=function(name,parent,isMain){
 if(name==='@/lib/tenant')return {activeTenant:async()=>identity};
 if(name==='@/lib/admin')return {isFounder:()=>founder};
 if(name==='@clerk/nextjs/server')return {currentUser:async()=>({firstName:'Alex'})};
 if(name==='next/navigation')return {redirect:location=>{throw Object.assign(new Error('redirect'),{location})}};
 if(name==='./window'&&parent.filename.endsWith('/chats/page.tsx'))return {CommandWindow:'command-fixture'};
 if(name==='@/lib/tank')return {
  commandRequest:async()=>Response.json([]),commandTools:async()=>{if(toolsFail)throw Error('unavailable');return tools},
  listRoster:async()=>{rosterReads++;return [{name:'fixture-model',inputPerM:.1,outputPerM:.4}]},
  readClientDashboard:async()=>({jobs_done:4,recent:[]}),createTask:async()=>{tasks++},
 };
 return original.call(this,name,parent,isMain);
};
for(const ext of ['.ts','.tsx'])require.extensions[ext]=(module,filename)=>module._compile(ts.transpileModule(fs.readFileSync(filename,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,filename);
require.extensions['.css']=()=>{};
function find(element,predicate){if(!element)return;for(const item of Array.isArray(element)?element:[element]){if(predicate(item))return item;const found=find(item?.props?.children,predicate);if(found)return found;}}
(async()=>{
 const chats=require('../workspace/app/chats/page.tsx').default;
 let page=await chats();assert.deepEqual(page.props.models,[]);assert.deepEqual(page.props.initialTools,['tiger.watch']);assert.equal(rosterReads,0);
 tools=[];page=await chats();assert.deepEqual(page.props.initialTools,[]);
 toolsFail=true;page=await chats();assert.deepEqual(page.props.initialTools,[]);assert(page.props.initialError.includes('Chat is still available'));
 founder=true;page=await chats();assert.equal(page.props.models[0].label,'fixture-model');assert.equal(rosterReads,1);
 const dashboard=require('../workspace/app/page.tsx').default;
 const view=await dashboard({searchParams:Promise.resolve({})});
 const form=find(view,item=>item?.type==='form'&&item.props.className==='dash-ask');assert(form);
 const prompt='Explain gold prices & Tank evaluation?';const data=new FormData();data.set('request',prompt);
 await assert.rejects(()=>form.props.action(data),error=>new URL(error.location,'https://workspace.invalid').searchParams.get('ask')===prompt&&error.location.startsWith('/chats?'));
 assert.equal(tasks,0);assert(find(view,item=>item?.props?.children==='Jobs done this month'));
 console.log('COMMAND-1B pages: dashboard ask handoff, Auto-only client props, founder roster and authoritative/empty/unavailable tool catalogues passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
