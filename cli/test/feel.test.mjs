import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { performance } from 'node:perf_hooks';
import { TerminalUI, previewText, wrapTerminal } from '../src/terminal.mjs';
import { Tank, safe, receiptLines } from '../src/client.mjs';
import { codeSession } from '../src/code-mode.mjs';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('feel terminal colours diffs wraps narrow output and expands tool steps safely', () => {
  let output='';const ui=new TerminalUI({write:text=>{output+=text;},columns:()=>24,tty:true});
  ui.write('--- a/file\n+++ b/file\n@@ -1 +1 @@\n-old\n+new\n');
  assert(output.includes('\x1b[31m-old'));assert(output.includes('\x1b[32m+new'));
  ui.status({model:'placeholder-model',mode:'auto-edit',cost_usd:0.002,savings_usd:-0.001});
  ui.tool({phase:'start',name:'read_file',arguments:{path:'file'}});ui.tool({phase:'end',result:{text:'details'}});assert(!output.includes('details'));
  ui.toggle('1');assert(safe(output).replaceAll('\n','').includes('details'));ui.toggle('1');assert(safe(output).replaceAll('\n','').includes('collapsed'));
  ui.write('\x1b]52;c;malicious\x07safe');assert(!output.includes('malicious'));
  for(const line of safe(output).split('\n'))assert(Array.from(line).length<=24,line);
  assert.equal(wrapTerminal('😀😀😀',4),'😀😀\n😀');
});

test('feel plain mode and NO_COLOR avoid control codes and show accessible tool details', () => {
  for(const settings of [{plain:true},{env:{NO_COLOR:''}},{tty:false}]) {
    let output='';const ui=new TerminalUI({write:text=>{output+=text;},tty:true,...settings});
    ui.preview('partial answer ');ui.write('-old\n+new\n');ui.status({model:'Auto',mode:'ask',cost_usd:null,savings_usd:null});
    ui.tool({phase:'start',name:'read_file',arguments:{path:'file'}});ui.tool({phase:'end',result:{text:'details'}});
    assert(!output.includes('\x1b'));assert(output.includes('details'));assert(output.includes('cost pending'));assert(!output.includes('partial answer'));
  }
});

test('feel previews never expose split credentials assignments private keys or terminal controls', () => {
  const secret='ghp_'+'placeholder'.repeat(3);
  const inputs=[`Answer ${secret} done\n`,`password = ${'placeholder'.repeat(3)}\n`,'-----BEGIN ' + 'PRIVATE KEY-----\nplaceholder-private-body\n-----END ' + 'PRIVATE KEY-----\n'];
  for(const input of inputs){let raw='';let rendered='';for(const c of input){raw+=c;rendered+=previewText(raw);}assert(!rendered.includes(secret));assert(!rendered.includes('placeholder-private-body'));assert(!rendered.includes('placeholder'.repeat(3)));}
  assert(!previewText('safe \x1b]52;c;danger\x07 done ').includes('danger'));
});

test('feel warm local Tank shows a first token under 1.5 seconds before completion', async t => {
  let requested=0;const server=createServer((req,res)=>{
    req.resume();req.on('end',()=>{
      assert(req.url.endsWith('/code-stream'));requested++;
      res.writeHead(200,{'Content-Type':'text/event-stream'});
      const send=(kind,data)=>res.write(`event: ${kind}\ndata: ${JSON.stringify(data)}\n\n`);
      const warm=requested>1;
      const first=setTimeout(()=>send('code_preview',{text:'Hello from Tank '}),warm?40:1);
      const last=setTimeout(()=>{send('code_result',{answer:'Hello from Tank.',requests:[],turn:{model:'placeholder-model',cost_usd:0.001}});res.end();},warm?1650:10);
      res.on('close',()=>{clearTimeout(first);clearTimeout(last);});
    });
  });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));t.after(()=>new Promise(resolve=>server.close(resolve)));
  const token='tv1.us-east.'+'1'.repeat(32)+'.'+'placeholder'.padEnd(43,'x');const local=`http://127.0.0.1:${server.address().port}`;
  const tank=new Tank(token,(url,init)=>fetch(String(url).replace('https://app.tervory.com',local),init));
  await tank.codeTurn('placeholder-thread',{text:'warm'},()=>{});
  let visibleAt;let live='';const ui=new TerminalUI({write(){},live:text=>{live+=text;if(text.includes('Hello')&&visibleAt===undefined)visibleAt=performance.now();},tty:true});
  const start=performance.now();const result=await tank.codeTurn('placeholder-thread',{text:'measured'},text=>ui.preview(text));
  assert(visibleAt!==undefined);assert(visibleAt-start<1500,`first token ${visibleAt-start} ms`);assert(performance.now()-start>=1600);assert.equal(result.answer,'Hello from Tank.');assert(live.includes('Hello'));
});

test('feel interrupted streams fail closed and never replay a turn', async () => {
  let calls=0;const token='tv1.us-east.'+'1'.repeat(32)+'.'+'placeholder'.padEnd(43,'x');
  const tank=new Tank(token,async()=>{calls++;return new Response('event: code_preview\ndata: {"text":"partial "}\n\n',{headers:{'Content-Type':'text/event-stream'}});});
  await assert.rejects(tank.codeTurn('placeholder',{text:'task'},()=>{}),/interrupted/);assert.equal(calls,1);
});

test('feel status reports mode model cost and measured savings against Auto', async t => {
  const root=await mkdtemp(join(tmpdir(),'opli-feel-'));t.after(()=>rm(root,{recursive:true,force:true}));execFileSync('git',['init','-q',root]);await writeFile(join(root,'file.txt'),'hello');
  const prompts=['/model placeholder-model','task','/mode plan','/exit'];const statuses=[];
  const tank={json:async(path)=>path.endsWith('/threads')?{thread_id:'placeholder-thread'}:path.endsWith('/code-models')?[{name:'placeholder-model'}]:{answer:'done',requests:[],turn:{model:'placeholder-model',cost_usd:0.003},receipt:{rows:[{cost_usd:0.003,auto_cost_status:'priced',auto_cost_usd:0.005}]}}};
  await codeSession(tank,root,'auto',{interactive:true,write(){},prompt:async()=>prompts.shift(),status:value=>statuses.push(value)},receiptLines,safe);
  assert(statuses.some(s=>s.model==='placeholder-model'&&s.cost_usd===0.003&&s.savings_usd===0.002));assert.equal(statuses.at(-1).mode,'plan');
});
