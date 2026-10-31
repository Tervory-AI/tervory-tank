import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { run, Tank, originFor, receiptLines, safe, events } from '../src/client.mjs';

// Synthetic credentials exist only in this fake-Tank harness, never live data.
const TOKEN = `tv1.us-east.${'0'.repeat(32)}.${'x'.repeat(43)}`;
const row = { step_id: 's1', model: 'fake-model', tokens_in: 20, tokens_out: 8,
  cost_usd: '0.000028', baseline_cost_usd: '0.000056', saved_usd: '0.000028', ledger_id: 'fake-ledger-1' };
const encode = (kind, data) => `event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`;

function harness({ answers = [], token = TOKEN, refusal = false } = {}) {
  let saved = token; let output = ''; const calls = []; const stored = [];
  const io = {
    write: value => { output += value; },
    secret: async () => token,
    prompt: async () => answers.shift() ?? null,
  };
  const transport = async (url, init) => {
    calls.push({ url, ...init, body: init.body ? JSON.parse(init.body) : null });
    assert.equal(init.redirect, 'error');
    assert.equal(init.headers.Authorization, `Bearer ${token}`);
    assert.equal(new URL(url).origin, originFor(token));
    if (refusal) return new Response('must not print secret detail', { status: 401 });
    const path = new URL(url).pathname;
    if (path.endsWith('/tools')) return Response.json(['base.batch', 'base.search']);
    if (path.endsWith('/models')) return Response.json([{ name: 'fake-model', input_usd_per_m: 1, output_usd_per_m: 2 }]);
    if (path.endsWith('/threads')) return Response.json(init.method === 'GET'
      ? [{ thread_id: 'fake-thread', title: 'Fake Tank evidence', spent_usd: '0.000028', saved_usd: '0.000028' }]
      : { thread_id: 'fake-thread' });
    if (path.endsWith('/turn')) {
      return new Response(encode('step', { status: 'running', actor: 'Tank', label: 'Fake step' })
        + encode('token', { text: 'Fake Tank answer.' })
        + encode('receipt', { rows: [{ ...row, requested_model: calls.at(-1).body.model }] })
        + encode('card', { card_id: 'fake-card', summary: 'Fake action', status: 'pending' })
        + encode('done', { message_id: 'fake-message' }), { headers: { 'Content-Type': 'text/event-stream' } });
    }
    if (path.endsWith('/actions') || path.endsWith('/build')) return Response.json({ card_id: 'fake-card', summary: 'Fake action', status: 'pending' });
    if (path.includes('/cards/')) return Response.json({ status: calls.at(-1).body.action === 'confirm' ? 'confirmed' : 'cancelled' });
    if (path.endsWith('/fake-thread')) return Response.json({ receipts: [row] });
    throw new Error(`Unexpected fake route ${path}`);
  };
  return { io, transport, calls, stored,
    store: { get: async () => saved, set: async value => { saved = value; stored.push(value); }, remove: async () => { saved = null; } },
    output: () => output };
}

test('login validates with Tank and writes only to keychain interface, never terminal', async () => {
  const h = harness(); await run(['login'], h);
  assert.deepEqual(h.stored, [TOKEN]);
  assert.equal(h.calls.length, 1); assert.match(h.calls[0].url, /\/command\/tools$/);
  assert(!h.output().includes(TOKEN));
});

test('revoked token refused before keychain write or command execution', async () => {
  const h = harness({ refusal: true });
  await assert.rejects(run(['login'], h), /Personal token refused/);
  assert.deepEqual(h.stored, []);
  await assert.rejects(run(['ask', 'hello'], h), /Personal token refused/);
  assert(!h.output().includes('secret detail'));
});

test('chat streams steps tokens receipt and N cancels without confirm', async () => {
  const h = harness({ answers: ['hello', 'N', '/exit'] });
  await run(['chat', 'fake-thread'], h);
  assert.match(h.output(), /\[running\] Tank: Fake step/);
  assert.match(h.output(), /Fake Tank answer/);
  assert.match(h.output(), /fake-ledger-1/);
  assert.match(h.output(), /baseline 0.000056/);
  assert(h.calls.some(c => c.body?.action === 'cancel'));
  assert(!h.calls.some(c => c.body?.action === 'confirm'));
});

test('one-shot defaults model to Auto and EOF cancels', async () => {
  const h = harness(); await run(['ask', 'hello'], h);
  assert.equal(h.calls.find(c => c.url.endsWith('/turn')).body.model, 'auto');
  assert.equal(h.calls.at(-1).body.action, 'cancel');
});

