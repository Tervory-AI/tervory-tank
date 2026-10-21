// Exercise the actual founder API route with offline identity and Tank responses.
const assert = require('node:assert/strict');
const Module = require('node:module');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const original = Module._load;
let allowed = true;
const calls = [];
const tank = new Proxy({}, {get: (_, name) => async (...args) => {
  calls.push([name, ...args]);
  return name === 'listSkills' || name === 'skillApprovalStatus' ? [] : {ok:true};
}});
Module._load = function(name, parent, isMain) {
  if (name === '@/lib/tank') return tank;
  if (name === '@/lib/tenant') return {currentTenant: async () => ({userId:'verified-founder', tenantId:'platform'})};
  if (name === '@/app/review/access') return {rejectUnlessFounder: async () => allowed ? null : {status:404,error:'Not found'}};
  if (name === '@/app/skala/library') return {tankRefusal: () => null};
  if (name === 'next/server') return {NextResponse: {json: (body, init) => Response.json(body, init)}};
  return original.call(this, name, parent, isMain);
};
require.extensions['.ts'] = (module, file) => module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'), {
  compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}
}).outputText, file);
const {POST, GET} = require('../workspace/app/api/skala/route.ts');
function req(body, origin='https://app.test') { return new Request('https://app.test/api/skala', {
  method:'POST', headers:{host:'app.test',origin,'content-type':'application/json'}, body:JSON.stringify(body)
}); }
(async () => {
  for (const action of ['bulk-preview','bulk-confirm','source-review','approve','rollback','retire']) {
    allowed = false;
    assert.equal((await POST(req({action,id:'base.test',version:'1.0.0',token:'preview'}))).status,404);
    allowed = true;
    assert.equal((await POST(req({action,id:'base.test',version:'1.0.0'},'https://other.test'))).status,403);
  }
  assert.deepEqual(calls, []);
  assert.equal((await POST(req({action:'bulk-preview',by:'spoofed'}))).status,200);
  assert.deepEqual(calls.pop(), ['previewSkillApprovals','verified-founder']);
  assert.equal((await POST(req({action:'bulk-confirm',token:'preview',confirmed:true}))).status,200);
  assert.deepEqual(calls.pop(), ['confirmSkillApprovals','verified-founder','preview',true]);
  await POST(req({action:'rollback',id:'base.test',version:'1.0.0',confirmed:'true'}));
  assert.deepEqual(calls.pop(), ['rollbackSkill','base.test','1.0.0','verified-founder',false]);
  await POST(req({action:'approve',id:'base.learned.test',version:'1.0.0',review_token:'review',confirmed:true}));
  assert.deepEqual(calls.pop(), ['approveReviewedSkill','base.learned.test','1.0.0','verified-founder','review',true]);
  await POST(req({action:'source-review',id:'base.learned.test',version:'1.0.0'}));
  assert.deepEqual(calls.pop(), ['reviewSkillSource','base.learned.test','1.0.0','verified-founder']);
  assert.equal((await POST(req({action:'bulk-confirm',confirmed:true}))).status,400);
  allowed = false;
  assert.equal((await GET()).status,404);
  assert.deepEqual(calls, []);
  console.log('Skala API founder identity, CSRF, snapshot and confirmation checks passed.');
})().catch(error => {console.error(error);process.exitCode=1});
