const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../../workspace/node_modules/typescript');
const root = path.resolve(__dirname, '../..');
function load(file, bindings = {}, globals = {}) {
  const source = fs.readFileSync(path.join(root, file), 'utf8');
  const code = ts.transpileModule(source, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const exports = {};
  vm.runInNewContext(code, {exports, require: name => {assert(name in bindings, name);return bindings[name];},
    process:{env:{TERVORY_ADMIN_USER_IDS:'owner'}}, URL, Uint8Array, TextDecoder, Set, Error, ...globals});
  return exports;
}
async function main() {
  const calls=[];
  let session={userId:'owner',orgRole:'org:member'};
  const actor={tenantId:'active-tenant',userId:'owner'};
  const tank=load('workspace/lib/tank.ts',{}, {fetch:async(url,options)=>{
    calls.push({url,options});
    return {ok:true,json:async()=>url.endsWith('/delete-products')?{deleted:2}:{products:0,product_rows:[]}};
  }});
  const actions=load('workspace/app/rig/admin/actions.ts',{
    '@clerk/nextjs/server':{auth:async()=>session},
    '@/lib/tenant':{activeTenant:async()=>({...actor,userId:session.userId})},
    '../../review/founder':load('workspace/app/review/founder.ts'),
    '@/lib/tank':tank,
  });
  const route=load('workspace/app/rig/admin/api/route.ts',{
    '../actions':actions,'next/server':{NextResponse:{json:(body,options={})=>({body,status:options.status||200})}},
  });
  function request(origin='https://app.example') {
    const bytes=new TextEncoder().encode(JSON.stringify({operation:'delete-products',data:{skus:['A','B'],tenant_id:'forged-tenant'}}));
    return {headers:new Headers({origin,host:'app.example'}),body:new ReadableStream({start(c){c.enqueue(bytes);c.close();}})};
  }
  let response=await route.POST(request());
  assert.equal(response.body.ok,true);
  assert.equal(response.body.message,'2 deleted.');
  assert.equal(response.body.deleted,2);
  assert.equal(calls[0].options.headers['x-tervory-tenant'],'active-tenant');
  assert.equal(calls[0].options.headers['x-tervory-user'],'owner');
  assert.equal(calls[0].options.cache,'no-store');
  assert(calls[0].url.endsWith('/v1/access/rig/admin/delete-products'));
  session={userId:'retailer-admin',orgRole:'org:admin'};
  assert.equal((await route.POST(request())).body.ok,true);
  session={userId:'member',orgRole:'org:member'};
  const count=calls.length;
  assert.equal((await route.POST(request())).status,403);
  session={userId:'owner',orgRole:'org:member'};
  assert.equal((await route.POST(request('https://other.example'))).status,403);
  assert.equal(calls.length,count);
  console.log('PASS: real Workspace route/actions/Tank helper; founder, org admin, member denial, origin and active tenant.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
