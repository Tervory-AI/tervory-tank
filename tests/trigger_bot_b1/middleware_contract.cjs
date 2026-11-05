// Execute real Trigger sign-in middleware and matcher around the actual Workspace callback.
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '../../workspace/node_modules');
const next = require(path.join(root, 'next/server'));
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
const origin = 'https://store.invalid';
const env = { TANK_URL: 'http://tank.invalid' };
const load = workspace({ env, fetch: async () => new Response(null, {status: 204,
    headers: {'Access-Control-Allow-Origin': origin}}),
  mocks: {
    'next-auth/jwt': {getToken: async () => {throw Error('Public bot must not require a session');}},
    'next/server': next,
  }});
const middleware = load('middleware.ts').default;
const route = load('app/v1/bot/messages/route.ts');
(async () => {
  for (const method of ['OPTIONS', 'POST']) {
    const request = new next.NextRequest('https://app.tervory.com/v1/bot/messages', {
      method, headers: {origin, host: 'app.tervory.com', 'content-type': 'application/json',
        'x-bot-key': 'tb1.us-east.' + 'a'.repeat(32) + '.rk_pub_' + 'b'.repeat(48)},
      ...(method === 'POST' ? {body: '{"text":"Delivery?"}'} : {})
    });
    const result = await middleware(request, {waitUntil: () => {}});
    assert.notEqual(result?.status, 307);
    assert.equal(result?.headers.get('location'), null);
    const response = await route[method](request);
    assert.equal(response.status, 204);
  }
  console.log('PASS signed-out OPTIONS and POST through real Trigger sign-in middleware: 204, no redirect');
})().catch(error => {console.error(error); process.exitCode = 1;});
