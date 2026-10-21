const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('../workspace/node_modules/typescript');
const source = fs.readFileSync('workspace/app/tank/proof/tenant-names.ts','utf8');
const compiled = ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
const loaded = {exports:{}};
new Function('module','exports',compiled)(loaded,loaded.exports);
const {resolveTenantNames} = loaded.exports;
(async()=>{
  const platform='00000000-0000-0000-0000-000000000001';
  const calls=[];
  const data=await resolveTenantNames([platform,'tenant-a','tenant-b'],async params=>{
    calls.push(params.offset);
    return params.offset===0 ? {data:[{id:'org-a',name:'AmmoSync'},{id:'unrelated',name:'Not on this box'}],totalCount:3}
      : {data:[{id:'org-new-b',name:'Sample Works'}],totalCount:3};
  },id=>({'org-a':'tenant-a','org-new-b':'tenant-b'})[id]??'outside');
  assert.deepEqual(calls,[0,2]);
  assert.deepEqual(data.tenant_names,{[platform]:'Tervory','tenant-a':'AmmoSync','tenant-b':'Sample Works'});
  assert.equal(data.tenant_names_note,null);
  const missing=await resolveTenantNames(['tenant-a'],async()=>{throw Error('unavailable')},id=>id);
  assert.equal(missing.tenant_names['tenant-a'],'Name unavailable (1)');
  assert.ok(missing.tenant_names_note);
  console.log('Tenant names: pagination, alias mapping, box isolation and visible failure passed.');
})().catch(err=>{console.error(err);process.exitCode=1});
