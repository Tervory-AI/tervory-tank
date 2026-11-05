import test from 'node:test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
process.env.COMMAND_TEST_TOOLS ??= fileURLToPath(new URL('../../cli/node_modules', import.meta.url));
const { workspace } = await import('../command_acceptance_20261031/workspace_loader.cjs');
const tenant = { tenantId: '00000000-0000-0000-0000-000000000011', userId: 'placeholder-user', tenantAdmin: false };
const id = '00000000-0000-0000-0000-000000000022';
const jsx = (type, props) => typeof type === 'function' ? type(props) : { type, props };
function nodes(tree) {
  if (tree === null || tree === undefined || typeof tree === 'boolean') return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (typeof tree !== 'object') return [tree];
  return [tree, ...nodes(tree.props?.children)];
}
function harness() {
  let revoked = false; const calls = [];
  const load = workspace({ env: { TANK_URL: 'http://placeholder-tank', TANK_API_KEY: 'placeholder-workspace-key' },
    mocks: {
      'react/jsx-runtime': { jsx, jsxs: jsx },
      'next/navigation': { redirect: value => { throw new Error('redirect:' + value); } },
      '@/lib/tenant': { activeTenant: async () => ({}) },
      '@/lib/trigger': { triggerIdentity: async () => tenant },
      '../../access/access.css': {},
    }, fetch: async (url, init) => {
      const path = new URL(url).pathname; calls.push({ path, ...init });
      assert.equal(init.headers['x-tervory-user'], tenant.userId);
      assert.equal(init.headers['x-tervory-tenant'], tenant.tenantId);
      if (path === '/v1/personal-tokens' && init.method === 'GET') return Response.json(revoked ? [] : [
        { token_id: id, region: 'us-east', device_name: 'placeholder-worker', created_at: '2026-11-03T12:00:00Z', last_used_at: null },
        { token_id: '00000000-0000-0000-0000-000000000033', device_name: 'placeholder-expired', created_at: '2026-11-03T12:00:00Z', refresh_expires_at: '2000-01-01T00:00:00Z' },
      ]);
      if (path === '/v1/personal-tokens/' + id && init.method === 'DELETE') { revoked = true; return new Response(null, { status: 204 }); }
      if (path.startsWith('/v1/command/device/approval/')) return Response.json({ device_name: 'placeholder-worker', user_code: 'BCDF-GHJK', created_at: '2026-11-03T12:00:00Z', region: 'us-east', status: init.method === 'POST' ? JSON.parse(init.body).action === 'approve' ? 'approved' : 'denied' : 'pending' });
      assert.fail('Unexpected fixture path: ' + path);
    } });
  return { load, calls };
}
test('CLI acceptance: sign-in list renders active devices and Revoke ends the selected sign-in', async () => {
  const h = harness(); const page = h.load('app/cli/sign-ins/page.tsx').default;
  let tree = nodes(await page({ searchParams: Promise.resolve({}) }));
  assert(tree.includes('CLI sign-ins')); assert(tree.includes('placeholder-worker')); assert(tree.includes('US East')); assert(tree.includes('Revoke'));
  assert(!tree.includes('placeholder-expired'));
  const form = tree.find(node => node.type === 'form'); const data = new FormData(); data.set('region', 'us-east'); data.set('token_id', id);
  await assert.rejects(form.props.action(data), { message: 'redirect:/cli/sign-ins?result=revoked' });
  tree = nodes(await page({ searchParams: Promise.resolve({ result: 'revoked' }) }));
  assert(tree.includes('Revoked. That sign-in stopped working at once, including its refresh token.'));
  assert(tree.includes('No active CLI sign-ins')); assert(!tree.includes('placeholder-worker'));
});
test('CLI acceptance: native approval replaces Workspace approval', () => {
  const env = { ...process.env };
  delete env.NODE_TEST_CONTEXT;
  const output = execFileSync(process.execPath, ['--test', 'cli/test/trigger-signin.test.mjs'], { encoding: 'utf8', env });
  assert.match(output, /# fail 0/);
});

// Real cross-platform release archives; dependency tarballs are warmed before
// the offline suite, then npm ci runs with npm_config_offline=true.
import { buildRelease, PLATFORMS } from '../../cli/scripts/build-release.mjs';
import { signRelease } from '../../cli/scripts/sign-release.mjs';
import { verifyRelease } from '../../cli/scripts/verify-release.mjs';
import { generateKeyPairSync } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, writeFileSync, renameSync, rmSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
let release;
function releaseFixture() {
  if (release) return release;
  const folder = mkdtempSync(join(tmpdir(), 'cli-acceptance-release-'));
  const manifest = buildRelease({ out: join(folder, 'site') });
  const directory = join(folder, 'site/releases', manifest.version);
  const pair = generateKeyPairSync('ed25519', { privateKeyEncoding: { type: 'pkcs8', format: 'pem' }, publicKeyEncoding: { type: 'spki', format: 'pem' } });
  signRelease(directory, pair.privateKey, pair.publicKey);
  return (release = { folder, manifest, directory, publicKey: pair.publicKey });
}
test.after(() => { if (release) rmSync(release.folder, { recursive: true, force: true }); });
test('CLI acceptance: real eight-platform tag payloads carry verified signatures and checksums', () => {
  const { directory, manifest, publicKey } = releaseFixture();
  assert.deepEqual(Object.keys(manifest.artifacts).sort(), Object.keys(PLATFORMS).sort());
  assert.equal(Object.keys(manifest.artifacts).length, 8);
  assert.equal(verifyRelease(directory, publicKey), 8);
  for (const platform of Object.keys(PLATFORMS)) {
    const listing = execFileSync('tar', ['--force-local', '-tzf', join(directory, manifest.artifacts[platform].file)]).toString();
    assert(listing.includes(`node_modules/@napi-rs/keyring-${platform}/`), platform);
    if (platform.startsWith('win32')) assert(listing.includes('/tervory.cmd'));
  }
});
test('CLI acceptance: verified Windows archive installs and its real Node entry reports the release', () => {
  const { folder, directory, manifest, publicKey } = releaseFixture();
  const platform = 'win32-x64-msvc';
  assert.equal(manifest.version, JSON.parse(readFileSync(new URL('../../cli/package.json', import.meta.url), 'utf8')).version);
  assert.equal(verifyRelease(directory, publicKey, platform, manifest.version), 1);
  const unpack = join(folder, 'unpack'); mkdirSync(unpack);
  execFileSync('tar', ['--force-local', '-xzf', join(directory, manifest.artifacts[platform].file), '-C', unpack]);
  const root = join(unpack, manifest.version); renameSync(join(unpack, `tervory-cli-${manifest.version}`), root);
  assert.equal(readFileSync(join(root, 'tervory.cmd'), 'utf8'), '@echo off\r\nnode "%~dp0bin\\tervory.mjs" %*\r\n');
  const env = { ...process.env, TERVORY_NO_UPDATE_CHECK: '1' };
  assert.equal(execFileSync(process.execPath, [join(root, 'bin/tervory.mjs'), 'version'], { env }).toString(), `tervory ${manifest.version} (${platform})\n`);
  // Public test key only; the signing private key never reaches disk.
  const keyFile = join(folder, 'trusted-public.pem'); writeFileSync(keyFile, publicKey);
  const verifier = fileURLToPath(new URL('../../cli/scripts/verify-release.mjs', import.meta.url));
  assert.equal(execFileSync(process.execPath, [verifier, directory, keyFile, platform, manifest.version], { env }).toString(), 'Release signatures and checksums verified.\n');
});
