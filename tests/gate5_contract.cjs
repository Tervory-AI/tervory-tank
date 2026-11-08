const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),Module=require('node:module');
const root=path.resolve(__dirname,'..'),ts=require('../workspace/node_modules/typescript');
const originalLoad=Module._load,originalResolve=Module._resolveFilename;
let authenticated=true,calls=[],fail=false;
const tenant={tenantId:'00000000-0000-4000-8000-000000000001',userId:'own-user'};
const mocks={
 'server-only':{},
 'next-auth/jwt':{getToken:async()=>({principal:{expiresAt:Date.now()+60000}})},
 '@/lib/tenant':{currentTenant:async()=>{if(!authenticated)throw Error('Trigger sign-in required');return tenant;}},
 '@/lib/tank':Object.fromEntries(['createTask','listTasks','route','sendFeedback','ledgerSummary','ledgerFailures','baseRun','baseRecords','baseBatches','baseEngines'].map(name=>[name,async(...args)=>{calls.push({name,args});if(fail)throw Error('upstream-secret-must-not-leak');return name==='baseRecords'?[{status:'done',confidence:1,profile:{name:{value:'=HYPERLINK("unsafe")'}}}]:{id:'result'};}])),
 '@/lib/workspace-gates':{
   chatWithMemory:async(tenantId,userId,messages)=>{calls.push({name:'chatWithMemory',args:[tenantId,userId,messages]});if(fail)throw Error('upstream-secret-must-not-leak');return {id:'result',content:'ok'};},
   createTaskWithMemory:async(tenantId,userId,title,taskType,request)=>{calls.push({name:'createTaskWithMemory',args:[tenantId,userId,title,taskType,request]});if(fail)throw Error('upstream-secret-must-not-leak');return {id:'result'};},
   setWorkspaceMemoryControl:async()=>({memory_control:'edit'}),
   viewWorkspaceMemory:async()=>({memories:[],memory_control:'edit'}),
   editWorkspaceMemory:async()=>({id:'x',updated:true}),
   forgetWorkspaceMemory:async()=>({forgotten:true}),
 }
};
Module._load=function(name,parent,main){if(Object.hasOwn(mocks,name))return mocks[name];return originalLoad.call(this,name,parent,main);};
Module._resolveFilename=function(name,parent,...args){if(name.startsWith('@/'))name=path.join(root,'workspace',name.slice(2));return originalResolve.call(this,name,parent,...args);};
require.extensions['.ts']=(m,file)=>m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,file);
const submissions=fs.mkdtempSync(path.join(require('node:os').tmpdir(),'workspace-submissions-'));process.env.WORKSPACE_SUBMISSIONS_DIR=submissions;
const json=(body,url='/api/tasks')=>new Request('https://app.tervory.com'+url,{method:'POST',headers:{'content-type':'application/json','Idempotency-Key':'00000000-0000-4000-8000-000000000099'},body:JSON.stringify(body)});
async function main(){
 const task=require('../workspace/app/api/tasks/route.ts');
 for(const body of [null,[],{title:1,request:{}},{title:'x',request:'y',task_type:'unapproved'},{title:'x',request:'x'.repeat(20001)}])assert.equal((await task.POST(json(body))).status,400);
 assert.equal(calls.length,0);
 const own={title:'Own task',request:'Own request',tenant_id:'other-tenant'};
 assert.equal((await task.POST(json(own))).status,202);assert.equal(calls[0].name,'createTaskWithMemory');assert.equal(calls[0].args[0],tenant.tenantId);assert.equal(calls[0].args[1],tenant.userId);
 assert.equal((await task.POST(json(own))).status,202);assert.equal(calls.filter(c=>c.name==='createTaskWithMemory').length,1);
 assert.equal((await task.POST(json({...own,title:'changed'}))).status,409);
 const persistent=process.env.WORKSPACE_SUBMISSIONS_DIR;delete process.env.WORKSPACE_SUBMISSIONS_DIR;assert.equal((await task.POST(json(own))).status,503);process.env.WORKSPACE_SUBMISSIONS_DIR=persistent;
 authenticated=false;calls=[];assert.equal((await task.GET()).status,401);assert.equal(calls.length,0);
 const base=require('../workspace/app/api/base/route.ts');
 let downloads=0;globalThis.fetch=async()=>{downloads++;throw Error('no network');};
 assert.equal((await base.POST(json({batch:'x',url:'https://drive.google.com/anything'},'/api/base'))).status,401);assert.equal(downloads,0);
 authenticated=true;
 for(const url of ['https://127.0.0.1/private','https://169.254.169.254/private','https://localhost/private','https://drive.google.com.attacker.invalid/private','file:///tmp/private'])assert.equal((await base.POST(json({batch:'x',url},'/api/base'))).status,400);
 assert.equal(downloads,0);
 let links=[];globalThis.fetch=async(input,init)=>{links.push(String(input));assert.equal(init.redirect,'manual');return new Response(null,{status:302,headers:{location:'https://127.0.0.1/private'}});};
 assert.equal((await base.POST(json({batch:'x',url:'https://drive.google.com/file/d/known/view'},'/api/base'))).status,400);assert.equal(links.length,1);
 links=[];globalThis.fetch=async(input,init)=>{links.push(String(input));assert.equal(init.redirect,'manual');return links.length===1?new Response(null,{status:302,headers:{location:'https://drive.usercontent.google.com/file'}}):new Response('name,city\nOwn record,Own city',{headers:{'content-type':'text/csv'}});};
 assert.equal((await base.POST(json({batch:'x',url:'https://drive.google.com/file/d/known/view'},'/api/base'))).status,202);assert.equal(links.length,2);assert.equal(calls.at(-1).args[0],tenant.tenantId);
 const chat=require('../workspace/app/api/chat/route.ts');
 assert.equal((await chat.POST(json({messages:'not-an-array'},'/api/chat'))).status,400);
 assert.equal((await chat.POST(json({messages:[{role:'system',content:'x'}]},'/api/chat'))).status,400);
 const ledger=require('../workspace/app/api/ledger/route.ts');
 for(const days of ['-1','Infinity','366','1.5'])assert.equal((await ledger.GET(new Request('https://app.tervory.com/api/ledger?days='+days))).status,400);
 fail=true;const error=await task.GET();assert.equal(error.status,502);assert(!(await error.text()).includes('upstream-secret'));fail=false;
 const exportRoute=require('../workspace/app/api/base/export/route.ts');
 const exported=await exportRoute.GET(new Request('https://app.tervory.com/api/base/export?batch=own&tenant_id=other'));
 assert.equal(exported.status,200);assert((await exported.text()).includes("'=HYPERLINK"));assert.equal(calls.at(-1).args[0],tenant.tenantId);
 const previous={TANK_URL:process.env.TANK_URL,TANK_API_KEY:process.env.TANK_API_KEY,TRIGGER_SIGNIN_WORKSPACE_SECRET:process.env.TRIGGER_SIGNIN_WORKSPACE_SECRET};
 Object.assign(process.env,{TANK_URL:'http://127.0.0.1:1',TANK_API_KEY:'placeholder',TRIGGER_SIGNIN_WORKSPACE_SECRET:'placeholder'});
 const {NextRequest}=require('../workspace/node_modules/next/server');
 const middleware=require('../workspace/middleware.ts').default;
 for(const origin of [undefined,'https://attacker.invalid']) {
  const request=new NextRequest('https://app.tervory.com/api/tasks',{method:'POST',headers:{host:'app.tervory.com',...(origin?{origin}:{})}});
  assert.equal((await middleware(request)).status,403);
 }
 const good=new NextRequest('https://app.tervory.com/api/tasks',{method:'POST',headers:{host:'app.tervory.com',origin:'https://app.tervory.com'}});
 assert.equal((await middleware(good)).status,200);
 for(const [name,value]of Object.entries(previous)){if(value===undefined)delete process.env[name];else process.env[name]=value;}
 const os=require('node:os');const temporary=fs.mkdtempSync(path.join(os.tmpdir(),'workspace-signups-'));
 try {
  const {storeAddress}=await import('../site/release-store.mjs');const file=path.join(temporary,'signups.jsonl');
  await Promise.all([storeAddress(file,'new@example.invalid'),storeAddress(file,'new@example.invalid')]);
  assert.equal(fs.readFileSync(file,'utf8').trim().split('\n').length,1);
 } finally {fs.rmSync(temporary,{recursive:true,force:true});}
 const config=require('../workspace/next.config.ts').default;const security=(await config.headers()).find(row=>row.source==='/:path*').headers;
 assert(security.some(row=>row.key==='X-Content-Type-Options'&&row.value==='nosniff'));
 const claimsModule=require('../workspace/lib/trigger-signin-principal.ts');
 const oldBindings=process.env.TRIGGER_SIGNIN_ORG_TENANTS;process.env.TRIGGER_SIGNIN_ORG_TENANTS=JSON.stringify({'100':tenant.tenantId,'200':'00000000-0000-4000-8000-000000000002'});
 const claims={sub:'own-user',exp:2000,[claimsModule.ORG_CLAIM]:'100',[claimsModule.ROLES_CLAIM]:{member:{'100':'own-org'},org_admin:{'200':'other-org'}}};
 assert.equal(claimsModule.signinPrincipal(claims,1000).orgRole,null);
 assert.equal(claimsModule.signinPrincipal(claims,1000).tenantId,tenant.tenantId);
 assert.throws(()=>claimsModule.signinPrincipal({...claims,exp:0},1000),/refused/);
 assert.throws(()=>claimsModule.signinPrincipal(claims,1000,'300'),/linked/);
 if(oldBindings===undefined)delete process.env.TRIGGER_SIGNIN_ORG_TENANTS;else process.env.TRIGGER_SIGNIN_ORG_TENANTS=oldBindings;
 const {submitOnce}=require('../workspace/lib/submission.ts');let runs=0;
 const run=async()=>{runs++;await new Promise(resolve=>setTimeout(resolve,10));return {id:'durable'};};
 const submissionKey='00000000-0000-4000-8000-000000000088';
 await Promise.allSettled([submitOnce(tenant.tenantId,tenant.userId,submissionKey,{same:true},run),submitOnce(tenant.tenantId,tenant.userId,submissionKey,{same:true},run)]);
 assert.equal(runs,1);assert.equal((await submitOnce(tenant.tenantId,tenant.userId,submissionKey,{same:true},async()=>{throw Error('must not run twice');})).id,'durable');
 const {jsonInput}=require('../workspace/lib/route-input.ts');
 await assert.rejects(jsonInput(json({text:'x'.repeat(100)}),10),/large/);
 const {fetchWithDeadline,requestBudget}=require('../workspace/lib/request.ts');
 requestBudget.milliseconds=25;
 let attempts=0;globalThis.fetch=async()=>{attempts++;return new Promise(()=>{});};
 // The guard prevents fake timers' unref from ending this test process early.
 const guard=setInterval(()=>{},1000);
 try {
  const start=Date.now();await assert.rejects(fetchWithDeadline('http://127.0.0.1/',{method:'POST',body:'one'}),/could not be confirmed/);assert(Date.now()-start<500);assert.equal(attempts,1);
  globalThis.fetch=async()=>new Response(new ReadableStream({start(out){out.enqueue(new TextEncoder().encode('{'));}}));
  const response=await fetchWithDeadline('http://127.0.0.1/');await assert.rejects(response.json(),/interrupted/);
  requestBudget.milliseconds=100;requestBudget.streamMilliseconds=25;
  let pump;globalThis.fetch=async()=>new Response(new ReadableStream({start(out){pump=setInterval(()=>out.enqueue(new TextEncoder().encode('heartbeat')),5);},cancel(){clearInterval(pump);}}),{headers:{'content-type':'text/event-stream'}});
  const stream=await fetchWithDeadline('http://127.0.0.1/');await assert.rejects(stream.text(),/interrupted/);clearInterval(pump);
  const controller=new AbortController();controller.abort();globalThis.fetch=async(_url,init)=>{assert(init.signal.aborted);throw Error('aborted');};
  await assert.rejects(fetchWithDeadline('http://127.0.0.1/',{signal:controller.signal}),/could not be confirmed/);
 } finally {clearInterval(guard);requestBudget.milliseconds=30000;requestBudget.streamMilliseconds=15*60000;}
 console.log('Gate 5: bounded headers/body, one write attempt, malformed inputs, tenant isolation, authentication before downloads, SSRF rejection, safe errors and spreadsheet escaping passed.');
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>fs.rmSync(submissions,{recursive:true,force:true}));
