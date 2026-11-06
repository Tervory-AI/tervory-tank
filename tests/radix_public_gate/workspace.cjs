const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
process.env.COMMAND_TEST_TOOLS = path.resolve('workspace/node_modules');
const {workspace} = require(path.join(process.argv[2], 'tests/command_acceptance_20261031/workspace_loader.cjs'));
const wire = JSON.parse(fs.readFileSync(0, 'utf8'));
const initial = new Headers(wire.headers);
const key = initial.get('x-tank-key');
const tenant = initial.get('x-tervory-tenant');
const calls = [];
let upstream = () => Response.json(wire.upstream);
const env = {TANK_API_KEY: key, TANK_URL: 'http://placeholder-tank:8000'};
const load = workspace({env, fetch: async (input, init) => {
  const url = new URL(input);
  assert.equal(url.origin, env.TANK_URL);
  assert.equal(url.pathname, '/v1/command/radix/deploy/gate');
  assert.deepEqual([...url.searchParams], [...new URL(wire.url).searchParams]);
  const headers = new Headers(init.headers);
  assert.deepEqual([...headers.keys()].sort(), ['accept', 'x-tank-key', 'x-tervory-tenant']);
  assert.equal(headers.get('x-tank-key'), key);
  assert.equal(headers.get('x-tervory-tenant'), tenant);
  assert.equal(init.method, 'GET');
  assert.equal(init.redirect, 'manual');
  assert.equal(init.cache, 'no-store');
  assert(init.signal instanceof AbortSignal);
  calls.push(url.toString());
  return upstream();
}, mocks: {
  '@/app/api/zenas/tank': {regionTank: () => {throw Error('unexpected regional forwarding');}},
  'next-auth/jwt': {getToken: () => {throw Error('service request must not require browser sign-in');}},
  'next/server': {NextResponse: {next: () => new Response(null, {status: 204})}},
}});
const request = (changes = {}, url = wire.url, method = 'GET') => {
  const headers = new Headers(initial);
  for (const [name, value] of Object.entries(changes)) value === null ? headers.delete(name) : headers.set(name, value);
  return new Request(url, {method, headers});
};
const check = async (response, status) => {
  assert.equal(response.status, status);
  assert.equal(response.headers.get('cache-control'), 'private, no-store');
  if (status !== 200) assert.deepEqual(await response.json(), {});
};
(async () => {
  // Reproduce the old public-only failure using the actual catch-all: no fetch.
  const old = load('app/v1/command/[...path]/route.ts');
  assert.equal((await old.GET(request(), {params: Promise.resolve({path: ['radix','deploy','gate']})})).status, 401);
  assert.equal(calls.length, 0);
  const middleware = load('middleware.ts').default;
  const incoming = request({host: 'tank.tervory.com'});
  incoming.nextUrl = new URL(incoming.url);
  assert.equal((await middleware(incoming)).status, 204);

  // Next's exact route handles GET before the catch-all. No new write corridor.
  const route = load('app/v1/command/radix/deploy/gate/route.ts');
  assert.deepEqual(Object.keys(route).sort(), ['GET','dynamic','runtime']);
  const accepted = await route.GET(request({cookie: 'placeholder-cookie', authorization: 'Bearer placeholder',
    'x-tervory-user': 'placeholder-forged', 'x-tervory-admin': 'placeholder-forged',
    'x-trigger-signin-token': 'placeholder-forged', 'x-tervory-role': 'org:admin'}));
  await check(accepted, 200);
  assert.deepEqual(await accepted.json(), wire.upstream);
  assert.equal(calls.length, 1);
  for (const bad of [null, 'placeholder-wrong', 'x'.repeat(key.length)]) {
    await check(await route.GET(request({'x-tank-key': bad})), 401);
  }
  for (const other of [null, '00000000-0000-0000-0000-000000000012']) {
    await check(await route.GET(request({'x-tervory-tenant': other})), 403);
  }
  for (const query of ['&app=main', '&tenant_id='+tenant, '&url=https://placeholder.invalid', '&unknown=1']) {
    await check(await route.GET(request({}, wire.url+query)), 400);
  }
  for (const [name,value] of [['tenant_id','placeholder-bad'],['app','../override']]) {
    const url = new URL(wire.url); url.searchParams.set(name,value);
    await check(await route.GET(request({},url)),400);
  }
  await check(await route.GET(request({},wire.url,'POST')),405);
  env.TANK_API_KEY = '';
  await check(await route.GET(request()),503);
  env.TANK_API_KEY = key;
  assert.equal(calls.length,1);

  for (const status of [401,403,503]) {
    upstream = () => new Response('placeholder-private-error', {status});
    await check(await route.GET(request()),status);
  }
  upstream = () => new Response(null,{status:302,headers:{location:'https://placeholder.invalid'}});
  const beforeRedirect = calls.length;
  await check(await route.GET(request()),502);
  assert.equal(calls.length,beforeRedirect+1);
  upstream = () => new Response('placeholder HTML',{headers:{'content-type':'text/html'}});
  await check(await route.GET(request()),502);
  upstream = () => new Response('{invalid',{headers:{'content-type':'application/json'}});
  await check(await route.GET(request()),502);
  upstream = () => {throw Error(key);};
  await check(await route.GET(request()),502);

  // Service keys still cannot enter the generic personal or mutation routes.
  for (const parts of [['threads'], ['radix','deploy','override']]) {
    assert.equal((await old.POST(request({},wire.url,'POST'), {params:Promise.resolve({path:parts})})).status,401);
  }
  console.log('PASS: public service-key gate matches internal decision, tenant/auth refusals, exact GET scope, no redirects or identity forwarding.');
})().catch(error => {console.error(error);process.exitCode=1;});
