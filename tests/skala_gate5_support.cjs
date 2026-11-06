const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const root = process.cwd();
const realRequire = createRequire(path.join(root, 'workspace/package.json'));
const ts = realRequire('typescript');
function loader(sources, overrides = {}, globals = {}, settings = {}) {
  const cache = new Map();
  function resolve(name, parent) {
    const base = name.startsWith('@/') ? path.join(root, 'workspace', name.slice(2)) : path.resolve(path.dirname(parent), name);
    return ['', '.ts', '.tsx', '.js'].map(suffix => base + suffix).find(file => Object.hasOwn(sources, file) || fs.existsSync(file));
  }
  function load(file) {
    file = path.resolve(root, file);
    if (cache.has(file)) return cache.get(file).exports;
    const module = {exports: {}};
    cache.set(file, module);
    const source = sources[file] ?? fs.readFileSync(file, 'utf8');
    const code = ts.transpileModule(source, {fileName: file, compilerOptions: {
      target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
    }}).outputText;
    function requireLocal(name) {
      if (Object.hasOwn(overrides, name)) return overrides[name];
      if (name === 'server-only' || name.endsWith('.css')) return {};
      if (name === '../squad-links') return {SquadLinks: () => null};
      if (name.startsWith('.') || name.startsWith('@/')) return load(resolve(name, file));
      return realRequire(name);
    }
    vm.runInNewContext('(function(module, exports, require){' + code + '\n})', {
      process: {env: settings}, console, URL, URLSearchParams, Request, Response, Headers,
      AbortSignal, AbortController, setTimeout, clearTimeout, crypto, TextEncoder, ReadableStream,
      fetch: () => { throw new Error('Unexpected network request'); }, ...globals,
    }, {filename: file})(module, module.exports, requireLocal);
    return module.exports;
  }
  return load;
}
function bundle(sources, entry, props) {
  const modules = new Map();
  const prod = {
    react: 'react/cjs/react.production.js', 'react/jsx-runtime': 'react/cjs/react-jsx-runtime.production.js',
    'react-dom': 'react-dom/cjs/react-dom.production.js',
    'react-dom/client': 'react-dom/cjs/react-dom-client.production.js', scheduler: 'scheduler/cjs/scheduler.production.js',
  };
  function add(file) {
    if (modules.has(file)) return modules.get(file).id;
    const record = {id: modules.size, code: ''}; modules.set(file, record);
    let source = sources[file] ?? fs.readFileSync(file, 'utf8');
    if (/\.tsx?$/.test(file)) source = ts.transpileModule(source, {fileName: file, compilerOptions: {
      target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
    }}).outputText;
    source = source.replace(/require\(["']([^"']+)["']\)/g, (_, name) => {
      if (name === '../squad-links') return '({SquadLinks:()=>null})';
      let target;
      if (prod[name]) target = path.join(root, 'workspace/node_modules', prod[name]);
      else if (name.startsWith('.')) {
        const base = path.resolve(path.dirname(file), name);
        target = ['', '.ts', '.tsx', '.js'].map(s => base + s).find(f => Object.hasOwn(sources, f) || fs.existsSync(f));
      } else target = realRequire.resolve(name);
      if (!target) throw new Error('Missing browser module ' + name);
      return '__require(' + add(target) + ')';
    });
    record.code = source;
    return record.id;
  }
  const entryId = add(path.join(root, 'workspace/app/skala', entry));
  const react = add(path.join(root, 'workspace/node_modules', prod.react));
  const client = add(path.join(root, 'workspace/node_modules', prod['react-dom/client']));
  const name = entry.startsWith('gold/') ? 'GoldView' : 'SkalaApp';
  return '(()=>{const process={env:{NODE_ENV:"production"}};const modules={' + [...modules.values()].map(m =>
    m.id + ':(module,exports,__require)=>{' + m.code + '\n}').join(',') + '};const cache={};function __require(id){if(cache[id])return cache[id].exports;const m={exports:{}};cache[id]=m;modules[id](m,m.exports,__require);return m.exports;}__require(' + client + ').hydrateRoot(document.getElementById("root"),__require(' + react + ').createElement(__require(' + entryId + ').' + name + ',' + JSON.stringify(props).replaceAll('<', '\\u003c') + '));})();';
}
module.exports = {loader, bundle, realRequire, root};
