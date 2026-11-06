const fs = require('node:fs'), path = require('node:path'), assert = require('node:assert/strict');
const Module = require('node:module'), {createHmac} = require('node:crypto');
const root = path.resolve(__dirname, '../workspace'), ts = require(root + '/node_modules/typescript');
require.extensions['.ts'] = (m, f) => m._compile(ts.transpileModule(fs.readFileSync(f, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText, f);
const resolve = Module._resolveFilename, load = Module._load;
Module._resolveFilename = function(name, ...rest) { return resolve.call(this, name.startsWith('@/') ? root + '/' + name.slice(2) : name, ...rest); };
let identity = {userId: 'owner', tenantId: 'tenant'};
Module._load = function(name, ...rest) {
  if (name === 'server-only') return {};
  if (name === 'next/cache') return {revalidatePath: () => {}};
  if (name === '@/lib/trigger-signin-fetch') return {signinFetch: (...args) => global.fetch(...args)};
  if (name === '@/lib/trigger-signin') return {auth: async () => identity};
  return load.call(this, name, ...rest);
};
function fresh(file) { const p = require.resolve(root + '/' + file); delete require.cache[p]; return require(p); }
process.env.TANK_URL = 'http://offline.invalid';
process.env.TANK_API_KEY = 'placeholder-service-key';
process.env.AUTUMBRA_UNDO_TOKEN_SECRET = 'placeholder-signing-key';
const sign = data => { const b = Buffer.from(JSON.stringify(data)).toString('base64url'); return b + '.' + createHmac('sha256', process.env.AUTUMBRA_UNDO_TOKEN_SECRET).update(b).digest('base64url'); };
const payload = {tenant_id: 'tenant', receipt_id: 'receipt', site: 'example.test', rule_id: 'a'.repeat(32), exp: Math.floor(Date.now()/1000)+60};
const token = sign(payload);
const post = (value = {token}) => new Request('http://offline.invalid/api/autumbra/undo', {method:'POST', body:JSON.stringify(value)});
const get = () => new Request('http://offline.invalid/api/autumbra/undo?token=' + token);
async function main() {
  const {AUTUMBRA_REQUEST, autumbraRequest} = require(root + '/lib/autumbra-request.ts');
  AUTUMBRA_REQUEST.timeoutMs = 20;
  const {UNDO_REQUEST, readUndoResponse} = require(root + '/app/autumbra/undo/request.ts');
  UNDO_REQUEST.timeoutMs = 20;
  for (const request of [() => autumbraRequest('http://offline.invalid', {method:'POST'}, r => r.json()), () => readUndoResponse('/api/autumbra/undo', {method:'POST'})]) {
    for (const phase of ['headers', 'body']) {
      let calls = 0, signal;
      global.fetch = (url, init) => { calls++; signal = init.signal; return phase === 'headers' ? new Promise(() => {}) : Promise.resolve({json: () => new Promise(() => {})}); };
      const start = Date.now();
      await assert.rejects(request());
      assert(Date.now()-start < 500 && signal.aborted); assert.equal(calls, 1);
      global.fetch = async () => Response.json({ok:true});
      await request(); // A manual retry works after the first deadline.
    }
  }
  let calls = 0;
  global.fetch = async () => { calls++; return new Response(null, {status:302, headers:{location:'https://other.invalid'}}); };
  await assert.rejects(autumbraRequest('http://offline.invalid', {}, r => r.json()));
  assert.equal(calls, 1);
  const abort = new AbortController(); abort.abort(); calls = 0;
  await assert.rejects(readUndoResponse('/api/autumbra/undo', {signal:abort.signal}));
  assert.equal(calls, 0);
  const route = fresh('app/api/autumbra/undo/route.ts');
  for (const value of [{}, {token:'bad'}, {token:42}, {token:'x'.repeat(20001)}, null, []]) {
    global.fetch = () => assert.fail('invalid request made an upstream call');
    assert([400,401].includes((await route.POST(post(value))).status));
  }
  const {verifyUndoToken} = fresh('lib/autumbra-undo-token.ts');
  for (const exp of [true, null, '9999999999', {}, [], Math.floor(Date.now()/1000)]) assert.throws(() => verifyUndoToken(sign({...payload, exp})));
  for (const response of [Response.json({detail:'placeholder-private-upstream'}, {status:500}), Response.json({}), Response.json({queued:false})]) {
    calls = 0; global.fetch = async () => { calls++; return response; };
    const result = await route.POST(post());
    assert.equal(result.status, 502); assert.equal((await result.json()).ok, false); assert.equal(calls, 1);
  }
  global.fetch = async () => { throw Error('placeholder-private-upstream'); };
  for (const result of [await route.POST(post()), await route.GET(get())]) {
    assert.equal(result.status, 502); assert(!(await result.text()).includes('placeholder-private-upstream'));
    assert.equal(result.headers.get('referrer-policy'), 'no-referrer');
    assert.equal(result.headers.get('cache-control'), 'no-store');
  }
  global.fetch = async (url, init) => { const sent = JSON.parse(init.body); assert.equal(sent.tenant_id, 'tenant'); assert.equal(sent.prior_receipt_id, 'receipt'); return Response.json({queued:true, private:'placeholder-private-upstream'}); };
  assert.deepEqual(await (await route.POST(post({token, tenant_id:'other'}))).json(), {ok:true, queued:true});
  delete process.env.TANK_API_KEY;
  global.fetch = () => assert.fail('missing setting caused I/O');
  const missing = fresh('app/api/autumbra/undo/route.ts');
  assert.equal((await missing.POST(post())).status, 503); assert.equal((await missing.GET(get())).status, 503);
  assert.equal((await fresh('lib/autumbra-weekly.ts').loadWeeklyReceipts('tenant')).available, false);
  assert.equal((await fresh('lib/autumbra-undo-status.ts').loadUndoStatus('tenant', 'receipt')).available, false);
  process.env.TANK_API_KEY = 'placeholder-service-key';
  for (const already_undone of ['false', null, 1, {}]) {
    global.fetch = async () => Response.json({already_undone});
    assert.equal((await fresh('lib/autumbra-undo-status.ts').loadUndoStatus('tenant','receipt')).available,false);
  }
  for (const file of ['lib/autumbra-weekly.ts', 'lib/autumbra-undo-status.ts', 'app/admin/autumbra/watch-request.ts', 'app/admin/autumbra/shields-data.ts']) {
    global.fetch = () => new Promise(() => {});
    const m = fresh(file), start = Date.now();
    if (m.loadWeeklyReceipts) assert.equal((await m.loadWeeklyReceipts('tenant')).available, false);
    if (m.loadUndoStatus) assert.equal((await m.loadUndoStatus('tenant','receipt')).available, false);
    if (m.ghostPanel) await assert.rejects(m.ghostPanel('owner'));
    if (m.shieldBoard) await assert.rejects(m.shieldBoard('owner'));
    assert(Date.now()-start < 500);
  }
  const {mayReadWeeklyReceipts} = fresh('lib/autumbra-receipts-access.ts');
  assert(await mayReadWeeklyReceipts('tenant', null));
  identity = {...identity, tenantId:'other'}; assert(!(await mayReadWeeklyReceipts('tenant', null)));
  identity = {userId:null}; assert(!(await mayReadWeeklyReceipts('tenant', null)));
  assert(await mayReadWeeklyReceipts('tenant', sign({tenant_id:'tenant',purpose:'receipts',exp:payload.exp})));
  assert(!(await mayReadWeeklyReceipts('other', sign({tenant_id:'tenant',purpose:'receipts',exp:payload.exp}))));
  const own = 'https://app.tervory.com/autumbra/undo/receipt?token=' + token;
  const foreign = 'https://app.tervory.com/autumbra/undo/receipt?token=' + sign({...payload,tenant_id:'other'});
  global.fetch = async () => Response.json({time_zone:'not/a/timezone',receipts:[
    {id:'receipt',url:own,advisory_url:'https://example.test/advisory'},
    {id:'receipt',url:foreign,advisory_url:'javascript:alert(1)'},
    {id:'receipt',url:'https://evil.invalid/?token=x',advisory_url:'https://user:pass@example.test'},
    {id:{invalid:true},site:{invalid:true},timestamp:[],severity:42},
  ]});
  const weekly = await fresh('lib/autumbra-weekly.ts').loadWeeklyReceipts('tenant');
  assert.equal(weekly.available,true); assert.equal(weekly.timeZone,'UTC');
  assert.equal(weekly.receipts[0].url,own); assert.equal(weekly.receipts[0].advisory_url,'https://example.test/advisory');
  assert.equal(weekly.receipts[1].url,undefined); assert.equal(weekly.receipts[1].advisory_url,undefined);
  assert.equal(weekly.receipts[2].url,undefined); assert.equal(weekly.receipts[2].advisory_url,undefined);
  assert.deepEqual(weekly.receipts[3],{});
  const actions = fresh('app/admin/autumbra/actions.ts');
  process.env.TERVORY_ADMIN_USER_IDS = 'owner';
  global.fetch = () => assert.fail('unauthorized or invalid action made an upstream call');
  identity = {userId:'other',tenantId:'tenant'};
  for (const action of [actions.look, actions.resolve, actions.shieldAction]) {
    assert.equal((await action(null,new FormData())).ok,false);
  }
  identity = {userId:'owner',tenantId:'tenant'};
  for (const tap of ['', 'invalid']) {
    const form = new FormData(); form.set('id','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'); form.set('tap',tap);
    assert.equal((await actions.shieldAction(null,form)).ok,false);
  }
  for (const tap of ['raise','undo']) {
    global.fetch = async url => { assert(String(url).endsWith('/'+tap)); return Response.json({state:tap==='undo'?'withdrawn':'dry_run'}); };
    const form = new FormData(); form.set('id','aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'); form.set('tap',tap);
    assert.equal((await actions.shieldAction(null,form)).ok,true);
  }
  console.log('Autumbra bounded requests, retries, auth, isolation, errors and receipt links passed');
}
main().catch(error => { console.error(error); process.exitCode=1; });
