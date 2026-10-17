// Runs only in a disposable GitHub Actions runner. Renders the actual Radix component.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { readFile, mkdir, writeFile } from "node:fs/promises";
import { resolve, join } from "node:path";

const require = createRequire(join(process.env.RUNNER_TEMP, "radix-browser/package.json"));
const { build } = require("esbuild");
const { chromium } = require("playwright");
const root = process.cwd();
const output = resolve(process.env.RUNNER_TEMP, "radix-page-site");
await mkdir(output, { recursive: true });
const bundle = await build({
  stdin: {
    contents: 'import React from "react"; import {createRoot} from "react-dom/client"; import {RadixPage} from "./app/radix/view"; createRoot(document.getElementById("root")).render(<RadixPage founder={new URLSearchParams(location.search).has("founder")} />);',
    resolveDir: root, loader: "tsx",
  },
  bundle: true, write: false, format: "iife", jsx: "automatic",
});
const css = (await readFile("app/globals.css", "utf8")) + "\n" + (await readFile("app/radix/radix.css", "utf8"));
const html = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Radix browser test</title><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Jost:wght@300&display=swap" rel="stylesheet"><style>:root{--font-inter:Inter;--font-jost:Jost;--font-mono:monospace}</style><link rel="stylesheet" href="/page.css"></head><body><main><div id="root"></div></main><script src="/page.js"></script></body></html>';
const server = createServer(async (req, res) => {
  if (req.url?.startsWith("/brand/")) {
    res.setHeader("content-type", "image/png");
    res.end(await readFile("public/brand/tervory-logo-reversed.png"));
  } else if (req.url === "/page.js") {
    res.setHeader("content-type", "text/javascript"); res.end(bundle.outputFiles[0].contents);
  } else if (req.url === "/page.css") {
    res.setHeader("content-type", "text/css"); res.end(css);
  } else { res.setHeader("content-type", "text/html"); res.end(html); }
});
await new Promise((done) => server.listen(0, "127.0.0.1", done));
const url = "http://127.0.0.1:" + server.address().port;
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const errors = [];
page.on("pageerror", (error) => errors.push(error.message));
const unexpected = [];
async function screenshot(name) {
  await page.evaluate(() => document.fonts.ready);
  const buffer = await page.screenshot({ path: join(output, name + ".png") });
  const b64 = buffer.toString("base64");
  for (let i = 0; i < b64.length; i += 16000) console.log("RX_IMAGE " + name + " " + (i / 16000) + " " + b64.slice(i, i + 16000));
}
async function noHorizontalOverflow() {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
}
try {
  await page.goto(url + "/?founder=1");
  await page.getByRole("heading", { name: "Radix", exact: true }).waitFor();
  await page.evaluate(() => document.fonts.ready);
  assert.equal(await page.locator(".rx-panel").getByRole("link", { name: "Tank", exact: true }).count(), 1);
  assert.equal(await page.locator(".rx-logo").first().evaluate((img) => img.complete && img.naturalWidth > 0), true);
  await screenshot("desktop-overview");
  await page.setViewportSize({ width: 1440, height: 800 });
  const panelBefore = await page.locator(".rx-panel").boundingBox();
  await page.locator("[data-scroll-root]").evaluate((node) => { node.scrollTop = node.scrollHeight; });
  assert.ok(await page.locator("[data-scroll-root]").evaluate((node) => node.scrollTop > 0));
  assert.deepEqual(await page.locator(".rx-panel").boundingBox(), panelBefore);
  assert.equal(await page.evaluate(() => window.scrollY), 0);
  await noHorizontalOverflow();
  await page.setViewportSize({ width: 1440, height: 1000 });

  // Interactions must not fetch targets, send keys, or create scans.
  page.on("request", (request) => {
    if (!request.url().startsWith(url) && !request.url().startsWith("data:")) unexpected.push(request.url());
  });
  await page.getByRole("button", { name: "View example report", exact: true }).click();
  assert.equal(await page.getByRole("heading", { name: "Example reports" }).count(), 1);
  await page.getByLabel("Severity", { exact: true }).selectOption("Critical");
  assert.equal(await page.locator(".rx-findings article").count(), 1);
  await page.getByText("Review the fix", { exact: true }).click();
  assert.equal(await page.getByText("Keep credentials in the server environment.", { exact: false }).isVisible(), true);
  await page.getByRole("searchbox").fill("no-match");
  await page.getByRole("heading", { name: "No matching example findings" }).waitFor();
  await page.getByRole("button", { name: "Clear filters" }).click();
  assert.equal(await page.locator(".rx-findings article").count(), 3);
  const download = page.getByRole("link", { name: "Download example report" });
  assert.match(decodeURIComponent(await download.getAttribute("href")), /EXAMPLE ONLY/);
  await screenshot("desktop-example-report");
  await page.getByRole("button", { name: "Leave example" }).click();
  await page.getByRole("heading", { name: "Reports are not connected" }).waitFor();

  const sourceButton = page.locator(".rx-panel").getByRole("button", { name: "Sources", exact: true });
  await sourceButton.click();
  const dialog = page.getByRole("dialog", { name: "Sources", exact: true });
  await dialog.waitFor();
  assert.equal(await dialog.locator('input[type="password"]').count(), 0);
  assert.equal(await dialog.getByRole("tabpanel", { name: "API keys" }).getByLabel("Masked example; no credential stored").isVisible(), true);
  await dialog.getByRole("tab", { name: "API keys" }).focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await dialog.getByRole("tab", { name: "Files", selected: true }).count(), 1);
  await page.keyboard.press("End");
  assert.equal(await dialog.getByRole("tab", { name: "MCP connections", selected: true }).count(), 1);
  await screenshot("desktop-sources");
  for (let i = 0; i < 12; i++) {
    await page.keyboard.press("Tab");
    assert.equal(await page.evaluate(() => document.activeElement.closest("dialog")?.open === true), true);
  }
  await page.keyboard.press("Escape");
  assert.equal(await sourceButton.evaluate((node) => node === document.activeElement), true);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  const drawer = page.getByRole("dialog", { name: "Navigation" });
  await drawer.getByRole("button", { name: "Overview", exact: true }).click();
  await screenshot("mobile-overview");
  await noHorizontalOverflow();
  await page.getByRole("button", { name: "Menu", exact: true }).click();
  await drawer.getByRole("button", { name: "Sources", exact: true }).click();
  await dialog.waitFor();
  assert.equal(await drawer.isVisible(), false);
  await dialog.locator(".rx-source-mobile").getByText("Files", { exact: true }).click();
  await dialog.locator(".rx-source-mobile").getByText("Uploads are not connected yet.", { exact: true }).waitFor();
  await screenshot("mobile-sources");
  await dialog.getByRole("button", { name: "Done", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "Menu", exact: true }).evaluate((node) => node === document.activeElement), true);
  await page.setViewportSize({ width: 320, height: 568 });
  await noHorizontalOverflow();
  assert.equal(await page.evaluate(() => window.scrollY), 0);

  await page.goto(url);
  await page.getByRole("heading", { name: "Radix", exact: true }).waitFor();
  assert.equal(await page.locator(".rx-panel").getByRole("link", { name: "Tank", exact: true }).count(), 0);
  assert.equal(await page.locator(".rx-panel").getByRole("link", { name: "Skala", exact: true }).count(), 0);
  // Fonts can reload on navigation; the action audit ends before that navigation.
  assert.deepEqual(errors, []);
  assert.deepEqual(unexpected.filter((value) => !value.startsWith("https://fonts.")), []);
  console.log("PASS: fixed panel, body scroll, examples, filters, downloads, source tabs, keyboard focus, mobile menu, masking, founder navigation and no external action requests.");
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
