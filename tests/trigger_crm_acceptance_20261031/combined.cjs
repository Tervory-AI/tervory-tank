// Actual Workspace route and adapter to actual loopback Tank; no external network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = process.env.CRM_ASSEMBLED_ROOT;
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  return resolve.call(this, name.startsWith('@/') ? path.join(root, 'workspace', name.slice(2)) : name, parent, ...rest);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
}).outputText, filename);
let session = { userId: 'offline-founder', orgId: 'org_offline_crm' };
const load = Module._load;
Module._load = function(name, parent, ...rest) {
  if (name === 'server-only') return {};
  if (name === '@clerk/nextjs/server') return { auth: async () => session };
  return load.call(this, name, parent, ...rest);
};
process.env.TANK_API_KEY = 'dummy-workspace-key';
process.env.TERVORY_ADMIN_USER_IDS = 'offline-founder';
const route = require(path.join(root, 'workspace/app/api/trigger-crm/[...path]/route.ts'));
async function get(parts, query = '') {
  return route.GET(new Request('https://offline.invalid/api/trigger-crm/' + parts.join('/') + query, {
    headers: { 'x-tervory-tenant': 'forged', 'x-tervory-user': 'forged', authorization: 'Bearer dummy-browser-key' },
  }), { params: Promise.resolve({ path: parts }) });
}
(async () => {
  for (const resource of ['leads', 'contacts', 'estimates']) {
    const response = await get([resource], '?page=2');
    assert.equal(response.status, 200);
    const data = await response.json();
    assert.equal(data.resource, resource);
    assert.equal(data.page, 2);
    assert.equal(data.items.length, 1);
    assert.equal(data.items[0].id, '00000000-0000-0000-0000-000000000013');
    assert.equal(data.items[0].public_token, undefined);
    assert.equal(data.items[0].org, undefined);
    assert.equal(data.items[0].password, undefined);
    assert.equal(JSON.stringify(data).includes('dummy-crm-token'), false);
    assert.equal(response.headers.get('cache-control'), 'private, no-store');
  }
  session.orgId = 'org_unconfigured';
  assert.equal((await get(['contacts'])).status, 503);
  for (const denied of [
    { userId: 'offline-client', orgId: 'org_offline_crm', grants: ['trigger'] },
    { userId: 'offline-admin', orgId: 'org_offline_crm', orgRole: 'org:admin', grants: ['trigger'] },
    { userId: 'offline-member', orgId: 'org_offline_crm', orgRole: 'org:member' },
  ]) {
    session = denied;
    assert.equal((await get(['contacts'], '?page=2')).status, 404);
  }
  session = { userId: null, orgId: 'org_offline_crm' };
  assert.equal((await get(['contacts'])).status, 404);
  session = { userId: 'offline-founder', orgId: 'org_offline_crm' };
  for (const parts of [['contacts','../admin'], ['contacts','x','send'], ['public']]) assert.equal((await get(parts)).status,404);
  assert.equal((await get(['contacts'],'?tenant_id=forged')).status,404);
  assert.equal(route.POST, undefined);
  console.log('PASS actual Workspace → Tank → fake BottleCRM; 3 envelopes, offset pagination, founder/tenant isolation, no credential reflection, read-only route');
})().catch(error => { console.error(error); process.exitCode = 1; });
