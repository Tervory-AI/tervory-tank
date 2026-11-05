import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { codeSession } from '../src/code-mode.mjs';
import { run, safe, receiptLines } from '../src/client.mjs';

const patch = '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n';
const request = (name, args = {}) => ({ name, arguments: args });
const response = (requests = [], answer = '', cost = 0.002) => ({ answer, requests, turn: { model: 'placeholder-model', cost_usd: cost }, receipt: { rows: [{ cost_usd: cost }] } });
async function fixture(t, prompts, plan) {
  const root = await mkdtemp(join(tmpdir(), 'opli-agent-'));
  execFileSync('git', ['init', '-q', root]); await writeFile(join(root, 'file.txt'), 'old\n');
  t.after(() => rm(root, { recursive: true, force: true }));
  const f = { root, calls: [], approvals: [], output: '', created: 0 };
  f.io = { interactive: true, write: value => { f.output += value; }, prompt: async label => { f.approvals.push(label); return prompts.shift() ?? null; } };
  f.tank = { json: async (path, body) => {
    f.calls.push({ path, body });
    if (path === '/v1/command/threads') return { thread_id: `placeholder-thread-${++f.created}` };
    if (path.endsWith('/code-turn')) return plan(body, f);
    if (f.extra) return f.extra(path, body);
    throw new Error('Unexpected fixture request: ' + path);
  } };
  f.run = options => codeSession(f.tank, root, 'auto', f.io, receiptLines, safe, options);
  return f;
}

test('agent Auto-edit loops through reads search edits and approved sandbox commands with undo intact', async t => {
  let round = 0;
  const f = await fixture(t, ['/mode auto-edit', 'change and test', 'y', '/undo', 'y', '/exit'], body => {
    assert.equal(body.mode, 'auto-edit');
    return [response([request('read_file', { path: 'file.txt' })]), response([request('search', { pattern: 'old' })]),
      response([request('propose_edit', { diff: patch })]), response([request('run_command', { command: 'echo placeholder-ok' })]), response([], 'done')][round++];
  });
  await f.run();
  assert.equal(round, 5); assert.equal(await readFile(join(f.root, 'file.txt'), 'utf8'), 'old\n');
  assert(!f.approvals.includes('Apply [y/N] ')); assert(f.approvals.includes('Run [y/N] ')); assert(f.approvals.includes('Undo [y/N] '));
  assert(f.output.includes('placeholder-ok'));
  const calls = f.calls.filter(c => c.path.endsWith('/code-turn'));
  assert.equal(new Set(calls.map(c => c.body.prompt_id)).size, 1);
  assert.equal(calls[4].body.continuation, true);
});

test('agent Ask and Auto-edit command denials stop without another model call', async t => {
  for (const mode of ['ask', 'auto-edit']) {
    let round = 0;
    const f = await fixture(t, [`/mode ${mode}`, 'execute', 'n', '/exit'], () => { round++; return response([request('run_command', { command: 'touch refused.txt' })]); });
    const result = await f.run(); assert.equal(round, 1); assert.equal(result.status, 'needs_input');
    await assert.rejects(readFile(join(f.root, 'refused.txt')));
  }
  let round = 0;
  const f = await fixture(t, ['edit', 'n', '/exit'], () => round++ ? response([request('propose_edit', { diff: patch })]) : response([request('read_file', { path: 'file.txt' })]));
  await f.run(); assert.equal(round, 2); assert.equal(await readFile(join(f.root, 'file.txt'), 'utf8'), 'old\n');
});

test('agent Plan stays read only and approval starts an Ask turn with separate edit approval', async t => {
  let round = 0;
  const f = await fixture(t, ['/mode plan', 'plan change', 'y', 'y', '/mode plan', '/undo', '/exit'], body => {
    const cases = [response([request('read_file', { path: 'file.txt' })]), response([], 'Change old to new.'),
      response([request('read_file', { path: 'file.txt' })]), response([request('propose_edit', { diff: patch })]), response([], 'done')];
    assert.equal(body.mode, round < 2 ? 'plan' : 'ask'); return cases[round++];
  });
  await f.run(); assert.equal(round, 5); assert.equal(await readFile(join(f.root, 'file.txt'), 'utf8'), 'new\n');
  assert(f.approvals.includes('Approve plan [y/N] ')); assert(f.approvals.includes('Apply [y/N] '));
  assert(!f.approvals.includes('Undo [y/N] ')); assert(f.output.includes('Switch mode before undo.'));
  for (const name of ['propose_edit', 'run_command', 'tervory']) {
    const blocked = await fixture(t, ['/mode plan', 'inspect', '/exit'], () => response([request(name, { diff: patch, command: 'touch forbidden', tool: 'paid_steps.approve' })]));
    assert.equal((await blocked.run()).status, 'needs_input');
    assert.deepEqual(blocked.approvals, ['> ', '> ', '> ']);
  }
});

test('agent model selector uses the server roster and shows each turn model and accumulated cost', async t => {
  const f = await fixture(t, ['/model forbidden', '/model placeholder-allowed', 'first', '/model auto', 'second', '/cost', '/exit'], body => {
    assert(['auto', 'placeholder-allowed'].includes(body.model)); return response([], 'done');
  });
  f.extra = async path => { assert.equal(path, '/v1/command/code-models'); return [{ name: 'placeholder-allowed', input_usd_per_m: 1, output_usd_per_m: 2 }]; };
  const result = await f.run();
  assert.deepEqual(f.calls.filter(c => c.path.endsWith('/code-turn')).map(c => c.body.model), ['placeholder-allowed', 'auto']);
  assert.equal(result.cost_usd, 0.004); assert(f.output.includes('Model not available.')); assert(f.output.includes('Model placeholder-model | cost $0.002000')); assert(f.output.includes('Session cost $0.004000'));
});

