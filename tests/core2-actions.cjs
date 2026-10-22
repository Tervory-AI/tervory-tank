const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../workspace/node_modules/typescript');
const source=fs.readFileSync('workspace/app/tank/proof/savings-actions.ts','utf8');
const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
let identity={tenantId:'organisation-a'}, calls=[];
const moduleObject={exports:{}};
vm.runInNewContext(compiled,{exports:moduleObject.exports,module:moduleObject,require(name){
  if(name==='@/lib/tenant')return {activeTenant:async()=>identity};
  if(name==='@/lib/tank')return {readClientSavings:async(tenant,endpoint,query)=>{calls.push({path:'/v1/client-savings'+endpoint,tenant,init:{query}});return {rows:[]};}};
  throw Error(`Unexpected import ${name}`);
}});
(async()=>{
  const api=moduleObject.exports;
  await api.readClientSavings();assert.equal(calls.at(-1).tenant,'organisation-a');
  await api.readClientSavingsRows({end:'2026-10-20T00:00:00Z',tenant_id:'victim',population:'costs',page:2,member:'Base',free_only:true,'x-tank-key':'forged'});
  const call=calls.at(-1);
  assert.equal(call.tenant,'organisation-a');assert.equal(call.path,'/v1/client-savings/rows');
  assert.deepEqual(JSON.parse(JSON.stringify(call.init.query)),{end:'2026-10-20T00:00:00Z',page:'2',member:'Base',free_only:'true'});
  identity={tenantId:'organisation-b'};
  await api.readSavingsRevision();assert.equal(calls.at(-1).tenant,'organisation-b');
  identity=null;const before=calls.length;
  await assert.rejects(api.readClientSavings(),/sign in/);assert.equal(calls.length,before);
  console.log('Signed-in organisation, argument projection and signed-out refusal passed.');
})().catch(e=>{console.error(e);process.exitCode=1;});
(async()=>{
  const compiled=ts.transpileModule(fs.readFileSync('workspace/lib/tank.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
  const mod={exports:{}};let request;
  vm.runInNewContext(compiled,{exports:mod.exports,module:mod,process:{env:{}},URLSearchParams,fetch:async(url,init)=>{request={url,init};return {ok:true,json:async()=>({})};},require(name){throw Error(name);}});
  await mod.exports.readClientSavings('session-tenant','/rows',{tenant_id:'victim',population:'costs',page:'2',end:'cutoff'});
  const url=new URL(request.url);assert.equal(url.pathname,'/v1/client-savings/rows');
  assert.deepEqual([...url.searchParams.entries()],[['end','cutoff'],['page','2'],['tenant_id','session-tenant']]);
})().catch(e=>{console.error(e);process.exitCode=1;});
(async()=>{
  const React=require('../workspace/node_modules/react');
  const {renderToStaticMarkup}=require('../workspace/node_modules/react-dom/server');
  const source=fs.readFileSync('workspace/app/tank/proof/page.tsx','utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,jsx:ts.JsxEmit.ReactJSX}}).outputText;
  const mod={exports:{}};
  vm.runInNewContext(compiled,{exports:mod.exports,module:mod,require(name){
    if(name==='react/jsx-runtime')return require('../workspace/node_modules/react/jsx-runtime');
    if(name.endsWith('/access'))return {goldIdentity:async()=>({role:'founder'})};
    if(name==='next/navigation')return {notFound(){throw Error('404');}};
    if(name==='./savings-founder')return {FounderSavingsPanel:async()=>{throw Error('offline');}};
    if(name==='./server')return {readProof:async()=>{throw Error('should not run');}};
    if(name==='@/lib/tank')return {moaEvidence:async()=>{throw Error('should not run');}};
    if(name==='../moa/view')return {};
    if(name==='./view'||name.endsWith('.css'))return {};
    throw Error(name);
  }});
  const html=renderToStaticMarkup(await mod.exports.default({searchParams:Promise.resolve({})}));
  assert(html.includes('Proof evidence is unavailable') && html.includes('role="alert"'));
  // Founder selections must keep the same scope for charts, drawers and exports.
  const server={exports:{}};let url;
  vm.runInNewContext(ts.transpileModule(fs.readFileSync('workspace/app/tank/proof/server.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,{
    exports:server.exports,module:server,URLSearchParams,process:{env:{}},fetch:async(value)=>{url=new URL(value);return {ok:true};},require(name){
      if(name.endsWith('/access'))return {goldIdentity:async()=>({role:'founder',userId:'founder'})};return {};
    }
  });
  for(const endpoint of ['/savings','/savings/rows','/savings/export/csv','/savings/export/pdf','']){
    await server.exports.proofResponse({tenant_id:'clients'},undefined,endpoint);
    assert.equal(url.searchParams.get('clients_only'),'true');assert.equal(url.searchParams.get('tenant_id'),null);
  }
  await server.exports.proofResponse({tenant_id:'all'});assert.equal(url.searchParams.size,0);
  await server.exports.proofResponse({tenant_id:'named-client'});assert.equal(url.searchParams.get('tenant_id'),'named-client');
})().catch(e=>{console.error(e);process.exitCode=1;});
