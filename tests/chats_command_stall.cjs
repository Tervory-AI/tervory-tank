/* Review of #506, B1, applied to the /chats loop: commandRequest (and the roster read the
 * route does on every request) must end at a hard bound, body included, even when Tank
 * stalls and a GC runs mid-stall. On Node 22 / undici 6.29.1 a redirect:"error" fetch
 * whose body stalls ignores its abort after a GC; commandRequest used exactly that.
 *
 * Runs the actual workspace/app/chats/api/[...path]/route.ts and lib/tank.ts against a
 * loopback Tank stub, with short bounds, and checks for each case that the caller gets a
 * plain answer within the bound and that the upstream connection is closed:
 *   headers never come; headers then a stalled JSON body; an error status with a stalled
 *   body; a turn stream that stalls after its first event; a live stream that keeps
 *   sending heartbeats past the idle bound (must NOT be cut); a redirect (never followed);
 *   a stalled roster read; commandRequest under Next's render-time dedupe fetch; and a JSON
 *   body that trickles a byte every 300 ms forever (beats the idle bound, so only the
 *   total body deadline ends it) through both the /chats route and the CLI PAT proxy, plus
 *   a stalled PAT proxy JSON body; each PAT proxy stop must close its upstream connection.
 * Run with: node --expose-gc tests/chats_command_stall.cjs. Synthetic: dummy keys, loopback. */
const assert = require('node:assert/strict');
const http = require('node:http');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
process.env.COMMAND_TEST_TOOLS ??= path.join(root, 'workspace/node_modules');
const { workspace } = require('./command_acceptance_20261031/workspace_loader.cjs');
const { createDedupeFetch } = require(path.join(root, 'workspace/node_modules/next/dist/server/lib/dedupe-fetch.js'));

assert.equal(typeof globalThis.gc, 'function', 'run with node --expose-gc');
const TENANT = '00000000-0000-4000-8000-000000000001';
const ID = '00000000-0000-4000-8000-000000000002';
const BOUND = 1500;
const within = (promise, ms, label) => Promise.race([
  promise,
  new Promise((_, reject) => setTimeout(() => reject(new Error(`${label}: no answer within ${ms} ms (hang)`)), ms).unref()),
]);

