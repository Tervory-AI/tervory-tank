// Offline browser proof using rows exported by test_lifecycle.py. No live data or Clerk session.
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../..");
const require = createRequire(join(root, "workspace/package.json"));
const { build } = require(process.env.SKALA_ESBUILD_PATH || "esbuild");
const { chromium } = require(process.env.SKALA_PLAYWRIGHT_PATH || "playwright");

const proof = process.env.SKALA_B3_PROOF_DIR || "/tmp/skala-b3-proof";
const shots = join(proof, "screenshots");
await mkdir(shots, { recursive: true });
const brand = join(root, "workspace/public/brand");
const jost = join(root, "workspace/app/fonts/Jost-300-latin.woff2");

const fixture = JSON.parse(await readFile(join(proof, "skills.json"), "utf8"));
const bundle = await build({
  stdin: {
    contents: `import React from "react"; import { createRoot } from "react-dom/client"; import { SkalaApp } from "./app/skala/view"; import { SquadFounderProvider } from "./app/squad-links"; const skills = ${JSON.stringify(fixture)}; createRoot(document.getElementById("root")).render(<SquadFounderProvider founder={true}><SkalaApp accountName="Offline test" skills={skills} loadError={null} /></SquadFounderProvider>);`,
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
  const actions = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.route("**/*", route => {
    const url = new URL(route.request().url());
    return url.hostname === "127.0.0.1" ? route.continue() : route.abort();
  });
  await page.route("**/api/skala", async route => {
    if (route.request().method() === "GET") return route.fulfill({json: fixture});
    actions.push(route.request().postDataJSON());
    return route.fulfill({json: {ok: true}});
  });
  await page.goto(`http://127.0.0.1:${port}`);
  const failed = page.getByRole("heading", {name: "base.b3", exact: true}).locator("..");
  await failed.getByText("staging", {exact:true}).waitFor();
  await failed.getByText("20%", {exact:true}).waitFor();
  const history = page.getByRole("heading", {name:"base.history",exact:true}).locator("..");
  await history.getByRole("button", {name:"Roll back to 1.0.0"}).waitFor();
  for (const width of [1440, 375]) {
    await page.setViewportSize({width, height: width === 375 ? 812 : 1000});
    if (width === 375) await failed.evaluate(el => el.scrollIntoView({block:"start"}));
    await page.screenshot({path: join(shots, `skala-b3-b4-${width}.png`), fullPage:true});
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
  }
  await history.getByRole("button", {name:"Roll back to 1.0.0"}).click();
  assert.equal(actions.length, 0); // The existing confirmation is still required.
  await page.getByRole("button", {name:"Confirm rollback"}).click();
  await page.waitForFunction(() => !document.querySelector("dialog[open]"));
  assert.ok(actions.some(a => a.action === "rollback" && a.confirmed === true));
  assert.deepEqual(errors, []);
  console.log("PASS: demotion at 20%, probation rollback confirmation, 1440/375px, no overflow or browser errors.");
} finally {
  await browser.close();
  server.close();
}
