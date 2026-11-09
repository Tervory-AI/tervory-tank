// Signed-in page checks for every product page a user reaches.
// Signs in once as the check account (LIVE_CHECK_EMAIL / LIVE_CHECK_PASSWORD, repo
// secrets, never printed), then opens each page in ops/signed_in_pages.json and runs
// ops/page_content_check.js on it. Writes results.json, summary.md and a screenshot
// for every failed page. --signed-out runs the same content checks without signing in.
import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {parseArgs} from 'node:util';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const {values} = parseArgs({options: {
  output: {type: 'string', default: 'signed-in-check-results'},
  pages: {type: 'string', default: path.join(root, 'ops/signed_in_pages.json')},
  'signed-out': {type: 'boolean', default: false},
}});
const out = path.resolve(values.output);
await fs.mkdir(out, {recursive: true});
const config = JSON.parse(await fs.readFile(values.pages, 'utf8'));
const check = (await fs.readFile(path.join(root, 'ops/page_content_check.js'), 'utf8')).trim();
const email = process.env.LIVE_CHECK_EMAIL || '';
const password = process.env.LIVE_CHECK_PASSWORD || '';
const signedOut = values['signed-out'];
const results = [];
const save = () => fs.writeFile(path.join(out, 'results.json'), JSON.stringify(results, null, 2) + '\n');

const require = createRequire(path.join(root, 'workspace/package.json'));
const {chromium} = require(process.env.LIVE_CHECK_PLAYWRIGHT_PATH || 'playwright');
const browser = await chromium.launch({headless: true, executablePath: process.env.LIVE_CHECK_CHROMIUM || undefined});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, serviceWorkers: 'block'});
context.setDefaultTimeout(30000);

const isSignIn = (url) => {
  const u = new URL(url);
  return u.hostname === 'auth.tervory.com' || u.pathname.startsWith('/sign-in');
};

async function inspect(page, id, url, status, failed, extra = {}) {
  const reasons = await page.evaluate(`(${check})(${JSON.stringify({status, failedRequests: [...failed], ...extra})})`)
    .catch(() => ['Page content could not be read']);
  return record(page, id, url, reasons);
}

async function record(page, id, url, reasons) {
  const row = {id, url, landed: page.url().split('?')[0], passed: reasons.length === 0, reasons, screenshot: null};
  if (!row.passed) {
    row.screenshot = `${id}.png`;
    await page.screenshot({path: path.join(out, row.screenshot), fullPage: true, timeout: 10000})
      .catch(() => { row.screenshot = null; });
  }
  results.push(row);
  await save();
  console.log(`${row.passed ? 'PASS' : 'FAIL'} ${id}${row.passed ? '' : ': ' + reasons.join('; ')}`);
  return row;
}

async function open(page, url) {
  const failed = new Set();
  const host = new URL(url).hostname.split('.').slice(-2).join('.');
  const watch = (response) => {
    if (response.status() >= 500 && new URL(response.url()).hostname.endsWith(host)) failed.add(response.status());
  };
  page.on('response', watch);
  let status = 0;
  let error = null;
  try {
    status = (await page.goto(url, {waitUntil: 'load'}))?.status() ?? 0;
    await page.waitForTimeout(2500);
  } catch (caught) {
    // Keep the browser's error code only, never a raw message with URLs or headers.
    error = 'Page did not load: ' + (String(caught.message).match(/net::(ERR_[A-Z_]+)/)?.[1] ?? caught.name);
  }
  page.off('response', watch);
  return {status, failed, error};
}

// Trigger sign-in: the workspace button, then the hosted login (login name, password,
// and a "skip" on an optional prompt). Every sign-in screen is itself checked.
async function signIn(page, label) {
  const button = page.getByRole('button', {name: /continue to trigger sign-in/i});
  await button.click();
  await page.waitForLoadState('load');
  await inspect(page, `${label}-provider`, page.url().split('?')[0], 0, [], {signIn: true});
  const login = page.locator('input[name="loginName"], #loginName, input[type="email"], input[autocomplete="username"]').first();
  if (await login.isVisible().catch(() => false)) {
    await login.fill(email);
    await page.locator('#submit-button, button[type="submit"]').first().click();
  } else {
    await page.getByText(email, {exact: false}).first().click().catch(() => {});
  }
  const secret = page.locator('input[type="password"]').first();
  if (await secret.waitFor({state: 'visible', timeout: 15000}).then(() => true, () => false)) {
    await secret.fill(password);
    await page.locator('#submit-button, button[type="submit"]').first().click();
  }
  for (let step = 0; step < 3 && isSignIn(page.url()); step++) {
    const skip = page.getByRole('button', {name: /^(skip|not now|later)$/i});
    if (await skip.isVisible().catch(() => false)) await skip.click();
    await page.waitForTimeout(3000);
  }
  return !isSignIn(page.url());
}

try {
  let page = await context.newPage();
  if (!signedOut) {
    if (!email || !password) {
      await record(page, 'sign-in', config.signIn, ['Check account settings LIVE_CHECK_EMAIL and LIVE_CHECK_PASSWORD are not set']);
    } else {
      const first = await open(page, config.signIn);
      await inspect(page, 'sign-in', config.signIn, first.status, first.failed, {signIn: true});
      if (!(await signIn(page, 'sign-in').catch(() => false))) {
        await record(page, 'sign-in-complete', config.signIn, ['The check account could not finish signing in']);
      }
    }
  }
  const signedIn = !signedOut && results.every((row) => row.passed || row.id === 'sign-in-provider');
  for (const target of config.pages) {
    // A fresh tab per page: a failed load can never be checked against the last page.
    await page.close();
    page = await context.newPage();
    let {status, failed, error} = await open(page, target.url);
    // A product host keeps its own session: sign in there once, then reopen the page.
    if (signedIn && isSignIn(page.url())) {
      await signIn(page, `${target.id}-sign-in`).catch(() => false);
      ({status, failed, error} = await open(page, target.url));
    }
    if (error) {
      await record(page, target.id, target.url, [error]);
      continue;
    }
    if (!signedOut && isSignIn(page.url())) {
      await record(page, target.id, target.url, ['Page sent the signed-in check account back to sign-in']);
      continue;
    }
    if (target.click) {
      await page.getByRole('button', {name: target.click, exact: true}).first().click().catch(() => {});
      await page.waitForTimeout(1500);
    }
    await inspect(page, target.id, target.url, status, failed, {
      signIn: isSignIn(page.url()), expect: isSignIn(page.url()) ? [] : target.expect, required: target.required,
    });
  }
} finally {
  await browser.close();
}
const summary = [`# ${signedOut ? 'Signed-out' : 'Signed-in'} page content check`, '',
  '| Page | Result | Reason |', '| --- | --- | --- |',
  ...results.map((row) => `| ${row.id} | ${row.passed ? 'PASS' : 'FAIL'} | ${(row.reasons.join('; ') || 'Real content').replaceAll('|', '\\|')} |`)];
await fs.writeFile(path.join(out, 'summary.md'), summary.join('\n') + '\n');
process.exitCode = results.some((row) => !row.passed) ? 1 : 0;
