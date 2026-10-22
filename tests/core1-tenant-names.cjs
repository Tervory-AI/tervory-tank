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
  assert.deepEqual(data.tenant_names,{[platform]:'Tervory (platform)','tenant-a':'AmmoSync','tenant-b':'Sample Works'});
  assert.equal(data.tenant_names_note,null);
  const missing=await resolveTenantNames(['tenant-a'],async()=>{throw Error('unavailable')},id=>id);
  assert.equal(missing.tenant_names['tenant-a'],'Unlinked account 1');
  assert.ok(missing.tenant_names_note);
  const migrated=await resolveTenantNames([platform,'tenant-old','tenant-new','tenant-orphan'],async()=>({
    data:[{id:'org-current',name:'Tervory',slug:'tervory'}],totalCount:1,
  }),()=> 'tenant-old',()=> 'tenant-new');
  assert.equal(migrated.tenant_names[platform],'Tervory (platform)');
  assert.equal(migrated.tenant_names['tenant-old'],'Tervory');
  assert.equal(migrated.tenant_names['tenant-new'],'Tervory (before account link)');
  assert.equal(migrated.tenant_names['tenant-orphan'],'Unlinked account 1');
  assert.equal(new Set(Object.values(migrated.tenant_names)).size,4);
  assert(!Object.values(migrated.tenant_names).some(name=>name.includes('Name unavailable')));
  // Repeated client names are distinct choices; unrelated orgs never appear.
  const duplicates=await resolveTenantNames(['tenant-a','tenant-b'],async()=>({data:[
    {id:'tenant-a',name:'Acme',slug:'acme-east'}, {id:'tenant-b',name:'Acme',slug:'acme-west'},
    {id:'outside',name:'Private outside account'},
  ],totalCount:3}),id=>id);
  assert.equal(duplicates.tenant_names['tenant-a'],'Acme (acme-east)');
  assert.equal(duplicates.tenant_names['tenant-b'],'Acme (acme-west)');
  assert(!Object.values(duplicates.tenant_names).includes('Private outside account'));
  // Old account names must not win just because they appear on the first page.
  const renamed=await resolveTenantNames(['old-tenant'],async({offset})=>offset===0
    ? {data:[{id:'old-org',name:'Before rename'}],totalCount:2}
    : {data:[{id:'new-org',name:'After rename'}],totalCount:2},()=> 'old-tenant',id=>id==='old-org'?'old-tenant':'new-tenant');
  assert.equal(renamed.tenant_names['old-tenant'],'After rename');
  console.log('Tenant names: pagination, alias mapping, box isolation and visible failure passed.');
})().catch(err=>{console.error(err);process.exitCode=1});
