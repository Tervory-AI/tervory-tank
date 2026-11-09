// Rig overview and search with fixture clients: full, partial, empty and unanswered data.
// No section may be a blank heading or a placeholder; each empty state names what will appear
// and what is needed. Offline: every request outside the local page is aborted.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import path from 'node:path';
import {createServer} from 'node:http';
import {createRequire} from 'node:module';

const root = process.cwd();
const require = createRequire(path.join(root, 'workspace/package.json'));
const {build} = require(process.env.RIG_ESBUILD_PATH || 'esbuild');
const {chromium} = require(process.env.RIG_PLAYWRIGHT_PATH || 'playwright');
const shots = process.env.RIG_SCREENSHOT_DIR || '';

const STATES = {
  full: {products: 240, fits: 58, active: 240, waiting: 0, feeds: 1, delivery: true},
  partial: {products: 120, fits: 0, active: 3, waiting: 4, feeds: 0, delivery: false},
  empty: {products: 0, fits: 0, active: 0, waiting: 0, feeds: 0, delivery: false},
  unanswered: {products: null, fits: null, active: null, waiting: null, feeds: null, delivery: null},
};
const entry = `import React from 'react'; import {createRoot} from 'react-dom/client';
import {Lab} from './app/rig/lab';
const states=${JSON.stringify(STATES)};
const name=new URLSearchParams(location.search).get('state');const status=states[name];
createRoot(document.getElementById('root')).render(<Lab accountName="Fixture store" products={status.products} fits={status.fits} plugins={{enabled:false}} status={status}/>);`;
const built = await build({stdin: {contents: entry, resolveDir: path.join(root, 'workspace'), loader: 'tsx'},
  bundle: true, write: false, jsx: 'automatic', define: {'process.env.NODE_ENV': '"production"'},
  plugins: [{name: 'unrelated-boundaries', setup(plugin) {
    plugin.onResolve({filter: /^\.\/plugins$|^\.\.\/squad-links$/}, args => ({path: args.path, namespace: 'offline'}));
    plugin.onLoad({filter: /.*/, namespace: 'offline'}, () => ({contents: 'export const Plugins=()=>null; export const SquadLinks=()=>null;'}));
  }}]});
