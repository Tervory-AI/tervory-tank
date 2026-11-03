const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),Module=require('node:module');
const root=path.resolve(__dirname,'../..'),ts=require(path.join(root,'workspace/node_modules/typescript'));
require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,f);
let session={};
const load=Module._load;
Module._load=function(name,...rest){if(name==='@/app/api/zenas/tank')return require(path.join(root,'workspace/app/api/zenas/tank.ts'));if(name==='@clerk/nextjs/server')return {auth:async()=>session};return load.call(this,name,...rest);};
process.env.TANK_API_KEY='dummy-workspace-key';process.env.TANK_URL='http://tank.invalid';
const {triggerIdentity}=require(path.join(root,'workspace/lib/trigger.ts'));
const {tenantIdFor}=require(path.join(root,'workspace/lib/tenant.ts'));
const {commandRequest}=require(path.join(root,'workspace/lib/tank.ts'));
const tenant={orgId:'org_offline',tenantId:tenantIdFor('org_offline'),userId:'offline-user',orgName:'Offline'};
let sent;
global.fetch=async(_url,init)=>{sent=init.headers;return Response.json({});};
(async()=>{
 for(const [patch,expected] of [[{},true],[{orgRole:'org:member'},false],[{orgId:'org_other'},false],[{userId:'other'},false]]){
  session={orgId:tenant.orgId,userId:tenant.userId,orgRole:'org:admin',...patch};
  const identity=await triggerIdentity(tenant);assert.equal(identity.tenantAdmin,expected);
  await commandRequest(identity,'tools',{headers:{'x-tervory-role':'org:admin','x-tervory-squad':'trigger','x-tervory-tenant':'forged'}});
  assert.equal(sent.get('x-tervory-role'),expected?'org:admin':'');
  assert.equal(sent.get('x-tervory-tenant'),tenant.tenantId);assert.equal(sent.has('x-tervory-squad'),false);
 }
 assert.equal(await triggerIdentity(null),null);
 console.log('PASS: Clerk session user/org/tenant binding; ordinary members and forged headers cannot grant admin voice tools.');
})().catch(e=>{console.error(e);process.exitCode=1;});
