// Run real Base handlers with only identity and upstream Tank transport mocked.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(file, mocks, env = 'production') {
  const exports = {};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
  }).outputText, {exports, URL, URLSearchParams, Response, Headers, Buffer, process: {env: {NODE_ENV: env}}, require(name) {
    if (name in mocks) return mocks[name];
    throw Error(`Unmocked ${name}`);
  }});
  return exports;
}
const hosts = load('workspace/lib/product-hosts.ts', {});
const origin = load('workspace/lib/workspace-origin.ts', {'./product-hosts': hosts});
let signedIn = true, calls = [];
const mocks = {
  '@/lib/workspace-origin': origin,
  '@/lib/tenant': {currentTenant: async () => {
    if (!signedIn) throw Error('signed out');
    return {tenantId: 'fixture-owner', userId: 'fixture-user'};
  }},
  '@/lib/tank': {baseProductRequest: async (...args) => {
    calls.push(args);
    return new Response('fixture-export', {status: 200, headers: {'content-type': 'text/csv', 'content-disposition': 'attachment; filename="records.csv"'}});
  }},
};
const product = load('workspace/app/base/product/[...path]/route.ts', mocks);
const download = load('workspace/app/base/download/route.ts', mocks);
function request(route, {host = 'app.tervory.com', origin: headerOrigin = 'https://app.tervory.com', method = 'GET', body, extra = {}} = {}) {
  const headers = {...extra};
  if (host !== null) headers.host = host;
  if (headerOrigin !== null) headers.origin = headerOrigin;
  return new Request(`http://0.0.0.0:3000/base/${route}`, {method, headers, ...(body === undefined ? {} : {body: typeof body === 'string' ? body : JSON.stringify(body)})});
}
function context(route) {return {params: Promise.resolve({path: route.split('/')})};}
(async () => {
  for (const host of ['app.tervory.com', 'base.tervory.com']) {
    for (const route of ['reference/batches', 'uploads', 'comparison']) {
      calls = [];
      const response = await product.POST(request(`product/${route}`, {host, origin: `https://${host}`, method: 'POST', body: {tenant_id: 'forged-tenant', rows: []}, extra: {'x-forwarded-proto': 'https'}}), context(route));
      assert.equal(response.status, 200);
      assert.equal(calls.length, 1);
      assert.equal(calls[0][0], 'fixture-owner');
      assert.equal(calls[0][3].tenant_id, undefined);
      if (route !== 'comparison') assert.equal(calls[0][3].created_by, 'fixture-user');
    }
  }
  for (const opts of [
    {origin: null}, {origin: 'null'}, {origin: 'not a url'}, {origin: 'https://foreign.test'},
    {origin: 'http://app.tervory.com'}, {origin: 'https://app.tervory.com/'},
    {origin: 'https://user:pass@app.tervory.com'}, {origin: 'https://app.tervory.com?x=1'},
    {origin: 'https://app.tervory.com https://foreign.test'},
    {origin: 'https://base.tervory.com'},
    {host: 'foreign.test', origin: 'https://foreign.test', extra: {'x-forwarded-host': 'app.tervory.com'}},
    {host: 'app.tervory.com.evil.test', origin: 'https://app.tervory.com.evil.test'},
    {host: 'app.tervory.com,foreign.test'}, {host: 'app.tervory.com:443'}, {host: null},
    {host: 'localhost:3000', origin: 'http://localhost:3000'},
  ]) {
    calls = [];
    assert.equal((await product.POST(request('product/uploads', {...opts, method: 'POST', body: {}}), context('uploads'))).status, 403, JSON.stringify(opts));
    assert.equal(calls.length, 0);
  }
  // Forwarded host/proto cannot override the trusted public Host or force a downgrade.
  assert.equal(origin.workspaceOrigin(request('download', {extra: {'x-forwarded-host': 'foreign.test', 'x-forwarded-proto': 'http'}})), 'https://app.tervory.com');
  for (const host of ['app.tervory.com', 'base.tervory.com']) {
    const batch = 'fixture & /?+#';
    const response = await download.GET(request(`download?${new URLSearchParams({batch: ` ${batch} `, tenant_id: 'forged', metric: 'forged'})}`, {host, extra: {'x-forwarded-host': 'foreign.test'}}));
    assert.equal(response.status, 307);
    const destination = new URL(response.headers.get('location'));
    assert.equal(destination.origin, `https://${host}`);
    assert.equal(destination.pathname, '/base/product/records.csv');
    assert.deepEqual(Object.fromEntries(destination.searchParams), {batch, metric: 'attempted', include_collectors: 'true'});
    calls = [];
    const result = await product.GET(new Request(destination, {headers: {host}}), context('records.csv'));
    assert.equal(calls[0][0], 'fixture-owner');
    assert.equal(calls[0][2].get('batch'), batch);
    assert.equal(result.headers.get('cache-control'), 'private, no-store');
    assert.equal(result.headers.get('content-type'), 'text/csv');
    assert.match(result.headers.get('content-disposition'), /attachment/);
    assert.equal(await result.text(), 'fixture-export');
  }
  for (const batch of ['', '   ', 'x'.repeat(121)]) {
    assert.equal((await download.GET(request(`download?${new URLSearchParams({batch})}`))).status, 400);
  }
  for (const host of ['foreign.test', 'app.tervory.com.evil.test', null]) {
    assert.equal((await download.GET(request('download?batch=fixture', {host}))).status, 400);
  }
  for (const [body, status] of [['{', 400], ['[]', 400], ['x'.repeat(2_100_001), 413]]) {
    assert.equal((await product.POST(request('product/uploads', {method: 'POST', body}), context('uploads'))).status, status);
  }
  calls = [];
  await product.GET(request('product/records.csv?batch=fixture&tenant_id=forged&unknown=x&limit=2'), context('records.csv'));
  assert.equal(calls[0][2].toString(), 'batch=fixture&limit=2');
  assert.equal((await product.GET(request('product/unknown'), context('unknown'))).status, 404);
  signedIn = false; calls = [];
  assert.equal((await product.GET(request('product/records.csv'), context('records.csv'))).status, 401);
  assert.equal((await product.POST(request('product/uploads', {method: 'POST', body: {}}), context('uploads'))).status, 401);
  assert.equal((await download.GET(request('download?batch=fixture'))).status, 401);
  assert.equal(calls.length, 0);
  console.log('Base actual handlers: proxied HTTPS writes, strict origins/hosts, public redirects, body/filter/batch validation, download headers and tenant identity passed.');
})().catch(error => {console.error(error); process.exitCode = 1;});
