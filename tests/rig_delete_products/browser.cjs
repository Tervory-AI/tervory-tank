// Production component, Workspace route/actions/helper, real Tank and Rig/Postgres.
// Only external Clerk identity is supplied locally; nothing signs in remotely.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {createServer}=require('node:http');
const ts=require('../../workspace/node_modules/typescript');
const {build}=require(process.env.RIG_ESBUILD_PATH||'esbuild');
const {chromium}=require(process.env.RIG_PLAYWRIGHT_PATH||'playwright');
const root=path.resolve(__dirname,'../..');
const tenant='11111111-1111-4111-8111-111111111111';
const other='22222222-2222-4222-8222-222222222222';
const actor={tenantId:tenant,userId:'local-owner'};
function load(file,bindings={}) {
  const code=ts.transpileModule(fs.readFileSync(path.join(root,file),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
  const exports={};
  vm.runInNewContext(code,{exports,require:name=>{assert(name in bindings,name);return bindings[name];},process,fetch,Headers,URL,Uint8Array,TextDecoder,Set,Error});
  return exports;
}
async function main() {
  const out=path.resolve(process.argv[2]);
  const tank=load('workspace/lib/tank.ts',{'@/app/api/zenas/tank':load('workspace/app/api/zenas/tank.ts')});
  const actions=load('workspace/app/rig/admin/actions.ts',{
    '@clerk/nextjs/server':{auth:async()=>({userId:actor.userId,orgRole:'org:member'})},
    '@/lib/tenant':{activeTenant:async()=>actor},
    '../../review/founder':load('workspace/app/review/founder.ts'), '@/lib/tank':tank,
  });
  const route=load('workspace/app/rig/admin/api/route.ts',{'../actions':actions,'next/server':{NextResponse:{json:(body,options={})=>({body,status:options.status||200})}}});
  const initial=await tank.rigAdminPanel(actor);
  assert.equal(initial.products,3);
  const built=await build({stdin:{contents:`import React from 'react'; import {createRoot} from 'react-dom/client'; import {RetailerAdmin} from './app/rig/admin/retailer-admin'; createRoot(document.getElementById('root')).render(<RetailerAdmin initial={${JSON.stringify(initial)}}/>);`,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
  const css=fs.readFileSync(path.join(root,'workspace/app/rig/admin/retailer-admin.css'),'utf8');
  const html=`<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>@font-face{font-family:Inter;src:url(/fonts/Inter-latin.woff2)}@font-face{font-family:Jost;src:url(/fonts/Jost-300-latin.woff2);font-weight:300} :root{--font-inter:Inter;--font-jost:Jost}body{margin:0;background:#fafbfd}${css}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>`;
  const server=createServer(async(req,res)=>{
    try {
      if(req.url==='/app.js'){res.setHeader('content-type','text/javascript');res.end(built.outputFiles[0].text);return;}
      if(req.url.startsWith('/fonts/')){res.end(fs.readFileSync(path.join(root,'workspace/app/fonts',path.basename(req.url))));return;}
      if(req.url==='/rig/admin/api'){
        const chunks=[];for await(const chunk of req)chunks.push(chunk);
        const request=new Request(`http://${req.headers.host}${req.url}`,{method:'POST',headers:req.headers,body:Buffer.concat(chunks)});
        const result=await route.POST(request);res.writeHead(result.status,{'content-type':'application/json'});res.end(JSON.stringify(result.body));return;
      }
      res.setHeader('content-type','text/html');res.end(html);
    } catch(error){res.statusCode=500;res.end();console.error(error.message);}
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const browser=await chromium.launch({executablePath:process.env.READ1_CHROMIUM_EXECUTABLE,args:['--no-sandbox']});
  const result={label:'local, fixture page',screenshots:[],confirmations:[],browser_errors:[],external_requests:[]};
  async function search(){
    const response=await fetch('http://127.0.0.1:8003/v1/rig/search?q=Walnut',{headers:{'x-rig-key':'rk_pub_offline_proof',origin:'https://shop.example'}});
    assert.equal(response.status,200);return response.json();
  }
  try {
    const page=await browser.newPage({viewport:{width:1440,height:1000}});
    page.on('pageerror',error=>result.browser_errors.push(error.message));
    page.on('request',req=>{if(!req.url().startsWith('http://127.0.0.1:'))result.external_requests.push(req.url());});
    await page.goto(`http://127.0.0.1:${server.address().port}/rig/admin`);
    const products=page.getByRole('region',{name:'Products',exact:true});
    await products.getByText('Walnut desk',{exact:true}).waitFor();
    async function capture(prefix){
      for(const width of [1440,375]){
        await page.setViewportSize({width,height:1000});await page.evaluate(()=>document.fonts.ready);
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
        const file=`${prefix}-${width}.png`;await page.screenshot({path:path.join(out,file),fullPage:false});result.screenshots.push(file);
      }
    }
    result.search_before=await search();assert(JSON.stringify(result.search_before).includes('D001'));
    await capture('before');
    // Cancel changes nothing.
    page.once('dialog',async dialog=>{result.confirmations.push(dialog.message());await dialog.dismiss();});
    await products.getByRole('row').filter({hasText:'D001'}).getByRole('button',{name:'Delete',exact:true}).click();
    assert.equal((await tank.rigAdminPanel(actor)).products,3);
    page.once('dialog',async dialog=>{result.confirmations.push(dialog.message());await dialog.accept();});
    await products.getByRole('row').filter({hasText:'D001'}).getByRole('button',{name:'Delete',exact:true}).click();
    await page.getByRole('status').filter({hasText:'1 deleted.'}).waitFor();
    assert.equal(await products.getByText('Walnut desk',{exact:true}).count(),0);
    result.search_after=await search();assert(!JSON.stringify(result.search_after).includes('D001'));
    await capture('one-deleted');
    await products.getByRole('checkbox',{name:'Products',exact:true}).check();
    page.once('dialog',async dialog=>{result.confirmations.push(dialog.message());await dialog.accept();});
    await products.getByRole('button',{name:'Delete selected',exact:true}).click();
    await page.getByRole('status').filter({hasText:'2 deleted.'}).waitFor();
    assert.equal(await products.locator('tbody tr').count(),0);
    await capture('all-deleted');
    assert(result.confirmations[0]==="Delete 1 product? This removes them from your catalogue and search. It can't be undone.");
    assert(result.confirmations[2]==="Delete 2 products? This removes them from your catalogue and search. It can't be undone.");
    const remaining=await tank.rigAdminPanel(actor);const second=await tank.rigAdminPanel({...actor,tenantId:other});
    assert.equal(remaining.products,0);assert.equal(second.products,3);
    result.deletion_receipts=remaining.receipts.filter(row=>row.provider==='delete-products');
    assert.deepEqual(result.deletion_receipts.map(row=>row.updated),[2,1]);
    assert.equal(second.receipts.filter(row=>row.provider==='delete-products').length,0);
    result.founder_without_org_admin='passed';result.second_tenant_products=second.products;result.real_tank='passed';
    assert.deepEqual(result.browser_errors,[]);assert.deepEqual(result.external_requests,[]);
    fs.writeFileSync(path.join(out,'job.json'),JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify(result,null,2));
  } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
