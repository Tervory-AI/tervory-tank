/* Real approved contact component, local HTTP, and fake failure before retry. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const http = require('node:http');
const assert = require('node:assert/strict');
const {createRequire} = require('node:module');
const root = path.resolve(__dirname, '..');
const template = path.join(root, 'agents/tisan/templates/next-site');
const req = createRequire(path.join(template, 'package.json'));
const ts = req('typescript');
const React = req('react');
const {renderToStaticMarkup} = req('react-dom/server');
const {chromium} = req('playwright');
const AxeBuilder = req('@axe-core/playwright').default;
const quality = req('./scripts/quality-check.cjs');
const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server.address().port)));
const close = server => new Promise(resolve => {server.closeAllConnections(); server.close(resolve);});

function source(relative) {
  const module = {exports: {}};
  vm.runInNewContext(ts.transpileModule(fs.readFileSync(path.join(template, relative), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX},
  }).outputText, {exports: module.exports, module, require: req, Response}, {filename: relative});
  return module.exports;
}

async function proof() {
  const content = renderToStaticMarkup(React.createElement(source('app/contact/page.tsx').default));
  const route = source('app/api/contact/route.ts');
  const css = await req('postcss')([req('@tailwindcss/postcss')({base: template})]).process(
    fs.readFileSync(path.join(template, 'app/globals.css'), 'utf8'), {from: path.join(template, 'app/globals.css')});
  const html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Contact</title><style>' +
    fs.readFileSync(path.join(template, 'app/tokens.css'), 'utf8') + css.css +
    '</style></head><body class="bg-paper font-body text-ink"><main id="content" class="px-4 py-8 sm:px-6">' + content + '</main></body></html>';
  let submitted = 0;
  const server = http.createServer(async (request, response) => {
    if (request.url === '/api/contact' && request.method === 'POST') {
      for await (const _chunk of request) { /* drain local fixture input */ }
      submitted++;
      const result = submitted === 1 ? Response.json({ok: false}, {status: 503}) : await route.POST();
      response.writeHead(result.status, {'Content-Type': 'application/json'});
      response.end(await result.text());
      return;
    }
    response.writeHead(200, {'Content-Type': 'text/html'});
    response.end(html);
  });
  const port = await listen(server), origin = `http://127.0.0.1:${port}`;
  const proxy = quality.proxyFor(origin), proxyPort = await listen(proxy);
  const browser = await chromium.launch({headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage',
    '--host-resolver-rules=MAP * ~NOTFOUND, EXCLUDE 127.0.0.1']});
  const external = [];
  try {
    for (const width of [375, 1440]) {
      const context = await browser.newContext({viewport: {width, height: 900}});
      await context.route('**/*', route => {
        if (new URL(route.request().url()).origin !== origin) {
          external.push(route.request().url());
          return route.abort();
        }
        return route.continue();
      });
      const page = await context.newPage();
      const cdp = await context.newCDPSession(page);
      await cdp.send('Network.enable');
      await cdp.send('Network.emulateNetworkConditions', {offline: false, latency: 150,
        downloadThroughput: 750 * 1024 / 8, uploadThroughput: 250 * 1024 / 8});
      await cdp.send('Emulation.setCPUThrottlingRate', {rate: 4});
      await page.goto(origin + '/contact', {waitUntil: 'networkidle', timeout: 15000});
      assert.equal(await page.title(), 'Contact');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      const audit = await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa']).analyze();
      assert.deepEqual(audit.violations, []);
      for (const name of ['Name','Email','Message']) assert.equal(await page.getByLabel(name, {exact: true}).count(), 1);
      await page.keyboard.press('Tab');
      assert.equal(await page.locator(':focus').getAttribute('id'), 'contact-name');
      const focus = await page.locator(':focus').evaluate(el => getComputedStyle(el).outlineStyle);
      assert.notEqual(focus, 'none');
      await page.keyboard.type('placeholder customer');
      await page.keyboard.press('Tab');
      assert.equal(await page.locator(':focus').getAttribute('id'), 'contact-email');
      await page.keyboard.type('placeholder@example.invalid');
      await page.keyboard.press('Tab');
      assert.equal(await page.locator(':focus').getAttribute('id'), 'contact-message');
      await page.keyboard.type('placeholder request');
      await page.keyboard.press('Tab');
      assert.equal(await page.locator(':focus').textContent(), 'Send');
      if (width === 375) {
        const failure = page.waitForResponse(r => r.url() === origin + '/api/contact' && r.status() === 503);
        await Promise.all([page.waitForURL(origin + '/api/contact', {waitUntil: 'domcontentloaded'}), page.keyboard.press('Enter')]);
        await failure;
        await page.goBack({waitUntil: 'networkidle'});
        assert.equal(await page.getByLabel('Name', {exact: true}).inputValue(), 'placeholder customer');
        await page.getByRole('button', {name: 'Send', exact: true}).focus();
        const accepted = page.waitForResponse(r => r.url() === origin + '/api/contact' && r.status() === 202);
        await page.keyboard.press('Enter');
        assert.deepEqual(await (await accepted).json(), {ok: true});
      }
      await context.close();
    }
    // Reuse the shipped mobile Lighthouse settings and performance threshold.
    const result = await quality.lighthouse(origin, ['/contact'], `http://127.0.0.1:${proxyPort}`);
    const score = result.scores.find(row => row.page === '/contact');
    const minimum = req('./lighthouserc.cjs').ci.assert.assertions['categories:performance'][1].minScore;
    assert.ok(score && score.scores.performance >= minimum, JSON.stringify(result));
    assert.equal(external.length, 0);
    assert.equal(submitted, 2);
    return {keyboard: true, labels: true, contrast: true, retry: true, performance: score.scores.performance, externalRequests: 0};
  } finally {
    await browser.close();
    await close(proxy);
    await close(server);
  }
}
proof().then(result => console.log(JSON.stringify(result))).catch(error => {console.error(error); process.exitCode = 1;});
