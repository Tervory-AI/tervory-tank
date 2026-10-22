const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const ts = require('../workspace/node_modules/typescript');
const root = path.resolve(__dirname, '..');

function moduleFrom(relative, bindings) {
  const source = fs.readFileSync(path.join(root, relative), 'utf8');
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const exports = {};
  vm.runInNewContext(compiled, { exports, require: name => {
    assert(name in bindings, `Unexpected dependency ${name}`); return bindings[name];
  }, process: { env: {} }, URL, Uint8Array, TextDecoder, Set, Error });
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
  assert.equal((await route.POST(request({ operation: 'import', data: { contents: 'x'.repeat(10_000_001) } }))).status, 413);
  assert.equal(calls.length, 1);

  let role = 'org:member';
  let active = { tenantId: 'server-tenant', userId: 'server-user' };
  const forwarded = [];
  const actions = moduleFrom('workspace/app/rig/admin/actions.ts', {
    '@clerk/nextjs/server': { auth: async () => ({ userId: 'server-user', orgRole: role }) },
    '@/lib/tenant': { activeTenant: async () => active },
    '../../review/founder': { isListedFounder: () => false },
    '@/lib/tank': {
      rigAdminPanel: async () => ({ price_configured: true }),
      rigAdminAction: async (actor, operation, data) => { forwarded.push({ actor, operation, data }); return { saved: true }; },
    },
  });
  assert.equal((await actions.changeRetailer('price-rule', {})).ok, false);
  assert.equal(forwarded.length, 0);
  role = 'org:admin';
  assert.equal((await actions.changeRetailer('templates', { tenant_id: 'browser-tenant' })).ok, true);
  assert.equal(forwarded[0].actor.tenantId, 'server-tenant');
  active = null;
  assert.equal((await actions.changeRetailer('price-rule', {})).ok, false);
  assert.equal(forwarded.length, 1);
  console.log('Retailer route: session role, server tenant, origin checks and bounded uploads passed.');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
