const assert = require('node:assert/strict');
const path = require('node:path');
process.env.COMMAND_TEST_TOOLS = path.resolve(__dirname, '../workspace/node_modules');
const { workspace } = require('./command_acceptance_20261031/workspace_loader.cjs');
const next = require(path.join(process.env.COMMAND_TEST_TOOLS, 'next/server'));

async function run() {
  const calls = [];
  const body = { regions: { 'us-east': { issuer: 'https://auth.tervory.com' } } };
  const load = workspace({ env: { TRIGGER_SIGNIN_CONFIG_TOKEN: 'offline-read-only' },
    mocks: { 'next/server': next }, fetch: async (url, init) => {
      calls.push({ url, init });
      assert.equal(url, 'http://tank:8000/v1/trigger-signin/config');
      assert.equal(init.headers['x-trigger-signin-config'], 'offline-read-only');
      assert.equal(init.headers['x-trigger-signin-setup'], undefined);
      assert.equal(init.redirect, 'error');
      return Response.json(body);
    } });
  const route = load('app/api/trigger-signin/config/route.ts');
  for (const secret of ['', 'wrong-read-only']) {
    const response = await route.GET(new Request('https://app.tervory.com/api/trigger-signin/config', {
      headers: { 'x-trigger-signin-config': secret },
    }));
    assert.equal(response.status, 404);
  }
  assert.equal(calls.length, 0);
  const response = await route.GET(new Request('https://app.tervory.com/api/trigger-signin/config', {
    headers: { 'x-trigger-signin-config': 'offline-read-only' },
  }));
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  assert.deepEqual(await response.json(), body);
  assert.equal(calls.length, 1);
  assert.equal(route.PUT, undefined);
  console.log('Global Trigger sign-in configuration boundary passed');
}
run().catch(error => { console.error(error); process.exitCode = 1; });