test('agent resume lists owned sessions reopens redacted history and defaults to Ask and Auto', async t => {
  const secret = 'ghp_' + 'placeholder'.repeat(3);
  const f = await fixture(t, ['placeholder-saved', 'continue', '/resume placeholder-other', 'again', '/exit'], body => {
    assert.equal(body.mode, 'ask'); assert.equal(body.model, 'auto'); assert(body.history.some(h => h.content.includes('earlier')));
    assert(!JSON.stringify(body).includes(secret)); return response([], 'done');
  });
  f.extra = async path => path === '/v1/command/code-sessions'
    ? [{ thread_id: 'placeholder-saved', title: 'earlier' }, { thread_id: 'placeholder-other', title: 'other' }]
    : { thread_id: path.split('/').at(-1), active: false, history: [{ kind: 'user', content: `earlier\n${secret}` }, { kind: 'tool', content: 'must not restore' }], cost_usd: 0.1 };
  await f.run({ resume: true }); assert.equal(f.created, 0); assert(!f.output.includes(secret));
  assert.deepEqual(f.calls.filter(c => c.path.endsWith('/code-turn')).map(c => c.path), ['/v1/command/threads/placeholder-saved/code-turn', '/v1/command/threads/placeholder-other/code-turn']);
});

test('agent help clear cost and exit stay local and clear starts a fresh thread', async t => {
  const f = await fixture(t, ['first', '/help', '/cost', '/clear', 'second', '/exit'], body => { assert(!body.history.length); return response([], 'answer'); });
  await f.run(); assert.equal(f.created, 2); assert(f.output.includes('/resume')); assert(f.output.includes('/undo')); assert(f.output.includes('Session cost $0.002000'));
  assert.equal(f.calls.filter(c => c.path.endsWith('/code-turn')).length, 2);
});

const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'placeholder'.padEnd(43, 'x');
async function headless(root, plan, format = 'json') {
  const before = process.cwd(); const calls = []; let output = ''; let error; let result;
  try {
    process.chdir(root);
    result = await run(['-p', 'inspect the folder', '--output', format], { store: { get: async () => token },
      io: { interactive: true, prompt: async () => assert.fail('Headless must never ask or auto-confirm'), write: text => { output += text; } },
      transport: async (url, init) => {
        calls.push({ url, body: init.body });
        if (url.endsWith('/threads')) return Response.json({ thread_id: 'placeholder-headless' });
        assert(url.endsWith('/code-turn')); return Response.json(await plan(JSON.parse(init.body)));
      } });
  } catch (value) { error = value; } finally { process.chdir(before); }
  return { output, error, calls, result };
}

test('agent headless json and text run read-only loops with one clean redacted result', async t => {
  const f = await fixture(t, [], () => {}); let count = 0;
  const secret = 'ghp_' + 'placeholder'.repeat(3);
  await writeFile(join(f.root, 'input.txt'), `safe\n${secret}\n`);
  const result = await headless(f.root, body => {
    if (!count++) return response([request('read_file', { path: 'input.txt' })]);
    assert(!JSON.stringify(body).includes(secret)); return response([], `done\n${secret}`);
  });
  assert.ifError(result.error); const json = JSON.parse(result.output); assert.equal(json.status, 'completed'); assert.equal(json.turns.length, 2); assert.equal(result.output.trim().split('\n').length, 1); assert(!result.output.includes(secret));
  const text = await headless(f.root, () => response([], 'done'), 'text'); assert.ifError(text.error); assert(text.output.includes('Status completed')); assert(text.output.includes('done')); assert(text.output.includes('Model placeholder-model | cost $0.002000'));
});

test('agent headless refuses paid steps destructive commands and edits without confirmation', async t => {
  const f = await fixture(t, [], () => {});
  for (const req of [request('run_command', { command: 'rm file.txt' }), request('propose_edit', { diff: patch }), request('tervory', { tool: 'paid_steps.approve', arguments: {} })]) {
    const result = await headless(f.root, () => ({ ...response([req]), cards: [{ card_id: 'placeholder-paid', status: 'pending', tool: 'paid_steps.approve' }] }));
    assert.equal(result.error.exitCode, 2); assert.equal(JSON.parse(result.output).status, 'needs_input');
    assert.equal(result.calls.length, 2); assert.equal(await readFile(join(f.root, 'file.txt'), 'utf8'), 'old\n');
  }
});

test('agent resume CLI flag and invalid options fail closed', async t => {
  const f = await fixture(t, [], () => {}); let asked = false;
  const before = process.cwd();
  try {
    process.chdir(f.root);
    await run(['code', '--resume'], { store: { get: async () => token }, io: { interactive: true, write() {}, prompt: async () => null }, transport: async url => { assert(url.endsWith('/code-sessions')); asked = true; return Response.json([]); } });
    assert(asked);
    for (const args of [['code', '--output', 'json'], ['-p', 'task', '--output', 'xml'], ['-p', 'task', '--resume']]) {
      await assert.rejects(run(args, { store: { get: async () => assert.fail() }, io: f.io }), /Invalid/);
    }
  } finally { process.chdir(before); }
});
