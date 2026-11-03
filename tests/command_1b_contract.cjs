const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  if (name.startsWith('@/')) name = path.join(root, 'workspace', name.slice(2));
  return originalResolve.call(this, name, parent, ...rest);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true } }).outputText, filename);
const mock = (filename, exports) => { require.cache[path.join(root,filename)] = { id:filename, filename:path.join(root,filename), loaded:true,exports }; };
const contract = require('../workspace/app/chats/contract.ts');
const presentation = require('../workspace/app/chats/presentation.ts');
const {modelValue} = require('../workspace/app/chats/models.ts');
const identity = {tenantId:'tenant-owned',userId:'user-owned',orgName:'Example',orgId:'org-owned'};
let currentIdentity = identity;
let founder = false;
let upstreamCalls = [];
let upstream = () => Response.json([]);
mock('workspace/lib/trigger.ts', {triggerIdentity:async tenant=>tenant ? {...tenant,tenantAdmin:false}:null});
mock('workspace/lib/tenant.ts', {activeTenant:async()=>currentIdentity});
mock('workspace/lib/admin.ts', {isFounder:()=>founder});
process.env.TANK_API_KEY = 'dummy-command-key';
process.env.TANK_URL = 'http://same-box.invalid';
global.fetch = async (url, init) => { upstreamCalls.push({url:String(url),init}); if(String(url).endsWith('/v1/models')) return Response.json([{name:'test-model',provider_model:'provider/test-model',input_usd_per_m:.1,output_usd_per_m:.5}]); return upstream(url,init); };
const route = require('../workspace/app/chats/api/[...path]/route.ts');
const request = (target, method='GET', body, origin='https://workspace.invalid') => route[method](new Request(`https://workspace.invalid/chats/api/${target}`, {method,headers:{origin,'content-type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)}),{params:Promise.resolve({path:target.split('?')[0].split('/')})});
const encoder = new TextEncoder();
const stream = (content, chunk=1) => new ReadableStream({start(controller){const bytes=encoder.encode(content);for(let i=0;i<bytes.length;i+=chunk)controller.enqueue(bytes.slice(i,i+chunk));controller.close();}});
const receipt = {rows:[{step_id:'step',ledger_id:'row',model:'test-model',baseline_model:'expensive-model',tokens_in:4,tokens_out:8,cost_usd:.01,baseline_cost_usd:.03,saved_usd:.02}],totals:{cost_usd:.01,baseline_cost_usd:.03,saved_usd:.02}};
const snapshot = {thread:{thread_id:'one',title:'Tank test-model',updated_at:'2026-10-21',spent_usd:.01,saved_usd:.02},messages:[{message_id:'answer',role:'assistant',content:'Tank used test-model.',receipt}],steps:[],cards:[{card_id:'founder-card',kind:'build',summary:'Build'},{card_id:'client-card',kind:'paid_run',summary:'Search'}]};
(async()=>{
  let events=[];
  await contract.readEvents(stream(':keepalive\r\nid: 7\r\nevent: token\r\ndata: {"text":"héllo 🌍",\r\ndata: "seq":7}\r\n\r\nevent: done\ndata: {"message_id":"ok"}'), event=>events.push(event));
  assert.equal(events[0].data.text,'héllo 🌍');assert.equal(events[0].seq,7);assert.equal(events[1].type,'done');
  await assert.rejects(()=>contract.readEvents(stream('event: token\ndata: invalid\n\n'),()=>{}));
  assert.equal(contract.dollars(null),'Unavailable');assert.equal(contract.dollars(0),'$0.00');assert.equal(contract.dollars(.00001),'$0.000010');
  for(const link of ['javascript:alert(1)','//evil.invalid','/\\evil.invalid','https://user:pass@evil.invalid','data:text/html,test']) assert.equal(contract.safeLink(link),undefined);
  assert.equal(contract.safeLink('/base?batch=1'),'/base?batch=1');
  assert.equal(contract.upsert([{id:'a',status:'planned'}],{id:'a',status:'done'},'id').length,1);
  const client = presentation.presentSnapshot(snapshot,false,['test-model']);
  assert.equal(client.cards.length,1);assert.equal(client.messages[0].receipt.rows[0].model,undefined);assert.equal(client.messages[0].receipt.totals.cost_usd,.01);
  assert.equal(client.messages[0].content,snapshot.messages[0].content);assert.equal(client.thread.title,snapshot.thread.title);assert.deepEqual(presentation.presentSnapshot(snapshot,true).messages[0].receipt,receipt);
  let response = await request('threads','POST',{title:'New',tenant_id:'forged',user_id:'forged'},'https://attacker.invalid');assert.equal(response.status,403);assert.equal(upstreamCalls.length,0);
  currentIdentity=null;response=await request('threads');assert.equal(response.status,401);currentIdentity=identity;
  response=await request('builds/next');assert.equal(response.status,404);
  response=await request('threads/../../admin');assert.equal(response.status,404);
  upstream=()=>Response.json({thread_id:'one'});
  response=await request('threads','POST',{title:'New',tenant_id:'forged',user_id:'forged'});assert.equal(response.status,200);
  const sent=upstreamCalls.at(-1);assert.equal(new URL(sent.url).searchParams.get('tenant_id'),null);assert.equal(new URL(sent.url).searchParams.get('user_id'),null);assert.equal(sent.init.headers.get('x-tervory-tenant'),'tenant-owned');assert.equal(JSON.parse(sent.init.body).user_id,undefined);assert.equal(JSON.parse(sent.init.body).tenant_id,undefined);assert.equal(sent.init.headers.get('x-tank-key'),'dummy-command-key');assert.equal(sent.init.headers.get('x-tervory-user'),'user-owned');
  response=await request('threads/one/turn','POST',{text:'hello',model:'not-a-model'});assert.equal(response.status,403);
  response=await request('threads/one/turn','POST',{text:'hello',attachments:[{name:'x',content_type:'text/plain',data_base64:'invalid!'}]});assert.equal(response.status,400);
  upstream=()=>new Response(stream('event: token\ndata: {"text":"test-"}\n\nevent: token\ndata: {"text":"model answered. "}\n\nevent: receipt\ndata: '+JSON.stringify(receipt)+'\n\nevent: done\ndata: {"message_id":"answer","seq":4}\n\n'),{headers:{'content-type':'text/event-stream'}});
  response=await request('threads/one/turn','POST',{text:'hello',model:'auto',attachments:[{name:'note.txt',content_type:'text/plain',text:'hello'}]});assert.equal(response.status,200);
  const wire=await response.text();const tokens=[];await contract.readEvents(stream(wire),event=>{if(event.type==='token')tokens.push(event.data.text)});assert.equal(tokens.join(''),'test-model answered. ');assert(!wire.includes('selected option'));assert(wire.includes('event: done'));assert.equal(JSON.parse(upstreamCalls.at(-1).init.body).model,'auto');
  upstream=()=>Response.json({...snapshot,messages:snapshot.messages.map(message=>({...message,receipt:undefined})),receipts:receipt.rows.map(row=>({...row,step_id:'answer'}))});response=await request('threads/one');const persisted=await response.json();assert.equal(persisted.cards.length,1);assert.equal(persisted.messages[0].receipt.rows[0].ledger_id,'row');assert.equal(persisted.receipts,undefined);
  founder=true;response=await request('threads/one');assert.equal((await response.json()).messages[0].receipt.rows[0].model,'test-model');founder=false;
  upstream=()=>Response.json({...snapshot,messages:[{message_id:'file-message',role:'user',content:'File',attachments:[{name:'public.txt',text:'Public fixture'}]}]});response=await request('threads/one/files/file-message/0');assert.equal(await response.text(),'Public fixture');assert(response.headers.get('content-disposition').includes('attachment'));response=await request('threads/one/files/other-message/0');assert.equal(response.status,404);
  // Lane A 6cedeb2: pending markers survive persistence, client projection and SSE.
  const unknown = {cost_usd:null,baseline_cost_usd:null,saved_usd:null};
  const pending = {rows:[],totals:unknown,status:'pending',step_id:'action'};
  assert.deepEqual(presentation.presentReceipt(pending,false),pending);
  const empty = {...snapshot,messages:[],receipts:[],cards:[{card_id:'action',kind:'other',status:'unknown'}],steps:[{step_id:'build',actor:'worker',status:'running',receipt_status:'pending'}]};
  const restored = contract.normalizeSnapshot(empty);
  assert.equal(restored.job_receipts.length,2);assert(restored.job_receipts.every(r=>r.status==='pending'&&r.totals.cost_usd===null));
  assert.equal(contract.receiptFor([]).totals.cost_usd,null);assert.equal(restored.thread.spent_usd,null);
  const answerPending=contract.normalizeSnapshot({...empty,cards:[],messages:[{message_id:'build',role:'assistant',content:'Working'}]});
  assert.equal(answerPending.messages[0].receipt.status,'pending');assert.equal(answerPending.job_receipts.length,0);
  const applied=contract.applyReceipt({...restored,messages:[{message_id:'answer',role:'assistant',content:'Text'}]},pending,'answer');
  assert.equal(applied.messages[0].receipt,undefined);assert.equal(applied.job_receipts.find(r=>r.step_id==='action').status,'pending');assert.equal(applied.thread.spent_usd,null);
  const isolated=contract.applyReceipt({...snapshot,messages:[{message_id:'answer',role:'assistant',content:'Text'}],cards:[],steps:[]},pending,'answer');assert.equal(isolated.messages[0].receipt,undefined);assert.equal(isolated.job_receipts[0].step_id,'action');
  const first=contract.applyReceipt({...snapshot,messages:[{message_id:'answer',role:'assistant',content:'Text'}],cards:[],steps:[{step_id:'step',actor:'Tervory',status:'running'}]},receipt,'answer');
  const second=contract.applyReceipt(first,{...receipt,rows:[{...receipt.rows[0],ledger_id:'row-two'}]},'answer');assert.equal(second.messages[0].receipt.rows.length,2);assert.equal(second.messages[0].receipt.totals.cost_usd,.02);
  // Pinned rows carry Tank's same-token Auto comparison; totals sum only fully priced rows.
  const autoRows = [
    {...receipt.rows[0], step_id:'answer', ledger_id:'auto-one', auto_cost_usd:null},
    {...receipt.rows[0], step_id:'work', ledger_id:'auto-two', auto_cost_usd:.004},
  ];
  const mixed = {...receipt, rows:autoRows, totals:{...receipt.totals, cost_usd:99, auto_cost_usd:99}};
  const grouped = contract.applyReceipt({...snapshot,messages:[{message_id:'answer',role:'assistant',content:'Text'}],cards:[],steps:[]},mixed,'answer');
  assert.equal(grouped.messages[0].receipt.totals.cost_usd,.01);
  assert.equal(grouped.messages[0].receipt.totals.auto_cost_usd,null);
  assert.equal(grouped.job_receipts[0].totals.cost_usd,.01);
  assert.equal(grouped.job_receipts[0].totals.auto_cost_usd,.004);
  const autoReload = contract.normalizeSnapshot({...snapshot,messages:[{message_id:'answer',role:'assistant',content:'Text'}],cards:[],steps:[],receipts:autoRows});
  assert.deepEqual(autoReload.messages[0].receipt,grouped.messages[0].receipt);
  assert.equal(autoReload.job_receipts[0].totals.auto_cost_usd,.004);
  const delta = contract.applyReceipt(grouped,{...receipt,rows:[{...autoRows[0],auto_cost_usd:.003}]},'answer');
  assert.equal(delta.messages[0].receipt.rows.length,1);
  assert.equal(delta.messages[0].receipt.totals.auto_cost_usd,.003);
  assert.equal(contract.receiptFor([autoRows[1],{...autoRows[1],ledger_id:'auto-three',auto_cost_usd:.006}]).totals.auto_cost_usd,.01);
  assert.equal(contract.receiptFor([{...autoRows[0],auto_cost_usd:Infinity}]).totals.auto_cost_usd,null);
  assert.equal(contract.receiptFor([{...autoRows[0],auto_cost_usd:NaN}]).totals.auto_cost_usd,null);
  assert.equal(contract.receiptFor([autoRows[1]],'work',true).totals.auto_cost_usd,null);
  assert.equal(contract.receiptFor(receipt.rows).totals.auto_cost_usd,undefined);
  const baselinePending={...receipt,rows:[{...receipt.rows[0],baseline_status:'baseline pending',saved_usd:null}]};
  assert.equal(presentation.presentReceipt(baselinePending,false).rows[0].baseline_status,'baseline pending');
  for(const status of ['executing','unknown','failed','confirmed','cancelled']) {
    const card={card_id:'action',kind:'other',status,summary:'Watch a page',retry_safe:false,tool:'tiger.watch',arguments:{url:'https://example.com/prices',label:'Prices',credential:'not-public'},result:{summary:'Watch saved',url:'https://example.com/result',private_data:'not-public'},error:'Check the action'};
    const safe=presentation.presentCard(card,false);assert.equal(safe.status,status);assert.equal(safe.targets[0].value,'https://example.com/prices');assert(safe.results.length);assert(!JSON.stringify(safe).includes('not-public'));assert.equal(contract.canConfirm(safe),false);
  }
  assert.equal(contract.canConfirm({status:'unknown',retry_safe:true}),false);assert.equal(contract.canConfirm({status:'failed',retry_safe:true}),true);
  assert.equal(presentation.visibleCard({kind:'paid_run',tool:'skala.evals'},false),false);
  const savings=presentation.presentCard({card_id:'savings',kind:'other',summary:'Savings',result:{tenant_id:'not-public',tasks:[{task_type:'fixture',calls:2,actual_usd:null,recorded_actual_usd:.01,baseline_usd:null,saved_usd:null,receipt_status:'pending',private_data:'not-public'}]}},true);
  assert(savings.results.some(item=>item.label==='Tasks 1 · Cost'&&item.value==='Unavailable'));assert(savings.results.some(item=>item.label==='Tasks 1 · Cost status'&&item.value==='pending'));assert(!JSON.stringify(savings).includes('not-public'));assert(!JSON.stringify(savings).includes('$0.00'));
  const binaryId='00000000-0000-4000-8000-000000000001';
  const rawRequest=(target,bytes,origin='https://workspace.invalid')=>route.POST(new Request('https://workspace.invalid/chats/api/'+target,{method:'POST',headers:{origin,'content-type':'application/octet-stream','x-tervory-squad':'all','x-tervory-user':'forged'},body:bytes}),{params:Promise.resolve({path:target.split('?')[0].split('/')})});
  upstream=()=>Response.json({attachment_id:binaryId,size:4,model_readable:false});
  response=await rawRequest('threads/one/attachments?name=photo.png',new Uint8Array([137,80,78,71]));assert.equal(response.status,200);assert.equal((await response.json()).model_readable,false);
  const upload=upstreamCalls.at(-1);assert.equal(upload.init.headers.get('content-type'),'application/octet-stream');assert.equal(upload.init.headers.get('x-tervory-squad'),null);assert.equal(upload.init.headers.get('x-tervory-user'),identity.userId);assert.equal(new URL(upload.url).searchParams.get('name'),'photo.png');assert.equal(upload.init.body.length,4);
  const count=upstreamCalls.length;assert.equal((await rawRequest('threads/one/attachments?name=bad%2Ffile',new Uint8Array())).status,400);assert.equal((await rawRequest('threads/one/attachments?name=photo.png',new Uint8Array(5*1024*1024+1))).status,413);assert.equal((await rawRequest('threads/one/attachments?name=photo.png',new Uint8Array(),'https://attacker.invalid')).status,403);assert.equal(upstreamCalls.length,count);
  upstream=(url)=>String(url).includes('/attachments/')?new Response(new Uint8Array([137,80,78,71]),{headers:{'content-type':'text/html','content-disposition':"attachment; filename*=UTF-8''photo.png",'set-cookie':'do-not-forward'}}):Response.json({...snapshot,messages:[{message_id:'file-message',role:'user',attachments:[{name:'photo.png',attachment_id:binaryId}]}]});
  for(const target of ['attachments/'+binaryId,'threads/one/files/file-message/0']) { response=await request(target);assert.equal(response.status,200);assert.equal((await response.arrayBuffer()).byteLength,4);assert.equal(response.headers.get('content-type'),'application/octet-stream');assert.equal(response.headers.get('x-content-type-options'),'nosniff');assert.equal(response.headers.get('cache-control'),'private, no-store');assert.equal(response.headers.get('set-cookie'),null);assert(response.headers.get('content-disposition').includes('photo.png')); }
  upstream=()=>Response.json({detail:'Attachment not found'},{status:404});assert.equal((await request('attachments/'+binaryId)).status,404);
  upstream=()=>Response.json({ok:true});response=await request('threads/one/turn','POST',{text:'use file',attachments:[{attachment_id:binaryId,name:'spoofed',tenant_id:'forged',text:'ignore this'}]});assert.equal(response.status,200);assert.deepEqual(JSON.parse(upstreamCalls.at(-1).init.body).attachments,[{attachment_id:binaryId}]);
  response=await request('threads/one/turn','POST',{text:'use file',attachments:[{attachment_id:'../../another-user'}]});assert.equal(response.status,400);
  // Ownership and same-thread enforcement remains with Lane A under server-derived identity.
  upstream=()=>Response.json({detail:'Attachment not found'},{status:404});response=await request('threads/one/turn','POST',{text:'use file',attachments:[{attachment_id:binaryId}]});assert.equal(response.status,404);
  founder=true;
  upstream=()=>Response.json({detail:'Pinned models await a router capability; choose Auto'},{status:409});response=await request('threads/one/turn','POST',{text:'hello',model:modelValue('test-model')});assert.equal(response.status,409);assert.equal((await response.json()).code,'pin_pending');
  upstream=()=>Response.json({detail:'Model is not on the roster'},{status:422});response=await request('threads/one/turn','POST',{text:'hello',model:modelValue('test-model')});assert.equal((await response.json()).code,'pin_unavailable');founder=false;
  upstream=()=>Response.json({card_id:'action',kind:'other',summary:'Action',status:'unknown',retry_safe:false,arguments:{url:'https://example.com'},error:'The action outcome is unknown.'});response=await request('cards/action','POST',{action:'confirm'});const action=await response.json();assert.equal(action.status,'unknown');assert.equal(action.retry_safe,false);assert.equal(action.targets[0].value,'https://example.com/');
  upstream=()=>new Response(stream('event: receipt\ndata: '+JSON.stringify(pending)+'\n\nevent: card\ndata: '+JSON.stringify({card_id:'action',kind:'other',summary:'Action',status:'failed',retry_safe:true,arguments:{batch:'fixture',records:[{}]}})+'\n\n'),{headers:{'content-type':'text/event-stream'}});
  response=await request('threads/one/events');const updates=[];await contract.readEvents(response.body,event=>updates.push(event));assert.deepEqual(updates[0].data,pending);assert.equal(updates[1].data.retry_safe,true);assert.equal(updates[1].data.targets[0].value,'fixture');
  // Even a server caller cannot supply arbitrary squad authority in this lane.
  upstream=()=>Response.json([]);await require('../workspace/lib/tank.ts').commandRequest(identity,'threads',{headers:{'x-tervory-squad':'all'}});assert.equal(upstreamCalls.at(-1).init.headers.get('x-tervory-squad'),null);
  // Only generated labels are scrubbed: people can discuss gold, tanks and evaluations.
  const words='  Gold prices, Tank, eval, shadow and test-model stay exactly as written.  ';
  const wording=presentation.presentSnapshot({...snapshot,thread:{...snapshot.thread,title:words},messages:[{message_id:'u',role:'user',content:words,attachments:[{name:'gold Tank.txt',text:words}]},{message_id:'a',role:'assistant',content:words}],steps:[{step_id:'s',label:'Tank test-model eval',actor:'Skala'}],cards:[{card_id:'c',kind:'other',tool:'tiger.read',summary:'Tank test-model',arguments:{question:words},result:{answer:words,summary:words,message:words}}]},false,['test-model']);
  assert.equal(wording.thread.title,words);assert(wording.messages.every(message=>message.content===words));assert.equal(wording.messages[0].attachments[0].name,'gold Tank.txt');assert.equal(wording.cards[0].targets[0].value,words);assert(wording.cards[0].results.every(item=>item.value===words));assert.equal(wording.steps[0].label,'service selected option service');assert.equal(wording.cards[0].summary,'service selected option');
  upstream=()=>new Response(stream('event: token\ndata: '+JSON.stringify({text:words.slice(0,17)})+'\n\nevent: token\ndata: '+JSON.stringify({text:words.slice(17)})+'\n\nevent: done\ndata: {}\n\n'),{headers:{'content-type':'text/event-stream'}});
  response=await request('threads/one/turn','POST',{text:words,model:'auto'});const exact=[];await contract.readEvents(response.body,event=>{if(event.type==='token')exact.push(event.data.text)});assert.equal(exact.join(''),words);assert.equal(JSON.parse(upstreamCalls.at(-1).init.body).text,words);
  const beforePin=upstreamCalls.filter(call=>call.url.includes('/turn')).length;
  response=await request('threads/one/turn','POST',{text:'hello',model:modelValue('test-model')});assert.equal(response.status,403);assert.equal(upstreamCalls.filter(call=>call.url.includes('/turn')).length,beforePin);
  // The authoritative catalogue is resolved by Lane A from tenant_squad, never a browser grant.
  upstream=(url,init)=>Response.json(init.headers.get('x-tervory-tenant')==='tenant-owned'?['tiger.watch']:[]);
  response=await request('tools?tenant_id=forged&user_id=forged');assert.deepEqual(await response.json(),['tiger.watch']);assert.equal(upstreamCalls.at(-1).init.headers.get('x-tervory-squad'),null);
  currentIdentity={...identity,tenantId:'other-owned'};response=await request('tools');assert.deepEqual(await response.json(),[]);currentIdentity=identity;
  await require('../workspace/lib/tank.ts').commandRequest(identity,'tools?tenant_id=forged&user_id=forged');assert.equal(new URL(upstreamCalls.at(-1).url).search,'');
  upstream=()=>Response.json({detail:'This tool is not available to this user'},{status:403});response=await request('cards/action','POST',{action:'confirm',squads:['tiger']});assert.equal(response.status,403);assert.deepEqual(JSON.parse(upstreamCalls.at(-1).init.body),{action:'confirm'});
  upstream=()=>new Response('private provider error',{status:503});response=await request('threads');assert.equal(response.status,502);assert(!(await response.text()).includes('private provider'));
  console.log('COMMAND-1B: stream, identity, CSRF, role projection, model pinning, files, failures and evidence assertions passed.');
})().catch(error=>{console.error(error);process.exitCode=1;});