const css = await fs.readFile(path.join(root, 'workspace/app/rig/rig.css'), 'utf8');
const html = `<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}</style></head><body><div id="root"></div><script src="/app.js"></script></body></html>`;
const brand = new Map();
for (const name of await fs.readdir(path.join(root, 'workspace/public/brand'))) {
  if (name.endsWith('.png')) brand.set('/brand/' + name, await fs.readFile(path.join(root, 'workspace/public/brand', name)));
}
const server = createServer((req, res) => {
  if (brand.has(req.url)) { res.setHeader('content-type', 'image/png'); return res.end(brand.get(req.url)); }
  res.setHeader('content-type', req.url === '/app.js' ? 'text/javascript' : 'text/html');
  res.end(req.url === '/app.js' ? built.outputFiles[0].text : html);
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;

/** Every h2 section in the page body: its heading and the text under it. */
async function sections(page) {
  return page.evaluate(() => [...document.querySelectorAll('.body section, .body aside')].filter(n => n.querySelector(':scope > h2'))
    .map(n => ({heading: n.querySelector(':scope > h2').textContent.trim(),
      rest: n.innerText.replace(n.querySelector(':scope > h2').innerText, '').trim()})));
}

async function noEmptySection(page, label) {
  for (const {heading, rest} of await sections(page)) {
    assert(rest.length > 12, `${label}: "${heading}" has no content`);
    assert(!/^[—–-]+$/.test(rest) && !/^—\s/.test(rest), `${label}: "${heading}" shows a placeholder`);
    assert(!/lorem|placeholder|todo|example product|demo/i.test(rest), `${label}: "${heading}" reads like a placeholder`);
  }
  assert.equal(await page.locator('.body footer:empty').count(), 0, `${label}: empty footer`);
}

const browser = await chromium.launch({executablePath: process.env.READ1_CHROMIUM_EXECUTABLE || '/usr/bin/chromium', args: ['--no-sandbox']});
try {
  const page = await browser.newPage();
  page.setDefaultTimeout(5000);
  const errors = [], calls = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/*', async route => {
    const req = route.request();
    if (!req.url().startsWith(base)) return route.abort();
    if (req.method() !== 'POST') return route.continue();
    const body = req.postDataJSON(); calls.push(body);
    if (body.op === 'search') return route.fulfill({json: body.q === 'nothing' ? {results: []} : {exact_match: true, results: [
      {id: 'FX-100', name: 'Fixture frame 100', category: 'Frames', price: {amount: 4200, currency: 'USD'}},
      {id: 'FX-200', name: 'Fixture frame 200', category: 'Frames', price: {amount: 5100, currency: 'USD'}}]}});
    if (body.op === 'graph') return route.fulfill({json: {branches: [{category: 'Grips', products: [{id: 'FX-G1', name: 'Fixture grip', price: {amount: 300}}]}]}});
    if (body.op === 'ask') return route.fulfill({json: {answer: 'Fixture grip fits Fixture frame 100.', items: [{name: 'Fixture grip', price: 'R300'}],
      sources: [{title: 'Fixture grip · R300', detail: 'Catalogue · product FX-G1 · listed in this catalogue'}]}});
    return route.fulfill({status: 404, json: {}});
  });
  const openTab = async (width, name) => {
    if (width === 375) await page.getByRole('button', {name: 'Menu', exact: true}).click();
    await page.locator('nav[aria-label="Rig"]').getByRole('button', {name, exact: true}).click();
  };
  for (const width of [375, 1440]) {
    await page.setViewportSize({width, height: 1000});
    for (const state of Object.keys(STATES)) {
      await page.goto(`${base}/?state=${state}`);
      await page.locator('.search-view').waitFor();
      // Search page, before any search.
      const ask = page.getByRole('complementary', {name: 'Ask Rig'});
      if (state === 'full' || state === 'partial') {
        await ask.getByRole('heading', {name: 'Rig can answer', exact: true}).waitFor();
        assert.deepEqual(await ask.locator('.answer-topics li').allTextContents(),
          ['Which parts fit a product', 'Whether one part fits a product', 'What a product costs in this catalogue']);
        assert.equal(await ask.getByRole('textbox', {name: 'Ask Rig'}).getAttribute('placeholder'), 'Ask about a product or part');
        assert.equal(await ask.locator('.thread').count(), 0);
      } else if (state === 'unanswered') {
        assert.match(await ask.innerText(), /Rig did not answer for this account\. Reload the page to try again\./);
        assert.equal(await page.getByRole('status').innerText(), 'Rig did not answer for this account. Reload the page to try again.');
        assert.equal(await ask.getByRole('textbox').count(), 0, 'no dead Ask box when Rig did not answer');
      } else {
        assert.match(await ask.innerText(), /answers questions from this account's catalogue, so it needs one first\./);
        assert.equal(await ask.getByRole('link', {name: 'Import your catalogue in Rig admin.'}).getAttribute('href'), '/rig/admin');
        assert.equal(await ask.getByRole('textbox').count(), 0, 'no dead Ask box without a catalogue');
      }
      await noEmptySection(page, `${state} search ${width}`);
      if (shots) await page.screenshot({path: path.join(shots, `rig-search-${state}-${width}.png`), fullPage: true});
      // Overview.
      await openTab(width, 'Overview');
      const built = page.locator('section').filter({has: page.getByRole('heading', {name: "What's built", exact: true})});
      const next = page.locator('section').filter({has: page.getByRole('heading', {name: 'Next step', exact: true})});
      const builtText = await built.innerText(), nextText = await next.innerText();
      if (state === 'full') {
        assert.deepEqual(await built.locator('h3').allTextContents(), ['Catalogue', 'Approved fits', 'Catalogue feed', 'Quote delivery']);
        assert.match(builtText, /240 products imported\. All 240 products show in search\./);
        assert.match(builtText, /58 fits are approved/);
        assert.match(nextText, /Nothing is waiting\. The catalogue, approved fits and quote delivery are set up\./);
        assert.equal(await next.getByRole('link').count(), 0);
      }
      if (state === 'partial') {
        assert.deepEqual(await built.locator('h3').allTextContents(), ['Catalogue']);
        // Why only a few products show: the rest are inactive in the catalogue.
        assert.match(builtText, /120 products imported\. 3 products show in search\. 117 products are marked inactive in the catalogue, so shoppers don't see them\./);
        // The count's fine print is hidden on phones by design; the built row says it at both widths.
        if (width === 1440) assert.match(await page.locator('.counts').innerText(), /3 products show in search/);
        assert.equal(await next.locator('h3').innerText(), 'Review 4 suggested fits');
        assert.equal(await next.getByRole('link', {name: 'Open the fit approval queue'}).getAttribute('href'), '/rig/admin');
      }
      if (state === 'empty') {
        assert.equal(await built.locator('h3').count(), 0);
        assert.match(builtText, /Nothing is set up for this account yet\. This list shows the catalogue, approved fits, feeds and quote delivery as each one is set up\./);
        assert.equal(await next.locator('h3').innerText(), 'Import your catalogue');
        assert.equal(await next.getByRole('link', {name: 'Open Rig admin'}).getAttribute('href'), '/rig/admin');
      }
      if (state === 'unanswered') {
        assert.match(builtText, /Rig did not answer for this account, so what's built can't be shown\. Reload the page to try again\./);
        assert.match(nextText, /Rig did not answer for this account, so the next step can't be shown\. Reload the page to try again\./);
      }
      assert(!/Support/.test(builtText + nextText), `${state}: Support link in place of data`);
      await noEmptySection(page, `${state} overview ${width}`);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${state} overview overflow ${width}`);
      if (shots) await page.screenshot({path: path.join(shots, `rig-overview-${state}-${width}.png`), fullPage: true});
    }
    // Ask works end to end from the page: the chosen product goes with the question.
    await page.goto(`${base}/?state=full`);
    await page.getByRole('textbox', {name: 'Search a brand, model or part', exact: true}).first().fill('Fixture');
    await page.getByRole('textbox', {name: 'Search a brand, model or part', exact: true}).first().press('Enter');
    await page.getByRole('heading', {name: 'Fixture frame 100', exact: true}).waitFor();
    const ask = page.getByRole('complementary', {name: 'Ask Rig'});
    assert.deepEqual(await ask.locator('.answer-topics li').allTextContents(),
      ['Which parts fit Fixture frame 100', 'Whether one part fits Fixture frame 100', 'What Fixture frame 100 costs in this catalogue']);
    calls.length = 0;
    await ask.getByRole('textbox', {name: 'Ask Rig'}).fill('Does the fixture grip fit?');
    await ask.getByRole('button', {name: 'Send'}).click();
    await ask.getByText('Fixture grip fits Fixture frame 100.', {exact: true}).waitFor();
    assert.deepEqual(calls.filter(c => c.op === 'ask'), [{op: 'ask', question: 'Does the fixture grip fit?', product_id: 'FX-100'}]);
    assert.equal(await ask.locator('.answer-topics').count(), 0);
    await ask.getByText('Fixture grip · R300', {exact: true}).waitFor();
    if (shots) await page.screenshot({path: path.join(shots, `rig-search-answered-${width}.png`), fullPage: true});
    // A search with no match says so instead of leaving the line blank.
    await page.getByRole('textbox', {name: 'Search a brand, model or part', exact: true}).first().fill('nothing');
    await page.getByRole('textbox', {name: 'Search a brand, model or part', exact: true}).first().press('Enter');
    await page.getByRole('status').filter({hasText: 'Nothing in this catalogue matches "nothing".'}).waitFor();
  }
  assert.deepEqual(errors, []);
  console.log('PASS: Rig overview and search, full/partial/empty/unanswered at 375 and 1440: no empty section, real built rows and next step, Ask topics, Ask sends the chosen product.');
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
