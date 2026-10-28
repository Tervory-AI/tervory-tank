// Read the existing page formatter. No client wording is duplicated in this test.
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(file) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, 'workspace', file), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}
  }).outputText;
  const exports = {};
  new Function('require', 'exports', code)(name => load(path.join(path.dirname(file), name + '.ts')), exports);
  return exports;
}
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const {fromTiger} = load('app/tiger/model.ts');
process.stdout.write(JSON.stringify(cases.map(({alert, observation}) =>
  fromTiger([], [observation], [alert], new Date(alert.ts)).alerts[0])));
