"""Execute Workspace auth/actions/billing with offline boundaries, no Clerk/Stripe calls."""
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_workspace_3d_admin_authorization_billing_and_server_owned_identity():
    script = r'''
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path');
const {createRequire} = require('node:module');
const root = process.cwd(), wr = createRequire(root + '/workspace/package.json');
const ts = wr('typescript'), React = wr('react'), {renderToStaticMarkup} = wr('react-dom/server');
let session = {}, calls = [], granted = false, fail = false;
const read = async (...args) => { calls.push(args); if (fail) throw Error('private diagnostic'); return new Response(JSON.stringify({rig_3d: granted, billing: {price: null}})); };
const cache = new Map();
function load(filename) {
  filename = path.resolve(filename);
  if (cache.has(filename)) return cache.get(filename).exports;
  const mod = {exports: {}}; cache.set(filename, mod);
  const source = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX}}).outputText;
  function local(spec) {
    if (spec === '@/lib/tank') return {rigThreeDRequest: read};
    if (spec === '@clerk/nextjs/server') return {auth: async () => session};
    if (spec === 'next/navigation') return {redirect: value => {throw {redirect: value};}};
    if (spec === 'next/cache') return {revalidatePath: () => {}};
    if (spec.startsWith('.') || spec.startsWith('@/')) {
      const base = spec.startsWith('@/') ? root+'/workspace/'+spec.slice(2) : path.resolve(path.dirname(filename), spec);
      return load(['', '.ts', '.tsx'].map(s => base+s).find(s => fs.existsSync(s) && fs.statSync(s).isFile()));
    }
    return wr(spec);
  }
  new Function('require', 'module', 'exports', source)(local, mod, mod.exports);
  return mod.exports;
}
(async () => {
  const dir = root + '/workspace/app/rig/admin/three-d/';
  const {administrator} = load(dir+'server.ts'), {changeThreeD} = load(dir+'actions.ts');
  const {loadRigThreeDBilling, RigThreeDAddon} = load(root+'/workspace/app/billing/rig-three-d.tsx');
  for (const value of [{}, {userId:'u', orgId:'org_sample', orgRole:'org:member'}, {userId:'u', orgRole:'org:admin'}]) {
    session = value; await assert.rejects(administrator);
    const form = new FormData(); form.set('operation','reset'); form.set('tenant_id','foreign');
    await assert.rejects(changeThreeD(form), err => err.redirect.endsWith('notice=failed'));
    assert.equal(calls.length,0);
  }
  session = {userId:'reviewer', orgId:'org_sample', orgRole:'org:admin'};
  const identity = await administrator();
  const form = new FormData(); form.set('operation','reset'); form.set('tenant_id','foreign'); form.set('actor','forged'); form.set('id','00000000-0000-0000-0000-000000000001');
  await assert.rejects(changeThreeD(form), err => err.redirect.endsWith('notice=reset'));
  assert.deepEqual(calls.pop(), [identity.tenantId,'reset',{id:form.get('id')},'reviewer']);
  form.set('operation','entitlement'); await assert.rejects(changeThreeD(form), err => err.redirect.endsWith('notice=failed')); assert.equal(calls.length,0);
  process.env.RIG_3D_PRICE_ID = '';
  let view = await loadRigThreeDBilling(identity.tenantId);
  let html = renderToStaticMarkup(React.createElement(RigThreeDAddon,{view}));
  assert(html.includes('Not available yet')); assert(!/<button|<form|checkout|price_/.test(html));
  process.env.RIG_3D_PRICE_ID = 'price_fixture';
  view = await loadRigThreeDBilling(identity.tenantId);
  html = renderToStaticMarkup(React.createElement(RigThreeDAddon,{view}));
  assert(html.includes('confirm the price')); assert(!/<button|<form|checkout|price_fixture/.test(html));
  granted = true; view = await loadRigThreeDBilling(identity.tenantId);
  assert(renderToStaticMarkup(React.createElement(RigThreeDAddon,{view})).includes('Included for this organisation'));
  fail = true; assert.equal((await loadRigThreeDBilling(identity.tenantId)).enabled,null);
  assert(calls.every(call => call[1] === 'capabilities'));
  const jobId = '00000000-0000-0000-0000-000000000002';
  const submit = new FormData();
  for (const [key,value] of Object.entries({operation:'submit',jobId,product:'centre',source:'cad',files:'centre.step',width:'160',height:'70',depth:'110',limit:'0',anchors:'left, -60, 35, 0, 0, 0, 0, 1'})) submit.set(key,value);
  await assert.rejects(changeThreeD(submit), err => err.redirect.endsWith('&job='+jobId));
  const sent = calls.at(-1); assert.equal(sent[0],identity.tenantId); assert.equal(sent[3],'reviewer');
  assert.equal(sent[2].tenant_id,identity.tenantId); assert.equal(sent[2].inputs[0],identity.tenantId+'/uploads/centre.step');
  assert.deepEqual(sent[2].anchors.left,{position_mm:[-60,35,0],quaternion:[0,0,0,1]});
  console.log('Admin role, server-owned tenant/actor, retry id, anchors and disabled billing passed.');
})().catch(error => {console.error(error);process.exitCode=1;});
'''
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