let mode = {};
const closed = [];
const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  res.on('close', () => closed.push(url.pathname));
  if (url.pathname === '/v1/models') {
    if (mode.roster === 'stall') { res.writeHead(200, { 'content-type': 'application/json' }); res.write('['); return; }
    res.writeHead(200, { 'content-type': 'application/json' }); res.end('[]'); return;
  }
  const kind = mode[url.pathname] ?? 'silent';
  if (kind === 'silent') return; // accept, never answer
  if (kind === 'stalled-json') { res.writeHead(200, { 'content-type': 'application/json' }); res.write('{"thread_id":'); return; }
  if (kind === 'stalled-error') { res.writeHead(500, { 'content-type': 'application/json' }); res.write('{"detail":'); return; }
  if (kind === 'trickle-json') { // never idle, never finishes: only a total deadline ends it
    res.writeHead(200, { 'content-type': 'application/json' }); res.write('{"threads":[');
    const drip = setInterval(() => res.write(' '), 300); res.on('close', () => clearInterval(drip)); return;
  }
  if (kind === 'redirect') { res.writeHead(302, { location: 'http://127.0.0.1:1/elsewhere' }); res.end(); return; }
  if (kind === 'stalled-stream') { res.writeHead(200, { 'content-type': 'text/event-stream' }); res.write('event: step\ndata: {"seq":1,"label":"Reading","actor":"Auto"}\n\n'); return; }
  if (kind === 'heartbeats') {
    res.writeHead(200, { 'content-type': 'text/event-stream' });
    res.write('event: token\ndata: {"seq":1,"text":"hi"}\n\n');
    const beat = setInterval(() => res.write(': waiting\n\n'), 200);
    setTimeout(() => { clearInterval(beat); res.end('event: done\ndata: {"seq":2}\n\n'); }, BOUND * 2);
    return;
  }
  res.writeHead(404); res.end();
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const make = fetch => {
    const load = workspace({
      env: { TANK_URL: origin, TANK_API_KEY: 'dummy-workspace-key', TANK_REGION: 'us-east' }, fetch,
      mocks: {
        '@/lib/trigger': { triggerIdentity: async tenant => tenant && { ...tenant, tenantAdmin: false } },
        '@/lib/tenant': { activeTenant: async () => ({ tenantId: TENANT, userId: 'user_chat', orgName: 'Stall', orgId: 'org_stall' }) },
        '@/lib/admin': { isFounder: () => false },
      },
    });
    const tank = load('lib/tank.ts');
    // The defaults are 300 s headers / 120 s stream idle / 60 s body / 15 s roster.
    assert.deepEqual(JSON.parse(JSON.stringify(tank.COMMAND_LIMITS)), { headersMs: 300000, idleMs: 120000, bodyMs: 60000 });
    assert.equal(tank.ROSTER_TIMEOUT_MS.value, 15000);
    Object.assign(tank.COMMAND_LIMITS, { headersMs: BOUND, idleMs: BOUND, bodyMs: BOUND });
    tank.ROSTER_TIMEOUT_MS.value = BOUND;
    return { tank, route: load('app/chats/api/[...path]/route.ts') };
  };
  // Records the signal each upstream fetch got, so a stop can be shown to abort the fetch
  // itself (a reader cancel alone also closes a healthy socket, so that is checked too).
  const sent = [];
  const recording = (url, init) => {
    const p = new URL(String(url)).pathname;
    sent.push({ url: String(url), signal: init?.signal, kind: p === '/v1/models' ? mode.roster ?? 'ok' : mode[p] ?? 'silent' });
    return globalThis.fetch(url, init);
  };
  const { tank, route } = make(recording);
  const call = (target, method = 'GET', body) => route[method](new Request(`https://app.tervory.com/chats/api/${target}`, {
    method, headers: { origin: 'https://app.tervory.com', host: 'app.tervory.com', 'content-type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body) }), { params: Promise.resolve({ path: target.split('/') }) });
  const timed = async (label, work) => {
    const began = Date.now(); const result = await within(work(), BOUND * 3, label); const took = Date.now() - began;
    return { result, took };
  };
  const collect = setInterval(() => globalThis.gc(), 300);

  // 1. Headers never come.
  mode = {};
  let { result, took } = await timed('headers stall', () => call('threads'));
  assert.equal(result.status, 504); assert.match((await result.json()).error, /did not answer in time/);
  assert(took >= BOUND - 100, `bound, not an early failure (${took} ms)`);

  // 2. Headers, then a JSON body that stalls.
  mode = { [`/v1/command/threads/${ID}`]: 'stalled-json' };
  ({ result, took } = await timed('json body stall', () => call(`threads/${ID}`)));
  assert.equal(result.status, 502); assert.match((await result.json()).error, /could not be completed/);

  // 3. An error status whose body stalls (the detail read is bounded too).
  mode = { '/v1/command/threads': 'stalled-error' };
  ({ result } = await timed('error body stall', () => call('threads', 'POST', { title: 'x' })));
  assert.equal(result.status, 502);

  // 4. A turn stream that stalls after its first event: the client gets the event, then a
  //    plain interruption message, and the stream ends; no model name appears.
  mode = { [`/v1/command/threads/${ID}/turn`]: 'stalled-stream' };
  ({ result } = await timed('turn headers', () => call(`threads/${ID}/turn`, 'POST', { text: 'hello', model: 'auto' })));
  assert.equal(result.status, 200);
  ({ result: result, took } = await timed('stalled turn stream', () => new Response(result.body).text()));
  assert.match(result, /event: step/);
  assert.match(result, /event: error\ndata: \{"message":"The response was interrupted\. Reopen this chat before sending again\."\}/);
  assert(took < BOUND * 2.5, `stream ended at its idle bound (${took} ms)`);

  // 5. Heartbeats keep a live stream open past the idle bound; it completes normally.
  mode = { [`/v1/command/threads/${ID}/events`]: 'heartbeats' };
  ({ result } = await timed('events headers', () => call(`threads/${ID}/events`)));
  ({ result, took } = await timed('heartbeat stream', () => new Response(result.body).text()));
  assert.match(result, /event: token/); assert.match(result, /event: done/); assert.doesNotMatch(result, /event: error/);
  assert(took >= BOUND, `ran longer than the idle bound (${took} ms) without being cut`);

  // 6. A redirect is refused, never followed.
  mode = { '/v1/command/threads': 'redirect' };
  ({ result } = await timed('redirect', () => call('threads')));
  assert.equal(result.status, 502);

  // 7. The roster read the route does first: a stalled body ends at its bound.
  mode = { roster: 'stall' };
  ({ result, took } = await timed('roster stall', () => call(`threads/${ID}`)));
  assert.equal(result.status, 502);
  assert(took >= BOUND - 100 && took < BOUND * 2.5, `roster bound (${took} ms)`);
  await assert.rejects(within(tank.listRoster(), BOUND * 3, 'listRoster'), error => error.name === 'DeadlineError');

  // 8. The page path: commandRequest under Next's render-time dedupe fetch, stalled body.
  const paged = make(createDedupeFetch(globalThis.fetch));
  mode = { '/v1/command/threads': 'stalled-json' };
  const response = await within(paged.tank.commandRequest({ tenantId: TENANT, userId: 'user_chat' }, 'threads'), BOUND * 3, 'page headers');
  await assert.rejects(within(response.json(), BOUND * 3, 'page body stall'), error => error.name === 'DeadlineError');
  mode = {};
  await assert.rejects(within(paged.tank.commandRequest({ tenantId: TENANT, userId: 'user_chat' }, 'threads'), BOUND * 3, 'page headers stall'),
    error => error.status === 504 && error.code === 'timeout');

  // 9. A JSON body that never goes idle and never ends: the total body deadline ends it.
  mode = { [`/v1/command/threads/${ID}`]: 'trickle-json' };
  ({ result, took } = await timed('chats json trickle', () => call(`threads/${ID}`)));
  assert.equal(result.status, 502);
  assert(took >= BOUND - 100 && took < BOUND * 2.5, `chats total body bound (${took} ms)`);

  // 10. The same trickle through the CLI PAT proxy (personalCommandRequest): the JSON read
  //     ends at its total bound (bodyMs, 60 s by default), not only an idle bound.
  //     Each stop must also close the upstream connection (the proxy aborts its fetch, not
  //     only the reader): checked per path right after the stop, before anything else runs.
  const pat = `tv1.us-east.${'0'.repeat(32)}.${'A'.repeat(43)}`;
  const PAT_LIMITS = { headersMs: BOUND, idleMs: BOUND, deviceMs: BOUND, bodyMs: BOUND };
  const viaPat = id => within(tank.personalCommandRequest(new Request(`https://app.tervory.com/v1/command/threads/${id}`, {
    headers: { host: 'app.tervory.com', authorization: `Bearer ${pat}` } }), ['threads', id], PAT_LIMITS), BOUND * 3, `pat headers ${id}`);
  const closedSoon = async (p, label) => {
    const until = Date.now() + 1000;
    while (!closed.includes(p) && Date.now() < until) await new Promise(resolve => setTimeout(resolve, 25));
    assert(closed.includes(p), `${label}: upstream ${p} was closed after the stop`);
    const call = sent.filter(entry => new URL(entry.url).pathname === p).at(-1);
    assert(call?.signal?.aborted, `${label}: the upstream fetch for ${p} was aborted, not only its reader cancelled`);
  };
  const PAT_TRICKLE = '00000000-0000-4000-8000-000000000003', PAT_STALL = '00000000-0000-4000-8000-000000000004';
  mode = { [`/v1/command/threads/${PAT_TRICKLE}`]: 'trickle-json', [`/v1/command/threads/${PAT_STALL}`]: 'stalled-json' };
  const proxied = await viaPat(PAT_TRICKLE);
  assert.equal(proxied.status, 200);
  const patBegan = Date.now();
  await assert.rejects(within(proxied.text(), BOUND * 3, 'pat json trickle'), error => error.name === 'DeadlineError');
  const patTook = Date.now() - patBegan;
  assert(patTook < BOUND * 2.5, `pat total body bound (${patTook} ms)`);
  await closedSoon(`/v1/command/threads/${PAT_TRICKLE}`, 'pat total deadline');
  //     A JSON body that stalls (idle stop) through the PAT proxy: same, socket closed.
  const stalledPat = await viaPat(PAT_STALL);
  await assert.rejects(within(stalledPat.text(), BOUND * 3, 'pat json stall'), error => error.name === 'DeadlineError');
  await closedSoon(`/v1/command/threads/${PAT_STALL}`, 'pat idle stop');

  clearInterval(collect);
  // Every stalled upstream connection was closed by the Workspace, not left open.
  await new Promise(resolve => setTimeout(resolve, 300));
  for (const p of ['/v1/command/threads', `/v1/command/threads/${ID}`, `/v1/command/threads/${ID}/turn`, '/v1/models'])
    assert(closed.includes(p), `upstream ${p} was closed`);
  // And every upstream fetch that met a stall (silent, stalled body, trickle) was aborted.
  const stalls = sent.filter(entry => ['silent', 'stalled-json', 'stalled-error', 'stalled-stream', 'trickle-json', 'stall'].includes(entry.kind));
  assert(stalls.length >= 8, `stalled fetches recorded (${stalls.length})`);
  for (const entry of stalls) assert(entry.signal?.aborted, `upstream fetch ${new URL(entry.url).pathname} (${entry.kind}) was aborted`);
  server.closeAllConnections(); server.close();
  console.log('chats_command_stall: commandRequest, the roster read and the PAT proxy JSON end at their bounds under stalls, trickles + gc; heartbeats keep streams alive');
})().catch(error => { console.error(error); process.exit(1); });
