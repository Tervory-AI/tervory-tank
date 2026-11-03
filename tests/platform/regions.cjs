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
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'offline-us';
process.env.TANK_URL_ZA = 'https://za.offline.invalid';
process.env.TANK_API_KEY_ZA = 'offline-za';
const tenant = '11111111-1111-4111-8111-111111111111';
const calls = [];
let missing = false;
global.fetch = async (target, init) => {
  const url = new URL(target); calls.push({url, init});
  if (url.pathname.startsWith('/v1/tenants/')) {
    assert.equal(url.origin, process.env.TANK_URL);
    assert.equal(new Headers(init.headers).get('x-tank-key'), 'offline-us');
    assert.equal(init.body, undefined); // No content leaves before routing authority is known.
    return missing ? new Response('', {status: 409}) : Response.json({home_region: 'za'});
  }
  assert.equal(url.origin, process.env.TANK_URL_ZA);
  assert.equal(new Headers(init.headers).get('x-tank-key'), 'offline-za');
  assert.equal(JSON.parse(init.body).home_region, 'za');
  return Response.json({ok: true});
};
(async () => {
  const tank = require('../../workspace/lib/tank.ts');
  await tank.tenantFetch(process.env.TANK_URL+'/v1/route', {method:'POST', headers:{'x-tank-key':'offline-us'},
    body:JSON.stringify({tenant_id:tenant, home_region:'us-east', messages:[{content:'private input'}]})});
  assert.equal(calls.length, 2);
  assert.equal(calls[0].url.pathname, '/v1/tenants/'+tenant);
  missing = true;
  await assert.rejects(() => tank.tenantFetch(process.env.TANK_URL+'/v1/route', {method:'POST', body:JSON.stringify({tenant_id:tenant})}));
  assert.equal(calls.length, 3); // No content request after failed authority lookup.
  await assert.rejects(() => tank.tenantFetch(process.env.TANK_URL+'/v1/route?tenant_id=other', {
    method:'POST', body:JSON.stringify({tenant_id:tenant})}));
  assert.equal(calls.length, 3);
  console.log('PASS: recorded ZA home, ZA key, authority-only lookup, missing-home refusal and mixed-tenant refusal.');
})().catch(error => { console.error(error); process.exitCode=1; });
