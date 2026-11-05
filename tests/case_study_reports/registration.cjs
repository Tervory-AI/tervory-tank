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
let session = { userId: 'alice', orgId: '60001' }, orgError, authError, membershipError, creations = 0;
const signin = {
  auth: async () => { if (authError) throw authError; return {...session, tenantId: session.orgId ? bindings[session.orgId] : null}; },
  currentUser: async () => ({ firstName: 'Alice' }),
  signinDirectory: async () => ({
    organizations: {
      getOrganization: async ({ organizationId }) => { if (orgError) throw orgError; return { id: organizationId, name: 'Workspace' }; },
      createOrganization: async () => { creations++; return { id: 'org_personal', name: 'Alice workspace' }; },
    },
    users: { getOrganizationMembershipList: async () => { if (membershipError) throw membershipError; return { data: [] }; } },
  }),
};
const bindings = Object.fromEntries(['60001', '60002', '60003', ...[301,302,307,308,401,403,400,404,422].map(status => `org_denied_${status}`), ...[408,429,500,502,503,504,'network'].map(status => `org_${status}`)].map((org, index) => [org, `00000000-0000-4000-8000-${String(index + 11).padStart(12, '0')}`]));
const originalLoad = Module._load;
Module._load = function (name, parent, ...rest) {
  if (name === 'next/headers') return {cookies: async () => ({get: () => undefined})};
  if (name === '@/lib/trigger-signin' || name === './trigger-signin') return signin;
  if (name === '@/lib/trigger-signin-fetch') return {signinFetch: (...args) => global.fetch(...args)};
  if (name === './trigger-signin-principal') return {tenantBindings: () => bindings};
  if (name === 'server-only') return {};
  return originalLoad.call(this, name, parent, ...rest);
};
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = 'dummy-offline';
let now = Date.now(), calls = [], mode = 503, release;
Date.now = () => now;
const events = [];
console.warn = (...args) => events.push(args);
console.info = (...args) => events.push(args);
global.fetch = async (url, init) => {
  assert.equal(new URL(url).origin, process.env.TANK_URL);
  assert.equal(init.method, 'POST');
  assert.equal(init.redirect, 'manual');
  assert.ok(init.signal instanceof AbortSignal);
  calls.push(init.headers);
  if (mode === 'network') throw new TypeError('private transport detail');
  if (mode === 'bug') throw new Error('programming error');
  if (mode === 'wait') await new Promise(resolve => { release = resolve; });
  if (mode === 'timeout') await new Promise((resolve, reject) => init.signal.addEventListener('abort', () => reject(init.signal.reason)));
  return new Response('', { status: typeof mode === 'number' ? mode : 200 });
};
const tenant = require('../../workspace/lib/tenant.ts');
const tank = require('../../workspace/lib/tank.ts');
(async () => {
  const a = await tenant.currentTenant();
  assert.equal(a.tenantId, tenant.tenantIdFor('60001'));
  assert.deepEqual(await tenant.activeTenant(), a);
  assert.equal(calls.length, 1); // Outage backoff.
  now += 1000;
  await tenant.activeTenant();
  assert.equal(calls.length, 2);
  now += 1999;
  await tenant.activeTenant();
  assert.equal(calls.length, 2);
  now++;
  mode = 200;
  await tenant.activeTenant();
  assert.equal(calls.length, 3);
  assert.ok(events.some(([event]) => event === 'case_study_registration_recovered'));
  now += 30_000;
  mode = 'wait';
  const first = tenant.activeTenant();
  await new Promise(setImmediate);
  const second = tenant.currentTenant();
  await new Promise(setImmediate);
  assert.equal(calls.length, 4); // Concurrent requests coalesce.
  release();
  await Promise.all([first, second]);
  // A different actor in the same tenant never inherits a success cooldown.
  session = { userId: 'bob', orgId: '60001' };
  mode = 403;
  await assert.rejects(tenant.activeTenant);
  for (const status of [301, 302, 307, 308, 401, 403, 400, 404, 422]) {
    session = { userId: 'alice', orgId: `org_denied_${status}` };
    mode = status;
    await assert.rejects(tenant.activeTenant);
    await assert.rejects(tenant.activeTenant); // Failure never becomes cached approval.
  }
  authError = new Error('Trigger sign-in auth failed');
  await assert.rejects(tenant.currentTenant, /Trigger sign-in auth failed/);
  await assert.rejects(tenant.activeTenant, /Trigger sign-in auth failed/);
  authError = undefined;
  session = { userId: 'alice', orgId: null };
  await assert.rejects(tenant.currentTenant, /Trigger sign-in required/);
  session = { userId: null, orgId: null };
  assert.equal(await tenant.activeTenant(), null);
  await assert.rejects(tenant.currentTenant, /Trigger sign-in required/);
  session = { userId: 'alice', orgId: null };
  assert.equal(await tenant.activeTenant(), null);
  assert.equal(creations, 0);
  mode = 'network';
  await assert.rejects(tenant.currentTenant, /Trigger sign-in required/);
  assert.equal(creations, 0);
  for (const modeValue of [408, 429, 500, 502, 503, 504, 'network']) {
    mode = modeValue;
    session = { userId: 'bob', orgId: `org_${modeValue}` };
    assert.equal((await tenant.activeTenant()).userId, 'bob');
    assert.equal(calls.at(-1)['X-Tervory-Tenant'], tenant.tenantIdFor(session.orgId));
    assert.equal(calls.at(-1)['X-Tervory-User'], 'bob');
  }
  // Reload the helper to model a process restart: durable identity is enough to
  // reconcile again; no pending in-memory task is required for recovery.
  delete require.cache[require.resolve('../../workspace/lib/tank.ts')];
  mode = 200;
  const restarted = require('../../workspace/lib/tank.ts');
  const beforeRestart = calls.length;
  await restarted.ensureCaseStudyReports({ tenantId: a.tenantId, userId: a.userId });
  assert.equal(calls.length, beforeRestart + 1);
  assert.equal(calls.at(-1)['X-Tervory-Tenant'], a.tenantId);
  mode = 'bug';
  await assert.rejects(() => tank.ensureCaseStudyReports({ tenantId: 'bug', userId: 'alice' }), /programming error/);
  mode = 'timeout';
  // AbortSignal.timeout uses an unref timer; keep this offline process alive.
  const keepAlive = setInterval(() => {}, 100);
  const started = performance.now();
  await tank.ensureCaseStudyReports({ tenantId: 'timeout', userId: 'alice' });
  clearInterval(keepAlive);
  assert.ok(performance.now() - started < 2500);
  assert.ok(!JSON.stringify(events).includes('private transport detail'));
  console.log('PASS: reporting outage recovery/backoff/single-flight, timeout, strict errors, Trigger sign-in denial, personal/no-org behavior and tenant/actor isolation');
})().catch(error => { console.error(error); process.exitCode = 1; });
