// Offline browser proof using the unchanged Skala component and captured DB results.
import assert from 'node:assert/strict';
import {createServer} from 'node:http';
import {readFile, mkdir} from 'node:fs/promises';
import {createRequire} from 'node:module';
import {dirname, join, basename} from 'node:path';
import {fileURLToPath} from 'node:url';
const root = join(dirname(fileURLToPath(import.meta.url)), '../..');
const require = createRequire(join(root, 'workspace/package.json'));
const {build} = require(process.env.SKALA_ESBUILD_PATH || 'esbuild');
const {chromium} = require(process.env.SKALA_PLAYWRIGHT_PATH || 'playwright');
const proof = JSON.parse(await readFile(join(root, 'tests/skala_intake/ready.json'), 'utf8'));
const approved = JSON.parse(await readFile(join(root, 'tests/skala_intake/approved.json'), 'utf8'));
const shots = process.env.SKALA_SHOTS_DIR || '/tmp/skala-intake-shots';
await mkdir(shots, {recursive:true});
const bundle = await build({stdin:{contents:`import React from 'react'; import {createRoot} from 'react-dom/client'; import {SkalaApp} from './app/skala/view'; import {SquadFounderProvider} from './app/squad-links'; createRoot(document.getElementById('root')).render(<SquadFounderProvider founder={true}><SkalaApp accountName={null} skills={${JSON.stringify(proof.skills)}} loadError={null}/></SquadFounderProvider>);`,resolveDir:join(root,'workspace'),loader:'tsx'},bundle:true,write:false,format:'iife',jsx:'automatic',plugins:[{name:'offline-next-navigation',setup(builder){builder.onResolve({filter:/^next\/navigation$/},()=>({path:'navigation',namespace:'offline'}));builder.onLoad({filter:/.*/,namespace:'offline'},()=>({contents:"export function usePathname(){return '/skala'} export function useRouter(){return {refresh(){},push(){},replace(){}}}",loader:'js'}));}}]});
const css = await readFile(join(root,'workspace/app/skala/skala.css'));
const html = '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>@font-face{font-family:Jost;font-weight:300;src:url(/jost.woff2)}:root{--font-jost:Jost;--font-inter:Arial;--font-mono:monospace}body{margin:0}</style><link rel="stylesheet" href="/style.css"></head><body><div id="root"></div><script src="/page.js"></script></body></html>';
const server = createServer(async(req,res)=>{try{const path = new URL(req.url,'http://localhost').pathname;let content;if(path==='/')content=html;else if(path==='/style.css'){res.setHeader('Content-Type','text/css');content=css;}else if(path==='/page.js'){res.setHeader('Content-Type','application/javascript');content=bundle.outputFiles[0].text;}else if(path==='/jost.woff2')content=await readFile(join(root,'workspace/app/fonts/Jost-300-latin.woff2'));else if(path.startsWith('/brand/'))content=await readFile(join(root,'workspace/public/brand',basename(path)));else{res.writeHead(404);res.end();return;}res.end(content);}catch{res.writeHead(404);res.end();}});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});
try{
 for(const width of [1440,375]){
  const page=await browser.newPage({viewport:{width,height:width===1440?1100:812}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));let confirmed=false;
  await page.route('**/api/skala',async route=>{
   if(route.request().method()==='GET')return route.fulfill({json:proof.skills.map(s=>({...s,state:confirmed?'approved':s.state}))});
   const body=route.request().postDataJSON();
   if(body.action==='bulk-preview')return route.fulfill({json:proof.preview});
   assert.equal(body.action,'bulk-confirm');assert.equal(body.confirmed,true);assert.equal(body.token,'offline-preview');confirmed=true;return route.fulfill({json:approved});
  });
  await page.goto(`http://127.0.0.1:${server.address().port}`);
  await page.getByRole('heading',{name:'trigger.proselint',exact:true}).waitFor();
  assert.equal(await page.locator('.sk-meta').filter({hasText:/^100%$/}).count(),7);
  assert.equal(await page.getByText('no model',{exact:true}).count(),7);
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  await page.screenshot({path:join(shots,`ready-${width}.png`)});
  await page.getByRole('button',{name:'Approve all ready',exact:true}).click();
  const dialog=page.getByRole('dialog',{name:'Confirm ready versions'});await dialog.waitFor();
  assert.equal(await dialog.locator('li').count(),7);
  for(const item of proof.preview.items)assert.ok(await dialog.getByText(`${item.id} · ${item.version}`,{exact:false}).count());
  await page.screenshot({path:join(shots,`bulk-${width}.png`)});
  await dialog.getByRole('button',{name:'Confirm listed approvals'}).click();
  await page.getByText('7 versions approved. Each approval was recorded.',{exact:true}).waitFor();
  assert.equal(await page.locator('.sk-state.approved').count(),7);
  await page.screenshot({path:join(shots,`approved-${width}.png`)});
  assert.deepEqual(errors,[]);await page.close();
 }
 console.log('PASS: unchanged Skala UI, seven 100% code skills, bulk confirmation, 1440px and 375px');
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
