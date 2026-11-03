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
  assert.equal(await page.getByRole("link", { name:"Rig", exact:true }).getAttribute("href"), "/rig");
  const assets = await page.locator("img").evaluateAll(images => images.map(image => {
    const box = image.getBoundingClientRect();
    return { src: image.getAttribute("src"), loaded: image.complete && image.naturalWidth > 0, width: box.width, height: box.height };
  }));
  for (const asset of assets) {
    assert(asset.loaded && asset.width > 0 && asset.height > 0, `Missing image ${asset.src}`);
    assert((await stat(`public${asset.src}`)).size > 0);
  }
  assert.equal(await page.locator(".engine-options, .engine-inspector").count(), 0);
  const engineNodes = page.locator(".engine-node");
  for (let index = 0; index < 5; index++) {
    await engineNodes.nth(index).click();
    assert.equal(await engineNodes.nth(index).getAttribute("aria-pressed"), "true");
    assert.equal(await page.locator(".engine-node.active .stage-number").textContent(), String(index + 1));
  }
  await engineNodes.first().focus();
  await page.keyboard.press("ArrowDown");
  assert.equal(await engineNodes.nth(1).getAttribute("aria-pressed"), "true");
  await page.keyboard.press("Home");
  assert.equal(await engineNodes.first().getAttribute("aria-pressed"), "true");
  const rig = page.locator("#rig");
  for (const label of ["Pair accessories", "Search the market", "Beat or match"]) {
    await rig.getByRole("button", { name: label, exact: true }).click();
  }
  assert.match(await rig.locator(".rig-caption").textContent(), /^In the cart/);
  assert(!/quote|payment|accept.*pay/i.test(await rig.textContent()));
  assert.equal(await rig.locator(".rig-price strong").textContent(), "$94");
  await rig.getByRole("button", { name: "Add to cart", exact: true }).click();
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
  for (const width of [320, 375, 390, 430, 431, 600, 767, 768, 1000, 1199, 1200, 1440]) {
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
    {
      const toggleOverflow = await rig.evaluate(section => {
        const right = section.getBoundingClientRect().right - parseFloat(getComputedStyle(section).paddingRight);
        return [...section.querySelectorAll('.rig-switches [role="switch"]')].flatMap(row =>
          [row, ...row.querySelectorAll("*")].flatMap(element => {
            const box = element.getBoundingClientRect();
            const failures = box.right > right + 0.5 ? [`Element outside Rig section: ${element.className || element.tagName}`] : [];
            for (const node of element.childNodes) {
              if (node.nodeType !== Node.TEXT_NODE || !node.textContent.trim()) continue;
              const range = document.createRange();
              range.selectNodeContents(node);
              if (range.getBoundingClientRect().right > right + 0.5) failures.push(`Text outside Rig section: ${node.textContent}`);
              if (parseFloat(getComputedStyle(element).fontSize) < 14) failures.push(`Toggle text below 14px: ${node.textContent}`);
            }
            return failures;
          })
        );
      });
      assert.deepEqual(toggleOverflow, [], `Rig toggle row overflow at ${width}`);
      const tags = rig.locator(".rig-switches .tag.optional");
      assert.equal(await tags.count(), 4);
      for (const tag of await tags.all()) assert(await tag.isVisible(), `Optional tag hidden at ${width}`);
    }
    // Inspect actual text ranges: clipping and mid-word wrapping cannot hide
    // behind scrollWidth or the homepage's overflow:clip.
    const checkDiagramGeometry = async () => page.locator(".engine-interactive, .rig-diagram").evaluateAll(diagrams => {
      const failures = [];
      const visible = el => {
        for (let p = el; p; p = p.parentElement) {
          const style = getComputedStyle(p);
          if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) return false;
        }
        return true;
      };
      for (const diagram of diagrams) {
        const bounds = diagram.getBoundingClientRect();
        const walker = document.createTreeWalker(diagram, NodeFilter.SHOW_TEXT);
        for (let node = walker.nextNode(); node; node = walker.nextNode()) {
          const el = node.parentElement;
          if (!node.textContent.trim() || !visible(el)) continue;
          const parent = el.getBoundingClientRect();
          const range = document.createRange();
          range.selectNodeContents(node);
          const box = range.getBoundingClientRect();
          if (box.left < parent.left - 1 || box.right > parent.right + 1 || box.top < parent.top - 1 || box.bottom > parent.bottom + 1) failures.push("Text outside box: " + node.textContent);
          if (box.left < bounds.left - 1 || box.right > bounds.right + 1) failures.push("Text outside diagram: " + node.textContent);
          if (parseFloat(getComputedStyle(el).fontSize) < 14) failures.push("Text below 14px: " + node.textContent);
          for (const match of node.textContent.matchAll(/[\p{L}\p{N}]+(?:[-’'][\p{L}\p{N}]+)*/gu)) {
            range.setStart(node, match.index); range.setEnd(node, match.index + match[0].length);
            const lines = new Set([...range.getClientRects()].map(r => Math.round(r.top)));
            if (lines.size > 1) failures.push("Broken word: " + match[0]);
          }
        }
      }
      return failures;
    });
    assert.deepEqual(await checkDiagramGeometry(), [], "Diagram text geometry at " + width);
    const shapes = await engineNodes.evaluateAll(nodes => nodes.map(n => {
      const r = n.getBoundingClientRect(); return { top:r.top, bottom:r.bottom, width:r.width, height:r.height };
    }));
    assert.equal(shapes.length, 5);
    shapes.forEach((r, i) => {
      assert(r.width > 0 && r.height > 0, "Engine shape hidden at " + width);
      if (i) assert(r.top >= shapes[i - 1].bottom, "Engine order at " + width);
    });
    for (let stage = 0; stage < 4; stage++) {
      assert.equal(await rig.locator(".rig-diagram").getAttribute("data-stage"), String(stage));
      assert.deepEqual(await checkDiagramGeometry(), [], "Rig state " + stage + " at " + width);
      const product = await rig.locator(".rig-product").boundingBox();
      const market = await rig.locator(".rig-market").boundingBox();
      assert(product.width > 0 && product.height > 0);
      assert(market.y >= product.y + product.height, "Market follows product");
      if (stage > 0) {
        const accessories = await rig.locator('[data-diagram-shape="accessory"]').all();
        assert.equal(accessories.length, 3);
        let previous = -Infinity;
        for (const accessory of accessories) {
          assert(await accessory.isVisible());
          const r = await accessory.boundingBox(); assert(r.y > previous); previous = r.y;
        }
      }
      if (stage >= 2) {
        const overlaps = await rig.locator(".market-rail").evaluate(rail => {
          const labels = [...rail.querySelectorAll(".seller small, .your-price small, .best-market")].map(el => {
            const r = el.getBoundingClientRect(); return { text:el.textContent, x:r.x, y:r.y, right:r.right, bottom:r.bottom };
          });
          return labels.flatMap((a, i) => labels.slice(i + 1).filter(b => Math.min(a.right,b.right) - Math.max(a.x,b.x) > 1 && Math.min(a.bottom,b.bottom) - Math.max(a.y,b.y) > 1).map(b => [a.text,b.text]));
        });
        assert.deepEqual(overlaps, [], "Overlapping market labels at " + width);
      }
      assert(await rig.locator(".rig-controls button").isVisible());
      if ((width === 375 || width === 1440) && (stage === 0 || stage === 3)) await rig.locator(".rig-diagram").screenshot({ path: `${output}/rig-${width}-stage-${stage}.png` });
      await rig.locator(".rig-controls button").click();
    }
    assert.equal(await rig.locator(".rig-diagram").getAttribute("data-stage"), "0");
    if (width === 375 || width === 1440) {
      await page.locator(".engine-interactive").screenshot({ path: `${output}/engine-${width}.png` });
      await page.locator("#engine").screenshot({ path: `${output}/engine-section-${width}.png` });
      await rig.locator(".rig-controls button").click();
      await rig.locator(".rig-controls button").click();
      await rig.locator(".rig-controls button").click();
      await rig.screenshot({ path: `${output}/rig-section-${width}.png` });
      await rig.locator(".rig-controls button").click();
    }
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
  console.log(JSON.stringify({ result: "PASS", widths: [320, 375, 390, 430, 431, 600, 767, 768, 1000, 1199, 1200, 1440], images: assets.length, engineStages: 5, rigStates: 4, switches: 4, receiptRows: 4, csv: "PASS", pdf: "PASS", forms: "saved + failed", javascriptErrors: errors, screenshotDirectory: output }, null, 2));
} finally {
  await browser.close();
}
