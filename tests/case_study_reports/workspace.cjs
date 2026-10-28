// Execute the actual Workspace tenant, Tank helper and API route with Clerk/fetch stubs.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function (name, parent, ...rest) {
  if (name.startsWith('@/')) name = path.join(root, 'workspace', name.slice(2));
  return originalResolve.call(this, name, parent, ...rest);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true},
}).outputText, filename);
let session = {userId: 'client-a', orgId: 'org_a'};
let creations = 0;
let membership = [];
const clerk = {
  auth: async () => session,
  currentUser: async () => ({firstName: 'Offline'}),
  clerkClient: async () => ({
    organizations: {
      getOrganization: async ({organizationId}) => ({id: organizationId, name: 'Offline'}),
      createOrganization: async () => {creations++; return {id: 'org_new', name: 'Offline'};},
    },
    users: {getOrganizationMembershipList: async () => ({data: membership})},
  }),
};
const originalLoad = Module._load;
Module._load = function (name, parent, ...rest) {
  if (name === '@clerk/nextjs/server') return clerk;
  if (name === 'server-only') return {};
  return originalLoad.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'unused-offline';
process.env.TERVORY_ADMIN_USER_IDS = 'founder';
const calls = [];
let fail = false;
global.fetch = async (url, init) => {
  assert.equal(new URL(url).origin, 'http://tank.offline.invalid');
  calls.push({url: new URL(url), ...init});
  if (fail) throw new Error('offline failure');
  return Response.json({tenant_id: init.headers['X-Tervory-Tenant'], products: []});
};
const tenants = require('../../workspace/lib/tenant.ts');
const tank = require('../../workspace/lib/tank.ts');
const route = require('../../workspace/app/api/case-studies/[[...path]]/route.ts');
const get = (parts = [], query = '') => route.GET(new Request('https://workspace.offline.invalid/api/case-studies?' + query, {
  headers: {'X-Tervory-Tenant': 'forged', 'X-Tervory-User': 'founder', 'X-Tank-Key': 'forged'},
}), {params: Promise.resolve({path: parts})});
(async () => {
  session = {userId: 'client-a', orgId: null};
  const created = await tenants.currentTenant();
  assert.equal(creations, 1);
  assert.equal(created.tenantId, tenants.tenantIdFor('org_new'));
  assert.equal(calls.at(-1).method, 'POST');
  assert.equal(calls.at(-1).url.pathname, '/v1/case-studies/ensure');
  assert.equal(calls.at(-1).headers['X-Tervory-Tenant'], created.tenantId);
  membership = [{organization: {id: 'org_new', name: 'Offline'}}];
  await tenants.currentTenant();
  assert.equal(creations, 1); // Existing membership is reconciled, not duplicated.
  session = {userId: 'client-a', orgId: 'org_a'};
  let response = await get(['base'], 'start=2026-10-01&user_id=forged');
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  const sent = calls.at(-1);
  assert.equal(sent.method, 'GET');
  assert.equal(sent.headers['X-Tervory-User'], 'client-a');
  assert.equal(sent.headers['X-Tervory-Tenant'], tenants.tenantIdFor('org_a'));
  assert.equal(sent.url.searchParams.get('tenant_id'), tenants.tenantIdFor('org_a'));
  assert.equal(sent.url.searchParams.get('user_id'), null);
  assert.equal(sent.cache, 'no-store');
  const reads = () => calls.filter(call => call.method === 'GET').length;
  const before = reads();
  for (const [parts, query, status] of [[['base'], 'tenant_id=' + tenants.tenantIdFor('org_b'), 403], [['clients'], '', 403], [['ensure'], '', 404], [['base', 'extra'], '', 404]]) {
    response = await get(parts, query);
    assert.equal(response.status, status);
    assert.equal(await response.text(), '');
  }
  assert.equal(reads(), before);
  session = {userId: 'client-b', orgId: 'org_b'};
  await get(['base']);
  assert.equal(calls.at(-1).headers['X-Tervory-Tenant'], tenants.tenantIdFor('org_b'));
  session = {userId: 'founder', orgId: 'org_a'};
  assert.equal((await get(['clients'])).status, 200);
  assert.equal((await get(['base'], 'tenant_id=' + tenants.tenantIdFor('org_b'))).status, 200);
  assert.equal(calls.at(-1).url.searchParams.get('tenant_id'), tenants.tenantIdFor('org_b'));
  session = {userId: null, orgId: null};
  const count = calls.length;
  assert.equal((await get(['base'])).status, 401);
  assert.equal(calls.length, count);
  session = {userId: 'client-a', orgId: 'org_a'};
  fail = true;
  response = await get(['base']);
  assert.equal(response.status, 503);
  assert.equal(await response.text(), ''); // No new page/error wording.
  await assert.rejects(() => tank.caseStudyRequest({tenantId: 'a', userId: 'a'}, 'https://other.invalid'));
  console.log('PASS: existing signup and membership registration, two tenants, founder access, forged identity/path refusal, no-store and empty error bodies.');
})().catch(error => {console.error(error); process.exitCode = 1;});
