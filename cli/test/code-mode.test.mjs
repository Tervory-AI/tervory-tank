import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, mkdir, symlink, rm, copyFile, chmod } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { execFileSync } from 'node:child_process';
import { CodeFolder, LIMITS, redactSecrets, processOutput, applyDiff } from '../src/code-tools.mjs';
import { run } from '../src/client.mjs';

const work = await mkdtemp(join(tmpdir(), 'code-mode-'));
test.after(() => rm(work, { recursive: true, force: true }));
async function folder() {
  const root = await mkdtemp(join(work, 'repo-'));
  execFileSync('git', ['init', '-q', root]);
  await writeFile(join(root, 'file.txt'), 'old\n');
  return CodeFolder.create(root);
}
const io = (answer = 'y', interactive = true) => ({ interactive, write() {}, prompt: async () => answer });
const patch = '--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n';

test('folder must be a git repository; paths and symlinks cannot escape', async () => {
  const nongit = join(work, 'nongit'); await mkdir(nongit);
  await writeFile(join(nongit, '.git'), 'not a git repository');
  await assert.rejects(CodeFolder.create(nongit), /git repository/);
  const f = await folder();
  await writeFile(join(work, 'outside.txt'), 'outside');
  await symlink(work, join(f.root, 'escape'));
  await symlink(join(work, 'outside.txt'), join(f.root, 'link.txt'));
  for (const name of ['../outside.txt', join(work, 'outside.txt'), 'escape/outside.txt', 'escape/new.txt', 'link.txt', '.git/config']) {
    await assert.rejects(f.read(name));
  }
  await assert.rejects(f.edit('../outside.txt', patch, io()));
  assert.equal(await readFile(join(work, 'outside.txt'), 'utf8'), 'outside');
});

test('secret filenames, binary data and oversized reads are refused; listing respects ignore', async () => {
  const f = await folder();
  for (const name of ['.env', '.env.local', 'cert.pem', 'cert.key', 'id_rsa']) {
    await writeFile(join(f.root, name), 'not read');
    await assert.rejects(f.read(name));
  }
  await writeFile(join(f.root, '.gitignore'), 'ignored.txt\n');
  await writeFile(join(f.root, 'ignored.txt'), 'ignored');
  await writeFile(join(f.root, 'binary'), Buffer.from([0, 1, 2]));
  await writeFile(join(f.root, 'huge'), 'a'.repeat(LIMITS.fileBytes + 1));
  await assert.rejects(f.read('binary')); await assert.rejects(f.read('huge'));
  const names = (await f.files()).files;
  assert(names.includes('file.txt')); assert(!names.includes('ignored.txt')); assert(!names.includes('.env'));
});

test('secret patterns are redacted as whole lines before file/search/git/command results leave', async () => {
  const f = await folder();
  const secret = 'ghp_' + 'A'.repeat(24), assigned = 'password=' + 'Z'.repeat(14);
  await writeFile(join(f.root, 'source.txt'), `safe\n${secret}\n${assigned}\n`);
  const result = await f.read('source.txt');
  assert.equal(result.text, 'safe\n[redacted]\n[redacted]\n');
  assert(!JSON.stringify(await f.search('redacted')).includes(secret));
  const output = await processOutput(process.execPath, ['-e', `process.stdout.write(${JSON.stringify(secret + '\n')})`], { cwd: f.root });
  assert.equal(output.output, '[redacted]\n');
  assert.equal(redactSecrets('sk-' + 'a'.repeat(24)), '[redacted]');
});

test('literal/regex search caps at 200 matches and regex execution is bounded', async () => {
  const f = await folder();
  await writeFile(join(f.root, 'source.txt'), 'match\n'.repeat(230));
  assert.equal((await f.search('match')).matches.length, 200);
  assert.equal((await f.search('^match$', true)).matches.length, 200);
  await writeFile(join(f.root, 'source.txt'), 'a'.repeat(10000) + '!');
  await assert.rejects(f.search('(a+)+$', true));
});

