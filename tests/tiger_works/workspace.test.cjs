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
test('failed checks keep their reason, attempt time and link without a price or internal evidence', () => {
  const { fromTiger, sectionFrom, SECTIONS, searchTiger } = load('app/tiger/model.ts');
  const watch = { id: 'watch', url: 'https://www.adafruit.com/product/4296', label: 'Page', every: '1h', alert_price: false, alert_stock: true };
  const before = { id: 'before', url: watch.url, ts: '2026-10-26T11:00:00Z', method: 'jsonld', price: '120.00', currency: 'USD', availability: 'InStock' };
  const pending = fromTiger([watch], [], []).products[0];
  assert.equal(pending.status, 'Not checked');
  assert.equal(pending.reason, null);
  assert.equal(pending.attemptedAt, null);
  assert.equal(sectionFrom('unread'), 'overview');
  assert.deepEqual(SECTIONS.map(row => row.id), ['overview', 'alerts', 'watch', 'history']);
  const cases = [
    ['blocked', {}, 'the store blocked automated checks'],
    ['captcha', {}, 'the store blocked automated checks'],
    ['robots', {}, 'the store blocked automated checks'],
    ['error', {}, "the page didn't load"],
    ['timeout', {}, "the page didn't load"],
    ['none', {}, 'the page layout changed'],
    ['unread', {}, 'the page layout changed'],
    ['jsonld', { price: null }, 'the page layout changed'],
    ['jsonld', { availability: null }, 'the page layout changed'],
    ['jsonld', { availability: "can't read" }, 'the page layout changed'],
    ['jsonld', { availability: 'Ships today' }, 'the page layout changed'],
  ];
  for (const [method, changes, reason] of cases) {
    const attempt = { ...before, id: 'attempt', ts: '2026-10-26T12:00:00Z', price: '115.00', method, evidence: 'INTERNAL_BROWSER_FAILURE', ...changes };
    const result = fromTiger([watch], [before, attempt], []);
    const row = result.products[0];
    assert.equal(row.status, 'Not checked');
    assert.equal(row.reason, reason);
    assert.equal(row.price, '—');
    assert.equal(row.stock, '—');
    assert.equal(row.url, watch.url);
    assert.equal(row.attemptedAt, attempt.ts);
    assert.equal(row.checked, 'Oct 26, 12:00 PM UTC');
    assert.equal(row.alertOn, 'Stock');
    assert.deepEqual(result.reads.map(row => row.id), ['before']);
    assert.equal(searchTiger(result, reason).products.length, 1);
    assert.ok(!JSON.stringify(result).includes('INTERNAL_BROWSER_FAILURE'));
    assert.ok(!JSON.stringify(result).includes('115.00'));
    assert.equal(result.alerts.length, 0);
  }
  const recovered = fromTiger([watch], [before, { ...before, id: 'recovered', ts: '2026-10-26T13:00:00Z', price: '115.00', availability: 'out_of_stock' }], []).products[0];
  assert.equal(recovered.status, 'Read');
  assert.equal(recovered.reason, null);
  assert.equal(recovered.price, '$115.00');
  assert.equal(recovered.stock, 'Out of stock');
});
