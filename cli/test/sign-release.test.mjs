import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync, verify } from 'node:crypto';
import { mkdtempSync, readFileSync, writeFileSync, rmSync, readdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { signRelease } from '../scripts/sign-release.mjs';

test('every platform archive, checksum and manifest is signed; tampering and another key fail', () => {
  const root = mkdtempSync(join(tmpdir(), 'cli-sign-placeholder-'));
  const keys = () => generateKeyPairSync('ed25519', { privateKeyEncoding: { type: 'pkcs8', format: 'pem' }, publicKeyEncoding: { type: 'spki', format: 'pem' } });
  const pair = keys(); const other = keys();
  try {
    const files = ['SHA256SUMS', 'manifest.json', ...['linux-x64-gnu', 'darwin-arm64', 'win32-x64-msvc'].map(p => `tervory-cli-0.5.0-${p}.tar.gz`)];
    for (const name of files) writeFileSync(join(root, name), `placeholder ${name}\n`);
    assert.deepEqual(signRelease(root, pair.privateKey, pair.publicKey), [...files].sort());
    for (const name of files) {
      const bytes = readFileSync(join(root, name)); const signature = Buffer.from(readFileSync(join(root, name + '.sig'), 'utf8').trim(), 'base64');
      assert(verify(null, bytes, pair.publicKey, signature));
      assert(!verify(null, Buffer.concat([bytes, Buffer.from('tampered')]), pair.publicKey, signature));
      assert(!verify(null, bytes, other.publicKey, signature));
    }
    assert.throws(() => signRelease(root, pair.privateKey, other.publicKey), /key refused/);
    assert(!readdirSync(root).some(name => name.endsWith('.pem')));
  } finally { rmSync(root, { recursive: true, force: true }); }
});
