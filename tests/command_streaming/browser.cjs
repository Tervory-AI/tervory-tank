// Local proof: unchanged UI design + actual Workspace proxy + local Tank.
// Authentication is a test identity; Python stubs only the model transport.
const {createServer} = require('node:http');
const {Readable} = require('node:stream');
const {pipeline} = require('node:stream/promises');
const fs = require('node:fs');
const path = require('node:path');
const Module = require('node:module');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const base = path.join(root, 'workspace');
const tools = process.env.COMMAND_TEST_TOOLS;
const {build} = require(path.join(tools, 'esbuild'));
const {chromium} = require(path.join(tools, 'playwright'));
const ts = require(path.join(base, 'node_modules/typescript'));
const originalResolve = Module._resolveFilename;
Module._resolveFilename = function(name, parent, ...rest) {
  if (name.startsWith('@/')) name = path.join(base, name.slice(2));
  return originalResolve.call(this, name, parent, ...rest);
};
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true},
}).outputText, filename);
function mock(filename, exports) {
  const resolved = path.join(base, filename);
  require.cache[resolved] = {id: resolved, filename: resolved, loaded: true, exports};
}
const identity = {tenantId: '00000000-0000-0000-0000-000000000011', userId: 'founder'};
mock('lib/tenant.ts', {activeTenant: async () => identity});
mock('lib/admin.ts', {isFounder: () => true});
// Inert test marker; never a production credential, never sent to the browser.
process.env.TANK_API_KEY = 'dummy-workspace-key';
const {commandRequest} = require('../../workspace/lib/tank.ts');
const handlers = require('../../workspace/app/chats/api/[...path]/route.ts');
const threadId = process.env.COMMAND_STREAMING_THREAD;
const mode = process.env.COMMAND_STREAMING_MODE;
const completeText = 'Hello world.\nA 😀 answer.';

(async () => {
  const saved = await (await commandRequest(identity, `threads/${threadId}`)).json();
  const bundle = await build({stdin: {
    contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import {CommandWindow} from './app/chats/window'; createRoot(document.getElementById('root')).render(<CommandWindow initialThreads={${JSON.stringify([saved.thread])}} models={[]} founder={true} account="Tervory · Boston · USD"/>);`,
    resolveDir: base, loader: 'tsx',
  }, bundle: true, write: false, jsx: 'automatic', outfile: '/tmp/command-streaming-browser.js', loader: {'.svg': 'file'},
  assetNames: '[name]', define: {'process.env.NODE_ENV': '"production"'}, plugins: [{name: 'local-navigation', setup(builder) {
    builder.onResolve({filter: /^next\/navigation$/}, () => ({path: 'navigation', namespace: 'offline'}));
    builder.onLoad({filter: /.*/, namespace: 'offline'}, () => ({contents: 'export function usePathname(){return location.pathname}', loader: 'jsx', resolveDir: base}));
  }}]});
  const resources = new Map(bundle.outputFiles.map(file => ['/' + path.basename(file.path), file.contents]));
  const css = fs.readFileSync(path.join(base, 'app/globals.css'), 'utf8') + '\n' + new TextDecoder().decode(resources.get('/command-streaming-browser.css'));
  const html = `<!doctype html><html><head><style>@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}body{margin:0;--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}${css}</style></head><body><div class="app-shell product"><div class="shell-main"><main id="root"></main></div></div><script src="/command-streaming-browser.js"></script></body></html>`;
  const serverErrors = [];
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, `http://${req.headers.host}`);
    try {
      if (url.pathname.startsWith('/chats/api/')) {
        const cancelled = new AbortController();
        res.on('close', () => {if (!res.writableFinished) cancelled.abort();});
        let body = ''; for await (const chunk of req) body += chunk;
        const request = new Request(url, {method: req.method, headers: req.headers, ...(body ? {body} : {}), signal: cancelled.signal});
        const response = await handlers[req.method](request, {params: Promise.resolve({path: url.pathname.slice('/chats/api/'.length).split('/')})});
        res.writeHead(response.status, Object.fromEntries(response.headers)); res.flushHeaders();
        if (response.body) await pipeline(Readable.fromWeb(response.body), res);
        else res.end();
        return;
      }
      if (resources.has(url.pathname)) {res.setHeader('content-type', url.pathname.endsWith('.svg') ? 'image/svg+xml' : 'text/javascript'); return res.end(resources.get(url.pathname));}
      if (/^\/(fonts|brand)\/[A-Za-z0-9_.-]+$/.test(url.pathname)) {
        const filename = path.join(base, 'public', url.pathname);
        if (fs.existsSync(filename)) return res.end(fs.readFileSync(filename));
      }
      if (url.pathname === '/chats') {res.setHeader('content-type', 'text/html'); return res.end(html);}
      res.statusCode = 404; res.end();
    } catch (error) {
      if (!res.destroyed) {serverErrors.push(error.message); res.destroy();}
    }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({executablePath: '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1000}});
    const errors = [], external = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      if (new URL(route.request().url()).hostname === '127.0.0.1') return route.continue();
      external.push(route.request().url()); return route.abort();
    });
    await page.goto(`http://127.0.0.1:${server.address().port}/chats?thread=${threadId}`);
    await page.getByRole('textbox', {name: 'Message Tervory'}).fill('Hello');
    await page.getByRole('button', {name: 'Send', exact: true}).click();
    const answer = page.locator('.cw-assistant .cw-message-text');
    await page.waitForFunction(() => document.querySelector('.cw-assistant .cw-message-text')?.textContent === 'Hello');
    assert.equal(await page.getByRole('button', {name: 'Sending…', exact: true}).count(), 1);
    assert.equal(await page.locator('.cw-receipt').count(), 0);
    assert(await page.getByText('Preparing answer', {exact: true}).isVisible());
    if (mode === 'complete') {
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({path: path.join(__dirname, 'offline-streaming.png')});
    }
    if (mode === 'broken_refresh') await page.route(`**/chats/api/threads/${threadId}`, route => route.abort());
    console.log('PROVISIONAL'); // Python now checks storage before releasing the model.
    if (mode === 'disconnect') {
      await page.close();
    } else if (mode === 'complete') {
      await page.waitForFunction(expected => document.querySelector('.cw-assistant .cw-message-text')?.textContent === expected, completeText);
      await page.getByText('Answer ready', {exact: true}).waitFor();
      await page.locator('.cw-receipt').waitFor();
      await page.getByRole('button', {name: 'Sending…', exact: true}).waitFor({state: 'hidden'});
      assert.equal(await answer.textContent(), completeText);
      assert((await page.locator('.cw-receipt').textContent()).includes('$0.002400'));
      assert.equal(await page.locator('.cw-confirm').count(), 0);
      await page.screenshot({path: path.join(__dirname, 'offline-complete.png')});
      await page.reload();
      await page.locator('.cw-receipt').waitFor();
      assert.equal(await answer.textContent(), completeText);
      assert.equal(await page.locator('.cw-receipt').count(), 1);
    } else {
      await page.getByRole('alert').waitFor();
      assert.equal(await page.getByRole('alert').textContent(), 'The answer could not be completed. Check routing policy and service availability.Reload');
      await page.waitForFunction(() => document.querySelectorAll('.cw-assistant .cw-message-text').length === 0);
      if (mode === 'broken') await page.screenshot({path: path.join(__dirname, 'offline-broken.png')});
    }
    assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.deepEqual(serverErrors, []);
    console.log(`PASS: ${mode}; real CommandWindow, Workspace proxy and Tank; no external browser requests or new UI wording.`);
  } finally {await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve));}
})().catch(error => {console.error(error); process.exitCode = 1;});
