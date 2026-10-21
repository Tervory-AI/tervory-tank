/* Offline capture of the actual Base import component. Effects/API calls do not run. */
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const React = require(path.join(root, 'workspace/node_modules/react'));
const { renderToStaticMarkup } = require(path.join(root, 'workspace/node_modules/react-dom/server'));
for (const ext of ['.ts', '.tsx']) require.extensions[ext] = (module, filename) => {
  module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {
    module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true,
    target: ts.ScriptTarget.ES2022,
  }}).outputText, filename);
};
require.extensions['.css'] = () => {};
const DataPage = require('../workspace/app/data/page.tsx').default;
const css = fs.readFileSync(path.join(root, 'workspace/app/data/data.css'), 'utf8');
const globalCss = fs.readFileSync(path.join(root, 'workspace/app/globals.css'), 'utf8');
const body = renderToStaticMarkup(React.createElement(DataPage));
const directory = path.join(root, 'tests/artifacts/agent1-data');
fs.mkdirSync(directory, {recursive: true});
fs.writeFileSync(path.join(directory, 'data.html'), `<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>:root{--bg:#fff;--ink:#001840;--muted:#55627a;--line:#B8BFD0;--red:#E80008}body{margin:0;font:15px Inter,Arial,sans-serif;color:var(--ink);background:#fff}main{max-width:1200px;margin:auto;padding:24px}input,select,textarea,button{font:inherit;box-sizing:border-box}input,select,textarea{padding:10px;border:1px solid var(--line);border-radius:4px}button{padding:10px 16px;background:#001840;color:white;border:0;border-radius:4px}h1{font-family:Jost,Arial,sans-serif;font-weight:300}${globalCss}${css}</style><main>${body}</main>`);
console.log('Saved actual Base import form for 375px and 1440px cloud captures.');
