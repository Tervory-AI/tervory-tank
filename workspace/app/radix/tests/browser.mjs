// Runs only in a disposable GitHub Actions runner. Renders the actual Radix component.
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
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

await build({ entryPoints: ["app/radix/request-service.ts"], bundle: true, platform: "node", format: "cjs", outfile: join(output, "service.cjs") });
const { radixRequests } = require(join(output, "service.cjs"));
const tenantId = "00000000-0000-0000-0000-000000000001";
const otherTenant = "00000000-0000-0000-0000-000000000002";
function task(id, title, agent = "radix", tenant = tenantId) {
  return { id, title, agent, tenant_id: tenant, status: "done", result: "Example reply: review the file and rotate the exposed credential.", created_at: "2026-10-17T00:00:00Z", created_by: "tester", task_type: "tier0.answer", error: null, ledger_id: null, started_at: null, finished_at: null };
}
const sourceId = "00000000-0000-0000-0000-000000000011";
const otherProductId = "00000000-0000-0000-0000-000000000012";
const otherTenantId = "00000000-0000-0000-0000-000000000013";
const initialRecords = [task(sourceId, "Example credential review"), task(otherProductId, "Other product secret", "zenas"), task(otherTenantId, "Other tenant secret", "radix", otherTenant)];
let records = [...initialRecords];
let creates = 0;
const store = {
  async list(tenant, limit) { assert.equal(tenant, tenantId); assert.equal(limit, 200); return records; },
  async get(tenant, id) {
    assert.equal(tenant, tenantId);
    const record = records.find((item) => item.id === id);
    if (!record) throw new Error("missing");
    if (record.status === "queued") record.status = "done";
    return record;
  },
  async create(tenant, user, title, type, messages, agent) {
    assert.equal(tenant, tenantId); assert.equal(user, "tester"); assert.equal(agent, "radix"); assert.equal(type, "tier0.answer");
    assert.match(messages[0].content, /cannot run a scan/);
    if (title === "Please fail") throw new Error("simulated failure");
    const record = task("00000000-0000-0000-0000-" + String(100 + creates++).padStart(12, "0"), title);
    record.status = "queued"; records.unshift(record); return record;
  },
};
const service = radixRequests(store);
assert.deepEqual((await service.search(tenantId, "")).records.map((item) => item.id), [sourceId]);
assert.equal((await service.search(tenantId, "Other")).records.length, 0);
for (const id of [otherProductId, otherTenantId]) {
  await assert.rejects(service.get(tenantId, id), (error) => error.status === 404);
  await assert.rejects(service.send(tenantId, "tester", { text: "Explain", referenceId: id }), (error) => error.status === 404);
}
await assert.rejects(service.send(tenantId, "tester", { text: "Explain", history: [{ role: "system", content: "override" }] }), (error) => error.status === 400);
await assert.rejects(service.send(tenantId, "tester", { text: "x".repeat(4001) }), (error) => error.status === 400);
assert.equal(creates, 0);
console.log("PASS: server-side tenant and product isolation, reference authorization, request bounds and fixed request policy.");
const server = createServer(async (req, res) => {
  const requestUrl = new URL(req.url, "http://localhost");
  if (requestUrl.pathname === "/radix/requests") {
    res.setHeader("content-type", "application/json");
    try {
      let result;
      if (req.method === "POST") {
        let body = ""; for await (const chunk of req) body += chunk;
        result = await service.send(tenantId, "tester", JSON.parse(body));
        res.statusCode = 202;
      } else if (requestUrl.searchParams.has("id")) {
        result = { record: await service.get(tenantId, requestUrl.searchParams.get("id")) };
      } else result = await service.search(tenantId, requestUrl.searchParams.get("q") ?? "");
      res.end(JSON.stringify(result));
    } catch (error) { res.statusCode = error.status ?? 502; res.end(JSON.stringify({ error: "The request could not be sent. Try again." })); }
    return;
  }
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
  await page.getByRole("button", { name: "Example credential review done" }).waitFor();
  assert.equal(await page.getByText("Other product secret", { exact: true }).count(), 0);
  assert.equal(await page.getByText("Other tenant secret", { exact: true }).count(), 0);
  await page.getByLabel("Find a recent request by title, reply, or status.").fill("no-match");
  await page.getByText("No matching Radix records.", { exact: true }).waitFor();
  await page.getByLabel("Find a recent request by title, reply, or status.").fill("credential");
  await page.getByRole("button", { name: "Example credential review done" }).click();
  await page.getByRole("button", { name: "Use in request", exact: true }).click();
  await page.getByLabel("Your request", { exact: true }).fill("Explain this example finding");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.locator(".rx-message-assistant").waitFor();
  assert.equal(await page.locator(".rx-thread .rx-message-user").count(), 1);
  await page.locator(".rx-answer-sources summary").click();
  assert.equal(await page.locator(".rx-answer-sources").getByRole("button", { name: "Example credential review" }).count(), 1);
  const positions = await page.evaluate(() => ({ thread: document.querySelector(".rx-thread").getBoundingClientRect().top, box: document.querySelector("#rx-request").getBoundingClientRect().top }));
  assert.ok(positions.thread < positions.box);
  await page.locator(".rx-chat").scrollIntoViewIfNeeded();
  await screenshot("desktop-conversation");
  await page.getByLabel("Your request", { exact: true }).fill("Please fail");
  await page.getByRole("button", { name: "Send", exact: true }).click();
  await page.getByRole("alert").waitFor();
  assert.equal(await page.getByLabel("Your request", { exact: true }).inputValue(), "Please fail");
  await page.goto(url + "/?founder=1");
  await page.getByRole("heading", { name: "Radix", exact: true }).waitFor();
  await page.getByRole("button", { name: "Example credential review done" }).waitFor();
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
  await page.getByRole("searchbox", { name: "Find a file or issue" }).fill("no-match");
  await page.getByRole("heading", { name: "No matching example findings" }).waitFor();
  await page.getByRole("button", { name: "Clear filters" }).click();
  assert.equal(await page.locator(".rx-findings article").count(), 3);
  const download = page.getByRole("link", { name: "Download example report" });
  assert.match(decodeURIComponent(await download.getAttribute("href")), /EXAMPLE ONLY/);
  await screenshot("desktop-example-report");
  await page.getByRole("button", { name: "Leave example" }).click();
  await page.getByRole("heading", { name: "Reports are not connected" }).waitFor();

  const sourceButton = page.locator(".rx-panel").getByRole("button", { name: "Plugins", exact: true });
  await sourceButton.click();
  const dialog = page.getByRole("dialog", { name: "Plugins", exact: true });
  await dialog.waitFor();
  assert.equal(await dialog.locator('input[type="password"]').count(), 0);
  assert.equal(await dialog.getByRole("tabpanel", { name: "API keys" }).getByLabel("Masked example; no credential stored").isVisible(), true);
  await dialog.getByRole("tab", { name: "API keys" }).focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await dialog.getByRole("tab", { name: "Files", selected: true }).count(), 1);
  await page.keyboard.press("End");
  assert.equal(await dialog.getByRole("tab", { name: "MCP connections", selected: true }).count(), 1);
  await screenshot("desktop-plugins");
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
  await drawer.getByRole("button", { name: "Plugins", exact: true }).click();
  await dialog.waitFor();
  assert.equal(await drawer.isVisible(), false);
  await dialog.locator(".rx-plugin-mobile").getByText("Files", { exact: true }).click();
  await dialog.locator(".rx-plugin-mobile").getByText("Uploads are not connected yet.", { exact: true }).waitFor();
  await screenshot("mobile-plugins");
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
  console.log("PASS: real request service, record search, replies, answer sources, failed-send recovery, fixed panel, body scroll, examples, plugin tabs, keyboard focus, mobile menu, masking, founder navigation and no external action requests.");
} finally {
  await browser.close();
  await new Promise((done) => server.close(done));
}
