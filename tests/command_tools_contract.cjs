// Offline response-contract checks against the actual Workspace server client.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(
  fs.readFileSync(filename, 'utf8'),
  {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}},
).outputText, filename);

// Read the backend's literal catalogue without importing it or contacting Tank.
const registered = JSON.parse(execFileSync('python3', ['-c', `
import ast, json, pathlib
tree = ast.parse(pathlib.Path('tank/command.py').read_text())
values = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body
          if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
          and node.targets[0].id in ('TOOLS', 'FOUNDER_TOOLS')}
print(json.dumps(sorted(set(values['FOUNDER_TOOLS'] + sum(values['TOOLS'].values(), [])))))
`], {cwd: root, encoding: 'utf8'}));
process.env.TANK_API_KEY = 'offline-test-placeholder';
process.env.TANK_URL = 'http://tank.invalid';
const {commandTools} = require('../workspace/lib/tank.ts');
const identity = {tenantId: 'tenant-owned', userId: 'user-owned'};
let payload;
global.fetch = async (url, init) => {
  assert.equal(String(url), 'http://tank.invalid/v1/command/tools');
  assert.equal(init.headers.get('x-tervory-tenant'), identity.tenantId);
  assert.equal(init.headers.get('x-tervory-user'), identity.userId);
  assert.equal(init.headers.get('x-tervory-squad'), null);
  assert.equal(init.cache, 'no-store');
  assert.equal(init.redirect, 'error');
  return Response.json(payload);
};

(async () => {
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
  console.log('commandTools: registered catalogue accepted; malformed/prototype payloads rejected; server identity preserved');
})().catch(error => { console.error(error); process.exitCode = 1; });
