import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, writeFile, readFile, rm, symlink } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { MCPClients, loadMCP } from '../src/mcp.mjs';
import { CodeFolder } from '../src/code-tools.mjs';
import { gitSlash, gitProcess } from '../src/code-git.mjs';
import { attachmentsFrom } from '../src/code-attachments.mjs';
import { codeSession } from '../src/code-mode.mjs';
import { safe, receiptLines } from '../src/client.mjs';

async function folder(t) {
  const root = await mkdtemp(join(tmpdir(),'opli-reach-')); t.after(() => rm(root,{recursive:true,force:true}));
  execFileSync('git',['init','-q',root]); execFileSync('git',['-C',root,'config','user.email','placeholder@example.invalid']); execFileSync('git',['-C',root,'config','user.name','Placeholder']);
  return {root,local:await CodeFolder.create(root)};
}
const ioFor = answers => ({ interactive:true, shown:'', prompts:[], write(text) { this.shown += text; }, async prompt(label) { this.prompts.push(label); return answers.shift() ?? null; } });

test('reach MCP stdio uses keyring references and asks before connect and every tool call', async t => {
  const {root}=await folder(t); const path=join(root,'mcp.json');
  const config={servers:{fixture:{transport:'stdio',command:process.execPath,args:[fileURLToPath(new URL('./fixtures/mcp-server.mjs',import.meta.url))],env:{PLACEHOLDER_MCP_SECRET:{keyring:'credential'}}}}};
  await writeFile(path,JSON.stringify(config)); const secret='placeholder-"private\\mcp-value'; let reads=0; let blocked=[];
  const io=ioFor(['y','n','y']); const client=new MCPClients({json:async()=>({blocked})},io,{load:()=>loadMCP(path),keyring:async(name,key)=>{assert.equal(name,'fixture');assert.equal(key,'credential');reads++;return {getPassword:()=>secret};}});t.after(()=>client.close());
  assert.deepEqual(await client.tools('plan',false),[]); assert.deepEqual(await client.tools('ask',true),[]); assert.equal(reads,0);
  assert.equal((await client.tools('auto-edit',false))[0].name,'echo');
  assert.equal((await client.call({server:'fixture',tool:'echo',arguments:{text:'hello'}},'auto-edit',false)).status,'cancelled');
  const result=await client.call({server:'fixture',tool:'echo',arguments:{text:'hello'}},'ask',false);
  assert.equal(result.content[0].text,'hello\n[redacted]'); assert(!io.shown.includes(secret)); assert(!(await readFile(path,'utf8')).includes(secret));
  blocked=['*']; await assert.rejects(client.call({server:'fixture',tool:'echo'},'ask',false)); assert.equal(reads,1);
  assert.deepEqual(io.prompts,['Connect MCP fixture [y/N] ','Run MCP tool [y/N] ','Run MCP tool [y/N] ']);
});

test('reach MCP HTTP uses the configured origin only and never leaks credentials or follows redirects', async t => {
  const secret='placeholder-http-secret';const io=ioFor(['y','y']);let calls=0;let redirect=false;
  const client=new MCPClients({json:async()=>({blocked:[]})},io,{load:async()=>({remote:{transport:'http',url:'https://placeholder.invalid/mcp',headers:{Authorization:{keyring:'bearer'}}}}),keyring:async()=>({getPassword:()=>secret}),transport:async(url,init)=>{
    assert.equal(String(url),'https://placeholder.invalid/mcp');assert.equal(init.redirect,'error');assert.equal(new Headers(init.headers).get('authorization'),secret);calls++;
    if(redirect)return new Response(null,{status:307,headers:{Location:'https://forbidden.invalid'}});
    if(init.method==='GET')return new Response(null,{status:405});
    const body=JSON.parse(init.body);if(body.id===undefined)return new Response(null,{status:202});
    const result=body.method==='initialize'?{protocolVersion:'2025-03-26',capabilities:{tools:{}},serverInfo:{name:'placeholder',version:'1'}}:body.method==='tools/list'?{tools:[{name:'echo',inputSchema:{type:'object'}}]}:{content:[{type:'text',text:secret}]};
    return Response.json({jsonrpc:'2.0',id:body.id,result});
  }});t.after(()=>client.close());
  await client.tools('ask',false);const result=await client.call({server:'remote',tool:'echo',arguments:{}},'ask',false);assert.equal(result.content[0].text,'[redacted]');
  redirect=true;io.prompt=async()=>'y';const before=calls;await assert.rejects(client.call({server:'remote',tool:'echo'},'ask',false));assert.equal(calls,before+1);assert(!io.shown.includes(secret));
});

