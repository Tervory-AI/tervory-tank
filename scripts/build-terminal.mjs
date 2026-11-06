import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
import {readFileSync, writeFileSync} from 'node:fs';
const require = createRequire(new URL('./browser-check/package.json', import.meta.url));
const {build} = require('esbuild');
const root = fileURLToPath(new URL('../', import.meta.url));
await build({entryPoints: [root + 'agents/rig/rigbox/three_d/terminal-runtime.mjs'],
  outfile: root + 'agents/rig/rigbox/three_d/widget/terminal-runtime.js', bundle: true, format: 'esm',
  minify: true, legalComments: 'inline', target: 'es2020',
  nodePaths: [root + 'scripts/browser-check/node_modules'],
  plugins: [{name: 'secure-three-identifiers', setup(builder) {
    builder.onLoad({filter: /three\/(?:build\/three\.module|src\/math\/MathUtils)\.js$/}, async ({path}) => {
      const original = readFileSync(path, 'utf8');
      const contents = original.replace(/function generateUUID\(\) \{[\s\S]*?\n\}/,
        'function generateUUID() { return globalThis.crypto.randomUUID(); }');
      if (contents === original) throw Error('Pinned Three UUID implementation changed');
      return {contents, loader: 'js'};
    });
  }}]});
// Three's embedded GLSL includes trailing whitespace; normalize the generated
// artifact without changing shader tokens or line boundaries.
const artifact = root + 'agents/rig/rigbox/three_d/widget/terminal-runtime.js';
writeFileSync(artifact, readFileSync(artifact, 'utf8').replace(/[\t ]+$/gm, ''));
