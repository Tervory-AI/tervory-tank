import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';
import ts from 'typescript';
import { run } from '../src/client.mjs';

const source = await readFile(new URL('../../../workspace/lib/tank.ts', import.meta.url), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const TENANT = '00000000-0000-0000-0000-000000000011';
const ID = '00000000-0000-0000-0000-000000000022';
const TOKEN = `tv1.us-east.${TENANT.replaceAll('-', '')}.${'x'.repeat(43)}`;

function edge(upstream) {
  const module = { exports: {} };
  vm.runInNewContext(code, { exports: module.exports, module, process: { env: { TANK_URL: 'http://fake-tank:8000', TANK_API_KEY: 'must-not-forward' } },
    URL, Request, Response, Headers, Uint8Array, fetch: upstream });
  return module.exports.personalCommandRequest;
}
function request(path, { token = TOKEN, host = 'app.tervory.com', method = 'GET', body, extra = {} } = {}) {
  return new Request(`https://${host}/v1/command/${path}`, { method, headers: {
    authorization: `Bearer ${token}`, host, 'content-type': 'application/json',
    'x-tervory-user': 'founder', 'x-tervory-tenant': 'forged', 'x-tank-key': 'forged', cookie: 'clerk=forged', ...extra,
  }, ...(body === undefined ? {} : { body: typeof body === 'string' ? body : JSON.stringify(body) }) });
}
function call(proxy, path, options) { return proxy(request(path, options), path.split('?')[0].split('/')); }

test('public adapter forwards only PAT and content type to fixed local Tank', async () => {
  let received;
  const proxy = edge(async (url, init) => { received = { url: String(url), ...init }; return Response.json(['base.search']); });
  assert.equal((await call(proxy, 'tools')).status, 200);
  assert.equal(received.url, 'http://fake-tank:8000/v1/command/tools');
  assert.deepEqual(Object.keys(received.headers).sort(), ['Authorization', 'Content-Type']);
  assert.equal(received.headers.Authorization, `Bearer ${TOKEN}`);
  assert.equal(received.redirect, 'error');
  assert(!JSON.stringify(received).includes('must-not-forward'));
});

test('public path refuses revoked PAT without leaking upstream body', async () => {
  const proxy = edge(async () => new Response(TOKEN, { status: 401 }));
  const result = await call(proxy, 'tools');
  assert.equal(result.status, 401); assert.equal(await result.text(), '{}');
});

test('public path rejects foreign region malformed tokens worker endpoints and identity queries before fetch', async () => {
  let count = 0; const proxy = edge(async () => { count++; return Response.json({}); });
  assert.equal((await call(proxy, 'tools', { host: 'za.tervory.com' })).status, 403);
  assert.equal((await call(proxy, 'tools', { token: 'bad' })).status, 401);
  assert.equal((await call(proxy, 'builds/next')).status, 404);
  assert.equal((await call(proxy, 'squads')).status, 404);
  assert.equal((await call(proxy, 'threads?tenant_id=forged')).status, 400);
  assert.equal((await call(proxy, `threads/${ID}/events?after=1&after=2`)).status, 400);
  assert.equal(count, 0);
});

test('public path preserves replay cursor SSE and cancellation signal', async () => {
  let received;
  const proxy = edge(async (url, init) => { received = { url: String(url), ...init }; return new Response('event: done\ndata: {}\n\n', { headers: { 'Content-Type': 'text/event-stream' } }); });
  const req = request(`threads/${ID}/events?after=42`);
  const result = await proxy(req, ['threads', ID, 'events']);
  assert.match(received.url, /after=42$/); assert.equal(received.signal, req.signal);
  assert.equal(await result.text(), 'event: done\ndata: {}\n\n');
  assert.equal(result.headers.get('cache-control'), 'no-store');
});

test('public POST body is bounded and content type checked', async () => {
  let count = 0; const proxy = edge(async () => { count++; return Response.json({}); });
  assert.equal((await call(proxy, 'threads', { method: 'POST', body: 'x'.repeat(2_000_001) })).status, 413);
  assert.equal((await call(proxy, 'threads', { method: 'POST', body: '{}', extra: { 'content-type': 'text/plain' } })).status, 415);
  assert.equal(count, 0);
});

test('CLI traverses public domain adapter to fake Tank with PAT and receives roster', async () => {
  const inner = [];
  const proxy = edge(async (url, init) => { inner.push({ url: String(url), ...init }); return Response.json([{ name: 'fake-model', input_usd_per_m: 1 }]); });
  let output = '';
  await run(['models'], {
    store: { get: async () => TOKEN }, io: { write: value => { output += value; } },
    transport: async (url, init) => { const req = new Request(url, init); return proxy(req, ['models']); },
  });
  assert.match(output, /fake-model/); assert.equal(inner.length, 1);
  assert.equal(inner[0].headers.Authorization, `Bearer ${TOKEN}`);
});
