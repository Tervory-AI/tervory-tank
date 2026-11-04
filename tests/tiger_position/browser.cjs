/* Offline React/Playwright fixture harness. No Clerk session or live Tank calls.
 * TIGER_TEST_TOOLS points to an isolated npm prefix containing playwright,
 * esbuild and pngjs; production dependencies are unchanged. */
const fs = require('node:fs');
const path = require('node:path');
const http = require('node:http');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const prefix = process.env.TIGER_TEST_TOOLS || path.join(root, '.tmp/browser/node_modules');
const { build } = require(path.join(prefix, 'esbuild'));
const { chromium } = require(path.join(prefix, 'playwright'));
const { PNG } = require(path.join(prefix, 'pngjs'));
const acceptance = process.env.TIGER_ACCEPTANCE_ROW;
assert(!acceptance || ['TG31', 'TG32'].includes(acceptance));
const output = path.join(root, '.tmp/tg2-screenshots', acceptance || 'all');
const copy = require('./frames/copy.json');
fs.mkdirSync(output, { recursive: true });

async function main() {
  const bundle = await build({
    stdin: { contents: `import React from 'react'; import {createRoot} from 'react-dom/client';
      import {TigerApp} from './workspace/app/tiger/view';
      import {emptyData} from './workspace/app/tiger/model';
      import {fixture} from './tests/tiger_position/fixture';
      const params=new URLSearchParams(location.search); const view=params.get('view')||'position';
      const data=params.has('unavailable')?{positions:null,matches:null,sites:null}:params.has('empty')?{...fixture,matches:[],sites:[]}:fixture;
      window.__fixture=data; window.__decisions=[];
      createRoot(document.getElementById('root')).render(<TigerApp data={emptyData()} comparison={data} initialTab="watch" initialView={view} accountName="{Store name}" notice=""/>);`,
      resolveDir: root, sourcefile: 'tg2-fixture.tsx', loader: 'tsx' },
    bundle: true, write: false, platform: 'browser', jsx: 'automatic', nodePaths: [path.join(root, 'workspace/node_modules')],
    define: { 'process.env.NODE_ENV': '"production"' },
    plugins: [{ name: 'offline-server-boundaries', setup(build) {
      build.onResolve({ filter: /^next\/navigation$/ }, () => ({ path: 'navigation', namespace: 'offline' }));
      build.onResolve({ filter: /(?:^|\/)position-actions$/ }, () => ({ path: 'decisions', namespace: 'offline' }));
      build.onResolve({ filter: /(?:^|\/)(plugin-actions|actions)$/ }, () => ({ path: 'actions', namespace: 'offline' }));
      build.onLoad({ filter: /.*/, namespace: 'offline' }, ({ path }) => ({ contents: path === 'navigation'
        ? 'export const useRouter=()=>({refresh(){}}); export const usePathname=()=>"/tiger";'
        : path === 'decisions'
        ? `export async function decideMatch(id,decision){window.__decisions.push({id,decision}); if(window.__failDecision)return {ok:false}; const row=window.__fixture.matches.find(r=>r.id===id); return {ok:true,match:{...row,state:decision==='confirm'?'confirmed':decision==='undo'?'suggested':'rejected'}}}`
        : 'export const addProduct=()=>{}; export const removeProduct=()=>{}; export const addTigerConnection=()=>{}; export const addTigerLink=()=>{}; export const removeTigerConnection=()=>{}; export const removeTigerFile=()=>{}; export const removeTigerLink=()=>{}; export const removeTigerSecret=()=>{}; export const saveTigerKey=()=>{}; export const uploadTigerFiles=()=>{};' }));
    } }],
  });
  const globals = fs.readFileSync(path.join(root, 'workspace/app/globals.css'), 'utf8');
  const tiger = fs.readFileSync(path.join(root, 'workspace/app/tiger/tiger.css'), 'utf8');
  const fonts = `@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2');font-weight:100 900}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}html{--font-inter:Inter;--font-jost:Jost;--font-mono:monospace}`;
  const server = http.createServer((req, res) => {
    const url = new URL(req.url, 'http://placeholder.invalid');
    if (url.pathname === '/bundle.js') { res.setHeader('content-type', 'text/javascript'); return res.end(bundle.outputFiles[0].contents); }
    if (url.pathname.startsWith('/fonts/')) { res.setHeader('content-type', 'font/woff2'); return res.end(fs.readFileSync(path.join(root, 'workspace/app', url.pathname))); }
    if (/^\/(brand|tiger)\/[a-z.-]+\.(png|svg)$/.test(url.pathname)) {
      res.setHeader('content-type', url.pathname.endsWith('svg') ? 'image/svg+xml' : 'image/png');
      return res.end(fs.readFileSync(path.join(root, 'workspace/public', url.pathname)));
    }
    res.setHeader('content-type', 'text/html');
    res.end(`<!doctype html><html><head><meta charset="utf-8"><style>${fonts}\n${globals}\n${tiger}</style></head><body><main id="root"></main><script src="/bundle.js"></script></body></html>`);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  const frames = [
    ['256-10','position',1440,false], ['256-170','position',375,false],
    ['256-283','matches',1440,false], ['256-406','matches',375,false],
    ['256-471','sites',1440,false], ['256-609','sites',375,false],
    ['267-19232','matches',1440,true], ['267-19356','matches',375,true],
    ['267-19424','sites',1440,true], ['267-19562','sites',375,true],
  ];
  const results = [];
  try {
    for (const [id, view, width, empty] of frames.filter(frame => !acceptance || frame[3] === (acceptance === 'TG32'))) {
      const reference = PNG.sync.read(fs.readFileSync(path.join(__dirname, 'frames', `${id}.png`)));
      // The 89px approval/illustrative-data bar belongs to Figma review, not the app.
      const height = reference.height - 89;
      const page = await browser.newPage({ viewport: { width, height }, colorScheme: 'light' });
      await page.route('**/*', route => route.request().url().startsWith(origin) ? route.continue() : route.abort());
      await page.goto(`${origin}/?view=${view}${empty ? '&empty=1' : ''}`, {waitUntil:'domcontentloaded'});
      await page.locator('.position-block').waitFor(); await page.evaluate(() => document.fonts.ready);
      await page.waitForFunction(() => Array.from(document.images).every(image => image.complete));
      assert.equal(await page.locator('.watch-views [aria-selected=true]').innerText(), {position:'Price position', matches:'Matches to review', sites:'Competitor sites'}[view]);
      assert.equal(await page.locator('.search input').getAttribute('placeholder'), 'Search watched products, readings and alerts');
      assert.equal(await page.locator('.position-block').evaluate(el => el.scrollWidth <= el.clientWidth), true);
      if (empty) assert.equal(await page.locator('.comparison-empty').innerText(), view === 'matches' ? 'No matches to review.' : 'No saved sites.');
      const text = (await page.locator('.body').innerText()).replace(/\s+/g, ' ');
      for (const fixed of [...copy.common, ...(empty ? [copy.empty[view]] : copy[view])]) assert.ok(text.includes(fixed), `${id}: missing approved text ${fixed}`);
      assert.equal(await page.getByText('Illustrative values · Figma only.', { exact: true }).count(), 0);
      for (const image of await page.locator('img:visible').all()) {
        if (!await image.evaluate(el => { const box=el.getBoundingClientRect(); return box.right>0&&box.bottom>0&&box.left<innerWidth&&box.top<innerHeight; })) continue;
        assert.equal(await image.evaluate(el => el.complete && el.naturalWidth > 0), true);
        const geometry=await image.evaluate(el=>({src:el.getAttribute('src'),width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height}));
        const expected=geometry.src.endsWith('search.svg')?[16,16]:geometry.src.endsWith('dot.svg')?[6,6]:width===375?[186,34]:[208,38];
        assert.deepEqual([geometry.width,geometry.height],expected,`${id}: static asset geometry ${geometry.src}`);
      }
      const actual = PNG.sync.read(await page.screenshot({ path: path.join(output, `${id}.png`) }));
      let changed = 0, total = 0;
      const diff = new PNG({width,height});
      for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
        const a=(y*width+x)*4, r=((y+89)*width+x)*4;
        const delta=Math.max(...[0,1,2].map(c=>Math.abs(actual.data[a+c]-reference.data[r+c])));
        if(delta>32) changed++;
        total++;
        diff.data[a]=delta>32?232:actual.data[a]; diff.data[a+1]=delta>32?0:actual.data[a+1]; diff.data[a+2]=delta>32?8:actual.data[a+2]; diff.data[a+3]=255;
      }
      fs.writeFileSync(path.join(output, `${id}-diff.png`), PNG.sync.write(diff));
      const geometry = await page.locator('.body,.head,.watch-views,.watch-content,.table-wrap:visible,.cards:visible,.note-card,.foot').evaluateAll(els => els.map(el=>({class:el.className,x:el.getBoundingClientRect().x,y:el.getBoundingClientRect().y,width:el.getBoundingClientRect().width,height:el.getBoundingClientRect().height})));
      const expectedFoot = {'256-10':1283,'256-170':2539,'256-283':999,'256-406':1769,'256-471':979,'256-609':1984,'267-19232':366,'267-19356':522,'267-19424':483,'267-19562':639};
      assert.ok(Math.abs(geometry.find(row=>row.class==='foot').y-expectedFoot[id])<=1, `${id}: footer differs from frame geometry`);
      if(width===375&&!empty) {
        const heights=await page.locator('.cards:visible > li').evaluateAll(els=>els.map(el=>el.getBoundingClientRect().height));
        assert.deepEqual(heights,{position:[814,477,363],matches:[529,529],sites:[344,364,364]}[view]);
      }
      const styles=await page.locator('.search').evaluate(el=>({form:getComputedStyle(el).cssText,height:el.getBoundingClientRect().height,padding:getComputedStyle(el).padding,min:getComputedStyle(el).minHeight,box:getComputedStyle(el).boxSizing,input:getComputedStyle(el.querySelector('input')).height})); const result={id,width,height,changedRatio:changed/total,geometry,styles}; results.push(result);
      console.log(id, 'changed pixels', (result.changedRatio*100).toFixed(2)+'%');
      if (view==='matches'&&!empty) {
        const scope=page.locator(width===375?'.matches-cards':'.matches-table');
        await scope.getByRole('button',{name:'Reject',exact:true}).click();
        await scope.getByRole('button',{name:'Undo',exact:true}).first().click();
        await scope.getByRole('button',{name:'Confirm',exact:true}).first().click();
        assert.deepEqual(await page.evaluate(()=>window.__decisions.map(row=>row.decision)),['reject','undo','confirm']);
      }
      if(view==='sites'&&!empty) {
        await page.getByRole('button',{name:'Tiger Plugins → Source links',exact:true}).click();
        assert.equal(await page.getByRole('tab',{name:'Source links',exact:true}).getAttribute('aria-selected'),'true');
        await page.getByRole('button',{name:'Close',exact:true}).click();
      }
      await page.close();
    }
    for(const width of [375,1440]) {
      const page=await browser.newPage({viewport:{width,height:900}});
      await page.goto(`${origin}/?view=matches&unavailable=1`, {waitUntil:'domcontentloaded'}); await page.locator('.position-block').waitFor();
      assert.equal(await page.getByText('No matches to review.',{exact:true}).count(),0);
      await page.close();
      const failed=await browser.newPage({viewport:{width,height:900}});
      await failed.goto(`${origin}/?view=matches`, {waitUntil:'domcontentloaded'}); await failed.locator('.position-block').waitFor();
      await failed.evaluate(()=>window.__failDecision=true);
      const scope=failed.locator(width===375?'.matches-cards':'.matches-table');
      await scope.getByRole('button',{name:'Reject',exact:true}).click();
      await scope.locator('[data-action-state=failed]').waitFor();
      assert.equal(await scope.getByRole('button',{name:'Confirm',exact:true}).isDisabled(),true);
      assert.equal(await failed.evaluate(()=>window.__decisions.length),1);
      assert.equal(await scope.getByText('Rejected',{exact:true}).count(),1);
      await failed.close();
    }
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
    for(const result of results) assert.ok(result.changedRatio<0.05,`${result.id}: ${(result.changedRatio*100).toFixed(2)}% differs`);
  } finally { await browser.close(); await new Promise(resolve=>server.close(resolve)); }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
