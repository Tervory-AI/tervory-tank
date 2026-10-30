// Existing CommandWindow, isolated HTTP fixtures; no live service or model.
const {createServer}=require('node:http');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..'), base=path.join(root,'workspace');
const deps=process.env.TRIGGER_BROWSER_TOOLS || '/tmp/trigger-browser-tools/node_modules';
const {build}=require(path.join(deps,'esbuild'));
const {chromium}=require(path.join(deps,'playwright'));
const ts=require(path.join(base,'node_modules/typescript'));
require.extensions['.ts']=(m,f)=>m._compile(ts.transpileModule(fs.readFileSync(f,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,f);
const {presentSnapshot}=require(path.join(base,'app/chats/presentation.ts'));
const check=JSON.parse(fs.readFileSync(path.join(__dirname,'check-report.json'),'utf8'));
const thread={thread_id:'offline-trigger',title:'Trigger checker proof',updated_at:'2026-10-28T12:00:00Z',spent_usd:0,saved_usd:0};
const card={card_id:'offline-check',tool:'trigger.check',kind:'other',summary:'trigger.check',status:'pending',arguments:{text:check.text}};
const state={thread,messages:[{message_id:'offline-user',role:'user',content:'Trigger, check: '+check.text}],steps:[{step_id:card.card_id,label:'trigger.check',actor:'trigger',status:'planned'}],cards:[card]};
(async()=>{
const bundle=await build({stdin:{contents:`import React from 'react';import {createRoot} from 'react-dom/client';import {CommandWindow} from './app/chats/window';createRoot(document.getElementById('root')).render(<CommandWindow initialThreads={${JSON.stringify([thread])}} models={[]} founder={true} initialTools={['trigger.write','trigger.check']} account="Tervory"/>);`,resolveDir:base,loader:'tsx'},bundle:true,write:false,jsx:'automatic',outfile:'/tmp/trigger-window.js',loader:{'.svg':'file'},assetNames:'[name]',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'navigation-fixture',setup(b){b.onResolve({filter:/^next\/navigation$/},()=>({path:'nav',namespace:'fixture'}));b.onLoad({filter:/.*/,namespace:'fixture'},()=>({contents:'export function usePathname(){return location.pathname}',loader:'jsx'}));}}]});
const resources=new Map(bundle.outputFiles.map(f=>['/'+path.basename(f.path),f.contents]));
const css=fs.readFileSync(path.join(base,'app/globals.css'),'utf8')+'\n'+new TextDecoder().decode(resources.get('/trigger-window.css'));
const html=`<!doctype html><html><head><style>@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}body{margin:0;--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}${css}</style></head><body><div class="app-shell product"><div class="shell-main"><main id="root"></main></div></div><script src="/trigger-window.js"></script></body></html>`;
let confirms=0;
const server=createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');
 const json=data=>{res.setHeader('Content-Type','application/json');res.end(JSON.stringify(data));};
 if(resources.has(url.pathname)){res.setHeader('Content-Type',url.pathname.endsWith('.svg')?'image/svg+xml':'text/javascript');return res.end(resources.get(url.pathname));}
 if(url.pathname.startsWith('/brand/')||url.pathname.startsWith('/fonts/'))return res.end(fs.readFileSync(path.join(base,url.pathname.startsWith('/brand/')?'public':'app',url.pathname)));
 if(!url.pathname.startsWith('/chats/api/')){res.setHeader('Content-Type','text/html');return res.end(html);}
 if(url.pathname.endsWith('/tools'))return json(['trigger.write','trigger.check']);
 if(url.pathname.endsWith('/threads'))return json([thread]);
 if(url.pathname.includes('/cards/')){confirms++;card.status='confirmed';card.result=check;state.steps[0].status='done';return json(presentSnapshot(state,true).cards[0]);}
 return json(presentSnapshot(state,true));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1100}}), errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(`http://127.0.0.1:${server.address().port}/chats?thread=offline-trigger`);
 await page.getByRole('button',{name:'Confirm',exact:true}).click();
 await page.getByText(check.summary,{exact:true}).waitFor();
 assert.equal(confirms,1);
 assert.equal(await page.getByText(check.text,{exact:true}).count(),1);
 await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:path.join(__dirname,'checker-1440.png'),fullPage:true});
 await page.reload();await page.getByText(check.summary,{exact:true}).waitFor();assert.equal(confirms,1);
 await page.setViewportSize({width:375,height:812});
 await page.getByText(check.summary,{exact:true}).waitFor();
 await page.screenshot({path:path.join(__dirname,'checker-375.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.deepEqual(errors,[]);
 console.log('PASS: real CommandWindow shows unchanged text and actual internal checker report after confirmation and reload; 1440px and 375px, no overflow/runtime errors. Offline fixture only.');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
