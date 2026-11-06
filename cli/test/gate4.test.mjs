import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import { promisify } from 'node:util';
import { mkdtemp, writeFile, readFile, readdir, mkdir, rm, symlink, cp, access } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { run, receiptLines, safe } from '../src/client.mjs';
import { codeSession } from '../src/code-mode.mjs';
import { CodeFolder } from '../src/code-tools.mjs';
import { MCPClients, loadMCP } from '../src/mcp.mjs';
import { gitSlash } from '../src/code-git.mjs';
import { terminalIO } from '../src/terminal.mjs';
import { ConfigurationError, LOGIN_SETTING, missingSetting } from '../src/configuration.mjs';
import { signRelease } from '../scripts/sign-release.mjs';

const execute = promisify(execFile);
const cli = fileURLToPath(new URL('..', import.meta.url));
const token = 'tv1.us-east.' + '1'.repeat(32) + '.' + 'placeholder'.padEnd(43, 'x');
const forbidden = () => assert.fail('No credential, network or execution operation is allowed');
function output(answers = []) {
  const io = { interactive: true, text: '', write(text) { this.text += text; }, prompt: async () => answers.shift() ?? null };
  return io;
}
async function folder(t) {
  const root = await mkdtemp(join(tmpdir(), 'opli-day-zero-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  execFileSync('git', ['init', '-q', root]);
  return root;
}

test('gate4 empty thread model and receipt lists keep zero shapes and name the first action', async () => {
  for (const [args, response, expected] of [
    [['threads'], [], /Threads 0 \| spent 0 \| saved 0\nFirst action: run tervory chat/],
    [['models'], [], /Models 0 \| in —\/M \| out —\/M\nFirst action: ask your administrator/],
    [['receipts', 'placeholder-thread'], { receipts: [] }, /Receipts 0 \| cost — \| baseline — \| saved —\nFirst action: send a message/],
  ]) {
    const io = output(); const calls = [];
    await run(args, { io, store: { get: async () => token }, transport: async (url, init) => { calls.push(init.method); return Response.json(response); } });
    assert.match(io.text, expected); assert.deepEqual(calls, ['GET']);
    assert.doesNotMatch(io.text, /sample|demo|NaN|undefined|fake|placeholder/i);
  }
  const io = output(); const calls = [];
  await run(['receipts', 'placeholder-task'], { io, store: { get: async () => token }, transport: async (url, init) => {
    calls.push([new URL(url).pathname, init.method]);
    return url.includes('/threads/') ? new Response(null, { status: 404 }) : Response.json({ rows: [] });
  } });
  assert.equal(calls.length, 2); assert(calls.every(([, method]) => method === 'GET'));
  assert.match(io.text, /Receipts 0/);
});

test('gate4 recorded receipt numbers remain exact and an in-flight receipt stays pending', () => {
  assert.deepEqual(receiptLines({}), ['Receipt pending']);
  const lines = receiptLines({ rows: [{ cost_usd: '0.000028', baseline_cost_usd: null, saved_usd: '0', ledger_id: 'placeholder-ledger' }] }, { empty: true }).join('\n');
  assert.match(lines, /cost 0\.000028/); assert.match(lines, /would have cost pending/); assert.match(lines, /saved 0/);
  assert.doesNotMatch(lines, /First action|Receipts 0|NaN|undefined/);
});

test('gate4 new and resumed empty chats show no invented messages steps or receipts', async () => {
  for (const args of [['chat'], ['chat', 'placeholder-thread']]) {
    const io = output(['/exit']); let turns = 0;
    await run(args, { io, store: { get: async () => token }, transport: async (url, init) => {
      if (url.endsWith('/turn')) { turns++; assert.fail('No message was entered'); }
      return Response.json(init.method === 'POST' ? { thread_id: 'placeholder-thread' } : { messages: [], steps: [], cards: [], receipts: [] });
    } });
    assert.match(io.text, /Messages 0 \| steps 0\nFirst action: enter a message/);
    assert.equal(turns, 0); assert.doesNotMatch(io.text, /sample|demo|assistant:|NaN|undefined/);
  }
});

test('gate4 a new code session has zero cost empty selectors and local first actions', async t => {
  const root = await folder(t); const shown = output(['/cost', '/steps', '/resume', '/model auto', '/branch', '/commit', '/exit']);
  const io = terminalIO({ ...shown, write: text => shown.write(text) }, { plain: true });
  const calls = [];
  const tank = { json: async path => { calls.push(path); return path === '/v1/command/threads' ? { thread_id: 'placeholder-thread' } : []; } };
  const result = await codeSession(tank, root, 'auto', io, receiptLines, safe);
  assert.equal(result.cost_usd, 0);
  for (const text of ['Messages 0 | tool steps 0', 'Session cost $0.000000', 'Tool steps 0', 'Code sessions 0', 'Models 0', 'Branches 0', 'Staged files 0']) assert(shown.text.includes(text), text);
  assert.match(shown.text, /cost \$0 \| saved vs Auto \$0/);
  assert.equal(calls.filter(path => path.endsWith('/code-turn')).length, 0);
  assert.doesNotMatch(shown.text, /sample|demo|NaN|undefined/i);
  const resume = output();
  const cancelled = await codeSession(tank, root, 'auto', resume, receiptLines, safe, { resume: true });
  assert.equal(cancelled.status, 'cancelled'); assert.match(resume.text, /Code sessions 0\nFirst action: run tervory code/);
});

test('gate4 empty file search and step views remain accessible and reset with the session', () => {
  for (const settings of [{ plain: true }, { tty: true, columns: () => 22 }, { tty: true, env: { NO_COLOR: '1' } }]) {
    let text = ''; const io = terminalIO({ write: value => { text += value; }, prompt: async () => null }, settings);
    io.tool({ phase: 'start', name: 'list_files' }); io.tool({ phase: 'end', result: { files: [], truncated: false } });
    io.tool({ phase: 'start', name: 'search' }); io.tool({ phase: 'end', result: { matches: [], truncated: false } });
    const flat = safe(text).replaceAll('\n', '');
    assert(flat.includes('Files 0')); assert(flat.includes('Matches 0')); assert.equal((flat.match(/First action:/g) ?? []).length, 2);
    text = ''; io.reset(); io.steps(''); assert(safe(text).replaceAll('\n', '').includes('Tool steps 0'));
    assert(!text.includes('Tool 1:'));
  }
});

test('gate4 missing login and keyring settings stop before requests and remain named in headless JSON', async () => {
  for (const args of [['threads'], ['run', 'base', 'batch'], ['code'], ['build', 'change']]) {
    await assert.rejects(run(args, { io: output(), store: { get: async () => null }, transport: forbidden }), error => error instanceof ConfigurationError && error.settings[0] === LOGIN_SETTING && error.message.includes('Run tervory login'));
  }
  for (const args of [['threads'], ['login']]) {
    await assert.rejects(run(args, { io: output(), store: { get: async () => { throw new Error('placeholder private backend error'); } }, transport: forbidden }), error => error.message.includes(LOGIN_SETTING) && !error.message.includes('placeholder private'));
  }
  const io = output();
  await assert.rejects(run(['-p', 'inspect', '--output', 'json'], { io, store: { get: async () => null }, transport: forbidden }), error => error.exitCode === 1 && error.reported);
  const result = JSON.parse(io.text); assert.deepEqual(result.missing_settings, [LOGIN_SETTING]);
  assert.equal(result.status, 'error'); assert.deepEqual(result.turns, []); assert.match(result.answer, /Run tervory login/);
  for (const args of [[], ['help'], ['version']]) await run(args, { io: output(), env: {}, store: { get: forbidden }, transport: forbidden });
});

test('gate4 missing MCP configuration names the field and an absent optional file stays empty', async t => {
  const root = await folder(t); const path = join(root, 'mcp.json');
  assert.deepEqual(await loadMCP(path), {});
  for (const [config, field] of [[{}, 'servers'], [{ servers: { local: {} } }, 'transport'], [{ servers: { local: { transport: 'stdio' } } }, 'command'], [{ servers: { local: { transport: 'http' } } }, 'url']]) {
    await writeFile(path, JSON.stringify(config));
    await assert.rejects(loadMCP(path), error => error instanceof ConfigurationError && error.settings[0].endsWith(field) && error.message.includes('mcp.json'));
  }
  await writeFile(path, JSON.stringify({ servers: {} })); assert.deepEqual(await loadMCP(path), {});
});

test('gate4 missing MCP keyring entries start neither HTTP nor stdio and do not exit code mode', async t => {
  const root = await folder(t); const marker = join(root, 'must-not-start');
  for (const config of [
    { transport: 'http', url: 'https://placeholder.invalid/mcp', headers: { Authorization: { keyring: 'credential' } } },
    { transport: 'stdio', command: process.execPath, args: ['-e', `require('fs').writeFileSync(${JSON.stringify(marker)},'started')`], env: { PLACEHOLDER_MCP_SECRET: { keyring: 'credential' } } },
  ]) {
    for (const unavailable of [false, true]) {
      const io = output(['y']);
      const clients = new MCPClients({ json: async () => ({ blocked: [] }) }, io, { load: async () => ({ local: config }), keyring: async () => ({ getPassword: () => { if (unavailable) throw new Error('placeholder private'); return null; } }), transport: forbidden });
      await assert.rejects(clients.tools('auto-edit', false), error => error instanceof ConfigurationError && error.message.includes('@tervory/cli/mcp/local/credential') && !error.message.includes('placeholder private'));
      assert.equal(clients.clients.size, 0); await clients.close(); await assert.rejects(access(marker));
    }
  }
  const io = output(['use my server', '/help', '/exit']); let closed = false;
  const result = await codeSession({ json: async path => { assert(path.endsWith('/threads')); return { thread_id: 'placeholder-thread' }; } }, root, 'auto', io, receiptLines, safe,
    { createMCP: () => ({ tools: async () => { throw missingSetting('@tervory/cli/mcp/local/credential', 'Run tervory mcp secret local credential.'); }, close: async () => { closed = true; } }) });
  assert.equal(result.status, 'needs_input'); assert(closed); assert.match(io.text, /Missing setting @tervory\/cli\/mcp\/local\/credential/); assert(io.text.includes('/help'));
});

test('gate4 missing gh authentication cannot push or create a pull request', async t => {
  const root = await folder(t); const calls = [];
  await assert.rejects(gitSlash('/pr', '', await CodeFolder.create(root), output(['y', 'y']), 'ask', { process: async (command, args) => { calls.push([command, ...args]); throw new Error('placeholder private'); } }), error => error instanceof ConfigurationError && /gh auth login/.test(error.message));
  assert.deepEqual(calls, [['gh', 'auth', 'status']]);
});

test('gate4 run dry-run validates real input through the live parser without credentials or effects', async t => {
  const root = await folder(t); const file = join(root, 'records.csv');
  await writeFile(file, 'name,state\n"Placeholder, One",RI\nPlaceholder Two,RI\n');
  const args = ['run', 'base', 'batch', '--file', file, '--args', '{"batch":"placeholder-batch"}'];
  const io = output();
  const result = await run([...args, '--dry-run', '--output', 'json'], { io, store: { get: forbidden, set: forbidden }, transport: forbidden });
  assert.deepEqual(JSON.parse(io.text), { status: 'dry_run', tool: 'base.batch', records: 2, argument_names: ['batch', 'records'], authorization: 'not_checked', task_schema: 'not_checked', network_calls: 0, tool_calls: 0, cost_usd: 0 });
  assert.equal(result.records, 2); assert(!io.text.includes('Placeholder')); assert(!io.text.includes('RI'));
  const calls = [];
  await run(args, { io: output(['n']), store: { get: async () => token }, transport: async (url, init) => {
    const body = init.body ? JSON.parse(init.body) : null; calls.push({ url, body });
    if (url.endsWith('/threads')) return Response.json({ thread_id: 'placeholder-thread' });
    if (url.endsWith('/tools')) return Response.json(['base.batch']);
    if (url.endsWith('/actions')) return Response.json({ card_id: 'placeholder-card', status: 'pending', summary: 'placeholder action' });
    assert.deepEqual(body, { action: 'cancel' }); return Response.json({ status: 'cancelled' });
  } });
  assert.deepEqual(calls.find(call => call.url.endsWith('/actions')).body, { tool: 'base.batch', arguments: { batch: 'placeholder-batch', records: [{ name: 'Placeholder, One', state: 'RI' }, { name: 'Placeholder Two', state: 'RI' }] } });
  await writeFile(file, 'name,state\n'); const empty = output();
  await run([...args, '--dry-run'], { io: empty, store: { get: forbidden }, transport: forbidden });
  assert.match(empty.text, /records 0 \| cost 0/); assert.match(empty.text, /First action: remove --dry-run/);
});

test('gate4 scheduled and training tool requests use the same dry-run command without launching work', async () => {
  // OPLI owns the generic run entrypoint, not these products' schedulers/trainers.
  for (const [agent, task] of [['base', 'batch'], ['tiger', 'train'], ['zenas', 'train'], ['placeholder', 'scheduled']]) {
    const io = output();
    const result = await run(['run', agent, task, '--args', '{"resume":true}', '--dry-run', '--output', 'json'], { io, store: { get: forbidden }, transport: forbidden });
    assert.equal(result.tool, `${agent}.${task}`); assert.equal(result.tool_calls, 0); assert.equal(result.network_calls, 0);
    assert.equal(result.authorization, 'not_checked'); assert.equal(result.task_schema, 'not_checked');
    assert.doesNotMatch(io.text, /approved|launched|receipt/);
  }
});

test('gate4 invalid dry-run inputs fail closed without login reads requests or filesystem writes', async t => {
  const root = await folder(t); const bad = join(root, 'bad.csv');
  const context = { io: output(), store: { get: forbidden }, transport: forbidden };
  for (const args of [[], ['run'], ['build', 'change'], ['-p', 'task'], ['run', 'base', 'batch', '--output', 'yaml'], ['run', 'base', 'batch', '--dry-run'], ['run', 'base', 'batch', '--model', 'auto']]) {
    await assert.rejects(run([...args, '--dry-run'], context), /Invalid|Run requires/);
  }
  for (const args of ['[]', 'null', '7', '{bad', JSON.stringify({ password: 'placeholder'.repeat(3) })]) await assert.rejects(run(['run', 'base', 'batch', '--args', args, '--dry-run'], context), /Invalid task arguments/);
  for (const content of [Buffer.from([0, 1, 2]), Buffer.from([255, 255]), 'a,b\n"unterminated', 'x'.repeat(2_000_001)]) {
    await writeFile(bad, content); await assert.rejects(run(['run', 'base', 'batch', '--file', bad, '--dry-run'], context), /Invalid CSV/);
  }
  await writeFile(bad, 'name\nplaceholder\n'); await symlink(bad, join(root, 'link.csv'));
  for (const path of [join(root, 'link.csv'), join(root, '.env'), join(root, 'absent.csv')]) await assert.rejects(run(['run', 'base', 'batch', '--file', path, '--dry-run'], context), /Invalid/);
  await assert.rejects(run(['run', 'base', 'batch', '--args', 'null'], context), /Invalid task arguments/);
});

test('gate4 the installed dry-run launcher makes zero outbound calls including passive updates', async t => {
  const root = await folder(t); const version = '0.11.0'; const installed = join(root, version);
  await mkdir(installed); await cp(join(cli, 'src'), join(installed, 'src'), { recursive: true }); await cp(join(cli, 'bin'), join(installed, 'bin'), { recursive: true });
  await cp(join(cli, 'package.json'), join(installed, 'package.json')); await symlink(join(cli, 'node_modules'), join(installed, 'node_modules'), 'dir');
  await writeFile(join(installed, 'RELEASE.json'), JSON.stringify({ version, platform: 'placeholder-platform' }));
  const marker = join(root, 'outbound'); const guard = join(root, 'guard.mjs');
  await writeFile(guard, `import {writeFileSync} from 'node:fs';globalThis.fetch=()=>{writeFileSync(${JSON.stringify(marker)},'called');throw Error('Outbound forbidden');};\n`);
  const env = { ...process.env, NODE_OPTIONS: `${process.env.NODE_OPTIONS ?? ''} --import=${pathToFileURL(guard).href}` };
  delete env.TERVORY_NO_UPDATE_CHECK; delete env.TERVORY_CLI_VERSION;
  const result = await execute(process.execPath, [join(installed, 'bin/tervory.mjs'), 'run', 'base', 'batch', '--dry-run', '--output', 'json'], { env });
  assert.equal(JSON.parse(result.stdout).status, 'dry_run'); assert.equal(result.stderr, ''); await assert.rejects(access(marker));
});

test('gate4 missing release signing settings name only the missing setting and write nothing', async t => {
  const root = await folder(t); const before = await readdir(root);
  for (const [privateValue, publicValue, name] of [[undefined, 'placeholder', 'CLI_RELEASE_SIGNING_KEY'], ['placeholder', undefined, 'CLI_RELEASE_SIGNING_PUBLIC_KEY']]) {
    assert.throws(() => signRelease(root, privateValue, publicValue), error => error instanceof ConfigurationError && error.settings[0] === name);
    assert.deepEqual(await readdir(root), before);
  }
  const env = { ...process.env }; delete env.CLI_RELEASE_SIGNING_KEY; delete env.CLI_RELEASE_SIGNING_PUBLIC_KEY;
  await assert.rejects(execute(process.execPath, [join(cli, 'scripts/sign-release.mjs'), root], { env }), error => error.code === 1 && error.stderr.includes('Missing setting CLI_RELEASE_SIGNING_KEY.') && !error.stderr.includes(' at '));
  assert.deepEqual(await readdir(root), before);
});

test('gate4 installer missing HOME or public key file exits plainly before download or install', async t => {
  const root = await folder(t); const marker = join(root, 'outbound'); const bin = join(root, 'bin'); await mkdir(bin);
  await writeFile(join(bin, 'curl'), `#!/bin/sh\ntouch '${marker}'\nexit 99\n`, { mode: 0o755 });
  const env = { ...process.env, PATH: bin + ':' + process.env.PATH };
  for (const name of ['HOME', 'TERVORY_HOME', 'TERVORY_BIN_DIR', 'TERVORY_CLI_BASE', 'TERVORY_CLI_PUBLIC_KEY_FILE']) delete env[name];
  await assert.rejects(execute('sh', [join(cli, 'install.sh')], { env }), error => error.stderr.includes('Missing setting HOME.') && !error.stderr.includes('parameter not set'));
  await assert.rejects(execute('sh', [join(cli, 'install.sh')], { env: { ...env, TERVORY_HOME: join(root, 'home'), TERVORY_BIN_DIR: join(root, 'launchers'), TERVORY_CLI_PUBLIC_KEY_FILE: join(root, 'absent-public.pem') } }), error => error.stderr.includes('TERVORY_CLI_PUBLIC_KEY_FILE is not readable.'));
  await assert.rejects(access(marker)); await assert.rejects(access(join(root, 'home'))); await assert.rejects(access(join(root, 'launchers')));
});
