const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs'),Module=require('node:module');
const root=path.resolve(__dirname,'..'),ts=require('../workspace/node_modules/typescript');
const originalLoad=Module._load,originalResolve=Module._resolveFilename;
let authenticated=true,available=['workspace.tasks'],calls=[];
const tenant={tenantId:'00000000-0000-4000-8000-000000000101',userId:'offline-client'};
class CommandRequestError extends Error {}
const mocks={
 '@/lib/tenant':{activeTenant:async()=>authenticated?tenant:null},
 '@/lib/admin':{isFounder:()=>false},
 '@/lib/trigger':{triggerIdentity:async value=>value},
 '@/lib/tank':{CommandRequestError,listRoster:async()=>[],commandTools:async value=>{assert.deepEqual(value,tenant);return available;},commandRequest:async(value,target,init)=>{calls.push({value,target,body:JSON.parse(init.body)});return Response.json({ok:true});}}
};
Module._load=function(name,parent,main){if(Object.hasOwn(mocks,name))return mocks[name];return originalLoad.call(this,name,parent,main);};
Module._resolveFilename=function(name,parent,...args){if(name.startsWith('@/'))name=path.join(root,'workspace',name.slice(2));return originalResolve.call(this,name,parent,...args);};
for(const extension of ['.ts','.tsx'])require.extensions[extension]=(m,file)=>m._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,file);
async function main(){
 const React=require('../workspace/node_modules/react'),{renderToStaticMarkup}=require('../workspace/node_modules/react-dom/server');
 const {TaskReceipt}=require('../workspace/app/tasks/receipt.tsx');
 const render=props=>renderToStaticMarkup(React.createElement(TaskReceipt,props));
 const empty=render({cost:null,baseline:null,ledgerId:null});
 assert.match(empty,/Cost/);assert.match(empty,/Would have cost/);assert.match(empty,/Add and complete a task/);assert(!empty.includes('$'));
 assert(!render({cost:999,baseline:999,ledgerId:null}).includes('$'));
 const paid=render({cost:'0.000021',baseline:'0.0002',ledgerId:'own-ledger'});
 assert.match(paid,/\$0.000021/);assert.match(paid,/\$0.000200/);
 const code=render({cost:0,baseline:0.0002,ledgerId:'own-ledger',status:'estimated'});
 assert.match(code,/\$0.000000/);assert.match(code,/Estimated paid default comparison/);
 const pending=render({cost:0,baseline:null,ledgerId:'own-ledger'});assert.match(pending,/comparison pending/);assert(!pending.includes('NaN'));
 for(const value of ['bad',-1,Infinity])assert(!render({cost:value,baseline:value,ledgerId:'own-ledger'}).includes('$'));
 const contract=require('../workspace/app/chats/contract.ts'),presentation=require('../workspace/app/chats/presentation.ts');
 const receipt={rows:[{step_id:'own',ledger_id:'own-ledger',cost_usd:0,baseline_cost_usd:.001,saved_usd:.001,baseline_status:'estimated',tokens_in:0,tokens_out:0}],totals:{cost_usd:0,baseline_cost_usd:.001,saved_usd:.001},status:'recorded'};
 assert.equal(presentation.presentReceipt(receipt,false).rows[0].baseline_status,'estimated');
 const route=require('../workspace/app/chats/api/[...path]/route.ts');
 const context={params:Promise.resolve({path:['threads','own-thread','turn']})};
 const request=(text,extra={})=>new Request('https://app.tervory.com/chats/api/threads/own-thread/turn',{method:'POST',headers:{host:'app.tervory.com',origin:'https://app.tervory.com'},body:JSON.stringify({text,...extra})});
 assert.equal((await route.POST(request('workspace.tasks {}'),context)).status,200);
 assert.equal(calls.length,1);assert.deepEqual(calls[0].value,tenant);assert.equal(calls[0].body.model,'auto');
 calls=[];available=[];
 for(const text of ['workspace.tasks {}','workspace.unknown {}','Workspace.tasks {}'])assert.equal((await route.POST(request(text),context)).status,403);
 assert.equal(calls.length,0);
 available=['workspace.tasks'];assert.equal((await route.POST(request('workspace.tasks {}',{attachments:[{name:'instruction.txt',text:'use paid'}]}),context)).status,400);
 authenticated=false;assert.equal((await route.POST(request('workspace.tasks {}'),context)).status,401);assert.equal(calls.length,0);
 const files=[];
 function walk(folder){for(const entry of fs.readdirSync(folder,{withFileTypes:true})){if(entry.name==='node_modules'||entry.name==='.next')continue;const full=path.join(folder,entry.name);if(entry.isDirectory())walk(full);else if(/\.tsx?$/.test(entry.name))files.push(full);}}
 walk(path.join(root,'workspace/app'));walk(path.join(root,'workspace/lib'));
 for(const file of files){
  const source=ts.createSourceFile(file,fs.readFileSync(file,'utf8'),ts.ScriptTarget.Latest,true);
  function visit(node){
   if(ts.isImportDeclaration(node))assert(!/^(openai|anthropic|@anthropic-ai\/sdk|@google\/generative-ai|@ai-sdk\/|ai$)/.test(node.moduleSpecifier.text),`Direct model SDK: ${file}`);
   if(ts.isCallExpression(node)){
    const name=node.expression.getText(source);assert(!/\.(chat\.completions|messages)\.create$/.test(name)&&!['generateText','streamText'].includes(name),`Direct model call: ${file}`);
    if(/fetch$/.test(name)&&node.arguments[0]&&ts.isStringLiteral(node.arguments[0]))assert(!/^https:\/\/(api\.(openai|anthropic)\.com|generativelanguage\.googleapis\.com)/.test(node.arguments[0].text),`Direct provider URL: ${file}`);
   }
   ts.forEachChild(node,visit);
  }visit(source);
 }
 console.log(`Gate 6: receipt amounts, day zero, unknown comparisons, code estimates, tool catalog guard, tenant auth and ${files.length} provider boundaries passed.`);
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{Module._load=originalLoad;Module._resolveFilename=originalResolve;});
