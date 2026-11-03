// Offline checks of the existing list card labels; no live workspace or network.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const req = createRequire(path.join(root, 'workspace/package.json'));
const ts = req('typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, filename);
const {presentCard} = require('../workspace/app/chats/presentation.ts');
for (const founder of [false, true]) for (const tool of ['base.list.show', 'base.list.export']) {
  const result = {actual_usd: 0.30000003, baseline_usd: 0.70000007, saved_usd: 0.40000004, calls: 2, receipt_status: 'priced'};
  const make = values => presentCard({card_id: 'placeholder', summary: 'placeholder', tool, kind: 'other', status: 'confirmed', result: values}, founder);
  let card = make(result);
  for (const [label, value] of [['Cost', '$0.30'], ['Would have cost', '$0.70'], ['Saved', '$0.40'], ['Calls', '2'], ['Cost status', 'priced']]) {
    assert.equal(card.results.filter(item => item.label === label).length, 1);
    assert(card.results.some(item => item.label === label && item.value === value));
  }
  card = make({...result, actual_usd: null, saved_usd: null, receipt_status: 'price not set'});
  assert(card.results.some(item => item.label === 'Cost' && item.value === 'Unavailable'));
  assert(card.results.some(item => item.label === 'Saved' && item.value === 'Unavailable'));
  assert(card.results.some(item => item.label === 'Cost status' && item.value === 'price not set'));
  card = make({...result, baseline_usd: null, saved_usd: null});
  assert(card.results.some(item => item.label === 'Would have cost' && item.value === 'Unavailable'));
  assert(card.results.some(item => item.label === 'Saved' && item.value === 'Unavailable'));
}
console.log('Saved-list Cost, Would have cost, Saved, Calls and Cost status use existing labels; unknown prices stay unavailable.');
