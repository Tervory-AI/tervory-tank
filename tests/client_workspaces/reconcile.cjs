// Execute the actual roster reconcile and instrumentation hook with a fake Clerk and a fake Tank.
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

const SECRETS = ['placeholder-tank-key', 'sk_test_placeholder_clerk', 'placeholder-tank-body', 'placeholder-clerk-detail'];
process.env.TANK_URL = 'http://tank.offline.invalid';
process.env.TANK_API_KEY = SECRETS[0];
process.env.CLERK_SECRET_KEY = SECRETS[1];
delete process.env.TERVORY_TENANT_ALIASES;

// Fake Clerk: organizations in memory; the list query is a case-insensitive substring match.
let orgs = [], clerkCalls = [], failCreate = new Set(), nextId = 1;
class ClerkAPIResponseError extends Error {}
const clerk = {
  auth: async () => { throw new Error('no request in a server-start reconcile'); },
  currentUser: async () => { throw new Error('no request in a server-start reconcile'); },
  clerkClient: async () => ({
    organizations: {
      getOrganizationList: async (params) => {
        clerkCalls.push(['list', params]);
        const hits = orgs.filter(org => org.name.toLowerCase().includes((params.query ?? '').toLowerCase()));
        return {data: hits.slice(params.offset ?? 0, (params.offset ?? 0) + (params.limit ?? 10)), totalCount: hits.length};
      },
      createOrganization: async (params) => {
        clerkCalls.push(['create', params]);
        if (failCreate.has(params.name)) throw new ClerkAPIResponseError('Bearer ' + SECRETS[1] + ' ' + SECRETS[3]);
        const org = {id: 'org_placeholder' + nextId++, name: params.name};
        orgs.push(org);
        return org;
      },
      updateOrganization: async () => { throw new Error('never rename'); },
      deleteOrganization: async () => { throw new Error('never delete'); },
    },
    users: {getOrganizationMembershipList: async () => { throw new Error('not used'); }},
  }),
};
const originalLoad = Module._load;
Module._load = function (name, parent, ...rest) {
  if (name === '@clerk/nextjs/server') return clerk;
  if (name === 'server-only') return {};
  return originalLoad.call(this, name, parent, ...rest);
};

// Fake Tank: case-study ensure and the founder squad endpoint, with real idempotence.
let registered = new Set(), squads = new Map(), changes = [], tankCalls = [];
global.fetch = async (url, init = {}) => {
  url = new URL(url);
  assert.equal(url.origin, 'http://tank.offline.invalid');
  const headers = Object.fromEntries(Object.entries(init.headers ?? {}).map(([k, v]) => [k.toLowerCase(), v]));
  assert.equal(headers['x-tank-key'], SECRETS[0]);
  tankCalls.push({path: url.pathname, method: init.method, headers, body: init.body});
  const tenant = headers['x-tervory-tenant'];
  if (url.pathname === '/v1/case-studies/ensure' && init.method === 'POST') {
    registered.add(tenant);
    return Response.json({tenant_id: tenant, products: [...(squads.get(tenant) ?? [])].sort()});
  }
  const squad = url.pathname.match(/^\/v1\/command\/squads\/([a-z_]+)$/);
  if (squad && init.method === 'PUT') {
    const {enabled} = JSON.parse(init.body);
    assert.equal(enabled, true, 'a product is never turned off');
    const set = squads.get(tenant) ?? new Set();
    squads.set(tenant, set);
    const changed = !set.has(squad[1]);
    set.add(squad[1]);
    if (changed) changes.push([tenant, squad[1]]);
    return Response.json({agent: squad[1], enabled: true, changed});
  }
  return new Response(SECRETS[2], {status: 500});
};

const logs = [];
for (const level of ['log', 'info', 'warn', 'error']) console[level] = (...args) => logs.push(args);
const wsFiles = () => Object.keys(require.cache).filter(file => file.startsWith(path.join(root, 'workspace') + path.sep) && !file.includes('node_modules'));
function fresh() {
  for (const file of wsFiles()) delete require.cache[file];
  return require('../../workspace/lib/client-roster.ts');
}
function reset() {
  orgs = []; clerkCalls = []; failCreate = new Set(); nextId = 1;
  registered = new Set(); squads = new Map(); changes = []; tankCalls = []; logs.length = 0;
}
const EXPECTED = {
  'Custom Nation': ['rig', 'tiger'], 'LOKD Security': ['radix'], AmmoSync: ['base', 'market_lab'], 'Shot Bonus': [], TNGO: [],
};
const FOUNDER = 'user_placeholder_founder';

