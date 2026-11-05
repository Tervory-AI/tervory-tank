// Actual proof transport; only cookie/native-provider and HTTP boundaries are fake.
const assert = require('node:assert/strict');
const fs = require('node:fs'), path = require('node:path'), Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const target = path.join(root, 'workspace/lib/trigger-signin-fetch.ts');
let native = {}, cookie;
const original = Module._load;
Module._load = function(name, parent, ...args) {
  if (parent?.filename === target) {
    if (name === 'server-only') return {};
    if (name === 'next/headers') return {cookies: async () => ({get: () => cookie ? {value: cookie} : undefined})};
    if (name === './trigger-signin') return {auth: async () => native, signinToken: async () => 'placeholder-native-proof'};
  }
  return original.call(this, name, parent, ...args);
};
require.extensions['.ts'] = (m, file) => m._compile(ts.transpileModule(fs.readFileSync(file, 'utf8'),
  {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText, file);
Object.assign(process.env, {TANK_URL:'http://tank:8000', TANK_URL_ZA:'https://za.invalid'});
const {signinFetch} = require(target);
let calls = [];
globalThis.fetch = async (url, init) => {calls.push({url:String(url),headers:new Headers(init.headers)}); return Response.json({ok:true});};
const tenantA = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', tenantB = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb';
const headers = (user, tenant) => ({'x-tank-key':'placeholder-key','x-tervory-user':user,'x-tervory-tenant':tenant});
(async () => {
  native = {userId:'native-user',orgId:'10001',tenantId:tenantA};
  await signinFetch('http://tank:8000/v1/command/threads', {headers:headers('native-user',tenantA)});
  assert.equal(calls.at(-1).headers.get('x-trigger-signin-token'),'placeholder-native-proof');
  assert.equal(calls.at(-1).headers.get('x-mobile-session'),null);
  native = {}; cookie = tenantB+'_'+'s'.repeat(43);
  await signinFetch('http://tank:8000/v1/command/threads', {headers:headers('mobile-user',tenantB)});
  assert.equal(calls.at(-1).headers.get('x-mobile-session'),cookie);
  assert.equal(calls.at(-1).headers.get('x-trigger-signin-token'),null);
  // Tenant helpers selected mobile B while a native A browser cookie also exists.
  native = {userId:'native-user',orgId:'10001',tenantId:tenantA};
  await signinFetch('http://tank:8000/v1/command/threads', {headers:headers('mobile-user',tenantB)});
  assert.equal(calls.at(-1).headers.get('x-mobile-session'),cookie);
  assert.equal(calls.at(-1).headers.get('x-trigger-signin-token'),null);
  native = {}; const count = calls.length;
  await assert.rejects(() => signinFetch('https://za.invalid/v1/command/threads', {headers:headers('mobile-user',tenantB)}));
  assert.equal(calls.length,count); // The opaque session never leaves its owning box.
  cookie = 'invalid';
  await assert.rejects(() => signinFetch('http://tank:8000/v1/command/threads', {headers:headers('mobile-user',tenantB)}));
  cookie = undefined; native = {userId:'native-user',orgId:'10001',tenantId:tenantA};
  await assert.rejects(() => signinFetch('http://tank:8000/v1/command/threads', {headers:headers('other-user',tenantB)}));
  console.log('mobile native proof-selection contract passed');
})().catch(error => {console.error(error);process.exitCode=1;});
