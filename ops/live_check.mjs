// Signed-out, read-only page checks. Never loads a login or provider credential.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire, stripTypeScriptTypes} from 'node:module';
import {parseArgs} from 'node:util';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const {values} = parseArgs({options: {
  output: {type: 'string', default: 'live-check-results'},
  'local-urls': {type: 'string'},
  'timeout-ms': {type: 'string', default: '30000'},
}});
const timeout = Number(values['timeout-ms']);
if (!Number.isInteger(timeout) || timeout < 1 || timeout > 30000) {
  throw new Error('Navigation timeout must be between 1 and 30000 milliseconds');
}
const out = path.resolve(values.output);
await fs.mkdir(out, {recursive: true});
const source = await fs.readFile(path.join(root, 'workspace/lib/product-hosts.ts'), 'utf8');
const hosts = await import(`data:text/javascript;base64,${Buffer.from(stripTypeScriptTypes(source)).toString('base64')}`);
let targets = [...new Set([hosts.APP_WORKSPACE_HOST,
  ...hosts.WORKSPACE_PRODUCT_HOSTS.map(row => row.host), 'rig.tervory.com'])]
  .map(host => ({host, url: `https://${host}/`}));
// Offline tests only: a test cannot silently replace the production host roster.
if (values['local-urls']) {
  const urls = JSON.parse(await fs.readFile(values['local-urls'], 'utf8'));
  if (!Array.isArray(urls) || !urls.length) throw new Error('Local URLs must be a nonempty list');
  targets = urls.map((url, i) => {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' || parsed.hostname !== '127.0.0.1' || parsed.username || parsed.password) {
      throw new Error('Offline targets must use http://127.0.0.1');
    }
    return {host: `local-${i}`, url};
  });
}
const banned = (await fs.readFile(path.join(root, 'ops/live_check_banned.txt'), 'utf8'))
  .split(/\r?\n/).map(line => line.trim()).filter(line => line && !line.startsWith('#'));
if (!banned.length) throw new Error('The banned text list is empty');
const require = createRequire(path.join(root, 'workspace/package.json'));
const {chromium} = require(process.env.LIVE_CHECK_PLAYWRIGHT_PATH || 'playwright');
const browser = await chromium.launch({headless: true, executablePath: process.env.LIVE_CHECK_CHROMIUM});
const results = [];
try {
  for (const target of targets) {
    const result = {host: target.host, passed: true, viewports: []};
    for (const width of [1440, 375]) {
      // New context per host AND viewport: no shared cookies, login, cache or storage.
      const context = await browser.newContext({viewport: {width, height: 900}, serviceWorkers: 'block'});
      const page = await context.newPage();
      const reasons = new Set();
      const row = {width, status: null, reasons: [], screenshot: null};
      page.on('pageerror', () => reasons.add('Uncaught browser exception'));
      page.on('crash', () => reasons.add('Browser page crashed'));
      page.on('console', message => {
        if (message.type() === 'error' && /uncaught|unhandled(?:\s+promise)?(?:\s+rejection)?/i.test(message.text())) {
          reasons.add('Uncaught console exception');
        }
      });
      page.on('response', response => {
        if (response.status() >= 500) reasons.add(`HTTP ${response.status()}`);
      });
      try {
        const response = await page.goto(target.url, {waitUntil: 'load', timeout});
        row.status = response?.status() ?? null;
        // Observe hydration / deferred runtime errors after load without waiting for
        // networkidle (analytics and long polling do not mean the page is broken).
        await page.waitForTimeout(2000);
      } catch (error) {
        reasons.add(error.name === 'TimeoutError' ? `Page did not load within ${timeout}ms` : 'Page navigation failed');
      }
      try {
        const text = await page.locator('body').innerText({timeout: 5000});
        for (const marker of ['Application error', 'client-side exception', ...banned]) {
          if (text.toLowerCase().includes(marker.toLowerCase())) reasons.add(`Visible text: ${marker}`);
        }
      } catch {
        reasons.add('Visible page text could not be read');
      }
      try {
        const filename = `${target.host}-${width}.png`;
        await page.screenshot({path: path.join(out, filename), fullPage: true, timeout: 10000});
        row.screenshot = filename;
      } catch {
        reasons.add('Screenshot could not be saved');
      }
      row.reasons = [...reasons];
      if (row.reasons.length) result.passed = false;
      result.viewports.push(row);
      await context.close();
    }
    results.push(result);
    // Checkpoint after every host, preserving proof if a later host crashes.
    await fs.writeFile(path.join(out, 'results.json'), JSON.stringify(results, null, 2) + '\n');
    const reason = [...new Set(result.viewports.flatMap(row => row.reasons))].join('; ');
    console.log(`${result.passed ? 'PASS' : 'FAIL'} ${result.host}${reason ? ': ' + reason : ''}`);
  }
} finally {
  await browser.close();
}
const summary = ['# Signed-out live page check', '',
  'Signed-in checks skipped: step 2 awaits founder-provided LIVE_CHECK_EMAIL and LIVE_CHECK_PASSWORD.', '',
  '| Host | Result | Reason | Screenshots |', '| --- | --- | --- | --- |'];
for (const result of results) {
  const reasons = [...new Set(result.viewports.flatMap(row => row.reasons))].join('; ') || 'Loaded without a detected failure';
  const shots = result.viewports.map(row => row.screenshot ? `[${row.width}px](${row.screenshot})` : `${row.width}px unavailable`).join(', ');
  summary.push(`| ${result.host} | ${result.passed ? 'PASS' : 'FAIL'} | ${reasons.replaceAll('|', '\\|')} | ${shots} |`);
}
await fs.writeFile(path.join(out, 'summary.md'), summary.join('\n') + '\n');
console.log('NOTICE: Signed-in checks skipped; step 2 awaits founder-provided settings.');
process.exitCode = results.some(result => !result.passed) ? 1 : 0;