test('reach MCP config refuses plaintext credentials secret arguments and symlinks', async t => {
  const {root}=await folder(t);const path=join(root,'mcp.json');
  for(const config of [{transport:'http',url:'https://user:password@placeholder.invalid'}, {transport:'http',url:'https://placeholder.invalid',headers:{Authorization:'placeholder'}}, {transport:'stdio',command:'node',args:['--token','placeholder']}]) {
    await writeFile(path,JSON.stringify({servers:{fixture:config}}));await assert.rejects(loadMCP(path),/MCP refused/);
  }
  await writeFile(path,JSON.stringify({servers:{}}));await symlink(path,join(root,'link'));await assert.rejects(loadMCP(join(root,'link')));
});

test('reach Git drafts a staged commit and needs explicit approval without push', async t => {
  const {root,local}=await folder(t);await writeFile(join(root,'file.txt'),'hello\n');execFileSync('git',['-C',root,'add','file.txt']);
  let count=0;const process=async(...args)=>{count++;return gitProcess(...args);};
  const no=ioFor(['n']);await gitSlash('/commit','',local,no,'ask',{process});assert.equal(count,0);assert(no.shown.includes('Commit message: Update file.txt'));
  await gitSlash('/commit','',local,ioFor(['y']),'auto-edit',{process});assert.equal(count,1);assert.equal(execFileSync('git',['-C',root,'log','-1','--format=%s']).toString().trim(),'Update file.txt');
  await assert.rejects(gitSlash('/commit','',local,ioFor(['y']),'plan',{process}));
});

test('reach Git branch and PR require approvals and never force push', async t => {
  const {root,local}=await folder(t);await writeFile(join(root,'file.txt'),'hello\n');execFileSync('git',['-C',root,'add','.']);execFileSync('git',['-C',root,'commit','-qm','Initial']);
  await gitSlash('/branch','feature/placeholder',local,ioFor(['y']),'ask');execFileSync('git',['-C',root,'remote','add','origin','https://github.com/placeholder/placeholder.git']);
  const calls=[];const process=async(command,args)=>{calls.push([command,...args]);return '';};
  await gitSlash('/pr','',local,ioFor(['n']),'ask',{process});assert.deepEqual(calls,[['gh','auth','status']]);calls.length=0;
  await gitSlash('/pr','',local,ioFor(['y','n']),'auto-edit',{process});assert.equal(calls.filter(a=>a.includes('push')).length,1);assert(!calls.some(a=>a.includes('create')));calls.length=0;
  await gitSlash('/pr','',local,ioFor(['y','y']),'ask',{process});assert.deepEqual(calls.at(-1),['gh','pr','create','--fill']);assert(!calls.some(a=>a.includes('--force')||a.includes('--force-with-lease')||a.includes('-f')));assert(calls.some(a=>a.includes('--no-force')));
  await assert.rejects(gitSlash('/branch','--force',local,ioFor(['y']),'ask'));
});

