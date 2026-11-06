const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const React = require(path.join(root, 'workspace/node_modules/react'));
const jsx = require(path.join(root, 'workspace/node_modules/react/jsx-runtime'));
const {renderToStaticMarkup} = require(path.join(root, 'workspace/node_modules/react-dom/server'));
const proposed = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const scenario = process.argv[3];
const mocks = {
  react: React, 'react/jsx-runtime': jsx,
  'next/navigation': {useRouter: () => ({refresh() {}})},
  '../squad-links': {SquadLinks: () => null},
  './actions': {}, './position-actions': {}, './plugin-actions': {},
};
function load(file, extra = {}) {
  const relative = file.startsWith('workspace/') ? file : 'workspace/' + file;
  const actual = [relative, relative + '.ts', relative + '.tsx'].find(p => proposed[p] !== undefined || fs.existsSync(path.join(root, p)));
  assert.ok(actual, file);
  const source = proposed[actual] ?? fs.readFileSync(path.join(root, actual), 'utf8');
  const code = ts.transpileModule(source, {compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText;
  const exports = {};
  new Function('require', 'exports', code)(name => name in extra ? extra[name] : name in mocks ? mocks[name] : load(path.join(path.dirname(actual), name), extra), exports);
  return exports;
}
function render(component, props) {
  return renderToStaticMarkup(React.createElement(component, props));
}
function clean(html) {
  assert.doesNotMatch(html, /Fieldlight|Example|£\d|\$\d|North shop|placeholder-observation/);
  assert.doesNotMatch(html, /(?:NaN|Infinity|undefined)/);
}
async function main() {
  if (scenario === 'chart') {
    const {PriceChart} = load('app/prices/chart.tsx');
    const html = render(PriceChart, {points: []});
    assert.match(html, /<svg[^>]*aria-label="Price history"/);
    assert.equal((html.match(/<line /g) || []).length, 2);
    assert.match(html, /—/);
    assert.match(html, /The first price shows up after the next check/);
    assert.doesNotMatch(html, /<path |<circle |\d\.\d\d<\/text>/);
    clean(html);
    const measured = render(PriceChart, {points: [{ts: '2026-11-07T00:00:00Z', price: 0}]});
    assert.match(measured, /0\.00/); assert.match(measured, /<circle /);
    return;
  }
  const model = load('app/tiger/model.ts');
  const empty = model.emptyData();
  assert.equal(empty.watchedCount, 0); assert.equal(empty.changesToday, 0);
  assert.deepEqual(empty.products, []); assert.deepEqual(empty.reads, []); assert.deepEqual(empty.alerts, []);
  assert.equal(empty.example, false);
  if (['overview', 'history', 'alerts', 'watch'].includes(scenario)) {
    const {TigerApp} = load('app/tiger/view.tsx');
    const html = render(TigerApp, {data: empty, notice: '', initialTab: scenario, accountName: null});
    clean(html);
    assert.match(html, /Add a product/);
    if (scenario === 'overview') {
      assert.equal((html.match(/<b>0<\/b>/g) || []).length, 2);
      assert.match(html, /No products watched yet/); assert.match(html, /No alerts yet/);
    }
    if (scenario === 'history') {assert.match(html, /<th>When<\/th>/); assert.match(html, /data-empty="true"/); assert.match(html, /—/);}
    if (scenario === 'alerts') assert.match(html, /0 alerts/);
    if (scenario === 'watch') assert.match(html, /0 on the watch list/);
    return;
  }
  const plugins = {enabled: true, secrets: [], files: [], links: [], connections: []};
  if (['position', 'matches', 'sites'].includes(scenario)) {
    const {PositionViews} = load('app/tiger/position-views.tsx');
    const html = render(PositionViews, {data: {positions: [], matches: [], sites: []}, initialView: scenario, query: '', plugins});
    clean(html);
    assert.match(html, scenario === 'position' ? /Add a product/ : /Tiger Plugins → Source links/);
    if (scenario === 'position') {assert.match(html, /Your rank/); assert.match(html, /data-empty="true"/); assert.match(html, /—/);}
    if (scenario === 'matches') assert.match(html, /No matches to review/);
    if (scenario === 'sites') assert.match(html, /No saved sites/);
    const unavailable = render(PositionViews, {data: {positions: null, matches: null, sites: null}, initialView: scenario, query: '', plugins: null});
    assert.doesNotMatch(unavailable, /No saved sites|No matches to review|data-empty="true"/);
    return;
  }
  if (scenario === 'unknown_site_counts') {
    const {siteRows} = load('app/tiger/position-model.ts');
    const {PositionViews} = load('app/tiger/position-views.tsx');
    const rows = siteRows([{id: 'saved', url: 'https://store.example', label: 'Store', lastChecked: null}], new Date('2026-11-07'));
    const html = render(PositionViews, {data: {positions: [], matches: [], sites: rows}, initialView: 'sites', query: '', plugins});
    assert.equal((html.match(/<td class="">—<\/td>/g) || []).length, 2); assert.match(html, /<dd>—<\/dd>/);
    assert.doesNotMatch(html, /<td class="">0<\/td>|Latest site check completed/);
    clean(html);
    return;
  }
  if (['API keys', 'Files', 'Source links', 'MCP connections'].includes(scenario)) {
    const {Plugins} = load('app/tiger/plugins.tsx');
    const html = render(Plugins, {plugins, onClose() {}, initialTab: scenario});
    clean(html);
    assert.match(html, {'API keys': /Add a key/, Files: /Choose files/, 'Source links': /Add link/, 'MCP connections': /Add connection/}[scenario]);
    assert.doesNotMatch(html, /<span class="pill"><i><\/i>Connected/);
    return;
  }
  if (scenario === 'loaders') {
    const actor = {tenantId: 'tenant-zero', userId: 'user-zero', orgName: ''};
    const api = {listTigerWatches: async () => ({watches: []}), listTigerAlerts: async () => ({alerts: []}),
      listTigerObservations: async () => {throw Error('no watched pages means no history requests');}};
    const {loadTiger} = load('app/tiger/load.ts', {'@/lib/tenant': {currentTenant: async () => actor}, '@/lib/tank': api});
    assert.deepEqual((await loadTiger()).data, empty);
    const {default: PricesPage} = load('app/prices/page.tsx', {'@/lib/tenant': {currentTenant: async () => actor}, '@/lib/tank': api,
      './submit-button': {SubmitButton: ({label}) => React.createElement('button', null, label)}});
    const html = renderToStaticMarkup(await PricesPage({searchParams: Promise.resolve({})}));
    clean(html); assert.match(html, /<svg[^>]*aria-label="Price history"/);
    assert.match(html, /Nothing is being watched yet. Add a page above/);
    return;
  }
  throw Error('unknown scenario');
}
main().catch(error => {console.error(error); process.exitCode = 1;});
