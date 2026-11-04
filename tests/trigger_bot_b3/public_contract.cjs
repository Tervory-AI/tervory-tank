// Actual public Workspace forwarder with fake upstream; no network or credentials.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
const signature = 'sha256=' + 'a'.repeat(64);
const raw = '{ "placeholder": "raw signed bytes", "no parsing": true }\n';
let calls = [], code = 200, returned = '123456';
const fetch = async (url, options) => {
  calls.push({ url: String(url), options });
  return new Response(options.method === 'POST' ? 'placeholder private upstream data' : returned, { status: code });
};
const load = env => workspace({ env, fetch })('app/v1/bot/whatsapp/route.ts');
const post = (region = 'us-east', overrides = {}) => new Request('https://placeholder.invalid/v1/bot/whatsapp?region=' + region, {
  method: 'POST', body: raw, ...overrides, headers: { 'content-type': 'application/json',
    'x-hub-signature-256': signature, cookie: 'placeholder-private', authorization: 'placeholder-private',
    'x-tervory-tenant': 'placeholder-forged', 'x-tervory-user': 'placeholder-forged', ...overrides.headers },
});
const get = query => new Request('https://placeholder.invalid/v1/bot/whatsapp?region=za&' + query);
(async () => {
  const route = load({ TANK_URL: 'http://placeholder-tank.invalid', TANK_URL_ZA: 'http://placeholder-za.invalid' });
  const response = await route.POST(post());
  assert.equal(response.status, 200);
  assert.equal(await response.text(), '');
  assert.equal(response.headers.get('cache-control'), 'no-store');
  assert.equal(calls[0].url, 'http://placeholder-tank.invalid/v1/bot/whatsapp');
  assert.equal(new TextDecoder().decode(calls[0].options.body), raw);
  assert.deepEqual(Object.keys(calls[0].options.headers).sort(), ['Content-Type', 'x-hub-signature-256']);
  assert.equal(calls[0].options.headers['x-hub-signature-256'], signature);
  assert.equal(calls[0].options.redirect, 'error');
  assert.equal((await route.POST(post('za'))).status, 200);
  assert.equal(calls[1].url, 'http://placeholder-za.invalid/v1/bot/whatsapp');
  const count = calls.length;
  assert.equal((await route.POST(post('placeholder-invalid'))).status, 503);
  assert.equal((await route.POST(post('za&region=us-east'))).status, 503);
  assert.equal((await load({ TANK_URL: 'http://placeholder-tank.invalid' }).POST(post('za'))).status, 503);
  assert.equal((await route.POST(post('us-east', { headers: { 'x-hub-signature-256': '' } }))).status, 403);
  assert.equal((await route.POST(post('us-east', { headers: { 'content-type': 'text/plain' } }))).status, 415);
  assert.equal((await route.POST(post('us-east', { body: 'placeholder'.repeat(30000) }))).status, 413);
  assert.equal(calls.length, count);
  const challenge = await route.GET(get('hub.mode=subscribe&hub.verify_token=placeholder-verify&hub.challenge=123456'));
  assert.equal(challenge.status, 200);
  assert.equal(await challenge.text(), '123456');
  const call = calls.at(-1);
  assert.equal(call.url, 'http://placeholder-za.invalid/v1/bot/whatsapp');
  assert.equal(call.options.headers['x-whatsapp-verify-token'], 'placeholder-verify');
  assert(!call.url.includes('placeholder-verify'));
  assert.equal((await route.GET(get('hub.mode=subscribe&hub.verify_token=placeholder&hub.challenge=123456&hub.challenge=654321'))).status, 403);
  returned = 'placeholder-reflected';
  assert.equal((await route.GET(get('hub.mode=subscribe&hub.verify_token=placeholder&hub.challenge=123456'))).status, 502);
  code = 403;
  assert.equal((await route.POST(post())).status, 403);
  assert.equal(await (await route.POST(post())).text(), '');
  const middleware = fs.readFileSync(path.resolve(__dirname, '../../workspace/middleware.ts'), 'utf8');
  assert(middleware.includes('"/v1/bot/whatsapp"'));
  const present = workspace({ env: {}, fetch })('app/chats/presentation.ts').presentCard;
  const card = present({ card_id: 'placeholder-card', tool: 'trigger.bot.stats', kind: 'other', status: 'confirmed',
    summary: 'trigger.bot.stats', result: { count: 1000, weeks: [] } }, false);
  assert(card.results.some(row => row.label === 'Count' && row.value === '1000'));
  console.log('PASS actual WhatsApp transport: raw signature bytes, explicit region, no identity/token URL forwarding, bounded input, private result, existing count card');
})().catch(error => { console.error(error); process.exitCode = 1; });