test('pinned model reports unavailable Auto instead of invented price snapshot', async () => {
  const h = harness(); await run(['ask', 'hello', '--model', 'fake-model'], h);
  assert.equal(h.calls.find(c => c.url.endsWith('/turn')).body.model, 'fake-model');
  assert.match(h.output(), /Auto unavailable \(no historical ledger evidence\)/);
  const calculated = receiptLines({ rows: [{ ...row, requested_model: 'fake-model', auto_cost_status: 'priced', auto_cost_usd: 42 }] });
  assert(!calculated.join('').includes('42'));
});

test('client cannot propose founder tools', async () => {
  const h = harness();
  await assert.rejects(run(['run', 'skala', 'approve', '--args', '{}'], h), /not available/);
  assert(!h.calls.some(c => c.url.endsWith('/actions')));
});

test('known squad action uses code, creates pending card, requires explicit yes', async () => {
  const h = harness({ answers: ['yes'] });
  await run(['run', 'base', 'search', '--args', '{"q":"synthetic"}'], h);
  const action = h.calls.find(c => c.url.endsWith('/actions'));
  assert.deepEqual(action.body, { tool: 'base.search', arguments: { q: 'synthetic' } });
  assert(!h.calls.some(c => c.url.endsWith('/turn')));
  assert.equal(h.calls.at(-1).body.action, 'confirm');
});

test('CSV file intake maps existing batch records without model', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'cli-fake-'));
  try {
    const file = join(directory, 'synthetic.csv');
    await writeFile(file, 'name,city\n"Fake, Name",Testville\n');
    const h = harness(); await run(['run', 'base', 'batch', '--file', file], h);
    assert.deepEqual(h.calls.find(c => c.url.endsWith('/actions')).body.arguments,
      { batch: 'synthetic', records: [{ name: 'Fake, Name', city: 'Testville' }] });
    assert(!h.calls.some(c => c.url.endsWith('/turn')));
  } finally { await rm(directory, { recursive: true }); }
});

test('build prints brief and declines without worker action', async () => {
  const h = harness({ answers: ['no'] }); await run(['build', 'Synthetic test brief'], h);
  assert.match(h.output(), /Synthetic test brief/);
  assert.equal(h.calls.find(c => c.url.endsWith('/build')).body.brief_markdown, 'Synthetic test brief');
  assert.equal(h.calls.at(-1).body.action, 'cancel');
});

test('token region alone chooses endpoint; no mutable origin option', async () => {
  assert.equal(originFor(TOKEN), 'https://app.tervory.com');
  assert.equal(originFor(TOKEN.replace('us-east', 'za')), 'https://za.tervory.com');
  const h = harness({ token: TOKEN.replace('us-east', 'za') }); await run(['models'], h);
  assert(h.calls.every(c => c.url.startsWith('https://za.tervory.com/')));
  await assert.rejects(run(['models', '--origin', 'https://other.invalid'], h), /Invalid command option/);
  assert.throws(() => new Tank('malformed'), /refused/);
});

test('threads and receipts preserve ledger numbers without rounding or estimates', async () => {
  const h = harness(); await run(['threads'], h); await run(['receipts', 'fake-thread'], h);
  assert.match(h.output(), /spent 0.000028/); assert.match(h.output(), /cost 0.000028/);
  assert.match(h.output(), /saved 0.000028/);
});

test('transport errors do not expose token or response body and never retry', async () => {
  let count = 0;
  const tank = new Tank(TOKEN, async () => { count++; throw new Error(TOKEN); });
  await assert.rejects(tank.request('/v1/command/tools'), /^Error: Tank connection failed\.$/);
  assert.equal(count, 1);
  await assert.rejects(tank.request('https://other.invalid/'), /path refused/);
});

test('terminal controls and complete credential strings are redacted', () => {
  assert.equal(safe(`\x1b[2J${TOKEN}`), '[redacted]');
  assert(!safe('\x1b]52;c;ZXZpbA==\x07').includes('ZXZpbA'));
});

test('SSE handles UTF-8 and event boundaries split across reads', async () => {
  const bytes = new TextEncoder().encode(encode('token', { text: 'héllo' }));
  const body = new ReadableStream({ start(controller) {
    for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
    controller.close();
  } });
  const out = []; for await (const item of events(new Response(body))) out.push(item);
  assert.deepEqual(out, [{ kind: 'token', data: { text: 'héllo' } }]);
});

test('stream truncation is not silently accepted or retried', async () => {
  const response = new Response('event: token\ndata: {"text":"hello"}');
  await assert.rejects(async () => { for await (const _ of events(response)) {} }, /interrupted/);
});

// Reuse the production run/stream/receipt code for a clearly labeled recording.
export async function fakeTranscript() {
  const h = harness({ answers: ['hello', 'N', '/exit'] });
  await run(['chat', 'fake-thread', '--model', 'fake-model'], h);
  return h.output();
}
