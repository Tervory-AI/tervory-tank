// Actual Workspace client; only HTTP is replaced. No provider or external call.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const original = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  if (name.startsWith('@/')) name = path.join(root, 'workspace', name.slice(2));
  return original.call(this, name, parent, ...rest);
};
require.extensions['.ts'] = (m, f) => m._compile(ts.transpileModule(fs.readFileSync(f, 'utf8'),
  {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, f);
Object.assign(process.env, {TANK_URL: 'http://us.invalid', TANK_API_KEY: 'local-workspace',
  TANK_REGION: 'us-east', TANK_URL_ZA: 'https://za.invalid', TANK_CONTENT_API_KEY_ZA: 'za-content',
  TANK_API_KEY_ZA: 'homes-only'});
const tank = require('../workspace/lib/tank.ts');
const tenant = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', other = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const identity = {tenantId: tenant, userId: 'clerk-user'};
let mode = 'za', calls = [];
global.fetch = async (raw, init) => {
  const url = new URL(String(raw)), headers = new Headers(init.headers);
  calls.push({url, headers, body: init.body, method: init.method});
  assert.equal(init.redirect, 'manual');
  if (url.pathname === '/v1/tenants/' + tenant + '/home') {
    assert(init.signal instanceof AbortSignal);
    assert.equal(url.origin, 'http://us.invalid');
    assert.equal(headers.get('x-tank-key'), 'local-workspace');
    if (init.method === 'PUT') return Response.json({tenant_id: tenant, home_region: 'za'});
    assert.equal(init.method, 'GET');
    assert.equal(init.body, undefined); // Metadata lookup never receives content.
    assert.equal(url.search, '');
    if (mode === 'missing') return Response.json({detail:{code:'tenant_home_missing'}}, {status:404});
    if (mode === 'unavailable') return Response.json({detail:'not ready'}, {status:503});
    if (mode === 'old-endpoint') return Response.json({detail:'Not Found'}, {status:404});
    if (mode === 'prototype') return Response.json({});
    if (mode === 'prototype-missing') return Response.json({}, {status:404});
    if (mode === 'redirect') return new Response(null, {status:302,headers:{location:'https://other.invalid'}});
    return Response.json({tenant_id: mode === 'mismatch' ? other : tenant,
      home_region: mode === 'invalid' ? 'elsewhere' : 'za'});
  }
  return Response.json(url.pathname === '/v1/command/tools' ? ['base.list'] : {ok:true});
};

(async()=>{
  assert.deepEqual(await tank.commandTools(identity), ['base.list']);
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url.origin, 'https://za.invalid');
  assert.equal(calls[1].headers.get('x-tank-key'), 'za-content');
  assert.equal(calls[1].headers.get('x-tervory-home-region'), 'za');
  calls=[];
  await tank.commandRequest(identity,'turns',{method:'POST',headers:{
    'x-tank-key':'spoof','x-tervory-tenant':other,'x-tervory-user':'spoof',
    'x-tervory-home-region':'us-east','x-tervory-squad':'tiger','x-tervory-role':'founder'},
    body:JSON.stringify({text:'private content'})});
  assert.equal(calls.length,2);
  assert.equal(calls[1].headers.get('x-tervory-tenant'),tenant);
  assert.equal(calls[1].headers.get('x-tervory-user'),'clerk-user');
  assert.equal(calls[1].headers.get('x-tervory-squad'),null);
  assert.equal(calls[1].headers.get('x-tervory-role'),'');
  assert.equal(calls[1].headers.get('x-tank-key'),'za-content');
  assert.equal(calls[1].headers.get('x-tervory-home-region'),'za');
  assert.equal(JSON.parse(calls[1].body).text,'private content');
  calls=[];
  await tank.createTask(tenant,'clerk-user','Task','tier0.answer',[{role:'user',content:'private task'}]);
  assert.equal(calls[1].url.origin,'https://za.invalid');
  assert.equal(calls[1].headers.get('x-tank-key'),'za-content');
  for (const send of [
    ()=>tank.marketLabRequest(tenant,'overview'),
    ()=>tank.baseProductRequest(tenant,'overview'),
    ()=>tank.memoryRecord({...identity,role:'reviewer'},tenant),
    ()=>tank.vaultPlugins('base.vault','base',tenant,identity.userId),
    ()=>require('../workspace/app/api/zenas/tank.ts').zenas('matters?tenant_id='+tenant),
  ]) {
    calls=[];
    await send();
    assert.equal(calls.length,2);
    assert.equal(calls[1].url.origin,'https://za.invalid');
    assert.equal(calls[1].headers.get('x-tank-key'),'za-content');
    if (calls[1].url.pathname.startsWith('/v1/zenas/')) assert.equal(calls[1].url.searchParams.get('home_region'),'za');
  }
  calls=[];
  await tank.workspaceRequest(identity,'/tasks');
  assert.equal(calls[1].url.pathname,'/v1/workspace/tasks');
  assert.equal(calls[1].headers.get('x-tervory-tenant'),tenant);
  delete process.env.TANK_CONTENT_API_KEY_ZA;
  calls=[];
  await assert.rejects(()=>tank.commandTools(identity));
  assert.equal(calls.length,1); // Homes credential cannot substitute for content.
  process.env.TANK_CONTENT_API_KEY_ZA='za-content';
  for (mode of ['unavailable','old-endpoint','mismatch','invalid','redirect']) {
    calls=[];
    await assert.rejects(()=>tank.commandTools(identity));
    assert.equal(calls.length,1,mode+' must fail before sending content or retrying');
  }
  try {
    Object.prototype.tenant_id=tenant; Object.prototype.home_region='za';
    Object.prototype.detail={code:'tenant_home_missing'};
    assert.equal(tank.requestTenant('/v1/controls',{body:JSON.stringify({paused:true})}),null);
    for(mode of ['prototype','prototype-missing']) {
      calls=[];await assert.rejects(()=>tank.commandTools(identity));assert.equal(calls.length,1);
    }
  } finally {
    delete Object.prototype.tenant_id;delete Object.prototype.home_region;delete Object.prototype.detail;
  }
  mode='missing';calls=[];
  await tank.commandTools(identity);
  assert.equal(calls[1].url.origin,'http://us.invalid');
  assert.equal(calls[1].headers.get('x-tank-key'),'local-workspace');
  calls=[];
  await tank.onboardTenantHome('founder-user',other,tenant,'za');
  assert.equal(calls.length,1);
  assert.equal(calls[0].url.origin,'http://us.invalid');
  assert.equal(calls[0].headers.get('x-tervory-user'),'founder-user');
  assert.equal(calls[0].headers.get('x-tervory-tenant'),other);
  assert.deepEqual(JSON.parse(calls[0].body),{home_region:'za'});
  console.log('Tenant home routing, content credentials, identity and fail-closed metadata passed.');
})().catch(error=>{console.error(error);process.exitCode=1});
