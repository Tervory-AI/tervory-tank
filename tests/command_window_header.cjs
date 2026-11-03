// Server-renders the real CommandWindow header offline: no chat selected shows no Spent/Saved totals.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const base = path.join(root, 'workspace');
const ts = require(path.join(base, 'node_modules/typescript'));
const resolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  if (name === 'next/navigation') return 'next-navigation-fixture';
  if (['react', 'react-dom', 'react-dom/server', 'react/jsx-runtime'].includes(name)) return resolve.call(this, path.join(base, 'node_modules', name), parent, ...rest);
  return resolve.call(this, name, parent, ...rest);
};
require.cache['next-navigation-fixture'] = { id: 'next-navigation-fixture', filename: 'next-navigation-fixture', loaded: true, exports: { usePathname: () => '/chats' } };
const compile = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText, filename);
require.extensions['.ts'] = compile;
require.extensions['.tsx'] = compile;
require.extensions['.css'] = () => {};
require.extensions['.svg'] = (module, filename) => { module.exports = { default: '/' + path.basename(filename) }; };
const React = require(path.join(base, 'node_modules/react'));
const { renderToStaticMarkup } = require(path.join(base, 'node_modules/react-dom/server'));
const { CommandWindow, ThreadTotals } = require(path.join(base, 'app/chats/window.tsx'));
const thread = { thread_id: 'one', title: 'Saved chat', updated_at: '2026-10-31', spent_usd: 0.01, saved_usd: 0.02 };
const snapshot = { thread, messages: [], steps: [], cards: [] };

const empty = renderToStaticMarkup(React.createElement(CommandWindow, { initialThreads: [], models: [], founder: false, account: 'Example · USD' }));
assert(!empty.includes('cw-totals'), 'no chat selected must not render header totals');
assert(!/Spent Unavailable|Saved Unavailable/.test(empty), empty);
const listed = renderToStaticMarkup(React.createElement(CommandWindow, { initialThreads: [thread], models: [], founder: true, account: 'Example · USD' }));
assert(!listed.includes('cw-totals') && listed.includes('Saved chat'), 'listing chats does not select one');
assert.equal(renderToStaticMarkup(React.createElement(ThreadTotals, { selected: null, snapshot: null })), '');
const shown = renderToStaticMarkup(React.createElement(ThreadTotals, { selected: 'one', snapshot }));
assert.match(shown, /class="cw-totals"/);
assert.match(shown, /Spent \$0\.01/);
assert.match(shown, /Saved \$0\.02/);
assert.match(shown, /href="\/chats\/evidence\/one"/);
const loading = renderToStaticMarkup(React.createElement(ThreadTotals, { selected: 'one', snapshot: null }));
assert.match(loading, /Spent Unavailable/); // a selected chat still loading keeps the honest placeholder
console.log('COMMAND window header: totals hidden with no chat selected, shown for a selected chat.');
