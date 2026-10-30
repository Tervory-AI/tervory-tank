/* Offline render of the actual dashboard components. No Clerk, Stripe or Tank network calls. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
const React = require(path.join(root, 'workspace/node_modules/react'));
const { renderToStaticMarkup } = require(path.join(root, 'workspace/node_modules/react-dom/server'));
const original = Module._load;
let founder = true;
let sourceError = false;
let identity = {tenantId:'fixture',orgName:'Example Company',userId:'client-fixture'};
const reads = [];
const grants = new Map([['fixture',['base.search','trigger.voice.show']], ['other-client',['tiger.watch']]]);
const fixture = {
  jobs_done: 4, saved_usd: null, credits_left: null,
  daily: [{day:'2026-10-20',calls:4,code:2,delivered:3,spent:0.12}, {day:'2026-10-21',calls:9,code:5,delivered:8,spent:0.24}],
  recent: [{id:'job-fixture',title:'Business list',status:'done'}], skills: [], squad: [], shadow_policies: 0, batch_policies: 0,
};
const savingsTotal={standards:['sonnet'],tops:['opus'],spent:'1',would_have_cost:'4',saved:'3',work_count:1,jobs_count:1,free_count:0,top_cost:'8',top_spent:'1',top_saved:'7',top_count:1,quality_pending:true};
const savings={as_of:'2026-10-21T12:00:00Z',revision:'1',total:savingsTotal,month:savingsTotal,daily:[{...savingsTotal,day:'2026-10-20',cumulative:'3'}],members:[{...savingsTotal,member:'Base'}]};
async function rigProxy(){if(sourceError)throw Error('unavailable');return savings;}
Module._load = function (name, parent, isMain) {
  if (name === 'server-only') return {};
  if (name === 'stripe') return class StripeFixture {
    constructor() {this.subscriptions={list:async function*(){
      yield {customer:'customer-one',items:{data:[{price:{unit_amount:1200}}]}};
      yield {customer:'customer-one',items:{data:[{price:{unit_amount:1500}}]}};
      yield {customer:'free-customer',items:{data:[{price:{unit_amount:0}}]}};
      yield {customer:{id:'customer-two'},items:{data:[{price:{unit_amount:700}}]}};
    }}};
  };
  if (name === '@clerk/nextjs/server') return {
    auth: async () => ({userId: founder ? 'founder-fixture' : 'client-fixture'}),
    currentUser: async () => ({firstName: 'Alex'}),
    clerkClient: async () => ({users: {getCount:async()=>2,getUserList:async()=>({totalCount:2,data:[{id:'user-one',firstName:'Alex',lastName:'Example',createdAt:Date.UTC(2026,9,21),publicMetadata:{company:'Example Company',country:'United States',plan:'Trial'}}]})}}),
  };
  if (name === '@/lib/admin') return {isFounder: id => id === 'founder-fixture'};
  if (name === '@/lib/tenant') return {activeTenant: async()=>identity,currentTenant:async()=>identity};
  if (name === '@/lib/tank') return {
    rigProxy, readClientSavings:async(tenant,endpoint,query)=>{reads.push(['savings',tenant]);return rigProxy('/v1/client-savings'+endpoint,tenant,{query})},
    listTasks:async(tenant,limit)=>{reads.push(['list',tenant,limit]);return Array.from({length:50},(_,index)=>({id:`recent-${index}`}))},
    getTask:async(tenant,id)=>{reads.push(['task',tenant,id]);if(tenant!=='fixture'||id!=='00000000-0000-0000-0000-000000000123')throw Error('Task not found');return {id,title:'Older task',status:'done'}},
    commandTools:async(actor)=>{reads.push(['tools',actor.tenantId,actor.userId]);if(sourceError)throw Error('unavailable');return grants.get(actor.tenantId) ?? []},
    commandRequest:async(actor,endpoint)=>{reads.push(['grants',actor.tenantId,actor.userId,endpoint]);return {json:async()=>[{agent:'zenas',enabled:true},{agent:'base',enabled:false}]}},
    readClientDashboard: async(tenant)=>{reads.push(['dashboard',tenant]);if(sourceError)throw Error('unavailable');return fixture},
    readFounderDashboard: async()=>fixture, readPaidPause:async()=>({paid_paused:false,refused:[]}),
    readDashboardCandidates:async()=>[], setPaidPause:async()=>({}),switchProvenModel:async()=>({ok:true}),
  };
  if (name === 'next/navigation') return {notFound:()=>{throw Error('404')},redirect:()=>{throw Error('redirect')}};
  if (name === 'next/server') return {NextResponse:{json:(data,init)=>Response.json(data,init)}};
  if (name === 'next/cache') return {revalidatePath:()=>{}};
  return original.call(this, name, parent, isMain);
};
for (const ext of ['.ts','.tsx']) require.extensions[ext] = (module, filename) => {
  const source = fs.readFileSync(filename,'utf8');
  module._compile(ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,esModuleInterop:true,target:ts.ScriptTarget.ES2022}}).outputText,filename);
};
require.extensions['.css'] = ()=>{};

async function render() {
  const ClientPage = require('../workspace/app/page.tsx').default;
  const ControlPage = require('../workspace/app/control/page.tsx').default;
  founder=false;
  await assert.rejects(()=>ControlPage(),/404/);
  founder=true;
  let client = renderToStaticMarkup(await ClientPage({searchParams:Promise.resolve({})}));
  const visible = client.replace(/<script[\s\S]*?<\/script>/g,'').replace(/<[^>]*>/g,' ');
  for (const word of ['Skala','Tank','ledger','receipt IDs','haiku','sonnet','eval','gold','shadow','retire','rung','tenant','region box']) {
    assert(!new RegExp(`\\b${word}\\b`,'i').test(visible),`banned client copy: ${word}`);
  }
  require('./client-copy.cjs')(visible);
  for (const text of ['Home','Chats','Files','Billing','Settings','What do you need today?','Add a file','Go','Jobs done this month','You saved','Recent work','Your team','Business lists']) assert(client.includes(text),text);
  for (const removed of ['Saved by team member','the standard model','Credits left','Waiting on you','Your activity could not be loaded']) assert(!visible.includes(removed),removed);
  assert(visible.includes('Business list') && visible.includes('Ready') && visible.includes('$3'));
  assert(client.includes('href="/base"') && !client.includes('href="/tiger"') && !client.includes('href="/zenas"'));
  assert.equal((client.match(/class="client-dashboard-job"/g)||[]).length,1);
  const {loadDashboardData}=require('../workspace/app/dashboard-data.ts');
  reads.length=0;
  for (const [tenantId,expected] of [['fixture',['base']],['other-client',['tiger']]]) {
    identity={...identity,tenantId};
    const start=reads.length;
    const result=await loadDashboardData(identity);
    assert.deepEqual(result.team.map(row=>row.agent),expected);
    assert.deepEqual(reads.slice(start).map(row=>row[1]),[tenantId,tenantId,tenantId]);
    assert.equal(reads.at(-1)[2],'client-fixture');
  }
  identity={...identity,tenantId:'fixture',userId:'founder-fixture'};
  assert.deepEqual((await loadDashboardData(identity)).team.map(row=>row.agent),['zenas']);
  assert.deepEqual(reads.at(-1),['grants','fixture','founder-fixture','squads']);
  identity={...identity,userId:'client-fixture'};
  const originalRecent=fixture.recent;
  fixture.recent=['queued','running','done','failed','done'].map((status,index)=>({id:`offline-${index}`,title:`Offline job ${index}`,status}));
  const four=await loadDashboardData(identity);
  assert.deepEqual(four.recent.map(row=>row.label),['Queued','In progress','Ready','Failed']);
  fixture.recent=[];
  assert(renderToStaticMarkup(await ClientPage()).includes('No work yet.'));
  fixture.recent=[{id:'offline-invalid',title:'Invalid status',status:'waiting'}];
  await assert.rejects(()=>loadDashboardData(identity),/job data is unavailable/);
  fixture.recent=originalRecent;
  sourceError=true;
  await assert.rejects(()=>ClientPage(),/unavailable/);
  sourceError=false;
  assert(client.includes('href="/tasks?task=job-fixture"'));
  const {GET:readTasks}=require('../workspace/app/api/tasks/route.ts');
  const selected='00000000-0000-0000-0000-000000000123';
  const board=await (await readTasks(new Request('https://app.invalid/api/tasks'))).json();
  assert.equal(board.length,50);
  assert(!board.some(row=>row.id===selected));
  const focused=await readTasks(new Request(`https://app.invalid/api/tasks?task=${selected}&tenant_id=other-client`,{headers:{'x-tervory-tenant':'other-client'}}));
  assert.deepEqual(await focused.json(),[{id:selected,title:'Older task',status:'done'}]);
  assert.deepEqual(reads.at(-1),['task','fixture',selected]);
  for(const invalid of ['', 'not-a-uuid', `${selected}/path`, '__proto__']) {
    const before=reads.length;
    assert.equal((await readTasks(new Request(`https://app.invalid/api/tasks?task=${encodeURIComponent(invalid)}`))).status,404);
    assert.equal(reads.length,before);
  }
  identity={...identity,tenantId:'other-client'};
  const denied=await readTasks(new Request(`https://app.invalid/api/tasks?task=${selected}&tenant_id=fixture`));
  assert.equal(denied.status,502);
  assert(!JSON.stringify(await denied.json()).includes('Older task'));
  assert.deepEqual(reads.at(-1),['task','other-client',selected]);
  identity={...identity,tenantId:'fixture'};
  const absent=await readTasks(new Request('https://app.invalid/api/tasks?task=00000000-0000-0000-0000-000000000124'));
  assert.equal(absent.status,502);
  const {FounderDashboard} = require('../workspace/app/control/view.tsx');
  const view={data:fixture,signups:{total:1,recent:[{id:'user',name:'Alex Example',company:'Example Company',country:'United States',plan:'Trial',createdAt:Date.UTC(2026,9,21)}],days:[]},paying:0,paused:false,models:[],refused:[],errors:[]};
  const control=renderToStaticMarkup(React.createElement(FounderDashboard,{view}));
  for (const label of ['Approve all ready','GHOST-1','AGENT-1','BATCH-1']) assert(control.includes(label));
  // WORKERS-2 tile: status, commit, last check-in, Pause/Resume; "not checking in" after 3 minutes.
  assert(control.includes('Workers status unavailable') && control.includes('Workers pause unavailable'));
  const beat=(ageS,state='running',issue=211)=>({worker:'boston',state,issue,commit:'c379a45deadbeef',last_error:null,seen_at:new Date(Date.now()-ageS*1000).toISOString(),age_s:ageS,checking_in:ageS<=180});
  const tile=w=>renderToStaticMarkup(React.createElement(FounderDashboard,{view:{...view,workers:w}}));
  const live=tile({workers_paused:false,worker:beat(30),stale_after_s:180});
  assert(live.includes('Running · issue #211') && live.includes('c379a45deadb') && live.includes('Pause workers') && !live.includes('not checking in'));
  const stale=tile({workers_paused:true,worker:beat(200,'paused',null),stale_after_s:180});
  assert(stale.includes('not checking in') && stale.includes('Resume workers'));
  assert(tile({workers_paused:false,worker:null,stale_after_s:180}).includes('No check-in yet'));
  const {signupSource,payingSource}=require('../workspace/app/control/sources.ts');
  process.env.STRIPE_SECRET_KEY='sk_test_dummy';
  assert.equal(await payingSource(),2);
  delete process.env.STRIPE_SECRET_KEY;
  await assert.rejects(()=>payingSource(),/not connected/);
  assert.equal((await signupSource()).total,2);
  assert.equal((await signupSource()).recent[0].name,'Alex Example');
  const dir=path.join(root,'tests/artifacts/dash-1');fs.mkdirSync(dir,{recursive:true});
  const css=fs.readFileSync(path.join(root,'workspace/app/globals.css'),'utf8') + fs.readFileSync(path.join(root,'workspace/app/control/dashboard.css'),'utf8') + fs.readFileSync(path.join(root,'workspace/app/dashboard.css'),'utf8');
  const fonts=`@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2')}@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}html,body{margin:0}:root{--font-jost:Jost;--font-inter:Inter;--font-mono:Mono}`;
  for (const [name,html] of [['client',client],['founder',control]]) fs.writeFileSync(path.join(dir,`${name}.html`),`<!doctype html><html lang="en"><meta charset="utf-8"><title>DASH-1 offline fixture · ${name}</title><style>${fonts}${css}</style><body><div class="app-shell product"><aside class="shell-side">Shared shell (must be hidden)</aside><div class="shell-main"><main>${html}</main></div></div></body></html>`);
  console.log('Dashboard rendering, non-founder gate, source fixtures and client copy checks passed.');
}
render().catch(err=>{console.error(err);process.exitCode=1});
