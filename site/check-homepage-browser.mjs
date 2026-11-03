// Uses an existing Playwright installation; adds no runtime/build dependency.
// Run against an isolated preview store, never the production signup store.
import assert from "node:assert/strict";
import { mkdir, readFile, stat } from "node:fs/promises";
import { pathToFileURL } from "node:url";

const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_MODULE).href);
const browser = await chromium.launch({ executablePath: process.env.BROWSER_EXECUTABLE, headless: true, args: ["--no-sandbox"] });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: "reduce", acceptDownloads: true });
const page = await context.newPage();
const url = process.env.HOMEPAGE_URL || "http://127.0.0.1:8916";
const output = process.env.SCREENSHOT_DIR || "/dev/shm/tervory-homepage-proof";
const errors = [];
const posts = [];
page.on("pageerror", error => errors.push(error.message));
page.on("request", request => { if (request.method() === "POST") posts.push(request.url()); });
await mkdir(output, { recursive: true });
try {
  await page.goto(url, { waitUntil: "networkidle" });
  await page.evaluate(() => document.fonts.ready);
  // Scroll like a reader so native lazy images load before visual comparison.
  await page.locator("img").evaluateAll(async images => {
    for (const image of images) { image.loading = "eager"; }
    await Promise.all(images.map(image => image.decode()));
  });
  assert.equal(await page.locator("h1").count(), 1);
  assert.equal(await page.locator(".squad-row").count(), 10);
  const assets = await page.locator("img").evaluateAll(images => images.map(image => {
    const box = image.getBoundingClientRect();
    return { src: image.getAttribute("src"), loaded: image.complete && image.naturalWidth > 0, width: box.width, height: box.height };
  }));
  for (const asset of assets) {
    assert(asset.loaded && asset.width > 0 && asset.height > 0, `Missing image ${asset.src}`);
    assert((await stat(`public${asset.src}`)).size > 0);
  }
  for (let index = 0; index < 5; index++) {
    const tab = page.getByRole("tablist", { name: "Tank stages" }).getByRole("tab").nth(index);
    await tab.click();
    assert.equal(await tab.getAttribute("aria-selected"), "true");
    assert.equal(await page.locator(".engine-node.active .stage-number").textContent(), String(index + 1));
    assert((await page.locator(".engine-inspector h3").textContent()).length > 5);
  }
  const firstTab = page.getByRole("tablist", { name: "Tank stages" }).getByRole("tab").first();
  await firstTab.click();
  await firstTab.focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.locator(".engine-node.active .stage-number").textContent(), "2");
  await page.keyboard.press("Home");
  assert.equal(await firstTab.getAttribute("aria-selected"), "true");
  const rig = page.locator("#rig");
  for (const label of ["Pair accessories", "Search the market", "Beat or match", "Get A Quote"]) {
    await rig.getByRole("button", { name: label, exact: true }).click();
  }
  assert.match(await rig.locator(".rig-controls").textContent(), /\$151/);
  assert.equal(await rig.locator(".rig-price strong").textContent(), "$94");
  await rig.getByRole("button", { name: "Accept & pay", exact: true }).click();
  assert.equal(await rig.locator(".rig-price strong").textContent(), "$104");
  for (const control of await rig.getByRole("switch").all()) {
    assert.equal(await control.getAttribute("aria-checked"), "false");
    await control.click();
    assert.equal(await control.getAttribute("aria-checked"), "true");
    await control.press("Space");
    assert.equal(await control.getAttribute("aria-checked"), "false");
  }
  assert.equal(posts.length, 0, "Illustration controls must never call a model, payment or store API");
  const receipts = page.locator(".receipt-example");
  await receipts.getByRole("tab", { name: "Per-call receipt", exact: true }).click();
  assert.equal(await receipts.locator("tbody tr").count(), 4);
  const downloadPromise = page.waitForEvent("download");
  await receipts.getByRole("button", { name: "Export CSV", exact: true }).click();
  const download = await downloadPromise;
  await download.saveAs(`${output}/receipt.csv`);
  const csv = await readFile(`${output}/receipt.csv`, "utf8");
  assert.match(csv, /ledger_id/);
  assert.match(csv, /led_7f3a94/);
  assert.equal(csv.split("\r\n").length, 5);
  await page.evaluate(() => { window.__printCalled = false; window.print = () => { window.__printCalled = true; }; });
  await receipts.getByRole("button", { name: "Export PDF", exact: true }).click();
  assert.equal(await page.evaluate(() => window.__printCalled), true);
  await page.pdf({ path: `${output}/receipt.pdf`, printBackground: true, preferCSSPageSize: true });
  assert((await stat(`${output}/receipt.pdf`)).size > 1000);
  await receipts.getByRole("tab", { name: "What you saved", exact: true }).click();
  for (const width of [320, 375, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    assert.equal(await page.evaluate(() => document.body.scrollWidth <= innerWidth), true, `Page overflow at ${width}`);
    const badgeFits = await page.locator(".receipt-tabs").evaluate(tabs => {
      const bounds = tabs.getBoundingClientRect();
      return [...tabs.children].every(child => {
        const box = child.getBoundingClientRect();
        return box.left >= bounds.left - 1 && box.right <= bounds.right + 1;
      });
    });
    assert(badgeFits, `Receipt tab or Example badge clips at ${width}`);
    await page.screenshot({ path: `${output}/homepage-${width}.png`, fullPage: true });
  }
  // Check both real form instances against the preview-only signup file.
  for (const form of await page.locator("form.release").all()) {
    await form.locator('input[type="email"]').fill("homepage-browser-check@example.com");
    await form.getByRole("button").click();
    await form.getByRole("status").filter({ hasText: "Saved." }).waitFor();
  }
  // Exercise the existing failure state without changing production data.
  await page.route("**/api/release-notice", route => route.fulfill({ status: 503, contentType: "application/json", body: '{"stored":false}' }));
  const form = page.locator("form.release").first();
  await form.getByRole("button").click();
  await form.getByRole("status").filter({ hasText: "That address was not saved. Try again." }).waitFor();
  const autoPage = await context.newPage();
  await autoPage.emulateMedia({ reducedMotion: "no-preference" });
  await autoPage.goto(url);
  await autoPage.waitForFunction(() => document.querySelector(".engine-node.active .stage-number")?.textContent === "2", { timeout: 10000 });
  assert.match(await autoPage.locator(".rig-caption").textContent(), /pairing the accessories/);
  await autoPage.close();
  assert.equal(errors.length, 0, errors.join("\n"));
  console.log(JSON.stringify({ result: "PASS", widths: [320, 375, 768, 1440], images: assets.length, engineStages: 5, rigStates: 5, switches: 5, receiptRows: 4, csv: "PASS", pdf: "PASS", forms: "saved + failed", javascriptErrors: errors, screenshotDirectory: output }, null, 2));
} finally {
  await browser.close();
}
