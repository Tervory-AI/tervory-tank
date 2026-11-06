const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const req = createRequire(path.join(root, 'workspace/package.json'));
const ts = req('typescript');
const React = req('react');
const {renderToStaticMarkup} = req('react-dom/server');

// Render the proposed shared-source patch in memory. Vendor bytes stay pinned.
const patch = fs.readFileSync(path.join(root, 'tank-patches/gate4.patch'), 'utf8').split('\n');
const proposed = new Map();
for (let i = 0; i < patch.length; i++) {
  if (!patch[i].startsWith('--- a/')) continue;
  const file = patch[i++].slice(6);
  assert.equal(patch[i], '+++ b/' + file);
  const before = fs.readFileSync(path.join(root, file), 'utf8').split('\n');
  let cursor = 0, output = [];
  while (++i < patch.length && !patch[i].startsWith('--- a/')) {
    const hunk = /^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@/.exec(patch[i]);
    if (!hunk) continue;
    const start = Number(hunk[1]) - 1;
    output.push(...before.slice(cursor, start)); cursor = start;
    while (++i < patch.length && /^[ +\-]/.test(patch[i]) && !patch[i].startsWith('--- a/')) {
      const line = patch[i], kind = line[0], text = line.slice(1);
      if (kind !== '+') {assert.equal(before[cursor], text, file); cursor++;}
      if (kind !== '-') output.push(text);
    }
    i--;
  }
  i--;
  output.push(...before.slice(cursor));
  proposed.set(file, output.join('\n'));
}
assert.equal(proposed.size, 5);
let states = [], stateIndex = 0;
const fakeReact = {...React, useState(initial) {
  const index = stateIndex++;
  return [index < states.length ? states[index] : typeof initial === 'function' ? initial() : initial, () => {}];
}, useEffect() {}, useCallback(fn) {return fn;}, useRef() {return {current: null};}};
const cache = new Map();
function load(file) {
  if (cache.has(file)) return cache.get(file);
  const source = proposed.get(file) ?? fs.readFileSync(path.join(root, file), 'utf8');
  const compiled = ts.transpileModule(source, {fileName: file, reportDiagnostics: true, compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.React, esModuleInterop: true,
  }});
  assert(!(compiled.diagnostics || []).some(d => d.category === ts.DiagnosticCategory.Error), file);
  const module = {exports: {}};
  new Function('require','module','exports','React',compiled.outputText)(name => {
    if (name === 'react') return fakeReact;
    if (name === 'react-dom') return {useFormStatus: () => ({pending: false})};
    if (name === 'next/navigation') return {useRouter: () => ({refresh() {}})};
    if (file.endsWith('/view.tsx')) {
      const children = {'./ask':['AskBase','RecordSearch'], './plugins':['PluginsDialog'],
        '../squad-links':['SquadLinks'], './batch-workflow':['BatchWorkflow'],
        './context-comparison':['ContextComparison'], './reference-workflow':['ReferenceWorkflow']};
      if (children[name]) return Object.fromEntries(children[name].map(key => [key, () => null]));
    }
    assert(name.startsWith('.'), 'Unexpected dependency ' + name);
    const relative = path.posix.normalize(path.posix.join(path.posix.dirname(file), name));
    const target = ['.ts','.tsx'].map(ext => relative + ext).find(p => fs.existsSync(path.join(root,p)));
    assert(target, relative);
    return load(target);
  }, module, module.exports, fakeReact);
  cache.set(file,module.exports);
  return module.exports;
}
function render(component, props, initial = []) {
  states = initial; stateIndex = 0;
  return renderToStaticMarkup(React.createElement(component, props));
}
const model = load('workspace/app/base/model.ts').buildModel({batches:[],skills:[],now:new Date('2026-11-05T12:00:00Z')});
assert.deepEqual(model.totals,{records:0,withSite:0,withEmail:0,skipped:0});
const overview = render(load('workspace/app/base/view.tsx').BaseView, {
  model,plugins:{enabled:false,message:null,secrets:[],files:[],links:[],connections:[]},accountName:null,
  refresh:async()=>{},search:async()=>{},ask:async()=>{},signedIn:true,
});
assert(overview.includes('No batches yet') && overview.includes('role="table" aria-label="Batches"'));
assert(overview.includes('href="#base-upload"'));
assert(!overview.includes('Acme') && !overview.includes('Kauai'));
const numbers = {groups:[],costs:[],states:[],states_done:0,unattributed_calls:0,records_without_receipts:0};
const reference = {file:null,total_all:0,collectors:0,history:[],groups:[],changes:[]};
const comparison = {states:[],rows:[]};
const initial = [reference,numbers,comparison,[],[],false,'','',false,null,null];
const component = load('workspace/app/base/reference-workflow.tsx').ReferenceWorkflow;
const workflow = render(component,{signedIn:true},initial);
for (const text of ['id="base-upload"','data-empty="costs"','<svg','<path','<text','>0</text>',
                    'Monthly cost change','Recorded calls','0 calls','data-empty="comparison"','Apollo CSV']) {
  assert(workflow.includes(text),text);
}
assert(workflow.includes('>—</text>') && !workflow.includes('$0.000000'));
assert(!workflow.includes('NaN') && !workflow.includes('Infinity'));
assert((workflow.match(/href="#base-upload"/g)||[]).length >= 4);
const noDataYet = render(component,{signedIn:true});
assert(!noDataYet.includes('data-empty="costs"'), 'Loading is not measured zero');
const unknownReceipts = render(component,{signedIn:true},[reference,{...numbers,records_without_receipts:1},comparison,...initial.slice(3)]);
assert(!unknownReceipts.includes('0 calls'), 'Missing receipt data must remain unknown');
const receipts = render(component,{signedIn:true},[...initial.slice(0,-1),{rows:[],total:0,cost:{},unpricedOnly:false}]);
assert(receipts.includes('aria-label="Cost receipts"') && receipts.includes('Showing 0 of 0 calls'));
const data = {...numbers,costs:[{state:'CA',month:'2026-11',rung:0,known_cost_usd:'0.125',
  cost_per_verified_record:'0.125',status:'priced',verified_records:1,unpriced:0}]};
const populated = render(component,{signedIn:true},[reference,data,comparison,...initial.slice(3)]);
assert(populated.includes('$0.125000') && !populated.includes('data-empty="costs"'));
const ask = load('workspace/app/base/ask.tsx');
assert(render(ask.RecordSearch,{search:async()=>{}}).includes('0 records'));
assert(render(ask.AskBase,{ask:async()=>{}}).includes('Upload a business list'));
const report = load('workspace/app/base/context-report.ts').contextReport([]);
const trial = render(load('workspace/app/base/context-comparison.tsx').ContextComparison,{report,canRunTrial:true});
assert(trial.includes('0 records') && trial.includes('aria-label="Company data comparison"'));
assert(trial.includes('Upload a business list') && !trial.includes('NaN'));
console.log('Day-zero overview, charts, lists, comparison and receipts retain shape, zero/unknown values and first actions; populated data preserved.');
