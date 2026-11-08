const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict'), Module = require('node:module');
const root = path.resolve(__dirname, '../workspace');
const ts = require(root + '/node_modules/typescript'), React = require(root + '/node_modules/react');
const {renderToStaticMarkup: render} = require(root + '/node_modules/react-dom/server');
for (const extension of ['.ts', '.tsx']) require.extensions[extension] = (m, name) => m._compile(ts.transpileModule(fs.readFileSync(name, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX},
}).outputText, name);
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, ...args) { return resolve.call(this, name.startsWith('@/') ? root + '/' + name.slice(2) : name, ...args); };
const load = Module._load;
Module._load = function(name, ...args) {
  if (name === 'server-only') return {};
  if (name === '@/lib/trigger-signin-fetch') return {signinFetch: (...values) => global.fetch(...values)};
  if (name === '@/lib/autumbra-receipts-access') return {mayReadWeeklyReceipts: async () => true};
  return load.call(this, name, ...args);
};
process.env.TANK_API_KEY = 'placeholder-key';
async function main() {
  const {loadWeeklyReceipts} = require(root + '/lib/autumbra-weekly.ts');
  const Page = require(root + '/app/autumbra/receipts/weekly/[tenant]/page.tsx').default;
  let rows = [];
  global.fetch = async () => ({ok: true, status: 200, json: async () => ({receipts: rows})});
  const page = async () => render(await Page({params: Promise.resolve({tenant: 'owner'})}));
  let html = await page();
  assert(html.includes('<dt>Cost</dt><dd>—</dd>') && html.includes('<dt>Would have cost</dt><dd>—</dd>'));
  assert(!html.includes('<li') && html.includes('log feed to start a check'));
  rows = [{id: 'recorded', outcome: 'blocked', cost_usd: 0, would_have_cost_usd: 0.000153}];
  html = await page();
  assert(html.includes('$0.000000') && html.includes('$0.000153'));
  for (const bad of [null, -1, Infinity, '0.99', true]) {
    rows = [{id: 'recorded', cost_usd: 0, would_have_cost_usd: bad}];
    assert.equal((await loadWeeklyReceipts('owner')).receipts[0].would_have_cost_usd, undefined);
    assert((await page()).includes('<dt>Would have cost</dt><dd>—</dd>'));
  }
  rows = [{id: 'fixture', fixture: true, cost_usd: 5, would_have_cost_usd: 10}];
  assert(!(await page()).includes('$'));
  console.log('Autumbra receipt costs, unknown prices and empty shape passed');
}
main().catch(error => { console.error(error); process.exitCode = 1; });
