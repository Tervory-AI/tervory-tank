const assert = require('node:assert/strict');
const path = require('node:path');
process.env.COMMAND_TEST_TOOLS = path.resolve('workspace/node_modules');
const {workspace} = require('../command_acceptance_20261031/workspace_loader.cjs');
const env = {TANK_URL: 'http://tank.synthetic.invalid', TANK_API_KEY: 'synthetic-runtime-reader'};
const record = {issuer: 'https://auth.tervory.com', client_id: '30001@tervory', workspace_client_id: '30002@tervory', project_id: '40001', founders: ['50001'], organisations: {'60001': '00000000-0000-4000-8000-000000000011'}};
let requests = 0;
const load = workspace({env, fetch: async (url, init) => {
  requests++;
  assert.equal(url, env.TANK_URL + '/v1/trigger-signin/config');
  assert.equal(init.headers['x-tank-key'], env.TANK_API_KEY);
  assert.equal(init.cache, 'no-store');
  assert.equal(init.redirect, 'error');
  return Response.json({regions: {'us-east': record}});
}});
(async () => {
  const runtime = load('lib/trigger-signin-runtime.ts');
  assert.equal((await runtime.signinRuntime()).project_id, '40001');
  assert.equal((await runtime.signinRuntime()).workspace_client_id, '30002@tervory');
  assert.equal(requests, 1);
  assert.equal(env.TERVORY_ADMIN_USER_IDS, '50001');
  const bindings = load('lib/trigger-signin-principal.ts').tenantBindings();
  assert.equal(bindings['60001'], record.organisations['60001']);
  assert.equal(env.TRIGGER_SIGNIN_CLIENT_ID, record.client_id);
  console.log('Generated runtime IDs, existing tenant bindings and native founder subject loaded from Tank');
})().catch(error => {console.error(error); process.exitCode = 1;});
