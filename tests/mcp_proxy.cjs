// Exercise the real forwarding helper; only fetch and server configuration are stubbed.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText, filename);
let region = 'us-east';
const original = Module._load;
Module._load = function(name, ...rest) {
  if (name === '@/app/api/zenas/tank') return {homeRegion:()=>region,regionTank:()=>null};
  if (name === '@/lib/device-login') return {approvalTank:()=>({url:'http://tank:8000',key:'offline-approval-test'})};
  if (name === '@/lib/tank') return require('../workspace/lib/tank.ts');
  return original.call(this,name,...rest);
};
const {mcpPublicRequest,mcpApproval} = require('../workspace/lib/mcp.ts');
let calls = [], answer = () => new Response('{}',{headers:{'content-type':'application/json'}});
global.fetch = async (url, init) => { calls.push({url:String(url),init}); return answer(); };
const request = (path, init={}) => new Request('https://app.tervory.com'+path,init);
(async()=>{
  const sent = {authorization:'Bearer synthetic', 'mcp-session-id':'session', 'mcp-protocol-version':'2025-11-25', accept:'application/json, text/event-stream','content-type':'application/json',origin:'https://claude.ai',cookie:'must-not-forward','x-tank-key':'must-not-forward','x-tervory-user':'founder','x-tervory-tenant':'foreign'};
  answer = ()=>new Response(null,{status:401,headers:{'www-authenticate':'Bearer resource_metadata="https://app.tervory.com/.well-known/oauth-protected-resource/mcp"','mcp-session-id':'reply-session','set-cookie':'must-not-return'}});
  let response = await mcpPublicRequest(request('/mcp',{method:'POST',headers:sent,body:'{}'}),'mcp');
  assert.equal(response.status,401);
  assert.equal(response.headers.get('mcp-session-id'),'reply-session');
  assert(response.headers.get('www-authenticate').includes('resource_metadata='));
  assert.equal(response.headers.get('set-cookie'),null);
  assert.deepEqual([...calls[0].init.headers.keys()].sort(),['accept','authorization','content-type','mcp-protocol-version','mcp-session-id','origin'].sort());
  assert.equal(calls[0].url,'http://tank:8000/mcp');
  assert.equal(calls[0].init.redirect,'manual');
  answer = ()=>new Response('{}',{headers:{'content-type':'application/json'}});
  for (const operation of ['token','revoke','register']) {
    calls=[];
    const body=operation==='register'?'{}':'grant_type=authorization_code&code=synthetic';
    response=await mcpPublicRequest(request('/oauth/'+operation,{method:'POST',headers:sent,body}),operation);
    assert.equal(response.status,200);
    await response.text();
    assert.deepEqual([...calls[0].init.headers.keys()],['content-type']);
    assert.equal(new TextDecoder().decode(calls[0].init.body),body);
  }
  for (const operation of ['resource','resourceMcp','authorization']) {
    calls=[];
    response=await mcpPublicRequest(request('/.well-known/test',{headers:sent}),operation);
    assert.equal(response.status,200);await response.text();
    assert.equal([...calls[0].init.headers.keys()].length,0);
  }
  calls=[];
  assert.equal((await mcpPublicRequest(new Request('https://za.tervory.com/mcp'),'mcp')).status,404);
  region='za';assert.equal((await mcpPublicRequest(request('/mcp'),'mcp')).status,404);region='us-east';
  assert.equal(calls.length,0);
  response=await mcpPublicRequest(request('/mcp',{method:'POST',headers:sent,body:'x'.repeat(65537)}),'mcp');
  assert.equal(response.status,413);assert.equal(calls.length,0);
  answer=()=>new Response(null,{status:204});
  response=await mcpPublicRequest(request('/mcp',{method:'DELETE',headers:sent}),'mcp');
  assert.equal(response.status,204);assert.equal(await response.text(),'');
  answer=()=>new Response('{}',{headers:{'content-type':'application/json'}});calls=[];
  const input={response_type:'code',client_id:'offline',redirect_uri:'https://client.example/cb',state:'state',code_challenge:'v'.repeat(43),code_challenge_method:'S256',resource:'https://app.tervory.com/mcp'};
  await mcpApproval({tenantId:'tenant',userId:'signed-in-user',tenantAdmin:false},input,'approve');
  assert.equal(calls[0].init.headers['x-tervory-user'],'signed-in-user');
  assert.equal(calls[0].init.headers['x-tervory-tenant'],'tenant');
  assert.equal(calls[0].init.headers['x-tervory-home-region'],'us-east');
  assert(!('authorization' in calls[0].init.headers));
  console.log('MCP proxy: allowlisted headers, body-only OAuth, discovery, ZA refusal, body limit, empty DELETE and signed-in approval passed');
})().catch(error=>{console.error(error);process.exitCode=1;});
