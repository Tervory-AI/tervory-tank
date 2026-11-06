// Exercise production clients/routes against a loopback-only Tank protocol double.
const assert = require('node:assert/strict');
const http = require('node:http');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const Module = require('node:module');
const root = path.resolve(__dirname, '..');
const ts = require('../workspace/node_modules/typescript');
const identity = {tenantId:'00000000-0000-4000-8000-000000000101',userId:'offline-client',orgId:'100'};
const jobId = '00000000-0000-4000-8000-000000000201';
const ledgerId = '00000000-0000-4000-8000-000000000301';
const key = 'placeholder';
const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'workspace-gate3-'));
const amounts = {spent:'0.01234567',would_have_cost:'0.04200000',saved:'0.02965433',work_count:1,jobs_count:1,free_count:0,top_cost:'0.04200000',top_spent:'0.01234567',top_saved:'0.02965433',top_count:1,quality_pending:false};
const savings = {as_of:'2026-11-06T00:00:00Z',revision:ledgerId,total:amounts,month:amounts,daily:[{...amounts,day:'2026-11-06',cumulative:amounts.saved}],members:[{...amounts,member:'Tank'}]};
let task, taskPosts = 0, polls = 0, accepted = 0, baseRows = [], failLedger = false;
const traffic = [], failures = [];
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://local');
    const chunks = []; for await (const chunk of req) chunks.push(chunk);
    const body = chunks.length ? JSON.parse(Buffer.concat(chunks).toString()) : null;
    traffic.push({path:url.pathname,method:req.method});
    assert.equal(req.headers['x-tank-key'], key);
    const json = (value, status = 200) => { res.writeHead(status, {'content-type':'application/json'});res.end(JSON.stringify(value)); };
    if (url.pathname === '/v1/trigger-signin/config') return json({regions:{'us-east':{issuer:'https://auth.tervory.com',client_id:'10',workspace_client_id:'20',project_id:'30',organisations:{'100':identity.tenantId},founders:[]}}});
    if (url.pathname.startsWith('/v1/tenants/')) {
      assert.equal(url.pathname, `/v1/tenants/${identity.tenantId}/home`);assert.equal(body,null);
      return json({tenant_id:identity.tenantId,home_region:'us-east'});
    }
    assert.equal(req.headers['x-tervory-home-region'], 'us-east');
    assert.equal(body?.tenant_id ?? url.searchParams.get('tenant_id'), identity.tenantId);
    if (url.pathname === '/v1/tasks' && req.method === 'POST') {
      assert.equal(body.created_by, identity.userId);taskPosts++;
      task = {id:jobId,title:body.title,task_type:body.task_type,status:'queued',result:null,error:null,ledger_id:null,created_at:'2026-11-06T00:00:00Z'};
      return json(task,202);
    }
    if (url.pathname === '/v1/tasks') {
      polls++;task = {...task,status:polls === 1 ? 'running':'done',...(polls > 1 ? {result:'Result from the offline source.',ledger_id:ledgerId,model:'recorded-model',rung:1,cost_usd:amounts.spent,latency_ms:120}: {})};
      return json([task]);
    }
    if (url.pathname === `/v1/ledger/${ledgerId}/feedback`) {
      assert.equal(body.by,identity.userId);assert.equal(body.feedback,'accepted');accepted=1;
      return json({ok:true});
    }
    if (url.pathname === '/v1/ledger/summary') {
      if (failLedger) return json({detail:'private-upstream-detail'},503);
      return json({days:30,calls:1,delivered:1,accepted,rejected:0,acceptance_rate:accepted,unpriced:0,cost_usd:Number(amounts.spent),cost_per_delivered_usd:Number(amounts.spent),cost_per_accepted_usd:accepted?Number(amounts.spent):null,by_model:[{model:task.model,rung:1,calls:1,accepted,rejected:0,tokens_in:120,tokens_out:34,cost_usd:amounts.spent,unpriced:0}]});
    }
    if (url.pathname === '/v1/dashboards/client') return json({jobs_done:1,recent:[{id:jobId,title:task.title,status:'done'}],granted_squads:['base']});
    if (url.pathname === '/v1/client-savings') return json(savings);
    if (url.pathname === '/v1/client-savings/revision') return json({revision:ledgerId});
    if (url.pathname === '/v1/client-savings/rows') return json({rows:[{id:ledgerId,job_id:jobId,job_title:task.title,member:'Tank',day:'2026-11-06',spent:amounts.spent,would_have_cost:amounts.would_have_cost,saved:amounts.saved,free_work:false,top_cost:amounts.top_cost,top_saved:amounts.top_saved,quality_compared:true}],total:amounts,page:0,has_more:false,as_of:savings.as_of});
    if (url.pathname === '/v1/base/run') {
      assert.equal(body.created_by,identity.userId);assert.equal(body.preview,true);
      baseRows = body.records.map((record,index)=>({id:String(index),task_id:jobId,batch:body.batch,raw:record,profile:{name:{value:record.name,source:'uploaded-csv',confidence:1},city:{value:record.city,source:'uploaded-csv',confidence:1}},passes:{clean:{status:'done'}},status:'done',confidence:1,error:null}));
      return json({task,tasks:[task],records:baseRows.length,batches:1,skills:{}});
    }
    if (url.pathname === '/v1/base/batches') return json([{batch:'own-upload',total:baseRows.length,done:baseRows.length,failed:0,pending:0}]);
    if (url.pathname === '/v1/base/records') { assert.equal(url.searchParams.get('batch'),'own-upload');return json(baseRows); }
    throw Error(`Unexpected protocol path: ${url.pathname}`);
  } catch (error) { failures.push(error);res.writeHead(500);res.end(); }
});
const originalLoad = Module._load, originalResolve = Module._resolveFilename, nativeFetch = globalThis.fetch;
const previous = {...process.env};
const post = (body, route = '/api/tasks') => new Request('https://app.tervory.com'+route,{method:'POST',headers:{'content-type':'application/json','Idempotency-Key':'00000000-0000-4000-8000-000000000401'},body:JSON.stringify(body)});
async function main() {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  Object.assign(process.env,{TANK_URL:origin,TANK_API_KEY:'placeholder',TANK_REGION:'us-east',WORKSPACE_SUBMISSIONS_DIR:temporary});
  globalThis.fetch = (input,init) => {
    assert.equal(new URL(input instanceof Request ? input.url : input).origin,origin,'No live service is permitted');
    return nativeFetch(input,init);
  };
  Module._load = function(name,parent,main) {
    if (name === 'server-only') return {};
    if (name === '@/lib/tenant') return {currentTenant:async()=>identity,activeTenant:async()=>identity};
    if (name === '@/lib/trigger-signin' || name === './trigger-signin') return {auth:async()=>identity,signinToken:async()=>key};
    if (name === 'next/headers') return {cookies:async()=>({get:()=>undefined})};
    return originalLoad.call(this,name,parent,main);
  };
  Module._resolveFilename = function(name,parent,...args) { if(name.startsWith('@/'))name=path.join(root,'workspace',name.slice(2));return originalResolve.call(this,name,parent,...args); };
  require.extensions['.ts'] = (module,file) => module._compile(ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022,esModuleInterop:true}}).outputText,file);
  const runtime = await require('../workspace/lib/trigger-signin-runtime.ts').signinRuntime();assert.equal(runtime.organisations['100'],identity.tenantId);
  const tasks = require('../workspace/app/api/tasks/route.ts');
  const request = {title:'Own source task',request:'Read the supplied source.',tenant_id:'untrusted-browser-tenant'};
  const created = await tasks.POST(post(request));assert.equal(created.status,202);assert.equal((await created.json()).id,jobId);
  assert.equal((await tasks.POST(post(request))).status,202);assert.equal(taskPosts,1);
  assert.equal((await (await tasks.GET()).json())[0].status,'running');
  const complete = (await (await tasks.GET()).json())[0];assert.equal(complete.status,'done');assert.equal(complete.ledger_id,ledgerId);assert.equal(complete.cost_usd,amounts.spent);
  const feedback = require('../workspace/app/api/feedback/route.ts');
  assert.equal((await feedback.POST(post({ledger_id:ledgerId,feedback:'accepted',tenant_id:'untrusted-browser-tenant'},'/api/feedback'))).status,200);
  const ledger = require('../workspace/app/api/ledger/route.ts');
  const summary = await (await ledger.GET(new Request('https://app.tervory.com/api/ledger?tenant_id=untrusted-browser-tenant'))).json();
  assert.equal(summary.accepted,1);assert.equal(summary.by_model[0].tokens_in,120);assert.equal(summary.cost_usd,Number(amounts.spent));
  const tank = require('../workspace/lib/tank.ts');assert.equal((await tank.readClientDashboard(identity.tenantId)).jobs_done,1);
  const actions = require('../workspace/app/tank/proof/savings-actions.ts');
  const report = await actions.readClientSavings();assert.equal(report.total.saved,amounts.saved);
  assert.equal((await actions.readSavingsRevision()).revision,ledgerId);
  const evidence = await actions.readClientSavingsRows({end:savings.as_of,page:0,tenant_id:'untrusted-browser-tenant',population:'excluded'});
  assert.equal(evidence.rows[0].job_id,jobId);assert.equal(evidence.rows[0].id,ledgerId);assert.equal(evidence.rows[0].spent,complete.cost_usd);
  const base = require('../workspace/app/api/base/route.ts');
  const imported = await base.POST(post({batch:'own-upload',csv:'name,city\nOwn company,Own city',preview:true},'/api/base'));assert.equal(imported.status,202);assert.equal((await imported.json()).records,1);
  const records = await (await base.GET(new Request('https://app.tervory.com/api/base?batch=own-upload&tenant_id=untrusted-browser-tenant'))).json();assert.equal(records[0].profile.name.source,'uploaded-csv');
  const exported = await require('../workspace/app/api/base/export/route.ts').GET(new Request('https://app.tervory.com/api/base/export?batch=own-upload'));
  assert.equal(exported.status,200);assert((await exported.text()).includes('Own company'));assert.equal(exported.headers.get('cache-control'),'no-store');
  failLedger=true;const unavailable=await ledger.GET(new Request('https://app.tervory.com/api/ledger'));assert.equal(unavailable.status,502);assert(!(await unavailable.text()).includes('private-upstream-detail'));
  failLedger=false;assert.equal((await ledger.GET(new Request('https://app.tervory.com/api/ledger'))).status,200);assert.equal(taskPosts,1);
  assert.deepEqual(failures,[]);
  console.log(`Gate 3: ${traffic.length} loopback protocol requests passed: sign-in configuration, tenant directory, task/result/receipt/feedback, dashboard, savings evidence/revision, CSV source/export and read recovery; one task submission.`);
}
main().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
  Module._load=originalLoad;Module._resolveFilename=originalResolve;globalThis.fetch=nativeFetch;
  for(const name of Object.keys(process.env))if(!(name in previous))delete process.env[name];Object.assign(process.env,previous);
  server.closeAllConnections();await new Promise(resolve=>server.close(resolve));fs.rmSync(temporary,{recursive:true,force:true});
});
