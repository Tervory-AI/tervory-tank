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
const {normalizeSnapshot}=require(path.join(base,'app/chats/contract.ts'));
const {presentSnapshot}=require(path.join(base,'app/chats/presentation.ts'));
const fixtures=JSON.parse(fs.readFileSync(path.join(__dirname,'window-fixtures.json'),'utf8'));
let state=fixtures.pending;
const thread=state.thread,card=state.cards[0];
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
 if(url.pathname.includes('/cards/')){confirms++;state=fixtures.saved;return json(presentSnapshot(normalizeSnapshot(state),true).cards.find(c=>c.card_id===card.card_id));}
 return json(presentSnapshot(normalizeSnapshot(state),true));
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
const page=await browser.newPage({viewport:{width:1440,height:1100}}), errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
 await page.goto(`http://127.0.0.1:${server.address().port}/chats?thread=${thread.thread_id}`);
 await page.getByRole('button',{name:'Confirm',exact:true}).waitFor();
 const preview=card.arguments.brief_markdown;
 await page.getByText(preview,{exact:true}).waitFor();
 assert.equal(confirms,0);
 await page.evaluate(()=>document.fonts.ready);
 await page.screenshot({path:path.join(__dirname,'voice-preview-1440.png'),fullPage:true});
 await page.setViewportSize({width:375,height:812});
 await page.getByText(preview,{exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(__dirname,'voice-preview-375.png'),fullPage:true});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.getByRole('button',{name:'Confirm',exact:true}).click();assert.equal(confirms,1);
 await page.reload();
 const history=fixtures.saved.cards.find(c=>c.tool==='trigger.voice.show').result.text;
 await page.getByText(history,{exact:true}).waitFor();
 await page.getByText(history,{exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(__dirname,'voice-history-375.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:1100});
 await page.getByText(history,{exact:true}).scrollIntoViewIfNeeded();
 await page.screenshot({path:path.join(__dirname,'voice-history-1440.png'),fullPage:true});
 assert.equal(confirms,1);assert.deepEqual(errors,[]);
 console.log('PASS: real CommandWindow renders the real parser preview before Confirm and saved version history after reload at 375/1440px. Offline fixture; no live founder acceptance claimed.');
}finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
