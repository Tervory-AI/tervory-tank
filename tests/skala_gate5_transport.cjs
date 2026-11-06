const assert = require('node:assert/strict');
const fs = require('node:fs');
const {test} = require('node:test');
const {loader} = require('./skala_gate5_support.cjs');
const sources = JSON.parse(fs.readFileSync(0, 'utf8'));
const settings = {TANK_API_KEY: 'offline-placeholder', TANK_URL: 'http://tank.test'};
const response = (data, status=200) => Response.json(data, {status});

test('client requests bound stalled headers and bodies and never replay writes', async () => {
  for (const stage of ['headers', 'body']) {
    let calls = 0, signal;
    const load = loader(sources, {}, {fetch: async (_, init) => {
      calls++; signal = init.signal;
      return stage === 'headers' ? new Promise(() => {}) : new Response(new ReadableStream({start(){}}));
    }});
    const {skalaFetch} = load('workspace/app/skala/request.ts');
    await assert.rejects(skalaFetch('/api/skala', {method: 'POST'}, 20), /could not be reached/);
    assert.equal(calls, 1); assert.equal(signal.aborted, true);
  }
});

test('read retries stop after one retry and writes require explicit retry', async () => {
  let calls = 0;
  const {skalaFetch} = loader(sources, {}, {fetch: async () => { calls++; return response({}, 503); }})('workspace/app/skala/request.ts');
  assert.equal((await skalaFetch('/api/skala')).status, 503); assert.equal(calls, 2);
  calls = 0;
  assert.equal((await skalaFetch('/api/skala', {method: 'POST'})).status, 503); assert.equal(calls, 1);
});

test('server bounds stalled Tank responses, preserves request IDs and refuses redirects', async () => {
  let calls = 0, seen;
  const load = loader(sources, {
    '@/lib/trigger-signin-fetch': {signinFetch: async (_, init) => { calls++; seen = init;
      return new Response(new ReadableStream({start(){}})); }},
    '@/app/api/zenas/tank': {regionTank: () => null},
  }, {}, settings);
  const api = load('workspace/lib/tank.ts'); api.SKALA_SERVER_TIMEOUT_MS.value = 20;
  await assert.rejects(api.runSkillEvals('base.test', '1.0.0', 'founder', 'request-one'), /deadline/);
  assert.equal(calls, 1); assert.equal(seen.headers.get('idempotency-key'), 'request-one');
  assert.equal(seen.signal.aborted, true);
  const redirect = loader(sources, {
    '@/lib/trigger-signin-fetch': {signinFetch: async () => response({}, 302)},
    '@/app/api/zenas/tank': {regionTank: () => null},
  }, {}, settings)('workspace/lib/tank.ts');
  await assert.rejects(redirect.listSkills(), /redirect/);
});

test('API auth, CSRF, identifiers and input shapes are checked before upstream work', async () => {
  let founder = false, calls = 0;
  const upstream = new Proxy({}, {get: () => async () => {calls++; throw new Error('offline-private-placeholder');}});
  const api = loader(sources, {
    'next/server': {NextResponse: {json: (body, init) => Response.json(body, init)}},
    '@/lib/tank': upstream,
    '@/app/review/access': {rejectUnlessFounder: async () => founder ? null : {status:404,error:'Not found'}},
    '@/lib/tenant': {currentTenant: async () => ({userId:'founder',tenantId:'offline-tenant'})},
  })('workspace/app/api/skala/route.ts');
  function req(body, origin='https://app.test') {return new Request('https://app.test/api/skala', {
    method:'POST', headers:{origin,host:'app.test'},body:JSON.stringify(body)});}
  assert.equal((await api.GET()).status,404);
  assert.equal((await api.POST(req({action:'evals',id:'base.test',version:'1.0.0'}))).status,404);
  founder=true;
  assert.equal((await api.POST(req({action:'evals'},'https://evil.test'))).status,403);
  for (const body of [[],{action:'evals',id:'../x',version:'1.0.0'},
      {action:'evals',id:'base.test',version:'../../x'},{action:'try',id:'base.test',version:'1.0.0',input:[]}]) {
    assert.equal((await api.POST(req(body))).status,400);
  }
  assert.equal(calls,0);
  const failure=await api.POST(req({action:'evals',id:'base.test',version:'1.0.0'}));
  assert.equal(failure.status,502);
  assert.doesNotMatch(await failure.text(), /offline-private-placeholder/);
});

test('gold identity never accepts a tenant or reviewer identity from the body', async () => {
  let user=null, role='member', calls=[];
  const load=loader(sources, {
    '@/lib/trigger-signin': {auth: async () => ({userId:user,orgRole:role})},
    'next/navigation': {notFound(){throw new Error('Not found');}},
    '@/app/review/access': {rejectUnlessFounder:async()=>role==='founder'?null:{status:404}, requireReviewer:async()=>{if(role!=='reviewer')throw new Error('Not found');}},
    '@/lib/tenant': {currentTenant:async()=>({tenantId:'verified-tenant'})},
    'next/server': {NextResponse:{json:(body,init)=>Response.json(body,init)}},
    '@/lib/tank': {goldSummary:async identity=>{calls.push(identity);return {};},checkGold:async identity=>{calls.push(identity);return {ok:true};}},
  });
  const access=load('workspace/app/skala/gold/access.ts');
  await assert.rejects(access.goldIdentity('tenant'),/Not found/);
  user='new-member';await assert.rejects(access.goldIdentity('tenant'),/Not found/);
  role='reviewer';
  const api=load('workspace/app/api/skala/gold/route.ts');
  const request=new Request('https://app.test/api/skala/gold?scope=tenant',{method:'POST',headers:{host:'app.test',origin:'https://app.test'},body:JSON.stringify({id:'00000000-0000-0000-0000-000000000001',action:'right',tenantId:'forged',userId:'forged'})});
  assert.equal((await api.POST(request)).status,200);
  assert.equal(calls[0].tenantId,'verified-tenant'); assert.equal(calls[0].userId,'new-member');
  await assert.rejects(access.goldIdentity('forged'),/Not found/);
});
