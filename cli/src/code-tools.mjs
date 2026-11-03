import { constants } from 'node:fs';
import { lstat, realpath, open, readdir, readFile, writeFile, rename, unlink, mkdtemp, rm } from 'node:fs/promises';
import { resolve, relative, isAbsolute, sep, dirname } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { Worker } from 'node:worker_threads';

export const LIMITS = Object.freeze({ files: 2000, fileBytes: 200_000, matches: 200, outputBytes: 65536, commandMs: 120_000 });
// Kept in parity with tests/test_secrets.py _LIVE / _ASSIGNED. Do not exempt
// placeholders here: local source sent to a model gets the stricter treatment.
const LIVE = [
  /-----BEGIN (?:RSA |OPENSSH |EC |DSA |PGP )?PRIVATE KEY-----/,
  /\bAKIA[0-9A-Z]{16}\b/, /\bghp_[A-Za-z0-9]{20,}\b/, /\bgithub_pat_[A-Za-z0-9_]{20,}\b/,
  /\bxox[baprs]-[A-Za-z0-9-]{10,}/, /\bsk-ant-[A-Za-z0-9_\-]{10,}/,
  /(?<![A-Za-z0-9_])sk-[A-Za-z0-9]{20,}/,
  /\b(?:sk|pk|rk)_live_[A-Za-z0-9]{8,}/, /\bAIza[0-9A-Za-z0-9_\-]{30,}/,
  /\beyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}/,
  /(?:^|[^A-Za-z0-9])(?:api[_-]?key|secret[_-]?key|client[_-]?secret|password|passwd|access[_-]?token|auth[_-]?token)\s*[:=]\s*['"]?[^\s'"#]{12,}/i,
  /tv[rd]?1\.(?:us-east|za)\.[A-Za-z0-9_.-]+/,
];
export function redactSecrets(value) {
  return String(value).split('\n').map(line => LIVE.some(pattern => pattern.test(line)) ? '[redacted]' : line).join('\n');
}
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
const refused = () => new Error('Code tool refused.');
const inside = (root, path) => { const rel = relative(root, path); return rel !== '..' && !rel.startsWith('..' + sep) && !isAbsolute(rel); };
export function secretPath(path) {
  return path.split(/[\\/]/).some(part => part === '.git' || /^\.env/i.test(part) || /^id_/i.test(part) || /\.(pem|key)$/i.test(part));
}

// The process output is collected, not streamed: redaction must see complete lines
// even when a secret arrives split across stdout/stderr chunks.
export async function processOutput(command, args, { cwd, shell = false, timeoutMs = LIMITS.commandMs, signal, input, outputBytes = LIMITS.outputBytes, delimiter = '\n' } = {}) {
  return new Promise((resolveResult, reject) => {
    let child; let timer; let killed = false; let size = 0; let total = 0; const chunks = [];
    const stop = () => {
      killed = true;
      try { if (process.platform !== 'win32') process.kill(-child.pid, 'SIGKILL'); else child.kill('SIGKILL'); } catch { /* already ended */ }
    };
    if (signal?.aborted) return reject(refused());
    try {
      child = spawn(command, args, { cwd, shell, detached: process.platform !== 'win32', windowsHide: true,
        env: { PATH: process.env.PATH, LANG: 'C.UTF-8', GIT_CONFIG_NOSYSTEM: '1', GIT_CONFIG_GLOBAL: '/dev/null' },
        stdio: [input === undefined ? 'ignore' : 'pipe', 'pipe', 'pipe'] });
    } catch { return reject(refused()); }
    if (input !== undefined) { child.stdin.on('error', () => {}); child.stdin.end(input); }
    const collect = chunk => { total += chunk.length; const keep = chunk.subarray(0, Math.max(0, outputBytes - size)); size += keep.length; if (keep.length) chunks.push(Buffer.from(keep)); };
    child.stdout.on('data', collect); child.stderr.on('data', collect);
    child.on('error', () => { clearTimeout(timer); signal?.removeEventListener('abort', stop); reject(refused()); });
    timer = setTimeout(stop, timeoutMs); signal?.addEventListener('abort', stop, { once: true });
    child.on('close', code => {
      clearTimeout(timer); signal?.removeEventListener('abort', stop);
      // An incomplete retained last line is omitted, so a secret whose suffix is
      // beyond the cap cannot leak its prefix.
      let output = Buffer.concat(chunks).toString('utf8');
      if (total > size) output = output.slice(0, output.lastIndexOf(delimiter) + 1);
      resolveResult({ code, timed_out: killed, truncated: total > size, output: redactSecrets(output) });
    });
  });
}

