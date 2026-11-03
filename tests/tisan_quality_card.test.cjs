const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const cache = new Map();
function load(name) {
  if (cache.has(name)) return cache.get(name);
  const file = path.join(root, 'workspace/app/chats', name + '.ts');
  const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
  const out = {}; cache.set(name, out);
  new Function('require', 'exports', code)((target) => load(target.replace('./', '')), out);
  return out;
}
const { presentCard } = load('presentation');

test('the existing result rows show all four build checks and page scores', () => {
  const result = { ok: true, results: [
    { name: 'accessibility', ok: true, summary: 'desktop and mobile pages; no serious or critical violations' },
    { name: 'lighthouse', ok: true, summary: '/contact performance 0.96 accessibility 1 best-practices 1 seo 0.9' },
    { name: 'links', ok: true, summary: '16 local links/assets answered 200' },
    { name: 'secrets', ok: true, summary: '60 generated text files; no findings' },
  ] };
  const card = presentCard({ card_id: 'test', kind: 'other', summary: 'tisan.build', tool: 'tisan.build', result }, true);
  for (const row of result.results) {
    assert(card.results.some((cell) => cell.value === row.name));
    assert(card.results.some((cell) => cell.value === row.summary));
  }
});

test('the same card names a broken link on a failed build', () => {
  const card = presentCard({ card_id: 'test', kind: 'other', summary: 'tisan.build', tool: 'tisan.build', result: {
    ok: false, results: [{ name: 'links', ok: false, summary: '/contact: /missing-test-link answered 404' }],
  } }, true);
  assert(card.results.some((row) => row.value === '/contact: /missing-test-link answered 404'));
  assert(card.results.some((row) => row.label === 'Success' && row.value === 'false'));
});
