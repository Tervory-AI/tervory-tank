import { readFile, writeFile, copyFile, mkdir, access } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const { createICO, createICNS } = require('png2icons');
export const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const pin = JSON.parse(await readFile(resolve(root, 'window/upstream.json')));
export const source = resolve(root, '.tmp/code-oss-source');
export async function prepare() {
  await mkdir(resolve(root, '.tmp'), { recursive: true });
  const archive = resolve(root, '.tmp/code-oss.tar.gz');
  try { await access(archive); }
  catch {
    const response = await fetch(`https://codeload.github.com/microsoft/vscode/tar.gz/${pin.commit}`, { signal: AbortSignal.timeout(300000) });
    if (!response.ok) throw Error('Code-OSS source download failed.');
    await writeFile(archive, Buffer.from(await response.arrayBuffer()));
  }
  if (createHash('sha256').update(await readFile(archive)).digest('hex') !== pin.sha256) throw Error('Code-OSS source checksum mismatch.');
  try { await access(resolve(source, 'package.json')); }
  catch {
    await mkdir(source, { recursive: true });
    execFileSync('tar', ['-xzf', archive, '--strip-components=1', '-C', source]);
  }
  if (JSON.parse(await readFile(resolve(source, 'package.json'))).version !== pin.release) throw Error('Wrong Code-OSS release.');
  const product = JSON.parse(await readFile(resolve(source, 'product.json')));
  const patch = JSON.parse(await readFile(resolve(root, 'window/patches/product.json')));
  Object.assign(product, patch);
  // All AI is Tervory/Tank. Do not leave an upstream Copilot activation path.
  delete product.defaultChatAgent; delete product.aiConfig; delete product.tasConfig;
  delete product.extensionTelemetry; delete product.telemetry;
  product.extensionAllowedProposedApi = (product.extensionAllowedProposedApi ?? []).filter(id => !/copilot/i.test(id));
  product.builtInExtensions = (product.builtInExtensions ?? []).filter(item => !/copilot/i.test(item.name));
  await writeFile(resolve(source, 'product.json'), JSON.stringify(product, null, 2) + '\n');
  const logo = await readFile(resolve(root, 'workspace/public/brand/tervory-logo.png'));
  // Format conversion of the exact supplied logo, never a replacement drawing.
  const ico = createICO(logo, 0, 0, true); const icns = createICNS(logo, 0, 0);
  if (!ico || !icns) throw Error('Brand icon conversion failed.');
  await writeFile(resolve(source, 'resources/win32/code.ico'), ico);
  await writeFile(resolve(source, 'resources/darwin/code.icns'), icns);
  for (const file of ['resources/linux/code.png', 'resources/win32/code_70x70.png', 'resources/win32/code_150x150.png']) await writeFile(resolve(source, file), logo);
  const installer = resolve(source, 'build/win32/code.iss');
  let setup = await readFile(installer, 'utf8');
  setup = setup.replaceAll('AppPublisher=Microsoft Corporation', 'AppPublisher=Tervory').replaceAll('https://code.visualstudio.com/', 'https://tervory.com/');
  await writeFile(installer, setup);
  await copyFile(resolve(source, 'LICENSE.txt'), resolve(root, 'window/CODE-OSS.LICENSE'));
  return source;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) console.log(await prepare());
