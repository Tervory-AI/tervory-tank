// Offline regression tests. These mocks are never product code or signed-in proof.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const workspaceRequire = createRequire(path.join(root, 'workspace/package.json'));
const ts = workspaceRequire('typescript');
let tenant = 'tenant-a';
let signedIn = true;
let records = [];
const calls = [];
const store = new Map();
const mocks = {
  '@/lib/tenant': { currentTenant: async () => {
    if (!signedIn) throw new Error('unauthenticated');
    return { tenantId: tenant, userId: 'test-user' };
  } },
  'next/cache': { revalidatePath: () => {} },
};
const cache = new Map();
function load(relative) {
  const file = path.resolve(root, relative);
  if (cache.has(file)) return cache.get(file);
  const compiled = ts.transpileModule(fs.readFileSync(file, 'utf8'), { compilerOptions: {
    jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022,
  } }).outputText;
  const module = { exports: {} };
  const requireFile = (name) => {
    if (mocks[name]) return mocks[name];
    if (name === '@/lib/tank') return load('workspace/lib/tank.ts');
    if (name.startsWith('.')) return load(path.relative(root, path.resolve(path.dirname(file), name + '.ts')));
    return workspaceRequire(name);
  };
  new Function('require', 'module', 'exports', compiled)(requireFile, module, module.exports);
  cache.set(file, module.exports);
  return module.exports;
}
const record = (id, changes = {}) => ({ id, task_id: null, batch: 'shared-name', raw: { name: `Business ${id}` },
  profile: { name: { value: `Business ${id}`, source: 'input' }, website: { value: 'https://business.example/', source: 'input:verified' },
    phone: { value: '(617) 555-0100', source: 'site' }, emails: { value: ['contact@business.example'], source: 'site' } },
  passes: { '2b': { gold_observation: { source_url: 'https://business.example/contact', observed_on: '2026-10-26', status: 200, blocked: false } },
    '7': { checks: { phone_matches_site: true } } },
  status: 'done', confidence: 70, error: null, created_at: '2026-10-26T00:00:00Z', ...changes });
