// Offline rendering of snapshots saved by test_confirmed_read_saved_replayed_and_isolated.
// Real CommandWindow/presentation; replayed HTTP responses. Never a live GitHub proof.
const {createServer} = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '../..');
const base = path.join(root, 'workspace');
const tools = process.env.COMMAND_TEST_TOOLS || '/tmp/command-repo-browser/node_modules';
const {build} = require(path.join(tools, 'esbuild'));
const {chromium} = require(path.join(tools, 'playwright'));
const ts = require(path.join(base, 'node_modules/typescript'));
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
  compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022},
}).outputText, filename);
const {normalizeSnapshot} = require('../../workspace/app/chats/contract.ts');
const {presentSnapshot, presentCard} = require('../../workspace/app/chats/presentation.ts');
const snapshot = process.env.COMMAND_REPO_SNAPSHOT || '/tmp/command-repo-snapshot.json';
const saved = JSON.parse(fs.readFileSync(snapshot, 'utf8'));
const pending = JSON.parse(fs.readFileSync(snapshot + '.pending', 'utf8'));
const question = 'which PRs are open and are their checks green?';
assert.equal(saved.messages[0].content, question);
assert.equal(saved.cards[0].result.items[0].checks_green, true);
let state = pending, confirmations = 0;

(async () => {
  const bundle = await build({stdin: {
    contents: `import React from 'react'; import {createRoot} from 'react-dom/client'; import {CommandWindow} from './app/chats/window'; createRoot(document.getElementById('root')).render(<CommandWindow initialThreads={${JSON.stringify([saved.thread])}} models={[]} founder={true} account="Tervory · Boston · USD"/>);`,
    resolveDir: base, loader: 'tsx',
  }, bundle: true, write: false, jsx: 'automatic', outfile: '/tmp/command-repo-browser.js', loader: {'.svg': 'file'},
  assetNames: '[name]', define: {'process.env.NODE_ENV': '"production"'}, plugins: [{name: 'local-navigation', setup(builder) {
    builder.onResolve({filter: /^next\/navigation$/}, () => ({path: 'navigation', namespace: 'offline'}));
    builder.onLoad({filter: /.*/, namespace: 'offline'}, () => ({contents: 'export function usePathname(){return location.pathname}', loader: 'jsx', resolveDir: base}));
  }}]});
  const resources = new Map(bundle.outputFiles.map(file => ['/' + path.basename(file.path), file.contents]));
  const css = fs.readFileSync(path.join(base, 'app/globals.css'), 'utf8') + '\n' + new TextDecoder().decode(resources.get('/command-repo-browser.css'));
  const html = `<!doctype html><html><head><style>@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}@font-face{font-family:Mono;src:url('/fonts/JetBrainsMono-latin.woff2')}body{margin:0;--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}${css}</style></head><body><div class="app-shell product"><div class="shell-main"><main id="root"></main></div></div><script src="/command-repo-browser.js"></script></body></html>`;
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost');
    const json = body => {res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(body));};
    if (resources.has(url.pathname)) {res.setHeader('content-type', url.pathname.endsWith('.svg') ? 'image/svg+xml' : 'text/javascript'); return res.end(resources.get(url.pathname));}
    if (/^\/(fonts|brand)\/[A-Za-z0-9_.-]+$/.test(url.pathname)) {
      const filename = path.join(base, 'public', url.pathname);
      if (fs.existsSync(filename)) return res.end(fs.readFileSync(filename));
    }
    if (url.pathname === '/chats') {res.setHeader('content-type', 'text/html'); return res.end(html);}
    if (url.pathname === '/chats/api/threads') return json([state.thread]);
    if (url.pathname === `/chats/api/threads/${saved.thread.thread_id}`) return json(presentSnapshot(normalizeSnapshot(state), true));
    if (url.pathname === `/chats/api/cards/${saved.cards[0].card_id}` && req.method === 'POST') {
      let body = ''; for await (const chunk of req) body += chunk;
      assert.deepEqual(JSON.parse(body), {action: 'confirm'});
      confirmations++; state = saved;
      return json(presentCard(saved.cards[0], true));
    }
    res.statusCode = 404; res.end();
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({executablePath: process.env.CHROMIUM_EXECUTABLE || '/usr/bin/chromium', headless: true, args: ['--no-sandbox']});
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 1400}});
    const errors = [], external = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/*', route => {
      if (new URL(route.request().url()).hostname === '127.0.0.1') return route.continue();
      external.push(route.request().url()); return route.abort();
    });
    const url = `http://127.0.0.1:${server.address().port}/chats?thread=${saved.thread.thread_id}`;
    await page.goto(url);
    await page.getByRole('button', {name: 'Confirm', exact: true}).waitFor();
    assert.equal(confirmations, 0);
    assert.equal(await page.getByText('checks_green', {exact: false}).count(), 0);
    await page.getByRole('button', {name: 'Confirm', exact: true}).click();
    const result = page.locator('.cw-card-details dd').filter({hasText: '"checks_green": true'});
    await result.waitFor();
    const shown = await result.textContent();
    assert.deepEqual(JSON.parse(shown), JSON.parse(saved.cards[0].result.text));
    assert.equal(confirmations, 1);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({path: path.join(__dirname, 'offline-founder-result.png'), fullPage: true});
    await page.reload();
    await result.waitFor();
    assert.equal(confirmations, 1);
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    console.log('PASS: existing Confirm, complete PR/check result visible, reload persists, one confirmation, no browser errors or external requests. Screenshot is offline stub data only.');
  } finally {await browser.close(); await new Promise(resolve => server.close(resolve));}
})().catch(error => {console.error(error); process.exitCode = 1;});
