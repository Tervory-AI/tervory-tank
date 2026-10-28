// Exercise the actual route, goldIdentity, founder gate and Tank helper offline.
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
let session = {userId: 'client-a', orgRole: 'org:member'};
const load = Module._load;
Module._load = function(name, parent, ...rest) {
  if (name === 'server-only') return {};
  if (name === 'next/navigation') return {notFound: () => {throw Object.assign(new Error(), {status: 404});}};
  if (name === '@clerk/nextjs/server') return {
    auth: async () => session,
    clerkClient: async () => ({users: {getUser: async () => ({publicMetadata: {jurisdiction: 'za', admission_no: 'offline-admission'}})}}),
  };
  return load.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'offline-workspace';
process.env.TERVORY_ADMIN_USER_IDS = 'offline-founder';
const id = '33333333-3333-4333-8333-333333333333';
const row = {id, tenant_id: '44444444-4444-4444-8444-444444444444', agent: 'tank',
  claim: 'Offline contract check.', evidence: [], confidence: 0.5, last_verified: null,
  embed_model: '', created_at: '2026-10-28T00:00:00+00:00', updated_at: '2026-10-28T00:00:00+00:00'};
const calls = [];
let status = 200;
let fail = false;
global.fetch = async (target, init) => {
  const url = new URL(target);
  assert.equal(url.origin, 'http://tank.offline.invalid');
  calls.push({url, ...init});
  if (fail) throw new Error('offline transport failure');
  return Response.json(status === 200 ? row : {detail: 'upstream internal detail'}, {status});
};
const {GET} = require('../../workspace/app/api/memory/records/[id]/route.ts');
async function get(recordId = id) {
  try {
    return await GET(new Request('https://workspace.offline.invalid/api/memory/records/' + recordId + '?tenant_id=forged&scope=tenant&url=https://other.invalid', {
      headers: {'X-Tervory-User': 'offline-founder', 'X-Tervory-Tenant': 'forged', 'X-Tank-Key': 'forged'},
    }), {params: Promise.resolve({id: recordId})});
  } catch (error) {
    if (error.status === 404) return new Response(null, {status: 404});
    throw error;
  }
}
(async () => {
  for (const userId of ['client-a', 'client-b', 'offline-reviewer', null]) {
    session = {userId, orgRole: userId === 'offline-reviewer' ? 'org:reviewer' : 'org:member'};
    const response = await get();
    assert.equal(response.status, 404);
    assert.equal(await response.text(), '');
  }
  assert.equal(calls.length, 0);
  session = {userId: 'offline-founder', orgRole: null};
  for (const invalid of ['..', '../publish', 'bad-id', id + '?tenant_id=forged']) {
    assert.equal((await get(invalid)).status, 404);
  }
  assert.equal(calls.length, 0);
  const response = await get();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  assert.deepEqual(await response.json(), row);
  const sent = calls[0];
  assert.equal(sent.url.pathname, '/v1/memory/records/' + id);
  assert.equal(sent.url.search, '');
  assert.equal(sent.method, 'GET');
  assert.equal(sent.headers['X-Tervory-User'], 'offline-founder');
  assert.equal(sent.headers['X-Tervory-Tenant'], '00000000-0000-0000-0000-000000000001');
  assert.equal(sent.headers['X-Tervory-Role'], 'founder');
  assert.equal(sent.headers['X-Tank-Key'], 'offline-workspace');
  assert.equal(sent.cache, 'no-store');
  assert.equal(sent.redirect, 'error');
  for (status of [404, 409, 503]) {
    const refused = await get();
    assert.equal(refused.status, status);
    assert.equal(await refused.text(), '');
    assert.equal(refused.headers.get('cache-control'), 'private, no-store');
  }
  fail = true;
  const broken = await get();
  assert.equal(broken.status, 503);
  assert.equal(await broken.text(), '');
  console.log('PASS: founder-only memory JSON, two-client/reviewer refusal, trusted identity, fixed GET path, no-store, empty error bodies.');
})().catch(error => {console.error(error); process.exitCode = 1;});
