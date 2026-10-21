// Renders the Skala library with fixture skills. No Clerk session and no customer data.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(join(root, "workspace/package.json"));
const { build } = require(process.env.SKALA_ESBUILD_PATH || "esbuild");
const { chromium } = require(process.env.SKALA_PLAYWRIGHT_PATH || "playwright");

const shots = join(root, "tests/screenshots/skala-2");
await mkdir(shots, { recursive: true });
const brand = join(root, "workspace/public/brand");
const jost = join(root, "workspace/.next/static/media/eb5d6e6e339da62d-s.p.woff2");

const fixture = [
  { id: "base.find_site", version: "1.8.0", agent: "base", rung: 3, task_type: null, description: "Finds a business website from the name and the city.", state: "staging", last_eval_score: 1, last_eval_at: "2026-10-21T00:00:00Z", present: true },
  { id: "base.learned.example", version: "1.0.0", agent: "base", rung: 3, task_type: null, description: "Room-authored candidate awaiting source review.", state: "staging", last_eval_score: 1, last_eval_at: "2026-10-21T00:00:00Z", present: true },
  { id: "base.find_site", version: "1.7.0", agent: "base", rung: 3, task_type: null, description: "Finds a business website from the name and the city.", state: "approved", last_eval_score: 0.96, last_eval_at: "2026-10-12T00:00:00Z", present: true },
  { id: "base.find_site", approved_at: "2026-09-01T00:00:00Z", version: "1.6.0", agent: "base", rung: 3, task_type: null, description: "Finds a business website from the name and the city.", state: "retired", last_eval_score: 0.91, last_eval_at: "2026-09-02T00:00:00Z", present: true },
  { id: "base.extract", version: "2.0.0", agent: "base", rung: 3, task_type: null, description: "Reads a business page and returns what they sell.", model: true, runs: 3, state: "staging", last_eval_score: 0.98, last_eval_at: "2026-10-18T00:00:00Z", present: true },
  { id: "base.normalize", version: "1.0.0", agent: "base", rung: 3, task_type: null, description: "Cleans a raw business record into canonical fields.", state: "candidate", last_eval_score: null, last_eval_at: null, present: true },
  { id: "tiger.price_extract", version: "1.1.0", agent: "tiger", rung: 3, task_type: null, description: "Reads the prices a page actually shows.", state: "approved", last_eval_score: 1, last_eval_at: "2026-10-01T00:00:00Z", present: true },
  { id: "market.research", version: "1.1.0", agent: "market_lab", rung: 3, task_type: "market.research", description: "A short answer, each claim with a source.", state: "candidate", last_eval_score: null, last_eval_at: null, present: true, calls_30d: 0, avg_cost_usd: null },
  { id: "reason.brief", version: "1.0.0", agent: "tier0", rung: 1, task_type: "reason.brief", description: "Concise structured analysis for a business owner.", state: "approved", last_eval_score: 0.8, last_eval_at: "2026-08-01T00:00:00Z", present: true, calls_30d: 40, avg_cost_usd: 0.0031 },
];

const bundle = await build({
  stdin: {
    contents: `import React from "react"; import { createRoot } from "react-dom/client"; import { SkalaApp } from "./app/skala/view"; import { SquadFounderProvider } from "./app/squad-links"; const skills = ${JSON.stringify(fixture)}; createRoot(document.getElementById("root")).render(<SquadFounderProvider founder={true}><SkalaApp accountName="Northwind" skills={skills} loadError={null} /></SquadFounderProvider>);`,
    resolveDir: join(root, "workspace"),
    loader: "tsx",
  },
  bundle: true,
  write: false,
  format: "iife",
  jsx: "automatic",
  plugins: [{
    name: "next-nav",
    setup(builder) {
      builder.onResolve({ filter: /^next\/navigation$/ }, () => ({ path: "next-navigation", namespace: "mock" }));
      builder.onLoad({ filter: /.*/, namespace: "mock" }, () => ({
        contents: "export function usePathname(){return '/skala'} export function useRouter(){return { refresh(){}, push(){}, replace(){} }}",
        loader: "js",
      }));
    },
  }],
});

const css = await readFile(join(root, "workspace/app/skala/skala.css"), "utf8");
const html = `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Skala</title><style>@font-face{font-family:Jost;font-style:normal;font-weight:300;font-display:swap;src:url(/fonts/jost.woff2) format("woff2")} :root{--font-jost:Jost;--font-inter:Inter;--font-mono:"JetBrains Mono"} body{margin:0}</style><link rel="stylesheet" href="/skala.css"></head><body><div id="root"></div><script src="/page.js"></script></body></html>`;