export class CodeFolder {
  #reads = new Map();
  static async create(folder = '.') {
    const root = await realpath(resolve(folder));
    if (!(await lstat(root)).isDirectory()) throw refused();
    const tool = new CodeFolder(root);
    const check = await tool.git(['rev-parse', '--show-toplevel']);
    if (check.code !== 0) throw new Error('Code mode requires a git repository.');
    return tool;
  }
  constructor(root) { this.root = root; }
  async git(args, input) {
    const options = ['-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null', '-c', 'core.attributesFile=/dev/null', '--no-pager'];
    if (['status', 'diff'].includes(args[0])) {
      // Git can invoke clean/process filters even with --no-ext-diff and
      // --no-textconv. Disable driver execution: read tools do not approve a
      // repository-configured shell command. Ask for names only, never values.
      const drivers = await processOutput('git', [...options, 'config', '--name-only', '--get-regexp', '^filter\\..*\\.(clean|process|required)$'], { cwd: this.root });
      if (drivers.truncated || ![0, 1].includes(drivers.code)) throw refused();
      for (const key of drivers.output.trim().split('\n').filter(Boolean)) {
        if (!/^filter\.[A-Za-z0-9_.-]+\.(clean|process|required)$/.test(key)) throw refused();
        options.push('-c', key + (key.endsWith('.required') ? '=false' : '='));
      }
    }
    return processOutput('git', [...options, ...args], { cwd: this.root, input, outputBytes: ['ls-files', 'check-ignore'].includes(args[0]) ? 8_388_608 : LIMITS.outputBytes, delimiter: args.includes('-z') ? '\0' : '\n' });
  }
  async path(name, { missing = false } = {}) {
    if (typeof name !== 'string' || !name || /[\x00-\x1f\x7f]/.test(name) || name.includes('\\')) throw refused();
    const path = resolve(this.root, name);
    if (!inside(this.root, path) || secretPath(relative(this.root, path))) throw refused();
    // Follow every ancestor, even when the final file does not exist yet.
    const parent = await realpath(dirname(path));
    if (!inside(this.root, parent)) throw refused();
    try {
      const canonical = await realpath(path);
      if (!inside(this.root, canonical) || secretPath(relative(this.root, canonical))) throw refused();
      if ((await lstat(path)).isSymbolicLink()) throw refused();
    } catch (error) { if (!missing || error.code !== 'ENOENT') throw error; }
    return path;
  }
  async files() {
    // Git supplies ignore semantics, including nested .gitignore and info/exclude.
    // Output is bounded; return only complete NUL-delimited names if truncated.
    const result = await this.git(['ls-files', '-z', '--cached', '--others', '--exclude-standard', '--', '.']);
    if (result.code !== 0) throw refused();
    const names = result.output.split('\0'); names.pop();
    const ignored = await this.git(['check-ignore', '--no-index', '-z', '--stdin'], names.join('\0') + '\0');
    if (![0, 1].includes(ignored.code) || ignored.truncated) throw refused();
    const excluded = new Set(ignored.output.split('\0'));
    const files = [];
    for (const name of names) {
      try {
        const path = await this.path(name);
        if (!excluded.has(name) && (await lstat(path)).isFile()) files.push(name);
      } catch { /* ignored, secret, symlink or vanished */ }
      if (files.length === LIMITS.files) break;
    }
    return { files, truncated: result.truncated || names.length > files.length && files.length === LIMITS.files };
  }
  async raw(name) {
    const path = await this.path(name, { missing: true });
    let handle;
    try {
      handle = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0) | (constants.O_NONBLOCK ?? 0));
      const stat = await handle.stat();
      if (!stat.isFile() || stat.size > LIMITS.fileBytes) throw refused();
      // On Linux verify the opened descriptor before reading, closing ancestor
      // symlink-swap races; other platforms recheck the canonical path below.
      if (process.platform === 'linux' && !inside(this.root, await realpath(`/proc/self/fd/${handle.fd}`))) throw refused();
      const bytes = Buffer.alloc(LIMITS.fileBytes + 1); const { bytesRead } = await handle.read(bytes, 0, bytes.length, 0);
      if (bytesRead > LIMITS.fileBytes) throw refused();
      const raw = bytes.subarray(0, bytesRead); const text = new TextDecoder('utf-8', { fatal: true }).decode(raw);
      if (text.includes('\0')) throw refused();
      await this.path(name);
      return { bytes: raw, text };
    } catch (error) {
      if (error.code === 'ENOENT') return null;
      throw refused();
    } finally { await handle?.close(); }
  }
  async read(name) {
    const path = await this.path(name, { missing: true });
    const value = await this.raw(name);
    this.#reads.set(path, value === null ? null : digest(value.bytes));
    return value === null ? { exists: false, text: '', size: 0 }
      : { exists: true, text: redactSecrets(value.text), size: value.bytes.length };
  }
  async search(pattern, regex = false) {
    if (typeof pattern !== 'string' || pattern.length > 500 || !pattern) throw refused();
    const files = (await this.files()).files; const matches = [];
    // Execute user/model regexes off the main thread with a hard bound; a
    // catastrophic expression cannot pin the interactive CLI.
    const worker = new Worker(`const {parentPort,workerData}=require('node:worker_threads');
      let re; try { re=workerData.regex?new RegExp(workerData.pattern):null; } catch { parentPort.postMessage({invalid:true}); }
      parentPort.on('message', ({text})=> {const lines=text.split('\\n');const rows=[];
        for(let i=0;i<lines.length;i++) if(re?re.test(lines[i]):lines[i].includes(workerData.pattern)) {
          rows.push({line:i+1,text:lines[i]});if(rows.length===200)break;}
        parentPort.postMessage({rows});});`, { eval: true, workerData: { pattern, regex } });
    try {
      for (const file of files) {
        let text; try { text = (await this.read(file)).text; } catch { continue; }
        const result = await new Promise((resolveResult, reject) => {
          const timer = setTimeout(() => reject(refused()), 1000);
          const done = value => { clearTimeout(timer); worker.off('error', fail); resolveResult(value); };
          const fail = () => { clearTimeout(timer); worker.off('message', done); reject(refused()); };
          worker.once('message', done); worker.once('error', fail); worker.postMessage({ text });
        });
        if (result.invalid) throw refused();
        matches.push(...result.rows.slice(0, LIMITS.matches - matches.length).map(row => ({ file, ...row })));
        if (matches.length >= LIMITS.matches) break;
      }
      return { matches, truncated: matches.length === LIMITS.matches };
    } finally { await worker.terminate(); }
  }
  async diff() {
    const { files } = await this.files();
    if (!files.length) return { output: '' };
    return this.git(['diff', '--no-ext-diff', '--no-textconv', '--ignore-submodules', '--', ...files]);
  }
  async edit(name, patch, io) {
    const path = await this.path(name, { missing: true });
    if (!this.#reads.has(path) || typeof patch !== 'string' || Buffer.byteLength(patch) > LIMITS.fileBytes || redactSecrets(patch) !== patch) throw refused();
    const expected = this.#reads.get(path);
    const check = async () => {
      await this.path(name, { missing: true });
      const value = await this.raw(name);
      if (value === null && expected === null) return '';
      if (value === null || expected === null || digest(value.bytes) !== expected || redactSecrets(value.text) !== value.text) throw refused();
      return value.text;
    };
    const before = await check(); const after = await applyDiff(before, patch, name, expected === null, this.root);
    if (Buffer.byteLength(after) > LIMITS.fileBytes || redactSecrets(after) !== after) throw refused();
    io.write(patch + '\n');
    if (io.interactive !== true || (await io.prompt('Apply [y/N] '))?.trim().toLowerCase() !== 'y') return { applied: false };
    await check();
    const temporary = resolve(dirname(path), `.tervory-${randomUUID()}`);
    try {
      await writeFile(temporary, after, { flag: 'wx', mode: expected === null ? 0o600 : (await lstat(path)).mode & 0o777 });
      await check(); await rename(temporary, path);
    } finally { await unlink(temporary).catch(() => {}); }
    this.#reads.set(path, digest(Buffer.from(after)));
    return { applied: true };
  }
  async command(command, io, timeoutMs) {
    if (process.platform !== 'linux') throw refused();
    // A confirmed command must not bypass the folder/secret-file boundary by
    // reading an absolute host path, a symlink, .env or the user's environment.
    // Use the worker's existing Bubblewrap; no unsandboxed fallback.
    const masks = [];
    const scan = async (directory, prefix = '') => {
      for (const entry of await readdir(directory, { withFileTypes: true })) {
        const name = prefix + entry.name;
        if (secretPath(name)) {
          masks.push(...(entry.isDirectory() ? ['--tmpfs', '/work/' + name] : ['--ro-bind', '/dev/null', '/work/' + name]));
        } else if (entry.isDirectory()) await scan(resolve(directory, entry.name), name + '/');
      }
    };
    await scan(this.root);
    return processOutput('bwrap', ['--unshare-all', '--die-with-parent', '--new-session',
      '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin', '--symlink', 'usr/lib', '/lib',
      '--symlink', 'usr/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
      '--bind', this.root, '/work', ...masks, '--chdir', '/work', '/bin/sh', '-c', command],
      { cwd: this.root, timeoutMs, signal: io.signal });
  }
  async tool(request, io, { timeoutMs = LIMITS.commandMs } = {}) {
    const args = request.arguments ?? {};
    switch (request.name) {
      case 'list_files': return this.files();
      case 'read_file': return this.read(args.path);
      case 'search': return this.search(args.pattern, args.regex === true);
      case 'git': return args.action === 'status' ? this.git(['status', '--short', '--', '.']) : args.action === 'diff' ? this.diff() : Promise.reject(refused());
      case 'propose_edit': return this.edit(args.path, args.diff, io);
      case 'run_command': {
        if (typeof args.command !== 'string' || !args.command || args.command.length > 8000 || /[\x00-\x1f\x7f]/.test(args.command) || redactSecrets(args.command) !== args.command) throw refused();
        io.write(args.command + '\n');
        if (io.interactive !== true || (await io.prompt('Run [y/N] '))?.trim().toLowerCase() !== 'y') return { ran: false };
        const result = await this.command(args.command, io, timeoutMs);
        io.write(result.output);
        return { ran: true, ...result };
      }
      default: throw refused();
    }
  }
}

