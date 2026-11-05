const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
process.env.COMMAND_TEST_TOOLS ??= path.join(root, 'workspace/node_modules');
const { workspace } = require('./command_acceptance_20261031/workspace_loader.cjs');
const { createDedupeFetch } = require(path.join(root, 'workspace/node_modules/next/dist/server/lib/dedupe-fetch.js'));

const CODE = 'BCDF-GHJK';
const answers = new Map();
const server = http.createServer((req, res) => {
  const answer = answers.get(`${req.method} ${req.url}`) ?? { status: 404, body: '{"detail":"not found"}' };
  res.writeHead(answer.status, { 'content-type': answer.type ?? 'application/json' });
  res.end(answer.body);
});

const within = (promise, ms, label) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${label}: no answer within ${ms} ms (hang)`)), ms).unref()),
]);

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const nextFetch = createDedupeFetch(globalThis.fetch);

  // 0. The harness reproduces the bug: on a deduped GET, cancel() never settles.
  const probe = await nextFetch(`${origin}/v1/command/device/approval/${CODE}`, { method: 'GET', cache: 'no-store' });
  assert.equal(probe.status, 404);
  const settled = await Promise.race([probe.body.cancel().then(() => true), new Promise(r => setTimeout(() => r(false), 300))]);
  assert.equal(settled, false, 'Next dedupe fetch no longer tees GET bodies; revisit this regression test');

  const load = workspace({
    env: { TANK_URL: origin, TANK_API_KEY: 'dummy-workspace-key', TANK_REGION: 'us-east' },
    fetch: nextFetch,
  });
  const { personalCommandRequest } = load('lib/tank.ts');
  const token = `tv1.us-east.${'0'.repeat(32)}.${'A'.repeat(43)}`;
  const call = (target, status, type, body) => {
    answers.set(`GET /v1/command/${target}`, { status, type, body });
    const request = new Request(`https://app.tervory.com/v1/command/${target}`, { headers: { host: 'app.tervory.com', authorization: `Bearer ${token}` } });
    return within(personalCommandRequest(request, target.split('/')), 2000, `adapter ${target} ${status}`);
  };
  assert.equal((await call('threads', 401, 'application/json', '{}')).status, 401);
  assert.equal((await call('threads', 500, 'text/plain', 'boom')).status, 500);
  assert.equal((await call('tools', 200, 'text/html', '<html></html>')).status, 502);
  assert.equal((await call('models', 200, 'application/json', '[]')).status, 404); // founder-only roster is not on the PAT allowlist
  const device = await within(personalCommandRequest(new Request('https://app.tervory.com/v1/command/device/code', {
    method: 'POST', headers: { host: 'app.tervory.com', 'content-type': 'application/json' }, body: '{}' }), ['device', 'code']), 2000, 'device code');
  assert.equal(device.status, 404);

  server.close();

  // 5. Stalls + GC, same process, after section 4 (formerly tests/device_login_timeout.cjs).
  assert.equal(typeof globalThis.gc, 'function', 'run with node --expose-gc');
  const held = [];
  const stall = http.createServer((req, res) => {
    held.push(res);
    // GET: accept and never answer. POST: headers, a partial body, then silence.
    if (req.method === 'POST') { res.writeHead(200, { 'content-type': req.url.includes('/approval/') || req.url.includes('/device/') ? 'application/json' : 'text/event-stream' }); res.write(req.url.includes('/turn') ? 'event: step\ndata: {}\n\n' : '{"user_code":'); }
  });
  await new Promise(resolve => stall.listen(0, '127.0.0.1', resolve));
  const stalled = `http://127.0.0.1:${stall.address().port}`;
  const quiet = workspace({
    env: { TANK_URL: stalled, TANK_API_KEY: 'dummy-workspace-key', TANK_REGION: 'us-east' },
    fetch: nextFetch,
  });
  const quietTank = quiet('lib/tank.ts');
  const collect = setInterval(() => globalThis.gc(), 500);
  // The CLI corridor through lib/tank.ts: device poll with a stalled body, a command whose
  // headers never come, and a turn stream that stalls after its first event.
  const limits = { deviceMs: 1500, headersMs: 1500, idleMs: 1500 };
  const begun = Date.now();
  const deviceStall = await within(quietTank.personalCommandRequest(new Request('https://app.tervory.com/v1/command/device/token', {
    method: 'POST', headers: { host: 'app.tervory.com', 'content-type': 'application/json' }, body: '{}' }), ['device', 'token'], limits), 4000, 'device stall + gc');
  assert.equal(deviceStall.status, 502);
  const headerStall = await within(quietTank.personalCommandRequest(new Request('https://app.tervory.com/v1/command/threads', {
    headers: { host: 'app.tervory.com', authorization: `Bearer ${token}` } }), ['threads'], limits), 4000, 'header stall + gc');
  assert.equal(headerStall.status, 502);
  const ID = '00000000-0000-4000-8000-000000000002';
  const turn = await within(quietTank.personalCommandRequest(new Request(`https://app.tervory.com/v1/command/threads/${ID}/turn`, {
    method: 'POST', headers: { host: 'app.tervory.com', authorization: `Bearer ${token}`, 'content-type': 'application/json' }, body: '{"text":"x"}' }),
    ['threads', ID, 'turn'], limits), 4000, 'turn headers');
  assert.equal(turn.status, 200);
  const reader = turn.body.getReader();
  assert.match(new TextDecoder().decode((await within(reader.read(), 4000, 'first event')).value), /event: step/);
  await assert.rejects(within(reader.read(), 4000, 'stalled stream + gc'), error => error.name === 'DeadlineError');
  assert(Date.now() - begun < 8000);
  clearInterval(collect);
  held.forEach(res => res.destroy()); stall.close();

  console.log('device-login under Next dedupe fetch: lookup/decide/adapter error paths answer promptly; stalls + gc end at their bounds');
})().catch(error => { console.error(error); process.exit(1); });
