const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const Module = require('node:module');
const root = path.resolve(__dirname, '../workspace');
const ts = require(root + '/node_modules/typescript');
const React = require(root + '/node_modules/react');
const {renderToStaticMarkup} = require(root + '/node_modules/react-dom/server');
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (module, filename) => {
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX},
  }).outputText, filename);
};
require.extensions['.css'] = () => {};
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, ...rest) {
  return resolve.call(this, name.startsWith('@/') ? root + '/' + name.slice(2) : name, ...rest);
};
const originalLoad = Module._load;
Module._load = function(name, ...rest) {
  if (name === 'server-only') return {};
  if (name === 'next/link') return {default: ({children, ...props}) => React.createElement('a', props, children)};
  if (name === '@/lib/trigger-signin-fetch') return {signinFetch: (...args) => global.fetch(...args)};
  if (name === '@/lib/autumbra-receipts-access') return {mayReadWeeklyReceipts: async () => true};
  if (name === '@/lib/autumbra-undo-status') return {loadUndoStatus: async () => ({already_undone: false})};
  return originalLoad.call(this, name, ...rest);
};
const render = element => renderToStaticMarkup(element);
const action = async () => null;
function fresh(file) {
  const resolved = require.resolve(root + '/' + file);
  delete require.cache[resolved];
  return require(resolved);
}
const zeroTile = {mode: 'dry_run', open_total: 0, open_by_severity: {},
  time_to_know_seconds: {median: null, worst: null, target: 3600},
  time_to_shield_seconds: {median: null, worst: null, target: 86400},
  sites_broken_by_a_shield: 0, cost_this_month_usd: 0, receipts_this_month: 0};