test('reach attachments redact text store images only and refuse secrets ignored files binary and escapes', async t => {
  const {root,local}=await folder(t);const secret='ghp_'+'placeholder'.repeat(3);await writeFile(join(root,'words.txt'),'hello\n'+secret);await writeFile(join(root,'image.png'),Buffer.from([137,80,78,71,13,10,26,10,0,0]));await writeFile(join(root,'bad.bin'),Buffer.from([0,1,2]));await writeFile(join(root,'.env'),'placeholder');await writeFile(join(root,'.gitignore'),'ignored.txt\n');await writeFile(join(root,'ignored.txt'),'private');
  let uploads=0;const tank={json:async(path,body)=>{uploads++;assert.equal(path,'/v1/command/code-attachments');assert.equal(body.thread_id,'placeholder-thread');return {attachment_id:'placeholder-image',model_readable:false};}};
  const files=await attachmentsFrom('Inspect @words.txt @"image.png"',local,tank,'placeholder-thread',ioFor([]));assert.equal(files[0].text,'hello\n[redacted]');assert.deepEqual(files[1],{attachment_id:'placeholder-image'});assert.equal(uploads,1);
  for(const path of ['.env','ignored.txt','bad.bin','../outside'])await assert.rejects(attachmentsFrom('@'+path,local,tank,'placeholder-thread',ioFor([])));
  await writeFile(join(root,'big.txt'),'x'.repeat(200001));await assert.rejects(attachmentsFrom('@big.txt',local,tank,'placeholder-thread',ioFor([])));assert.equal(uploads,1);
  await writeFile(join(root,'big.png'),Buffer.alloc(5*1024*1024+1));await assert.rejects(attachmentsFrom('@big.png',local,tank,'placeholder-thread',ioFor([])));assert.equal(uploads,1);
});

test('reach web search and fetch use Tank Confirm and receipts only', async t => {
  const {root}=await folder(t);let round=0;let calls=[];const io=ioFor(['search then fetch','y','y','/exit']);
  const card=name=>({card_id:name,tool:'mcp.placeholder.'+name,status:'pending',arguments:{query:'placeholder'},summary:name});
  const tank={json:async(path,body)=>{calls.push({path,body});if(path.endsWith('/threads'))return {thread_id:'placeholder-thread'};
    if(path.endsWith('/code-turn')){const name=['web_search','web_fetch'][round++];return {answer:name?'':'done',requests:name?[{name:'tervory',arguments:{tool:card(name).tool,arguments:{query:'placeholder'}}}]:[],cards:name?[card(name)]:[],turn:{model:'Auto',cost_usd:0}};}
    if(path.includes('/cards/'))return {...card(path.split('/').at(-1)),status:'confirmed'};
    return {thread:{spent_usd:0},cards:['web_search','web_fetch'].map(name=>({...card(name),status:'confirmed',result:{content:'result',ledger_id:'placeholder-ledger'}})),steps:['web_search','web_fetch'].map(name=>({step_id:name,status:'done'})),receipts:[{step_id:'web_fetch',ledger_id:'placeholder-ledger',cost_usd:0}]};}};
  await codeSession(tank,root,'auto',io,receiptLines,safe);assert.equal(calls.filter(x=>x.path.includes('/cards/')&&x.body.action==='confirm').length,2);assert(calls.every(x=>x.path.startsWith('/v1/command/')));assert.equal(round,3);
});

test('reach local MCP catalogue and results participate in the code loop', async t => {
  const {root}=await folder(t);const io=ioFor(['use tool','/exit']);let closed=false;let calls=0;let turn=0;
  const mcp={tools:async(mode,headless)=>{assert.equal(mode,'ask');assert.equal(headless,false);return [{server:'fixture',name:'echo',description:'echo',inputSchema:{type:'object'}}];},call:async args=>{assert.equal(args.tool,'echo');calls++;return {content:[{type:'text',text:'result'}]};},close:async()=>{closed=true;}};
  const tank={json:async(path,body)=>{if(path.endsWith('/threads'))return {thread_id:'placeholder-thread'};assert.equal(body.local_mcp[0].name,'echo');if(turn++) {assert(body.tool_results[0].output.includes('result'));return {answer:'done',requests:[]};}return {answer:'',requests:[{name:'local_mcp',arguments:{server:'fixture',tool:'echo',arguments:{}}}]};}};
  await codeSession(tank,root,'auto',io,receiptLines,safe,{createMCP:()=>mcp});assert.equal(calls,1);assert(closed);
});
