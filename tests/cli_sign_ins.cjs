/* Review of #506, B3: the Workspace "CLI sign-ins" list with Revoke.
 * Runs the actual workspace/lib/cli-sign-ins.ts (with lib/device-login.ts and lib/tank.ts)
 * against a recording fetch, and renders the actual app/cli/sign-ins/list.tsx.
 * Synthetic only: dummy keys, no network. Run with: node tests/cli_sign_ins.cjs */
const assert = require('node:assert/strict');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
process.env.COMMAND_TEST_TOOLS ??= path.join(root, 'workspace/node_modules');
const tools = process.env.COMMAND_TEST_TOOLS;
const { workspace } = require('./command_acceptance_20261031/workspace_loader.cjs');
const React = require(path.join(tools, 'react'));
const jsx = require(path.join(tools, 'react/jsx-runtime'));
const { renderToStaticMarkup } = require(path.join(tools, 'react-dom/server'));

const HOME = 'https://tank-us.test';
const ZA = 'https://tank-za.test';
const MINE = '11111111-1111-4111-8111-111111111111';
const OLD = '22222222-2222-4222-8222-222222222222';
const GONE = '33333333-3333-4333-8333-333333333333';
const identity = { tenantId: '00000000-0000-4000-8000-000000000001', userId: 'user_b3', tenantAdmin: true };
const future = new Date(Date.now() + 86400e3).toISOString();
const past = new Date(Date.now() - 1000).toISOString();
const row = (token_id, extra = {}) => ({ token_id, name: 'tervory-cli', region: 'us-east', device_name: 'zenas-mbp',
  created_at: '2026-10-31T20:05:00+00:00', expires_at: future, refresh_expires_at: future, last_used_at: null, revoked_at: null, ...extra });

// Values from the vm sandbox come from another realm; compare their JSON form.
const plain = value => JSON.parse(JSON.stringify(value));
const calls = [];
let answer = () => new Response('[]', { status: 200 });
async function recordingFetch(url, init) {
  calls.push({ url: String(url), method: init.method, headers: { ...init.headers }, redirect: init.redirect, hasSignal: !!init.signal });
  return answer(String(url), init);
}
const env = { TANK_URL: HOME, TANK_API_KEY: 'dummy-workspace-key', TANK_REGION: 'us-east',
              TANK_URL_ZA: ZA, TANK_API_KEY_ZA: 'dummy-za-workspace-key', TANK_DEVICE_APPROVAL_KEY_ZA: 'dummy-za-approval-key' };
