// Self-hosted distribution: build-release.mjs -> install.sh -> tervory update.
// Everything is served from a loopback HTTP server standing in for
// https://app.tervory.com/cli; no registry publish, no network beyond build-time
// `npm ci` of the pinned lockfile. Host platform only (the CI runner's).
import test from 'node:test';
import assert from 'node:assert/strict';
import { execFile, execFileSync } from 'node:child_process';
import { createServer } from 'node:http';
import { existsSync, mkdtempSync, readFileSync, readlinkSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { promisify } from 'node:util';
import { buildRelease, compareVersions } from '../scripts/build-release.mjs';

const CLI = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const run = promisify(execFile);
const ARCH = { x64: 'x64', arm64: 'arm64' }[process.arch];
const musl = process.platform === 'linux' && !process.report.getReport().header.glibcVersionRuntime;
const PLATFORM = process.platform === 'darwin' ? `darwin-${ARCH}` : `linux-${ARCH}-${musl ? 'musl' : 'gnu'}`;
const supported = (process.platform === 'linux' || process.platform === 'darwin') && ARCH;

const work = mkdtempSync(join(tmpdir(), 'tervory-release-test-'));
const out = join(work, 'site');
let server; let base; const tamper = { on: false };

test.before(async () => {
  if (!supported) return;
  buildRelease({ out, platforms: [PLATFORM], version: '0.1.0' });
  buildRelease({ out, platforms: [PLATFORM], version: '0.1.1' });
  server = createServer((req, res) => {
    const path = new URL(req.url, 'http://x').pathname.replace(/^\/cli\//, '');
    const file = resolve(out, path);
    if (!file.startsWith(out + '/') || !existsSync(file)) { res.writeHead(404).end('not found'); return; }
    let bytes = readFileSync(file);
    if (tamper.on && file.endsWith('.tar.gz')) { bytes = Buffer.from(bytes); bytes[bytes.length - 20] ^= 0xff; }
    res.writeHead(200).end(bytes);
  });
  await new Promise(r => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}/cli`;
});
test.after(() => { server?.close(); rmSync(work, { recursive: true, force: true }); });

// Map the fixed https://app.tervory.com/cli base onto the loopback server.
const transport = (url, init) => fetch(String(url).replace('https://app.tervory.com/cli', base), init);

function install(env, home) {
  return run('sh', [join(CLI, 'install.sh')], {
    env: { PATH: process.env.PATH, HOME: home, TERVORY_CLI_BASE: base, TERVORY_BIN_DIR: join(home, 'bin'), ...env },
  }).then(r => ({ code: 0, ...r }), e => ({ code: e.code, stdout: e.stdout, stderr: e.stderr }));
}

test('release is reproducible and the manifest matches the bytes', { skip: !supported && 'host platform has no build' }, () => {
  const manifest = JSON.parse(readFileSync(join(out, 'releases/0.1.1/manifest.json'), 'utf8'));
  const artifact = manifest.artifacts[PLATFORM];
  assert.equal(artifact.file, `tervory-cli-0.1.1-${PLATFORM}.tar.gz`);
  const sum = execFileSync('sha256sum', [join(out, 'releases/0.1.1', artifact.file)]).toString().split(' ')[0];
  assert.equal(sum, artifact.sha256);
  assert.match(readFileSync(join(out, 'releases/0.1.1/SHA256SUMS'), 'utf8'), new RegExp(`^${sum}  ${artifact.file}\\n$`));
  assert.deepEqual(JSON.parse(readFileSync(join(out, 'latest.json'), 'utf8')), { version: '0.1.1', manifest: 'releases/0.1.1/manifest.json' });
  assert.equal(readFileSync(join(out, 'install.sh'), 'utf8'), readFileSync(join(CLI, 'install.sh'), 'utf8'));
  const again = join(work, 'again');
  buildRelease({ out: again, platforms: [PLATFORM], version: '0.1.1' });
  assert.deepEqual(readFileSync(join(again, 'releases/0.1.1', artifact.file)), readFileSync(join(out, 'releases/0.1.1', artifact.file)));
  assert(compareVersions('0.10.0', '0.9.9') > 0);
});

test('install.sh installs latest, honours TERVORY_CLI_VERSION, and refuses a tampered tarball', { skip: !supported && 'host platform has no build' }, async () => {
  const home = mkdtempSync(join(work, 'home-'));
  const latest = await install({}, home);
  assert.equal(latest.code, 0, latest.stderr);
  assert.match(latest.stdout, /SHA-256 verified: [0-9a-f]{64}/);
  assert.equal(readlinkSync(join(home, '.tervory/cli/current')), '0.1.1');
  const version = await run(join(home, 'bin/tervory'), ['version'], { env: { PATH: process.env.PATH, HOME: home } });
  assert.equal(version.stdout, `tervory 0.1.1 (${PLATFORM})\n`);

  const pinned = await install({ TERVORY_CLI_VERSION: '0.1.0' }, home);
  assert.equal(pinned.code, 0, pinned.stderr);
  assert.equal(readlinkSync(join(home, '.tervory/cli/current')), '0.1.0');

  assert.notEqual((await install({ TERVORY_CLI_VERSION: '9.9.9' }, home)).code, 0);
  assert.notEqual((await install({ TERVORY_CLI_VERSION: '1.0; rm -rf /' }, home)).code, 0);
  assert.notEqual((await install({ TERVORY_CLI_BASE: 'http://example.com/cli' }, home)).code, 0);

  const fresh = mkdtempSync(join(work, 'home-'));
  tamper.on = true;
  try {
    const refused = await install({}, fresh);
    assert.notEqual(refused.code, 0);
    assert.match(refused.stderr, /Checksum mismatch .* Nothing was installed\./);
    assert.equal(existsSync(join(fresh, '.tervory/cli')), false);
    assert.equal(existsSync(join(fresh, 'bin/tervory')), false);
  } finally { tamper.on = false; }
});

test('tervory update: latest, TERVORY_CLI_VERSION pin, and checksum refusal', { skip: !supported && 'host platform has no build' }, async () => {
  const home = mkdtempSync(join(work, 'home-'));
  assert.equal((await install({ TERVORY_CLI_VERSION: '0.1.0' }, home)).code, 0);
  const cliDir = join(home, '.tervory/cli');
  // Drive the installed copy's own modules (their package root is the installed release).
  const installed = await import(pathToFileURL(join(cliDir, '0.1.0/src/client.mjs')));
  let output = ''; const io = { write: v => { output += v; }, prompt: async () => null };

  tamper.on = true;
  try {
    await assert.rejects(installed.run(['update'], { transport, io, env: {} }),
      /Update refused: checksum mismatch for tervory-cli-0\.1\.1-.*Nothing was changed\./);
  } finally { tamper.on = false; }
  assert.equal(readlinkSync(join(cliDir, 'current')), '0.1.0');
  assert.equal(existsSync(join(cliDir, '0.1.1')), false);

  // A pin to the installed version is a no-op, even though 0.1.1 is latest.
  await installed.run(['update'], { transport, io, env: { TERVORY_CLI_VERSION: '0.1.0' } });
  assert.match(output, /0\.1\.0 is already installed/);
  assert.equal(readlinkSync(join(cliDir, 'current')), '0.1.0');
  await assert.rejects(installed.run(['update'], { transport, io, env: { TERVORY_CLI_VERSION: 'latest' } }), /invalid version/);
  await assert.rejects(installed.run(['update'], { transport, io, env: { TERVORY_CLI_VERSION: '7.7.7' } }), /version 7\.7\.7 is not available/);

  await installed.run(['update'], { transport, io, env: {} });
  assert.match(output, /SHA-256 verified: [0-9a-f]{64}\nUpdated Tervory CLI 0\.1\.0 -> 0\.1\.1\./);
  assert.equal(readlinkSync(join(cliDir, 'current')), '0.1.1');

  // --version wins over the pin; downgrade back to 0.1.0 through the 0.1.1 copy.
  const newer = await import(pathToFileURL(join(cliDir, '0.1.1/src/client.mjs')));
  await newer.run(['update', '--version', '0.1.0'], { transport, io, env: { TERVORY_CLI_VERSION: '0.1.1' } });
  assert.equal(readlinkSync(join(cliDir, 'current')), '0.1.0');
  const launched = await run(join(home, 'bin/tervory'), ['version'], { env: { PATH: process.env.PATH, HOME: home } });
  assert.equal(launched.stdout, `tervory 0.1.0 (${PLATFORM})\n`);

  // Review of #506 should-fix 3: latest.json pointing below the installed copy (a rollback,
  // a stale cache or a tampered mirror) is refused unless --version / the pin asks for it.
  const stale = (url, init) => String(url).endsWith('/latest.json')
    ? Promise.resolve(Response.json({ version: '0.1.0', manifest: 'releases/0.1.0/manifest.json' }))
    : transport(url, init);
  const before = readlinkSync(join(cliDir, 'current'));
  await assert.rejects(newer.run(['update'], { transport: stale, io, env: {} }),
    /Update refused: latest\.json offers 0\.1\.0, older than the installed 0\.1\.1\. Use tervory update --version 0\.1\.0 to downgrade\./);
  assert.equal(readlinkSync(join(cliDir, 'current')), before);
  assert(existsSync(join(cliDir, '0.1.1/RELEASE.json')));

  // Development checkouts never self-update.
  const { run: devRun } = await import('../src/client.mjs');
  await assert.rejects(devRun(['update'], { transport, io, env: {} }), /only available for copies installed with: curl -fsSL https:\/\/app\.tervory\.com\/cli\/install\.sh \| sh/);
});

test('update notice: at most daily, silent on failure', { skip: !supported && 'host platform has no build' }, async () => {
  const home = mkdtempSync(join(work, 'home-'));
  assert.equal((await install({ TERVORY_CLI_VERSION: '0.1.0' }, home)).code, 0);
  const root = join(home, '.tervory/cli/0.1.0');
  const { updateNotice } = await import(pathToFileURL(join(root, 'src/update.mjs')));
  let calls = 0; const counted = (url, init) => { calls++; return transport(url, init); };
  assert.match(await updateNotice({ transport: counted, now: () => 1_000_000 }), /0\.1\.0 -> 0\.1\.1\. Run: tervory update/);
  assert.match(await updateNotice({ transport: counted, now: () => 1_000_000 + 60_000 }), /0\.1\.1/);
  assert.equal(calls, 1);
  assert.equal(await updateNotice({ transport: async () => { throw new Error('offline'); }, now: () => 10 ** 12 }), null);
});
