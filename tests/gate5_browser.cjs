const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'),tools=process.env.WORKSPACE_BROWSER_TOOLS || process.env.TRIGGER_BROWSER_TOOLS || process.env.COMMAND_TEST_TOOLS||path.join(__dirname,'browser/node_modules');
const {build}=require(path.join(tools,'esbuild')),{chromium}=require(path.join(tools,'playwright'));
const base=path.join(root,'workspace');
(async()=>{
 const session=`export function SessionProvider({children}){return children} export function useSession(){return {status:'authenticated',data:{principal:{orgId:sessionStorage.getItem('signed-in')?'new-org':null},organisations:['new-org']},update:async()=>{}}} export async function signIn(){if(new URLSearchParams(location.search).has('fail-signin')&&!sessionStorage.getItem('signin-failed')){sessionStorage.setItem('signin-failed','1');throw Error('offline');}sessionStorage.setItem('signed-in','1');location.href='/onboarding'} export async function signOut(){sessionStorage.clear();location.href='/sign-in'}`;
 const bundle=await build({stdin:{contents:`
 import React from 'react';import {createRoot} from 'react-dom/client';
 import {Shell} from './app/shell';import Tasks from './app/tasks/page';import Data from './app/data/page';
 import Onboarding from './app/onboarding/page';import {TriggerSigninButton,OrganisationSwitcher,SignoutButton} from './app/trigger-signin-provider';
 import {ReleaseForm} from '../site/app/release-form';import {BillingScreen} from './app/billing/screen';import {emptyBilling} from './app/billing/billing';
 const pathname=location.pathname;
 const body=pathname==='/tasks'?<Tasks/>:pathname==='/data'?<Data/>:pathname==='/onboarding'?<Onboarding/>:pathname==='/billing'?<BillingScreen tab={new URLSearchParams(location.search).get('tab')||'plans'} view={emptyBilling(true)} notice={null}/>:<section><h1>Trigger sign-in</h1><TriggerSigninButton/><ReleaseForm/></section>;
 createRoot(document.getElementById('root')).render(<><nav aria-label="Launch journeys"><a href="/sign-in">Sign in</a><a href="/tasks">Task board</a><a href="/data">Files</a><a href="/billing">Billing</a></nav><Shell founder={false} reviewer={false} readAccess={async()=>({founder:false,reviewer:false})}>{body}<OrganisationSwitcher/><SignoutButton/></Shell></>);
 `,resolveDir:base,loader:'tsx'},bundle:true,write:false,alias:{'react':path.join(base,'node_modules/react'),'react-dom':path.join(base,'node_modules/react-dom')},jsx:'automatic',outfile:'/tmp/gate5-ui.js',loader:{'.svg':'file'},define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'identity-boundary',setup(b){b.onResolve({filter:/^next\/navigation$/},()=>({path:'navigation',namespace:'fake'}));b.onResolve({filter:/^next\/link$/},()=>({path:'link',namespace:'fake'}));b.onResolve({filter:/^next-auth\/react$/},()=>({path:'session',namespace:'fake'}));b.onResolve({filter:/billing\/actions$|^\.\/actions$/},args=>args.importer.includes('/billing/')?({path:'actions',namespace:'fake'}):undefined);b.onLoad({filter:/.*/,namespace:'fake'},({path:p})=>({contents:p==='link'?`import React from 'react';export default function Link({children,...props}){return <a {...props}>{children}</a>}`:p==='session'?session:p==='actions'?'export async function startCheckout(){return {error:"No payment was started."}}':`export function useSelectedLayoutSegments(){return location.pathname.split("/").filter(Boolean)} export function usePathname(){return location.pathname} export function useSearchParams(){return new URLSearchParams(location.search)} export function useRouter(){return {refresh(){location.reload()}}}`,loader:'jsx',resolveDir:base}));}}]});
 const resources=new Map(bundle.outputFiles.map(f=>['/'+path.basename(f.path),f.contents]));
 const css=fs.readFileSync(path.join(base,'app/globals.css'),'utf8')+'\n'+new TextDecoder().decode(resources.get('/gate5-ui.css')||new Uint8Array());
 const html=`<!doctype html><html lang="en"><head><title>Workspace launch journeys</title><meta name="viewport" content="width=device-width,initial-scale=1"><style>*{box-sizing:border-box}body{margin:0}${css}</style></head><body><div id="root"></div><script src="/gate5-ui.js"></script></body></html>`;
 const accepted=new Map();let conflictNext=false,dropNext=false;let tasks=[],taskPosts=0,feedback=0,failRead=true,signup=0,filePosts=0;
 const server=http.createServer(async(req,res)=>{
  const url=new URL(req.url,'http://local');
  if(resources.has(url.pathname)){res.setHeader('content-type',url.pathname.endsWith('.css')?'text/css':'text/javascript');return res.end(resources.get(url.pathname));}
  const json=(value,status=200)=>{res.writeHead(status,{'content-type':'application/json'});res.end(JSON.stringify(value));};
  if(url.pathname==='/api/tasks'&&req.method==='GET')return failRead?json({error:'unavailable'},503):json(tasks);
  if(url.pathname==='/api/tasks'&&req.method==='POST'){if(conflictNext){conflictNext=false;return json({error:'This task was already submitted.',retry_safe:false},409);}const key=req.headers['idempotency-key'];if(accepted.has(key))return json(accepted.get(key),202);taskPosts++;const chunks=[];for await(const chunk of req)chunks.push(chunk);const input=JSON.parse(Buffer.concat(chunks).toString());await new Promise(r=>setTimeout(r,150));tasks=[...tasks,{id:'own-task-'+taskPosts,title:input.title,task_type:'tier0.answer',status:'done',result:'First result from the local fake.',ledger_id:'00000000-0000-4000-8000-000000000002',created_at:'2026-11-06',model:'code',rung:3,cost_usd:0,latency_ms:12}];accepted.set(key,tasks.at(-1));if(dropNext){dropNext=false;req.socket.destroy();return;}return json(tasks.at(-1),202);}
  if(url.pathname==='/api/feedback'){feedback++;return json({ok:true});}
  if(url.pathname==='/api/base'&&req.method==='GET')return json([]);
  if(url.pathname==='/api/base'&&req.method==='POST'){filePosts++;return json({labels:['own-upload']},202);}
  if(url.pathname==='/api/release-notice'){signup++;return json({stored:signup>1},signup>1?200:503);}
  if(url.pathname.startsWith('/brand/')||url.pathname.startsWith('/fonts/')){const p=path.join(base,url.pathname.startsWith('/brand/')?'public':'app',url.pathname);if(fs.existsSync(p))return res.end(fs.readFileSync(p));res.writeHead(404);return res.end();}
  res.setHeader('content-type','text/html');res.end(html);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const origin=`http://127.0.0.1:${server.address().port}`;
 const browser=await chromium.launch({executablePath:process.env.COMMAND_BROWSER||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const errors=[],outside=[];
 try {
  const context=await browser.newContext({viewport:{width:375,height:812},colorScheme:'dark',reducedMotion:'reduce'});
  await context.route('**/*',async route=>{if(!route.request().url().startsWith(origin+'/')){outside.push(route.request().url());return route.abort();}await new Promise(r=>setTimeout(r,20));return route.continue();});
  await context.addInitScript(()=>{window.__layoutShift=0;new PerformanceObserver(list=>{for(const entry of list.getEntries())if(!entry.hadRecentInput)window.__layoutShift+=entry.value;}).observe({type:'layout-shift',buffered:true});});
  const page=await context.newPage();page.on('pageerror',e=>{errors.push(e.message);console.error('Browser runtime:',e.message);});
  const cdp=await context.newCDPSession(page);await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  const audit=async()=>{await page.addScriptTag({path:path.join(tools,'axe-core/axe.min.js')});const result=await page.evaluate(()=>axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));assert.deepEqual(result.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>({target:n.target,reason:n.failureSummary}))})),[]);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert(await page.evaluate(()=>window.__layoutShift<0.1),"Unexpected layout shift");assert(await page.evaluate(()=>performance.getEntriesByType("navigation")[0].domContentLoadedEventEnd<5000),"Slow phone bootstrap exceeded budget");};
  await page.goto(origin+'/sign-in?fail-signin=1');
  await page.getByRole('textbox',{name:'Get early access',exact:true}).fill('new@example.invalid');
  await page.getByRole('button',{name:'Join the list',exact:true}).click();await page.getByRole('status').filter({hasText:'not saved'}).waitFor();
  await page.getByRole('button',{name:'Join the list',exact:true}).click();await page.getByRole('status').filter({hasText:'Saved.'}).waitFor();assert.equal(signup,2);await audit();
  await page.getByRole('button',{name:'Continue to Trigger sign-in'}).click();await page.getByRole('alert').filter({hasText:'Sign-in could not be completed'}).waitFor();await page.getByRole('button',{name:'Continue to Trigger sign-in'}).click();await page.waitForURL('**/onboarding');
  await page.getByRole('heading').first().waitFor();
  await page.goto(origin+'/tasks');await page.getByRole('alert').filter({hasText:'Tasks could not be loaded'}).waitFor();
  failRead=false;await page.getByRole('button',{name:'Reload tasks'}).click();await page.getByRole('alert').waitFor({state:'hidden'});
  await page.getByLabel('Title',{exact:true}).fill('My first task');await page.getByLabel('What you need',{exact:true}).fill('Read my first request.');
  await page.getByRole('button',{name:'Add task',exact:true}).dblclick();await page.getByText('First result from the local fake.',{exact:true}).waitFor();assert.equal(taskPosts,1);
  assert((await page.locator('.card .meta').first().textContent()).includes('$0.00000'));
  await page.getByRole('button',{name:'Accept',exact:true}).click();await page.getByText('accepted',{exact:true}).waitFor();assert.equal(feedback,1);
  dropNext=true;await page.getByLabel('Title',{exact:true}).fill('Ambiguous task');await page.getByLabel('What you need',{exact:true}).fill('Recover this accepted request.');
  await page.getByRole('button',{name:'Add task',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[role=status]')?.textContent.includes('Do not submit it again')||document.querySelector('#task-title').value==='');
  if(await page.getByRole('status').filter({hasText:'Do not submit it again'}).isVisible()){assert(await page.getByRole('button',{name:'Add task',exact:true}).isDisabled());await page.getByRole('button',{name:'Reload tasks'}).click();await page.getByRole('status').filter({hasText:'Do not submit it again'}).waitFor({state:'hidden'});}assert.equal(taskPosts,2);assert.equal(await page.getByLabel('Title',{exact:true}).inputValue(),'');
  conflictNext=true;await page.getByLabel('Title',{exact:true}).fill('Pending request');await page.getByLabel('What you need',{exact:true}).fill('Do not send this twice.');await page.getByRole('button',{name:'Add task',exact:true}).click();await page.getByRole('status').filter({hasText:'Do not submit it again'}).waitFor();assert(await page.getByRole('button',{name:'Add task',exact:true}).isDisabled());assert.equal(taskPosts,2);

  await audit();
  await page.goto(origin+'/data');await page.getByLabel('CSV rows').waitFor();assert.equal(await page.getByLabel('CSV rows').inputValue(),'');
  await page.getByLabel('Batch name').fill('own-upload');await page.getByLabel('CSV file').setInputFiles({name:'rows.csv',mimeType:'text/csv',buffer:Buffer.from('name,city\nFirst record,Own city')});
  const submit=page.locator('button[type=submit]').first();await submit.click();await page.waitForFunction(()=>document.querySelector('#batch-name').value==='');assert.equal(filePosts,1);await audit();
  for(const tab of ['plans','usage','invoices']){await page.goto(origin+'/billing?tab='+tab);await page.getByRole('heading',{level:1}).waitFor();await audit();}
  await page.goto(origin+'/tasks');await page.keyboard.press('Tab');assert(await page.evaluate(()=>document.activeElement.tagName==='A'));await page.getByRole('button',{name:'Sign out of Trigger sign-in'}).click();await page.waitForURL('**/sign-in');
  assert.deepEqual(errors,[]);assert.deepEqual(outside,[]);
  console.log('Gate 5 browser journeys passed: first signup/error/retry, sign-in/day zero, task/result/receipt/feedback without duplicate submission, file upload, billing tabs, keyboard/phone accessibility and sign-out.');
 } finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
