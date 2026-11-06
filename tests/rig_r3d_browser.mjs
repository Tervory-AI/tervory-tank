import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import http from 'node:http';
import crypto from 'node:crypto';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {chromium} = require(process.env.RIG_PLAYWRIGHT_PATH || '../scripts/browser-check/node_modules/playwright');
const root = process.cwd(), bundle = path.join(root, 'agents/rig/rigbox/three_d/widget');
const model = fs.readFileSync(path.join(root, 'tests/fixtures/rig_three_d/models/centre.glb'));
const digest = crypto.createHash('sha256').update(model).digest('hex');
const generated = fs.readFileSync(path.join(root, 'tests/fixtures/rig_r3d/approved.glb'));
const generatedDigest = crypto.createHash('sha256').update(generated).digest('hex');
const key = 'rk_pub_offline_r3d';
const clients = new Set(), requested = [];
const empty = () => ({date:'2026-11-06',timezone:'UTC',counts:{approved:0,today:0,active:0},approved:[],live:null,latest:null});
let state = empty(), deny = false, completedRows = [];
const event = (stage, elapsed) => ({id:stage,stage,elapsed_ms:elapsed,at:'2026-11-06T12:00:00+00:00',outcome:'delivered',cost:{amount_usd:'0.10',basis:'upper_bound',receipt_ids:[]}});
const build = n => ({id:`00000000-0000-0000-0000-${String(n).padStart(12,'0')}`,name:`Approved fixture ${n}`,status:'approved',today:true,
  price:{amount:'100',currency:'USD'},events:['understand','design','check','price','ready'].map((stage,i)=>event(stage,2500*i)),
  cost:{amount_usd:'0.10',basis:'upper_bound',receipt_ids:[]},
  model:{url:`/v1/rig/3d/assets/00000000-0000-0000-0000-${String(n).padStart(12,'0')}`,sha256:n===2?generatedDigest:digest,size_bytes:n===2?generated.length:model.length},
  receipt:{job_id:`00000000-0000-0000-0000-${String(n).padStart(12,'0')}`,approved_at:'2026-11-06T12:00:00Z',sha256:digest,receipt_ids:['00000000-0000-0000-0000-000000000123']}});
