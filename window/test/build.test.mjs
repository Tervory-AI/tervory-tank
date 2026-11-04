import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { execFileSync } from 'node:child_process';
import { root, pin, source } from '../build/prepare.mjs';

test('pinned Code-OSS source is MIT and the real product patch uses Open VSX without Microsoft telemetry', async () => {
  assert.equal(JSON.parse(await readFile(resolve(source, 'package.json'))).version, pin.release);
  assert.match(pin.sha256, /^[0-9a-f]{64}$/);
  assert((await readFile(resolve(source, 'LICENSE.txt'), 'utf8')).includes('MIT License'));
  const product = JSON.parse(await readFile(resolve(source, 'product.json')));
  for (const key of ['nameShort', 'nameLong', 'win32DirName']) assert.equal(product[key], 'Tervory');
  assert.equal(product.darwinBundleIdentifier, 'com.tervory.window');
  assert.equal(product.extensionsGallery.serviceUrl, 'https://open-vsx.org/vscode/gallery');
  assert.equal(product.enableTelemetry, false); assert.equal(product.enableCrashReporter, false);
  assert.equal(product.defaultChatAgent, undefined);
  assert.deepEqual(await readFile(resolve(source, 'resources/linux/code.png')), await readFile(resolve(root, 'workspace/public/brand/tervory-logo.png')));
  assert((await readFile(resolve(source, 'resources/win32/code.ico'))).length > 0);
  assert((await readFile(resolve(source, 'resources/darwin/code.icns'))).length > 0);
});
