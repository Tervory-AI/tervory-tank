// Backend contract only: no proposed Figma screen or live service is invoked.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(process.env.PAID_STEP_TYPESCRIPT);
const source = path.join(root, 'workspace/app/settings/paid-steps/api/route.ts');
let actor = { tenantId: 'placeholder-tenant', userId: 'placeholder-admin', tenantAdmin: true };
const calls = [];
class CommandRequestError extends Error { constructor(status) { super('placeholder'); this.status = status; } }
const compiled = ts.transpileModule(fs.readFileSync(source, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText;
const loaded = new Module(source, module);
loaded.filename = source;
loaded.require = name => ({
  '@/lib/trigger': { triggerIdentity: async () => actor },
  '@/lib/tenant': { activeTenant: async () => 'placeholder-tenant' },
  '@/lib/tank': { CommandRequestError, commandRequest: async (identity, target, init) => {
    assert.equal(identity, actor);
    if (!actor.tenantAdmin) throw new CommandRequestError(403);
    calls.push({ target, init });
    return Response.json({ steps: [{ step_id: 'base.placeholder.model.fixture', mode: 'ask' }] });
  } },
}[name] ?? require(name));
loaded._compile(compiled, source);
const route = loaded.exports;
const request = (body, options = {}) => new Request('https://app.tervory.com/settings/paid-steps/api', {
  method: 'PUT', headers: { 'Content-Type': 'application/json', Origin: 'https://app.tervory.com', ...options.headers },
  body: typeof body === 'string' ? body : JSON.stringify(body),
});
(async () => {
  const read = await route.GET(new Request('https://app.tervory.com/settings/paid-steps/api'));
  assert.equal(read.status, 200);
  assert.equal(read.headers.get('cache-control'), 'no-store');
  assert.equal((await read.json()).steps[0].mode, 'ask');
  assert.equal(calls[0].target, 'paid-steps');
  for (const mode of ['ask','auto']) {
    assert.equal((await route.PUT(request({ step_id:'base.placeholder.model.fixture',mode,tenant_id:'placeholder-other' }))).status, 200);
    assert.equal(calls.at(-1).target, 'paid-steps/base.placeholder.model.fixture');
    assert.deepEqual(JSON.parse(calls.at(-1).init.body), { mode });
  }
  const count = calls.length;
  assert.equal((await route.PUT(request({step_id:'../controls',mode:'auto'}))).status,422);
  assert.equal((await route.PUT(request({step_id:'base.placeholder',mode:'sometimes'}))).status,422);
  assert.equal((await route.PUT(request('x'.repeat(1025)))).status,413);
  assert.equal((await route.PUT(request({}, {headers:{Origin:'https://placeholder-other.example'}}))).status,403);
  assert.equal((await route.PUT(request({}, {headers:{'Content-Type':'text/plain'}}))).status,415);
  assert.equal(calls.length,count);
  actor = {...actor, tenantAdmin:false};
  assert.equal((await route.GET(new Request('https://app.tervory.com/settings/paid-steps/api'))).status,403);
  actor = null;
  assert.equal((await route.GET(new Request('https://app.tervory.com/settings/paid-steps/api'))).status,401);
})().catch(error => { console.error(error); process.exitCode = 1; });
