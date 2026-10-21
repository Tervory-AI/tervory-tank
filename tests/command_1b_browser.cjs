// Real CommandWindow component, same-box HTTP fixtures. Never connects to production.
const {createServer}=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..');
const tools=process.env.COMMAND_TEST_TOOLS || '/tmp/command-1b-tools/node_modules';
const {build}=require(path.join(tools,'esbuild'));
const {chromium}=require(path.join(tools,'playwright'));
const base=path.join(root,'workspace');
const output=path.join(root,'tests/fixtures/command-1b');
const thread={thread_id:'thread-one',title:'Base run: Delaware ATF list',updated_at:'2026-10-21T12:00:00Z',spent_usd:0,saved_usd:4.12};
const receipt={rows:['Normalise records','Match to ATF list','Find websites','Read sites'].map((step,i)=>({step_id:step,model:'code',tokens_in:0,tokens_out:0,cost_usd:0,baseline_model:'baseline',baseline_cost_usd:[.61,.88,1.38,1.25][i],saved_usd:[.61,.88,1.38,1.25][i],ledger_id:'entry-'+i})),totals:{cost_usd:0,baseline_cost_usd:4.12,saved_usd:4.12}};
const original={thread,messages:[{message_id:'user-one',role:'user',content:'Run Base on the Delaware ATF list and show me what it would have cost on a top model.'},{message_id:'answer-one',role:'assistant',content:'Running Base on 1,284 Delaware licences. Every step so far is plain code, so the cost is $0. One step is paid: a web search for 212 records with no site found. Confirm it below or cancel this step.',receipt}],steps:['Normalise 1,284 records','Match to ATF list','Find websites','Read sites','Web search, 212 records','Verify and score'].map((label,i)=>({step_id:'step-'+i,label,actor:'Base',status:i<4?'done':'planned',...(i===3?{link:'/base?batch=B-0142'}:{})})),cards:[{card_id:'paid-one',kind:'paid_run',summary:'Paid step: web search for 212 records with no website found.',cost_estimate_usd:1.06,status:'pending'}]};
let state=structuredClone(original),calls=[],failConfirm=false,turns=0;
(async()=>{
const bundle=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {CommandWindow} from './app/chats/window';const founder=new URL(location.href).searchParams.get('role')!=='client';createRoot(document.getElementById('root')).render(<CommandWindow initialThreads={${JSON.stringify([thread,{...thread,thread_id:'two',title:'Tiger: price watch'}])}} models={[{value:'pinned',label:founder?'fixture-model':'Option 1',inputPerM:.1,outputPerM:.4}]} founder={founder} account="Tervory · Boston · USD"/>);`,resolveDir:base,loader:'tsx'},bundle:true,write:false,jsx:'automatic',outfile:'/tmp/command-window.js',loader:{'.svg':'file'},assetNames:'[name]',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'shared-squad-fixture',setup(build){build.onResolve({filter:/^next\/navigation$/},()=>({path:'squad',namespace:'fixture'}));build.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export function usePathname(){return location.pathname}',loader:'jsx',resolveDir:base}));}}]});
const resources=new Map(bundle.outputFiles.map(file=>['/'+path.basename(file.path),file.contents]));
const css=fs.readFileSync(path.join(base,'app/globals.css'),'utf8')+'\n'+new TextDecoder().decode(resources.get('/command-window.css'));
const html=`<!doctype html><html><head><style>@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}body{margin:0;--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}${css}</style></head><body><div class="app-shell product"><aside class="shell-side">Shared shell</aside><header class="shell-mobile">Shared mobile</header><div class="shell-main"><main id="root"></main></div></div><script src="/command-window.js"></script></body></html>`;
const server=createServer(async(req,res)=>{
  const url=new URL(req.url,'http://localhost');
  if(resources.has(url.pathname)){res.setHeader('Content-Type',url.pathname.endsWith('.svg')?'image/svg+xml':'text/javascript');res.end(resources.get(url.pathname));return;}
  if(url.pathname.startsWith('/brand/')||url.pathname.startsWith('/fonts/')){const file=path.join(base,url.pathname.startsWith('/brand/')?'public':'app',url.pathname);res.end(fs.readFileSync(file));return;}
  if(!url.pathname.startsWith('/chats/api/')){res.setHeader('Content-Type','text/html');res.end(html);return;}
  let raw='';for await(const chunk of req)raw+=chunk;const body=raw?JSON.parse(raw):{};const target=url.pathname.slice('/chats/api/'.length);calls.push({target,method:req.method,body});
  const json=(data,status=200)=>{res.statusCode=status;res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
  if(target==='threads'&&req.method==='GET')return json([state.thread]);
  if(target==='threads'&&req.method==='POST'){state={thread:{...thread,thread_id:'new-thread',title:'New chat',spent_usd:0,saved_usd:0},messages:[],steps:[],cards:[]};return json({thread_id:'new-thread'});}
  if(target.startsWith('cards/')){if(failConfirm)return json({error:'Confirmation could not be saved. Reload before trying again.'},502);state.cards=state.cards.map(card=>({...card,status:body.action==='confirm'?'confirmed':'cancelled'}));state.steps[4].status=body.action==='confirm'?'running':'planned';return json({ok:true});}
  if(target.endsWith('/turn')){turns++;assert.equal(body.model,'pinned');assert.equal(body.attachments[0].name,'notes.txt');state.messages.push({message_id:'sent-user',role:'user',content:body.text,attachments:body.attachments});res.setHeader('Content-Type','text/event-stream');res.write('event: token\ndata: {"text":"First words ","seq":1}\n\n');setTimeout(()=>{res.write('event: token\ndata: {"text":"First words ","seq":1}\n\n');res.write('event: token\ndata: {"text":"arrived live.","seq":2}\n\n');res.write('event: receipt\ndata: '+JSON.stringify(receipt)+'\n\n');state.messages.push({message_id:'sent-answer',role:'assistant',content:'First words arrived live.',receipt});res.end('event: done\ndata: {"message_id":"sent-answer","seq":3}\n\n');},400);return;}
  if(req.method==='PATCH'){state.thread.title=body.title;return json({ok:true});}
  return json(state);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const port=server.address().port;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1120}});const errors=[];page.on('pageerror',error=>errors.push(error.message));
try {
 await page.goto(`http://127.0.0.1:${port}/chats?thread=thread-one`);await page.getByRole('heading',{name:thread.title}).waitFor();await page.evaluate(()=>document.fonts.ready);
 assert.equal(calls.filter(call=>call.target.startsWith('cards/')).length,0);
 assert.equal(await page.locator('.shell-side').isVisible(),false);
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.getByRole('button',{name:'Squad',exact:true}).click();await page.getByRole('link',{name:/Skala/}).waitFor();await page.keyboard.press('Escape');
 await page.screenshot({path:path.join(output,'window-1440.png')});
 await page.setViewportSize({width:375,height:812});await page.screenshot({path:path.join(output,'window-375.png')});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.getByRole('button',{name:'Work 4/6'}).click();assert(await page.getByRole('button',{name:'Close work'}).evaluate(element=>element===document.activeElement));await page.screenshot({path:path.join(output,'work-375.png')});
 await page.keyboard.press('Escape');await page.waitForFunction(()=>document.activeElement?.classList.contains('cw-work-tab'));assert(await page.getByRole('button',{name:'Work 4/6'}).evaluate(element=>element===document.activeElement));
 await page.getByText('Receipt ·',{exact:false}).click();assert(await page.locator('.cw-receipt-mobile .cw-receipt-row').first().isVisible());
 await page.getByRole('button',{name:'Menu',exact:true}).click();await page.getByRole('searchbox').fill('Tiger');assert.equal(await page.locator('.cw-threads button').count(),1);await page.getByRole('searchbox').fill('');await page.getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('button',{name:'Rename',exact:true}).click();await page.getByRole('textbox',{name:'Chat name'}).fill('Saved conversation');await page.getByRole('button',{name:'Save',exact:true}).click();await page.getByRole('heading',{name:'Saved conversation'}).waitFor();
 failConfirm=true;await page.getByRole('button',{name:'Confirm',exact:true}).click();await page.getByRole('alert').waitFor();assert.equal(state.cards[0].status,'pending');failConfirm=false;
 await page.getByRole('button',{name:'Cancel',exact:true}).click();await page.waitForFunction(()=>!document.querySelector('.cw-confirm'));assert.equal(state.cards[0].status,'cancelled');
 await page.getByRole('combobox').selectOption('pinned');await page.getByLabel('Attach files').setInputFiles({name:'notes.txt',mimeType:'text/plain',buffer:Buffer.from('Public fixture')});
 await page.getByRole('textbox',{name:'Message Tervory'}).fill('Read the attached note');await page.getByRole('button',{name:'Send',exact:true}).click();await page.getByText('First words ',{exact:true}).waitFor();await page.getByText('First words arrived live.',{exact:true}).waitFor();assert.equal(turns,1);
 await page.reload();await page.getByText('First words arrived live.',{exact:true}).waitFor();assert.equal(turns,1);
 await page.getByRole('button',{name:'Menu',exact:true}).click();await page.getByRole('button',{name:'+ New chat',exact:true}).click();await page.getByRole('heading',{name:'New chat',exact:true}).waitFor();assert.equal(state.messages.length,0);
 state=structuredClone(original);await page.goto(`http://127.0.0.1:${port}/chats?thread=thread-one&role=client`);await page.getByRole('heading',{name:thread.title}).waitFor();assert.equal(await page.getByRole('combobox').textContent().then(text=>text.includes('fixture-model')),false);assert.equal(await page.locator('.cw-receipt-row').first().textContent().then(text=>text.includes('baseline')),false);
 await page.screenshot({path:path.join(output,'client-375.png')});
 assert.deepEqual(errors,[]);console.log('Browser passed: desktop/mobile, work focus, menu/search, rename, explicit cancel, failed confirmation, pin/files/stream deduplication, persisted reload, new chat, client labels; no overflow or runtime errors.');
} finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