async function main() {
  const {ShieldsTile} = fresh('app/admin/autumbra/tile.tsx');
  for (const board of [null, {tile: zeroTile, shields: []}, {tile: {...zeroTile, fixture: true, open_total: 999}, shields: []}]) {
    const html = render(React.createElement(ShieldsTile, {board, act: action}));
    for (const label of ['Open issues', 'Time to know', 'Time to shield', 'Sites broken by a shield', 'Cost this month']) assert(html.includes(label), label);
    assert.equal((html.match(/<dd>/g) || []).length, 5);
    assert(!html.includes('999') && !html.includes('None yet'));
    if (board && !board.tile.fixture) {
      assert(html.includes('<dd>0</dd>') && html.includes('<dd>$0.0000</dd>'));
      assert.equal((html.match(/<dd>—<\/dd>/g) || []).length, 2);
      assert(html.includes('Use Look to start a check.'));
    } else {
      assert.equal((html.match(/<dd>—<\/dd>/g) || []).length, 5);
      assert(html.includes('Connect Autumbra Watch'));
    }
  }
  const populated = render(React.createElement(ShieldsTile, {board: {tile: {...zeroTile, open_total: 7, cost_this_month_usd: 0.1234,
      time_to_know_seconds: {median: 0, worst: 0, target: 3600}}, shields: []}, act: action}));
  assert(populated.includes('<dd>7</dd>') && populated.includes('$0.1234') && populated.includes('0 min'));
  const noReceipt = {id: 'real-shield', site: 'example.test', kind: 'waf_managed', state: 'proposed',
    plan: {plain: 'Managed rule', rule: {expression: 'true'}}, receipts: []};
  assert(render(React.createElement(ShieldsTile, {board: {tile: zeroTile, shields: [noReceipt]}, act: action}))
    .includes('Use Shield to record a shield receipt.'));
  const {AutumbraConsole} = fresh('app/admin/autumbra/panel.tsx');
  const emptyPanel = {incidents: [], monitor: {running: false, unavailable_checks: 0}, integrations: {}};
  for (const data of [null, emptyPanel]) {
    const html = render(React.createElement(AutumbraConsole, {data, look: action, resolve: action, threatReceipts: data ? [] : null}));
    assert(html.includes('Investigations') && html.includes('ThreatPayload / advisory receipts'));
    assert(html.includes(data ? '0 recorded' : '— recorded'));
    assert(html.includes(data ? 'Use Look to start a check.' : 'Connect Autumbra Watch'));
    assert(!html.includes('fixture-'));
  }
  const pendingInvestigation = {id: 'real-investigation', target: 'site', signal: 'health', state: 'open',
    created_at: '2026-11-05T00:00:00Z', cost_usd: 0, steps: []};
  const pendingHtml = render(React.createElement(AutumbraConsole, {data: {...emptyPanel, incidents: [pendingInvestigation]},
    look: action, resolve: action}));
  assert(pendingHtml.includes('1 recorded') && pendingHtml.includes('0 recorded steps')
    && pendingHtml.includes('Use Look to start a check.'));
  const {isUsableGhostPanel} = fresh('app/admin/autumbra/watch-data.ts');
  for (const count of [NaN, Infinity, -1, 0.1]) assert(!isUsableGhostPanel({...emptyPanel, monitor: {running: true, unavailable_checks: count}}));
  assert(isUsableGhostPanel(emptyPanel));

  const key = 'TANK_API_KEY';
  delete process.env[key];
  let calls = 0;
  global.fetch = async () => { calls++; throw Error('network forbidden'); };
  let weekly = fresh('lib/autumbra-weekly.ts');
  assert.equal((await weekly.loadWeeklyReceipts('tenant')).available, false);
  assert.equal(calls, 0);
  let shields = fresh('app/admin/autumbra/shields-data.ts');
  await assert.rejects(shields.shieldBoard('founder'), /TANK_API_KEY/);
  assert.equal(calls, 0);
  process.env[key] = 'offline-test-marker';
  for (const response of [{receipts: []}, {}, {receipts: null}, {receipts: [{fixture: true}, {kind: 'exercise'}, {control: 'fixture_edge'},
      {receipt: {fixture: true}}, {receipt: {kind: 'exercise'}}, {receipt: {control: 'fixture_edge'}}]}]) {
    global.fetch = async () => ({ok: true, status: 200, json: async () => response});
    weekly = fresh('lib/autumbra-weekly.ts');
    const result = await weekly.loadWeeklyReceipts('tenant');
    assert.equal(result.receipts.length, 0);
    assert.equal(result.available, Array.isArray(response.receipts));
    const Page = fresh('app/autumbra/receipts/weekly/[tenant]/page.tsx').default;
    const html = render(await Page({params: Promise.resolve({tenant: 'tenant'})}));
    assert(html.includes(result.available ? '0 recorded' : '— recorded'));
    assert(html.includes(result.available ? "log feed to start a check" : 'Reconnect Autumbra'));
    assert(!html.includes('acted') && !html.includes('fixture_edge'));
  }
  for (const bad of [{...zeroTile, fixture: true}, {...zeroTile, open_total: -1}, {...zeroTile, receipts_this_month: NaN}, {...zeroTile, cost_this_month_usd: Infinity}, {...zeroTile, time_to_know_seconds: {median: null, worst: -1, target: 3600}}]) {
    global.fetch = async url => ({ok: true, json: async () => String(url).endsWith('/tile') ? bad : {shields: []}});
    shields = fresh('app/admin/autumbra/shields-data.ts');
    await assert.rejects(shields.shieldBoard('founder'), /unavailable/);
  }
  global.fetch = async url => ({ok: true, json: async () => String(url).endsWith('/tile') ? zeroTile : {shields: []}});
  shields = fresh('app/admin/autumbra/shields-data.ts');
  assert.deepEqual((await shields.shieldBoard('founder')).tile, zeroTile);
  const Undo = fresh('app/autumbra/undo/[id]/page.tsx').default;
  for (const token of ['', 'invalid']) {
    const html = render(await Undo({params: Promise.resolve({id: 'no-receipt'}), searchParams: Promise.resolve({token})}));
    assert(html.includes('Use the Undo link'));
    assert(!html.includes('blocked an address') && !html.includes('<button'));
  }
  process.env.AUTUMBRA_UNDO_TOKEN_SECRET = 'offline-test-marker';
  const {createHmac} = require('node:crypto');
  const body = Buffer.from(JSON.stringify({tenant_id: 'tenant', receipt_id: 'signed-receipt',
    rule_id: '', site: 'example.test', exp: Math.floor(Date.now() / 1000) + 60})).toString('base64url');
  const token = body + '.' + createHmac('sha256', process.env.AUTUMBRA_UNDO_TOKEN_SECRET).update(body).digest('base64url');
  for (const id of ['signed-receipt', 'different-receipt']) {
    const html = render(await Undo({params: Promise.resolve({id}), searchParams: Promise.resolve({token})}));
    assert(!html.includes('blocked an address'));
    assert.equal(html.includes('<button'), id === 'signed-receipt');
  }
  console.log('Autumbra day-zero metrics, lists, receipts, missing settings and populated states passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
