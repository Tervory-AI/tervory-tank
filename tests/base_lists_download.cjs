// Offline server-route regression. No live tenant, browser, token or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const requireWorkspace = createRequire(path.join(root, 'workspace/package.json'));
const ts = requireWorkspace('typescript');
const source = fs.readFileSync(path.join(root, 'workspace/app/base/download/route.ts'), 'utf8');
const compiled = ts.transpileModule(source, {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
const identity = {tenantId: '11111111-1111-4111-8111-111111111111', userId: 'invented-user'};
const listId = '22222222-2222-4222-8222-222222222222';
const bytes = new TextEncoder().encode('\uFEFFname,phone,cost_usd,baseline_cost_usd\r\n"Invented, company",+12025550123,0.10,0.30\r\n');
let signedIn = true;
let calls = 0;
let upstreamStatus = 200;
const moduleValue = {exports: {}};
function mocked(name) {
  if (name === '@/lib/tenant') return {currentTenant: async () => {if (!signedIn) throw Error('offline'); return identity;}};
  if (name === '@/lib/workspace-origin') return {workspaceOrigin: () => 'https://app.tervory.com'};
  if (name === '@/lib/tank') return {commandRequest: async (actor, route, init, options) => {
    assert.equal(options.passThroughErrors, true);
    calls++;
    assert.deepEqual(actor, identity);
    assert.equal(route, 'base/lists/csv?list_id='+listId);
    return new Response(upstreamStatus === 200 ? bytes : JSON.stringify({detail: 'offline failure'}), {status: upstreamStatus, headers: {'x-internal': 'not-forwarded', 'content-type': 'application/json'}});
  }};
  throw Error('Unexpected dependency '+name);
}
new Function('require', 'module', 'exports', compiled)(mocked, moduleValue, moduleValue.exports);
(async () => {
  const {GET} = moduleValue.exports;
  let result = await GET(new Request('https://app.tervory.com/base/download?list_id='+listId));
  assert.equal(result.status, 200);
  assert.deepEqual(new Uint8Array(await result.arrayBuffer()), bytes);
  assert.equal(result.headers.get('content-disposition'), 'attachment; filename="base-list.csv"');
  assert.equal(result.headers.get('x-internal'), null);
  for (const status of [403, 404, 500]) {
    upstreamStatus = status;
    result = await GET(new Request('https://app.tervory.com/base/download?list_id='+listId));
    assert.equal(result.status, status);
    assert.equal(result.headers.get('content-type'), 'application/json');
    assert.equal(result.headers.get('content-disposition'), null);
    assert.deepEqual(await result.json(), {detail: 'offline failure'});
  }
  result = await GET(new Request('https://app.tervory.com/base/download?list_id=invalid'));
  assert.equal(result.status, 400);
  assert.equal(calls, 4);
  result = await GET(new Request('https://app.tervory.com/base/download?batch=original'));
  assert.equal(result.status, 307);
  assert.equal(result.headers.get('location'), 'https://app.tervory.com/base/product/records.csv?batch=original&metric=attempted&include_collectors=true');
  signedIn = false;
  result = await GET(new Request('https://app.tervory.com/base/download?list_id='+listId));
  assert.equal(result.status, 401);
  assert.equal(calls, 4);
  console.log('Saved-list CSV bytes preserved; tenant identity forwarded; existing batch download unchanged.');
})().catch(error => {console.error(error); process.exitCode = 1;});
