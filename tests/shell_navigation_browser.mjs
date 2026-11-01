// Offline acceptance: real Shell + SquadLinks + CSS; only Clerk and Next routing are mocked.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';
const root=process.cwd(), require=createRequire(path.join(root,'workspace/package.json'));
const {build}=require(process.env.NAV_ESBUILD_PATH || 'esbuild');
const {chromium}=require(process.env.NAV_PLAYWRIGHT_PATH || 'playwright');
const out=process.env.NAV_SCREENSHOT_DIR || path.join(process.env.TMPDIR || '/tmp','navigation-shots');
await fs.mkdir(out,{recursive:true});
const entry=`import React from 'react';import {createRoot} from 'react-dom/client';import {Shell} from './app/shell';
const readAccess=async()=>({founder:false,reviewer:false});
createRoot(document.getElementById('root')).render(<Shell founder={false} reviewer={false} readAccess={readAccess}><a id="content-link" href="#content">Content fixture</a></Shell>);`;
const bundle=await build({stdin:{contents:entry,resolveDir:path.join(root,'workspace'),loader:'tsx'},bundle:true,write:false,format:'esm',jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},plugins:[{name:'offline-routing',setup(b){
 b.onResolve({filter:/^(@clerk\/nextjs|next\/link|next\/navigation)$/},args=>({path:args.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},args=>({loader:'js',resolveDir:path.join(root,'workspace'),contents:args.path==='@clerk/nextjs'?`export const useAuth=()=>({isLoaded:true,isSignedIn:false,userId:null});export const OrganizationSwitcher=()=>null;export const UserButton=()=>null;`:args.path==='next/link'?`import React from 'react';export default function Link(props){return React.createElement('a',props);}`:`export const usePathname=()=>location.pathname;export const useSearchParams=()=>new URLSearchParams(location.search);export const useSelectedLayoutSegments=()=>[new URLSearchParams(location.search).get('room')||location.pathname.split('/')[1]];` }));
}}]});
const css=await fs.readFile(path.join(root,'workspace/app/globals.css'),'utf8')+`
@font-face{font-family:Inter;src:url(/fonts/Inter-latin.woff2);font-weight:100 900}
@font-face{font-family:Jost;src:url(/fonts/Jost-300-latin.woff2);font-weight:300}
@font-face{font-family:Mono;src:url(/fonts/JetBrainsMono-latin.woff2)}
:root{--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}`;
// Preload only repository assets; request paths never reach the filesystem.
const assets=new Map();
for(const name of await fs.readdir(path.join(root,'workspace/public/brand'))){
 const file=path.join(root,'workspace/public/brand',name);
 if((await fs.stat(file)).isFile()) assets.set(`/brand/${name}`,await fs.readFile(file));
}
for(const name of ['Inter-latin.woff2','Jost-300-latin.woff2','JetBrainsMono-latin.woff2']){
 assets.set(`/fonts/${name}`,await fs.readFile(path.join(root,'workspace/app/fonts',name)));
}
const server=createServer((req,res)=>{
 if(req.url==='/bundle.js'){res.setHeader('Content-Type','text/javascript');res.end(bundle.outputFiles[0].text);return;}
 if(assets.has(req.url)){res.end(assets.get(req.url));return;}
 res.setHeader('Content-Type','text/html');res.end(`<style>${css}</style><div id="root"></div><script type="module" src="/bundle.js"></script>`);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({headless:true,executablePath:process.env.NAV_CHROMIUM || undefined});
const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
const base=`http://127.0.0.1:${server.address().port}`;
try {
 for(const width of [375,1440]){
  await page.setViewportSize({width,height:900});await page.goto(`${base}/chats`);await page.locator('#app-sidebar').waitFor({state:width===375?'hidden':'visible'});
  assert.equal(await page.getByRole('link',{name:'Chats',exact:true,includeHidden:true}).getAttribute('aria-current'),'page');
  assert.equal(await page.getByRole('link',{name:'Dashboard',exact:true,includeHidden:true}).getAttribute('aria-current'),null);
  if(width===375){
   await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').textContent(),'Skip to content');
   await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').getAttribute('id'),'shell-menu');
   await page.keyboard.press('Tab');assert.equal(await page.locator(':focus').getAttribute('id'),'content-link');
   await page.locator('#shell-menu').focus();await page.keyboard.press('Enter');
   await page.waitForFunction(()=>document.activeElement?.id==='shell-side-close');
   assert.equal(await page.locator('#shell-menu').getAttribute('aria-expanded'),'true');
   await page.evaluate(()=>document.fonts.ready);
   const closeBounds=await page.locator('#shell-side-close').boundingBox();
   const sideBounds=await page.locator('#app-sidebar').boundingBox();
   assert(closeBounds.x+closeBounds.width<=sideBounds.x+sideBounds.width);
   await page.screenshot({path:path.join(out,'mobile-open.png')});
   await page.getByRole('button',{name:'Squad',exact:true}).click();
   await page.locator('#squad-popout').waitFor();await page.keyboard.press('Escape');
   await page.locator('#squad-popout').waitFor({state:'hidden'});
   assert.equal(await page.locator('#shell-menu').getAttribute('aria-expanded'),'true');
   assert.equal((await page.locator(':focus').textContent()).trim(),'Squad');
   await page.keyboard.press('Escape');await page.locator('#app-sidebar').waitFor({state:'hidden'});
   assert.equal(await page.locator(':focus').getAttribute('id'),'shell-menu');
   assert.equal(await page.locator('#shell-menu').getAttribute('aria-expanded'),'false');
   await page.keyboard.press('Enter');await page.locator('#shell-side-close').click();
   assert.equal(await page.locator(':focus').getAttribute('id'),'shell-menu');
   await page.locator('#shell-menu').click();await page.locator('.shell-dim').click({position:{x:350,y:600}});
   assert.equal(await page.locator(':focus').getAttribute('id'),'shell-menu');
   await page.screenshot({path:path.join(out,'mobile-closed.png')});
  } else {
   await page.getByRole('link',{name:'Chats',exact:true,includeHidden:true}).focus();
   assert.equal(await page.locator(':focus').textContent(),'Chats');
   assert.equal(await page.locator(':focus').evaluate(el=>getComputedStyle(el).outlineStyle),'solid');
   await page.screenshot({path:path.join(out,'desktop.png')});
  }
 }
 // Host rules: only / rewrites; Chats and Projects deep links stay intact.
 for(const host of ['app.tervory.com','zenas.tervory.com','base.tervory.com','tiger.tervory.com']){
  const target=`https://${host}/chats`;
  await page.route(target,route=>route.fulfill({contentType:'text/html',body:`<style>${css}</style><div id="root"></div><script type="module">${bundle.outputFiles[0].text}</script>`}));
  await page.goto(target);await page.getByRole('link',{name:'Chats',exact:true,includeHidden:true}).waitFor();
  const href=await page.getByRole('link',{name:'Chats',exact:true,includeHidden:true}).getAttribute('href');assert.equal(new URL(href,target).pathname,'/chats');
  assert.equal(await page.getByRole('link',{name:'Projects',exact:true}).getAttribute('href'),'/matters');
  assert.equal(await page.getByRole('link',{name:'Dashboard',exact:true,includeHidden:true}).getAttribute('href'),'https://app.tervory.com/');
 }
 await page.goto(`${base}/?room=moot`);await page.locator('#app-sidebar').waitFor();
 assert.equal(await page.getByRole('link',{name:'Dashboard',exact:true,includeHidden:true}).getAttribute('aria-current'),null);
 assert.deepEqual(errors,[]);console.log('PASS: 375/1440 drawer tab order, focus, open/close/Escape, desktop navigation, host destinations, current-page state. Offline fixture only.');
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
