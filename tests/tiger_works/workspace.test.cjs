const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(file, mocks = {}) {
  const source = fs.readFileSync(path.join(root, 'workspace', file), 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
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
  const before = { id: 'before', url: watch.url, ts: '2026-10-26T11:00:00Z', method: 'jsonld', product_name: 'Fixture product', price: '120.00', currency: 'USD', availability: 'InStock' };
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
    assert.equal(row.price, null);
    assert.equal(row.stock, null);
    assert.equal(row.url, watch.url);
    assert.equal(row.attemptedAt, attempt.ts);
    assert.equal(row.checked, 'Oct 26, 12:00 PM UTC');
    assert.equal(row.alertOn, 'Stock');
    assert.equal(result.reads.find(row => row.id === 'attempt').price, null);
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

const { fromTiger: present, emptyData } = load('app/tiger/model.ts');
const watch = { id: 'watch', url: 'https://shop.example/product', label: 'Untitled page', every: '1h' };
const observation = { id: 'o', url: watch.url, ts: '2026-10-26T12:00:00Z', product_name: 'Desk lamp', last_product_name: 'Desk lamp', price: '24.00', currency: 'EUR', availability: 'InStock', method: 'jsonld' };
for (const [field, value, reason] of [
  ['product_name', null, "the product name wasn't found on the page"],
  ['product_name', ' ', "the product name wasn't found on the page"],
  ['price', null, 'the page layout changed'],
  ['price', '', 'the page layout changed'],
  ['price', 'invalid', 'the page layout changed'],
  ['availability', null, 'the page layout changed'],
  ['currency', null, "the currency wasn't found on the page"],
  ['currency', '', "the currency wasn't found on the page"],
  ['ts', '', "the attempt time wasn't recorded"],
  ['ts', 'invalid', "the attempt time wasn't recorded"],
]) test(`missing or invalid ${field}: ${JSON.stringify(value)} is flagged`, () => {
  const data = present([watch], [{ ...observation, [field]: value }], []);
  assert.equal(data.products[0].reason, reason);
  assert.equal(data.products[0].price, null);
  assert.equal(data.reads[0].price, null);
  assert.equal(data.reads[0].reason, reason);
  assert.ok(!JSON.stringify(data).includes('Untitled page'));
});
test('a nameless first attempt uses the URL; a later failure keeps the read name', () => {
  const failed = { ...observation, product_name: null, last_product_name: null, issue: 'missing_name', price: null, method: 'unread' };
  const first = present([watch], [failed], []).products[0];
  assert.equal(first.name, null); assert.equal(first.url, watch.url); assert.equal(first.attemptedAt, failed.ts);
  const carried = present([watch], [{ ...failed, last_product_name: 'Desk lamp' }], []).products[0];
  assert.equal(carried.name, 'Desk lamp'); assert.equal(carried.reason, "the product name wasn't found on the page");
  assert.equal(present([watch], [], []).products[0].name, null);
});
test('missing page and schedule are explicit row errors', () => {
  for (const [change, reason] of [[{ url: '' }, "the page link wasn't recorded"], [{ every: null }, "the check interval wasn't recorded"]]) {
    const row = present([{ ...watch, ...change }], [observation], []).products[0];
    assert.equal(row.reason, reason); assert.equal(row.price, null);
  }
});
test('failed observation loads do not masquerade as never checked', async () => {
  const mod = load('app/tiger/load.ts', {
    '@/lib/tenant': { currentTenant: async () => ({ tenantId: 'tenant-a' }) },
    '@/lib/tank': { listTigerWatches: async () => ({ watches: [watch] }), listTigerAlerts: async () => ({ alerts: [] }), listTigerObservations: async () => { throw new Error('internal failure'); } },
  });
  const data = (await mod.loadTiger()).data;
  assert.equal(data.products[0].reason, "the latest check couldn't be loaded");
  assert.equal(data.products[0].price, null);
});
test('missing alert values and currencies are flagged rather than guessed', () => {
  const alert = { id: 'a', url: watch.url, ts: '2026-10-26T12:01:00Z', kind: 'price', before: '24.00', after: '23.00' };
  for (const change of [{ before: null }, { after: null }, { kind: '' }, { ts: '' }, { url: '' }]) {
    const row = present([watch], [observation], [{ ...alert, ...change }]).alerts[0];
    assert.match(row.change, /^Not checked — /); assert.equal(row.before, null); assert.equal(row.now, null);
  }
  const missingName = present([watch], [{ ...observation, product_name: null, last_product_name: null }], [alert]).alerts[0];
  assert.equal(missingName.reason, "the product name wasn't found on the page");
  assert.equal(missingName.product, null); assert.equal(missingName.now, null);
  const missingCurrency = present([watch], [{ ...observation, currency: null }], [alert]).alerts[0];
  assert.equal(missingCurrency.reason, "the alert details weren't recorded");
  assert.equal(missingCurrency.now, null);
  assert.equal(present([watch], [observation], [alert]).alerts[0].now, 'EUR 23.00');
});

for (const result of [{}, { observations: null }]) test('missing observation collection is flagged', async () => {
  const mod = load('app/tiger/load.ts', {
    '@/lib/tenant': { currentTenant: async () => ({ tenantId: 'tenant-a' }) },
    '@/lib/tank': { listTigerWatches: async () => ({ watches: [watch] }), listTigerAlerts: async () => ({ alerts: [] }), listTigerObservations: async () => result },
  });
  assert.equal((await mod.loadTiger()).data.products[0].reason, "the latest check couldn't be loaded");
});
test('missing account name renders an explicit status, and nameless rows render links in every section', () => {
  const React = require(path.join(root, 'workspace/node_modules/react'));
  const { renderToStaticMarkup } = require(path.join(root, 'workspace/node_modules/react-dom/server'));
  const { TigerApp } = load('app/tiger/view.tsx', {
    react: React,
    'react/jsx-runtime': require(path.join(root, 'workspace/node_modules/react/jsx-runtime')),
    './actions': {}, '../squad-links': { SquadLinks: () => null },
  });
  const data = present([watch], [{ ...observation, product_name: null, last_product_name: null }], []);
  for (const initialTab of ['overview', 'watch', 'history']) {
    const html = renderToStaticMarkup(React.createElement(TigerApp, { data, initialTab, accountName: null, notice: '' }));
    assert.match(html, /role="status">Account name could not be loaded\./);
    assert.ok(html.includes(`href="${watch.url}"`));
    assert.ok(html.includes("the product name wasn&#x27;t found on the page"));
    assert.ok(!html.includes('Untitled page') && !html.includes('Your account') && !html.includes('24.00'));
  }
});
