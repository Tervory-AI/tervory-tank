import { build } from '../extension/node_modules/esbuild/lib/main.js';
import { cp, mkdir, readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { root } from './prepare.mjs';
const base = resolve(root, 'window/extension');
await mkdir(resolve(base, 'dist'), {recursive:true});
await mkdir(resolve(base, 'media'), {recursive:true});
await cp(resolve(root, 'workspace/public/brand/tervory-logo.png'), resolve(base, 'media/tervory-logo.png'));
await build({entryPoints:[resolve(base,'src/extension.cjs')], outfile:resolve(base,'dist/extension.cjs'), bundle:true,
  platform:'node', format:'cjs', target:'node22', external:['vscode','@napi-rs/keyring','@huggingface/transformers'],
  nodePaths:[resolve(root, 'cli/node_modules')]});
if (process.argv[2]) {
  const out = resolve(process.argv[2], 'extensions/tervory'); await mkdir(out, {recursive:true});
  for (const file of ['package.json', 'dist', 'media', 'node_modules']) await cp(resolve(base,file), resolve(out,file), {recursive:true});
  await readFile(resolve(out, 'dist/extension.cjs'));
}
