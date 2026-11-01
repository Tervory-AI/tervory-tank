// Offline verification of the actual Clerk binding and Workspace header writer.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '../..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
require.extensions['.ts'] = (module, file) => module._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true}
}).outputText, file);
let session = {};
const load = Module._load;
Module._load = function(name, ...rest) {
  if (name === '@clerk/nextjs/server') return {auth: async () => session};
  return load.call(this, name, ...rest);
};
process.env.TANK_API_KEY = 'dummy-workspace-key';
process.env.TANK_URL = 'http://tank.invalid';
const {triggerIdentity} = require(path.join(root, 'workspace/lib/trigger.ts'));
const {tenantIdFor} = require(path.join(root, 'workspace/lib/tenant.ts'));
const {commandRequest} = require(path.join(root, 'workspace/lib/tank.ts'));
const tenant = {orgId: 'org_offline', tenantId: tenantIdFor('org_offline'), userId: 'offline-user', orgName: 'Offline'};
let sent;
global.fetch = async (_url, init) => { sent = init.headers; return Response.json({}); };
(async () => {
  const cases = [
    [{}, {}, true],
    [{orgRole: 'org:member'}, {}, false],
    [{orgId: 'org_other'}, {}, false],
    [{userId: 'other-user'}, {}, false],
    [{}, {tenantId: tenantIdFor('org_other')}, false],
  ];
  for (const [sessionPatch, tenantPatch, expected] of cases) {
    session = {orgId: tenant.orgId, userId: tenant.userId, orgRole: 'org:admin', ...sessionPatch};
    const identity = await triggerIdentity({...tenant, ...tenantPatch});
    assert.equal(identity.tenantAdmin, expected);
    await commandRequest(identity, 'tools', {headers: {
      'x-tervory-role': 'org:admin', 'x-tervory-squad': 'trigger',
      'x-tervory-user': 'forged-user', 'x-tervory-tenant': 'forged-tenant',
    }});
    assert.equal(sent.get('x-tervory-role'), expected ? 'org:admin' : '');
    assert.equal(sent.get('x-tervory-user'), identity.userId);
    assert.equal(sent.get('x-tervory-tenant'), identity.tenantId);
    assert.equal(sent.has('x-tervory-squad'), false);
  }
  assert.equal(await triggerIdentity(null), null);
  console.log('PASS: verified Clerk user/org/tenant admin binding; forged role/user/tenant/squad headers cannot grant Trigger authority.');
})().catch(error => {console.error(error); process.exitCode = 1;});
