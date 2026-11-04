const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(file, mocks = {}) {
  const full = path.join(root, 'workspace', file);
  const actual = fs.existsSync(full) ? full : fs.existsSync(full + '.ts') ? full + '.ts' : full + '.tsx';
  const source = fs.readFileSync(actual, 'utf8');
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX } }).outputText;
  const exported = {};
  new Function('require', 'exports', code)(name => name in mocks ? mocks[name] : load(path.join(path.dirname(file), name), mocks), exported);
  return exported;
}
const model = load('app/tiger/position-model.ts');
const now = new Date('2026-11-03T22:00:00Z');
const links = [{ id: 'saved', label: 'Saved competitor', url: 'https://competitor.example', lastChecked: null, status: 'not_checked' }];
const raw = { sku: 'sku-1', name: 'Real catalogue name', own_price: '120.00', currency: 'GBP', competitors: [] };
const fresh = { url: 'https://competitor.example/product', price: '100.00', currency: 'GBP', stock: 'InStock', checked_at: '2026-11-03T21:50:00Z' };
const watches = [{ url: fresh.url, every: '1h', enabled: true }];

test('position excludes overdue readings but retains their real last reading', () => {
  const expired = { ...fresh, url: fresh.url + '-old', price: '90.00', checked_at: '2026-11-03T14:00:00Z' };
  const rows = model.positionRows([{ ...raw, competitors: [fresh, expired] }], [...watches, { url: expired.url, every: '6h', enabled: true }], links, now);
  assert.equal(rows[0].name, raw.name);
  assert.equal(rows[0].cheapest, '£100.00'); assert.equal(rows[0].rank, '2 of 2'); assert.equal(rows[0].difference, '+£20.00 · +20%');
  assert.equal(rows[0].competitors[1].price, '£90.00'); assert.equal(rows[0].competitors[1].stale, true);
  assert.equal(rows[0].competitors[0].checked, '10 minutes ago');
});
test('ties, currency, zero denominator and unknown schedules never invent a position', () => {
  const run = (item, watch = watches[0], own = raw) => model.positionRows([{ ...own, competitors: [item] }], [watch], links, now)[0];
  assert.equal(run({ ...fresh, price: '120' }).rank, '1 of 2');
  for (const row of [run({ ...fresh, currency: 'USD' }), run(fresh, { ...watches[0], enabled: false }), run(fresh, { ...watches[0], every: 'unknown' }), run({ ...fresh, checked_at: null }), run({ ...fresh, checked_at: '2027-01-01' })]) {
    assert.equal(row.rank, '—'); assert.equal(row.cheapest, '—');
  }
  assert.equal(run({ ...fresh, price: '0' }).difference, '+£120.00');
  assert.equal(run({ ...fresh, price: 'invalid' }).competitors[0].price, null);
  assert.equal(model.positionRows([{ ...raw, competitors: [fresh] }], watches, [], now)[0].competitors.length, 0);
});
test('unsafe links and missing values cannot turn into fabricated prices or checks', () => {
  assert.equal(model.publicLink('javascript:alert(1)'), null);
  assert.equal(model.publicLink('https://user:password@competitor.example'), null);
  for (const value of [null, '', 'no price', -1, Infinity]) assert.equal(model.positionMoney(value, 'GBP'), null);
  assert.equal(model.positionMoney('100', null), null);
  const row = model.siteRows(links, now)[0];
  assert.equal(row.pages, null); assert.equal(row.matches, null); assert.equal(row.status, null); assert.equal(row.checked, null);
});
test('site counts join only saved links and keep real zero distinct from unavailable', () => {
  const rows = model.siteRows(links, now, [{ url: links[0].url, pages: 0, matches: 0, checked_at: fresh.checked_at, status: 'human_check', skipped: null }, { url: 'https://unsaved.example', pages: 999, matches: 999 }]);
  assert.equal(rows.length, 1); assert.equal(rows[0].label, links[0].label);
  assert.equal(rows[0].pages, 0); assert.equal(rows[0].matches, 0); assert.equal(rows[0].status, 'human_check');
});
test('server loader isolates failed reads and never reports them as empty matches', async () => {
  const actor = { tenantId: 'tenant-a', userId: 'user-a' };
  const calls = [];
  const mod = load('app/tiger/position-load.ts', {
    '@/lib/tenant': { currentTenant: async () => actor },
    './vault-server': { loadTigerPlugins: async () => ({ enabled: true, links }) },
    '@/lib/tank': {
      listTigerMatches: async value => { calls.push(value); throw Error('unavailable'); },
      listTigerPosition: async value => { calls.push(value); return { tenant_id: actor.tenantId, products: [{ ...raw, competitors: [fresh] }] }; },
      listTigerWatches: async value => { assert.equal(value, actor.tenantId); return { watches }; },
    },
  });
  const data = await mod.loadTigerComparison();
  assert.equal(data.matches, null); assert.equal(data.positions.length, 1); assert.equal(data.sites.length, 1);
  assert.deepEqual(calls, [actor, actor]);
});
test('foreign tenant responses never enter the views', async () => {
  const mod = load('app/tiger/position-load.ts', {
    '@/lib/tenant': { currentTenant: async () => ({ tenantId: 'tenant-a', userId: 'user-a' }) },
    './vault-server': { loadTigerPlugins: async () => ({ enabled: false, links: [] }) },
    '@/lib/tank': { listTigerMatches: async () => ({ tenant_id: 'tenant-b', matches: [] }), listTigerPosition: async () => ({ tenant_id: 'tenant-b', products: [] }), listTigerWatches: async () => ({ watches }) },
  });
  const data = await mod.loadTigerComparison();
  assert.equal(data.matches, null); assert.equal(data.positions, null); assert.equal(data.sites, null);
});
test('server action takes identity only from the current session and validates input first', async () => {
  const calls = []; let reads = 0;
  const actor = { tenantId: 'tenant-a', userId: 'user-a' };
  const mod = load('app/tiger/position-actions.ts', {
    'next/cache': { revalidatePath: value => calls.push(value) },
    '@/lib/tenant': { currentTenant: async () => { reads++; return actor; } },
    '@/lib/tank': { decideTigerMatch: async (...args) => { calls.push(args); return { id: args[1], state: 'suggested' }; } },
  });
  assert.deepEqual(await mod.decideMatch('not-a-uuid', 'undo'), { ok: false }); assert.equal(reads, 0);
  const id = '00000000-0000-4000-8000-000000000001';
  assert.equal((await mod.decideMatch(id, 'undo')).ok, true);
  assert.deepEqual(calls, [[actor, id, 'undo'], '/tiger']);
});
test('Tank helper uses durable proposals and confirmations without a model turn', async () => {
  const previousFetch = global.fetch, previousUrl = process.env.TANK_URL, priorKey = process.env.TANK_API_KEY;
  process.env.TANK_URL = 'http://placeholder.invalid'; process.env.TANK_API_KEY = 'placeholder-service-key';
  const actor = { tenantId: 'tenant-a', userId: 'user-a' }, id = '00000000-0000-4000-8000-000000000001';
  const calls = [];
  const answers = [{ thread_id: 'thread-id' }, { card_id: 'card-id' }, { status: 'confirmed', result: { match: { id, tenant_id: actor.tenantId, state: 'suggested' } } }];
  global.fetch = async (url, init) => { calls.push({ path: new URL(url).pathname, headers: new Headers(init.headers), body: JSON.parse(init.body) }); return Response.json(answers.shift()); };
  try {
    const api = load('lib/tank.ts', { '@/app/api/zenas/tank': {} });
    assert.equal((await api.decideTigerMatch(actor, id, 'undo')).state, 'suggested');
    assert.deepEqual(calls.map(c => c.path), ['/v1/command/threads', '/v1/command/threads/thread-id/actions', '/v1/command/cards/card-id']);
    assert.deepEqual(calls[1].body, { tool: 'tiger.match.undo', arguments: { match_id: id } });
    assert.deepEqual(calls[2].body, { action: 'confirm' });
    for (const call of calls) { assert.equal(call.headers.get('x-tervory-tenant'), actor.tenantId); assert.equal(call.headers.get('x-tervory-user'), actor.userId); }
  } finally {
    global.fetch = previousFetch;
    if (previousUrl === undefined) delete process.env.TANK_URL;
    else process.env.TANK_URL = previousUrl;
    if (priorKey === undefined) delete process.env.TANK_API_KEY;
    else process.env.TANK_API_KEY = priorKey;
  }
});
test('frame-only examples never appear in production Tiger sources', () => {
  const folder = path.join(root, 'workspace/app/tiger');
  const source = fs.readdirSync(folder).filter(name => /\.(tsx?|css)$/.test(name)).map(name => fs.readFileSync(path.join(folder, name), 'utf8')).join('\n');
  assert.ok(!/North shop|East shop|West shop|Fieldlight|north-shop\.example|FL-DL01/.test(source));
});
test('an unframed site outcome never claims a successful check', () => {
  const React = require(path.join(root, 'workspace/node_modules/react'));
  const { renderToStaticMarkup } = require(path.join(root, 'workspace/node_modules/react-dom/server'));
  const { PositionViews } = load('app/tiger/position-views.tsx', {
    react: React, 'react/jsx-runtime': require(path.join(root, 'workspace/node_modules/react/jsx-runtime')),
    'next/navigation': { useRouter: () => ({ refresh() {} }) }, './plugins': {}, './position-actions': {},
  });
  const row = { ...model.siteRows(links, now)[0], checkedAt: fresh.checked_at, checked: '10 minutes ago' };
  const html = renderToStaticMarkup(React.createElement(PositionViews, { data: { positions: [], matches: [], sites: [row] }, initialView: 'sites', query: '', plugins: null }));
  assert.ok(!html.includes('<time') && !html.includes('Latest site check completed.'));
});
