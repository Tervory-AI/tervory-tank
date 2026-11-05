// Execute the actual Workspace tenant, Tank helper and API route with Trigger sign-in/fetch stubs.
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
let session = {userId: 'client-a', orgId: '60001'};
let creations = 0;
let membership = [];
const signin = {
  auth: async () => ({...session, tenantId: session.orgId ? bindings[session.orgId] : null}),
  currentUser: async () => ({firstName: 'Offline'}),
  signinDirectory: async () => ({
    organizations: {
      getOrganization: async ({organizationId}) => ({id: organizationId, name: 'Offline'}),
      createOrganization: async () => {creations++; return {id: '60003', name: 'Offline'};},
    },
    users: {getOrganizationMembershipList: async () => ({data: membership})},
  }),
};
const bindings = Object.fromEntries(['60001', '60002', '60003', ...[301,302,307,308,401,403,400,404,422].map(status => `org_denied_${status}`), ...[408,429,500,502,503,504,'network'].map(status => `org_${status}`)].map((org, index) => [org, `00000000-0000-4000-8000-${String(index + 11).padStart(12, '0')}`]));
const originalLoad = Module._load;
Module._load = function (name, parent, ...rest) {
  if (name === '@/lib/trigger-signin' || name === './trigger-signin') return signin;
  if (name === '@/lib/trigger-signin-fetch') return {signinFetch: (...args) => global.fetch(...args)};
  if (name === './trigger-signin-principal') return {tenantBindings: () => bindings};
  if (name === 'server-only') return {};
  return originalLoad.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'dummy-offline';
process.env.TANK_REGION = 'us-east';
process.env.TERVORY_ADMIN_USER_IDS = 'founder';
const {legacyHome} = require('../legacy_tenant_home.cjs');
const homeLookups = [];
const calls = [];
let fail = false;
global.fetch = async (url, init) => {
  const home = legacyHome(url,init,{tenants:Object.values(bindings),key:'dummy-offline',origin:process.env.TANK_URL,calls:homeLookups});
  if(home)return home;
  init = {...init, headers:Object.fromEntries(new Headers(init.headers))};
  assert.equal(new URL(url).origin, 'http://tank.offline.invalid');
  calls.push({url: new URL(url), ...init});
  if (fail) throw new Error('offline failure');
  return Response.json({tenant_id: init.headers['x-tervory-tenant'], products: []});
};
const tenants = require('../../workspace/lib/tenant.ts');
const tank = require('../../workspace/lib/tank.ts');
const route = require('../../workspace/app/api/case-studies/[[...path]]/route.ts');
const get = (parts = [], query = '') => route.GET(new Request('https://workspace.offline.invalid/api/case-studies?' + query, {
  headers: {'X-Tervory-Tenant': 'forged', 'X-Tervory-User': 'founder', 'X-Tank-Key': 'forged'},
}), {params: Promise.resolve({path: parts})});
(async () => {
  session = {userId: 'client-a', orgId: null};
  await assert.rejects(tenants.currentTenant(), /Trigger sign-in required/);
  assert.equal(creations, 0);
  session = {userId: 'client-a', orgId: '60001'};
  let response = await get(['base'], 'start=2026-10-01&user_id=forged');
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  assert(homeLookups.length > 0);
  const sent = calls.at(-1);
  assert.equal(sent.method, 'GET');
  assert.equal(sent.headers['x-tervory-user'], 'client-a');
  assert.equal(sent.headers['x-tervory-tenant'], tenants.tenantIdFor('60001'));
  assert.equal(sent.url.searchParams.get('tenant_id'), tenants.tenantIdFor('60001'));
  assert.equal(sent.url.searchParams.get('user_id'), null);
  assert.equal(sent.cache, 'no-store');
  const reads = () => calls.filter(call => call.method === 'GET').length;
  const before = reads();
  for (const [parts, query, status] of [[['base'], 'tenant_id=' + tenants.tenantIdFor('60002'), 403], [['clients'], '', 403], [['ensure'], '', 404], [['base', 'extra'], '', 404]]) {
    response = await get(parts, query);
    assert.equal(response.status, status);
    assert.equal(await response.text(), '');
  }
  assert.equal(reads(), before);
  session = {userId: 'client-b', orgId: '60002'};
  await get(['base']);
  assert.equal(calls.at(-1).headers['x-tervory-tenant'], tenants.tenantIdFor('60002'));
  session = {userId: 'founder', orgId: '60001'};
  assert.equal((await get(['clients'])).status, 200);
  assert.equal((await get(['base'], 'tenant_id=' + tenants.tenantIdFor('60002'))).status, 200);
  assert.equal(calls.at(-1).url.searchParams.get('tenant_id'), tenants.tenantIdFor('60002'));
  session = {userId: null, orgId: null};
  const count = calls.length, homeCount = homeLookups.length;
  assert.equal((await get(['base'])).status, 401);
  assert.equal(calls.length, count);
  assert.equal(homeLookups.length, homeCount);
  session = {userId: 'client-a', orgId: '60001'};
  fail = true;
  response = await get(['base']);
  assert.equal(response.status, 503);
  assert.equal(await response.text(), ''); // No new page/error wording.
  await assert.rejects(() => tank.caseStudyRequest({tenantId: 'a', userId: 'a'}, 'https://other.invalid'));
  console.log('PASS: existing signup and membership registration, two tenants, founder access, forged identity/path refusal, no-store and empty error bodies.');
})().catch(error => {console.error(error); process.exitCode = 1;});
