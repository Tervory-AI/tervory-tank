// Exercise the actual future-widget transport; fake upstream, no external network.
const assert = require('node:assert/strict');
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
const origin = 'https://store.invalid';
const key = region => `tb1.${region}.${'a'.repeat(32)}.rk_pub_${'b'.repeat(48)}`;
let calls = [];
let upstreamOrigin = origin;
const fetch = async (url, options) => {
  calls.push({ url: String(url), options });
  return Response.json({ state: 'handed_over', answer: null, sources: [] }, { headers: { 'Access-Control-Allow-Origin': upstreamOrigin } });
};
const load = env => workspace({ env, fetch })('app/v1/bot/messages/route.ts');
const request = (region = 'us-east', overrides = {}) => new Request('https://workspace.invalid/v1/bot/messages', {
  method: 'POST', body: JSON.stringify({ text: 'Delivery?' }), ...overrides,
  headers: { 'content-type': 'application/json', origin, 'x-bot-key': key(region),
    authorization: 'must-not-forward', cookie: 'must-not-forward', 'x-tervory-user': 'forged',
    'x-tervory-tenant': 'forged', 'x-forwarded-for': '198.51.100.1', ...overrides.headers },
});
(async () => {
  const route = load({ TANK_URL: 'http://tank.invalid', TANK_URL_ZA: 'http://za.invalid' });
  assert.equal((await route.POST(request())).status, 200);
  assert.equal(calls[0].url, 'http://tank.invalid/v1/bot/messages');
  assert.deepEqual(Object.keys(calls[0].options.headers).sort(), ['content-type', 'origin', 'x-bot-key', 'x-forwarded-for']);
  assert.equal(calls[0].options.headers['x-forwarded-for'], '198.51.100.1');
  assert.equal(calls[0].options.cache, 'no-store');
  assert.equal(calls[0].options.redirect, 'error');
  assert.equal((await route.POST(request('za'))).status, 200);
  assert.equal(calls[1].url, 'http://za.invalid/v1/bot/messages');
  const count = calls.length;
  assert.equal((await load({ TANK_URL: 'http://tank.invalid' }).POST(request('za'))).status, 503);
  assert.equal((await route.POST(request('us-east', { headers: { origin: 'http://store.invalid' } }))).status, 403);
  assert.equal((await route.POST(request('us-east', { headers: { 'x-bot-key': 'invalid' } }))).status, 403);
  assert.equal((await route.POST(request('us-east', { body: 'x'.repeat(16001) }))).status, 413);
  assert.equal(calls.length, count);
  upstreamOrigin = 'https://another.invalid';
  assert.equal((await route.POST(request())).status, 502);
  const preflight = await route.OPTIONS(new Request('https://workspace.invalid/v1/bot/messages', { headers: { origin } }));
  assert.equal(preflight.status, 204);
  assert.equal(preflight.headers.get('access-control-allow-origin'), origin);
  assert.equal(preflight.headers.get('access-control-allow-credentials'), null);
  console.log('PASS bot public transport: exact origin, bounded body, isolated regions, no Workspace identity forwarding, no fallback, CORS match');
})().catch(error => { console.error(error); process.exitCode = 1; });