test('edits require a prior read and literal y; stale file and approval-time mutations refuse', async () => {
  const f = await folder();
  await assert.rejects(f.edit('file.txt', patch, io()));
  await f.read('file.txt');
  for (const answer of ['N', 'yes', '', null]) assert.equal((await f.edit('file.txt', patch, io(answer))).applied, false);
  assert.equal((await f.edit('file.txt', patch, io('y', false))).applied, false);
  assert.equal(await readFile(join(f.root, 'file.txt'), 'utf8'), 'old\n');
  assert.equal((await f.edit('file.txt', patch, io())).applied, true);
  await writeFile(join(f.root, 'file.txt'), 'changed\n');
  await assert.rejects(f.edit('file.txt', patch, io()));
  await writeFile(join(f.root, 'file.txt'), 'old\n'); await f.read('file.txt');
  await assert.rejects(f.edit('file.txt', patch, { ...io(), prompt: async () => {
    await writeFile(join(f.root, 'file.txt'), 'during approval\n'); return 'y';
  } }));
});

test('new file diff requires a missing-file read; malformed/context-mismatched diffs refuse', async () => {
  const f = await folder();
  const add = '--- /dev/null\n+++ b/test.txt\n@@ -0,0 +1 @@\n+test\n';
  await assert.rejects(f.edit('test.txt', add, io()));
  await f.read('test.txt'); assert.equal((await f.edit('test.txt', add, io())).applied, true);
  assert.equal(await readFile(join(f.root, 'test.txt'), 'utf8'), 'test\n');
  await assert.rejects(applyDiff('different\n', patch, 'file.txt', false, f.root));
  await assert.rejects(applyDiff('old\n', patch.replace('b/file.txt', 'b/../outside.txt'), 'file.txt', false, f.root));
});

test('commands show in full, require y and cannot run non-interactively; cwd and output cap', async () => {
  const f = await folder();
  const command = 'printf done > marker'; const request = { name: 'run_command', arguments: { command } };
  let shown = '';
  for (const terminal of [io('N'), io('yes'), io('y', false)]) {
    terminal.write = text => { shown += text; };
    assert.equal((await f.tool(request, terminal)).ran, false);
  }
  await assert.rejects(readFile(join(f.root, 'marker')));
  assert(shown.includes(command));
  const executed = await f.tool(request, io());
  assert.equal(executed.ran, true); assert.equal(executed.code, 0, executed.output);
  assert.equal(await readFile(join(f.root, 'marker'), 'utf8'), 'done');
  const output = await processOutput(process.execPath, ['-e', 'process.stdout.write("x".repeat(100000))'], { cwd: f.root });
  assert(output.truncated); assert(Buffer.byteLength(output.output) <= LIMITS.outputBytes);
  const timed = await processOutput(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { cwd: f.root, timeoutMs: 80 });
  assert(timed.timed_out);
});

test('fake Tank code loop uses existing region/token, redacts results and never retries a failed turn', async () => {
  const f = await folder();
  const secret = 'ghp_' + 'B'.repeat(24);
  await writeFile(join(f.root, 'file.txt'), `safe\n${secret}\n`);
  const token = 'tv1.za.' + '1'.repeat(32) + '.' + 'x'.repeat(43);
  const received = []; let output = ''; let prompts = ['inspect file', '/exit'];
  await run(['code', f.root], { store: { get: async () => token },
    io: { interactive: true, prompt: async () => prompts.shift(), write: value => { output += value; } },
    transport: async (url, init) => {
      assert.equal(new URL(url).origin, 'https://za.tervory.com');
      assert.equal(init.headers.Authorization, 'Bearer ' + token);
      if (url.endsWith('/threads')) return Response.json({ thread_id: 'thread' });
      received.push(JSON.parse(init.body));
      if (received.length === 1) return Response.json({ answer: '', requests: [{ name: 'read_file', arguments: { path: 'file.txt' } }] });
      assert(!init.body.includes(secret)); assert(init.body.includes('[redacted]'));
      return Response.json({ answer: 'Ready', requests: [], receipt: { rows: [] } });
    } });
  assert.equal(received.length, 2); assert(output.includes('Ready')); assert(!output.includes(secret));
  let calls = 0; prompts = ['inspect file'];
  await assert.rejects(run(['code', f.root], { store: { get: async () => token },
    io: { interactive: true, prompt: async () => prompts.shift(), write() {} },
    transport: async url => { if (url.endsWith('/threads')) return Response.json({ thread_id: 'thread' }); calls++; throw Error('offline'); } }));
  assert.equal(calls, 1);
});

test('list caps at 2000 entries, including repositories with more than 64 KB of names', async () => {
  const f = await folder();
  await mkdir(join(f.root, 'many'));
  await Promise.all(Array.from({ length: 2010 }, (_, i) => writeFile(join(f.root, 'many', `${'long-name-'.repeat(4)}${i}.txt`), '')));
  const result = await f.files();
  assert.equal(result.files.length, 2000); assert(result.truncated);
});

