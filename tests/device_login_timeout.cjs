/* Regression: Tank accepts the connection and never answers, or sends headers and
 * stalls the body. device-login.ts had no timeout, so the /cli/device render and the
 * Approve action waited until undici's ~300 s header timeout (review of #496, item 1).
 * Now bounded by DEVICE_TIMEOUT_MS (10 s) and mapped to the existing 502 message.
 * Runs the actual workspace/lib/device-login.ts behind Next's own dedupe fetch.
 * Synthetic only: dummy keys, loopback, no network. */
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
process.env.COMMAND_TEST_TOOLS ??= path.join(root, 'workspace/node_modules');
const { workspace } = require('./command_acceptance_20261031/workspace_loader.cjs');
const { createDedupeFetch } = require(path.join(root, 'workspace/node_modules/next/dist/server/lib/dedupe-fetch.js'));

const CODE = 'BCDF-GHJK';
const identity = { tenantId: '00000000-0000-4000-8000-000000000001', userId: 'user_e2e', tenantAdmin: false };
const within = (promise, ms, label) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${label}: no answer within ${ms} ms (hang)`)), ms).unref()),
]);

(async () => {
  const nextFetch = createDedupeFetch(globalThis.fetch);
  // Tank accepts TCP and never answers, or sends headers then stalls the body:
  //    lookup and approve both end with the 502 "could not be reached" message, within the bound.
  const held = [];
  const silent = http.createServer((req, res) => {
    held.push(res);
    if (req.method === 'POST') { res.writeHead(200, { 'content-type': 'application/json' }); res.write('{"user_code":'); }
  });
  await new Promise(resolve => silent.listen(0, '127.0.0.1', resolve));
  const quiet = workspace({
    env: { TANK_URL: `http://127.0.0.1:${silent.address().port}`, TANK_API_KEY: 'dummy-workspace-key', TANK_REGION: 'us-east' },
    fetch: nextFetch,
  })('lib/device-login.ts');
  assert.equal(quiet.DEVICE_TIMEOUT_MS, 10_000);
  const began = Date.now();
  const [lookup, decide] = await within(Promise.all([
    quiet.deviceApproval(identity, 'us-east', CODE),
    quiet.deviceApproval(identity, 'us-east', CODE, 'approve'),
  ]), 13_000, 'silent Tank');
  assert.equal(lookup.ok, false); assert.equal(lookup.status, 502); assert.match(lookup.message, /could not be reached/);
  // POST: headers arrive, the body never finishes; the same signal cuts it off.
  assert.equal(decide.ok, false); assert.equal(decide.status, 502);
  assert(Date.now() - began >= 9_000, 'the bound is the 10 s timeout, not an early failure');
  held.forEach(res => res.destroy()); silent.close();

  console.log('device-login: silent and stalled Tank both end at the 10 s bound');
})().catch(error => { console.error(error); process.exit(1); });
