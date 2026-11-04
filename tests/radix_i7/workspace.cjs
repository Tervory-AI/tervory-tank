const assert = require('node:assert/strict');
const path = require('node:path');
process.env.COMMAND_TEST_TOOLS = path.resolve('workspace/node_modules');
const {workspace} = require('../command_acceptance_20261031/workspace_loader.cjs');
const id = '33333333-3333-4333-8333-333333333333';
const tenant = '11111111-1111-4111-8111-111111111111';
let signedIn = true;
const calls = [];
class CommandRequestError extends Error {constructor(status,code,message){super(message);this.status=status;this.code=code;}}
const load = workspace({env:{}, fetch:()=>{throw Error('placeholder network called');},mocks:{
  '@/lib/trigger':{triggerIdentity:async()=>signedIn?{tenantId:tenant,userId:'placeholder-client'}:null},
  '@/lib/tenant':{activeTenant:async()=>({tenantId:tenant})}, '@/lib/admin':{isFounder:()=>false},
  '@/lib/tank':{CommandRequestError,commandRequest:async(identity,target)=>{
    calls.push({identity,target});
    assert.equal(identity.tenantId,tenant);
    if(target.endsWith('/evidence/11')) return Response.json({rule:'placeholder-rule-11'});
    assert.equal(target,`radix/reports/${id}/html`);
    return new Response('<html>placeholder complete report</html>',{headers:{'Content-Type':'text/html','Content-Disposition':`attachment; filename*=UTF-8''radix-${id}.html`}});
  }},
  '../../models':{modelValue:value=>value},
}});
(async()=>{
  const handler=load('app/chats/api/[...path]/route.ts');
  const target=`radix/reports/${id}/html`;
  const response=await handler.GET(new Request(`https://app.tervory.com/chats/api/${target}?tenant_id=placeholder-other`),{params:Promise.resolve({path:target.split('/')})});
  assert.equal(response.status,200);
  assert.equal(response.headers.get('content-type'),'application/octet-stream');
  assert.equal(response.headers.get('cache-control'),'private, no-store');
  assert.equal(response.headers.get('x-content-type-options'),'nosniff');
  assert(response.headers.get('content-disposition').endsWith('.html'));
  assert((await response.text()).includes('placeholder complete report'));
  assert.equal(calls[0].target,target); // Browser query cannot select another tenant.
  const proof=`radix/reports/${id}/evidence/11`;
  const evidence=await handler.GET(new Request(`https://app.tervory.com/chats/api/${proof}`),{params:Promise.resolve({path:proof.split('/')})});
  assert.equal((await evidence.json()).rule,'placeholder-rule-11');
  signedIn=false;
  const refused=await handler.GET(new Request(`https://app.tervory.com/chats/api/${target}`),{params:Promise.resolve({path:target.split('/')})});
  assert.equal(refused.status,401);assert.equal(calls.length,2);
  const {presentCard}=load('app/chats/presentation.ts');
  const card=presentCard({card_id:'placeholder',tool:'radix.report',kind:'other',summary:'radix.findings',result:{url:`https://app.tervory.com/chats/api/${target}`,cost_usd:0}},false);
  assert(card.results.some(row=>row.label==='Result'&&row.href===`https://app.tervory.com/chats/api/${target}`));
  console.log('PASS: authenticated report download, tenant query ignored, private attachment, existing Result link; no new label');
})().catch(error=>{console.error(error);process.exitCode=1;});
