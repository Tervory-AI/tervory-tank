// Actual Workspace callback with local fakes. No browser credentials or network.
const assert = require('node:assert/strict');
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
let actor = { tenantId: 'placeholder-tenant', userId: 'placeholder-user', tenantAdmin: true };
let upstream = 200;
let calls = [];
const load = workspace({ env: {}, fetch: async () => { throw Error('Outside fetch forbidden'); }, mocks: {
  '@/lib/tenant': { activeTenant: async () => actor },
  '@/lib/tank': { commandRequest: async (identity, path, options) => {
    calls.push({ identity, path, body: JSON.parse(options.body) });
    return Response.json({ status: 'connected' }, { status: upstream });
  } },
} });
const route = load('app/oauth/trigger-meta/callback/route.ts');
const request = query => new Request('https://app.tervory.com/oauth/trigger-meta/callback?' + query, {
  headers: { 'x-tervory-tenant': 'placeholder-forged', 'x-tervory-user': 'placeholder-forged' },
});
(async () => {
  const success = await route.GET(request('state=placeholder-state&code=placeholder-code'));
  assert.equal(success.status, 303);
  assert.equal(success.headers.get('location'), 'https://app.tervory.com/chats');
  assert.equal(success.headers.get('referrer-policy'), 'no-referrer');
  assert.equal(success.headers.get('cache-control'), 'no-store');
  assert.equal(await success.text(), '');
  assert.equal(calls[0].identity, actor);
  assert.equal(calls[0].path, 'trigger-meta/oauth/callback');
  assert.deepEqual(calls[0].body, { state: 'placeholder-state', code: 'placeholder-code', error: null });
  assert.equal((await route.GET(request('state=placeholder-state&state=placeholder-duplicate&code=placeholder-code'))).status, 400);
  assert.equal(calls.length, 1);
  actor = null;
  assert.equal((await route.GET(request('state=placeholder-state&code=placeholder-code'))).status, 401);
  assert.equal(calls.length, 1);
  actor = { tenantId: 'placeholder-tenant', userId: 'placeholder-user' };
  upstream = 409;
  const failure = await route.GET(request('state=placeholder-state&code=placeholder-code'));
  assert.equal(failure.status, 409);
  assert.equal(await failure.text(), '');
  assert.equal(failure.headers.get('location'), null);
  console.log('PASS actual Meta callback: trusted active tenant, bounded unique parameters, private POST exchange, no reflected code/token, fixed chats redirect');
})().catch(error => { console.error(error); process.exitCode = 1; });
