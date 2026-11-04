const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, 'workspace', name.slice(2)) : name, parent, ...rest);
};
require.extensions['.ts'] = (module, file) => module._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true},
}).outputText, file);
const identity = {tenantId:'11111111-1111-4111-8111-111111111111',userId:'client-a'};
const load = Module._load;
Module._load = function(name, parent, ...rest) {
  if (name === '@/lib/tenant') return {currentTenant:async()=>identity};
  return load.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'offline-us';
process.env.TANK_URL_ZA = 'https://za.offline.invalid';
process.env.TANK_API_KEY_ZA = 'offline-homes';
process.env.TANK_CONTENT_API_KEY_ZA = 'offline-za';
let calls = 0;
global.fetch = async (target, init) => {
  calls++;
  const url = new URL(target);
  if (url.pathname.startsWith('/v1/tenants/')) return Response.json({home_region:'za'});
  assert.equal(url.origin, process.env.TANK_URL_ZA);
  const headers = new Headers(init.headers);
  assert.equal(headers.get('x-tank-key'), 'offline-za');
  assert.equal(headers.get('x-tervory-tenant'), identity.tenantId);
  assert.equal(headers.get('x-tervory-user'), identity.userId);
  assert.deepEqual(JSON.parse(init.body), {feedback:'wrong',note:'Incorrect total.'});
  return Response.json({ok:true,feedback:'wrong',verdict:'rejected',board_state:'unverified'});
};
(async () => {
  const route = require('../../workspace/app/api/tasks/[id]/feedback/route.ts');
  const request = body => new Request('https://workspace.offline.invalid/api/tasks/task/feedback', {
    method:'POST', body:JSON.stringify(body), headers:{'content-type':'application/json','x-tervory-user':'founder'},
  });
  const context = {params:Promise.resolve({id:'task-id'})};
  for (const value of [{feedback:'wrong'}, {feedback:'wrong',note:' '}, {feedback:{toString:'wrong'}}]) {
    assert.equal((await route.POST(request(value), context)).status, 400);
  }
  assert.equal(calls, 0);
  const response = await route.POST(request({feedback:'wrong',note:'Incorrect total.',tenant_id:'forged',by:'founder'}), context);
  assert.equal(response.status,200);
  assert.equal(response.headers.get('cache-control'),'private, no-store');
  assert.equal((await response.json()).board_state,'unverified');
  assert.equal(calls,2);
  console.log('PASS: wrong requires a note; Clerk identity survives forged fields; feedback follows recorded home and regional key.');
})().catch(error=>{console.error(error);process.exitCode=1;});