global.fetch = async (input, init) => {
  const url = new URL(input);
  const body = init?.body ? JSON.parse(init.body) : null;
  calls.push({ path: url.pathname, tenant: url.searchParams.get('tenant_id'), body });
  if (url.pathname === '/v1/base/run') {
    assert.equal(body.tenant_id, tenant);
    assert.equal(body.preview, false);
    assert.equal(body.engine, null);
    store.set(body.tenant_id, body.records.map((raw, i) => record(String(i), { raw, batch: body.batch, status: 'queued', profile: {}, passes: {} })));
    return Response.json({ records: body.records.length, task: { id: 'task' }, tasks: [], batches: 1, skills: {} });
  }
  if (url.pathname === '/v1/skala') return Response.json([]);
  const requested = url.searchParams.get('tenant_id');
  assert.equal(requested, tenant, 'Never read the platform tenant or a caller-supplied tenant');
  if (url.pathname === '/v1/base/batches') return Response.json(requested === 'tenant-a'
    ? [{ batch: 'shared-name', started: '2026-10-26', total: 10, done: 10, failed: 0, pending: 0, with_site: 10, with_email: 10 }]
    : []);
  if (url.pathname === '/v1/base/records') {
    const requestedBatch = url.searchParams.get('batch');
    const items = (store.get(requested) || []).filter((item) => !requestedBatch || item.batch === requestedBatch);
    const offset = Number(url.searchParams.get('offset'));
    return Response.json(items.slice(offset, offset + Number(url.searchParams.get('limit'))));
  }
  throw new Error('Unexpected endpoint');
};
(async () => {
  const csv = load('workspace/app/base/csv.ts');
  assert.deepEqual(csv.parseBusinessCsv('\uFEFFname,website\r\n"One, Inc.",https://one.example\r\n"Two ""and"" Co.",https://two.example'),
    [{ name: 'One, Inc.', website: 'https://one.example' }, { name: 'Two "and" Co.', website: 'https://two.example' }]);
  for (const invalid of ['name,name\na,b', 'website\nx', 'name\n"open', 'name,website\na', 'name\n' + 'x\n'.repeat(1001)]) {
    assert.throws(() => csv.parseBusinessCsv(invalid));
  }
  assert.equal(csv.csvCell('=1+1'), "'=1+1");
  for (const phone of ['+15125550101', '+442079460018', '15125550101']) assert.equal(csv.csvCell(phone), phone);
  for (const formula of ['=HYPERLINK("https://evil.example/","click")', '+SUM(1,2)', '-1+2', '@SUM(1,2)', '  =1+1']) {
    const exported = csv.csvCell(formula);
    const parsed = csv.parseBusinessCsv('name,phone\nExample,' + exported);
    assert.equal(parsed[0].phone, "'" + formula);
  }
  for (const heading of ['__proto__', 'constructor', 'prototype']) assert.throws(() => csv.parseBusinessCsv('name,' + heading + '\nExample,test'));
  const display = load('workspace/app/base/display.ts');
  assert.equal(display.dateLabel('2026-10-26T23:44:00+00:00'), '26 Oct 2026, 4:44 pm');
  assert.equal(display.dateLabel('2026-10-26'), '26 Oct 2026');
  assert.equal(display.dateLabel(null), 'Date not recorded');
  assert.equal(display.selectionLabel('CA', 'unspecified'), 'California, licence type not given');
  assert.equal(display.countLabel(1, 'call'), '1 call');
  assert.equal(display.countLabel(2, 'call'), '2 calls');
  assert.equal(display.receiptLabel({vendor: 'brave.search', rung: 1}), 'Web search');
  assert.equal(display.costStep({vendors: ['brave.search'], rung: 1}), 'Web search');
  assert.equal(display.reasonLabel('blocked'), 'This website does not allow automatic reads. We stopped checking it.');
  assert(!display.refreshLabel('unavailable').includes('unavailable'));
  const trend = load('workspace/app/base/cost-trend.ts').costTrend([
    {state: 'TX', month: '2026-09', cost_per_verified_record: '0.002', unpriced: 0},
    {state: 'TX', month: '2026-10', cost_per_verified_record: '0.000792', unpriced: 1},
  ]);
  assert.equal(trend[1].cost, 0.000792);
  assert.equal(trend[1].unpriced, 1);
  assert.equal(trend[1].change, '$0.001208 less than September 2026');

  assert.equal(csv.csvCell('a,"b"'), '"a,""b"""');

  const React = workspaceRequire('react');
  const {renderToStaticMarkup} = workspaceRequire('react-dom/server');
  mocks['next/link'] = {default: ({children, ...props}) => React.createElement('a', props, children)};
  const {FounderConsole} = load('workspace/app/admin/console.tsx');
  const metric = {calls: 2, unpriced_calls: 1, spend_usd: 0.000792, booked_usd: 1, outcomes: 1, margin_pct: 99.92,
    cost_per_outcome: 0.000792, proven_pct: 0, off_paid_pct: 0, independence_pct: 0};
  const rendered = renderToStaticMarkup(React.createElement(FounderConsole, {
    days: 30, counters: {note: 'Fixture', routes: [], lifetime: metric, last_30_days: metric, change: metric},
    taskSeries: {points: [{...metric, key: 'base.find_site', day: '2026-10-26', calls_by_rung: {'1': 2}}], totals: [{...metric, key: 'base.find_site'}]},
    agentSeries: {totals: [{...metric, key: 'base'}]}, focus: [], graduations: [], prices: [], ladders: [], savePrice: async () => null, setAutoPromote: async () => {},
  }));
  assert(rendered.includes('Daily priced costs and margins'));
  assert(rendered.includes('$0.000792') && rendered.includes('99.9%'));
  assert(rendered.includes('excludes 1 unpriced call') && !rendered.includes('excludes 1 unpriced calls'));
  assert(rendered.includes('/admin/unpriced?day=2026-10-26'));
  assert(rendered.includes('/admin/unpriced?days=30&amp;task=base.find_site'));
  const proof = load('workspace/app/base/evidence.ts');
  assert.equal(proof.resultStatus(record('1')).status, 'verified');
  for (const observation of [{}, { source_url: 'javascript:alert(1)', observed_on: '2026-10-26', status: 200, blocked: false },
    { source_url: 'https://business.example', observed_on: '2026-02-31', status: 200, blocked: false },
    { source_url: 'https://business.example', observed_on: '2026-10-26', status: 200, blocked: true }]) {
    assert.equal(proof.resultStatus(record('1', { passes: { '2b': { gold_observation: observation }, '7': { checks: {} } } })).status, 'failed');
  }
  assert.equal(proof.resultStatus(record('1', { passes: { ...record('1').passes, '7': { checks: { phone_matches_site: false } } } })).status, 'failed');
  const batchData = load('workspace/app/base/batch-data.ts');
  const unverifiedFields = record('input-fields', { profile: {
    name: { value: 'Input name', source: 'input' }, website: { value: 'https://business.example', source: 'input:verified' },
    phone: { value: 'unconfirmed phone', source: 'input' }, emails: { value: ['guess@business.example'], source: 'pattern' },
    description: { value: 'Unconfirmed estimate', source: 'site:model' },
  }, passes: { ...record('x').passes, '7': { checks: {} } } });
  const safeFields = batchData.resultRow(unverifiedFields);
  assert.equal(safeFields.phone, '');
  assert.equal(safeFields.emails, '');
  assert.equal(safeFields.description, '');
  assert.match(proof.resultStatus(record('blocked', { passes: { '2b': { error: 'blocked by human check' } } })).reason, /human access/);
  const blocked = record('blocked-url', { passes: { '2b': { error: 'blocked', access_error: {
    status: 'blocked', url: 'https://business.example/contact', next: 'client_connection',
  } } } });
  assert.deepEqual(batchData.resultRow(blocked).blockedUrls, ['https://business.example/contact']);
  assert.equal(batchData.resultRow(blocked).status, 'failed');
  assert.equal(batchData.verifiedCsv([batchData.resultRow(blocked)]).trim().split('\r\n').length, 1);
  assert.match(proof.resultStatus(record('archived', { passes: { '2b': { archive_date: '2020-01-01' } } })).reason, /archived/);
  assert.match(proof.resultStatus(record('timeout', { status: 'failed', error: 'request timed out' })).reason, /respond in time/);
  const actions = load('workspace/app/base/job-actions.ts');
  const download = load('workspace/app/base/download/route.ts');
  const page = load('workspace/app/base/load.ts');
  const data = new FormData();
  data.set('tenant_id', 'forged-tenant');
  data.set('preview', 'true');
  data.set('engine', 'forged-engine');
  data.set('name', 'Our businesses');
  data.set('file', new File(['name,website\n' + Array.from({ length: 10 }, (_, i) => `Business ${i},https://business.example`).join('\n')], 'businesses.csv'));
  signedIn = false;
  assert.equal((await actions.uploadBaseCsv(data)).ok, false);
  assert.equal((await download.GET(new Request('https://app.example/base/download?batch=shared-name'))).status, 401);
  assert.equal(calls.length, 0);
  signedIn = true;
  const queued = await actions.uploadBaseCsv(data);
  assert.equal(queued.ok, true);
  assert.equal(queued.rows, 10);
  assert.equal(calls[0].body.tenant_id, 'tenant-a');
  assert.equal((await actions.baseBatchStatus(queued.batch)).result.pending, 10);
  assert.equal((await download.GET(new Request('https://app.example/base/download?batch=' + encodeURIComponent(queued.batch)))).status, 307);
  store.set('tenant-a', Array.from({ length: 10 }, (_, i) => record(String(i), { batch: queued.batch })));
  const checked = await actions.baseBatchStatus(queued.batch);
  assert.equal(checked.result.total, 10);
  assert.equal(checked.result.verified, 10);
  const response = await download.GET(new Request('https://app.example/base/download?tenant_id=forged&batch=' + encodeURIComponent(queued.batch)));
  assert.equal(response.status, 307);
  const target = new URL(response.headers.get('location'));
  assert.equal(target.pathname, '/base/product/records.csv');
  assert.equal(target.searchParams.get('batch'), queued.batch);
  assert.equal(target.searchParams.has('tenant_id'), false);
  assert.equal(target.searchParams.get('metric'), 'attempted');
  records = store.get('tenant-a');
  records[1] = record('1', { batch: queued.batch, passes: {} });
  records[2] = record('2', { batch: queued.batch, status: 'failed' });
  const partial = await actions.baseBatchStatus(queued.batch);
  assert.equal(partial.result.verified, 8);
  assert.equal(partial.result.failed, 2);
  assert.equal(partial.result.reasons.length, 2);
  assert.equal((await page.loadBase()).batches.length, 1);
  tenant = 'tenant-b';
  assert.equal((await page.loadBase()).batches.length, 0);
  assert.equal((await actions.baseBatchStatus(queued.batch)).ok, false);
  // The redirect carries no caller tenant; the product route derives it from the session.
  assert.equal(new URL((await download.GET(new Request('https://app.example/base/download?tenant_id=tenant-a&batch=' + encodeURIComponent(queued.batch)))).headers.get('location')).searchParams.has('tenant_id'), false);
  assert.ok(!calls.some((call) => call.tenant === '00000000-0000-0000-0000-000000000001'));
  tenant = 'tenant-a';
  store.set(tenant, Array.from({ length: 1001 }, (_, i) => record(String(i))));
  assert.equal((await actions.baseBatchStatus('shared-name')).result.total, 1001);
  assert.equal((await actions.baseBatchStatus('shared-name')).result.rows.length, 100);
  const repeated = store.get(tenant);
  repeated[1000] = repeated[999];
  assert.equal((await actions.baseBatchStatus('shared-name')).ok, false);
  assert.equal((await download.GET(new Request('https://app.example/base/download'))).status, 400);
  console.log('Base upload, polling, export, CSV safety, evidence and two-tenant isolation checks passed.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
