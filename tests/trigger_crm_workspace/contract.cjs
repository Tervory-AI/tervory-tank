// Offline boundary proof: actual route, tenant alias derivation and Tank adapter; no CRM records or provider calls.
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
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText, filename);
let session = { userId: 'offline-founder', orgId: 'org_offline' };
const load = Module._load;
Module._load = function(name, parent, ...rest) {
  if (name === 'server-only') return {};
  if (name === '@clerk/nextjs/server') return { auth: async () => session };
  return load.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'dummy-workspace-key';
process.env.TERVORY_ADMIN_USER_IDS = 'offline-founder';
process.env.TERVORY_TENANT_ALIASES = 'org_offline=org_previous';
const { tenantIdFor } = require('../../workspace/lib/tenant.ts');
const { crmReadPath, crmReadQuery } = require('../../workspace/lib/trigger-crm.ts');
const { triggerCrmRead } = require('../../workspace/lib/tank.ts');
const route = require('../../workspace/app/api/trigger-crm/[...path]/route.ts');
const id = '33333333-3333-4333-8333-333333333333';
let count = 0;
let upstream = () => Response.json({ resource: 'leads', items: [], page: 1, count: 0 });
global.fetch = async (target, init) => {
  count++;
  const url = new URL(target);
  assert.equal(url.origin, 'http://tank.offline.invalid');
  assert.equal(init.method, 'GET');
  assert.equal(init.cache, 'no-store');
  assert.equal(init.redirect, 'error');
  assert.deepEqual(init.headers, {
    accept: 'application/json', 'x-tank-key': 'dummy-workspace-key',
    'x-tervory-user': session.userId, 'x-tervory-admin': session.userId,
    'x-tervory-tenant': tenantIdFor('org_offline'),
  });
  assert.equal(url.searchParams.has('tenant_id'), false);
  assert.equal(url.searchParams.has('user_id'), false);
  return upstream(url, init);
};
async function get(parts = ['leads'], query = '') {
  return route.GET(new Request('https://app.offline.invalid/api/trigger-crm/' + parts.join('/') + query, {
    headers: { 'x-tank-key': 'forged', 'x-tervory-user': 'forged', 'x-tervory-tenant': 'forged', authorization: 'forged', cookie: 'forged' },
  }), { params: Promise.resolve({ path: parts }) });
}
(async () => {
  for (const denied of [null]) {
    session = { userId: denied, orgId: 'org_offline' };
    assert.equal((await get()).status, 404);
  }
  session = { userId: 'offline-founder', orgId: null };
  assert.equal((await get()).status, 404);
  assert.equal(count, 0);
  session = { userId: 'offline-founder', orgId: 'org_offline' };
  for (const parts of [[], ['invoices'], ['accounts'], ['leads', '..'], ['leads', id, 'send'], ['https://evil.invalid'], ['leads?tenant_id=x']]) {
    assert.equal((await get(parts)).status, 404);
    assert.equal(crmReadPath(parts), null);
  }
  for (const query of ['?tenant_id=forged', '?url=https://evil.invalid', '?page=0', '?page=10001', '?page=1&page=2', '?page=-1', '?page=01', '?page=1.1', '?page=']) assert.equal((await get(['leads'], query)).status, 404);
  assert.equal((await get(['leads', id], '?page=1')).status, 404);
  assert.equal(count, 0);
  assert.equal(crmReadQuery(new URLSearchParams('page=10000'), false).get('page'), '10000');
  const ok = await get(['leads'], '?page=2');
  assert.equal(ok.status, 200);
  assert.equal(ok.headers.get('cache-control'), 'private, no-store');
  assert.equal(ok.headers.get('x-content-type-options'), 'nosniff');
  assert.deepEqual(await ok.json(), { resource: 'leads', items: [], page: 1, count: 0 });
  assert.equal(tenantIdFor('org_previous'), tenantIdFor('org_offline'));
  for (const denied of [
    { userId: 'offline-client', orgId: 'org_offline', grants: ['trigger'] },
    { userId: 'offline-admin', orgId: 'org_offline', orgRole: 'org:admin', grants: ['trigger'] },
    { userId: 'offline-member', orgId: 'org_offline', orgRole: 'org:member' },
  ]) {
    session = denied;
    const before = count;
    assert.equal((await get()).status, 404);
    assert.equal((await get(['contacts', id])).status, 404);
    assert.equal(count, before, 'nonfounders must be refused before Tank transport');
  }
  session = { userId: 'offline-founder', orgId: 'org_offline' };
  for (const resource of ['contacts', 'estimates']) {
    upstream = () => Response.json({ resource, item: { id } });
    assert.equal((await get([resource, id])).status, 200);
  }
  for (const status of [403, 404, 422, 502, 503, 401, 500]) {
    upstream = () => Response.json({ token: 'DO_NOT_REFLECT', detail: 'upstream internal' }, { status });
    const response = await get();
    assert.equal(response.status, [403, 404, 422, 502, 503].includes(status) ? status : 502);
    assert.equal(await response.text(), '');
  }
  for (const data of [[], null, { resource: 'contacts', items: [] }, { resource: 'leads', items: {} }]) {
    upstream = () => Response.json(data);
    assert.equal((await get()).status, 502);
  }
  upstream = () => { throw new Error('sensitive upstream exception'); };
  const unavailable = await get();
  assert.equal(unavailable.status, 503);
  assert.equal(await unavailable.text(), '');
  const before = count;
  await assert.rejects(triggerCrmRead({ userId: 'offline-founder', tenantId: 'ignored' }, ['../admin'], new URLSearchParams()), /invalid_crm_request/);
  assert.equal(count, before);
  assert.deepEqual(Object.keys(route).sort(), ['GET', 'dynamic', 'runtime']);
  console.log('PASS: founder-only read corridor; granted client, tenant admin and member refused before transport, active-tenant aliases, path/query allowlists, no mutation export, same-box forwarding, empty errors, response envelope checks');
})().catch(error => { console.error(error); process.exitCode = 1; });
