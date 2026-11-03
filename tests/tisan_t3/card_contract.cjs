const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('../../workspace/node_modules/typescript');
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true}
}).outputText, filename);
const {presentCard} = require('../../workspace/app/chats/presentation.ts');
for (const founder of [false, true]) {
  for (const tool of ['tisan.preview', 'tisan.feedback', 'tisan.handover']) {
    const card = presentCard({card_id: 'placeholder-card', kind: 'other', tool, summary: tool,
      arguments: {slug: 'placeholder-site'},
      result: {request_id: 'placeholder-hidden-request', commit: 'placeholder-hidden-commit',
        memory_id: 'placeholder-hidden-memory', checks: [{name: 'placeholder-hidden-check', ok: true}],
        build_id: 2, url: 'https://placeholder-stage.test/', status: 'changes_requested'}}, founder);
    assert.deepEqual(card.targets, [{label: 'Site', value: 'placeholder-site'}]);
    assert.deepEqual(card.results, [
      {label: 'Status', value: 'changes_requested'},
      {label: 'Result', value: 'https://placeholder-stage.test/', href: 'https://placeholder-stage.test/'},
      {label: 'Build', value: '2'}]);
    assert(!JSON.stringify(card).includes('placeholder-hidden'));
  }
}
console.log('6 existing-card projections passed; hidden fields excluded');
