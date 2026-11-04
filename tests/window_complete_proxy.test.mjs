import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
process.env.COMMAND_TEST_TOOLS = fileURLToPath(new URL('../cli/node_modules', import.meta.url));
const { workspace } = await import('./command_acceptance_20261031/workspace_loader.cjs');
const token = `tv1.us-east.${'1'.repeat(32)}.${'a'.repeat(43)}`;

test('completion proxy keeps fixed region and forwards no asserted identity or service key', async () => {
  let received;
  const load = workspace({ env: { TANK_URL: 'http://fake-tank:8000', TANK_API_KEY: 'dummy-not-forwarded' },
    fetch: async (url, init) => { received = { url: String(url), ...init }; return Response.json({ status: 'ok', text: 'code', receipts: [] }); } });
  const proxy = load('lib/tank.ts').personalCommandRequest;
  const request = new Request('https://app.tervory.com/v1/command/complete', { method: 'POST', headers: {
    host: 'app.tervory.com', authorization: `Bearer ${token}`, 'content-type': 'application/json',
    'x-tank-key': 'forged', 'x-tervory-tenant': 'forged', 'x-tervory-user': 'founder',
  }, body: JSON.stringify({ prefix: 'before', suffix: 'after' }) });
  assert.equal((await proxy(request, ['complete'])).status, 200);
  assert.equal(received.url, 'http://fake-tank:8000/v1/command/complete');
  assert.deepEqual(Object.keys(received.headers).sort(), ['Authorization', 'Content-Type']);
  assert.equal(received.headers.Authorization, `Bearer ${token}`);
  assert.equal(received.redirect, 'manual');
  assert.equal((await proxy(new Request(request.url, { headers: request.headers }), ['complete'])).status, 404);
});
