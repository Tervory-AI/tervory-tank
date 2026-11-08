// Production React and typed proposal client. Only HTTP/session transport is local;
// real issuer verification, Command confirmation, SQL, Hermes and worker stay intact.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {createServer} = require('node:http');
const {createRequire} = require('node:module');
const product = process.env.WORKSPACE_PRODUCT_SOURCE;
assert(product, 'WORKSPACE_PRODUCT_SOURCE must name the reviewed product checkout');
const base = path.join(product, 'workspace');
const local = createRequire(path.join(product, 'tests/browser/package.json'));
const {build} = local('esbuild');
const {chromium} = local('playwright');
const ts = require(path.join(base, 'node_modules/typescript'));
require.extensions['.ts'] = (module, filename) => module._compile(ts.transpileModule(fs.readFileSync(filename, 'utf8'), {compilerOptions: {module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022}}).outputText, filename);
const {normalizeSnapshot} = require(path.join(base, 'app/chats/contract.ts'));
const {presentSnapshot, presentCard} = require(path.join(base, 'app/chats/presentation.ts'));
const signed = JSON.parse(process.env.WORKSPACE_BROWSER_HEADERS);
const upstream = process.env.WORKSPACE_BROWSER_BACKEND;
async function backend(target, init = {}) {
  const response = await fetch(upstream + target, {...init, headers: {...signed, 'content-type': 'application/json'}, signal: AbortSignal.timeout(15000)});
  if (globalThis.dropChatAfterPayment && target === '/v1/command/workspace/chat') {await response.arrayBuffer(); return new Response('{}', {status: 503});}
  return response;
}
(async () => {
 const bundle = await build({stdin: {contents: `import React from 'react';import {createRoot} from 'react-dom/client';import Tasks from './app/tasks/page';import {CommandWindow} from './app/chats/window';createRoot(document.getElementById('root')).render(location.pathname==='/tasks'?<Tasks/>:<CommandWindow initialThreads={[]} models={[]} founder={false} account="Workspace"/>);`, resolveDir: base, loader: 'tsx'}, bundle: true, write: false, jsx: 'automatic', outfile: '/tmp/workspace-browser.js', loader: {'.svg': 'file'}, define: {'process.env.NODE_ENV': '"production"'}, plugins: [{name: 'navigation-edge', setup(b) {b.onResolve({filter: /^next\/navigation$/}, () => ({path: 'navigation', namespace: 'edge'})); b.onLoad({filter: /.*/, namespace: 'edge'}, () => ({contents: 'export function usePathname(){return location.pathname}', loader: 'js'}));}}]});
 const proposal = await build({entryPoints: [path.join(base, 'lib/workspace-gates.ts')], bundle: true, write: false, platform: 'node', format: 'cjs', plugins: [{name: 'http-edge', setup(b) {
  b.onResolve({filter: /^server-only$/}, () => ({path: 'empty', namespace: 'edge'}));
  b.onResolve({filter: /^@\/lib\/tank$/}, () => ({path: 'tank', namespace: 'edge'}));
  b.onLoad({filter: /.*/, namespace: 'edge'}, args => ({contents: args.path === 'empty' ? '' : `export const COMMAND_LIMITS={bodyMs:15000};export const commandRequest=(_identity,target,init)=>globalThis.workspaceBackend('/v1/command/'+target,init);export async function boundedFetch(url,init,_ms,read){return read(await globalThis.workspaceBackend(new URL(url).pathname,init));}`, loader: 'js'}));
 }}]});
 globalThis.workspaceBackend = backend;
 const compiled = new module.constructor(); compiled.paths = module.paths; compiled._compile(proposal.outputFiles[0].text, '/tmp/workspace-proposal.cjs');
 const gates = compiled.exports;
 const resources = new Map(bundle.outputFiles.map(file => ['/' + path.basename(file.path), file.contents]));
 const css = fs.readFileSync(path.join(base, 'app/globals.css'), 'utf8') + '\n' + new TextDecoder().decode(resources.get('/workspace-browser.css'));
 const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>body{margin:0}${css}</style></head><body><div class="app-shell product"><div class="shell-main"><main id="root"></main></div></div><script src="/workspace-browser.js"></script></body></html>`;
 const server = createServer(async (req, res) => {
  try {
   const url = new URL(req.url, 'http://localhost');
   const json = (data, status = 200) => {res.statusCode = status; res.setHeader('content-type', 'application/json'); res.end(JSON.stringify(data));};
   if (resources.has(url.pathname)) {res.setHeader('content-type', url.pathname.endsWith('.svg') ? 'image/svg+xml' : 'text/javascript'); res.end(resources.get(url.pathname)); return;}
   if (url.pathname.startsWith('/brand/') || url.pathname.startsWith('/fonts/')) {res.end(fs.readFileSync(path.join(base, url.pathname.startsWith('/brand/') ? 'public' : 'app', url.pathname))); return;}
   const chunks = []; for await (const chunk of req) chunks.push(chunk);
   const body = Buffer.concat(chunks).toString();
   if (url.pathname === '/api/tasks') {
    if (req.method === 'GET') return json(await gates.listTasksWithMemory(process.env.WORKSPACE_BROWSER_TENANT, process.env.WORKSPACE_BROWSER_USER));
    const args = JSON.parse(body);
    return json(await gates.createTaskWithMemory(process.env.WORKSPACE_BROWSER_TENANT, process.env.WORKSPACE_BROWSER_USER, args.title, args.task_type, args.request), 202);
   }
   if (!url.pathname.startsWith('/chats/api/')) {res.setHeader('content-type', 'text/html'); res.end(html); return;}
   const target = url.pathname.slice('/chats/api/'.length);
   const response = await backend('/v1/command/' + target + url.search, {method: req.method, ...(body ? {body} : {})});
   if (response.headers.get('content-type')?.includes('text/event-stream')) {res.setHeader('content-type', 'text/event-stream'); res.end(await response.text()); return;}
   const data = await response.json();
   if (!response.ok) return json(data, response.status);
   if (/^threads\/[^/]+$/.test(target) && req.method === 'GET') return json(presentSnapshot(normalizeSnapshot(data), false));
   if (target.startsWith('cards/')) return json(presentCard(data, false));
   return json(data);
  } catch (error) {res.statusCode = 500; res.end(JSON.stringify({error: error.name}));}
 });
 await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
 const origin = `http://127.0.0.1:${server.address().port}`;
 const browser = await chromium.launch({headless: true, args: ['--no-sandbox']});
 const page = await browser.newPage({viewport: {width: 375, height: 812}});
 page.setDefaultTimeout(12000);
 const output = process.env.WORKSPACE_BROWSER_OUTPUT;
 if (output) fs.mkdirSync(output, {recursive: true});
 const errors = []; page.on('pageerror', e => errors.push(e.name));
 async function state() {return (await backend('/fixture/workspace/state')).json();}
 async function control(tool, args, expected) {
  const threadResponse = await backend('/v1/command/threads', {method: 'POST', body: '{}'});
  assert.equal(threadResponse.status, 200);
  const {thread_id} = await threadResponse.json();
  await page.goto(`${origin}/chats?thread=${thread_id}`);
  await page.getByRole('textbox', {name: 'Message Tervory'}).fill(tool + ' ' + JSON.stringify(args));
  await page.getByRole('button', {name: 'Send', exact: true}).click();
  await page.getByRole('button', {name: 'Confirm', exact: true}).click();
  await page.getByText(expected, {exact: true}).first().waitFor();
  if (output) await page.screenshot({path: path.join(output, tool.replaceAll('.', '-') + '-' + expected.replace(/[^a-z0-9]/gi, '_') + '.png')});
 }
 try {
  await page.goto(origin + '/tasks');
  await page.getByText('Add a task to fill this board.', {exact: true}).waitFor();
  await page.getByLabel('Title', {exact: true}).fill('placeholder browser task');
  await page.getByLabel('What you need', {exact: true}).fill('placeholder browser request');
  await page.getByRole('button', {name: 'Add task', exact: true}).click();
  await page.waitForURL('**/chats?thread=*');
  await page.getByRole('button', {name: 'Confirm', exact: true}).waitFor();
  assert.equal((await state()).provider_calls, 0);
  // Keyboard confirmation, same approved card, no automatic confirmation.
  await page.getByRole('button', {name: 'Confirm', exact: true}).focus(); await page.keyboard.press('Enter');
  await page.getByText('CONFIRMED', {exact: true}).waitFor();
  await page.goto(origin + '/tasks');
  await page.locator('article.card.done').filter({hasText: 'placeholder browser task'}).waitFor();
  let observed = await state(); assert.equal(observed.provider_calls, 1); assert.equal(observed.done_tasks, 1);
  assert(observed.paid_receipts.some(row => row.tokens_in === 10 && row.tokens_out === 3 && Number(row.cost_usd) === .013));
  const taskMemory = observed.memories.find(row => row.kind === 'workspace.receipt'); assert(taskMemory);
  await control('workspace.memory.view', {memory_id: taskMemory.id}, 'CONFIRMED');
  await page.getByText(/placeholder browser request/).first().waitFor();
  await control('workspace.memory.edit', {memory_id: taskMemory.id, text: 'placeholder browser corrected answer'}, 'placeholder browser corrected answer');
  await control('workspace.memory.forget', {memory_id: taskMemory.id}, 'true');
  await page.goto(origin + '/tasks'); await page.locator('article.card.done').filter({hasText: 'placeholder browser task'}).waitFor();
  assert(!(await state()).memories.some(row => row.id === taskMemory.id), 'Board polling must not resurrect forgotten completed-task memory');
  await control('workspace.memory.view', {}, '0 items');
  await backend('/fixture/workspace/fault', {method: 'POST', body: JSON.stringify({method: 'GET', path: '/records', status: 503})});
  await control('workspace.memory.view', {}, 'FAILED');
  assert.equal((await state()).provider_calls, 1);
  await backend('/fixture/workspace/fault', {method: 'POST', body: JSON.stringify({method: null, path: null, status: 503})});
  await control('workspace.memory.view', {}, '0 items');
  await control('workspace.memory.control', {control: 'off'}, 'off');
  await control('workspace.memory.view', {}, 'off');
  assert.equal((await state()).provider_calls, 1);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  globalThis.dropChatAfterPayment = true;
  await assert.rejects(gates.chatWithMemory(process.env.WORKSPACE_BROWSER_TENANT, process.env.WORKSPACE_BROWSER_USER, [{role: 'user', content: 'placeholder uncertain chat'}]), error => error.status === 503);
  assert.equal((await state()).provider_calls, 2, 'A lost post-payment response must never cause a second dispatch');
  assert.deepEqual(errors, []);
  console.log('Workspace browser passed: real task proposal/keyboard Confirm/worker/paid receipt; personal view/edit/forget; durable forget after board poll; empty/error/retry/off; mobile; no paid retry.');
 } finally {await browser.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve));}
})().catch(error => {console.error(error); process.exitCode = 1;});
