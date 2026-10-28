// Run the actual founder route, Clerk tenant mapping and Tank helper offline.
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
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true},
}).outputText, filename);
let session = {userId: 'client-a', orgId: 'org_a'};
const load = Module._load;
Module._load = function(name, parent, ...rest) {
  if (name === 'server-only') return {};
  if (name === '@clerk/nextjs/server') return {
    auth: async () => session,
    clerkClient: async () => ({organizations: {getOrganization: async ({organizationId}) => ({id: organizationId, name: 'Offline'})}}),
  };
  return load.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'dummy-offline';
process.env.TERVORY_ADMIN_USER_IDS = 'founder';
const calls = [];
let fail = false;
global.fetch = async (target, init) => {
  const url = new URL(target);
  assert.equal(url.origin, 'http://tank.offline.invalid');
  calls.push({url, ...init});
  if (fail) throw new Error('offline failure');
  return Response.json(url.pathname.endsWith('/ensure') ? {products: []} : {history: []});
};
const {tenantIdFor} = require('../../workspace/lib/tenant.ts');
const {GET} = require('../../workspace/app/rig/price-history/route.ts');
const get = (query = '') => GET(new Request('https://workspace.offline.invalid/rig/price-history?' + query, {
  headers: {'X-Tervory-User': 'founder', 'X-Tervory-Tenant': 'forged', 'X-Tank-Key': 'forged'},
}));
(async () => {
  for (const userId of ['client-a', 'client-b', null]) {
    session = {userId, orgId: 'org_a'};
    const response = await get();
    assert.equal(response.status, 403);
    assert.equal(await response.text(), '');
  }
  assert.equal(calls.length, 0);
  session = {userId: 'founder', orgId: 'org_a'};
  const response = await get('tenant_id=' + tenantIdFor('org_b') + '&product_id=part%2B7&offset=2&limit=10&url=https://other.invalid&user_id=forged');
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  const sent = calls.at(-1);
  assert.equal(sent.url.pathname, '/v1/agents/rig/price-history');
  assert.equal(sent.url.searchParams.get('tenant_id'), tenantIdFor('org_b'));
  assert.equal(sent.url.searchParams.get('product_id'), 'part+7');
  assert.deepEqual([...sent.url.searchParams.keys()].sort(), ['limit', 'offset', 'product_id', 'tenant_id']);
  assert.equal(sent.headers['X-Tervory-Tenant'], tenantIdFor('org_a'));
  assert.equal(sent.headers['X-Tervory-User'], 'founder');
  assert.equal(sent.cache, 'no-store');
  assert.equal(sent.redirect, 'error');
  session = {userId: 'founder', orgId: null};
  assert.equal((await get()).status, 401);
  session = {userId: 'founder', orgId: 'org_a'};
  fail = true;
  const broken = await get();
  assert.equal(broken.status, 503);
  assert.equal(await broken.text(), '');
  console.log('PASS: founder-only JSON, client/forged identity refusal, trusted tenant, fixed Tank path, no-store, empty error bodies.');
})().catch(error => {console.error(error); process.exitCode = 1;});
