const fs = require('node:fs');
const assert = require('node:assert/strict');
const ts = require('../workspace/node_modules/typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText, filename);
const {presentCard} = require('../workspace/app/chats/presentation.ts');
for (const [tool, result, values] of [
  ['autumbra.fixes', {items: [{name: 'placeholder-package', summary: '1.0 → 1.1 · placeholder-advisory · placeholder-match', status: 'high'}]}, ['placeholder-package', 'placeholder-match', 'high']],
  ['autumbra.blocks', {items: [{name: '45.33.32.156', status: 'published', summary: 'placeholder-record'}]}, ['45.33.32.156', 'published', 'placeholder-record']],
  ['autumbra.enforce.create', {name: 'placeholder-project', status: 'created', summary: 'AUTUMBRA_HEALTH_SECRET'}, ['placeholder-project', 'created', 'AUTUMBRA_HEALTH_SECRET']],
  ['autumbra.fix.approve', {status: 'opened', pr_url: 'https://github.com/Tervory-AI/tervory-tank/pull/999999'}, ['opened', '/999999']],
]) {
  const rendered = presentCard({card_id: 'placeholder-card', tool, summary: tool, status: 'confirmed', result}, true);
  const text = JSON.stringify(rendered.results);
  for (const value of values) assert(text.includes(value), tool + ': missing ' + value);
}
console.log('4 existing-card projections passed');
