// Render the actual menu consumers with synthetic props. No effects, network or providers.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const {createRequire} = Module;
const root = path.resolve(__dirname, '..');
const local = createRequire(path.join(root, 'workspace/package.json'));
const ts = local('typescript');
const React = local('react');
const {renderToStaticMarkup} = local('react-dom/server');
const original = Module._load;
Module._load = function(name, parent, isMain) {
  if (name === 'next/link') return props => React.createElement('a', props);
  if (name === 'next/navigation') return {
    usePathname: () => '/chats', useRouter: () => ({refresh() {throw Error('Unexpected refresh');}}),
  };
  // Plugins are outside this menu test; do not import server action credentials.
  if (name === './plugins' && parent.filename.endsWith('/rig/lab.tsx')) return {Plugins: () => null};
  return original.call(this, name, parent, isMain);
};
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true, target: ts.ScriptTarget.ES2022},
}).outputText, filename);
require.extensions['.css'] = module => {module.exports = {};};
require.extensions['.svg'] = (module, filename) => {module.exports = {src: filename};};
global.fetch = () => {throw Error('Unexpected network request');};
const {Lab} = require('../workspace/app/rig/lab.tsx');
const {ReviewConsole} = require('../workspace/app/review/console.tsx');
const {CommandWindow} = require('../workspace/app/chats/window.tsx');
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
function destination(html, label) {
  const tag = [...html.matchAll(/<a\b([^>]*)>([^<]*)<\/a>/g)].find(match => match[2] === label);
  assert(tag, `Missing ${label} anchor`);
  return /href="([^"]+)"/.exec(tag[1])[1];
}
const menus = [
  ['Rig', render(Lab, {accountName:'Fixture', products:null, fits:null, plugins:{}})],
  ['Review', render(ReviewConsole, {items:[], note:'', reviewer:'Fixture', account:'Fixture'})],
  ['Chats client', render(CommandWindow, {initialThreads:[], models:[], founder:false, account:'Fixture'})],
  ['Chats founder', render(CommandWindow, {initialThreads:[], models:[], founder:true, account:'Fixture'})],
];
for (const [name, html] of menus) {
  const dashboard = name === 'Chats founder' ? 'https://app.tervory.com/control' : 'https://app.tervory.com/';
  assert.equal(destination(html, 'Dashboard'), dashboard, name);
  assert.equal(destination(html, 'Projects'), '/matters', name);
  assert.equal(destination(html, 'Chats'), '/chats', name);
  for (const host of ['app.tervory.com', 'zenas.tervory.com', 'base.tervory.com']) {
    assert.equal(new URL(destination(html, 'Dashboard'), `https://${host}/`).hostname, 'app.tervory.com');
    assert.equal(new URL(destination(html, 'Chats'), `https://${host}/`).pathname, '/chats');
  }
  if (name === 'Rig' || name === 'Review') assert.equal(destination(html, 'Support'), 'https://tervory.com');
  if (name.startsWith('Chats')) assert.match(html, /href="\/chats" aria-current="page"/);
}
console.log('PASS: actual Rig, Review, client/founder Chats menu destinations; host roots, founder control, current Chats marker. Isolated static render only.');
