// Offline rendering regression only; invented values never enter a live page.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const req = createRequire(path.join(root, 'workspace/package.json'));
const ts = req('typescript');
const React = req('react');
const {renderToStaticMarkup} = req('react-dom/server');
const keys = ['phone_e164', 'phone_valid', 'phone_line_type', 'email_syntax_ok', 'email_disposable'];
const evidence = {value: 'https://invented.example/', source_url: 'https://invented.example/', checked_at: '2026-11-01', verified: true, reason: null};
const original = {website: evidence, phone: {...evidence, value: '+12025550123'}, email: {...evidence, value: ['invented@quality.example']}, socials: {...evidence, value: null, verified: false, reason: 'Not found in the public pages checked.'}};
const additions = Object.fromEntries(keys.map(k => [k, {...evidence, value: 'HIDDEN_QUALITY_'+k}]));
function render(file, fields, legacy = false) {
  const cache = new Map();
  let index = 0;
  const records = {total: 1, rows: [{record_id: 'invented', name: 'Invented business', state: 'DC', fields}]};
  const state = file.includes('reference') ? [null, null, null, [], [], false, '', '', false, records, null] : [records, ''];
  function load(relative) {
    const full = path.resolve(root, 'workspace/app/base', relative);
    if (cache.has(full)) return cache.get(full);
    let source = fs.readFileSync(full, 'utf8');
    if (legacy && /(?:reference|batch)-workflow\.tsx$/.test(full)) {
      source = source.replace('import { pageFieldEntries } from "./field-visibility";\n', '')
        .replaceAll('pageFieldEntries(row.fields)', 'Object.entries(row.fields)');
    }
    const compiled = ts.transpileModule(source, {compilerOptions: {jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText;
    const module = {exports: {}};
    function local(name) {
      if (name === 'react') return {...React, useState: () => [state[index++], () => {}], useEffect: () => {}, useCallback: fn => fn};
      if (name === 'next/navigation') return {useRouter: () => ({refresh() {}})};
      if (name.startsWith('.')) {
        const base = path.resolve(path.dirname(full), name);
        const target = ['.ts', '.tsx'].map(ext => base+ext).find(p => fs.existsSync(p));
        return load(path.relative(path.join(root, 'workspace/app/base'), target));
      }
      return req(name);
    }
    new Function('require', 'module', 'exports', compiled)(local, module, module.exports);
    cache.set(full, module.exports);
    return module.exports;
  }
  const exports = load(file);
  const component = exports.ReferenceWorkflow || exports.BatchWorkflow;
  return renderToStaticMarkup(React.createElement(component, {signedIn: true, selected: 'invented-batch'}));
}
for (const file of ['reference-workflow.tsx', 'batch-workflow.tsx']) {
  const before = render(file, original, true);
  const after = render(file, {...original, ...additions});
  assert.equal(after, before, `${file}: full rendered HTML must remain byte-identical`);
  assert.ok(after.includes('invented@quality.example'));
  for (const key of keys) assert.ok(!after.includes(key));
  console.log(`${file}: full HTML byte-identical; all five quality fields excluded`);
}
// Export schema and explicit page exclusion list must agree.
const strip = file => ts.transpileModule(fs.readFileSync(path.join(root, 'workspace/app/base', file), 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS}}).outputText;
function simple(file) {const m = {exports: {}}; new Function('exports', strip(file))(m.exports); return m.exports;}
assert.deepEqual(simple('csv.ts').CONTACT_QUALITY_COLUMNS, keys);
assert.ok(keys.every(k => simple('field-visibility.ts').PAGE_FIELD_EXCLUSIONS.includes(k)));
