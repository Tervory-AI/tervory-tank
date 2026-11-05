// Offline response-contract checks against the actual Workspace server client.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFile} = require('node:child_process');
const {promisify} = require('node:util');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
// Match the alias resolution used by command_1b_contract.cjs. Load the real
// regional adapter too; do not replace commandTools or its imports with mocks.
const signinFetchFile = path.join(root, 'workspace/lib/trigger-signin-fetch.ts');
require.cache[signinFetchFile] = {id: signinFetchFile, filename: signinFetchFile, loaded: true,
  exports: {signinFetch: (...args) => globalThis.fetch(...args)}};
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  if (name.startsWith('@/')) name = path.join(root, 'workspace', name.slice(2));
  return originalResolve.call(this, name, parent, ...rest);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(
  fs.readFileSync(filename, 'utf8'),
  {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}},
).outputText, filename);

// Evaluate only catalogue declarations, never import Tank or its runtime deps.
// Include augmented assignments and imported registries added on newer main.
const catalogue = () => promisify(execFile)('python3', ['-c', `
import ast, json, pathlib
folder = pathlib.Path('tank')

def catalogue(module, names):
    tree = ast.parse((folder / (module + '.py')).read_text())
    def target(node):
        while isinstance(node, ast.Subscript):
            node = node.value
        return node.id if isinstance(node, ast.Name) else None
    declarations = [node for node in tree.body
                    if (isinstance(node, ast.Assign) and any(target(t) in names for t in node.targets))
                    or (isinstance(node, ast.AugAssign) and target(node.target) in names)]
    needed = {node.id for statement in declarations for node in ast.walk(statement)
              if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)}
    values = {'__builtins__': {}}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                if local in needed:
                    values[local] = catalogue(node.module, {alias.name})[alias.name]
    for node in declarations:
        # Contract registries map literal tool names to Pydantic classes. Only
        # their real keys are catalogue data; their classes need no evaluation.
        if (isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict)
                and module != 'command' and not module.startswith('command_tools/')):
            node.value = ast.Dict(keys=node.value.keys, values=[ast.Constant(None) for _ in node.value.keys])
        code = ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[]))
        exec(compile(code, module, 'exec'), values)
    return {name: values[name] for name in names}

if (folder / 'command_tools' / '__init__.py').is_file():
    tree = ast.parse((folder / 'command_tools' / '__init__.py').read_text())
    products = next(ast.literal_eval(node.value) for node in tree.body
                    if isinstance(node, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == 'PRODUCTS' for t in node.targets))
    declarations = [catalogue('command_tools/' + name, {'TOOLS', 'FOUNDER_TOOLS'})
                    for name in products]
else:
    declarations = [catalogue('command', {'TOOLS', 'FOUNDER_TOOLS'})]
registered = {tool for values in declarations
              for tool in values['FOUNDER_TOOLS'] + sum(values['TOOLS'].values(), [])}
print(json.dumps(sorted(registered)))
`], {cwd: root, encoding: 'utf8'});
process.env.TANK_API_KEY = 'offline-test-placeholder';
process.env.TANK_URL = 'http://tank.invalid';
const {commandTools} = require('../workspace/lib/tank.ts');
const identity = {tenantId: 'tenant-owned', userId: 'user-owned'};
let payload;
let redirect = false;
global.fetch = async (url, init) => {
  assert.equal(String(url), 'http://tank.invalid/v1/command/tools');
  assert.equal(init.headers.get('x-tervory-tenant'), identity.tenantId);
  assert.equal(init.headers.get('x-tervory-user'), identity.userId);
  assert.equal(init.headers.get('x-tervory-squad'), null);
  assert.equal(init.cache, 'no-store');
  // The newer bounded client refuses 3xx itself instead of following them.
  assert.equal(init.redirect, 'manual');
  assert(init.signal instanceof AbortSignal);
  assert.equal(init.headers.get('x-tank-key'), 'offline-test-placeholder');
  if (redirect) return new Response(null, {status: 302, headers: {location: 'https://outside.invalid'}});
  return Response.json(payload);
};

(async () => {
  const {stdout} = await catalogue();
  const registered = JSON.parse(stdout);
  for (const name of ['trigger.voice.show', 'trigger.voice.set', 'trigger.voice.rollback']) {
    assert(registered.includes(name), `${name} must be registered by Tank`);
  }
  payload = registered;
  assert.deepEqual(await commandTools(identity), registered);
  payload = [];
  assert.deepEqual(await commandTools(identity), []);
  for (const bad of [
    null, {}, 'trigger.voice.show', [null], [42],
    ...['trigger', '.trigger', 'trigger.', 'trigger..show', 'trigger/voice.show',
      '../trigger.show', 'trigger.voice.show?x=y', 'trigger.voice.show#x',
      'trigger.voice.show\n', ' trigger.show', 'trigger. voice.show',
      'Trigger.voice.show', 'trigger.voice-show', 'trigger.voice\u0000show',
      '__proto__.show', 'trigger.__proto__.show', 'trigger.constructor',
      'constructor.prototype.show', 'trigger.prototype.show'].map(name => ['base.search', name]),
  ]) {
    payload = bad;
    await assert.rejects(() => commandTools(identity), {message: 'Tool access could not be loaded.'});
  }
  redirect = true;
  await assert.rejects(() => commandTools(identity), {status: 502, code: 'request_failed'});
  console.log('commandTools: registered catalogue accepted; malformed/prototype payloads rejected; server identity preserved');
})().catch(error => { console.error(error); process.exitCode = 1; });