test('approved command cannot read secret paths, outside symlinks or inherited host credentials', async () => {
  const f = await folder();
  await writeFile(join(f.root, '.env'), 'private-file-canary');
  await writeFile(join(work, 'host-private.txt'), 'outside-file-canary');
  await symlink(join(work, 'host-private.txt'), join(f.root, 'outside-link'));
  const result = await f.tool({ name: 'run_command', arguments: {
    command: `cat .env; cat outside-link; cat ${join(work, 'host-private.txt')}; printenv; echo sandbox-ok`,
  } }, io());
  assert.equal(result.code, 0, result.output);
  assert(result.output.includes('sandbox-ok'), result.output);
  assert(!result.output.includes('private-file-canary'));
  assert(!result.output.includes('outside-file-canary'));
  assert(!result.output.includes('TANK_API_KEY='));
  await assert.rejects(f.edit('.env', patch, io()));
});

test('fake Tank can request a missing-file read, explicit edit and explicit test run without a new sign-in', async () => {
  const f = await folder();
  const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'x'.repeat(43);
  const requests = [
    { name: 'read_file', arguments: { path: 'small.test.mjs' } },
    { name: 'propose_edit', arguments: { path: 'small.test.mjs', diff: '--- /dev/null\n+++ b/small.test.mjs\n@@ -0,0 +1,2 @@\n+import test from "node:test";\n+test("small test", () => {});\n' } },
    { name: 'run_command', arguments: { command: 'node --test small.test.mjs' } },
  ];
  let count = 0; let prompts = ['add a small test', 'y', 'y', '/exit']; const results = [];
  await run(['code', f.root], { store: { get: async () => token }, io: {
    interactive: true, prompt: async () => prompts.shift(), write() {},
  }, transport: async (url, init) => {
    if (url.endsWith('/threads')) return Response.json({ thread_id: 'thread' });
    const body = JSON.parse(init.body); results.push(body.tool_results);
    assert.equal(new URL(url).origin, 'https://app.tervory.com');
    return Response.json({ answer: '', requests: count < requests.length ? [requests[count++]] : [] });
  } });
  assert((await readFile(join(f.root, 'small.test.mjs'), 'utf8')).includes('small test'));
  const execution = JSON.parse(results.at(-1).find(r => r.name === 'run_command').output).result;
  assert.equal(execution.code, 0); assert(execution.output.includes('# pass 1'));
});

test('all repository live-key families and assigned-secret lines are redacted', () => {
  // Synthetic values assembled at runtime, never credentials or live data.
  const samples = [
    '-----BEGIN ' + 'PRIVATE KEY-----', 'AKIA' + '0'.repeat(16), 'ghp_' + 'a'.repeat(24),
    'github_pat_' + 'a'.repeat(24), 'xoxb-' + 'a'.repeat(12), 'sk-ant-' + 'a'.repeat(12),
    'sk-' + 'a'.repeat(24), ...['sk', 'pk', 'rk'].map(prefix => prefix + '_live_' + 'a'.repeat(12)),
    'AIza' + 'a'.repeat(30), 'eyJ' + 'a'.repeat(20) + '.' + 'a'.repeat(10) + '.' + 'a'.repeat(10),
    ...['API_KEY', 'secret-key', 'client_secret', 'password', 'passwd', 'access_token', 'auth-token']
      .map(name => name + '=' + 'a'.repeat(14)),
  ];
  for (const value of samples) assert.equal(redactSecrets(value), '[redacted]');
});

test('git status and diff work without exposing secret-file contents', async () => {
  const f = await folder();
  execFileSync('git', ['add', 'file.txt'], { cwd: f.root });
  await writeFile(join(f.root, 'file.txt'), 'changed\n');
  await writeFile(join(f.root, '.e*'), 'old glob file\n');
  await writeFile(join(f.root, '.env'), 'old private file\n');
  execFileSync('git', ['--literal-pathspecs', 'add', '.e*', '.env'], { cwd: f.root });
  await writeFile(join(f.root, '.e*'), 'changed glob file\n');
  await writeFile(join(f.root, '.env'), 'private-git-canary');
  const status = await f.tool({ name: 'git', arguments: { action: 'status' } }, io());
  const diff = await f.tool({ name: 'git', arguments: { action: 'diff' } }, io());
  assert(status.output.includes('file.txt')); assert(diff.output.includes('+changed'));
  assert(diff.output.includes('+changed glob file'));
  assert(!diff.output.includes('private-git-canary'));
  assert(!diff.output.includes('old private file'));
});