const files = new Map([
  ["/", html],
  ["/skala.css", css],
  ["/page.js", bundle.outputFiles[0].text],
]);

const server = createServer(async (request, response) => {
  const url = new URL(request.url ?? "/", "http://127.0.0.1");
  if (url.pathname.startsWith("/brand/")) {
    const name = url.pathname.slice("/brand/".length);
    if (!/^[a-z0-9.-]+$/i.test(name)) { response.writeHead(404); response.end(); return; }
    const bytes = await readFile(join(brand, name));
    response.writeHead(200, { "content-type": "image/png" });
    response.end(bytes);
    return;
  }
  if (url.pathname === "/fonts/jost.woff2") {
    const bytes = await readFile(jost);
    response.writeHead(200, { "content-type": "font/woff2" });
    response.end(bytes);
    return;
  }
  const body = files.get(url.pathname);
  if (body === undefined) { response.writeHead(404); response.end(); return; }
  const type = url.pathname.endsWith(".js") ? "text/javascript" : url.pathname.endsWith(".css") ? "text/css" : "text/html";
  response.writeHead(200, { "content-type": type });
  response.end(body);
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const port = server.address().port;
const browser = await chromium.launch({ headless: true, executablePath: process.env.SKALA_CHROMIUM_PATH || "/usr/bin/chromium" });

try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const actions = [];
  await page.route("**/api/skala", async route => {
    if (route.request().method() === "GET") return route.fulfill({json: fixture});
    const body = route.request().postDataJSON();
    actions.push(body);
    if (body.action === "bulk-preview") return route.fulfill({json: {token: "preview-test", items: [{id: "base.find_site", version: "1.8.0"}]}});
    if (body.action === "bulk-confirm") return route.fulfill({json: {ok: true, approved: [{id: "base.find_site", version: "1.8.0"}]}});
    if (body.action === "source-review") return route.fulfill({json: {source: "async def run(payload, ctx):\n    return payload\n# END OF FULL SOURCE", review_token: "source-test"}});
    return route.fulfill({json: {ok: true}});
  });
  await page.goto(`http://127.0.0.1:${port}/`);
  await page.getByRole("heading", { name: "Skala", level: 1 }).waitFor();
  await page.getByRole("heading", { name: "base.find_site" }).waitFor();
  await page.getByText("no model").first().waitFor();
  await page.getByText("uses a model · $0.0031/call (30 days)").waitFor();
  await page.getByText("uses a model · no calls yet").waitFor();
  const colours = await page.evaluate(() => {
    const badge = document.querySelector(".sk-state.approved");
    const button = document.querySelector("button.primary");
    return {
      badge: badge ? getComputedStyle(badge).backgroundColor : "",
      button: button ? getComputedStyle(button).backgroundColor : "",
    };
  });
  assert.notEqual(colours.badge, colours.button);
  assert.notEqual(colours.badge, "rgb(232, 0, 8)");
  assert.equal(await page.getByRole("button", { name: "Transfer" }).count(), 0);
  assert.equal(await page.getByText("This vault is off").count(), 0);
  assert.equal(await page.getByText("Ask Skala").count(), 0);
  await page.getByRole("link", { name: "Check examples" }).waitFor();

  const ratios = await page.evaluate(() => {
    const root = document.querySelector("[data-scroll-root]");
    const pageOverflow = document.documentElement.scrollWidth - window.innerWidth;
    const boxOverflow = root ? root.scrollWidth - root.clientWidth : 0;
    const logos = [...document.images].filter((img) => img.getBoundingClientRect().height > 0).map((img) => {
      const box = img.getBoundingClientRect();
      return {
        src: img.getAttribute("src"),
        height: box.height,
        ratio: box.width / box.height,
        natural: img.naturalWidth / img.naturalHeight,
      };
    });
    return { pageOverflow, boxOverflow, logos };
  });
  assert.ok(ratios.pageOverflow <= 1, `page overflow ${ratios.pageOverflow}`);
  assert.ok(ratios.boxOverflow <= 1, `library overflow ${ratios.boxOverflow}`);
  for (const logo of ratios.logos) {
    assert.ok(Math.abs(logo.ratio - logo.natural) < 0.08, `${logo.src} squeezed ${logo.ratio} vs ${logo.natural}`);
    if (logo.src?.includes("skala-on-dark") || logo.src?.includes("base-on-dark")) {
      assert.ok(logo.height >= 39, `${logo.src} is ${logo.height}px`);
    }
  }

  await page.getByText("uses a model · $0.0031/call (30 days)").scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(shots, "skala-1440.png") });
  await page.evaluate(() => {
    const root = document.querySelector("[data-scroll-root]");
    if (root) root.scrollTop = 0;
  });

  await page.setViewportSize({ width: 375, height: 812 });
  await page.getByRole("button", { name: "Menu" }).click();
  await page.getByRole("link", { name: "Dashboard" }).waitFor();
  assert.equal(await page.getByRole("button", { name: "Close" }).first().getAttribute("aria-expanded"), "true");
  const mobileOpen = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert.ok(mobileOpen <= 1, `open menu overflow ${mobileOpen}`);
  await page.locator("#sk-panel").getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: "Menu" }).waitFor();
  const mobile = await page.evaluate(() => {
    const root = document.querySelector("[data-scroll-root]");
    const search = document.querySelector(".sk-search");
    return {
      pageOverflow: document.documentElement.scrollWidth - window.innerWidth,
      boxOverflow: root ? root.scrollWidth - root.clientWidth : 0,
      searchWidth: search ? search.getBoundingClientRect().width : 0,
      inner: window.innerWidth,
    };
  });
  assert.ok(mobile.pageOverflow <= 1, `mobile overflow ${mobile.pageOverflow}`);
  assert.ok(mobile.boxOverflow <= 1, `mobile library overflow ${mobile.boxOverflow}`);
  assert.ok(mobile.searchWidth >= mobile.inner - 40, `search width ${mobile.searchWidth}`);
  await page.screenshot({ path: join(shots, "skala-375.png") });

  await page.getByLabel("Search skills").fill("price");
  await page.getByRole("heading", { name: "tiger.price_extract" }).waitFor();
  assert.equal(await page.getByRole("heading", { name: "base.find_site" }).count(), 0);
  await page.getByLabel("Search skills").fill("");
  await page.getByLabel("State").selectOption("staging");
  await page.getByRole("heading", {name: "base.extract", exact: true}).locator("..").getByRole("button", { name: "Approve", exact: true }).click();
  await page.getByRole("heading", { name: "Approve base.extract 2.0.0?" }).waitFor();
  await page.getByRole("button", { name: "Cancel" }).click();
  await page.getByLabel("State").selectOption("");
  const findSite = page.getByRole("heading", {name: "base.find_site", exact: true}).locator("..");
  assert.equal(await findSite.getByText("1.6.0", {exact:true}).isVisible(), false);
  await findSite.getByText("History (1)").click();
  await findSite.getByRole("button", {name: "Roll back to 1.6.0"}).click();
  await page.getByRole("button", {name: "Confirm rollback"}).click();
  assert.ok(actions.some(a => a.action === "rollback" && a.confirmed === true));
  await page.getByRole("button", {name: "Approve all ready", exact: true}).click();
  const bulk = page.getByRole("dialog", {name: "Confirm ready versions"});
  await bulk.getByText("base.find_site · 1.8.0").waitFor();
  assert.equal(await bulk.getByText("base.learned.example").count(), 0);
  await bulk.getByRole("button", {name: "Confirm listed approvals"}).click();
  assert.ok(actions.some(a => a.action === "bulk-confirm" && a.token === "preview-test" && a.confirmed === true));
  await page.getByRole("heading", {name: "base.learned.example", exact:true}).locator("..").getByRole("button", {name:"Approve",exact:true}).click();
  await page.getByText("# END OF FULL SOURCE", {exact:false}).waitFor();
  await page.getByRole("dialog").getByRole("button", {name:"Approve",exact:true}).click();
  assert.ok(actions.some(a => a.action === "approve" && a.review_token === "source-test" && a.confirmed === true));
  if (process.env.SKALA_AXE_PATH) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.addScriptTag({ path: process.env.SKALA_AXE_PATH });
    const violations = await page.evaluate(async () => {
      const result = await window.axe.run(document, { resultTypes: ["violations"] });
      return result.violations.map((item) => ({ id: item.id, impact: item.impact, nodes: item.nodes.length }));
    });
    const serious = violations.filter((item) => item.impact === "serious" || item.impact === "critical");
    assert.deepEqual(serious, [], JSON.stringify(violations, null, 2));
  }
  assert.deepEqual(errors, []);
  console.log("Skala library screenshots and checks passed.");
} finally {
  await browser.close();
  server.close();
}
