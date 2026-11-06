const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const modules = path.resolve('workspace/node_modules');
const ts = require(path.join(modules, 'typescript'));
const React = require(path.join(modules, 'react'));
const {renderToStaticMarkup} = require(path.join(modules, 'react-dom/server'));
const root = path.join(process.argv[2], 'workspace/app/radix');
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file).exports;
  const module = {exports: {}}; cache.set(file, module);
  const result = ts.transpileModule(fs.readFileSync(file, 'utf8'), {fileName: file, reportDiagnostics: true,
    compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX}});
  assert.equal(result.diagnostics.filter(d => d.category === ts.DiagnosticCategory.Error).length, 0);
  function local(name) {
    if (name === 'react') return React;
    if (name === 'react/jsx-runtime') return require(path.join(modules, 'react/jsx-runtime'));
    if (name === './plugins') return {Plugins: () => null};
    if (name === './conversation') return {RadixDesk: () => null};
    if (name === '../squad-links') return {SquadLinks: () => null};
    for (const suffix of ['.tsx', '.ts']) {
      const candidate = path.resolve(path.dirname(file), name + suffix);
      if (fs.existsSync(candidate)) return load(candidate);
    }
    throw Error('Unexpected dependency ' + name);
  }
  vm.runInNewContext(result.outputText, {module, exports: module.exports, require: local, console,
    fetch: () => { throw Error('No network in day-zero render'); }, AbortController});
  return module.exports;
}
const {summary, SummaryView, FIRST_SCAN} = load(path.join(root, 'summary.tsx'));
const severities = ['critical','high','medium','low','info','unknown'];
const figure = (id, value) => ({id, value, status: 'available'});
const data = {product:'radix', figures:[figure('radix.scans',0),figure('radix.findings_by_severity',severities.map(id=>({id,value:0})))],
  tank:[figure('tank.work_by_execution',['code','cache','model'].map(id=>({id,value:0}))),figure('tank.spend',0)]};
const render = (data, section='Overview') => renderToStaticMarkup(React.createElement(SummaryView, {data:summary(data),section}));
for (const section of ['Overview','Findings','Reports']) {
  const html = render(data, section);
  assert.match(html, /<h2>Scans<\/h2><p>0<\/p>/);
  assert.match(html, /<h2>Receipts<\/h2><p>0<\/p><p>\$0.00<\/p>/);
  assert.equal((html.match(/<svg/g)||[]).length, 1);
  assert.equal((html.match(/<line /g)||[]).length, 5);
  assert.equal((html.match(/<rect /g)||[]).length, 0);
  const svg = html.match(/<svg.*?<\/svg>/)[0];
  assert.equal((svg.match(/<text /g)||[]).length, 1);
  assert.match(svg, />0<\/text>/);
  assert(html.includes(FIRST_SCAN));
  assert.doesNotMatch(html, /example|made-up|1 240|248/i);
  if (section !== 'Overview') assert(html.includes('No '+section.toLowerCase()+' yet'));
}
for (const malformed of [null, {}, {...data,product:'tiger'}, {...data,figures:[]}]) {
  const html = render(malformed);
  assert.match(html, /—/); assert.doesNotMatch(html, /<rect /);
}
const real = structuredClone(data); real.figures[0].value=7; real.figures[1].value[1].value=2;
real.tank[0].value[0].value=4; real.tank[1].value=1.25;
const filled=render(real);
assert.match(filled, /<h2>Scans<\/h2><p>7<\/p>/);
assert.match(filled, /<h2>Receipts<\/h2><p>4<\/p><p>\$1.25<\/p>/);
assert.match(filled, /high: 2/);
real.tank[1].unknown_cost_calls=1;
assert.equal(summary(real).spend, null);
real.figures[1].value[1].value=-1;
assert.equal(summary(real).findings, null);
const {RadixPage}=load(path.join(root,'view.tsx'));
const page=renderToStaticMarkup(React.createElement(RadixPage,{accountName:'placeholder account',settings:null}));
assert.doesNotMatch(page,/example|made-up|data:text\/markdown/i);
assert.match(page,/Findings by severity/);
const {radixRequests}=load(path.resolve('workspace/app/radix/request-service.ts'));
const {mapVaultPayload}=load(path.resolve('workspace/app/radix/plugins-model.ts'));
for (const enabled of [false,true]) {
  const panel=mapVaultPayload({enabled});
  assert.equal(panel.enabled,enabled);
  for (const key of ['secrets','files','links','connections']) assert.equal(panel[key].length,0);
  if (!enabled) assert.match(panel.message,/Turn it on in Tank/);
}
(async()=>{
  const calls=[];
  const requests=radixRequests({list:async(tenant)=>{calls.push(tenant);return[];},create:async()=>{throw Error('unexpected write');},get:async()=>{throw Error('unexpected read');}});
  const empty=await requests.search('placeholder-tenant','');
  assert.deepEqual(JSON.parse(JSON.stringify(empty)),{records:[],limited:false});
  assert.deepEqual(calls,['placeholder-tenant']);
  console.log('PASS: zero charts, counts, findings/reports, receipts, unknown settings/data, real metric values, no client examples, empty tenant records.');
})().catch(error=>{console.error(error);process.exitCode=1;});
