// Offline proof that Apollo results use existing card labels and collections.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const req = createRequire(path.join(root, 'workspace/package.json'));
const ts = req('typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, filename);
const {presentCard} = require('../workspace/app/chats/presentation.ts');
for (const founder of [false, true]) {
  const summary = JSON.stringify({matched: 1, base_only: 2, apollo_only: 3, field_agreement: {website: {matches: 1}}});
  const card = presentCard({card_id: 'placeholder', summary: 'placeholder', tool: 'base.compare.apollo', kind: 'other', status: 'confirmed', result: {
    total: 6, cost_usd: 0, summary, records: [{name: 'placeholder business', status: 'matched', summary: '{"website":"matches"}'}],
  }}, founder);
  for (const [label, value] of [['Total', '6'], ['Cost', '$0.00'], ['Summary', summary]]) {
    assert(card.results.some(item => item.label === label && item.value === value), label);
  }
  assert(card.results.some(item => item.label === 'Records'));
}
console.log('Apollo comparison uses existing Total, Cost, Summary and Records labels.');
