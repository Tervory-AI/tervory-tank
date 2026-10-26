const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(file, mocks = {}) {
  const source = fs.readFileSync(path.join(root, 'workspace', file), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
  const exported = {};
  new Function('require', 'exports', code)(name => {
    if (name in mocks) return mocks[name];
    return load(path.join(path.dirname(file), name + '.ts'), mocks);
  }, exported);
  return exported;
}
test('form sends both checkbox choices, including unchecked price', async () => {
  for (const price of [true, false]) for (const stock of [true, false]) {
    const calls = [];
    const actions = load('app/tiger/actions.ts', {
      'next/navigation': { redirect: url => { throw new Error('redirect:' + url); } },
      '@/lib/tenant': { currentTenant: async () => ({ tenantId: 'tenant-a' }) },
      '@/lib/tank': { createTigerWatch: async (...args) => calls.push(args) },
    });
    const data = new FormData();
    data.set('url', 'https://www.adafruit.com/product/4296'); data.set('every', '1h');
    if (price) data.set('price', 'on'); if (stock) data.set('stock', 'on');
    await assert.rejects(actions.addProduct(data), /redirect:\/tiger\?tab=watch$/);
    assert.equal(calls[0][0], 'tenant-a');
    assert.equal(calls[0][1].alert_price, price); assert.equal(calls[0][1].alert_stock, stock);
    assert.equal(calls[0][1].threshold, 0);
  }
});
test('unread results retain the URL without exposing internal evidence', () => {
  const { fromTiger } = load('app/tiger/model.ts');
  const watch = { id: 'watch', url: 'https://www.adafruit.com/product/4296', label: 'Page', every: '1h', alert_price: false, alert_stock: true };
  assert.equal(fromTiger([watch], [], []).products[0].status, 'Not checked');
  for (const method of ['error', 'none', 'unread', 'blocked', 'robots']) {
    const result = fromTiger([watch], [{ id: 'obs', url: watch.url, ts: '2026-10-26T12:00:00Z', method, evidence: 'INTERNAL_BROWSER_FAILURE' }], []);
    assert.equal(result.products[0].status, "Can't read");
    assert.equal(result.products[0].alertOn, 'Stock');
    assert.equal(result.unread[0].url, watch.url);
    assert.ok(!JSON.stringify(result).includes('INTERNAL_BROWSER_FAILURE'));
  }
});
