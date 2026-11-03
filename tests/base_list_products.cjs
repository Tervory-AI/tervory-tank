// Offline route and existing-card proof. Synthetic values never enter a live screen.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const req = createRequire(path.join(root, 'workspace/package.json'));
const ts = req('typescript');
const compiled = ts.transpileModule(fs.readFileSync(path.join(root, 'workspace/app/base/download/route.ts'), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
const identity = {tenantId: '11111111-1111-4111-8111-111111111111', userId: 'placeholder-user'};
const listId = '22222222-2222-4222-8222-222222222222';
const auditId = '33333333-3333-4333-8333-333333333333';
const campaignId = '44444444-4444-4444-8444-444444444444';
const bytes = new TextEncoder().encode('\uFEFFname,source_url\r\n"placeholder, product",https://placeholder.example/product\r\n');
let signedIn = true;
let upstreamStatus = 200;
const calls = [];
const moduleValue = {exports: {}};
function mocked(name) {
  if (name === '@/lib/tenant') return {currentTenant: async () => {if (!signedIn) throw Error('placeholder'); return identity;}};
  if (name === '@/lib/workspace-origin') return {workspaceOrigin: () => 'https://app.tervory.com'};
  if (name === '@/lib/tank') return {commandRequest: async (actor, route, init, options) => {
    assert.deepEqual(actor, identity);
    assert.equal(options.passThroughErrors, true);
    calls.push(route);
    return new Response(upstreamStatus === 200 ? bytes : JSON.stringify({detail: 'placeholder failure'}), {status: upstreamStatus, headers: {'content-type': 'application/json', 'x-internal': 'placeholder'}});
  }};
  throw Error('Unexpected dependency '+name);
}
new Function('require', 'module', 'exports', compiled)(mocked, moduleValue, moduleValue.exports);
(async () => {
  const {GET} = moduleValue.exports;
  const url = 'https://app.tervory.com/base/download?list_id='+listId;
  let result = await GET(new Request(url+'&kind=products'));
  assert.equal(calls.at(-1), 'base/lists/products.csv?list_id='+listId);
  assert.equal(result.status, 200);
  assert.equal(result.headers.get('content-disposition'), 'attachment; filename="base-products.csv"');
  assert.equal(result.headers.get('cache-control'), 'private, no-store');
  assert.equal(result.headers.get('x-content-type-options'), 'nosniff');
  assert.equal(result.headers.get('x-internal'), null);
  assert.deepEqual(new Uint8Array(await result.arrayBuffer()), bytes);
  for (const suffix of ['', '&kind=placeholder', '&kind=PRODUCTS']) {
    result = await GET(new Request(url+suffix));
    assert.equal(calls.at(-1), 'base/lists/csv?list_id='+listId);
    assert.equal(result.headers.get('content-disposition'), 'attachment; filename="base-list.csv"');
    assert.deepEqual(new Uint8Array(await result.arrayBuffer()), bytes);
  }
  for (const status of [403, 404, 500]) {
    upstreamStatus = status;
    result = await GET(new Request(url+'&kind=products'));
    assert.equal(result.status, status);
    assert.equal(result.headers.get('content-disposition'), null);
    assert.equal(result.headers.get('content-type'), 'application/json');
    assert.deepEqual(await result.json(), {detail: 'placeholder failure'});
  }
  upstreamStatus = 200;
  const previous = calls.length;
  result = await GET(new Request('https://app.tervory.com/base/download?list_id=placeholder&kind=products'));
  assert.equal(result.status, 400);
  assert.equal(calls.length, previous);
  result = await GET(new Request('https://app.tervory.com/base/download?batch=placeholder&kind=products'));
  assert.equal(result.status, 307);
  assert.equal(result.headers.get('location'), 'https://app.tervory.com/base/product/records.csv?batch=placeholder&metric=attempted&include_collectors=true');
  result = await GET(new Request(url+'&kind=products&audit_id='+auditId+'&campaign_id='+campaignId));
  assert.equal(calls.at(-1), 'base/audits/csv?audit_id='+auditId+'&campaign_id='+campaignId);
  assert.equal(result.headers.get('content-disposition'), 'attachment; filename="base-audit.csv"');
  signedIn = false;
  const beforeSignedOut = calls.length;
  result = await GET(new Request(url+'&kind=products'));
  assert.equal(result.status, 401);
  assert.equal(calls.length, beforeSignedOut);

  require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, filename);
  const {presentCard} = require('../workspace/app/chats/presentation.ts');
  for (const founder of [false, true]) {
    const card = presentCard({card_id: 'placeholder', tool: 'base.list.products', kind: 'other', summary: 'placeholder', status: 'confirmed', result: {total: 3, url: url+'&kind=products', cost_usd: 0, ledger_id: 'placeholder'}}, founder);
    assert(card.results.some(item => item.label === 'Total' && item.value === '3'));
    assert(card.results.some(item => item.label === 'Result' && item.href === url+'&kind=products'));
    assert(card.results.some(item => item.label === 'Cost' && item.value === '$0.00'));
  }
  console.log('Product CSV bytes, tenant routing, audit/batch/list compatibility, and existing Total/Result/Cost card labels passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