const load = workspace({ env, fetch: (...args) => recordingFetch(...args) });
const lib = load('lib/cli-sign-ins.ts');
const within = (promise, ms, label) => Promise.race([promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${label}: no answer within ${ms} ms`)), ms).unref())]);

(async () => {
  // 1. Each region is asked with that region's approval key, scoped to this user and org, no role.
  answer = url => new Response(JSON.stringify(url.startsWith(ZA)
    ? [row(MINE, { region: 'za', device_name: 'za-laptop', last_used_at: '2026-10-31T21:00:00Z' })]
    : [row(OLD), row(GONE, { revoked_at: past }), row('44444444-4444-4444-8444-444444444444', { refresh_expires_at: past }),
       row('not-a-uuid'), { token_id: OLD }]), { status: 200 });
  const regions = await lib.listSignIns(identity);
  assert.deepEqual(calls.map(c => [c.method, c.url]).sort(), [['GET', `${HOME}/v1/personal-tokens`], ['GET', `${ZA}/v1/personal-tokens`]]);
  const byUrl = Object.fromEntries(calls.map(c => [c.url.startsWith(ZA) ? 'za' : 'us', c]));
  assert.equal(byUrl.us.headers['x-tank-key'], 'dummy-workspace-key');
  assert.equal(byUrl.za.headers['x-tank-key'], 'dummy-za-approval-key', 'ZA uses the dedicated approval key, never the ZA Workspace key');
  for (const c of calls) {
    assert.equal(c.headers['x-tervory-user'], 'user_b3');
    assert.equal(c.headers['x-tervory-tenant'], identity.tenantId);
    assert.equal(c.headers['x-tervory-role'], undefined);
    assert.equal(c.redirect, 'manual');
    assert.ok(c.hasSignal);
  }
  // Only active rows: revoked, refresh-expired, malformed rows are dropped.
  assert.deepEqual(plain(regions).map(r => [r.region, r.ok, r.items.map(i => i.token_id)]), [['us-east', true, [OLD]], ['za', true, [MINE]]]);
  assert.deepEqual(Object.keys(plain(regions)[1].items[0]).sort(), ['created_at', 'device_name', 'last_used_at', 'region', 'token_id']);

  // 2. A refused or missing region is a message, never a crash, and the other region still lists.
  calls.length = 0;
  answer = url => url.startsWith(ZA) ? new Response('{"detail":"Not available for this account here"}', { status: 403 })
                                     : new Response('[]', { status: 200 });
  let [us, za] = await lib.listSignIns(identity);
  assert.deepEqual(plain(us), { region: 'us-east', ok: true, items: [] });
  assert.equal(za.ok, false); assert.match(za.message, /managed by Tervory support/);
  answer = url => url.startsWith(ZA) ? new Response('', { status: 302, headers: { location: 'https://evil.test/' } })
                                     : new Response('{}', { status: 200 });
  [us, za] = await lib.listSignIns(identity);
  assert.equal(us.ok, false); assert.match(us.message, /could not be loaded/);
  assert.equal(za.ok, false); assert.match(za.message, /could not be reached/, 'a redirect is never followed');
  const noZa = workspace({ env: { ...env, TANK_URL_ZA: 'http://tank-za.test' }, fetch: recordingFetch })('lib/cli-sign-ins.ts');
  calls.length = 0;
  answer = () => new Response('[]', { status: 200 });
  [, za] = await noZa.listSignIns(identity);
  assert.match(za.message, /not connected here/, 'plain-http ZA URL is refused');
  assert.ok(calls.every(c => !c.url.startsWith('http://')));

  // 3. Revoke: DELETE on the row's own region, only a well-formed id, 204 is success.
  calls.length = 0;
  answer = () => new Response(null, { status: 204 });
  assert.equal(await lib.revokeSignIn(identity, 'za', MINE), true);
  assert.deepEqual(calls.map(c => [c.method, c.url, c.headers['x-tank-key']]), [['DELETE', `${ZA}/v1/personal-tokens/${MINE}`, 'dummy-za-approval-key']]);
  calls.length = 0;
  for (const bad of ['../threads', `${MINE}/x`, '', 'x'.repeat(36)]) assert.equal(await lib.revokeSignIn(identity, 'us-east', bad), false);
  assert.equal(calls.length, 0, 'malformed ids never reach Tank');
  answer = () => new Response('{"detail":"Token not found"}', { status: 404 });
  assert.equal(await lib.revokeSignIn(identity, 'us-east', OLD), false);

  // 4. Hard deadline, body included: headers then a body that never ends.
  answer = () => new Response(new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode('[')); } }), { status: 200 });
  const started = Date.now();
  const [stalled, revoke] = await within(Promise.all([lib.listSignIns(identity), lib.revokeSignIn(identity, 'us-east', OLD)]),
                                         lib.SIGN_IN_TIMEOUT_MS + 3000, 'stalled body');
  assert.ok(Date.now() - started >= lib.SIGN_IN_TIMEOUT_MS - 50);
  assert.ok(stalled.every(r => !r.ok && /could not be reached/.test(r.message)));
  assert.equal(revoke, false);

  // 5. The page renders the device name, region, created and last used, with one Revoke form per sign-in.
  const { SignInList, when } = workspace({ env, fetch: recordingFetch,
    mocks: { react: React, 'react/jsx-runtime': jsx } })('app/cli/sign-ins/list.tsx');
  const action = async () => {};
  const html = renderToStaticMarkup(React.createElement(SignInList, { regions, action }));
  assert.match(html, /<h1>CLI sign-ins/);
  assert.match(html, /za-laptop/); assert.match(html, /zenas-mbp/);
  assert.match(html, /South Africa \(ZA\)/); assert.match(html, /US East/);
  assert.match(html, /Signed in Oct 31, 2026, 20:05 UTC/);
  assert.match(html, /Last used Oct 31, 2026, 21:00 UTC/); assert.match(html, /Last used Never/);
  assert.equal((html.match(/>Revoke<\/button>/g) ?? []).length, 2);
  assert.match(html, new RegExp(`name="token_id" value="${MINE}"`));
  assert.match(html, /name="region" value="za"/);
  assert.match(html, /gives whoever started that sign-in your access/);
  for (const secret of ['dummy-', 'token_hash', 'refresh']) assert.ok(!html.includes(secret), secret);
  const empty = renderToStaticMarkup(React.createElement(SignInList, { regions: [us, { region: 'za', ok: false, message: 'Down.' }], action, notice: 'Revoked.' }));
  assert.match(empty, /No active CLI sign-ins/); assert.match(empty, /South Africa \(ZA\): Down\./); assert.match(empty, /role="status">Revoked\./);
  assert.equal(when(null), 'Never'); assert.equal(when('nope'), 'Unknown');
  console.log('cli_sign_ins: ok');
})().catch(error => { console.error(error); process.exit(1); });
