const assert=require('node:assert/strict');
const {workspace}=require('../command_acceptance_20261031/workspace_loader.cjs');
const tenant={tenantId:'00000000-0000-0000-0000-000000000011',orgId:'1001',userId:'placeholder-user',orgName:'placeholder store'};
let session={...tenant,orgRole:'org:admin'}, mobile=null, identities=0, calls=[];
const load=workspace({env:{},fetch(){throw Error('Unexpected network');},mocks:{
  '@/lib/trigger-signin':{auth:async()=>session},
  './tenant':{tenantIdFor:org=>org==='1001'?tenant.tenantId:'00000000-0000-0000-0000-000000000012'},
  './mobile':{mobileIdentity:async()=>mobile},
  '@/lib/tenant':{activeTenant:async()=>{identities++;return tenant;}},
  '@/lib/tank':{commandRequest:async(actor,path,init)=>{calls.push({actor,path,init});return {json:()=>new Promise(()=>{})};}},
}});
(async()=>{
  const helper=load('app/trigger/request.ts');
  const identity=load('lib/trigger.ts').triggerIdentity;
  assert.equal((await identity(tenant)).tenantAdmin,true);
  for(const patch of [{orgId:'1002'},{userId:'another-user'},{orgRole:'org:member'}]) {
    session={...tenant,orgRole:'org:admin',...patch};
    assert.equal((await identity(tenant)).tenantAdmin,false);
  }
  mobile={...tenant,tenantAdmin:false};session={...tenant,orgRole:'org:admin',orgId:'1002'};
  assert.equal((await identity(tenant)).tenantAdmin,false);
  mobile=null;session={...tenant,orgRole:'org:admin'};
  assert.equal(helper.clientError(new Error('placeholder private credential')), 'The action could not be completed. Please try again.');
  await assert.rejects(helper.waitForAction(new Promise(()=>{}),10),/outcome is unknown/);
  assert.equal(await helper.waitForAction(Promise.resolve('owned result'),10),'owned result');
  const actionLoad=workspace({env:{},fetch(){throw Error('Unexpected network');},mocks:{
    '@/lib/trigger':{triggerIdentity:identity},
    '@/lib/tenant':{activeTenant:async()=>{identities++;return tenant;}},
    '@/lib/tank':{commandRequest:async(actor,path,init)=>{calls.push({actor,path,init});return {json:()=>new Promise(()=>{})};}},
    './request':{waitForAction:(promise,ms)=>{assert.equal(ms,10000);return helper.waitForAction(promise,10);}},
  }});
  const actions=actionLoad('app/trigger/actions.ts');
  const before=identities;
  await assert.rejects(actions.confirmTrigger(tenant.tenantId,tenant.tenantId,'delete'));
  assert.equal(identities,before);assert.equal(calls.length,0);
  await assert.rejects(actions.readTrigger('crm','leads'),/outcome is unknown/);
  assert.equal(calls.length,1);assert.equal(calls[0].actor.tenantId,tenant.tenantId);
  assert(calls[0].init.signal);
  console.log('PASS bounded headers/body, no automatic retry, sanitized errors, bound native/mobile roles and malformed mutations');
})().catch(e=>{console.error(e);process.exitCode=1;});