const packet = () => 'event: build\ndata: ' + JSON.stringify(state) + '\n\n';
const publish = () => {for(const client of clients) client.write(packet());};
const server = http.createServer((req,res) => {
  requested.push(req.url);
  if(req.url === '/3d/config') {res.setHeader('Content-Type','application/json');res.end(JSON.stringify({publishable_key:key}));return;}
  if(req.url.startsWith('/v1/')) {
    if(req.headers['x-rig-key'] !== key || deny) {res.writeHead(403);res.end();return;}
    if(req.url.endsWith('/events')) {
      res.writeHead(200,{'Content-Type':'text/event-stream','Cache-Control':'no-store'});clients.add(res);res.write(packet());req.on('close',()=>clients.delete(res));return;
    }
    if(req.url.startsWith('/v1/rig/3d/terminal/completed?')) {
      const before = new URL(req.url,'http://offline.invalid').searchParams.get('before');
      const start = before ? completedRows.findIndex(row=>row.id===before)+1 : 0;
      const rows = completedRows.slice(start,start+20);
      res.setHeader('Content-Type','application/json');res.end(JSON.stringify({builds:rows,next:rows.length===20?rows.at(-1).id:null}));return;
    }
    if(req.url.startsWith('/v1/rig/3d/assets/')) {res.writeHead(200,{'Content-Type':'model/gltf-binary'});res.end(req.url.endsWith('000000000002')?generated:model);return;}
  }
  const name = ['/3d/','/3d/wall'].includes(req.url) ? 'index.html' : req.url.replace(/^\/3d\//,'');
  const filename = path.resolve(bundle,name);
  if(!filename.startsWith(bundle + path.sep) || !fs.existsSync(filename)) {res.writeHead(404);res.end();return;}
  const types = {'.js':'text/javascript','.html':'text/html','.css':'text/css','.wasm':'application/wasm'};
  res.writeHead(200,{'Content-Type':types[path.extname(name)] || 'application/octet-stream'});res.end(fs.readFileSync(filename));
});
await new Promise(resolve => server.listen(0,'127.0.0.1',resolve));
const url = `http://127.0.0.1:${server.address().port}`;
const browser = await chromium.launch({headless:true,executablePath:process.env.READ1_CHROMIUM_EXECUTABLE || '/usr/bin/chromium',
  args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
  for(const viewport of [{width:1920,height:1080},{width:1080,height:1920}]) {
    state = empty(); deny = false; completedRows = [];
    // Keep the full CSS viewport/touch targets while bounding software-GPU raster
    // work on shared CI runners. Real WebGL/texture/RAF assertions remain below.
    const context = await browser.newContext({viewport,hasTouch:true,deviceScaleFactor:.5});
    await context.route('**/*',route=>route.request().url().startsWith(url) ? route.continue() : route.abort());
    const page = await context.newPage(), errors=[];
    // Only Date is controlled: keep native RAF/touch scheduling for real WebGL.
    await page.clock.setFixedTime(new Date());
    page.on('pageerror',error=>errors.push(error.message));
    await page.addInitScript(() => {
      window.draws = 0;
      for(const Class of [WebGLRenderingContext,WebGL2RenderingContext]) {
        for(const name of ['drawElements','drawArrays']) {
          const original = Class.prototype[name];
          Class.prototype[name] = function(...args) {window.draws++;return original.apply(this,args);};
        }
      }
    });
    const before = requested.length;
    await page.goto(url + '/3d/');
    await page.waitForFunction(()=>document.querySelector('#connection').textContent === '3D product view');
    assert.equal(await page.locator('#today-count').textContent(),'0');
    assert.equal(await page.locator('#model').isVisible(),false);
    assert.match(await page.locator('#intro').innerText(),/Prepare and approve your first product/);
    assert(!requested.slice(before).some(name=>name.includes('/assets/') || name.includes('terminal-runtime')));
    assert(await page.evaluate(()=>document.documentElement.scrollWidth === innerWidth && document.documentElement.scrollHeight === innerHeight));
    await page.clock.setFixedTime(new Date(await page.evaluate(()=>Date.now()) + 61000));
    await page.waitForFunction(()=>document.body.dataset.attract === 'true');
    assert.equal(await page.locator('body').getAttribute('data-attract'),'true');
    assert.equal(await page.locator('#model').isVisible(),false);
    // The idle wall cycles models every eight seconds. Start the manual-control
    // journey with a real touch so it cannot replace the model mid-assertion.
    await page.touchscreen.tap(50, 150);
    assert.equal(await page.locator('body').getAttribute('data-attract'),'false');
    state = { ...empty(), counts:{approved:2,today:2,active:0}, approved:[build(1),build(2)], latest:build(1)}; publish();
    await page.waitForFunction(()=>document.querySelector('#model').dataset.phase === 'wireframe',{},{timeout:20000});
    await page.waitForFunction(()=>document.querySelector('#model').dataset.phase === 'solid');
    await page.waitForFunction(()=>document.querySelector('#product-name').textContent === 'Approved fixture 1');
    assert((await page.evaluate(()=>window.draws)) > 0);
    const draws = await page.evaluate(()=>window.draws); await page.waitForTimeout(600);
    assert((await page.evaluate(()=>window.draws)) > draws,'The lit model must continue rendering on RAF');
    assert.match(await page.locator('#cost').textContent(),/Reserved cost.*\$0.10/);
    assert.equal(await page.locator('[data-stage=check] time').textContent(),'5.0s');
    assert(await page.locator('#receipt').isVisible());
    assert.equal(await page.locator('#receipt-hash').textContent(),digest);
    await page.locator('#rotate-right').tap(); await page.locator('#zoom-in').tap();
    assert.equal(await page.locator('body').getAttribute('data-attract'),'false');
    for(const name of ['rotate-left','rotate-right','zoom-in','zoom-out','next','reset']) {
      const box = await page.locator('#'+name).boundingBox();assert(box.width>=64 && box.height>=64);
      assert(box.y>=0 && box.y+box.height<=viewport.height);
    }
    await page.locator('#rotate-left').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'rotate-left');
    const directory = process.env.RIG_SCREENSHOT_DIR;
    if(directory) {fs.mkdirSync(directory,{recursive:true});await page.screenshot({path:path.join(directory,`r3d-${viewport.width}.png`),scale:'css'});}
    await page.clock.setFixedTime(new Date(await page.evaluate(()=>Date.now()) + 130000));
    try {await page.waitForFunction(()=>document.querySelector('#product-name').textContent === 'Approved fixture 2');}
    catch(error) {console.error(await page.evaluate(()=>({body:document.body.innerText,attract:document.body.dataset.attract,now:Date.now()})));throw error;}
    // Observe the automatic switch, then resume the user's interaction before
    // checking textures/progress; another idle cycle must not replace this asset.
    await page.touchscreen.tap(50, 150);
    await page.waitForFunction(()=>document.querySelector('#model').dataset.phase === 'solid');
    assert(requested.some(name=>name.endsWith('basis_transcoder.wasm')),'Real Forge KTX2 output must use the existing texture decoder');
    const live = {...build(100),status:'running',model:null,receipt:null,events:[event('understand',500),event('design',1800)]};
    state = {...state,live,counts:{...state.counts,active:1}};publish();
    await page.waitForFunction(()=>document.querySelector('#live-name').textContent === 'Approved fixture 100');
    assert.equal(await page.locator('[data-stage=ready] time').textContent(),'—');
    assert.equal(await page.locator('#receipt').isVisible(),false);
    assert(!requested.slice(before).some(name=>name.endsWith('/00000000-0000-0000-0000-000000000100')));
    state = {...state,live:null,latest:{...live,status:'failed',events:[event('understand',500),{...event('design',2000),outcome:'failed'}]},counts:{...state.counts,active:0}};publish();
    await page.waitForFunction(()=>document.querySelector('#build-status').textContent === 'The model conversion failed.');
    assert.equal(await page.locator('[data-stage=design]').getAttribute('data-outcome'),'failed');
    assert.equal(await page.locator('#receipt').isVisible(),false);
    state = {...state,live,latest:live,counts:{...state.counts,active:1}};
    await page.goto(url+'/3d/wall');
    await page.waitForFunction(()=>document.querySelectorAll('#completed button').length === 2);
    assert(await page.locator('#wall-builds').isVisible());assert.equal(await page.locator('#active-count').textContent(),'1');
    assert.equal(await page.locator('#live-name').textContent(),'Approved fixture 100');
    completedRows = Array.from({length:21},(_,n)=>build(n+1));
    state = {...state,approved:completedRows.slice(0,20),counts:{approved:21,today:21,active:1}};publish();
    await page.waitForFunction(()=>!document.querySelector('#more-builds').hidden);
    await page.locator('#more-builds').tap();
    await page.waitForFunction(()=>document.querySelectorAll('#completed button').length === 21);
    await page.locator('#completed button').last().tap();
    await page.waitForFunction(()=>document.querySelector('#product-name').textContent === 'Approved fixture 21');
    publish();await page.waitForTimeout(100);
    assert.equal(await page.locator('#product-name').textContent(),'Approved fixture 21');
    completedRows = [build(100),...completedRows];
    state = {...state,live:null,latest:build(100),approved:completedRows.slice(0,20),counts:{approved:22,today:22,active:0}};publish();
    await page.waitForFunction(()=>document.querySelector('#product-name').textContent === 'Approved fixture 100');
    assert.equal(await page.locator('#receipt-id').textContent(),build(100).id);
    deny=true; for(const client of clients) client.end();
    await page.waitForFunction(()=>!document.querySelector('#retry').hidden);
    assert.equal(await page.locator('#model').isVisible(),false);
    deny=false;state=empty();await page.locator('#retry').tap();
    await page.waitForFunction(()=>document.querySelector('#today-count').textContent === '0');
    assert.deepEqual(errors,[]);
    await context.close();
  }
  console.log('R3D touch layouts, real Three/WebGL, wireframe, stream, receipts, idle, wall, day zero and retry passed.');
} finally {
  await browser.close();for(const client of clients) client.end();server.closeAllConnections();await new Promise(resolve=>server.close(resolve));
}
