/* Actual CLI -> actual Workspace PAT adapter -> disposable loopback Tank. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {pathToFileURL} = require('node:url');
const root = path.resolve(__dirname, '../..');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
assert.equal(new URL(input.origin).hostname, '127.0.0.1');
const ts = require(path.join(process.env.COMMAND_TEST_TOOLS, 'typescript'));
const source = ts.transpileModule(fs.readFileSync(path.join(root, 'workspace/lib/tank.ts'), 'utf8'), {
  compilerOptions: {target:ts.ScriptTarget.ES2022, module:ts.ModuleKind.CommonJS}
}).outputText;
const moduleValue = {exports:{}};
let upstreamCalls = 0;
const upstreamStatuses = [];
vm.runInNewContext(source, {module:moduleValue,exports:moduleValue.exports,
  process:{env:{TANK_URL:input.origin,TANK_API_KEY:'dummy-workspace-key'}},
  URL,Request,Response,Headers,Uint8Array,ReadableStream,AbortController,AbortSignal,setTimeout,clearTimeout,fetch:async(url,init)=>{
    assert.equal(new URL(url).origin,input.origin);
    assert.deepEqual(Object.keys(init.headers).sort(),['Authorization','Content-Type']);
    upstreamCalls++; const response = await fetch(url,init);
    upstreamStatuses.push(response.status); return response;
  }});
const proxy = moduleValue.exports.personalCommandRequest;
const transport = async(url,init)=>{
  const request = new Request(url,init);
  return proxy(request,new URL(url).pathname.slice('/v1/command/'.length).split('/'));
};
(async()=>{
  const cli = await import(pathToFileURL(path.join(root,'cli/src/client.mjs')).href);
  const base = `tv1.us-east.${input.tenant.replaceAll('-','')}.`;
  const founder = base+'f'.repeat(43), client = base+'c'.repeat(43);
  let output = '';
  await cli.run(['build','Offline acceptance cancellation'],{
    store:{get:async()=>founder},transport,
    io:{write:value=>{output+=value;},prompt:async()=> 'N'}
  });
  assert(output.includes('Offline acceptance cancellation'));
  assert(!output.includes(founder));
  const tank = new cli.Tank(client,transport);
  assert.deepEqual(await tank.json('/v1/command/tools'),[]);
  const tid = (await tank.json('/v1/command/threads',{})).thread_id;
  await assert.rejects(()=>tank.json('/v1/command/build',{thread_id:tid,brief_markdown:'Denied'}),/403/);
  const count = upstreamCalls;
  const foreign = new cli.Tank(client.replace('us-east','za'),transport);
  // Token chooses the ZA public hostname; adapter forwards to its configured box.
  // Local Tank must independently refuse the region mismatch.
  await assert.rejects(()=>foreign.json('/v1/command/tools'),/403/);
  assert.equal(upstreamCalls,count+1);
  assert.equal(upstreamStatuses.at(-1),403);
  process.stdout.write('PASS: actual CLI/public PAT adapter/Tank cancellation and client denial\n');
})().catch(error=>{console.error(error);process.exitCode=1;});
