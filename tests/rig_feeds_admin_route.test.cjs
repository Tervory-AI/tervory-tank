const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../workspace/node_modules/typescript');
const root = path.resolve(__dirname, '..');

function moduleFrom(relative, bindings, globals = {}) {
  const source = fs.readFileSync(path.join(root, relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => {
    assert(name in bindings, `Unexpected dependency ${name}`); return bindings[name];
  }, process: { env: {} }, URL, Uint8Array, TextDecoder, Set, Error, ...globals });
  return exports;
}

async function main() {
  let signedIn = true;
  const calls = [];
  const route = moduleFrom('workspace/app/rig/admin/api/route.ts', {
    'next/server': { NextResponse: { json: (body, options = {}) => ({ body, status: options.status || 200 }) } },
    '../actions': {
      retailerIdentity: async () => { if (!signedIn) throw new Error('not signed in'); },
      changeRetailer: async (operation, data) => { calls.push({ operation, data }); return { ok: true, message: 'Saved.' }; },
    },
  });
  function request(value, origin = 'https://app.example') {
    const data = new TextEncoder().encode(JSON.stringify(value));
    return { headers: new Headers({ origin, host: 'app.example' }), body: new ReadableStream({ start(controller) { controller.enqueue(data); controller.close(); } }) };
  }
  assert.equal((await route.POST(request({ operation: 'import', data: {} }, 'https://other.example'))).status, 403);
  assert.equal((await route.POST(request({ operation: 'import', data: {} }, 'null'))).status, 403);
  signedIn = false;
  assert.equal((await route.POST(request({ operation: 'import', data: {} }))).status, 403);
  signedIn = true;
  assert.equal((await route.POST(request({ operation: 'delete-all', data: {} }))).status, 422);
  assert.equal((await route.POST(request({ operation: 'import', data: [] }))).status, 422);
  const big = await route.POST(request({ operation: 'import', data: { contents: 'x'.repeat(1_100_000) } }));
  assert.equal(big.status, 200);
  assert.equal(calls.length, 1);
  assert.equal(calls[0].data.contents.length, 1_100_000);
  assert.equal((await route.POST(request({ operation: 'import', data: { contents: 'x'.repeat(12_000_001) } }))).status, 413);
  assert.equal(calls.length, 1);

  let role = 'org:member';
  let active = { tenantId: 'server-tenant', userId: 'server-user' };
  // Load the real helper: mocking rigAdminAction hid the missing mapping allow-list entry.
  // Only the HTTP boundary is replaced; real actions and route call the real tank.ts exports.
  const forwarded = [];
  const regionTransport = moduleFrom('workspace/app/api/zenas/tank.ts', {});
  const tank = moduleFrom('workspace/lib/tank.ts', { '@/app/api/zenas/tank': regionTransport }, { fetch: async (url, options) => {
    forwarded.push({ url, options });
    return { ok: true, json: async () => url.endsWith('/mapping')
      ? { preview_id: 'server-preview', fields: ['code'], columns: { sku: 'code' }, required: ['sku'] }
      : { saved: true } };
  } });
  const actions = moduleFrom('workspace/app/rig/admin/actions.ts', {
    '@clerk/nextjs/server': { auth: async () => ({ userId: 'server-user', orgRole: role }) },
    '@/lib/tenant': { activeTenant: async () => active },
    '../../review/founder': { isListedFounder: () => false },
    '@/lib/tank': tank,
  });
  const realRoute = moduleFrom('workspace/app/rig/admin/api/route.ts', {
    'next/server': { NextResponse: { json: (body, options = {}) => ({ body, status: options.status || 200 }) } },
    '../actions': actions,
  });
  assert.equal((await realRoute.POST(request({ operation: 'mapping', data: {} }))).status, 403);
  assert.equal(forwarded.length, 0);
  role = 'org:admin';
  const data = { distributor: 'catalogue', currency: 'NZD', country: 'NZ', price_basis: 'cost' };
  const preview = await realRoute.POST(request({ operation: 'mapping', data }));
  assert.equal(preview.body.ok, true);
  assert.equal(preview.body.mapping.preview_id, 'server-preview');
  assert(forwarded[0].url.endsWith('/v1/access/rig/admin/mapping'));
  assert.deepEqual(JSON.parse(forwarded[0].options.body), { data });
  assert.equal(forwarded[0].options.method, 'POST');
  assert.equal(forwarded[0].options.cache, 'no-store');
  assert.equal(forwarded[0].options.headers['x-tervory-tenant'], 'server-tenant');
  assert.equal(forwarded[0].options.headers['x-tervory-user'], 'server-user');
  for (const operation of ['confirm-mapping', 'import']) {
    const response = await realRoute.POST(request({ operation, data }));
    assert.equal(response.body.ok, true);
    assert(forwarded.at(-2).url.endsWith('/v1/access/rig/admin/' + operation));
  }
  const count = forwarded.length;
  assert.throws(() => tank.rigAdminAction(active, 'delete-all', {}), /Unknown retailer operation/);
  active = null;
  assert.equal((await actions.changeRetailer('mapping', {})).ok, false);
  assert.equal(forwarded.length, count);

  const accessCalls = [];
  const accessRoute = moduleFrom('workspace/app/access/api/[...path]/route.ts', {
    'next/server': { NextResponse: { json: (body, options = {}) => ({ body, status: options.status || 200 }) } },
    '../../identity': { accessIdentity: async () => ({ tenantId: 'member-tenant', userId: 'member-user' }) },
    '@/lib/tank': { accessRequest: async (...args) => { accessCalls.push(args); return { ok: true }; } },
  });
  function accessRequest(body) {
    return { headers: new Headers({ origin: 'https://app.example', host: 'app.example' }),
      nextUrl: new URL('https://app.example/access/api/feeds/import'), text: async () => JSON.stringify(body) };
  }
  for (const operation of ['import', 'connect', 'refresh']) {
    const context = { params: Promise.resolve({ path: ['feeds', operation] }) };
    assert.equal((await accessRoute.POST(accessRequest({ target: 'rig' }), context)).status, 403);
    assert.equal(accessCalls.length, 0);
  }
  assert.equal((await accessRoute.POST(accessRequest({ distributor: 'zanders' }),
    { params: Promise.resolve({ path: ['feeds', 'import'] }) })).status, 200);
  assert.equal(accessCalls.length, 1);
  console.log('Retailer route: session role, server tenant, origin checks and bounded uploads passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
