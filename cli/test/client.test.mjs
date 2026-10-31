import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { run, Tank, originFor, receiptLines, safe, events, StreamSanitizer, showTurn, followThread } from '../src/client.mjs';

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
    if (path.includes('/cards/')) return Response.json({ card_id: 'fake-card', status: calls.at(-1).body.action === 'confirm' ? 'confirmed' : 'cancelled' });
    if (path.endsWith('/fake-thread')) return Response.json({ receipts: [row], steps: [{ step_id: 'fake-card', status: 'done', actor: 'base', label: 'Fake work done' }] });
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

test('pinned model shows Tank-priced Auto comparison and never computes one', async () => {
  const h = harness(); await run(['ask', 'hello', '--model', 'fake-model'], h);
  assert.equal(h.calls.find(c => c.url.endsWith('/turn')).body.model, 'fake-model');
  assert.match(h.output(), /Auto comparison pending/);
  const priced = receiptLines({ rows: [{ ...row, requested_model: 'fake-model', auto_model: 'fake-auto', auto_cost_status: 'priced', auto_cost_usd: 0.05 }] });
  assert.match(priced.join(''), /Auto would have cost 0\.05 \(fake-auto, same tokens at policy model prices\)/);
  const unpriced = receiptLines({ rows: [{ ...row, requested_model: 'fake-model', auto_cost_status: 'pending', auto_cost_usd: 42 }] });
  assert(!unpriced.join('').includes('42'));
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
  assert.equal(h.calls.find(c => c.url.includes('/cards/')).body.action, 'confirm');
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

test('stateful sanitizer redacts synthetic credentials and controls at every character boundary', () => {
  const cases = [
    [TOKEN, '[redacted]'],
    [`before ${TOKEN} after`, 'before [redacted] after'],
    ['héllo \x1b[2Jworld', 'héllo world'],
    ['before\x1b]52;c;ZXZpbA==\x07after', 'beforeafter'],
    ['before\x1b]52;c;ZXZpbA==\x1b\\after', 'beforeafter'],
    ['before\x9d52;c;ZXZpbA==\x9cafter', 'beforeafter'],
    [`${TOKEN.slice(0, 20)}\x1b[31m${TOKEN.slice(20)}`, '[redacted]'],
    ['before\x1b]unfinished', 'before'],
  ];
  for (const [raw, expected] of cases) {
    for (let cut = 0; cut <= raw.length; cut++) {
      const sanitizer = new StreamSanitizer();
      assert.equal(sanitizer.write(raw.slice(0, cut)) + sanitizer.write(raw.slice(cut)) + sanitizer.end(), expected,
        `cut ${cut}`);
    }
    const sanitizer = new StreamSanitizer();
    assert.equal([...raw].map(char => sanitizer.write(char)).join('') + sanitizer.end(), expected);
  }
});

test('actual showTurn path redacts split tokens and controls while streaming ordinary text', async () => {
  const attack = `héllo ${TOKEN} \x1b]52;c;ZXZpbA==\x1b\\ safe`;
  for (let cut = 0; cut <= attack.length; cut++) {
    let output = '';
    const tank = { request: async () => new Response(
      encode('token', { text: attack.slice(0, cut) }) + encode('token', { text: attack.slice(cut) }) + encode('done', {})) };
    await showTurn(tank, 'fake-thread', 'test', 'auto', [], { write: text => { output += text; } });
    assert.equal(output, 'héllo [redacted]  safe', `SSE split ${cut}`);
  }
  const sanitizer = new StreamSanitizer();
  assert.equal(sanitizer.write('ordinary streamed answer'), 'ordinary streamed answer');
});

test('UTF-8 transport splits at every byte preserve sanitizer state', async () => {
  const wire = encode('token', { text: `héllo ${TOKEN}` }) + encode('token', { text: '\x1b[2J world' });
  const bytes = new TextEncoder().encode(wire);
  for (let cut = 0; cut <= bytes.length; cut++) {
    const response = new Response(new ReadableStream({ start(controller) {
      controller.enqueue(bytes.slice(0, cut)); controller.enqueue(bytes.slice(cut)); controller.close();
    } }));
    const sanitizer = new StreamSanitizer(); let output = '';
    for await (const event of events(response)) output += sanitizer.write(event.data.text);
    output += sanitizer.end(); assert.equal(output, 'héllo [redacted] world', `byte ${cut}`);
  }
});

test('authoritative replace discards preview and seq duplicates never duplicate the final answer', async () => {
  let output = ''; const previews = []; let requests = 0;
  const tank = { request: async () => { requests++; return new Response(
    encode('token', { text: 'Provisional text', seq: 1 })
    + encode('token', { text: 'Provisional text', seq: 1 })
    + encode('token', { text: 'Validated final answer.', replace: true, seq: 2 })
    + encode('token', { text: 'Validated final answer.', replace: true, seq: 2 })
    + encode('done', { seq: 3 })); } };
  await showTurn(tank, 'fake-thread', 'test', 'auto', [], { write: text => { output += text; }, preview: text => previews.push(text) });
  assert.equal(output, 'Validated final answer.');
  assert(previews.some(value => value.startsWith('Provisional tex'))); assert.equal(requests, 1);
});

test('whole-string output strips C1 controls in titles cards models and receipts', () => {
  assert.equal(safe('title\x9d52;c;bad\x9c visible\x9b2J'), 'title visible');
  assert.equal(safe(`card ${TOKEN}`), 'card [redacted]');
});

test('job watcher observes steps and receipts until terminal state with read-only polls', async () => {
  let polls = 0; let waits = 0; let output = '';
  const tank = { json: async path => {
    assert.equal(path, '/v1/command/threads/fake-thread'); polls++;
    return { steps: [{ step_id: 'build', status: polls === 1 ? 'running' : 'done', actor: 'worker', label: 'Fake build', link: 'https://example.invalid/fake-pr' }],
      receipts: polls === 1 ? [] : [{ ...row, step_id: 'build' }] };
  } };
  await followThread(tank, 'fake-thread', { card_id: 'card', build_id: 'build' }, {
    write: text => { output += text; }, wait: async () => { waits++; },
  });
  assert.equal(polls, 2); assert.equal(waits, 1);
  assert.match(output, /\[running\]/); assert.match(output, /\[done\]/);
  assert.match(output, /fake-ledger-1/); assert.match(output, /fake-pr/);
});

test('job watcher stops at its bound and does not repeat action or turn', async () => {
  let polls = 0; let output = '';
  await followThread({ json: async () => { polls++; return { steps: [{ step_id: 'card', status: 'running', actor: 'base', label: 'Fake work' }] }; } },
    'fake-thread', { card_id: 'card' }, { write: text => { output += text; }, wait: async () => {} }, { limit: 2, interval: 0 });
  assert.equal(polls, 2); assert.match(output, /Reopen thread fake-thread/);
  assert.equal(output.match(/Fake work/g).length, 1);
});

test('job watcher cancellation and failed state stop without retry', async () => {
  const controller = new AbortController(); controller.abort(); let polls = 0;
  await assert.rejects(followThread({ json: async () => { polls++; } }, 'fake-thread', {},
    { signal: controller.signal, write() {} }), /cancelled/);
  assert.equal(polls, 0);
  await followThread({ json: async () => { polls++; return { cards: [{ card_id: 'card', status: 'unknown' }] }; } },
    'fake-thread', { card_id: 'card' }, { write() {} });
  assert.equal(polls, 1);
});

test('reopened chat shows saved messages and follows existing job without another model turn', async () => {
  let polls = 0; let output = '';
  const h = harness({ answers: ['/exit'] });
  h.transport = async (url, init) => {
    assert.equal(init.method, 'GET'); assert(url.endsWith('/threads/fake-thread')); polls++;
    return Response.json({ messages: [{ role: 'assistant', content: 'Saved answer' }],
      cards: [{ card_id: 'card', status: 'confirmed', build_id: 'build' }],
      steps: [{ step_id: 'build', actor: 'worker', label: 'Saved work', status: polls === 1 ? 'running' : 'done' }] });
  };
  h.io.write = text => { output += text; };
  await run(['chat', 'fake-thread'], h);
  assert.match(output, /Saved answer/); assert.match(output, /Saved work/);
  assert.equal(polls, 2);
});

// Reuse the production run/stream/receipt code for a clearly labeled recording.
export async function fakeTranscript() {
  const h = harness({ answers: ['hello', 'N', '/exit'] });
  await run(['chat', 'fake-thread', '--model', 'fake-model'], h);
  return h.output();
}
