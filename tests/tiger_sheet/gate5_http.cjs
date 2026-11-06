const fs=require('node:fs'), path=require('node:path'), assert=require('node:assert/strict');
const ts=require(path.resolve(__dirname,'../../workspace/node_modules/typescript'));
const tenant='11111111-1111-4111-8111-111111111111';
const actor={tenantId:tenant,userId:'placeholder-user'};
const source=fs.readFileSync(process.argv[2],'utf8');
const code=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText;
let mode='ok',calls=[],signals=[];
async function fakeFetch(url,init){
 const name=new URL(url).pathname;
 assert.equal(init.redirect,'manual'); assert(init.signal);
 assert.equal(new Headers(init.headers).get('x-tank-key'),'placeholder-workspace-key');
 signals.push(init.signal);
 if(name.endsWith('/home'))return Response.json({tenant_id:tenant,home_region:'us-east'});
 calls.push({name,init});
 if(mode==='headers')return new Promise(()=>{});
 if(mode==='body')return new Response(new ReadableStream({start(){}}));
 if(mode==='redirect')return new Response(null,{status:307,headers:{location:'https://private.invalid'}});
 if(mode==='error')return Response.json({detail:'placeholder-private-value'},{status:503});
 if(mode==='empty')return new Response(null,{status:204});
 if(name.endsWith('/threads'))return Response.json({thread_id:'placeholder-thread'});
 if(name.endsWith('/actions'))return Response.json({card_id:'placeholder-card'});
 if(name.includes('/cards/'))return Response.json({status:'confirmed',result:{match:{id:'placeholder-match',tenant_id:tenant}}});
 return Response.json({watches:[],alerts:[],observations:[],products:[],matches:[]});
}
function load(configured=true){
 const exported={};
 new Function('require','exports','process','setTimeout',code)(name=>{
  if(name==='@/lib/trigger-signin-fetch')return {signinFetch:fakeFetch};
  if(name==='@/app/api/zenas/tank')return {regionTank:()=>{throw Error('unexpected directory');}};
  throw Error(name);
 },exported,{env:{TANK_URL:'https://placeholder.invalid',TANK_API_KEY:configured?'placeholder-workspace-key':''}},
 (fn,ms)=>{assert(ms>0&&ms<=300000);return setTimeout(fn,Math.min(ms,25));});
 return exported;
}
(async()=>{
 const api=load(),vault=['tiger.vault','tiger',tenant,actor.userId];
 const operations=[
  ()=>api.listTigerWatches(tenant),()=>api.listTigerAlerts(tenant),()=>api.listTigerObservations(tenant,'https://store.example/item'),
  ()=>api.createTigerWatch(tenant,{url:'https://store.example/item',every:'1h'}),()=>api.deleteTigerWatch(tenant,'placeholder-watch'),
  ()=>api.listTigerPosition(actor),()=>api.listTigerMatches(actor),()=>api.decideTigerMatch(actor,'placeholder-match','confirm'),
  ()=>api.vaultPlugins(...vault),()=>api.saveVaultSecret(...vault,'placeholder-name','Key','placeholder-value'),
  ()=>api.removeVaultSecret(...vault,'placeholder-name'),()=>api.uploadVaultFiles(...vault,new FormData()),
  ()=>api.removeVaultFile(...vault,'placeholder-file'),()=>api.addVaultLink(...vault,'https://store.example','Source','daily'),
  ()=>api.removeVaultLink(...vault,'placeholder-link'),()=>api.addVaultConnection(...vault,'Source','https://store.example','none',''),
  ()=>api.removeVaultConnection(...vault,'placeholder-connection'),
 ];
 for(const operation of operations){
  mode='ok';calls=[];signals=[];await operation();assert(calls.length>=1);
  for(const failure of ['headers','body','redirect','error']){
   mode=failure;calls=[];signals=[];
   await assert.rejects(operation,error=>!error.message.includes('placeholder-private-value'));
   assert.equal(calls.length,1,'a failed external operation must not be automatically repeated');
   if(['headers','body'].includes(failure))assert(signals.at(-1).aborted);
  }
 }
 mode='empty';assert.deepEqual(await api.removeVaultSecret(...vault,'placeholder-name'),{});
 calls=[];signals=[];await assert.rejects(load(false).listTigerWatches(tenant));assert.equal(signals.length,0);
 assert.throws(()=>api.requestTenant('/x?tenant_id=other',{body:JSON.stringify({tenant_id:tenant})}),/Conflicting/);
 console.log('all Tiger HTTP paths bounded, scoped, redacted, and never automatically replayed');
})().catch(error=>{console.error(error);process.exitCode=1;});
