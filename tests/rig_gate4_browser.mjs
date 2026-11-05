import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';

const root = process.cwd();
const require = createRequire(path.join(root, 'workspace/package.json'));
const {build} = require(process.env.RIG_ESBUILD_PATH || 'esbuild');
const {chromium} = require(process.env.RIG_PLAYWRIGHT_PATH || 'playwright');
const initial = {products:0, product_rows:[], currency:'USD', settings:{}, price_configured:false,
  templates:{}, fits:[], missed_searches:[], receipts:[], feeds:[]};
const entry = `import React from 'react'; import {createRoot} from 'react-dom/client';
import {Lab, CatalogueNumbers} from './app/rig/lab';
import {RetailerAdmin} from './app/rig/admin/retailer-admin';
import {OrderRows} from './app/rig/admin/commerce-admin';
import {ThreeDAdminScreen} from './app/rig/admin/three-d/screen';
const mode=new URLSearchParams(location.search).get('view');
const node=mode==='admin'?<RetailerAdmin initial={${JSON.stringify(initial)}}/>:
mode==='orders'?<OrderRows orders={[]} now={0}/>:
mode==='three-d'?<ThreeDAdminScreen enabled jobs={[]} jobId="placeholder" action={async()=>{}}/>:
mode==='unknown'?<CatalogueNumbers products={null} fits={null}/>:
<Lab accountName="Your account" products={0} fits={0} plugins={{enabled:false}}/>;
createRoot(document.getElementById('root')).render(node);`;
const built = await build({stdin:{contents:entry,resolveDir:path.join(root,'workspace'),loader:'tsx'},
  bundle:true,write:false,jsx:'automatic',define:{'process.env.NODE_ENV':'"production"'},
  plugins:[{name:'unrelated-boundaries',setup(plugin){
    plugin.onResolve({filter:/^\.\/plugins$|^\.\.\/squad-links$|^\.\/preview$/}, args=>({path:args.path,namespace:'offline'}));
    plugin.onLoad({filter:/.*/,namespace:'offline'},()=>({contents:'export const Plugins=()=>null; export const SquadLinks=()=>null; export const ProductPreview=()=>null;'}));
  }}]});
const css = (await Promise.all(['rig.css','admin/retailer-admin.css','admin/three-d/three-d.css'].map(name=>
  fs.readFile(path.join(root,'workspace/app/rig',name),'utf8')))).join('\n');
const html=`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>`;
const server=createServer((req,res)=>{res.setHeader('content-type',req.url==='/app.js'?'text/javascript':'text/html');res.end(req.url==='/app.js'?built.outputFiles[0].text:html);});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const base=`http://127.0.0.1:${server.address().port}`;
const browser=await chromium.launch({executablePath:process.env.READ1_CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});
try {
  const page=await browser.newPage();
  const errors=[]; page.on('pageerror',error=>errors.push(error.message));
  await page.route('**/*',route=>route.request().url().startsWith(base)?route.continue():route.abort());
  for(const width of [375,1440]) {
    await page.setViewportSize({width,height:1000});
    await page.goto(base+'/?view=unknown');
    await page.locator('.counts').waitFor();
    assert.deepEqual(await page.locator('.count b').allTextContents(),['—','—']);
    await page.goto(base);
    await page.locator('.results-line a').waitFor();
    assert.match(await page.locator('.results-line').innerText(), /—.*Import your catalogue/s);
    if(width===375) await page.getByRole('button',{name:'Menu',exact:true}).click();
    await page.getByRole('button',{name:'Overview',exact:true}).click();
    assert.deepEqual(await page.locator('.count b').allTextContents(),['0','0']);
    assert.equal(await page.getByRole('link',{name:'Import your catalogue file or connect an official feed.'}).count(),1);
    for(const tab of ['Catalogues','Fits to review','Skins','Progress']) {
      if(width===375) await page.getByRole('button',{name:'Menu',exact:true}).click();
      await page.getByRole('button',{name:tab,exact:true}).click();
      assert((await page.locator('.body').innerText()).match(/0|—/),tab);
      assert((await page.locator('.body a').count())>0,tab);
      assert((await page.locator('.count b').allTextContents()).every(value=>value==='0'||value==='—'),tab);
    }
    await page.goto(base+'/?view=admin');
    await page.getByRole('heading',{name:'Retailer settings',exact:true}).waitFor();
    assert.match(await page.locator('.retailer-count').innerText(),/^0 products/);
    assert.match(await page.locator('.retailer-products tbody').innerText(),/0.*Import your catalogue/s);
    for(const [heading,first] of [['Feeds','Start with your catalogue file'],['Fit approval queue','Find fit suggestions'],
      ['Setup templates','Choose the product categories'],['What shoppers couldn’t find','Search'],['Import history','Import a file']]) {
      const section=page.locator('section').filter({has:page.getByRole('heading',{name:heading,exact:true})});
      assert((await section.innerText()).includes(first),heading);
    }
    assert.equal(await page.locator('.retailer-fit, .retailer-template, .retailer-history article, .retailer-searches li').count(),0);
    await page.goto(base+'/?view=orders');
    await page.getByRole('link',{name:'Shop connection'}).waitFor();
    assert.equal(await page.locator('.rig-commerce-orders strong').innerText(),'0');
    assert.equal(await page.locator('[data-order-id]').count(),0);
    await page.goto(base+'/?view=three-d');
    await page.getByRole('heading',{name:'3D product views'}).waitFor();
    for(const heading of ['Products to review','Preparation progress']) {
      const section=page.locator('section').filter({has:page.getByRole('heading',{name:heading,exact:true})});
      assert.equal(await section.locator('b').innerText(),'0');
      assert.equal(await section.getByRole('link',{name:'Prepare product view'}).count(),1);
    }
    assert.equal(await page.locator('.three-admin article').count(),0);
    assert(!/Sample Desk|Archon|STI-P-9|demo price/i.test(await page.locator('body').innerText()));
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: Rig day-zero counts, unknown values, empty lists and first actions at both widths.');
} finally {await browser.close();await new Promise(resolve=>server.close(resolve));}
