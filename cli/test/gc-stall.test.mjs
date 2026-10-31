// Review of #506, B1: on Node 22 / undici 6.29.1 a fetch with redirect:"error" whose body
// stalls after the headers never aborts once a GC has run. Every CLI call must still end
// at its own deadline. npm test runs node --expose-gc; gc() runs throughout each stall.
import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { deviceCall, events, Tank } from '../src/client.mjs';
import { latestVersion } from '../src/update.mjs';
import { boundedFetch, DeadlineError, RedirectError } from '../src/http.mjs';

const TOKEN = `tv1.us-east.${'0'.repeat(32)}.${'A'.repeat(43)}`;

async function stallingServer(handler) {
  const held = [];
  const server = createServer((req, res) => { held.push(res); handler(req, res); });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  const transport = (url, init) => fetch(`http://127.0.0.1:${port}${new URL(url).pathname}`, init);
  return { transport, close: () => { held.forEach(res => res.destroy()); server.close(); } };
}

async function withGc(work) {
  assert.equal(typeof globalThis.gc, 'function', 'npm test must run node --expose-gc');
  const timer = setInterval(() => globalThis.gc(), 100);
  try { return await work(); } finally { clearInterval(timer); }
}

const bounded = async (promise, low, high) => {
  const began = Date.now();
  const outcome = await Promise.race([
    promise.then(value => ({ value }), error => ({ error })),
    new Promise(resolve => setTimeout(() => resolve({ hung: true }), high).unref()),
  ]);
  assert(!outcome.hung, `still pending after ${high} ms (hang)`);
  assert(Date.now() - began >= low, 'ended before its deadline');
  return outcome;
};

test('stalled body + gc: deviceCall, Tank.json, a stalled stream and latest.json all end at their deadlines', async () => {
  const { transport, close } = await stallingServer((req, res) => {
    const stream = req.url.endsWith('/turn');
    res.writeHead(200, { 'content-type': stream ? 'text/event-stream' : 'application/json' });
    res.write(stream ? 'event: step\ndata: {}\n\n' : '{"a":');
  });
  try {
    await withGc(async () => {
      const device = await bounded(deviceCall('us-east', 'token', {}, transport, {}, 500), 450, 3000);
      assert.match(device.error.message, /^Tank connection failed\.$/);

      const latest = await bounded(latestVersion(transport, undefined, 500), 450, 3000);
      assert.match(latest.error.message, /latest\.json did not arrive in time/);

      // Tank.json bounds the whole call: drive boundedFetch with the same read Tank.json uses.
      const json = await bounded(boundedFetch(transport, 'https://app.tervory.com/v1/command/threads', {}, 500, r => r.json()), 450, 3000);
      assert(json.error instanceof DeadlineError);

      const tank = new Tank(TOKEN, transport);
      const response = await tank.request('/v1/command/threads/x/turn', { text: 'x' });
      const seen = [];
      const stream = (async () => { for await (const event of events(response, { idleMs: 500 })) seen.push(event.kind); })();
      const stalled = await bounded(stream, 450, 3000);
      assert.deepEqual(seen, ['step']);
      assert.match(stalled.error.message, /Tank stream stalled; the turn was not retried/);
    });
  } finally { close(); }
});

test('no headers + gc: Tank.request ends at its header deadline', async () => {
  const { transport, close } = await stallingServer(() => {});
  try {
    await withGc(async () => {
      const result = await bounded(boundedFetch(transport, 'https://app.tervory.com/v1/command/tools', {}, 500, r => r), 450, 3000);
      assert(result.error instanceof DeadlineError);
    });
  } finally { close(); }
});

test('redirects are refused, never followed, on every bounded call', async () => {
  let hits = 0;
  const { transport, close } = await stallingServer((req, res) => {
    hits++; res.writeHead(302, { location: 'https://evil.example/' }); res.end();
  });
  try {
    await assert.rejects(boundedFetch(transport, 'https://app.tervory.com/x', {}, 2000, r => r), error => error instanceof RedirectError && error.status === 302);
    await assert.rejects(deviceCall('us-east', 'code', {}, transport), /^Error: Tank connection failed\.$/);
    await assert.rejects(new Tank(TOKEN, transport).json('/v1/command/tools'), /^Error: Tank connection failed\.$/);
    await assert.rejects(latestVersion(transport), /redirected \(302\); redirects are refused/);
    assert.equal(hits, 4);
  } finally { close(); }
});

test('Ctrl-C (the caller signal) still aborts a stalled stream at once', async () => {
  const { transport, close } = await stallingServer((req, res) => { res.writeHead(200, { 'content-type': 'text/event-stream' }); res.write(': hi\n\n'); });
  try {
    const controller = new AbortController();
    const tank = new Tank(TOKEN, transport, controller.signal);
    const response = await tank.request('/v1/command/threads/x/turn', { text: 'x' });
    const stream = (async () => { for await (const _ of events(response, { signal: controller.signal, idleMs: 60_000 })); })();
    setTimeout(() => controller.abort(), 200);
    const result = await bounded(stream, 150, 3000);
    assert.match(result.error.message, /Command cancelled/);
  } finally { close(); }
});
