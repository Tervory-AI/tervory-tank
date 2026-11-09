const assert=require('node:assert/strict'),path=require('node:path');
process.env.COMMAND_TEST_TOOLS=path.resolve('workspace/node_modules');
const {workspace}=require('../command_acceptance_20261031/workspace_loader.cjs');
const hearing='11111111-1111-4111-8111-111111111111';
const context={params:Promise.resolve({hearing})};
async function run({signedIn=true,member=true,home='us-east',origin=true,configured=true}={}){
 const calls=[];
 const load=workspace({env:configured?{MOOT_REGION:'us-east',MOOT_RUNTIME_URL:'http://local-moot',MOOT_INTERNAL_API_KEY:'placeholder-internal-key'}:{},
  mocks:{'@/lib/trigger-signin':{auth:async()=>({userId:signedIn?'member':null}),signinDirectory:async()=>({organizations:{getOrganizationMembershipList:async()=>({data:member?[{publicUserData:{userId:'member'}}]:[]})}})},
   '@/lib/tenant':{currentTenant:async()=>({tenantId:'22222222-2222-4222-8222-222222222222',orgId:'org',userId:'member'})},
   '@/lib/workspace-origin':{isWorkspaceOrigin:()=>origin},'@/lib/tank':{tenantDestination:async()=>({home})}},
  fetch:async(url,init)=>{calls.push({url:String(url),init});return Response.json({token:'fixture-room-token',identity:'fixture-participant'});}});
 const route=load('app/api/moot/media/[hearing]/route.ts');
 const req=new Request('http://workspace/api/moot/media/'+hearing,{method:'POST',body:JSON.stringify({seat:'applicant'})});
 return {response:await route.POST(req,context),calls};
}
(async()=>{
 for(const [options,status] of [[{signedIn:false},401],[{member:false},404],[{home:'za'},403],[{origin:false},403],[{configured:false},503]]){
  const result=await run(options);assert.equal(result.response.status,status);assert.equal(result.calls.length,0);
 }
 const success=await run();assert.equal(success.response.status,200);assert.equal(success.calls.length,1);
 assert.equal(success.calls[0].init.headers['X-Moot-Actor'],'member');
 assert.equal(success.calls[0].init.headers['X-Moot-Key'],'placeholder-internal-key');
 const body=await success.response.text();assert(!body.includes('placeholder-internal-key'));
 console.log('Workspace sign-in, membership, origin, region and server-only credential boundary passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
