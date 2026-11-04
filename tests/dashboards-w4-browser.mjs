// Offline production-component renders from dashboards-w4-render.cjs.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {pathToFileURL} from 'node:url';
const root=process.cwd();
const {chromium}=await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const output=process.env.W4_SCREENSHOTS || path.join(root,'docs/screenshots/dashboards-w4');
const base=process.env.W4_FIXTURES || '/dev/shm/dashboards-w4';
const screen=process.env.W4_SCREEN || 'founder';
await fs.mkdir(output,{recursive:true});
const server=createServer(async(req,res)=>{
  const pathname=new URL(req.url,'http://offline').pathname;
  let file;
  if(pathname.startsWith('/brand/') || pathname.startsWith('/dashboards/'))file=path.join(root,'workspace/public',pathname);
  else if(pathname.startsWith('/fonts/'))file=path.join(root,'workspace/app',pathname);
  else if(/^\/(main|current)\/(founder|client)\.html$/.test(pathname))file=path.join(base,pathname);
  else {res.writeHead(404);res.end();return;}
  try{res.setHeader('Content-Type',({'.html':'text/html','.svg':'image/svg+xml','.png':'image/png','.woff2':'font/woff2'})[path.extname(file)] || 'application/octet-stream');res.end(await fs.readFile(file));}
  catch{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await chromium.launch({executablePath:process.env.BROWSER_EXECUTABLE,args:['--no-sandbox']});
const errors=[];
try{
  for(const phase of ['main','current'])for(const width of [1440,375]){
    const page=await browser.newPage({viewport:{width,height:900},deviceScaleFactor:1});
    page.on('pageerror',error=>errors.push(error.message));
    await page.route('**/*',route=>new URL(route.request().url()).hostname==='127.0.0.1'?route.continue():route.abort());
    await page.goto(`http://127.0.0.1:${server.address().port}/${phase}/${screen}.html`);
    await page.evaluate(()=>document.fonts.ready);
    await page.locator('img').evaluateAll(images=>Promise.all(images.map(image=>image.decode())));
    if(phase==='current'){
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${screen} ${width}: overflow`);
      const assets=await page.locator('img').evaluateAll(images=>images.map(image=>({src:image.getAttribute('src'),loaded:image.complete&&image.naturalWidth>0,width:image.width,height:image.height})));
      assert(assets.every(image=>image.loaded&&image.width>0&&image.height>0));
      if(screen==='founder'){
        assert.equal((await page.locator('.control-panel').boundingBox()).width,width,'Panel fills the viewport, not the old shared-shell cap');
        const metrics=await page.locator('.control-value').allTextContents();
        assert.deepEqual(metrics,['2','2','83','$12.75']);
        assert.deepEqual(await page.locator('.control-label').allTextContents(),['Sign-ups','Paying clients','Work done today','Spent this month']);
        assert.deepEqual(await page.locator('.control-metric-sub').allTextContents(),['+2 this week','+2 this week','37% by code, no model','']);
        assert.deepEqual(await page.locator('.control-age').allTextContents(),['1h ago','2h ago']);
        for(const name of ['Pause all paid work','Pause workers','Approve all','Switch','Later'])assert(await page.getByRole('button',{name,exact:true}).isEnabled());
        assert.equal(await page.locator('.control-needs-count').textContent(),'3');
        assert.equal(await page.locator('.control-decision-copy').nth(0).textContent(),'2 skills passed their tests');
        assert.equal(await page.locator('.control-decision-copy').nth(1).textContent(),'Cheaper model proven for placeholder market research · saves $50/mo');
        assert.equal(await page.locator('.control-decision-copy').nth(2).textContent(),'Daily check: 7 examples');
        assert.deepEqual(await page.locator('.control-squad-count').allTextContents(),['3 running','4 queued',...Array(5).fill('0 running')]);
        assert.equal(await page.locator('.control-signup-who').first().textContent(),'placeholder signup 0placeholder company 0 · placeholder country');
        assert.equal(await page.getByRole('button',{name:'Approve all',exact:true}).isEnabled(),true);
        assert.equal(await page.locator('[data-tile="workers"]').count(),0);
        assert.equal(await page.locator('.control-top>img').getAttribute('width'),'180');
        assert(!/—|Recorded spend|Approve all ready/.test(await page.locator('body').innerText()));
      }
      const overflow=await page.evaluate(()=>{
        const bad=[];const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
        while(walker.nextNode()){const n=walker.currentNode,e=n.parentElement;if(!n.textContent.trim()||e.closest('script,style,dialog')||!e.checkVisibility())continue;const r=document.createRange();r.selectNodeContents(n);for(const box of r.getClientRects())if(box.width&&(box.right>innerWidth+.5||box.left<-.5))bad.push(n.textContent);}
        return bad;
      });
      assert.deepEqual(overflow,[],`Text outside ${screen} ${width}`);
    }
    await page.screenshot({path:path.join(output,`${phase}-${screen}-${width}.png`),fullPage:true});
    await page.close();
  }
  assert.deepEqual(errors,[]);
  console.log(`PASS: ${screen} route-to-screen placeholder fixtures, main comparison, assets and text bounds at 1440/375. No live data or founder credentials.`);
}finally{await browser.close();await new Promise(resolve=>server.close(resolve));}
