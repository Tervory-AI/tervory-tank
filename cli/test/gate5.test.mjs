import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { mkdtemp, writeFile, mkdir, symlink, link, rm, readFile } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { performance } from 'node:perf_hooks';
import { run, Tank, events, safe } from '../src/client.mjs';
import { boundedFetch, boundedBody, responseBytes } from '../src/http.mjs';
import { MCPClients } from '../src/mcp.mjs';
import { latestVersion } from '../src/update.mjs';
import { TerminalUI, terminalIO } from '../src/terminal.mjs';
import { LIMITS } from '../src/code-tools.mjs';

const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'placeholder'.padEnd(43, 'x');
const refresh = token.replace('tv1.', 'tvr1.');
const grant = () => ({ access_token: token, refresh_token: refresh, expires_at: new Date(Date.now()+3600000).toISOString(), refresh_expires_at: new Date(Date.now()+86400000).toISOString() });
const forbid = () => assert.fail('No request or side effect is permitted');
const output = (answers = []) => {
  const io = { interactive: true, text: '', labels: [], write(value) { io.text += value; }, async prompt(label) { io.labels.push(label); return answers.shift() ?? null; } };
  return io;
};
async function folder(t) {
  const root = await mkdtemp(join(tmpdir(), 'opli-launch-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  execFileSync('git', ['init', '-q', root]);
  return root;
}
async function fakeTank(t, handler) {
  const calls = []; const errors = [];
  const server = createServer(async (req, res) => {
    try {
      const parts = []; for await (const part of req) parts.push(part);
      const call = { path: req.url, method: req.method, headers: req.headers, body: parts.length ? JSON.parse(Buffer.concat(parts)) : undefined };
      calls.push(call);
      if (!call.path.includes('/device/')) assert.equal(call.headers.authorization, `Bearer ${token}`);
      else assert.equal(call.headers.authorization, undefined);
      await handler(call, res);
    } catch (error) { errors.push(error); res.writeHead(500).end('{}'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(async () => { server.closeAllConnections(); await new Promise(resolve => server.close(resolve)); assert.deepEqual(errors, []); });
  const transport = (url, init) => {
    assert.equal(new URL(url).origin, 'https://app.tervory.com');
    return fetch(`http://127.0.0.1:${server.address().port}${new URL(url).pathname}`, init);
  };
  return { calls, transport };
}
const json = (res, body, status = 200) => res.writeHead(status, { 'content-type': 'application/json' }).end(JSON.stringify(body));
const stream = (res, frames) => res.writeHead(200, { 'content-type': 'text/event-stream' }).end(frames.map(([event, data]) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`).join(''));
const receipt = { ledger_id: 'recorded-ledger', model: 'fixture-model', cost_usd: 0.004, tokens_in: 4, tokens_out: 8, saved_usd: 0, baseline_cost_usd: 0.004 };

test('gate5 journey: first device signup, day zero, attached first question, result, receipt, chat, and logout', async t => {
  const root = await folder(t); const file = join(root, 'brief.txt'); await writeFile(file, 'A real client question');
  let credential = null; let polls = 0; let answered = false;
  const store = { get: async () => credential, set: async value => { credential = value; }, remove: async () => { credential = null; } };
  const f = await fakeTank(t, (call, res) => {
    if (call.path.endsWith('/device/code')) return json(res, { device_code: 'tzd1.placeholder', identity_provider: 'trigger-signin', user_code: 'TEST-1234', verification_uri: 'https://auth.tervory.com/device', interval: 1 });
    if (call.path.endsWith('/device/token')) return ++polls === 1 ? json(res, { error: 'authorization_pending' }, 400) : json(res, grant());
    if (call.path.endsWith('/device/revoke')) return json(res, { revoked: true });
    if (call.path.endsWith('/threads')) return json(res, call.method === 'POST' ? { thread_id: 'first-thread' } : answered ? [{ thread_id: 'first-thread', title: 'A real client question', spent_usd: 0.004, saved_usd: 0 }] : []);
    if (call.path.endsWith('/turn')) {
      assert.equal(call.body.model, 'auto');
      if (!answered) assert.deepEqual(call.body.attachments, [{ name: 'brief.txt', text: 'A real client question' }]);
      answered = true; return stream(res, [['token', { text: 'Your result.' }], ['receipt', { rows: [receipt] }], ['done', {}]]);
    }
    assert(call.path.endsWith('/threads/first-thread'));
    return json(res, { messages: [{ role: 'assistant', content: 'Your result.' }], receipts: [receipt], cards: [], steps: [] });
  });
  const io = output(['Continue', '/exit']); io.sleep = async () => {}; io.open = async url => assert.equal(new URL(url).origin, 'https://auth.tervory.com');
  const deps = { store, io, transport: f.transport };
  await assert.rejects(run(['threads'], deps), /Run tervory login/); assert.equal(f.calls.length, 0);
  await run(['login'], deps); assert.equal(polls, 2); assert(credential);
  await run(['threads'], deps); assert.match(io.text, /Threads 0 \| spent 0 \| saved 0/);
  await run(['ask', 'Inspect this', '--file', file], deps);
  await run(['receipts', 'first-thread'], deps); await run(['chat', 'first-thread'], deps); await run(['threads'], deps);
  assert.match(io.text, /Your result/); assert.match(io.text, /cost 0.004/); assert.match(io.text, /ledger recorded-ledger/);
  assert.match(io.text, /assistant: Your result/); assert(io.labels.includes('> '));
  await run(['logout'], deps); assert.equal(credential, null); assert.match(io.text, /credential is revoked/);
  assert(!io.text.includes(token)); assert(!io.text.includes(refresh));
  assert.equal(f.calls.filter(call => call.path.endsWith('/turn')).length, 2);
});

test('gate5 journey: uncertain error has no retry; reopening the thread permits an explicit new action', async t => {
  let attempt = 0;
  const f = await fakeTank(t, (call, res) => {
    if (call.path.endsWith('/turn')) {
      if (++attempt === 1) return json(res, { secret: 'private upstream detail' }, 503);
      return stream(res, [['token', { text: 'Recovered result' }], ['done', {}]]);
    }
    return json(res, { messages: [], receipts: [], steps: [], cards: [] });
  });
  const io = output(['Try again', '/exit']); const deps = { io, store: { get: async () => token }, transport: f.transport };
  await assert.rejects(run(['ask', 'Start', '--thread', 'saved'], deps), /Tank refused the command \(503\)/);
  assert.equal(attempt, 1); assert(!io.text.includes('private upstream detail'));
  await run(['chat', 'saved'], deps); assert.equal(attempt, 2); assert.match(io.text, /Recovered result/);
});

test('gate5 journey: run and build require approval and show the actual terminal result and receipt', async t => {
  let confirmations = 0; let proposals = 0;
  const card = { card_id: 'card-one', tool: 'base.search', status: 'pending', summary: 'Search approved client data' };
  const f = await fakeTank(t, (call, res) => {
    if (call.path.endsWith('/tools')) return json(res, ['base.search']);
    if (call.path.endsWith('/actions') || call.path.endsWith('/build')) { proposals++; return json(res, card); }
    if (call.path.endsWith('/cards/card-one')) { assert.equal(call.body.action, 'confirm'); confirmations++; return json(res, { ...card, status: 'confirmed' }); }
    return json(res, { cards: [{ ...card, status: 'confirmed' }], steps: [{ step_id: card.card_id, status: 'done', actor: 'Base', label: 'Search complete' }], receipts: [{ ...receipt, step_id: card.card_id }] });
  });
  const io = output(['y', 'y']); const deps = { io, transport: f.transport, store: { get: async () => token } };
  await run(['run', 'base', 'search', '--thread', 'saved', '--args', '{"query":"client data"}'], deps);
  await run(['build', 'Requested change', '--thread', 'saved'], deps);
  assert.equal(proposals, 2); assert.equal(confirmations, 2); assert.match(io.text, /Search complete/); assert.match(io.text, /ledger recorded-ledger/);
});

test('gate5 journey: code modes, first edit and receipt, undo, resume and clear use the same real client over HTTP', async t => {
  const root = await folder(t); await writeFile(join(root, 'file.txt'), 'old\n'); let round = 0; let created = 0; const requestIds = new Set();
  const f = await fakeTank(t, (call, res) => {
    if (call.path.endsWith('/threads')) return json(res, { thread_id: 'code-' + ++created });
    if (call.path.endsWith('/code-models')) return json(res, [{ name: 'fixture-model' }]);
    if (call.path.endsWith('/code-sessions')) return json(res, [{ thread_id: 'code-1', title: 'Change file' }]);
    if (call.path.endsWith('/code-sessions/code-1')) return json(res, { thread_id: 'code-1', active: false, cost_usd: 0.012, history: [{ kind: 'user', content: 'Change file' }, { kind: 'assistant', content: 'Done' }] });
    assert(call.path.endsWith('/code-turn'));
    assert.match(call.body.request_id, /^[0-9a-f-]{36}$/); assert(!requestIds.has(call.body.request_id)); requestIds.add(call.body.request_id);
    const plans = [
      { answer: '', requests: [{ name: 'read_file', arguments: { path: 'file.txt' } }] },
      { answer: '', requests: [{ name: 'propose_edit', arguments: { diff: '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n' } }] },
      { answer: 'Done', requests: [] }, { answer: 'Proposed plan', requests: [] },
    ];
    const plan = plans[round++]; assert(plan);
    assert.equal(call.body.mode, round <= 3 ? 'ask' : 'plan');
    return json(res, { ...plan, turn: { model: 'fixture-model', cost_usd: 0.004 }, receipt: { rows: [receipt] } });
  });
  const io = output(['/help', '/model fixture-model', 'Change file', 'y', '/cost', '/undo', 'y', '/mode plan', 'Plan another change', 'n', '/resume code-1', '/clear', '/exit']);
  await run(['code', root], { io, store: { get: async () => token }, transport: f.transport });
  assert.equal(round, 4); assert.equal(created, 2); assert.equal(await readFile(join(root, 'file.txt'), 'utf8'), 'old\n');
  for (const label of ['Apply [y/N] ', 'Undo [y/N] ', 'Approve plan [y/N] ']) assert(io.labels.includes(label), label);
  assert.match(io.text, /Session cost \$0.012000/); assert.match(io.text, /assistant: Done/); assert.match(io.text, /ledger recorded-ledger/);
});

test('gate5 external calls: cancellation stops uncooperative transports and never starts pre-cancelled work', async () => {
  for (const phase of ['headers', 'body']) {
    let calls = 0; const abort = new AbortController();
    const pending = boundedFetch(async () => { calls++; return phase === 'headers' ? new Promise(() => {}) : new Response(new ReadableStream({})); }, 'https://fixture.invalid', { signal: abort.signal }, 1000, response => response.text());
    setTimeout(() => abort.abort(), 15);
    const start = performance.now(); await assert.rejects(pending, { name: 'AbortError' }); assert(performance.now()-start < 500); assert.equal(calls, 1);
    await assert.rejects(boundedFetch(forbid, '', { signal: abort.signal }, 1000, forbid), { name: 'AbortError' });
  }
  const stalled = new Response(new ReadableStream({}));
  await assert.rejects(boundedFetch(async () => stalled, '', {}, 20, response => response.text()), { name: 'DeadlineError' });
});

test('gate5 endless Tank heartbeats and MCP bodies have total deadlines and byte caps', async () => {
  let timer; let closed = false;
  const response = new Response(new ReadableStream({ start(controller) { timer = setInterval(() => controller.enqueue(Buffer.from(': heartbeat\n\n')), 2); }, cancel() { clearInterval(timer); closed = true; } }));
  await assert.rejects(async () => { for await (const ignored of events(response, { idleMs: 100, totalMs: 30 })) void ignored; }, /time limit.*not retried/);
  assert(closed);
  for (const [body, limit, expected] of [[new ReadableStream({}), 100, /deadline/], [new Response('too large').body, 3, /limit/]]) {
    await assert.rejects(new Response(boundedBody(body, limit, 20)).text(), expected);
  }
  await assert.rejects(responseBytes(new Response('12345'), 4), /limit/);
});

test('gate5 MCP connection, body, tool, close failures are bounded with no replay or secret echo', async () => {
  for (const phase of ['headers', 'body', 'call']) {
    let calls = 0; let toolCalls = 0; const io = output(['y', 'y']); const secret = 'placeholder-"private\\credential';
    const client = new MCPClients({ json: async () => ({ blocked: [] }) }, io, {
      timeoutMs: 40, load: async () => ({ remote: { transport: 'http', url: 'https://fixture.invalid/mcp' } }),
      transport: async (_url, init) => {
        calls++;
        if (phase === 'headers') return new Promise(() => {});
        if (phase === 'body') return new Response(new ReadableStream({}), { headers: { 'content-type': 'application/json' } });
        if (init.method === 'GET') return new Response(null, { status: 405 });
        const body = JSON.parse(init.body);
        if (body.id === undefined) return new Response(null, { status: 202 });
        if (body.method === 'tools/call') { toolCalls++; return new Promise(() => {}); }
        return Response.json({ jsonrpc: '2.0', id: body.id, result: body.method === 'initialize' ? { protocolVersion: '2025-03-26', capabilities: { tools: {} }, serverInfo: { name: 'fixture', version: '1' } } : { tools: [{ name: 'echo', inputSchema: { type: 'object' } }] } });
      },
    });
    client.values.add(secret);
    if (phase === 'call') {
      await client.tools('ask', false);
      await assert.rejects(client.call({ server: 'remote', tool: 'echo', arguments: { [secret]: secret } }, 'ask', false), /Nothing was retried/);
      assert.equal(toolCalls, 1); assert(io.text.includes('[redacted]')); assert(!io.text.includes('private'));
      client.clients.get('remote').client.close = () => new Promise(() => {});
    } else { await assert.rejects(client.tools('ask', false), /Nothing was retried/); assert.equal(calls, 1); }
    const start = performance.now(); await client.close(); assert(performance.now()-start < 500);
  }
});

test('gate5 input security: ask, chat and CSV reject links, secret parent aliases, binary and oversized files before credentials or network', async t => {
  const root = await folder(t); await mkdir(join(root, '.ssh')); await writeFile(join(root, '.ssh', 'notes.txt'), 'private'); await symlink(join(root, '.ssh'), join(root, 'alias'));
  await writeFile(join(root, 'file.txt'), 'plain'); await symlink(join(root, 'file.txt'), join(root, 'linked')); await link(join(root, 'file.txt'), join(root, 'hardlink'));
  await writeFile(join(root, 'binary'), Buffer.from([0, 1, 2])); await writeFile(join(root, 'invalid-utf8'), Buffer.from([255]));
  await writeFile(join(root, 'big'), Buffer.alloc(LIMITS.fileBytes+1, 97));
  await writeFile(join(root, 'secret'), 'ghp_' + 'placeholder'.repeat(3));
  for (const file of ['alias/notes.txt', 'linked', 'hardlink', 'binary', 'invalid-utf8', 'big', 'secret']) {
    for (const cmd of ['ask', 'chat']) await assert.rejects(run([cmd, 'question', '--file', join(root, file)], { io: output(), store: { get: forbid }, transport: forbid }), /Invalid file/);
  }
  await assert.rejects(run(['run', 'base', 'batch', '--dry-run', '--file', join(root, 'alias/notes.txt')], { io: output(), store: { get: forbid }, transport: forbid }), /Invalid CSV/);
});

test('gate5 security: path traversal cannot carry a credential outside Command and prompt secrets are redacted', async () => {
  const tank = new Tank(token, forbid);
  for (const path of ['/v1/command/../admin', '/v1/command/%2e%2E/admin', '/v1/command/threads/%2fadmin', '/v1/command/threads/%5cadmin']) await assert.rejects(tank.json(path), /path refused/);
  const secret = 'ghp_' + 'placeholder'.repeat(3); let body;
  await run(['ask', 'Inspect ' + secret, '--thread', 'saved'], { io: output(), store: { get: async () => token }, transport: async (_url, init) => { body = JSON.parse(init.body); return new Response('event: done\ndata: {}\n\n'); } });
  assert(!body.text.includes(secret)); assert.match(body.text, /redacted/);
});

test('gate5 logout never claims a failed remote revocation succeeded', async () => {
  for (const transport of [async () => Response.json({ error: 'private canary' }, { status: 503 }), async () => { throw Error('private canary'); }]) {
    let removed = 0; const io = output();
    await run(['logout'], { io, transport, store: { get: async () => JSON.stringify({ version: 1, region: 'us-east', ...grant() }), remove: async () => { removed++; } } });
    assert.equal(removed, 1); assert.match(io.text, /Server revocation could not be confirmed/); assert(!io.text.includes('private canary')); assert(!io.text.includes('credential is revoked'));
  }
});

test('gate5 update metadata is bounded and does not retry oversized responses', async () => {
  let calls = 0;
  await assert.rejects(latestVersion(async () => { calls++; return new Response(' '.repeat(LIMITS.fileBytes+1)); }), /Update failed/);
  assert.equal(calls, 1);
});

test('gate5 terminal keyboard labels, plain contrast, narrow layout and preview clearing remain usable under large output', async () => {
  for (const settings of [{ tty: true, columns: () => 20 }, { tty: true, env: { NO_COLOR: '' } }, { plain: true }]) {
    const raw = output(['y']); const io = terminalIO(raw, settings);
    assert.equal(await io.prompt('Approve\x1b]52;c;hidden\x07 [y/N] '), 'y');
    assert(raw.labels[0].includes('[y/N]')); assert(!raw.labels[0].includes('hidden'));
    io.write('-removed\n+added\n'); io.status({ model: 'Auto', mode: 'ask', cost_usd: 0, savings_usd: 0 });
    const plain = safe(raw.text); assert.match(plain, /-removed/); assert.match(plain, /\+added/);
    if (settings.columns) assert(plain.split('\n').every(line => line.length <= 20)); else assert(!raw.text.includes('\x1b'));
  }
  let live = ''; const ui = new TerminalUI({ write() {}, live: value => { live += value; }, tty: true, columns: () => 30 });
  const start = performance.now(); ui.preview('visible '.repeat(100000)); const elapsed = performance.now()-start;
  assert(elapsed < 1500, `large preview took ${elapsed} ms`); assert(live.length <= 30);
  ui.preview(''); assert.equal(ui.active, false); assert(live.endsWith('\r\x1b[2K'));
});

test('gate5 keyring operations use private IPC and kill stalled native calls without leaking secrets', async t => {
  const { fork } = await import('node:child_process');
  const { keyringEntry } = await import('../src/keyring.mjs');
  const root = await folder(t); const fixture = join(root, 'keyring-fixture.mjs');
  await writeFile(fixture, `process.once('message', message => { if(message.method==='getPassword')process.send({ok:true,value:'placeholder-value'}); else if(message.method==='deletePassword')process.send({ok:false,value:'private failure canary'}); else setInterval(()=>{},1000); });`);
  const children = []; let launches = 0;
  const entry = keyringEntry('@tervory/cli', 'personal-token', { timeoutMs: 500, launch: (_file, args, options) => {
    launches++; assert.deepEqual(args, []); assert.deepEqual(options.execArgv, []);
    assert.deepEqual(options.stdio, ['ignore', 'ignore', 'ignore', 'ipc']); assert(!JSON.stringify(options).includes('private-value'));
    const child = fork(fixture, args, options); children.push(child); return child;
  } });
  t.after(() => children.forEach(child => child.kill('SIGKILL')));
  assert.equal(await entry.getPassword(), 'placeholder-value');
  await assert.rejects(entry.deletePassword(), error => error.message === 'OS keyring failed or timed out.');
  const start = performance.now(); await assert.rejects(entry.setPassword('private-value'), /timed out/);
  assert(performance.now()-start < 3000); assert.equal(launches, 3); assert(children.every(child => child.killed));
});

test('gate5 real headless entrypoint keeps JSON parseable on a narrow terminal and fails closed on paid work', async t => {
  const { execFile } = await import('node:child_process'); const { promisify } = await import('node:util'); const { fileURLToPath, pathToFileURL } = await import('node:url');
  const execute = promisify(execFile); const root = await folder(t); const loader = join(root, 'offline.mjs');
  await writeFile(loader, `import {registerHooks} from 'node:module';
Object.defineProperty(process.stdout,'isTTY',{value:true});Object.defineProperty(process.stderr,'isTTY',{value:true});Object.defineProperty(process.stdout,'columns',{value:10});
registerHooks({resolve(s,c,next){const r=next(s,c);if(r.url.endsWith('/src/keyring.mjs'))return {shortCircuit:true,url:'data:text/javascript,'+encodeURIComponent('export const keyringEntry=()=>({getPassword:async()=>'+${JSON.stringify(JSON.stringify(token))}+'});')};return r;}});
globalThis.fetch=async(url,init)=>{if(new URL(url).origin!=='https://app.tervory.com')throw Error('Unexpected host');if(url.endsWith('/threads'))return Response.json({thread_id:'headless'});if(!url.endsWith('/code-turn'))throw Error('No confirmation or job may run');return Response.json({answer:'This is a long answer that must remain valid JSON.',requests:[{name:'tervory',arguments:{tool:'paid_steps.approve'}}],turn:{model:'Auto',cost_usd:0},receipt:{rows:[]}});};`);
  const error = await execute(process.execPath, ['--import', pathToFileURL(loader).href, fileURLToPath(new URL('../bin/tervory.mjs', import.meta.url)), '-p', 'Do paid work', '--output', 'json'], { cwd: root, env: { ...process.env, TERVORY_NO_UPDATE_CHECK: '1' } }).then(() => assert.fail('Paid work needs input'), error => error);
  assert.equal(error.code, 2); const result = JSON.parse(error.stdout); assert.equal(result.status, 'needs_input'); assert.equal(result.cost_usd, 0); assert(!error.stdout.includes('\x1b')); assert(!error.stdout.includes(token));
});

test('gate5 remote job failures and unknown outcomes are visible and never resubmitted', async () => {
  const { followThread } = await import('../src/client.mjs');
  for (const status of ['failed', 'unknown', 'cancelled']) {
    const io = output(); let calls = 0;
    await followThread({ json: async () => { calls++; return { cards: [{ card_id: 'first', status }] }; } }, 'saved', { card_id: 'first' }, io);
    assert.equal(calls, 1); assert.match(io.text, new RegExp(status)); assert.match(io.text, /nothing was retried/); assert.match(io.text, /Reopen thread saved/);
  }
});

test('gate5 command JSON and a stream of small events cannot grow without a byte limit', async () => {
  let calls = 0;
  await assert.rejects(new Tank(token, async () => { calls++; return new Response(' '.repeat(2000001)); }).json('/v1/command/threads'), /Tank connection failed/);
  assert.equal(calls, 1);
  const body = new Response(':heartbeat\n\n'.repeat(200000));
  await assert.rejects(async () => { for await (const ignored of events(body)) void ignored; }, /stream exceeds the limit.*not retried/);
});

test('gate5 update cancellation kills a stuck extractor and leaves the installed version intact', async t => {
  const { update } = await import('../src/update.mjs'); const { createHash } = await import('node:crypto'); const { access, readlink } = await import('node:fs/promises');
  const root = await folder(t); const cliDir = join(root, 'cli'); const installed = join(cliDir, '0.1.0'); await mkdir(installed, { recursive: true });
  await writeFile(join(installed, 'RELEASE.json'), JSON.stringify({ version: '0.1.0', platform: 'linux-x64-gnu' })); await symlink('0.1.0', join(cliDir, 'current'));
  const marker = join(root, 'started'); const tar = join(root, 'tar');
  await writeFile(tar, `#!${process.execPath}\nrequire('fs').writeFileSync(${JSON.stringify(marker)},String(process.pid));setInterval(()=>{},1000);\n`, { mode: 0o755 });
  const bytes = Buffer.from('placeholder archive bytes'); const abort = new AbortController(); let calls = 0;
  const pending = update({ root: installed, tar, version: '0.1.1', io: { write() {}, signal: abort.signal }, transport: async url => {
    calls++;
    if (url.endsWith('/manifest.json')) return Response.json({ version: '0.1.1', artifacts: { 'linux-x64-gnu': { file: 'tervory-cli-0.1.1-linux-x64-gnu.tar.gz', size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') } } });
    return new Response(bytes);
  } });
  const rejected = assert.rejects(pending, /archive extraction failed or timed out.*Nothing was changed/);
  const deadline = Date.now()+3000;
  while (true) { try { await access(marker); break; } catch { if (Date.now()>deadline) { abort.abort(); assert.fail('Extractor never started'); } await new Promise(resolve => setTimeout(resolve, 10)); } }
  abort.abort(); await rejected; assert.equal(calls, 2); assert.equal(await readlink(join(cliDir, 'current')), '0.1.0');
  const pid = Number(await readFile(marker, 'utf8')); assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
});

test('gate5 MCP HTTP delivers an SSE tool result before the remote stream closes', async () => {
  let cancelled = false; let calls = 0;
  const client = new MCPClients({ json: async () => ({ blocked: [] }) }, output(['y', 'y']), {
    timeoutMs: 1000, load: async () => ({ remote: { transport: 'http', url: 'https://fixture.invalid/mcp' } }),
    transport: async (_url, init) => {
      if (init.method === 'GET') return new Response(null, { status: 405 });
      const body = JSON.parse(init.body);
      if (body.id === undefined) return new Response(null, { status: 202 });
      const result = body.method === 'initialize' ? { protocolVersion: '2025-03-26', capabilities: { tools: {} }, serverInfo: { name: 'fixture', version: '1' } }
        : body.method === 'tools/list' ? { tools: [{ name: 'echo', inputSchema: { type: 'object' } }] } : { content: [{ type: 'text', text: 'tool result' }] };
      const message = { jsonrpc: '2.0', id: body.id, result };
      if (body.method !== 'tools/call') return Response.json(message);
      calls++;
      return new Response(new ReadableStream({ start(controller) { controller.enqueue(Buffer.from('event: message\ndata: '+JSON.stringify(message)+'\n\n')); }, cancel() { cancelled = true; } }), { headers: { 'content-type': 'text/event-stream' } });
    },
  });
  try {
    await client.tools('ask', false);
    const result = await client.call({ server: 'remote', tool: 'echo', arguments: {} }, 'ask', false);
    assert.equal(result.content[0].text, 'tool result'); assert.equal(calls, 1);
  } finally { await client.close(); }
  assert(cancelled);
});

test('gate5 passive update failure reports a plain notification without failing the command or exposing transport details', async t => {
  const { updateNotice } = await import('../src/update.mjs');
  const root = join(await folder(t), 'cli', '0.1.0'); await mkdir(root, { recursive: true });
  await writeFile(join(root, 'RELEASE.json'), JSON.stringify({ version: '0.1.0', platform: 'linux-x64-gnu' }));
  let failed = 0; let calls = 0;
  const result = await updateNotice({ root, transport: async () => { calls++; throw Error('private transport detail'); }, onFailure: (...args) => { assert.deepEqual(args, []); failed++; } });
  assert.equal(result, null); assert.equal(calls, 1); assert.equal(failed, 1);
});

test('gate5 cancelled MCP startup still closes its local stdio child', async t => {
  const root = await folder(t); const fixture = join(root, 'mcp-pending.mjs'); const marker = join(root, 'pid');
  await writeFile(fixture, `import {writeFileSync} from 'node:fs';writeFileSync(${JSON.stringify(marker)},String(process.pid));process.stdin.resume();setInterval(()=>{},1000);`);
  const abort = new AbortController(); const io = { ...output(['y']), signal: abort.signal };
  // Allow the SDK's documented two-second stdio shutdown grace period.
  const client = new MCPClients({ json: async () => ({ blocked: [] }) }, io, { timeoutMs: 5000, load: async () => ({ local: { transport: 'stdio', command: process.execPath, args: [fixture] } }) });
  let pid;
  try {
    const rejected = assert.rejects(client.tools('ask', false), /failed or timed out/);
    const deadline = Date.now()+3000;
    while (true) { try { pid = Number(await readFile(marker, 'utf8')); break; } catch { if (Date.now()>deadline) assert.fail('MCP child did not start'); await new Promise(resolve => setTimeout(resolve, 10)); } }
    abort.abort(); await rejected; await client.close();
    assert.throws(() => process.kill(pid, 0), { code: 'ESRCH' });
  } finally { abort.abort(); await client.close(); if (pid) try { process.kill(pid, 'SIGKILL'); } catch {} }
});
