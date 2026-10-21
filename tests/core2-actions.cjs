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
  if(name==='@/lib/tank')return {rigProxy:async(path,tenant,init)=>{calls.push({path,tenant,init});return {rows:[]};}};
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
