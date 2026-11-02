// Local component-only proof. All displayed rows are test fixtures; no production API or scan.
const {createServer}=require('node:http');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'..'), base=path.join(root,'workspace');
const {build}=require(path.join(root,'.git/ui-tools/node_modules/esbuild'));
const {chromium}=require(path.join(root,'.git/ui-tools/node_modules/playwright'));
(async()=>{
 const findings=Array.from({length:8},(_,i)=>({rule:`rule-${i}`,severity:'medium',tool:'zap',file:'https://example.test/'+('long'.repeat(35)),line:0,explanation:i===0?'<img src=x onerror=alert(1)>':`Explanation ${i}`,remediation:`Fix ${i}`}));
 const views=[{kind:'proof',domain:'example.test',name:'_tervory-verify.example.test',value:'tervory-'+('a'.repeat(64)),expires_at:'2099-11-02T00:00:00Z'},{kind:'findings',scan_id:'12345678-1234-1234-1234-123456789012',findings},{kind:'scan',scan_id:'pending-id',status:'running'},{kind:'scan',scan_id:'failed-id',status:'failed'},{kind:'findings',scan_id:'empty-id',findings:[]},{kind:'proof',domain:'example.test',expires_at:'2001-01-01T00:00:00Z'}];
 const bundle=await build({stdin:{contents:`import React from 'react';import{createRoot}from'react-dom/client';import{RadixCard}from'./app/chats/radix-card';const views=${JSON.stringify(views)};createRoot(document.getElementById('root')).render(<div className="command-window"><main>{views.map((view,i)=><RadixCard key={i} view={view} onPrepare={message=>{document.getElementById('draft').textContent=message}}/>)}<p id="draft"/></main></div>);`,resolveDir:base,loader:'tsx'},bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'}});
 const css=fs.readFileSync(path.join(base,'app/chats/window.css'),'utf8');
 const fonts=`@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}:root{--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}`;
 const html=`<!doctype html><meta charset="utf-8"><style>${fonts}${css}\n.command-window{display:block;height:auto;overflow:visible}.command-window>main{max-width:720px;margin:auto}.cw-radix{margin-bottom:24px}body{margin:0}</style><div id="root"></div><script src="/bundle.js"></script>`;
 const server=createServer((req,res)=>{if(/^\/fonts\/[A-Za-z0-9-]+\.woff2$/.test(req.url)){res.setHeader('content-type','font/woff2');return res.end(fs.readFileSync(path.join(base,'app',req.url)))}if(req.url==='/bundle.js'){res.setHeader('content-type','text/javascript');res.end(bundle.outputFiles[0].contents)}else{res.setHeader('content-type','text/html');res.end(html)}});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE||'/home/ammosync/.cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell',args:['--no-sandbox'],headless:true});
 try{const context=await browser.newContext({permissions:['clipboard-read','clipboard-write']});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(`http://127.0.0.1:${server.address().port}`);await page.evaluate(()=>document.fonts.ready);assert((await page.locator('h3').first().evaluate(n=>getComputedStyle(n).fontFamily)).includes('Jost'));
 await page.getByRole('button',{name:'Copy TXT value',exact:true}).click();assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),views[0].value);
 await page.getByRole('button',{name:'Copy scan ID',exact:true}).first().click();assert.equal(await page.evaluate(()=>navigator.clipboard.readText()),views[1].scan_id);
 assert.equal(await page.locator('.cw-radix-finding').count(),8);await page.locator('.cw-radix-finding').last().locator('summary').click();assert((await page.locator('.cw-radix-finding').last().textContent()).includes('Fix 7'));assert(await page.locator('.cw-radix-finding').last().getAttribute('open') !== null);
 assert.equal(await page.locator('.cw-radix img').count(),0);assert((await page.locator('.cw-radix-finding').first().textContent()).includes('<img src=x onerror=alert(1)>'));
 await page.getByRole('heading',{name:'Scan running',exact:true}).waitFor();await page.getByRole('heading',{name:'Scan did not finish',exact:true}).waitFor();await page.getByRole('heading',{name:'No findings returned',exact:true}).waitFor();await page.getByRole('heading',{name:'Proof expired',exact:true}).waitFor();
 await page.getByRole('button',{name:'I’ve added the record · check proof',exact:true}).click();assert((await page.locator('#draft').textContent()).includes('prepare a scan'));
 for(const width of [320,375,768,1440]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width}`);await page.screenshot({path:path.join(root,`.git/radix-${width}.png`),fullPage:true});}
 await page.evaluate(()=>Object.defineProperty(navigator.clipboard,'writeText',{configurable:true,value:async()=>{throw new Error('clipboard denied')}}));await page.getByRole('button',{name:'Copy TXT value',exact:true}).click();await page.getByText('Copy unavailable. Select the value above to copy it.',{exact:true}).waitFor();
 assert.deepEqual(errors,[]);console.log('PASS browser clipboard, eighth finding, escaped hostile text, real statuses, unsent draft, four responsive widths');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1});