// Use Git's existing unified-diff parser/applicator, not a second patch engine.
// Stage against a fixed neutral filename in a fresh scratch repo. No caller path,
// Git configuration, filter or hook can turn a patch into another file operation.
export async function applyDiff(before, patch, name, creating = false, root = process.cwd()) {
  const lines = patch.split('\n');
  if (lines[0] !== `--- ${creating ? '/dev/null' : 'a/' + name}` || lines[1] !== `+++ b/${name}`) throw refused();
  lines[0] = `--- ${creating ? '/dev/null' : 'a/target'}`; lines[1] = '+++ b/target';
  const input = lines.join('\n');
  const scratch = await mkdtemp(resolve(root, '.tervory-edit-'));
  const git = args => processOutput('git', ['-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
    '-c', 'core.attributesFile=/dev/null', ...args], { cwd: scratch, input });
  try {
    if ((await git(['init', '--quiet'])).code !== 0) throw refused();
    if (!creating) await writeFile(resolve(scratch, 'target'), before, { flag: 'wx', mode: 0o600 });
    const parsed = await git(['apply', '--numstat', '-z', '--unidiff-zero', '--whitespace=nowarn']);
    // The original patch may describe exactly one ordinary text file. Additional
    // headers, binary patches, renames and deleted files cannot escape this check.
    if (parsed.code !== 0 || !/^\d+\t\d+\ttarget\x00$/.test(parsed.output)) throw refused();
    if ((await git(['apply', '--check', '--unidiff-zero', '--whitespace=nowarn'])).code !== 0) throw refused();
    if ((await git(['apply', '--unidiff-zero', '--whitespace=nowarn'])).code !== 0) throw refused();
    const target = resolve(scratch, 'target'); const stat = await lstat(target);
    if (!stat.isFile() || stat.isSymbolicLink() || stat.size > LIMITS.fileBytes) throw refused();
    const result = new TextDecoder('utf-8', { fatal: true }).decode(await readFile(target));
    if (result.includes('\0')) throw refused();
    return result;
  } finally { await rm(scratch, { recursive: true, force: true }); }
}