(async () => {
  // Importing the roster, the tenant helper or the instrumentation hook never reconciles.
  process.env.TERVORY_ADMIN_USER_IDS = FOUNDER;
  let roster = fresh();
  const instrumentation = require('../../workspace/instrumentation.ts');
  assert.equal(clerkCalls.length + tankCalls.length + logs.length, 0, 'nothing runs at import time');
  delete process.env.NEXT_RUNTIME;
  instrumentation.register();
  await new Promise(resolve => setTimeout(resolve, 50));
  assert.equal(clerkCalls.length + tankCalls.length, 0, 'register() does nothing outside the Node runtime');
  assert.deepEqual(roster.CLIENT_ROSTER.map(client => [client.name, [...client.products]]), Object.entries(EXPECTED));

  // First run: five organizations, five tenants, exactly the listed products.
  reset();
  orgs.push({id: 'org_placeholder_near', name: 'Custom Nation Old'}); // a near name is not a match
  roster = fresh();
  const tenant = require('../../workspace/lib/tenant.ts');
  await roster.reconcileClients();
  const created = clerkCalls.filter(call => call[0] === 'create').map(call => call[1]);
  assert.deepEqual(created, Object.keys(EXPECTED).map(name => ({name, createdBy: FOUNDER})));
  for (const call of clerkCalls.filter(call => call[0] === 'list')) assert.ok(call[1].query, 'the list is always queried by name');
  const byName = Object.fromEntries(orgs.map(org => [org.name, org]));
  const tenants = Object.keys(EXPECTED).map(name => tenant.tenantIdFor(byName[name].id));
  assert.deepEqual([...registered].sort(), [...tenants].sort());
  for (const call of tankCalls) assert.equal(call.headers['x-tervory-user'], FOUNDER);
  for (const [name, products] of Object.entries(EXPECTED)) {
    assert.deepEqual([...(squads.get(tenant.tenantIdFor(byName[name].id)) ?? [])].sort(), products);
  }
  assert.equal(changes.length, 5);
  assert.equal(squads.has(tenant.tenantIdFor('org_placeholder_near')), false);
  const okLines = logs.filter(line => line[0] === 'client_reconciled');
  assert.deepEqual(okLines.map(line => line[1]), Object.keys(EXPECTED).map(name => ({client: name, orgId: byName[name].id, tenantId: tenant.tenantIdFor(byName[name].id)})));

  // Second run, next server start: nothing created, no extra product change.
  const orgCount = orgs.length;
  clerkCalls = []; logs.length = 0;
  roster = fresh();
  await roster.reconcileClients();
  assert.equal(clerkCalls.filter(call => call[0] === 'create').length, 0);
  assert.equal(orgs.length, orgCount);
  assert.equal(changes.length, 5);
  assert.equal(logs.filter(line => line[0] === 'client_reconciled').length, 5);

  // An existing organization with the same name is reused, even past the first list page.
  reset();
  for (let i = 0; i < 120; i++) orgs.push({id: 'org_placeholder_other' + i, name: 'AmmoSync ' + i});
  orgs.push({id: 'org_placeholder_existing', name: 'AmmoSync'});
  roster = fresh();
  await roster.reconcileClients();
  assert.deepEqual(clerkCalls.filter(call => call[0] === 'create').map(call => call[1].name), ['Custom Nation', 'LOKD Security', 'Shot Bonus', 'TNGO']);
  assert.equal(orgs.filter(org => org.name === 'AmmoSync').length, 1);
  assert.deepEqual([...squads.get(tenant.tenantIdFor('org_placeholder_existing'))].sort(), ['base', 'market_lab']);

  // Empty TERVORY_ADMIN_USER_IDS: nothing at all, one fixed line.
  for (const value of ['', ' , ']) {
    reset();
    process.env.TERVORY_ADMIN_USER_IDS = value;
    roster = fresh();
    await roster.reconcileClients();
    assert.equal(clerkCalls.length + tankCalls.length, 0);
    assert.deepEqual(logs, [['client_reconcile_skipped_no_founder']]);
  }
  reset();
  delete process.env.TERVORY_ADMIN_USER_IDS;
  roster = fresh();
  await roster.reconcileClients();
  assert.equal(clerkCalls.length + tankCalls.length, 0);
  assert.deepEqual(logs, [['client_reconcile_skipped_no_founder']]);

  // The founder is the first listed id.
  reset();
  process.env.TERVORY_ADMIN_USER_IDS = ` ${FOUNDER} ,user_placeholder_second`;
  roster = fresh();
  await roster.reconcileClients();
  assert.ok(clerkCalls.filter(call => call[0] === 'create').every(call => call[1].createdBy === FOUNDER));

  // One client's Clerk failure leaves the other four done; the next start retries it.
  reset();
  process.env.TERVORY_ADMIN_USER_IDS = FOUNDER;
  failCreate.add('LOKD Security');
  roster = fresh();
  await roster.reconcileClients();
  assert.deepEqual(orgs.map(org => org.name), ['Custom Nation', 'AmmoSync', 'Shot Bonus', 'TNGO']);
  assert.equal(registered.size, 4);
  assert.deepEqual(logs.filter(line => line[0] === 'client_reconcile_failed').map(line => line[1]),
    [{client: 'LOKD Security', orgId: undefined, tenantId: undefined, error: 'ClerkAPIResponseError'}]);
  failCreate.clear();
  roster = fresh();
  await roster.reconcileClients();
  assert.equal(orgs.length, 5);
  assert.equal(registered.size, 5);
  assert.deepEqual([...squads.get(tenant.tenantIdFor(orgs.find(org => org.name === 'LOKD Security').id))], ['radix']);

  // A Tank failure for a client is logged by class only and does not stop the rest.
  reset();
  const realFetch = global.fetch;
  global.fetch = async (url, init) => (new URL(url).pathname === '/v1/command/squads/radix'
    ? new Response(SECRETS[2] + ' ' + SECRETS[0], {status: 403}) : realFetch(url, init));
  roster = fresh();
  await roster.reconcileClients();
  global.fetch = realFetch;
  const failed = logs.filter(line => line[0] === 'client_reconcile_failed');
  assert.equal(failed.length, 1);
  assert.equal(failed[0][1].client, 'LOKD Security');
  assert.equal(failed[0][1].error, 'Error');
  assert.equal(logs.filter(line => line[0] === 'client_reconciled').length, 4);

  // Nothing secret is logged, and each line carries only the allowed fields.
  const allLogs = JSON.stringify(logs);
  for (const secret of SECRETS) assert.ok(!allLogs.includes(secret), 'secret in logs');
  assert.ok(!/bearer|x-tank-key|authorization/i.test(allLogs));
  for (const line of logs) {
    assert.ok(['client_reconciled', 'client_reconcile_failed', 'client_reconcile_skipped_no_founder'].includes(line[0]));
    if (line[1]) for (const key of Object.keys(line[1])) assert.ok(['client', 'orgId', 'tenantId', 'error'].includes(key), key);
  }

  // In the Node runtime register() returns at once; the reconcile runs in the background
  // and a failure there never reaches start-up.
  reset();
  let release;
  const gate = new Promise(resolve => { release = resolve; });
  const realList = clerk.clerkClient;
  clerk.clerkClient = async () => { await gate; throw new Error('Clerk unreachable ' + SECRETS[1]); };
  process.env.NEXT_RUNTIME = 'nodejs';
  for (const file of wsFiles()) delete require.cache[file];
  const hook = require('../../workspace/instrumentation.ts');
  assert.equal(hook.register(), undefined, 'start-up does not wait on the reconcile');
  release();
  await new Promise(resolve => setTimeout(resolve, 50));
  assert.deepEqual(logs, [['client_reconcile_failed', {error: 'Error'}]]);
  assert.ok(!JSON.stringify(logs).includes(SECRETS[1]));
  clerk.clerkClient = realList;
  delete process.env.NEXT_RUNTIME;

  process.stdout.write('PASS: five organizations/tenants/products, idempotent second run, exact-name reuse, empty founder no-op, per-client failure isolation, no secret logged, no import-time run, background register().\n');
})().catch(error => { process.stderr.write(String(error && error.stack || error) + '\n'); process.exitCode = 1; });
