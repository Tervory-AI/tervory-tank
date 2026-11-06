const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = process.argv[2];
const ts = require(path.resolve('workspace/node_modules/typescript'));
const tenant = '00000000-0000-0000-0000-000000000011';
const other = '00000000-0000-0000-0000-000000000012';
const id = '33333333-3333-4333-8333-333333333333';
const key = 'placeholder-service-value';
function loader({fetch, mocks={}, fast=false}) {
  const cache = new Map();
  function load(file) {
    if(cache.has(file))return cache.get(file).exports;
    const module={exports:{}}; cache.set(file,module);
    const source=ts.transpileModule(fs.readFileSync(file,'utf8'),{fileName:file,reportDiagnostics:true,
      compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}});
    assert.equal(source.diagnostics.filter(d=>d.category===ts.DiagnosticCategory.Error).length,0);
    const local = name => {
      if(name in mocks)return mocks[name];
      if(name==='@/lib/trigger-signin-fetch')return {signinFetch:fetch};
      if(name==='@/app/api/zenas/tank')return {regionTank:()=>{throw Error('unexpected regional lookup');}};
      if(name==='next/server')return {NextResponse:{json:Response.json}};
      const base=name.startsWith('@/')?path.join(root,'workspace',name.slice(2)):path.resolve(path.dirname(file),name);
      return load(base+'.ts');
    };
    vm.runInNewContext(source.outputText,{module,exports:module.exports,require:local,
      process:{env:{TANK_URL:'http://placeholder-tank:8000',TANK_API_KEY:'placeholder-service-value'}},fetch,
      Request,Response,Headers,URL,URLSearchParams,AbortController,AbortSignal,Uint8Array,TextDecoder,TextEncoder,
      ReadableStream,console,setTimeout:fast?(fn,ms)=>setTimeout(fn,Math.min(ms,15)):setTimeout,clearTimeout});
    return module.exports;
  }
  return file=>load(path.join(root,'workspace',file));
}
(async()=>{
  let attempts=0,signal;
  const io=loader({fast:true,fetch:async(_,init)=>{attempts++;signal=init.signal;return new Promise(()=>{});}})('app/radix/io.ts');
  await assert.rejects(io.radixJSON('/placeholder',{method:'POST'}),/Radix could not complete/);
  assert.equal(attempts,1); assert(signal.aborted);
  const controller=new AbortController();controller.abort();
  await assert.rejects(io.radixJSON('/placeholder',{signal:controller.signal}),/Radix could not complete/);
  assert.equal(attempts,1);

  let signedIn=false,creates=0,reads=0;
  const task={id,tenant_id:tenant,agent:'radix',title:'placeholder request',status:'done',result:'placeholder reply',created_at:'2026-11-05'};
  const store={list:async owner=>{assert.equal(owner,tenant);reads++;return [task,{...task,tenant_id:other,title:'private-other-tenant'}];},
    get:async(owner,ref)=>{assert.equal(owner,tenant);assert.equal(ref,id);return task;},
    create:async(owner,user,title,type,messages,agent)=>{assert.equal(owner,tenant);assert.equal(user,'placeholder-user');assert.equal(agent,'radix');creates++;return task;}};
  const route=loader({fast:true,fetch:()=>{throw Error('unexpected network');},mocks:{
    '@/lib/tank':{radixTaskStore:store},'@/lib/tenant':{currentTenant:async()=>{if(!signedIn)throw Error(key);return {tenantId:tenant,userId:'placeholder-user'};}}
  }})('app/radix/requests/route.ts');
  const req=(body,extra={})=>new Request('https://radix.tervory.com/radix/requests',{method:'POST',headers:{origin:'https://radix.tervory.com',host:'radix.tervory.com',...extra},body:JSON.stringify(body)});
  assert.equal((await route.GET(new Request('https://radix.tervory.com/radix/requests'))).status,401);
  assert.equal(reads,0); signedIn=true;
  const records=await (await route.GET(new Request('https://radix.tervory.com/radix/requests?tenant_id='+other))).json();
  assert.equal(records.records.length,1); assert(!JSON.stringify(records).includes('private-other'));
  assert.equal((await route.POST(req({text:'placeholder'},{origin:'https://placeholder-attacker.invalid'}))).status,403);
  assert.equal((await route.POST(req({text:'placeholder'},{'sec-fetch-site':'cross-site'}))).status,403);
  for(const body of [{text:''},{text:'x'.repeat(4001)},{text:'placeholder',history:[{role:'system',content:'placeholder'}]},{text:'placeholder',referenceId:'../private'}]){
    assert.equal((await route.POST(req(body))).status,400);
  }
  assert.equal((await route.POST(req({text:'x'.repeat(256001)}))).status,413);assert.equal(creates,0);
  assert.equal((await route.POST(req({text:'placeholder',tenant_id:other,userId:'placeholder-forged'}))).status,202);
  assert.equal(creates,1);
  let cancelled=false;
  const hanging=new Request('https://radix.tervory.com/radix/requests',{method:'POST',duplex:'half',body:new ReadableStream({cancel(){cancelled=true;}})});
  const refused=await route.POST(hanging);assert.equal(refused.status,502);assert(cancelled);assert.equal(creates,1);assert(!(await refused.text()).includes(key));

  // Actual regional transport and whole-body deadlines for every Radix corridor.
  const calls=[];let stall=false,broken=false;
  const tank=loader({fast:true,fetch:async(input,init)=>{
    const url=new URL(input);calls.push({url,init});
    assert(init.signal instanceof AbortSignal);assert.equal(init.redirect,'manual');
    if(url.pathname.endsWith('/home'))return Response.json({tenant_id:tenant,home_region:'us-east'});
    assert.equal(new Headers(init.headers).get('x-tank-key'),key);
    if(stall)return new Response(new ReadableStream({}),{headers:{'content-type':'application/json'}});
    if(broken)return new Response(key,{status:503});
    if(url.pathname.includes('/vaults/'))return init.method==='DELETE'?new Response(null,{status:204}):Response.json({vault:'radix.vault',enabled:true});
    if(url.pathname.includes('/case-studies/'))return Response.json({product:'radix',figures:[],tank:[]});
    return Response.json(init.method==='GET'&&url.pathname==='/v1/tasks'?[task]:task);
  }})('lib/tank.ts');
  const operations=[()=>tank.radixTaskStore.list(tenant,200),()=>tank.radixTaskStore.get(tenant,id),
    ()=>tank.radixTaskStore.create(tenant,'placeholder-user','placeholder','tier0.answer',[],'radix'),
    ()=>tank.vaultPlugins('radix.vault','radix',tenant,'placeholder-user'),
    ()=>tank.caseStudyRequest({tenantId:tenant,userId:'placeholder-user'},'radix')];
  for(const operation of operations){await operation();const before=calls.length;stall=true;await assert.rejects(operation());stall=false;
    assert.equal(calls.length,before+2);assert(calls.at(-1).init.signal.aborted);await operation();}
  await tank.removeVaultSecret('radix.vault','radix',tenant,'placeholder-user','placeholder-key');
  broken=true;await assert.rejects(tank.radixTaskStore.list(tenant,200),error=>!error.message.includes(key));
  console.log('PASS: day-zero auth, tenant isolation, bounded bodies, deadlines, one-attempt writes, explicit retry and safe errors.');
})().catch(error=>{console.error(error);process.exitCode=1;});