test('cancelling at command approval stops execution and any following model turn', async () => {
  const f = await folder(); const controller = new AbortController(); let calls = 0;
  const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'x'.repeat(43);
  await assert.rejects(run(['code', f.root], { store: { get: async () => token },
    io: { interactive: true, signal: controller.signal, write() {}, prompt: async label => {
      if (label.startsWith('Run')) { controller.abort(); return 'y'; }
      return 'run a test';
    } },
    transport: async url => {
      if (url.endsWith('/threads')) return Response.json({ thread_id: 'thread' });
      calls++;
      return Response.json({ answer: '', requests: [{ name: 'run_command', arguments: { command: 'printf wrong > cancel-marker' } }] });
    },
  }), /cancelled/);
  assert.equal(calls, 1);
  await assert.rejects(readFile(join(f.root, 'cancel-marker')));
});

test('git read tools cannot execute repository clean/process filters without approval', async () => {
  const f = await folder();
  const sub = join(f.root, 'sub'); await mkdir(sub);
  execFileSync('git', ['init', '-q', sub]);
  await writeFile(join(sub, 'file.txt'), 'sub original\n');
  execFileSync('git', ['add', 'file.txt'], { cwd: sub });
  execFileSync('git', ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'sub'], { cwd: sub });
  await writeFile(join(f.root, '.gitmodules'), '[submodule "sub"]\npath = sub\nurl = ./sub\n');
  execFileSync('git', ['add', 'sub', '.gitmodules'], { cwd: f.root, stdio: 'pipe' });
  execFileSync('git', ['-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'parent'], { cwd: f.root });
  execFileSync('git', ['config', 'filter.subguard.clean', 'sh -c "printf wrong > sub-filter-marker; cat"'], { cwd: sub });
  await writeFile(join(sub, '.gitattributes'), 'file.txt filter=subguard\n');
  await writeFile(join(sub, 'file.txt'), 'sub modified\n');
  // Positive control: a normal status must execute this exact fixture's
  // submodule filter. Size changes alone can skip it and give false assurance.
  execFileSync('git', ['--literal-pathspecs', 'status', '--short', '--', '.'], { cwd: f.root });
  assert.equal(await readFile(join(sub, 'sub-filter-marker'), 'utf8'), 'wrong');
  await rm(join(sub, 'sub-filter-marker'));
  execFileSync('git', ['add', 'file.txt'], { cwd: f.root });
  execFileSync('git', ['config', 'filter.guard.clean', 'sh -c "printf wrong > filter-marker; cat"'], { cwd: f.root });
  await writeFile(join(f.root, '.gitattributes'), 'file.txt filter=guard\n');
  await writeFile(join(f.root, 'file.txt'), 'changed\n');
  const diff = await f.tool({ name: 'git', arguments: { action: 'diff' } }, io());
  await f.tool({ name: 'git', arguments: { action: 'status' } }, io());
  assert(diff.output.includes('+changed'));
  await assert.rejects(readFile(join(f.root, 'filter-marker')));
  await assert.rejects(readFile(join(sub, 'sub-filter-marker')));
});


test('missing files and approval-time ancestor swaps cannot create Git hooks', async () => {
  const f = await folder();
  const add = '--- /dev/null\n+++ b/lnk/hooks/post-checkout\n@@ -0,0 +1 @@\n+wrong\n';
  await symlink('.git', join(f.root, 'lnk'));
  await assert.rejects(f.read('lnk/hooks/post-checkout'));
  await assert.rejects(f.edit('lnk/hooks/post-checkout', add, io()));
  await assert.rejects(readFile(join(f.root, '.git/hooks/post-checkout')));
  await rm(join(f.root, 'lnk'));
  await mkdir(join(f.root, 'lnk/hooks'), { recursive: true });
  await f.read('lnk/hooks/post-checkout');
  await assert.rejects(f.edit('lnk/hooks/post-checkout', add, { ...io(), prompt: async () => {
    await rm(join(f.root, 'lnk'), { recursive: true });
    await symlink('.git', join(f.root, 'lnk')); return 'y';
  } }));
  await assert.rejects(readFile(join(f.root, '.git/hooks/post-checkout')));
  await mkdir(join(f.root, '.GIT/hooks'), { recursive: true });
  await assert.rejects(f.read('.GIT/hooks/new'));
});

test('Git reads remain pinned when an approved command creates a nested repository', async () => {
  const f = await folder();
  await mkdir(join(f.root, 'selected'));
  await writeFile(join(f.root, 'selected/original.txt'), 'parent tracked\n');
  execFileSync('git', ['add', 'selected/original.txt'], { cwd: f.root });
  const selected = await CodeFolder.create(join(f.root, 'selected'));
  const initialized = await selected.tool({ name: 'run_command', arguments: { command: 'git init -q' } }, io());
  assert.equal(initialized.code, 0, initialized.output);
  await writeFile(join(selected.root, 'original.txt'), 'changed parent\n');
  const status = await selected.tool({ name: 'git', arguments: { action: 'status' } }, io());
  assert(status.output.includes('AM original.txt'), status.output);
  assert((await selected.diff()).output.includes('+changed parent'));
  assert((await selected.files()).files.includes('original.txt'));
});

test('external Node runtime is read-only, named before approval and cannot expose HOME', async () => {
  const f = await folder();
  const runtime = await mkdtemp(join(work, 'runtime-'));
  await mkdir(join(runtime, 'bin'));
  const node = join(runtime, 'bin/node'); await copyFile(process.execPath, node);
  await writeFile(join(runtime, 'bin/.npmrc'), 'neighbor-file-canary');
  await writeFile(join(f.root, 'real.test.mjs'), 'import test from "node:test"; test("external runner", () => {});\n');
  let shown = '';
  const result = await f.tool({ name: 'run_command', arguments: { command: `${node} --test real.test.mjs` } }, {
    ...io(), write: value => { shown += value; }, prompt: async () => { assert(shown.includes(node)); return 'y'; },
  });
  assert.equal(result.code, 0, result.output); assert(result.output.includes('# pass 1'));
  const neighbor = await f.tool({ name: 'run_command', arguments: { command: `${node} -e 'console.log("runner-ok"); try { console.log(require("fs").readFileSync("${runtime}/bin/.npmrc", "utf8")); } catch {}'` } }, io());
  assert.equal(neighbor.code, 0, neighbor.output); assert(neighbor.output.includes('runner-ok'));
  assert(!neighbor.output.includes('neighbor-file-canary'));
  const write = await f.tool({ name: 'run_command', arguments: { command: `${node} -e 'require("fs").writeFileSync("${node}", "wrong")'` } }, io());
  assert.notEqual(write.code, 0); assert.match(write.output, /EROFS|[Rr]ead-only/); await assert.rejects(readFile(join(runtime, 'bin/wrong')));
});

test('session history is bounded, redacted and transient; continuation rounds share one prompt id', async () => {
  const f = await folder();
  const token = 'tv1.za.' + '1'.repeat(32) + '.' + 'x'.repeat(43);
  const secret = 'ghp_' + 'C'.repeat(24);
  const received = []; const prompts = ['first prompt', `second prompt ${secret}`, '/exit'];
  await run(['code', f.root], { store: { get: async () => token }, io: {
    interactive: true, prompt: async () => prompts.shift(), write() {},
  }, transport: async (url, init) => {
    if (url.endsWith('/threads')) return Response.json({ thread_id: 'thread' });
    const body = JSON.parse(init.body); received.push(body);
    assert(!init.body.includes(secret));
    return Response.json({ answer: 'earlier answer', requests: received.length < 3 ? [{ name: 'read_file', arguments: { path: 'file.txt' } }] : [] });
  } });
  assert.deepEqual(received.map(r => r.continuation), [false, true, true, false]);
  assert.equal(new Set(received.slice(0, 3).map(r => r.prompt_id)).size, 1);
  assert.notEqual(received[0].prompt_id, received[3].prompt_id);
  const history = received[3].history;
  assert(history.some(h => h.kind === 'user' && h.content === 'first prompt'));
  assert(history.some(h => h.kind === 'assistant' && h.content === 'earlier answer'));
  assert(history.some(h => h.kind === 'tool' && h.content.includes('read_file') && h.content.includes('file.txt')));
  assert.equal(received[3].text, '[redacted]');
  let next = 0; let lastHistory;
  await run(['code', f.root], { store: { get: async () => token }, io: {
    interactive: true, prompt: async () => next < 60 ? `turn${next++}` : '/exit', write() {},
  }, transport: async (url, init) => {
    if (url.endsWith('/threads')) return Response.json({ thread_id: 'bounded-thread' });
    const body = JSON.parse(init.body); lastHistory = body.history;
    assert(body.history.length <= 40);
    assert(body.history.reduce((n, item) => n + Buffer.byteLength(item.content), 0) <= 200000);
    return Response.json({ answer: 'a'.repeat(39000), requests: [] });
  } });
  assert(!lastHistory.some(item => item.content === 'turn0'));
  assert(lastHistory.some(item => item.content === 'turn58'));
});


test('external Node intermediate links do not expose their host directory', async () => {
  const f = await folder();
  const install = await mkdtemp(join(work, 'node-install-'));
  const middle = await mkdtemp(join(work, 'node-links-'));
  await mkdir(join(install, 'bin'));
  await symlink(process.execPath, join(middle, 'node'));
  await symlink(join(middle, 'node'), join(install, 'bin/node'));
  await writeFile(join(middle, 'private.txt'), 'unmounted-directory-canary');
  const command = `${join(install, 'bin/node')} -e 'console.log("runtime-ok"); try { console.log(require("fs").readFileSync("${middle}/private.txt", "utf8")); } catch {}'`;
  const result = await f.tool({ name: 'run_command', arguments: { command } }, io());
  assert.equal(result.code, 0, result.output);
  assert(result.output.includes('runtime-ok'));
  assert(!result.output.includes('unmounted-directory-canary'));
});


test('external runtime rejects directories, nonexecutables and their symlinks before approval', async () => {
  const f = await folder(); const outside = await mkdtemp(join(work, 'other-projects-'));
  await mkdir(join(outside, 'client-a/.aws'), { recursive: true });
  await writeFile(join(outside, 'client-a/.npmrc'), 'unrelated-npm-canary');
  await writeFile(join(outside, 'client-a/.aws/credentials'), 'unrelated-aws-canary');
  let prompts = 0;
  for (const name of ['node', 'python', 'pytest']) {
    const directory = join(outside, name); await mkdir(directory);
    await assert.rejects(f.tool({ name: 'run_command', arguments: { command: `'${directory}' --version; cat '${outside}/client-a/.npmrc'` } }, {
      ...io(), prompt: async () => { prompts++; return 'y'; },
    }));
    const aliases = join(outside, name + '-links'); await mkdir(aliases);
    await symlink(directory, join(aliases, name));
    await assert.rejects(f.prepareCommand(`'${join(aliases, name)}' --version`));
  }
  const bin = join(outside, 'nonexec'); await mkdir(bin);
  const file = join(bin, 'node'); await writeFile(file, 'not executable'); await chmod(file, 0o600);
  await symlink(file, join(bin, 'python'));
  await assert.rejects(f.prepareCommand(`'${file}' --version`));
  await assert.rejects(f.prepareCommand(`'${join(bin, 'python')}' --version`));
  assert.equal(prompts, 0);
});

test('external runtimes refuse pip-user and uv launchers without exposing .local user data', async () => {
  const f = await folder(); const home = await mkdtemp(join(work, 'user-home-'));
  const local = join(home, '.local'); await mkdir(join(local, 'bin'), { recursive: true });
  await mkdir(join(local, 'share/python_keyring'), { recursive: true });
  await mkdir(join(local, 'share/fish'), { recursive: true });
  await writeFile(join(local, 'share/python_keyring/keyring_pass.cfg'), 'unrelated-keyring-canary');
  await writeFile(join(local, 'share/fish/fish_history'), 'unrelated-history-canary');
  const python = join(local, 'bin/python3'); await symlink(process.execPath, python);
  const pytest = join(local, 'bin/pytest'); await writeFile(pytest, `#!${python}\n`); await chmod(pytest, 0o700);
  // Include plausible pip-user libraries: they still cannot authorize a .local bind.
  await mkdir(join(local, 'lib/python3.12/site-packages'), { recursive: true });
  for (const runner of [python, pytest]) {
    let prompts = 0;
    await assert.rejects(f.tool({ name: 'run_command', arguments: {
      command: `'${runner}' --version; cat '${local}/share/python_keyring/keyring_pass.cfg' '${local}/share/fish/fish_history'`,
    } }, { ...io(), prompt: async () => { prompts++; return 'y'; } }));
    assert.equal(prompts, 0);
  }
});
