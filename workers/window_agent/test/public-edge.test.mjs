import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
process.env.COMMAND_TEST_TOOLS ??= fileURLToPath(new URL('../../../cli/node_modules', import.meta.url));
const { workspace } = await import('../../../tests/command_acceptance_20261031/workspace_loader.cjs');
const ID = '00000000-0000-0000-0000-000000000011';
const TOKEN = `tv1.us-east.${ID.replaceAll('-', '')}.${'x'.repeat(43)}`;
function load(fetch) { return workspace({ env: { TANK_URL: 'http://local-tank:8000', TANK_API_KEY: 'dummy-must-not-forward' }, fetch }); }
function request(path, method = 'GET', body) {
  return new Request(`https://app.tervory.com/v1/command/${path}`, { method,
    headers: { authorization: `Bearer ${TOKEN}`, 'content-type': 'application/json', cookie: 'forged', 'x-tank-key': 'forged', 'x-tervory-user': 'founder' },
    ...(body === undefined ? {} : { body }) });
}

test('only the eight explicit user endpoints forward through the existing public corridor', async () => {
  const received = [];
  const proxy = load(async (url, init) => { received.push({ url: String(url), init }); return Response.json({}); })('lib/tank.ts').personalCommandRequest;
  const allowed = [
    ['GET', 'jobs'], ['POST', 'jobs'], ['GET', `jobs/${ID}/receipt`], ['POST', `jobs/${ID}/cancel`],
    ['GET', 'vault/github'], ['POST', 'vault/github'], ['POST', 'reviews'], ['POST', 'webhooks'],
  ];
  for (const [method, suffix] of allowed) {
    const path = 'window-agents/' + suffix;
    assert.equal((await proxy(request(path, method, method === 'POST' ? '{}' : undefined), path.split('/'))).status, 200);
    const last = received.at(-1);
    assert.equal(last.url, `http://local-tank:8000/v1/${path}`);
    assert.deepEqual({ ...last.init.headers }, { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' });
  }
  const before = received.length;
  for (const [method, suffix] of [
    ['POST', 'worker/next'], ['POST', `worker/${ID}/${ID}/credential`], ['POST', `worker/${ID}/${ID}/code-turn`],
    ['GET', 'webhooks'], ['GET', 'reviews'], ['GET', `jobs/${ID}/cancel`], ['POST', `jobs/${ID}/receipt`],
    ['PUT', 'vault/github'], ['GET', 'jobs/not-a-uuid/receipt'], ['GET', 'unknown'],
  ]) {
    const path = 'window-agents/' + suffix;
    assert.equal((await proxy(request(path, method, method === 'GET' ? undefined : '{}'), path.split('/'))).status, 404);
  }
  assert.equal(received.length, before);
});

const routePath = 'app/v1/command/window-agents/webhooks/[tenantId]/[hookId]/route.ts';
function hookRequest(body, extra = {}, host = 'app.tervory.com') {
  return new Request(`https://${host}/v1/command/window-agents/webhooks/${ID}/${ID}`, { method: 'POST', body,
    headers: { 'content-type': 'application/json', 'x-hub-signature-256': 'sha256=' + 'a'.repeat(64),
      'x-github-event': 'pull_request', 'x-github-delivery': ID, authorization: `Bearer ${TOKEN}`, 'x-tank-key': 'forged', ...extra } });
}
const context = { params: Promise.resolve({ tenantId: ID, hookId: ID }) };

test('webhook transport forwards raw bytes and GitHub signature/event headers only to local Tank', async () => {
  let received;
  const route = load(async (url, init) => { received = { url: String(url), init }; return new Response(null, { status: 202 }); })(routePath);
  const raw = '{ "repository": "é", "n": 1 }\n';
  assert.equal((await route.POST(hookRequest(raw), context)).status, 202);
  assert.equal(route.GET, undefined);
  assert.equal(received.url, `http://local-tank:8000/v1/window-agents/webhooks/${ID}/${ID}`);
  assert.deepEqual(received.init.body, new TextEncoder().encode(raw));
  assert.deepEqual({ ...received.init.headers }, { 'Content-Type': 'application/json', 'x-hub-signature-256': 'sha256=' + 'a'.repeat(64), 'x-github-event': 'pull_request', 'x-github-delivery': ID });
  assert.equal(received.init.redirect, 'manual');
});

test('oversized, malformed-signature and foreign-host webhooks never reach Tank', async () => {
  let calls = 0;
  const route = load(async () => { calls++; return new Response(null, { status: 202 }); })(routePath);
  assert.equal((await route.POST(hookRequest('x'.repeat(1_000_001)), context)).status, 413);
  assert.equal((await route.POST(hookRequest('{}', { 'x-hub-signature-256': 'bad' }), context)).status, 404);
  assert.equal((await route.POST(hookRequest('{}', {}, 'foreign.example'), context)).status, 404);
  assert.equal(calls, 0);
});

test('webhook transport returns no detail for unknown hooks or bad signatures rejected by Tank', async () => {
  const route = load(async () => Response.json({ detail: 'Not Found' }, { status: 404 }))(routePath);
  const result = await route.POST(hookRequest('{}'), context);
  assert.equal(result.status, 404);
  assert.equal(await result.text(), '');
});
