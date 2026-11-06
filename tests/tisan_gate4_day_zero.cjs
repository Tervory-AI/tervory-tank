const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const localRequire = createRequire(path.join(root, 'agents/tisan/templates/next-site/package.json'));
const ts = localRequire('typescript');
const React = localRequire('react');
const { renderToStaticMarkup } = localRequire('react-dom/server');
const page = path.join(root, 'workspace/app/tisan');

function render(view, tab, filter = 'all') {
  let hook = 0;
  const state = {1: view, 3: filter, 4: tab ? 'plugins' : 'none', 5: tab || 'keys'};
  const react = {...React, useEffect() {}, useState(initial) {
    hook++;
    return [Object.hasOwn(state, hook) ? state[hook] : typeof initial === 'function' ? initial() : initial, () => {}];
  }};
  const cache = new Map();
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = {exports: {}};
    cache.set(filename, module);
    function requireSource(name) {
      if (name === 'react') return react;
      if (name === 'react/jsx-runtime') return localRequire(name);
      if (name === 'next/navigation') return {useRouter: () => ({refresh() {throw Error('network forbidden');}})};
      if (name === '../squad-links') return {SquadLinks: () => null};
      if (name === './gold-review') return {GoldReview: () => null};
      if (name === './plugin-actions') return new Proxy({}, {get: () => () => {throw Error('network forbidden');}});
      if (!name.startsWith('./')) throw Error('unexpected import: ' + name);
      const target = path.resolve(path.dirname(filename), name);
      return load(fs.existsSync(target + '.tsx') ? target + '.tsx' : target + '.ts');
    }
    const js = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {
      module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022,
    }}).outputText;
    vm.runInNewContext(js, {module, exports: module.exports, require: requireSource, URL, Date, console}, {filename});
    return module.exports;
  }
  const {Tisan} = load(path.join(page, 'tisan.tsx'));
  const vault = load(path.join(page, 'vault-model.ts'));
  const copy = load(path.join(page, 'copy.ts'));
  assert.equal(copy.RECORDS.length, 0);
  assert.equal(copy.OPENING_THREAD.length, 0);
  for (const kind of ['Build', 'Page', 'Test']) {
    assert.equal(copy.searchRecords('', kind).length, 0);
    assert.match(copy.groupMeta(kind, 0).countLabel, /^0 /);
  }
  const html = renderToStaticMarkup(React.createElement(Tisan, {
    plugins: vault.mapVaultPayload({enabled: true}), accountName: null,
  }));
  assert.doesNotMatch(html, /\b[1-9][0-9]* (?:builds|pages|test runs|receipts|requests)\b/);
  return html;
}

for (const view of ['overview', 'builds', 'design', 'tests']) {
  const html = render(view);
  assert.match(html, /No builds yet\./);
  assert.match(html, />Start build<\/button>/);
}
for (const filter of ['Build', 'Page', 'Test']) {
  const html = render('overview', null, filter);
  assert.match(html, />0 results<\/p>/);
  assert.match(html, /No builds yet\./);
  assert.match(html, />Start build<\/button>/);
}
for (const [tab, empty, action] of [
  ['keys', 'No keys saved.', 'Save key'], ['files', 'No files stored.', 'Choose files'],
  ['links', 'No links saved.', 'Add link'], ['mcp', 'No connections saved.', 'Add connection'],
]) {
  const html = render('overview', tab);
  assert.ok(html.includes(empty), tab);
  assert.ok(html.includes('>' + action + '</button>'), tab);
  assert.doesNotMatch(html, /class="(?:file-row|secret-row|connection-row|link-row)"/);
}
console.log('11 empty client views: truthful zero counts, empty lists, existing first actions');
